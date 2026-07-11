# ADR-0014: Run all 140 candidates before filtering the primary suite

- Status: Accepted
- Date opened: 2026-07-11
- Date accepted: 2026-07-11
- Decision owner: project owner
- Supersedes the task-count portion of: [ADR-0013](0013-runnable-evaluation-suite-v0.md)

## Context

The first runnable-suite draft selected 100 of the 140 sourced candidates before task-level environment, verifier, and success-rate checks had been run. The project owner directed that the executable suite should include all 140 candidates initially and that filtering can happen later.

## Decision

The active provisional primary manifest and candidate-pool manifest each contain **all 140 exact candidates**:

- 30 REAL v1 tasks;
- 30 WebArena-Verified tasks;
- 30 WorkArena++ Level 2 tasks;
- 30 VisualWebArena tasks; and
- 20 WARC-Bench tasks.

The 20-task smoke suite remains a strict subset. The provisional regression seed initially equals the smoke suite. The target final primary suite remains approximately 100 tasks, but no candidate is removed until environment setup, reset, solvability, verifier quality, duplication, stability, and repeated task-level reference performance have been assessed.

The backend-neutral bridge architecture, standardized results, and fail-closed validity rules from ADR-0013 remain in force.

## Why

- It prevents premature filtering based on benchmark-level averages or heuristic difficulty labels.
- It preserves every candidate and its provenance while the validation evidence is still incomplete.
- It lets the project compare failures and setup costs across all candidate sources before freezing quotas.
- It makes later exclusions reviewable: every removed task must have a recorded reason.

## Consequences

- Initial full runs may be more expensive than the eventual 100-task primary suite.
- `primary.json` is explicitly provisional and currently aliases the complete 140-task candidate pool.
- Per-task calibration against the accepted 35–70% band remains required before final admission.
- The superseded 100-task draft is retained for audit but is not the active manifest.
