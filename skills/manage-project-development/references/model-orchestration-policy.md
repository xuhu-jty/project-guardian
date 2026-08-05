# Adaptive risk model orchestration

Use this policy for every change item. The user describes the outcome; Guardian chooses the route automatically. Diagnosis-only questions remain read-only until a change goal exists.

## Route matrix

| Risk | Planning | Execution | Review | Typical work |
| --- | --- | --- | --- | --- |
| Low | `gpt-5.6-terra` `medium` | `gpt-5.6-luna` `max` | deterministic automated guard; Terra `medium` only on alert | Contained maintenance, docs/tests-only work, localized low-impact edits |
| Standard | `gpt-5.6-terra` `high` | `gpt-5.6-luna` `max` | `gpt-5.6-terra` `high` focused review | Ordinary features, bugs, and refactors with known boundaries |
| High, focused execution | `gpt-5.6-sol` `max` | `gpt-5.6-luna` `max` | `gpt-5.6-sol` `xhigh` full review | Core algorithm or business-critical change with an executable plan |
| High, judgment-heavy execution | `gpt-5.6-sol` `max` | `gpt-5.6-terra` `xhigh` | `gpt-5.6-sol` `xhigh` full review | New architecture, contracts, migrations, drift, or repeated failures |
| Major bug | — | fresh `gpt-5.6-sol` `max` fixer | fresh `gpt-5.6-sol` `xhigh` final reviewer | Severe finding from any route |

Every Luna stage defaults to `max`. If the active Codex surface cannot run `max`, fall back to `xhigh` only after recording a concrete `fallback_reason`; persist requested and actual effort. Never silently substitute another model or effort.

## Automatic assessment

- Choose low only for a `maintenance` item whose impact is demonstrably contained. Uncertainty defaults to standard.
- Use standard for one-module features, bug fixes, and refactors with known contracts and no high-risk signal.
- Use high for a new project or architecture, core algorithms, security/authorization, data integrity, migration, financial or commercial-critical results, concurrency/resource risks, public protocols, cross-module changes, commercial releases, recurring failures, stalled product quality, or scope drift.
- Use Terra xhigh for high-risk execution that must still make architectural judgment. Use Luna max when the Sol max plan is stable and execution is focused.
- Escalate after two consecutive failed product outcomes. Green tests without observable improvement count as failure.
- Reassessment may add evidence or escalate after work starts, but must not weaken the persisted route.

## Token-efficient task topology

- Keep one implementation worktree per work item and bind one owning execution task.
- Load `get_work_context` for handoff. Add only the exact module map and symbols required for the current stage; never replay a whole chat, project map, or evidence history.
- Store long planning detail in the planning artifact. Pass later stages its artifact identifier, contract, affected symbols, current diff, evidence status, and fingerprint.
- Planning is read-only. Execution edits only the bound worktree. Independent review uses a different task and reads the same frozen candidate.
- Use `get_verification_plan` after implementation. Reuse evidence matching the current fingerprint and run pending tests, automated checks, and review concurrently.
- Task creation is not completion. Persist every actual transition with `record_task_stage`.

## Planning contract

Planning must return:

1. The reviewed requirement/design contract artifact, including original request, clarified outcome, selected approach, acceptance, non-goals, protected behavior, and user decisions.
2. Architecture decision and module boundary consistent with that selected approach.
3. Expected files, symbols, inputs, outputs, parameters, and dependencies.
4. Worktree ownership and serialization requirements.
5. Baseline, target, related, integration, regression, and conditional full checks.
6. Risks, rollback, and explicit stop/escalation conditions.

Keep planning read-only while discovery and solution design run. It may record `running`, but it cannot record `completed/ready` until the design contract passes review. Return `needs_clarification` only for product choices that materially change the outcome. Return `blocked` when the architecture or baseline is unsafe.

## Execution contract

Confirm the bound task, route, and worktree. Declare scope and baseline before editing. Implement in coherent batches, scan changes after each meaningful batch, and stop when reality conflicts with the plan, a new public contract is needed, an undeclared module is crossed, or attempts repeatedly fail.

## Review contract

- Low risk: run `run_automated_guard`. A pass replaces independent AI review. An alert requires the returned Terra medium review and any conditional test-integrity evidence.
- Standard risk: perform one focused review of the original request, current diff, affected contracts, protected behavior, test integrity, and fresh evidence.
- High risk: perform a full Sol xhigh review of architecture, security, data, concurrency, recovery, regressions, and product-level evaluation.
- Minor low/standard fixes use a focused delta review when scope and public contracts remain unchanged. High-risk fixes always receive a fresh full review.
- A major finding starts a separate Sol max fixer. That fixer cannot approve its own work; a fresh Sol xhigh final review against the current fingerprint is mandatory.

Return `passed`, `minor_findings`, `major_bug`, or `blocked`. Treat security or authorization failure, data loss, unsafe migration, wrong business-critical results, public contract break, architecture violation, release blocker, crash, broad regression, recurring defect, or green tests without product improvement as major.

## User-visible status

Show the persisted risk label, exact current model role, requested effort, and any capability fallback. Examples: `标准风险 · GPT-5.6 Luna · Max 执行`, `高风险 · GPT-5.6 Terra · Xhigh 执行`, or `GPT-5.6 Sol · Xhigh 最终复审`. Render the compact project closeout automatically and keep exactly one primary action.
