# Adaptive risk model orchestration

Use this policy for every feature, bug fix, refactor, architecture change, or maintenance change. Diagnosis-only questions remain read-only until a change goal exists. The user describes the outcome; Guardian chooses the route automatically.

## Route matrix

| Risk | Planning | Execution | Independent review | Typical work |
| --- | --- | --- | --- | --- |
| Low | `gpt-5.6-terra` `medium` | `gpt-5.6-luna` `high` | `gpt-5.6-terra` `medium` | Contained maintenance, docs/tests-only work, localized low-impact edits |
| Standard | `gpt-5.6-terra` `high` | `gpt-5.6-luna` `xhigh` | `gpt-5.6-terra` `high` | Ordinary features, bugs, and refactors with known boundaries |
| High, focused execution | `gpt-5.6-sol` `xhigh` | `gpt-5.6-luna` `xhigh` | `gpt-5.6-sol` `xhigh` | Core algorithm or business-critical change with an executable plan |
| High, judgment-heavy execution | `gpt-5.6-sol` `xhigh` | `gpt-5.6-terra` `xhigh` | `gpt-5.6-sol` `xhigh` | New-project architecture, cross-module contracts, migrations, scope drift, or repeated failures |
| Major bug | — | `gpt-5.6-sol` `xhigh` fixer | fresh `gpt-5.6-sol` `xhigh` reviewer | Severe finding from any route |

Do not ask the user which model or risk level to use. Do not silently substitute another model or reasoning effort. If an exact route model is unavailable, preserve the work item and report which stage could not start.

## Automatic assessment

After creating a change item and reading the relevant code graph, call `assess_work_item_risk` before planning. Supply only observed signals and a short evidence-based explanation.

- Choose low only for a `maintenance` item whose impact is demonstrably contained, such as `test_or_docs_only`, `routine_maintenance`, or `localized_change`. Uncertainty defaults to standard.
- Standard is the normal route for one-module features, bug fixes, and refactors with known contracts and no high-risk signal.
- High is mandatory for a new project or architecture, core algorithms, security/authorization, data integrity or migration, financial or commercial-critical results, concurrency/resource risks, public API/protocol changes, commercial releases, cross-module changes, recurring failures, product quality that does not improve, or scope drift.
- High-risk execution uses Terra xhigh when implementation itself must make architectural or contract judgment. It uses Luna xhigh when the Sol plan is stable and execution is focused.
- Reassessment after a stage starts may add evidence or escalate the route, but must not weaken it. Stages recorded under a weaker route no longer satisfy the current gate and must be repeated where required.

## Task topology

- Keep one implementation worktree per work item. The authorized execution task owns it and must be bound with `bind_work_item`.
- Planning is read-only and uses the exact returned planning model and effort.
- Start execution only after a completed planning outcome of `ready` that matches the current route.
- Review must use the exact returned review model and effort in a different Codex task from execution. It reads the same worktree without editing.
- A major-fix task may edit the implementation worktree only after other writers are idle. It is always a separate Sol xhigh task.
- The major fixer cannot approve its own work. A fresh Sol xhigh final-review task is mandatory.
- Use task wait/read tools to collect actual outcomes. Task creation is not completion.
- Persist every transition with `record_task_stage`; chat prose alone is not authoritative.

## Planning contract

Planning must produce all of the following before returning `ready`:

1. User-visible outcome and clarified acceptance criteria.
2. Non-goals and protected existing behaviors.
3. Architecture decision and module boundaries, including why the change belongs there.
4. Expected files, symbols, inputs, outputs, parameters, and dependencies.
5. Worktree/task ownership and serialization for overlapping scopes.
6. Baseline, target, related, full, integration, and regression checks.
7. Risks, containment or rollback, and explicit stop/escalation conditions.

If requirements remain ambiguous, record `needs_clarification` and ask only product questions that materially change the outcome. If the architecture or baseline is unsafe, record `blocked` and do not dispatch execution.

## Execution contract

The authorized executor follows the accepted plan without silently changing architecture, scope, acceptance criteria, protected behavior, or test strength. It must:

1. Confirm its bound task, current risk route, and worktree before editing.
2. Declare scope with `set_change_scope` and record baseline evidence.
3. Implement in small coherent batches and call `scan_changes` after each meaningful batch.
4. Stop and return to planning when code reality conflicts with the plan, a new public contract is needed, an undeclared module is crossed, or attempts repeatedly fail.
5. Run planned checks and record `implemented` only when ready for independent review.

Minor review findings return to the authorized executor. Any new implementation invalidates the previous passing review.

## Independent review contract

The reviewer reads the original request, planning artifact, current diff, affected modules and symbols, evidence, and worktree fingerprint. It checks observable requirements, architecture boundaries, undeclared coupling, protected behavior, test integrity, edge cases, security, privacy, authorization, data integrity, concurrency, resources, and recovery.

Return one of `passed`, `minor_findings`, `major_bug`, or `blocked`. A major finding includes security or authorization failure, data loss/corruption, unsafe migration, wrong financial/business-critical result, public contract break, core architecture violation, release blocker, crash, severe resource failure, broad regression, recurring defect, repeated scope growth, or tests passing without product quality improving.

For `major_bug`, start a separate Sol xhigh fixer, then a different Sol xhigh final reviewer. Only a fresh `passed` review against the current fingerprint can unblock merge readiness.

Repeated ineffective attempts discovered from attempt history escalate to high-risk architecture replanning first; they do not skip directly to a major fixer. Use the Sol major-fix route only after an independent `review` or `final_review` explicitly records `major_bug` against the current plan and fingerprint.

## User-visible status

Show the persisted risk label, the reason, and the exact current model role. Examples: `标准风险 · GPT-5.6 Luna · Xhigh 执行`, `高风险 · GPT-5.6 Terra · Xhigh 执行`, or `GPT-5.6 Sol · Xhigh 最终复审`. Keep exactly one primary next action and ask the user only for product decisions or final merge confirmation.
