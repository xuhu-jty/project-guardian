---
name: manage-project-development
description: Manage AI-assisted development through a persistent project map that links Codex tasks, Git branches and worktrees, modules, files, symbols, tests, scoped work items, drift evidence, architecture escalation, and user-confirmed merges. Use for project onboarding, feature or bug work, diagnosis, progress and branch ownership questions, architecture drift, regression prevention, task routing, worktree selection, and merge readiness.
---

# Manage project development

Keep conversation lightweight. Treat Project Guardian state and recorded raw evidence as authoritative.

## Non-negotiable rules

- Preserve the user's original request verbatim in one coherent work item.
- Diagnose “why” questions before authorizing code changes.
- Never describe a project, task, test command, or merge as complete while its Guardian gate is blocked.
- Let Codex own task worktrees. Bind the existing Codex task and worktree with `bind_work_item`; do not create a second worktree. Use `prepare_worktree` only as an explicitly requested legacy fallback.
- Automatically classify every change item with `assess_work_item_risk`; never ask the user to choose a model or risk level. Persist the evidence signals and short reason before planning.
- Enforce the exact route returned by Guardian: low risk uses Terra medium → Luna high → Terra medium; standard risk uses Terra high → Luna xhigh → Terra high; high risk uses Sol xhigh planning, Luna xhigh or Terra xhigh execution, and Sol xhigh review. A major Bug always requires a separate Sol xhigh fixer and another Sol xhigh final reviewer.
- Use exact model and reasoning overrides when starting each stage, and call `record_task_stage` for every transition. Never silently substitute a model, treat task dispatch as completion, weaken a route after work starts, or let a fixer approve its own work.
- Map every changed path and affected module or symbol to the work contract. Treat unmatched files, undeclared modules, and overlapping active scopes as drift.
- Never merge automatically. Ask for confirmation only after `check_merge_readiness` is ready.
- Never end a Guardian operation with raw tool output or a silent completion. Always show the user the current state, exactly one primary next action, and the sentence: `以后在这个项目的任意 Codex 任务里输入“打开项目图”即可重新打开。`

## Health and recovery

1. Call `guardian_health` once at the start of Guardian work.
2. If the MCP transport fails, do not retry the same call in that task. Stop before editing a registered project and state which persistent gates are unavailable.
3. Call `get_project_map` to read the persisted snapshot. It never scans files.
4. Call `scan_project` only when onboarding is missing or the snapshot is stale.
5. Call `get_project_dashboard` after onboarding, routing, progress, branch, verification, or merge-readiness work so the user always gets the persisted next step.

## Project onboarding

1. Call `project_init` when no state exists.
2. Call `scan_project` to import branches, existing worktrees, committed modules, files, symbols, signatures, parameters, and test targets.
3. Do not create change work while `can_start_work` is false.
4. If the default branch is an empty shell, use the recorded candidates and evidence. Call `select_project_base` automatically only when one candidate is clearly authoritative; otherwise ask one product-level question and keep the project blocked.
5. Never call a stored test command “confirmed” until it has run against the selected canonical commit and `record_project_validation` stores the result. A known failing baseline may become `ready_with_warnings`; a missing target remains blocked.

Read [onboarding-policy.md](references/onboarding-policy.md) for base selection, existing dirty worktrees, and readiness states.

## Route a request

1. Read `get_project_map` before routing.
2. Search `search_code_graph` for the user's feature or symptom, then load only relevant modules with `get_module_map`.
3. Reuse an active item only for the same observable outcome. Create a child or sibling when the outcome branches.
4. Create a `question` item for diagnosis-only work. Create a change item only after onboarding is ready and the change goal is established.
   - Treat architecture advice/options with no repository deliverable as a read-only `question`.
   - Treat a new project's architecture or an agreed versioned architecture document as an `architecture` change item; planning may return `needs_clarification`, and implementation must not begin until its deliverable is explicit.
