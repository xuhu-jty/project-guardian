---
name: manage-project-development
description: Manage AI-assisted product and software development through adaptive requirement interviews, optimal-solution comparison, a reviewed design contract, and a persistent project map linking Codex tasks, Git branches and worktrees, modules, files, symbols, tests, drift evidence, architecture escalation, and user-confirmed merges. Use for new projects, new features, requirement clarification, product decisions, design/spec documents, project onboarding, bugs and diagnosis, progress or branch ownership questions, regression prevention, task routing, worktree selection, and merge readiness.
---

# Manage project development

Keep conversation lightweight. Treat Project Guardian state and recorded raw evidence as authoritative.

## Non-negotiable rules

- Preserve the user's original request verbatim in one coherent work item.
- Route ordinary new projects and features through `start_requirement_discovery`; do not create an execution worktree or assume an MVP before the reviewed design contract is ready.
- Inspect known project facts before asking. Ask one consequential question at a time, skip answered dimensions, and never ask the user to choose implementation details that Codex can determine safely.
- Recommend the requirement-best solution, not the smallest solution. Auto-select a clear, reversible, high-confidence winner; stop and ask the user when a material product trade-off or genuine uncertainty remains.
- Diagnose “why” questions before authorizing code changes.
- Never describe a project, task, test command, or merge as complete while its Guardian gate is blocked.
- Let Codex own task worktrees. Bind the existing Codex task and worktree with `bind_work_item`; do not create a second worktree. Use `prepare_worktree` only as an explicitly requested legacy fallback.
- Automatically classify every change item with `assess_work_item_risk`; never ask the user to choose a model or risk level. Persist the evidence signals and short reason before planning.
- Enforce the exact v2 route returned by Guardian: every Luna stage defaults to `max`; high-risk planning and major-Bug repair use Sol `max`; high-risk review uses fresh Sol `xhigh`. Low-risk work runs the deterministic automated guard first and starts a focused Terra review only when the guard raises an alert.
- Use exact model and reasoning overrides when starting each stage, and call `record_task_stage` for every transition. When `max` is unavailable, use `xhigh` only with a concrete `fallback_reason` so Guardian records requested and actual effort. Never silently substitute a model, treat task dispatch as completion, weaken a route after work starts, or let a fixer approve its own work.
- Map every changed path and affected module or symbol to the work contract. Treat unmatched files, undeclared modules, and overlapping active scopes as drift.
- Never merge automatically. Ask for confirmation only after `check_merge_readiness` is ready.
- Never end a Guardian operation with raw tool output or a silent completion. Before every final reply call `get_project_closeout` and render its compact project map at the reply end with the current state and exactly one primary action. Keep `打开项目图` as the manual full-map fallback.

## Health and recovery

1. Call `guardian_health` once at the start of Guardian work.
2. If the MCP transport fails, do not retry the same call in that task. Stop before editing a registered project and state which persistent gates are unavailable.
3. Call `get_project_closeout` for the lightweight persisted snapshot. Use `get_project_map` only for onboarding/base analysis or an explicitly expanded full map.
4. Call `scan_project` only when onboarding is missing or the snapshot is stale.
5. Call `get_project_closeout` after every operation. Call `get_project_dashboard` additionally after onboarding, risk escalation, review failure, merge readiness, or an explicit full-map request.

## Project onboarding

1. Call `project_init` when no state exists.
2. Call `scan_project` to import branches, existing worktrees, committed modules, files, symbols, signatures, parameters, and test targets.
3. Do not create change work while `can_start_work` is false.
4. If the default branch is an empty shell, use the recorded candidates and evidence. Call `select_project_base` automatically only when one candidate is clearly authoritative; otherwise ask one product-level question and keep the project blocked.
5. Never call a stored test command “confirmed” until it has run against the selected canonical commit and `record_project_validation` stores the result. A known failing baseline may become `ready_with_warnings`; a missing target remains blocked.

Read [onboarding-policy.md](references/onboarding-policy.md) for base selection, existing dirty worktrees, and readiness states.

## Route a request

1. Read `get_project_closeout` before routing. For an existing item, load `get_work_context`; do not replay its complete conversation or evidence history.
2. Search `search_code_graph` for the user's feature or symptom, then load only relevant modules with `get_module_map`.
3. Reuse an active item only for the same observable outcome. Create a child or sibling when the outcome branches.
4. Create a `question` item for diagnosis-only work. For an ordinary new project or feature, call `start_requirement_discovery` before implementation planning. Use `create_work_item` only when the user has already supplied a fully clarified, testable contract.
   - Treat architecture advice/options with no repository deliverable as a read-only `question`.
   - Treat a new project's architecture as an `architecture` discovery item; requirements, selected approach, acceptance, and document review must become explicit before worktree binding.
