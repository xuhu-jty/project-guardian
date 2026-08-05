from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path


PLUGIN_ROOT = Path(os.environ.get("PLUGIN_ROOT") or os.environ.get("CLAUDE_PLUGIN_ROOT") or Path(__file__).parents[1])
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

import project_guardian_core as guardian  # noqa: E402


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="strict", newline="\n")


PATCH_PATH = re.compile(r"^\*\*\* (?:Add|Update|Delete) File:\s*(.+?)\s*$", re.MULTILINE)
MUTATING_GIT = re.compile(r"(?:^|[;&|]\s*)git\s+(?:-[^\s]+\s+)*(merge|commit|cherry-pick|rebase|reset|clean)\b", re.IGNORECASE)
MUTATING_FILE = re.compile(
    r"\b(Set-Content|Add-Content|Out-File|Remove-Item|Move-Item|Copy-Item|New-Item|mkdir|rmdir|del|erase)\b|"
    r"(?:^|[;&|]\s*)(rm|mv|cp|touch|install|sed\s+-i)\b|(?:^|[^<])>>?\s*[^&]",
    re.IGNORECASE,
)


def deny(reason: str) -> int:
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(output, ensure_ascii=False))
    return 0


def _relative_patch_path(raw: str, worktree: str) -> str | None:
    value = raw.strip().strip('"').replace("\\", "/")
    candidate = Path(value)
    if candidate.is_absolute():
        if not guardian._is_within(candidate, worktree):
            return None
        return Path(guardian.normalize_path(candidate)).relative_to(Path(guardian.normalize_path(worktree))).as_posix()
    if any(part == ".." for part in candidate.parts):
        return None
    return candidate.as_posix().removeprefix("./")


def _writer_stage_error(item: dict, session_id: str) -> str | None:
    orchestration = item.get("orchestration") or {}
    if orchestration.get("profile") not in guardian.ADAPTIVE_ORCHESTRATION_PROFILES:
        return None
    active_writers = [
        run
        for run in orchestration.get("runs", [])
        if run.get("stage") in {"execution", "major_fix"} and run.get("status") == "running"
    ]
    if not active_writers:
        return (
            "Project Guardian blocked this edit because no risk-authorized execution or Sol major-fix stage is currently running. "
            "Record the authorized writer stage first."
        )
    writer = active_writers[-1]
    if writer.get("stage") == "execution" and not guardian._run_matches_current_route(item, writer, "execution"):
        return (
            "Project Guardian blocked this edit because the recorded executor belongs to an older, weaker risk route. "
            "Complete the newly required planning stage and record the current route's execution stage first."
        )
    if writer.get("thread_id") != session_id:
        model = guardian.MODEL_LABELS.get(writer.get("model"), writer.get("model", "unknown model"))
        effort = str(writer.get("reasoning_effort") or "").capitalize()
        role = guardian.STAGE_ROLE_LABELS.get(writer.get("stage"), writer.get("stage"))
        label = f"{model} · {effort} {role}"
        return (
            f"Project Guardian blocked this edit because task '{writer.get('thread_id')}' owns the active writer stage "
            f"'{label}'. Planning and review tasks are read-only."
        )
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        cwd = payload.get("cwd") or os.getcwd()
        context = guardian.find_context(cwd)
    except Exception:
        return 0
    if not context:
        return 0
    tool = payload.get("tool_name")
    session_id = str(payload.get("session_id") or "unknown")
    tool_input = payload.get("tool_input") or {}
    if isinstance(tool_input, dict):
        command = str(tool_input.get("command") or tool_input.get("input") or tool_input.get("code") or "")
    else:
        command = str(tool_input)

    if tool in {"Bash", "shell_command", "exec_command", "functions.exec", "exec"}:
        match = MUTATING_GIT.search(command)
        if match and match.group(1).lower() in {"merge", "cherry-pick", "rebase", "reset", "clean"}:
            return deny("Project Guardian blocked a history-changing or destructive Git command. It never merges automatically.")
        patch_like = "*** Begin Patch" in command
        if context["mode"] in {"local", "unbound_worktree"} and (match or MUTATING_FILE.search(command) or patch_like):
            reason = (
                "Project Guardian blocks changes in an unbound Codex worktree. Bind it to a work item first."
                if context["mode"] == "unbound_worktree"
                else "Project Guardian blocks changes in the registered local checkout. Use a bound Codex worktree."
            )
            return deny(reason)
        direct_file_mutation = bool(MUTATING_FILE.search(command))
        if context["mode"] == "worktree" and direct_file_mutation and not patch_like:
            return deny(
                "Project Guardian blocked a direct shell file mutation. Use apply_patch so task ownership and file scope can be verified."
            )
        if patch_like:
            tool = "apply_patch"
        else:
            return 0

    direct_paths: list[str] = []
    if tool in {"Edit", "Write"} and isinstance(tool_input, dict):
        direct_path = tool_input.get("file_path") or tool_input.get("path")
        if direct_path:
            direct_paths = [str(direct_path)]
    elif tool != "apply_patch":
        return 0
    if context["mode"] in {"local", "unbound_worktree"}:
        reason = (
            "Project Guardian blocks edits in an unbound Codex worktree. Bind it to a work item first."
            if context["mode"] == "unbound_worktree"
            else "Project Guardian blocks direct edits in the registered local checkout. Use a bound Codex worktree."
        )
        return deny(reason)

    item = context["item"]
    worktree = item["worktree_path"]
    writer_error = _writer_stage_error(item, session_id)
    if writer_error:
        return deny(writer_error)
    paths = direct_paths or PATCH_PATH.findall(command)
    if not paths:
        return deny("Project Guardian could not determine which files this patch changes.")
    denied = []
    for raw in paths:
        relative = _relative_patch_path(raw, worktree)
        if relative is None:
            denied.append(raw.strip())
            continue
        allowed, _ = guardian.scope_allows(item, relative)
        if not allowed:
            denied.append(relative)
    if denied:
        return deny(
            "Project Guardian blocked files outside the declared work-item scope: " + ", ".join(sorted(set(denied)))
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
