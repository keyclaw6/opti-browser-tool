# Decision Register

Only entries marked **Accepted** are active project decisions. **Open** means intentionally unresolved. **Proposed** means documented for review but not binding. **Superseded** entries remain for audit history.

- Read [`DECISION_TIMELINE.md`](DECISION_TIMELINE.md) for chronological rationale and corrections.
- Read [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md) for the compact current-state interpretation.
- Read [`REVIEW_GUIDE.md`](REVIEW_GUIDE.md) for independent verification.

The codebase may contain provisional scaffolding for an unresolved question; implementation existence does not change ADR status.

| ADR | Title | Status | Why or next step |
|---|---|---|---|
| [0001](adr/0001-project-constitution.md) | Project constitution | Accepted | Governing objective and constraints from the project brief |
| [0002](adr/0002-shared-substrate-and-lane-boundaries.md) | Shared substrate and lane boundaries | Open | Research existing harness structures before choosing |
| [0003](adr/0003-initial-browser-backend.md) | Initial browser backend and action mechanisms | Open | Compare current browser/control foundations and hypotheses first |
| [0004](adr/0004-trace-storage.md) | Trace event log and artifact storage | Open | Study candidate harness and benchmark trace requirements |
| [0005](adr/0005-experiment-gating.md) | Experiment validity and acceptance gate | Open | Adapt and validate the two reference auto-research projects |
| [0006](adr/0006-live-site-testing-policy.md) | Live-site testing isolation and safety | Open | Define detailed controls before live-site execution |
| [0007](adr/0007-nested-smoke-suite.md) | Smoke suite is nested in the primary suite | Accepted | Explicit project-owner direction |
| [0008](adr/0008-primary-benchmark-source-shortlist.md) | Primary evaluation benchmark-source portfolio | Proposed | Source allocation remains subject to task-level validation |
| [0009](adr/0009-regression-suite-seeding-and-promotion.md) | Regression-suite seeding and promotion | Proposed | Calibrate thresholds from repeated baseline runs |
| [0010](adr/0010-task-difficulty-calibration-band.md) | Task difficulty calibration band | Superseded | Original 35–70 proposal; sequence clarified by ADR-0012 |
| [0011](adr/0011-minimum-success-floor-for-task-candidates.md) | Minimum 40% success floor | Superseded | Numeric floor corrected by project owner |
| [0012](adr/0012-reference-success-band-35-to-70.md) | Reference success band is 35–70% | Accepted | Explicit project-owner correction and approval |
| [0013](adr/0013-runnable-evaluation-suite-v0.md) | Runnable 100-task suite draft and bridge convention | Superseded | 100-task suite replaced by ADR-0014; bridge code remains provisional infrastructure, not a browser-foundation decision |
| [0014](adr/0014-run-all-140-candidates-before-filtering.md) | Run all 140 candidates before filtering | Accepted | Explicit project-owner direction; final filtering follows validation |
