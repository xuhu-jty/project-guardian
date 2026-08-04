# Workflow policy

## Routing and task ownership

- Reuse an item for a clarification, reproduction, or follow-up with the same observable outcome.
- Create a child for a separately testable prerequisite and a sibling for a different capability, module responsibility, or release risk.
- Keep explanation-only questions in diagnosis until evidence establishes a change goal.
- Bind exactly one active work item to one Codex task and one worktree. Never bind a worktree or task to two active items.
- Prefer Codex-created worktrees. A Guardian-created worktree is an explicit compatibility fallback, not the normal route.

## Scope and parallel work

- Allow scope expansion only when each new path is necessary for the same acceptance criterion and its affected modules and tests can be verified.
- Split work for an unrelated outcome, public API redesign, migration, independent release risk, or different commercial behavior.
- Compare paths and graph nodes before parallel changes. Serialize work sharing a mutable core file, exported symbol, schema, generated artifact, model, migration, or module boundary.
- Record serialization with `depends_on`; do not hide an overlap by widening both scopes.

## Architecture escalation

Escalate when any condition applies:

- three consecutive attempts fail;
- the same defect returns after a prior fix;
- passing local tests do not improve product-level evaluation;
- changes repeatedly add special cases to a shared core path;
- a dependency crosses a documented module boundary;
- a public contract changes for one local case;
- the affected area expands on two consecutive attempts.

During architecture review, stop tactical patches. Compare the current design with at least one structural alternative, migration cost, protected behavior, and falsifiable evaluation evidence.
