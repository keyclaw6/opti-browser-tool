# ADR-0011: Minimum success floor for task candidates

- Status: Accepted
- Date opened: 2026-07-11
- Date accepted: 2026-07-11
- Decision owner: project owner
- Supersedes: [ADR-0010](0010-task-difficulty-calibration-band.md)

## Context

The evaluation suite must leave room for harness improvements without being dominated by tasks that current strong systems almost never solve. A candidate pool concentrated near zero success would make treatment effects hard to detect, provide too few successful traces for comparison, and blur genuine harness regressions with benchmark difficulty.

The project owner explicitly directed that candidate tasks should be prioritized from benchmarks where current state-of-the-art or otherwise strong reproducible systems achieve **at least 40% success**.

## Decision

Use **40% success as the minimum evidence floor** for candidate sourcing.

The rule has two levels:

1. **Source screening.** A benchmark or benchmark slice should normally have a latest verifiable public strong-system aggregate success rate of at least 40% before it supplies candidates.
2. **Final task admission.** An individual task should normally have an estimated success rate of at least 40% under the pinned local strong reference system before it enters the primary suite.

A benchmark aggregate is only a source-screening proxy. It must not be copied onto every task in that benchmark or represented as task-level evidence.

For this ADR, “current SOTA” is operationalized as the strongest recent result that can be tied to a specific benchmark revision, model or agent system, protocol, and evaluator. An unversioned leaderboard number or a result that cannot be reproduced is weaker evidence than a slightly older result tied to the exact task set.

## Why

A 40% floor should provide:

- enough successful runs to compare winning and failing trajectories;
- enough failures to leave improvement headroom;
- better sensitivity to incremental harness changes than a near-zero benchmark;
- more reliable regression diagnosis; and
- a practical path toward selecting a stable nested smoke suite.

## Consequences

- WorkArena++ Level 2 is preferred over Level 3 for the first candidate pool because the verified L2 reference is above 40%, while the available L3 reference is far below the floor and used a modified step budget.
- The full WebArena-Verified set is sampled instead of defaulting to its difficulty-prioritized Hard subset.
- Every Batch 1 task remains provisional until local task-level calibration.
- Tasks below 40% may be retained in a replacement or research-only pool when they cover a critical failure mode, but they require an explicit exception and must not dominate the primary aggregate.
- The project has **not** accepted an upper saturation ceiling. Tasks that strong systems pass almost always must still be identified and removed or assigned a narrow smoke/regression role.

## Still open

This ADR does not decide:

- which model and harness constitute the calibration reference system;
- the upper success threshold above which a task is considered saturated;
- how many repeated trials are required;
- the confidence-interval rule around the 40% boundary;
- whether visual-first and structured-action lanes require separate calibration systems; or
- how many deliberate below-floor exception tasks may be retained.
