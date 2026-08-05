# Beginner experience policy

## Automatic end-of-turn project map

A Codex task has no reliable permanent “conversation ended” event because the user can continue at any time. Treat each final Guardian reply as the stable boundary.

Before every final reply:

1. Call `get_project_closeout`.
2. Render its compact mini map below the reply automatically.
3. Show one plain-language current state and exactly one primary next action.
4. Keep `展开完整项目图` secondary unless the full-map trigger applies.

Automatically render `get_project_dashboard` after first onboarding, risk escalation, review failure, merge readiness, or an explicit `打开项目图` request. Do not reload or narrate the full dashboard on routine turns.

## What the user should understand without Git knowledge

The user never needs to choose a branch, worktree, task, model, risk level, review mode, or context size. Ordinary phrases remain valid fallbacks:

- `打开项目图`
- `我下一步做什么`
- `项目进度`
- `查看分支和工作树`

New projects and features begin as a normal conversation. Never ask the user to select `product`, `internal`, `defect`, a work-item kind, or a contract phase.

## Requirement conversation

- Show one question at a time and explain in one sentence why its answer changes the result.
- Prefer the user's language. Keep architecture, schema, framework, and file decisions out of beginner questions.
- When the user says “不知道”, do the analysis first, show concrete options and a recommendation, then ask only if the remaining choice materially changes the product.
- Never describe the workflow as “MVP first”. Say Guardian is choosing the best-fit solution; a minimal, complete, phased, reuse-first, or replacement approach may win.
- During discovery, the primary card shows `正在问清需求`, the single open question or missing dimension, and `还没有创建开发工作树`.
- During solution design, show the recommendation and whether Guardian can proceed automatically.
- During document review, show the five review dimensions and any one blocking concern.

The map is embedded below the Codex reply, not a permanent sidebar page.

## Information hierarchy

The compact map shows, in order:

1. Project state and one-sentence summary.
2. Active work item, status, risk, and current model stage.
3. Drift, blocked, or waiting-for-merge alerts.
4. One primary action.
5. Secondary `展开完整项目图` action.

When present, place the requirement/design phase before the Git branch. Surface the selected approach in plain language; keep the full contract behind `查看需求与设计文档`.

The expanded dashboard contains `怎么使用`, `分支与工作树`, `功能模块`, and `开发任务`. Use exact persisted branch, module, work-item, and thread identifiers. A visualization click may navigate or request a follow-up; it must not silently mutate Guardian state.

## Empty, blocked, and completion states

- No active work: say `直接告诉 Codex 要增加什么功能，或者哪里表现不对`.
- Requirement discovery: continue the same item and ask only its next consequential question.
- Needs user decision: show exactly one question, the recommendation, and the stakes; do not create a worktree.
- Design review: continue the cold document review; do not claim the feature is ready for development.
- Blocked: show the concrete blocker and one recovery action.
- Verification failed: continue the same task or escalate; never call the feature finished.
- Merge ready: show compact completed work, reusable evidence, drift, and risk, then ask for explicit confirmation. The button must not merge by itself.
- After confirmed merge: show the completed node and the next single project action.

## Token discipline

Render structured state rather than asking the model to rewrite the map. Use `get_project_closeout` for routine turns, `get_work_context` for task handoff, exact module/symbol queries for code, and `get_verification_plan` for evidence. Never load a full map merely to produce the automatic end card.