5. For a change item, inspect the request, code graph, affected modules, public contracts, data/security/business impact, and prior failures. Call `assess_work_item_risk` automatically with the matching evidence signals and a plain-language reason. Do not expose model choice as a user decision.
6. Start or reuse a read-only planning task with the exact planning model and reasoning returned in `route.stages`. Have it produce the complete planning contract, then record `planning` with `record_task_stage`. Do not edit during planning.
7. Only after planning outcome `ready`, create the owning Codex execution task and worktree with the exact execution model and reasoning returned by the route. Bind it with `bind_work_item`, then record `execution` before and after implementation.
8. When the user asks to open a mapped task, use the Codex task navigation tool with the stored `thread_id`.
9. When the user asks what a branch contains or is doing, call `get_branch_map`; do not infer ownership from the branch name alone.

Read [workflow-policy.md](references/workflow-policy.md) when deciding reuse, split, task ownership, serialization, or architecture escalation.

Read [model-orchestration-policy.md](references/model-orchestration-policy.md) before planning, dispatching, implementing, reviewing, or fixing any change item.

## Change and verify

1. Set `allowed_changes`, `impacted_nodes`, and any dependencies with `set_change_scope` before editing. Resolve or serialize reported conflicts.
2. Record the exact pre-change baseline.
3. Implement only in the bound worktree. Call `scan_changes` after each meaningful batch.
4. Fix orphan files and undeclared module impacts before continuing.
5. After execution records `implemented`, start a different Codex task with the exact review model and reasoning returned by the persisted risk route. Review the original request, plan, diff, architecture, tests, regressions, and current fingerprint.
6. Return minor findings to the authorized executor, then run a fresh independent review. For a `major_bug`, start a separate Sol xhigh fixer in the same scoped worktree, then require another separate Sol xhigh final review. Record every stage and outcome.
7. Run target, related, full, integration, review, and conditional test-integrity or architecture gates. Record raw evidence against the current fingerprint.
8. In `record_attempt`, `success` means the original observable or product outcome improved; green tests alone do not count. After three failed outcomes, recurring defects, repeated scope growth, or unchanged product-level quality, stop tactical patching. Guardian stores the attempt fingerprint and escalates the item to the high-risk architecture route; repeat any stages invalidated by the stronger route.
9. Call `check_merge_readiness`. It must remain blocked without completed stages matching the current persisted risk route and a fresh independent passing review. If ready, explain the evidence and ask only for merge confirmation.
10. After the confirmed merge actually exists, call `complete_work_item` with its real merge commit.

Read [evidence-policy.md](references/evidence-policy.md) before final verification.

## User-facing project map

- Treat `打开项目图`, `项目进度`, `我下一步做什么`, `怎么看分支`, and `怎么使用 Guardian` as direct requests for the dashboard. Do not ask the user to locate a file or run a command.
- On first use, after `project_init` and `scan_project`, automatically call `get_project_dashboard` and show the dashboard even when the user did not know to ask for it.
- Lead with one plain-language answer to “我现在只需要做什么？”. Put counts, tabs, branches, modules, and technical detail below it.
- Lead with `项目接入`, `正在处理`, `功能模块`, `分支与工作树`, and `需要确认`.
- Show “未接入 / 需选择基线 / 待验证 / 可开发 / 有基线警告” instead of a generic percentage.
- Label unbound worktrees as “待认领”; show dirty worktrees and scope conflicts prominently.
- Keep commits, paths, module IDs, symbol signatures, and test evidence under technical details unless requested.
- When an in-conversation visualization surface is available, render `get_project_dashboard` as a compact interactive view in the reply. The first visible area must contain the state summary, one primary button, and `输入“打开项目图”可随时回来`. Include a `怎么使用` tab. Branch and module actions must send a follow-up containing the exact stored identifiers; task actions must navigate with the stored `thread_id`. Never invent nodes or claim that a visualization click changed Guardian state by itself.
- If the visualization surface is unavailable, show the same dashboard as compact text with one primary action and the reopen phrase. Never imply that Guardian has a permanent sidebar panel: the project map appears below the Codex reply in whichever project task asked for it.
- After a dashboard button triggers work, refresh the dashboard or at minimum state the changed status and the next primary action before ending the response.

Read [user-experience-policy.md](references/user-experience-policy.md) before onboarding a beginner, rendering the dashboard, or deciding how to close a Guardian response.
