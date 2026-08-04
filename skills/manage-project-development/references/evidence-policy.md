# Evidence policy

## Required evidence

Before work-item evidence, project onboarding must identify the canonical commit and record every configured baseline command as passed or failed. Merely storing a command is not validation.

Record evidence against the exact worktree fingerprint. A successful merge candidate normally requires:

1. `baseline`: pre-change build and test state; presence is required, but pre-existing failures may be recorded honestly.
2. `target`: the requested behavior or reproduced defect is proven.
3. `related`: direct callers, consumers, or adjacent feature tests pass.
4. `full`: the repository's broad regression suite passes.
5. `independent_review`: a read-only reviewer finds no unresolved goal, regression, or architecture blocker.
6. `integration`: the candidate is validated against the latest intended base.
7. `test_integrity_review`: required when test code, fixtures, snapshots, or expected results changed.
8. `architecture`: required after architecture escalation.

An `architecture` work item, including a greenfield initial architecture, starts with `architecture_review_required=true`; it must record successful architecture evidence before merge even when the repository deliverable is documentation-only.

For a low-risk change whose scanned diff contains documentation only, `baseline`, `target`, and `independent_review` are sufficient. Guardian omits `related`, `full`, and `integration` gates only after verifying every changed path is a README, standard project document, Markdown/AsciiDoc/reStructuredText file, or a file under `docs/`. Test-only changes are not documentation-only and still require the normal regression gates.

## Evidence integrity

Record the command, exit result in the summary, relevant artifact path, Git commit, and automatically calculated worktree fingerprint. Evidence becomes stale whenever the candidate fingerprint changes.

Do not accept these as proof:

- “tests passed” without a command or raw result summary;
- a reduced test count without explanation;
- skipped, deleted, or weakened assertions;
- verification from a different commit or dirty-tree fingerprint;
- an implementer's self-review in place of independent review;
- a local strategy metric without fixed-seed, replay, holdout, or comparative evidence when product quality is statistical.

## Strategy and learning systems

For decision engines, ranking systems, and trained models, supplement unit tests with differential evaluation against a fixed baseline. Record intended behavior changes separately from unexplained changes. Use a holdout set that is not tuned during implementation. Passing correctness tests does not prove product-quality improvement.

When calling `record_attempt`, set `success=true` only if the original observable or product-level outcome improved. A compiling build or passing unit tests with unchanged real-world quality is a failed attempt and must increment the escalation counter.
