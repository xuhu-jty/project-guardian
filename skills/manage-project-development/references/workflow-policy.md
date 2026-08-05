# Workflow policy

## Routing and task ownership

- Start new projects and ordinary features in requirement discovery. Discovery is read-only and owns no execution worktree.
- Reuse a discovery item while the clarified observable outcome remains the same. Create a sibling when the user chooses a genuinely different product outcome; do not hide the fork inside one oversized contract.
- Reuse an item for a clarification, reproduction, or follow-up with the same observable outcome.
- Create a child for a separately testable prerequisite and a sibling for a different capability, module responsibility, or release risk.
- Keep explanation-only questions in diagnosis until evidence establishes a change goal.
- Bind exactly one active work item to one Codex task and one worktree. Never bind a worktree or task to two active items.
- Bind only after the adaptive design contract is reviewed and ready and planning completed with the contract artifact.
- Prefer Codex-created worktrees. A Guardian-created worktree is an explicit compatibility fallback, not the normal route.

## Scope and parallel work

- Allow scope expansion only when each new path is necessary for the same acceptance criterion and its affected modules and tests can be verified.
- Split work for an unrelated outcome, public API redesign, migration, independent release risk, or different commercial behavior.
- Compare paths and graph nodes before parallel changes. Serialize work sharing a mutable core file, exported symbol, schema, generated artifact, model, migration, or module boundary.
- Record serialization with `depends_on`; do not hide an overlap by widening both scopes.
- Move unconfirmed “might be useful later” ideas into non-goals or a separate candidate item. They cannot expand the active worktree.

## Architecture escalation

Escalate when any condition applies:

- two consecutive attempts fail;
- the same defect returns after a prior fix;
- passing local tests do not improve product-level evaluation;
- changes repeatedly add special cases to a shared core path;
- a dependency crosses a documented module boundary;
- a public contract changes for one local case;
- the affected area expands on two consecutive attempts.

During architecture review, stop tactical patches. Compare the current design with at least one structural alternative, migration cost, protected behavior, and falsifiable evaluation evidence.

## Candidate freeze and merge queue

- After implementation, scan once and treat the resulting fingerprint as the candidate shared by tests, automated gates, and review.
- Run independent gates in parallel. Persist each result against that same fingerprint.
- Reuse current evidence. A user confirmation does not invalidate a candidate.
- If a low/standard minor fix changes no public contract or scope, run affected tests and a focused delta review. High-risk changes always receive a fresh full review.
- Ask the user once after readiness. If the candidate and intended base remain unchanged, perform the confirmed merge immediately without repeating passed gates.
- If the base changes before merge, rerun integration and only the gates invalidated by that base change. If the candidate changes, compute a new plan from `get_verification_plan`.