5. Follow [requirement-design-policy.md](references/requirement-design-policy.md) for adaptive questioning, “I don't know” handling, solution comparison, user-decision boundaries, and the single design-contract review.
6. For a change item, inspect the request, code graph, affected modules, public contracts, data/security/business impact, and prior failures. Call `assess_work_item_risk` automatically with the matching evidence signals and a plain-language reason. Do not expose model choice as a user decision.
7. Start or reuse a read-only planning task with the exact planning model and reasoning returned in `route.stages`. Record it as running while it interviews, compares approaches, and establishes the design contract. Do not edit during planning.
8. Record planning as `completed/ready` only after `review_design_contract` passes. Use the design-contract artifact URI plus exact affected symbols as the implementation handoff.
9. Only then create the owning Codex execution task and worktree with the exact execution model and reasoning returned by the route. Bind it with `bind_work_item`, then record `execution` before and after implementation.
10. When the user asks to open a mapped task, use the Codex task navigation tool with the stored `thread_id`.
11. When the user asks what a branch contains or is doing, call `get_branch_map`; do not infer ownership from the branch name alone.

Read [workflow-policy.md](references/workflow-policy.md) when deciding reuse, split, task ownership, serialization, or architecture escalation.

Read [model-orchestration-policy.md](references/model-orchestration-policy.md) before planning, dispatching, implementing, reviewing, or fixing any change item.

## Change and verify

1. Set `allowed_changes`, `impacted_nodes`, and any dependencies with `set_change_scope` before editing. Resolve or serialize reported conflicts.
2. Record the exact pre-change baseline.
3. Implement only in the bound worktree. Call `scan_changes` after each meaningful batch.
4. Fix orphan files and undeclared module impacts before continuing.
5. After execution records `implemented`, call `get_verification_plan`. Reuse passing evidence bound to the same candidate fingerprint and start pending tests, automated checks, and independent review in parallel.
6. For v2 low risk, call `run_automated_guard`. If it passes, do not start a separate AI reviewer. If it raises an alert, start the returned focused Terra review. Standard and high-risk work always use the persisted independent review route.
7. Return minor findings to the authorized executor, then review the current candidate again. Use a focused delta review for standard/low work when scope and public contracts did not expand; use a full fresh review for high risk. For a `major_bug`, start a separate Sol `max` fixer in the same scoped worktree, then require another separate Sol `xhigh` final review.
8. Record raw evidence against the current fingerprint. Do not rerun or resend a passing gate while its fingerprint remains current.
9. In `record_attempt`, `success` means the original observable or product outcome improved; green tests alone do not count. After two failed outcomes, a recurring defect, repeated scope growth, or unchanged product-level quality, stop tactical patching and escalate to the Sol `max` architecture route.
10. Call `check_merge_readiness`. If ready, freeze the returned candidate fingerprint and base information, explain only the compact evidence summary, and ask for merge confirmation.
11. After confirmation, if the candidate fingerprint and intended base are unchanged, merge without repeating the completed cycle; then call `complete_work_item` with the real merge commit. If either changed, rerun only the invalidated integration gates.

Read [evidence-policy.md](references/evidence-policy.md) before final verification.

## User-facing project map

- Treat `打开项目图`, `项目进度`, `我下一步做什么`, `怎么看分支`, and `怎么使用 Guardian` as direct requests for the dashboard. Do not ask the user to locate a file or run a command.
- On every Guardian-managed turn, automatically call `get_project_closeout` before the final reply and render its mini map below the reply. The user must not need to type a command to see current progress.
- On first use, after `project_init` and `scan_project`, automatically call `get_project_dashboard`. Also expand it after risk escalation, review failure, or merge readiness.
- Lead with one plain-language answer to “我现在只需要做什么？”. Put counts, tabs, branches, modules, and technical detail below it.
- Lead with `项目接入`, `正在处理`, `功能模块`, `分支与工作树`, and `需要确认`.
- Show “未接入 / 需选择基线 / 待验证 / 可开发 / 有基线警告” instead of a generic percentage.
- Label unbound worktrees as “待认领”; show dirty worktrees and scope conflicts prominently.
- Keep commits, paths, module IDs, symbol signatures, and test evidence under technical details unless requested.
- When an in-conversation visualization surface is available, render `get_project_closeout` as the automatic end card. Its first visible area contains state, active item, current model stage, alerts, one primary button, and `展开完整项目图`. Render `get_project_dashboard` only for the expanded view. Branch and module actions must send the exact stored identifiers; task actions navigate with the stored `thread_id`.
- If the visualization surface is unavailable, show the same dashboard as compact text with one primary action and the reopen phrase. Never imply that Guardian has a permanent sidebar panel: the project map appears below the Codex reply in whichever project task asked for it.
- After a dashboard button triggers work, refresh the dashboard or at minimum state the changed status and the next primary action before ending the response.

Read [user-experience-policy.md](references/user-experience-policy.md) before onboarding a beginner, rendering the dashboard, or deciding how to close a Guardian response.
