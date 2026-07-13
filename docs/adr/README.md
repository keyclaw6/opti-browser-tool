# Architecture Decision Records

File names use `NNNN-short-title.md`. The authoritative status summary is [`../DECISION_REGISTER.md`](../DECISION_REGISTER.md), and the chronological rationale is [`../DECISION_TIMELINE.md`](../DECISION_TIMELINE.md).

- Open ADRs record unresolved questions and the evidence needed before a choice.
- Proposed ADRs present a concrete option for discussion but are not binding.
- Accepted ADRs are active decisions. Do not rewrite their historical rationale; add a superseding ADR when the decision changes.
- Superseded ADRs remain in place so corrections can be reviewed.

| ADR | Title | Status |
|---|---|---|
| [0001](0001-project-constitution.md) | Project constitution | Accepted |
| [0002](0002-shared-substrate-and-lane-boundaries.md) | Shared substrate and lane boundaries | Open |
| [0003](0003-initial-browser-backend.md) | Initial browser backend and action mechanisms | Open |
| [0004](0004-trace-storage.md) | Trace event log and artifact storage | Accepted |
| [0005](0005-experiment-gating.md) | Experiment validity and acceptance gate | Accepted |
| [0006](0006-live-site-testing-policy.md) | Live-site testing isolation and safety | Open |
| [0007](0007-nested-smoke-suite.md) | Smoke suite is nested in the primary suite | Accepted |
| [0008](0008-primary-benchmark-source-shortlist.md) | Primary benchmark-source portfolio | Proposed |
| [0009](0009-regression-suite-seeding-and-promotion.md) | Regression seeding and promotion | Proposed |
| [0010](0010-task-difficulty-calibration-band.md) | Task difficulty calibration band | Superseded/history |
| [0011](0011-minimum-success-floor-for-task-candidates.md) | Minimum 40% floor | Superseded |
| [0012](0012-reference-success-band-35-to-70.md) | Reference success band is 35–70% | Accepted |
| [0013](0013-runnable-evaluation-suite-v0.md) | Runnable suite bridge convention and initial 100-task draft | Superseded; bridge code remains provisional infrastructure |
| [0014](0014-run-all-140-candidates-before-filtering.md) | Run all 140 before filtering | Accepted |
| [0015](0015-auto-research-loop-architecture.md) | Auto-research loop architecture | Accepted |
| [0016](0016-judge-panel-and-verifier-audit-protocol.md) | Judge panel and verifier audit protocol | Accepted |

The template is in [`TEMPLATE.md`](TEMPLATE.md).
