from __future__ import annotations

import json
import os
import sys
from pathlib import Path


PLUGIN_ROOT = Path(os.environ.get("PLUGIN_ROOT") or os.environ.get("CLAUDE_PLUGIN_ROOT") or Path(__file__).parents[1])
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

import project_guardian_core as guardian  # noqa: E402


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="strict", newline="\n")


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        context = guardian.find_context(payload.get("cwd") or os.getcwd())
    except Exception:
        return 0
    if not context:
        return 0
    project = context["project"]
    session_id = str(payload.get("session_id") or "unknown")
    if context["mode"] == "local":
        message = (
            f"Project Guardian manages '{project['name']}'. This is its local checkout. "
            "Do not edit here. Run guardian_health, read get_project_map, and complete onboarding gates first. "
            "For a change, automatically assess risk and enforce the exact persisted Terra/Luna/Sol route in one bound worktree. "
            "Before ending any Guardian response, call get_project_dashboard and visibly show one next action plus the reopen phrase '打开项目图'."
        )
    elif context["mode"] == "unbound_worktree":
        message = (
            f"This is an unbound Codex worktree for Guardian project '{project['name']}'. "
            f"Do not edit until a work item is created and bind_work_item records thread_id '{session_id}' "
            f"with worktree_path '{context['worktree_path']}'. Do not create a second worktree. "
            "This worktree may be edited only by the assigned risk-authorized executor or a recorded Sol major-fix stage. "
            "Before ending any Guardian response, call get_project_dashboard and visibly show one next action plus the reopen phrase '打开项目图'."
        )
    else:
        item = context["item"]
        contract = item.get("contract", {})
        allowed = ", ".join(entry["path"] for entry in item.get("scope", {}).get("allowed_changes", [])) or "not declared"
        orchestration = item.get("orchestration") or {}
        runs = orchestration.get("runs", [])
        risk_route = guardian._risk_route_view(item)
        if runs:
            latest = runs[-1]
            latest_stage = (
                f"{guardian.MODEL_LABELS.get(latest.get('model'), latest.get('model'))} · "
                f"{str(latest.get('reasoning_effort') or '').capitalize()} "
                f"{guardian.STAGE_ROLE_LABELS.get(latest.get('stage'), latest.get('stage'))}"
            )
        else:
            latest_stage = "待自动判断风险" if not risk_route["assessed"] else risk_route["stages"][0]["label"]
        message = (
            f"Project Guardian work item {item['id']}: {item['title']}. "
            f"Goal: {contract.get('goal', 'missing')}. Status: {item.get('status')}. "
            f"Risk route: {risk_route['level_label']}. Current model stage: {latest_stage}. "
            f"Allowed change paths: {allowed}. Preserve the original request and use scan_changes plus evidence gates before completion. "
            f"Owning Codex task: {(item.get('task') or {}).get('thread_id') or session_id}. Never merge automatically. "
            "Before ending any Guardian response, call get_project_dashboard and visibly show one next action plus the reopen phrase '打开项目图'."
        )
    output = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": message,
        }
    }
    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
