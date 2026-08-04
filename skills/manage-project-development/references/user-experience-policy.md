# Beginner experience policy

## What the user should understand without Git knowledge

Project Guardian is operated through ordinary Codex messages. The user does not need to open a local HTML file, remember a tool name, choose a branch, or decide when to create a worktree.

The stable entry phrases are:

- `打开项目图` — show the current interactive project view below the reply.
- `我下一步做什么` — show the same current state and one recommended action.
- `项目进度` — focus the view on active, blocked, waiting-for-confirmation, and completed work.
- `查看分支和工作树` — focus on what each code line contains and which Codex task owns it.

The map is conversation-embedded. It is not a permanent Codex sidebar page. It can be reopened from any Codex task whose working directory belongs to the guarded Git project.

## Required response closeout

Every successful Guardian operation must end with three visible pieces, in this order:

1. `当前状态` — one plain-language sentence based on persisted state, never an invented percentage.
2. `下一步` — exactly one recommended action. If interactive output is available, make it the only primary button.
3. `如何回来` — `以后在这个项目的任意 Codex 任务里输入“打开项目图”即可重新打开。`

Do not make the user choose among several equally prominent technical actions. Secondary actions such as viewing branches, modules, or progress belong below the primary action or inside tabs.

## First-use behavior

After initialization or scanning:

1. Call `get_project_dashboard`.
2. Explain whether the project is unscanned, needs a real base, needs baseline tests, is blocked, or is ready.
3. Render the dashboard automatically.
4. If the state is `needs_base_selection`, offer `让 Codex 判断真实基线` as the primary action. The user should not need to name a branch unless evidence is genuinely ambiguous.
5. If the state is ready and no work item exists, invite the user to describe one new feature or one observed problem in ordinary language.

## Dashboard information hierarchy

The first screen must answer “what now?” before showing inventory:

- State label.
- One-sentence summary.
- One primary action with helper text explaining what it will and will not do.
- Reopen hint: `输入“打开项目图”可随时回来`.

Use tabs or progressive disclosure for:

- `怎么使用`
- `分支与工作树`
- `功能模块`
- `开发任务`

Every branch action uses the exact persisted branch name. Every module action uses the exact module ID. Every task action uses the stored Codex `thread_id` when available. A visualization click may request Codex work or navigate to a task; it must never silently mutate Guardian state.

## Empty, blocked, and completion states

- No active work: say `直接告诉 Codex 要增加什么功能，或者哪里表现不对` and offer one start button.
- Blocked: state the specific blocker and one recovery action. Do not expose a dead end.
- Verification failed: continue the same task toward a passing result or architecture review; do not call the feature finished.
- Merge ready: show completed work, evidence, drift, and risk, then ask for explicit merge confirmation. The primary button must not merge by itself.
