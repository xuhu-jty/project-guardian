# Project onboarding policy

## States

- `not_scanned`: durable project state exists but Git and code structure have not been inventoried.
- `needs_base_selection`: the default branch does not represent the code and no canonical committed line is safe to infer.
- `needs_test_validation`: the canonical commit and code graph exist, but registered baseline commands have not run there.
- `blocked`: a command target is absent or another onboarding invariant is invalid.
- `ready`: canonical code and baseline commands are recorded and current.
- `ready_with_warnings`: development may continue while preserving explicit baseline failures, missing test coverage, graph truncation, or dirty-worktree warnings.

Zero configured baseline commands is not a blocker. The project becomes `ready_with_warnings` and the dashboard must state that no project-level test command is registered.

## Canonical base

- Prefer a meaningful default branch containing project markers and source files.
- For a genuinely new repository where every visible branch points to the same single committed code line, select the default branch automatically even if it contains only a README or `.gitignore`; that commit is the greenfield baseline.
- When the default branch is an empty shell, compare committed candidates by project markers, source volume, recency, worktree state, and branch relationships.
- Select automatically only when one candidate is clearly stronger and committed. Otherwise keep the project blocked and ask the user a plain-language question; do not ask them to interpret hashes.
- Never treat uncommitted worktree content as part of a canonical commit. Display it as a dirty warning and preserve it.

## Existing worktrees

- Import every Git worktree before routing work.
- Mark unmatched worktrees as `unassigned`; never delete, reset, commit, move, or adopt them automatically.
- Bind a worktree only after validating that its Git common directory belongs to the registered project.
- Re-scan after branch or worktree topology changes.

## Baseline commands

- A registered command is configuration, not evidence.
- Confirm referenced solution, project, script, or configuration files exist in the canonical commit before running it.
- Record the actual command outcome and canonical commit. Preserve failures as baseline evidence rather than changing tests to make onboarding green.
