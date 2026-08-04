from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path


PLUGIN_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

import project_guardian_core as guardian  # noqa: E402


def git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def initialize_repo(root: Path) -> None:
    root.mkdir()
    git(root, "init", "-b", "main")
    git(root, "config", "user.email", "guardian@example.test")
    git(root, "config", "user.name", "Guardian Test")
    (root / "App.csproj").write_text('<Project Sdk="Microsoft.NET.Sdk"></Project>\n', encoding="utf-8")
    (root / "src").mkdir()
    (root / "src" / "Engine.cs").write_text(
        "public class Engine {\n    public string Choose(string hand, int rule) { return hand; }\n}\n",
        encoding="utf-8",
    )
    git(root, "add", ".")
    git(root, "commit", "-m", "baseline")


class GuardianWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.data = self.base / "guardian-data"
        self.repo = self.base / "repo"
        self.worktrees: list[Path] = []
        os.environ["PROJECT_GUARDIAN_DATA"] = str(self.data)
        initialize_repo(self.repo)

    def tearDown(self) -> None:
        for worktree in reversed(self.worktrees):
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(worktree)],
                cwd=self.repo,
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        os.environ.pop("PROJECT_GUARDIAN_DATA", None)
        self.temporary.cleanup()

    def add_codex_worktree(self) -> Path:
        path = self.base / f"codex-{uuid.uuid4().hex[:6]}"
        git(self.repo, "worktree", "add", "--detach", str(path), "main")
        self.worktrees.append(path)
        return path

    def onboard(self, test_commands: list[str] | None = None) -> dict:
        guardian.project_init(str(self.repo), name="Test project", test_commands=test_commands or [])
        return guardian.scan_project(str(self.repo))

    def create_candidate(self, title: str = "Change engine behavior") -> tuple[dict, Path]:
        self.onboard()
        item = guardian.create_work_item(
            str(self.repo),
            title=title,
            original_request="Change the engine without breaking the reader",
            goal="Update the engine behavior",
            kind="feature",
            acceptance_criteria=["Engine output changes as requested"],
            non_goals=["Do not change the reader"],
            protected_behaviors=["Existing reader remains compatible"],
        )
        route = guardian.assess_work_item_risk(
            str(self.repo),
            item["id"],
            signals=["single_module_change"],
            summary="Localized feature in one known module; use the standard route",
        )
        self.assertEqual("standard", route["route"]["level"])
        guardian.record_task_stage(
            str(self.repo),
            item["id"],
            stage="planning",
            thread_id=f"terra-plan-{uuid.uuid4().hex}",
            model="gpt-5.6-terra",
            reasoning_effort="high",
            status="completed",
            summary="Terra plan covers scope, tests, risks, and protected behavior",
            outcome="ready",
            artifact="guardian://test-plan",
        )
        worktree = self.add_codex_worktree()
        executor_thread = f"luna-exec-{uuid.uuid4().hex}"
        guardian.bind_work_item(
            str(self.repo),
            item["id"],
            thread_id=executor_thread,
            worktree_path=str(worktree),
            host_id="local",
        )
        guardian.record_task_stage(
            str(self.repo),
            item["id"],
            stage="execution",
            thread_id=executor_thread,
            model="gpt-5.6-luna",
            reasoning_effort="xhigh",
            status="running",
            summary="Standard-route Luna implementation started",
        )
        guardian.set_change_scope(
            str(self.repo),
            item["id"],
            allowed_changes=[{"path": "src/**", "reason": "Implements the requested engine behavior"}],
            impacted_nodes=["module:App"],
        )
        return item, worktree

    def complete_standard_model_pipeline(self, item: dict) -> None:
        stored = guardian.get_work_item(str(self.repo), item["id"])
        executor_thread = stored["task"]["thread_id"]
        guardian.record_task_stage(
            str(self.repo),
            item["id"],
            stage="execution",
            thread_id=executor_thread,
            model="gpt-5.6-luna",
            reasoning_effort="xhigh",
            status="completed",
            summary="Standard-route Luna implementation and planned checks completed",
            outcome="implemented",
        )
        guardian.record_task_stage(
            str(self.repo),
            item["id"],
            stage="review",
            thread_id=f"terra-review-{uuid.uuid4().hex}",
            model="gpt-5.6-terra",
            reasoning_effort="high",
            status="completed",
            summary="Independent Terra review passed against the current fingerprint",
            outcome="passed",
        )

    def run_guard_hook(
        self, cwd: Path, tool_name: str, command: str, session_id: str | None = None
    ) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["PLUGIN_ROOT"] = str(PLUGIN_ROOT)
        environment["PROJECT_GUARDIAN_DATA"] = str(self.data)
        context = guardian.find_context(str(cwd))
        if session_id is None and context and context.get("mode") == "worktree":
            session_id = (context["item"].get("task") or {}).get("thread_id")
        payload = {
            "session_id": session_id or "test-session",
            "cwd": str(cwd),
            "hook_event_name": "PreToolUse",
            "tool_name": tool_name,
            "tool_input": {"command": command},
        }
        return subprocess.run(
            [sys.executable, str(PLUGIN_ROOT / "hooks" / "guard_tool.py")],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=environment,
            check=True,
        )

    def test_scan_persists_modules_symbols_and_worktrees(self) -> None:
        result = self.onboard()
        self.assertTrue(result["onboarding"]["can_start_work"])
        project_map = guardian.get_project_map(str(self.repo))
        self.assertEqual("main", project_map["onboarding"]["canonical_base"]["ref"])
        self.assertEqual(1, project_map["graph_summary"]["modules"])
        module = guardian.get_module_map(str(self.repo), "module:App")
        choose = next(symbol for symbol in module["symbols"] if symbol["name"] == "Choose")
        self.assertEqual(["hand", "rule"], choose["parameters"])
        search = guardian.search_code_graph(str(self.repo), "Choose")
        self.assertEqual("symbol", search["matches"][0]["type"])
        branch = guardian.get_branch_map(str(self.repo), "main")
        self.assertEqual("baseline", branch["branch"]["last_commit_subject"])
        self.assertTrue(branch["branch"]["top_areas"])

    def test_dashboard_explains_how_to_reopen_and_offers_one_next_step(self) -> None:
        self.onboard()
        dashboard = guardian.get_project_dashboard(str(self.repo))
        self.assertEqual("可以开发，但有基线警告", dashboard["state"]["status_label"])
        self.assertEqual("start-request", dashboard["next_step"]["primary_action"]["id"])
        self.assertEqual("打开项目图", dashboard["next_step"]["reopen"]["phrase"])
        self.assertIn("回复下方", dashboard["next_step"]["reopen"]["instruction"])
        self.assertEqual(3, len(dashboard["how_to_use"]))
        self.assertEqual(1, dashboard["metrics"]["branches"])

    def test_single_greenfield_code_line_is_selected_as_baseline(self) -> None:
        repo = self.base / "greenfield"
        repo.mkdir()
        git(repo, "init", "-b", "main")
        git(repo, "config", "user.email", "guardian@example.test")
        git(repo, "config", "user.name", "Guardian Test")
        (repo / "README.md").write_text("# New project\n", encoding="utf-8")
        git(repo, "add", ".")
        git(repo, "commit", "-m", "greenfield baseline")
        guardian.project_init(str(repo), name="Greenfield")
        result = guardian.scan_project(str(repo))
        self.assertTrue(result["onboarding"]["can_start_work"])
        self.assertEqual("main", result["onboarding"]["canonical_base"]["ref"])

    def test_empty_default_with_similar_code_branches_needs_base_selection(self) -> None:
        repo = self.base / "ambiguous"
        repo.mkdir()
        git(repo, "init", "-b", "main")
        git(repo, "config", "user.email", "guardian@example.test")
        git(repo, "config", "user.name", "Guardian Test")
        (repo / ".gitignore").write_text("bin/\n", encoding="utf-8")
        git(repo, "add", ".")
        git(repo, "commit", "-m", "empty main")
        for branch_name, project_name in (("feature/a", "A"), ("feature/b", "B")):
            git(repo, "checkout", "main")
            git(repo, "checkout", "-b", branch_name)
            (repo / f"{project_name}.csproj").write_text("<Project></Project>\n", encoding="utf-8")
            (repo / f"{project_name}.cs").write_text(f"public class {project_name} {{}}\n", encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-m", f"add {project_name}")
        git(repo, "checkout", "main")
        guardian.project_init(str(repo), name="Ambiguous")
        result = guardian.scan_project(str(repo))
        self.assertEqual("needs_base_selection", result["onboarding"]["status"])
        dashboard = guardian.get_project_dashboard(str(repo))
        self.assertEqual("review-base", dashboard["next_step"]["primary_action"]["id"])
        self.assertEqual("让 Codex 判断真实基线", dashboard["next_step"]["primary_action"]["label"])
        with self.assertRaises(guardian.GuardianError):
            guardian.create_work_item(
                str(repo),
                title="Unsafe feature",
                original_request="Add feature",
                goal="Add feature",
                kind="feature",
                acceptance_criteria=["Works"],
                non_goals=["No migration"],
                protected_behaviors=["Existing behavior"],
            )

    def test_missing_test_target_blocks_onboarding(self) -> None:
        result = self.onboard(["dotnet test Missing.sln"])
        self.assertEqual("blocked", result["onboarding"]["status"])
        self.assertFalse(result["onboarding"]["can_start_work"])

    def test_registered_test_requires_recorded_validation(self) -> None:
        result = self.onboard(["dotnet test App.csproj"])
        self.assertEqual("needs_test_validation", result["onboarding"]["status"])
        ready = guardian.record_project_validation(
            str(self.repo), "dotnet test App.csproj", True, "Command exited 0 with one passing test"
        )
        self.assertEqual("ready", ready["status"])

    def test_codex_worktree_binding_prevents_second_worktree(self) -> None:
        item, worktree = self.create_candidate()
        prepared = guardian.prepare_worktree(str(self.repo), item["id"])
        self.assertTrue(prepared["reused"])
        self.assertEqual(str(worktree.resolve()), prepared["worktree_path"])

    def test_merge_gate_accepts_fresh_complete_evidence(self) -> None:
        item, worktree = self.create_candidate()
        guardian.record_evidence(str(self.repo), item["id"], "baseline", True, "Baseline passed", "test baseline")
        (worktree / "src" / "Engine.cs").write_text(
            "public class Engine { public string Choose(string hand, int rule) => hand + rule; }\n",
            encoding="utf-8",
        )
        scan = guardian.scan_changes(str(self.repo), item["id"])
        self.assertEqual([], scan["orphan_changes"])
        self.assertEqual([], scan["unexpected_impacted_nodes"])
        for kind in ("target", "related", "full", "independent_review", "integration"):
            guardian.record_evidence(str(self.repo), item["id"], kind, True, f"{kind} passed", f"run {kind}")
        self.complete_standard_model_pipeline(item)
        readiness = guardian.check_merge_readiness(str(self.repo), item["id"])
        self.assertTrue(readiness["ready"], readiness["blockers"])
        dashboard = guardian.get_project_dashboard(str(self.repo))
        self.assertEqual("review-merge", dashboard["next_step"]["primary_action"]["id"])
        self.assertTrue(dashboard["next_step"]["primary_action"]["requires_confirmation"])
        git(worktree, "add", ".")
        git(worktree, "commit", "-m", "candidate")
        candidate_commit = git(worktree, "rev-parse", "HEAD")
        git(self.repo, "merge", "--ff-only", candidate_commit)
        completion = guardian.complete_work_item(
            str(self.repo), item["id"], candidate_commit, "Merged after user confirmation"
        )
        self.assertEqual(candidate_commit, completion["merge_commit"])

    def test_orphan_change_blocks_merge(self) -> None:
        item, worktree = self.create_candidate()
        (worktree / "outside.txt").write_text("unexpected\n", encoding="utf-8")
        scan = guardian.scan_changes(str(self.repo), item["id"])
        self.assertEqual(["outside.txt"], scan["orphan_changes"])
        readiness = guardian.check_merge_readiness(str(self.repo), item["id"])
        self.assertIn("scope", {entry["gate"] for entry in readiness["blockers"]})

    def test_parallel_scope_conflict_is_persisted(self) -> None:
        first, _ = self.create_candidate("First change")
        second = guardian.create_work_item(
            str(self.repo),
            title="Second change",
            original_request="Change the same engine in another way",
            goal="Second engine outcome",
            kind="feature",
            acceptance_criteria=["Second outcome works"],
            non_goals=["Do not change storage"],
            protected_behaviors=["First behavior remains stable"],
        )
        second_tree = self.add_codex_worktree()
        guardian.bind_work_item(str(self.repo), second["id"], "thread-second", str(second_tree))
        scope = guardian.set_change_scope(
            str(self.repo),
            second["id"],
            allowed_changes=[{"path": "src/Engine.cs", "reason": "Second outcome"}],
            impacted_nodes=["module:App"],
        )
        self.assertTrue(scope["blocked"])
        self.assertEqual(first["id"], scope["conflicts"][0]["item_id"])

    def test_risk_assessment_selects_low_standard_and_high_routes(self) -> None:
        self.onboard()
        low = guardian.create_work_item(
            str(self.repo), "Update developer notes", "Clarify setup notes", "Improve developer notes", "maintenance",
            ["Notes are accurate"], ["No runtime changes"], ["Runtime behavior is unchanged"],
        )
        low_route = guardian.assess_work_item_risk(
            str(self.repo), low["id"], ["test_or_docs_only", "localized_change"], "Documentation-only maintenance"
        )["route"]
        self.assertEqual("low", low_route["level"])
        self.assertEqual(("gpt-5.6-terra", "medium"), guardian._expected_stage_model(guardian.get_work_item(str(self.repo), low["id"]), "planning"))
        self.assertEqual(("gpt-5.6-luna", "high"), guardian._expected_stage_model(guardian.get_work_item(str(self.repo), low["id"]), "execution"))

        standard = guardian.create_work_item(
            str(self.repo), "Add one option", "Add one engine option", "Support the option", "feature",
            ["Option works"], ["No new protocol"], ["Existing output remains compatible"],
        )
        standard_route = guardian.assess_work_item_risk(
            str(self.repo), standard["id"], ["single_module_change"], "One-module feature"
        )["route"]
        self.assertEqual("standard", standard_route["level"])
        self.assertEqual("gpt-5.6-terra", standard_route["stages"][0]["model"])
        self.assertEqual("high", standard_route["stages"][0]["reasoning_effort"])

        high = guardian.create_work_item(
            str(self.repo), "Replace architecture", "Replace the engine architecture", "Create new boundaries", "architecture",
            ["New architecture works"], ["No unplanned migration"], ["Compatibility is preserved"],
        )
        high_route = guardian.assess_work_item_risk(
            str(self.repo), high["id"], ["architecture_change", "cross_module_change"], "Architecture crosses modules"
        )["route"]
        self.assertEqual("high", high_route["level"])
        self.assertEqual("judgment", high_route["execution_track"])
        self.assertEqual("gpt-5.6-sol", high_route["stages"][0]["model"])
        self.assertEqual("gpt-5.6-terra", high_route["stages"][1]["model"])

    def test_low_risk_documentation_diff_uses_proportionate_evidence(self) -> None:
        item = {
            "orchestration": {
                "risk_assessment": {"assessed": True, "level": "low"},
            }
        }
        self.assertEqual(
            ["target", "independent_review"],
            guardian._required_evidence_kinds(item, {"changed_files": ["README.md", "docs/setup.rst"]}),
        )
        self.assertEqual(
            ["target", "related", "full", "independent_review", "integration"],
            guardian._required_evidence_kinds(item, {"changed_files": ["tests/EngineTests.cs"]}),
        )

    def test_model_stage_requires_automatic_risk_assessment(self) -> None:
        self.onboard()
        item = guardian.create_work_item(
            str(self.repo), "Unassessed feature", "Add a feature", "Add a feature", "feature",
            ["Feature works"], ["No migration"], ["Existing behavior remains"],
        )
        with self.assertRaisesRegex(guardian.GuardianError, "Assess"):
            guardian.record_task_stage(
                str(self.repo), item["id"], "planning", "planner",
                "gpt-5.6-terra", "high", "completed", "Plan", "ready"
            )

    def test_adaptive_pipeline_enforces_roles_independence_and_major_bug_route(self) -> None:
        item, worktree = self.create_candidate()
        stored = guardian.get_work_item(str(self.repo), item["id"])
        executor_thread = stored["task"]["thread_id"]
        with self.assertRaises(guardian.GuardianError):
            guardian.record_task_stage(
                str(self.repo), item["id"], "execution", executor_thread,
                "gpt-5.6-sol", "xhigh", "completed", "Wrong executor", "implemented"
            )
        with self.assertRaises(guardian.GuardianError):
            guardian.record_task_stage(
                str(self.repo), item["id"], "execution", executor_thread,
                "gpt-5.6-luna", "high", "completed", "Insufficient reasoning", "implemented"
            )
        with self.assertRaises(guardian.GuardianError):
            guardian.record_task_stage(
                str(self.repo), item["id"], "review", "sol-review-early",
                "gpt-5.6-terra", "high", "completed", "Too early", "passed"
            )
        guardian.record_task_stage(
            str(self.repo), item["id"], "execution", executor_thread,
            "gpt-5.6-luna", "xhigh", "completed", "Implementation ready", "implemented"
        )
        with self.assertRaises(guardian.GuardianError):
            guardian.record_task_stage(
                str(self.repo), item["id"], "review", executor_thread,
                "gpt-5.6-terra", "high", "completed", "Self review", "passed"
            )
        guardian.record_task_stage(
            str(self.repo), item["id"], "review", "terra-review-major",
            "gpt-5.6-terra", "high", "completed", "Public contract regression", "major_bug"
        )
        with self.assertRaises(guardian.GuardianError):
            guardian.record_task_stage(
                str(self.repo), item["id"], "major_fix", "luna-fixer",
                "gpt-5.6-luna", "xhigh", "completed", "Wrong fixer", "fixed"
            )
        guardian.record_task_stage(
            str(self.repo), item["id"], "major_fix", "sol-major-fixer",
            "gpt-5.6-sol", "xhigh", "completed", "Major regression fixed", "fixed"
        )
        with self.assertRaises(guardian.GuardianError):
            guardian.record_task_stage(
                str(self.repo), item["id"], "final_review", "sol-major-fixer",
                "gpt-5.6-sol", "xhigh", "completed", "Fixer self review", "passed"
            )
        orchestration = guardian.record_task_stage(
            str(self.repo), item["id"], "final_review", "sol-final-review",
            "gpt-5.6-sol", "xhigh", "completed", "Fresh independent review passed", "passed"
        )
        self.assertEqual("adaptive-risk-v1", orchestration["profile"])
        self.assertEqual("final_review", orchestration["runs"][-1]["stage"])

    def test_merge_is_blocked_without_completed_model_pipeline(self) -> None:
        item, _ = self.create_candidate()
        readiness = guardian.check_merge_readiness(str(self.repo), item["id"])
        reasons = [entry["reason"] for entry in readiness["blockers"] if entry["gate"] == "model_orchestration"]
        self.assertTrue(any("gpt-5.6-luna" in reason for reason in reasons))
        self.assertTrue(any("gpt-5.6-terra" in reason for reason in reasons))

    def test_three_failures_trigger_architecture_review(self) -> None:
        item, worktree = self.create_candidate()
        for number in range(3):
            result = guardian.record_attempt(str(self.repo), item["id"], False, f"attempt {number + 1} failed")
        self.assertTrue(result["architecture_review_required"])
        self.assertEqual("architecture_review", result["status"])
        self.assertEqual("high", result["risk_route"]["level"])
        self.assertEqual("judgment", result["risk_route"]["execution_track"])
        self.assertTrue(result["fingerprint"])
        stored = guardian.get_work_item(str(self.repo), item["id"])
        with self.assertRaisesRegex(guardian.GuardianError, "gpt-5.6-terra"):
            guardian.record_task_stage(
                str(self.repo), item["id"], "execution", stored["task"]["thread_id"],
                "gpt-5.6-luna", "xhigh", "completed", "Old route cannot continue", "implemented"
            )
        patch = "*** Begin Patch\n*** Update File: src/Engine.cs\n*** End Patch"
        blocked = self.run_guard_hook(worktree, "apply_patch", patch)
        self.assertIn("older, weaker risk route", json.loads(blocked.stdout)["hookSpecificOutput"]["permissionDecisionReason"])

    def test_question_does_not_receive_worktree(self) -> None:
        guardian.project_init(str(self.repo))
        item = guardian.create_work_item(
            str(self.repo),
            title="Explain current behavior",
            original_request="Why does this happen?",
            goal="Explain the observed behavior",
            kind="question",
            acceptance_criteria=["Provide a reproducible explanation"],
            non_goals=["Do not change code"],
            protected_behaviors=["Repository remains unchanged"],
        )
        with self.assertRaises(guardian.GuardianError):
            guardian.prepare_worktree(str(self.repo), item["id"])

    def test_hook_blocks_local_and_unbound_but_allows_scoped_tree(self) -> None:
        item, worktree = self.create_candidate()
        patch = "*** Begin Patch\n*** Update File: src/Engine.cs\n*** End Patch"
        local = self.run_guard_hook(self.repo, "apply_patch", patch)
        self.assertEqual("deny", json.loads(local.stdout)["hookSpecificOutput"]["permissionDecision"])
        allowed = self.run_guard_hook(worktree, "apply_patch", patch)
        self.assertEqual("", allowed.stdout)
        unbound = self.add_codex_worktree()
        blocked = self.run_guard_hook(unbound, "apply_patch", patch)
        self.assertIn("unbound", json.loads(blocked.stdout)["hookSpecificOutput"]["permissionDecisionReason"])
        reviewer = self.run_guard_hook(worktree, "apply_patch", patch, session_id="sol-review-task")
        self.assertIn("read-only", json.loads(reviewer.stdout)["hookSpecificOutput"]["permissionDecisionReason"])
        direct_write = self.run_guard_hook(
            worktree, "shell_command", "Set-Content -LiteralPath src/Engine.cs -Value changed"
        )
        self.assertIn("direct shell file mutation", json.loads(direct_write.stdout)["hookSpecificOutput"]["permissionDecisionReason"])
        stored = guardian.get_work_item(str(self.repo), item["id"])
        self.assertEqual(stored["task"]["thread_id"], guardian.find_context(str(worktree))["item"]["task"]["thread_id"])

    def test_v1_state_migrates_without_losing_commands(self) -> None:
        guardian.project_init(str(self.repo), test_commands=["dotnet test App.csproj"])
        path = guardian._project_file(str(self.repo))
        state = json.loads(path.read_text(encoding="utf-8"))
        state["schema_version"] = 1
        state.pop("settings", None)
        state.pop("onboarding", None)
        state.pop("inventory", None)
        state["architecture"].pop("graph", None)
        path.write_text(json.dumps(state), encoding="utf-8")
        migrated = guardian.project_init(str(self.repo))
        self.assertEqual(4, migrated["schema_version"])
        self.assertEqual("adaptive-risk-v1", migrated["settings"]["model_orchestration_profile"])
        self.assertEqual(["dotnet test App.csproj"], migrated["test_commands"])


class McpProtocolTests(unittest.TestCase):
    def test_utf8_map_round_trip_under_non_utf8_console_setting(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            repo = base / "repo"
            initialize_repo(repo)
            environment = os.environ.copy()
            environment["PROJECT_GUARDIAN_DATA"] = str(base / "data")
            environment["PYTHONIOENCODING"] = "cp936"
            old = os.environ.get("PROJECT_GUARDIAN_DATA")
            os.environ["PROJECT_GUARDIAN_DATA"] = environment["PROJECT_GUARDIAN_DATA"]
            try:
                guardian.project_init(str(repo), name="中文项目")
                guardian.scan_project(str(repo))
                item = guardian.create_work_item(
                    str(repo), "普通功能", "增加普通功能", "完成普通功能", "feature",
                    ["功能可用"], ["不改协议"], ["现有行为保持兼容"],
                )
            finally:
                if old is None:
                    os.environ.pop("PROJECT_GUARDIAN_DATA", None)
                else:
                    os.environ["PROJECT_GUARDIAN_DATA"] = old
            requests = "\n".join(
                [
                    json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}}),
                    json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "guardian_health", "arguments": {"project_root": str(repo)}}}),
                    json.dumps({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "get_project_map", "arguments": {"project_root": str(repo)}}}),
                    json.dumps({"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "get_project_dashboard", "arguments": {"project_root": str(repo)}}}),
                    json.dumps({"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "assess_work_item_risk", "arguments": {"project_root": str(repo), "item_id": item["id"], "signals": ["single_module_change"], "summary": "单模块普通功能"}}}),
                    json.dumps({"jsonrpc": "2.0", "id": 6, "method": "tools/list", "params": {}}),
                    "",
                ]
            )
            completed = subprocess.run(
                [sys.executable, str(PLUGIN_ROOT / "scripts" / "project_guardian_mcp.py")],
                input=requests,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=environment,
                check=True,
            )
            messages = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
            self.assertEqual("0.3.0", messages[0]["result"]["serverInfo"]["version"])
            self.assertTrue(messages[1]["result"]["structuredContent"]["ok"])
            project_map = messages[2]["result"]["structuredContent"]
            self.assertEqual("中文项目", project_map["name"])
            self.assertIn("项目接入", project_map["mermaid"])
            self.assertEqual("打开项目图", project_map["guardian_guidance"]["reopen"]["phrase"])
            dashboard = messages[3]["result"]["structuredContent"]
            self.assertEqual("continue-work-item", dashboard["next_step"]["primary_action"]["id"])
            route = messages[4]["result"]["structuredContent"]["route"]
            self.assertEqual("standard", route["level"])
            self.assertEqual("gpt-5.6-terra", route["stages"][0]["model"])
            tool_names = {tool["name"] for tool in messages[5]["result"]["tools"]}
            self.assertIn("assess_work_item_risk", tool_names)


if __name__ == "__main__":
    unittest.main()
