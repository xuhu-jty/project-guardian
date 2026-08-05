from __future__ import annotations

import json
import sys
import traceback
from typing import Any, Callable

import project_guardian_core as guardian


SERVER_NAME = "project-guardian"
SERVER_VERSION = "0.5.0"
SERVER_INSTRUCTIONS = "Use Project Guardian before editing registered projects. Automatically route new projects and feature ideas into requirement discovery: inspect known project facts first, ask only one consequential question at a time, compare meaningful approaches without defaulting to an MVP, recommend the best fit, and ask the user only when a material trade-off or low confidence remains. Persist one reviewed requirement/design contract before planning can become ready or a worktree can bind. Route models automatically; every Luna stage uses max by default with an explicit xhigh capability fallback only when max is unavailable. Use Sol max for high-risk planning and major-bug repair, then fresh Sol xhigh for high-risk review. Reuse compact context and fingerprint evidence. Before every final reply, call get_project_closeout and render its compact project map. Never merge automatically."


def _configure_stdio() -> None:
    # MCP stdio is UTF-8 regardless of the active Windows console code page.
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8", errors="strict")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="strict", newline="\n", line_buffering=True)
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace", newline="\n", line_buffering=True)


_configure_stdio()


def _schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


STRING_LIST = {"type": "array", "items": {"type": "string"}}
CONTRACT_UPDATES = _schema(
    {
        "problem_statement": {"type": "string"},
        "goal": {"type": "string"},
        "stakeholders": STRING_LIST,
        "user_scenarios": STRING_LIST,
        "current_state": {"type": "string"},
        "functional_requirements": STRING_LIST,
        "quality_requirements": STRING_LIST,
        "constraints": STRING_LIST,
        "preferences": STRING_LIST,
        "assumptions": STRING_LIST,
        "acceptance_criteria": STRING_LIST,
        "non_goals": STRING_LIST,
        "protected_behaviors": STRING_LIST,
    }
)
QUESTION_OPTION = _schema(
    {
        "id": {"type": "string"},
        "label": {"type": "string"},
        "description": {"type": "string"},
        "recommended": {"type": "boolean"},
    },
    ["id", "label", "description"],
)
REQUIREMENT_QUESTION = _schema(
    {
        "dimension": {"type": "string"},
        "prompt": {"type": "string"},
        "reason": {"type": "string"},
        "options": {"type": "array", "items": QUESTION_OPTION},
    },
    ["dimension", "prompt", "reason"],
)
SOLUTION_APPROACH = _schema(
    {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "summary": {"type": "string"},
        "fit_score": {"type": "integer", "minimum": 0, "maximum": 10},
        "effort": {"type": "string"},
        "risk": {"type": "string"},
        "pros": STRING_LIST,
        "cons": STRING_LIST,
        "reuses": STRING_LIST,
    },
    ["id", "name", "summary", "fit_score", "effort", "risk", "pros", "cons"],
)
DESIGN_REVIEW_SCORES = _schema(
    {
        "completeness": {"type": "integer", "minimum": 0, "maximum": 10},
        "consistency": {"type": "integer", "minimum": 0, "maximum": 10},
        "clarity": {"type": "integer", "minimum": 0, "maximum": 10},
        "scope": {"type": "integer", "minimum": 0, "maximum": 10},
        "feasibility": {"type": "integer", "minimum": 0, "maximum": 10},
    },
    ["completeness", "consistency", "clarity", "scope", "feasibility"],
)


TOOLS = [
    {
        "name": "guardian_health",
        "description": "Fast MCP and state health check. Call once before project operations and do not retry a failed transport in the same task.",
        "inputSchema": _schema({"project_root": {"type": "string"}}),
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "project_init",
        "description": "Initialize durable Project Guardian state for a Git repository. Read/write local guardian state but does not modify repository files.",
        "inputSchema": _schema(
            {
                "project_root": {"type": "string", "description": "Any path inside the Git repository"},
                "name": {"type": "string"},
                "test_commands": STRING_LIST,
            },
            ["project_root"],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True},
    },
    {
        "name": "list_guarded_projects",
        "description": "List projects already initialized in Project Guardian.",
        "inputSchema": _schema({}),
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "scan_project",
        "description": "Scan Git branches, existing worktrees, the canonical committed code line, modules, files, symbols, parameters, and registered test targets into durable Guardian state. Does not modify repository files.",
        "inputSchema": _schema(
            {
                "project_root": {"type": "string"},
                "canonical_ref": {"type": "string", "description": "Optional explicit branch, tag, or commit to scan as the canonical base"},
            },
            ["project_root"],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True},
    },
    {
        "name": "select_project_base",
        "description": "Select and rescan the repository's canonical committed code line with a recorded reason.",
        "inputSchema": _schema(
            {
                "project_root": {"type": "string"},
                "base_ref": {"type": "string"},
                "reason": {"type": "string"},
            },
            ["project_root", "base_ref", "reason"],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False},
    },
    {
        "name": "record_project_validation",
        "description": "Record the raw outcome of a registered baseline command against the selected canonical commit.",
        "inputSchema": _schema(
            {
                "project_root": {"type": "string"},
                "command": {"type": "string"},
                "success": {"type": "boolean"},
                "summary": {"type": "string"},
            },
            ["project_root", "command", "success", "summary"],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False},
    },
    {
        "name": "get_project_map",
        "description": "Return the persisted project snapshot, onboarding gates, modules, work-item/task bindings, worktrees, drift counts, and Mermaid source. This does not scan the repository; call scan_project when the snapshot is absent or stale.",
        "inputSchema": _schema({"project_root": {"type": "string"}}, ["project_root"]),
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "get_project_dashboard",
        "description": "Return the beginner-facing dashboard model: current status, exactly one primary next action, reopen instructions, usage steps, branches, modules, and development tasks. Use this whenever the user asks what to do next or to open the project map.",
        "inputSchema": _schema({"project_root": {"type": "string"}}, ["project_root"]),
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "get_project_closeout",
        "description": "Return the compact project map that must be rendered automatically at the end of every Guardian-managed reply. It contains current state, one action, active work, alerts, and an expand-full-map action without the full inventory.",
        "inputSchema": _schema({"project_root": {"type": "string"}}, ["project_root"]),
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "get_module_map",
        "description": "Read one persisted module's files, dependencies, functions, methods, signatures, and parameters without loading the whole code graph.",
        "inputSchema": _schema(
            {"project_root": {"type": "string"}, "module_id": {"type": "string"}},
            ["project_root", "module_id"],
        ),
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "get_branch_map",
        "description": "Read one persisted branch's last commit, code areas, size, canonical delta, worktrees, owning work item, and Codex task link.",
        "inputSchema": _schema(
            {"project_root": {"type": "string"}, "branch": {"type": "string"}},
            ["project_root", "branch"],
        ),
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "search_code_graph",
        "description": "Search the persisted module, file, and symbol graph for a feature, filename, function, method, signature, or parameter.",
        "inputSchema": _schema(
            {
                "project_root": {"type": "string"},
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            },
            ["project_root", "query"],
        ),
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "get_work_item",
        "description": "Read the immutable contract, scope, evidence, and current state for one work item.",
        "inputSchema": _schema(
            {"project_root": {"type": "string"}, "item_id": {"type": "string"}},
            ["project_root", "item_id"],
        ),
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "get_design_contract",
        "description": "Return the single versioned requirement/design contract and its Markdown view: original request, clarified facts, open question, approaches, recommendation, user decisions, acceptance criteria, and document review. Prefer this over replaying the discovery conversation.",
        "inputSchema": _schema(
            {"project_root": {"type": "string"}, "item_id": {"type": "string"}},
            ["project_root", "item_id"],
        ),
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "start_requirement_discovery",
        "description": "Start read-only requirement discovery for a new project, feature, refactor, architecture change, maintenance request, or defect before creating an execution worktree. Automatically choose kind and profile from the request; the user never selects workflow metadata.",
        "inputSchema": _schema(
            {
                "project_root": {"type": "string"},
                "title": {"type": "string"},
                "original_request": {"type": "string"},
                "kind": {"type": "string", "enum": sorted(guardian.WORK_ITEM_KINDS - {"question"})},
                "profile": {"type": "string", "enum": sorted(guardian.REQUIREMENT_PROFILES)},
                "parent_id": {"type": "string"},
            },
            ["project_root", "title", "original_request", "kind", "profile"],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False},
    },
    {
        "name": "update_requirement_discovery",
        "description": "Persist clarified requirement facts and optionally resolve the current question or register exactly one next consequential question. Inspect code and prior decisions first; never ask for technical facts Guardian can discover. If the user says they do not know, research or reason first, recommend concrete options, then ask only when the product trade-off remains material.",
        "inputSchema": _schema(
            {
                "project_root": {"type": "string"},
                "item_id": {"type": "string"},
                "updates": CONTRACT_UPDATES,
                "resolved_question_id": {"type": "string"},
                "answer": {"type": "string"},
                "next_question": REQUIREMENT_QUESTION,
            },
            ["project_root", "item_id"],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True},
    },
    {
        "name": "finalize_requirement_discovery",
        "description": "Validate that the adaptive requirement profile is complete and transition from questioning to solution comparison. This does not choose an MVP or start implementation.",
        "inputSchema": _schema(
            {
                "project_root": {"type": "string"},
                "item_id": {"type": "string"},
                "clarified_summary": {"type": "string"},
            },
            ["project_root", "item_id", "clarified_summary"],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False},
    },
    {
        "name": "record_solution_design",
        "description": "Compare requirement-driven solution approaches and persist the best recommendation. Minimal, complete, phased, reuse-first, or replacement designs are all candidates, never defaults. Auto-select a clear high-confidence winner; when a material trade-off or low confidence remains, persist one beginner-facing user decision and stop.",
        "inputSchema": _schema(
            {
                "project_root": {"type": "string"},
                "item_id": {"type": "string"},
                "complexity": {"type": "string", "enum": ["simple", "nontrivial"]},
                "approaches": {"type": "array", "items": SOLUTION_APPROACH},
                "recommendation_id": {"type": "string"},
                "recommendation_reason": {"type": "string"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "decision_signals": {
                    "type": "array",
                    "items": {"type": "string", "enum": sorted(guardian.DECISION_SIGNALS)},
                },
                "decision_question": {"type": "string"},
            },
            [
                "project_root",
                "item_id",
                "complexity",
                "approaches",
                "recommendation_id",
                "recommendation_reason",
                "confidence",
            ],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False},
    },
    {
        "name": "record_solution_decision",
        "description": "Record the user's answer to the single open solution decision, even when it differs from Guardian's recommendation, then move the chosen approach into document review.",
        "inputSchema": _schema(
            {
                "project_root": {"type": "string"},
                "item_id": {"type": "string"},
                "decision_id": {"type": "string"},
                "selected_option_id": {"type": "string"},
                "answer": {"type": "string"},
            },
            ["project_root", "item_id", "decision_id", "selected_option_id", "answer"],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False},
    },
    {
        "name": "review_design_contract",
        "description": "Record a cold document review across completeness, consistency, clarity, scope, and feasibility. A passing reviewed contract becomes the only executable source of truth; revision findings return it to solution design and no worktree may bind yet.",
        "inputSchema": _schema(
            {
                "project_root": {"type": "string"},
                "item_id": {"type": "string"},
                "reviewer_thread_id": {"type": "string"},
                "scores": DESIGN_REVIEW_SCORES,
                "outcome": {"type": "string", "enum": ["passed", "needs_revision"]},
                "summary": {"type": "string"},
                "findings": STRING_LIST,
            },
            ["project_root", "item_id", "reviewer_thread_id", "scores", "outcome", "summary"],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False},
    },
    {
        "name": "reopen_design_contract",
        "description": "Reopen a previously reviewed adaptive contract when implementation evidence contradicts its selected design. Preserve revision lineage, invalidate the old review and planning revision, and return to solution design instead of silently changing product intent.",
        "inputSchema": _schema(
            {
                "project_root": {"type": "string"},
                "item_id": {"type": "string"},
                "reason": {"type": "string"},
            },
            ["project_root", "item_id", "reason"],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False},
    },
    {
        "name": "get_work_context",
        "description": "Return a compact work-item context capsule with contract, scope, current route, latest stage per role, current diff summary, reusable evidence, and only the latest attempt. Prefer this over replaying a whole conversation or loading all evidence history.",
        "inputSchema": _schema(
            {"project_root": {"type": "string"}, "item_id": {"type": "string"}},
            ["project_root", "item_id"],
        ),
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "get_verification_plan",
        "description": "Return fingerprint-aware verification gates, reusable evidence, pending evidence, and parallel test/review groups for one candidate without changing its state.",
        "inputSchema": _schema(
            {"project_root": {"type": "string"}, "item_id": {"type": "string"}},
            ["project_root", "item_id"],
        ),
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "create_work_item",
        "description": "Create an already-clarified compatibility work item with an immutable request and explicit acceptance, non-goal, and protected-behavior contract. For ordinary new projects or features, prefer start_requirement_discovery so Guardian asks before planning.",
        "inputSchema": _schema(
            {
                "project_root": {"type": "string"},
                "title": {"type": "string"},
                "original_request": {"type": "string"},
                "goal": {"type": "string"},
                "kind": {"type": "string", "enum": sorted(guardian.WORK_ITEM_KINDS)},
                "acceptance_criteria": STRING_LIST,
                "non_goals": STRING_LIST,
                "protected_behaviors": STRING_LIST,
                "parent_id": {"type": "string"},
            },
            [
                "project_root",
                "title",
                "original_request",
                "goal",
                "kind",
                "acceptance_criteria",
                "non_goals",
                "protected_behaviors",
            ],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False},
    },
    {
        "name": "bind_work_item",
        "description": "Bind a Guardian work item to the owning Codex task and, for change work, adopt that task's existing Git worktree. This never creates a second worktree.",
        "inputSchema": _schema(
            {
                "project_root": {"type": "string"},
                "item_id": {"type": "string"},
                "thread_id": {"type": "string"},
                "worktree_path": {"type": "string"},
                "host_id": {"type": "string"},
                "task_title": {"type": "string"},
            },
            ["project_root", "item_id", "thread_id"],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False},
    },
    {
        "name": "assess_work_item_risk",
        "description": "Automatically classify a change item's model route from persisted request, architecture, scope, and failure evidence. The user never chooses a model. Reassessment may escalate but cannot weaken a route after model work starts.",
        "inputSchema": _schema(
            {
                "project_root": {"type": "string"},
                "item_id": {"type": "string"},
                "signals": {
                    "type": "array",
                    "items": {"type": "string", "enum": sorted(guardian.RISK_SIGNALS)},
                },
                "summary": {"type": "string"},
            },
            ["project_root", "item_id", "signals", "summary"],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True},
    },
    {
        "name": "record_task_stage",
        "description": "Persist one adaptive model-orchestration stage. Enforces Luna max by default, explicit max-to-xhigh capability fallback, independent review tasks, and Sol max fixer / Sol xhigh final-review separation.",
        "inputSchema": _schema(
            {
                "project_root": {"type": "string"},
                "item_id": {"type": "string"},
                "stage": {"type": "string", "enum": sorted(guardian.ORCHESTRATION_STAGES)},
                "thread_id": {"type": "string"},
                "model": {"type": "string"},
                "reasoning_effort": {"type": "string"},
                "status": {"type": "string", "enum": sorted(guardian.ORCHESTRATION_STATUSES)},
                "summary": {"type": "string"},
                "outcome": {"type": "string"},
                "artifact": {"type": "string"},
                "host_id": {"type": "string"},
                "fallback_reason": {
                    "type": "string",
                    "description": "Required only when the requested max effort is unavailable and the stage explicitly falls back to xhigh.",
                },
            },
            [
                "project_root",
                "item_id",
                "stage",
                "thread_id",
                "model",
                "reasoning_effort",
                "status",
                "summary",
            ],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False},
    },
    {
        "name": "prepare_worktree",
        "description": "Legacy fallback to create a Guardian-owned worktree only when explicitly allowed. Prefer a Codex task worktree plus bind_work_item.",
        "inputSchema": _schema(
            {
                "project_root": {"type": "string"},
                "item_id": {"type": "string"},
                "base_ref": {"type": "string"},
                "allow_guardian_create": {"type": "boolean"},
            },
            ["project_root", "item_id"],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True},
    },
    {
        "name": "set_change_scope",
        "description": "Declare repository-relative paths or glob patterns that may change, with a required contract-derived reason for each one.",
        "inputSchema": _schema(
            {
                "project_root": {"type": "string"},
                "item_id": {"type": "string"},
                "allowed_changes": {
                    "type": "array",
                    "items": _schema(
                        {
                            "path": {"type": "string", "description": "Repository-relative path or glob"},
                            "reason": {"type": "string"},
                        },
                        ["path", "reason"],
                    ),
                },
                "impacted_nodes": STRING_LIST,
                "architecture_notes": STRING_LIST,
                "depends_on": STRING_LIST,
            },
            ["project_root", "item_id", "allowed_changes"],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False},
    },
    {
        "name": "scan_changes",
        "description": "Compare a worktree with its recorded base, map each changed file to scope reasons, and identify drift or changed tests.",
        "inputSchema": _schema(
            {"project_root": {"type": "string"}, "item_id": {"type": "string"}},
            ["project_root", "item_id"],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False},
    },
    {
        "name": "record_evidence",
        "description": "Record baseline, target, related, full, review, integration, test-integrity, or architecture evidence bound to the current worktree fingerprint. automated_guard evidence can only be generated by run_automated_guard.",
        "inputSchema": _schema(
            {
                "project_root": {"type": "string"},
                "item_id": {"type": "string"},
                "kind": {"type": "string", "enum": sorted(guardian.EVIDENCE_KINDS)},
                "success": {"type": "boolean"},
                "summary": {"type": "string"},
                "command": {"type": "string"},
                "artifact": {"type": "string"},
            },
            ["project_root", "item_id", "kind", "success", "summary"],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False},
    },
    {
        "name": "run_automated_guard",
        "description": "Run deterministic scope, drift, protected-path, sensitive-file, module-boundary, and test-deletion checks for a v2 low-risk candidate. A failure routes the item to a focused AI review instead of pretending the gate passed.",
        "inputSchema": _schema(
            {"project_root": {"type": "string"}, "item_id": {"type": "string"}},
            ["project_root", "item_id"],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True},
    },
    {
        "name": "record_attempt",
        "description": "Record an implementation attempt. Two consecutive failures automatically escalate the item to the high-risk Sol Max architecture route.",
        "inputSchema": _schema(
            {
                "project_root": {"type": "string"},
                "item_id": {"type": "string"},
                "success": {
                    "type": "boolean",
                    "description": "True only when the original observable or product outcome improved; passing tests alone is not success.",
                },
                "summary": {"type": "string"},
            },
            ["project_root", "item_id", "success", "summary"],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False},
    },
    {
        "name": "check_merge_readiness",
        "description": "Deterministically evaluate contract completeness, drift scan, fresh evidence, architecture review, and all merge gates. This never merges code.",
        "inputSchema": _schema(
            {"project_root": {"type": "string"}, "item_id": {"type": "string"}},
            ["project_root", "item_id"],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False},
    },
    {
        "name": "complete_work_item",
        "description": "After the user-confirmed merge has actually happened, record its merge commit and close the work item. This tool never performs the merge.",
        "inputSchema": _schema(
            {
                "project_root": {"type": "string"},
                "item_id": {"type": "string"},
                "merge_commit": {"type": "string"},
                "summary": {"type": "string"},
                "target_ref": {"type": "string"},
            },
            ["project_root", "item_id", "merge_commit", "summary"],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False},
    },
]


HANDLERS: dict[str, Callable[..., Any]] = {
    "guardian_health": guardian.guardian_health,
    "project_init": guardian.project_init,
    "list_guarded_projects": guardian.list_projects,
    "scan_project": guardian.scan_project,
    "select_project_base": guardian.select_project_base,
    "record_project_validation": guardian.record_project_validation,
    "get_project_map": guardian.get_project_map,
    "get_project_dashboard": guardian.get_project_dashboard,
    "get_project_closeout": guardian.get_project_closeout,
    "get_branch_map": guardian.get_branch_map,
    "get_module_map": guardian.get_module_map,
    "search_code_graph": guardian.search_code_graph,
    "get_work_item": guardian.get_work_item,
    "get_design_contract": guardian.get_design_contract,
    "start_requirement_discovery": guardian.start_requirement_discovery,
    "update_requirement_discovery": guardian.update_requirement_discovery,
    "finalize_requirement_discovery": guardian.finalize_requirement_discovery,
    "record_solution_design": guardian.record_solution_design,
    "record_solution_decision": guardian.record_solution_decision,
    "review_design_contract": guardian.review_design_contract,
    "reopen_design_contract": guardian.reopen_design_contract,
    "get_work_context": guardian.get_work_context,
    "get_verification_plan": guardian.get_verification_plan,
    "create_work_item": guardian.create_work_item,
    "bind_work_item": guardian.bind_work_item,
    "assess_work_item_risk": guardian.assess_work_item_risk,
    "record_task_stage": guardian.record_task_stage,
    "prepare_worktree": guardian.prepare_worktree,
    "set_change_scope": guardian.set_change_scope,
    "scan_changes": guardian.scan_changes,
    "record_evidence": guardian.record_evidence,
    "run_automated_guard": guardian.run_automated_guard,
    "record_attempt": guardian.record_attempt,
    "check_merge_readiness": guardian.check_merge_readiness,
    "complete_work_item": guardian.complete_work_item,
}


def _send(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def _result(request_id: Any, value: Any) -> None:
    _send({"jsonrpc": "2.0", "id": request_id, "result": value})


def _error(request_id: Any, code: int, message: str) -> None:
    _send({"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}})


def _tool_result(request_id: Any, value: Any, is_error: bool = False) -> None:
    text = json.dumps(value, ensure_ascii=False, indent=2) if not isinstance(value, str) else value
    result = {"content": [{"type": "text", "text": text}], "isError": is_error}
    if isinstance(value, (dict, list)):
        result["structuredContent"] = value if isinstance(value, dict) else {"items": value}
    _result(request_id, result)


def _attach_guidance(name: str, arguments: dict[str, Any], value: Any) -> Any:
    """Make every successful project operation end with a deterministic user-facing next step."""
    project_root = arguments.get("project_root")
    if not project_root or not isinstance(value, dict) or name in {"get_project_dashboard", "get_project_closeout"}:
        return value
    try:
        closeout = guardian.get_project_closeout(project_root)
    except guardian.GuardianError:
        return value
    enriched = dict(value)
    enriched["guardian_closeout"] = closeout
    enriched["guardian_guidance"] = {
        "status_label": closeout["state"]["status_label"],
        "summary": closeout["state"]["summary"],
        "primary_action": closeout["primary_action"],
        "reopen": closeout["reopen"],
    }
    return enriched


def handle(message: dict[str, Any]) -> None:
    method = message.get("method")
    request_id = message.get("id")
    if method == "initialize":
        requested = (message.get("params") or {}).get("protocolVersion") or "2025-06-18"
        _result(
            request_id,
            {
                "protocolVersion": requested,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                "instructions": SERVER_INSTRUCTIONS,
            },
        )
        return
    if method in {"notifications/initialized", "notifications/cancelled"}:
        return
    if method == "ping":
        _result(request_id, {})
        return
    if method == "tools/list":
        _result(request_id, {"tools": TOOLS})
        return
    if method == "tools/call":
        params = message.get("params") or {}
        name = params.get("name")
        arguments = params.get("arguments") or {}
        handler = HANDLERS.get(name)
        if handler is None:
            _tool_result(request_id, {"error": f"Unknown tool: {name}"}, is_error=True)
            return
        try:
            value = handler(**arguments)
            _tool_result(request_id, _attach_guidance(name, arguments, value))
        except (guardian.GuardianError, TypeError, ValueError) as exc:
            _tool_result(request_id, {"error": str(exc), "tool": name}, is_error=True)
        except Exception as exc:  # Keep protocol stdout clean; diagnostics go to stderr.
            traceback.print_exc(file=sys.stderr)
            _tool_result(request_id, {"error": f"Internal error: {exc}", "tool": name}, is_error=True)
        return
    if request_id is not None:
        _error(request_id, -32601, f"Method not found: {method}")


def main() -> int:
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            message = json.loads(raw)
            if not isinstance(message, dict):
                raise ValueError("Message must be a JSON object")
            handle(message)
        except json.JSONDecodeError as exc:
            _error(None, -32700, f"Parse error: {exc}")
        except Exception as exc:
            traceback.print_exc(file=sys.stderr)
            _error(None, -32603, f"Internal error: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
