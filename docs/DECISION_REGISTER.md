# Decision Register

Only entries marked **Accepted** are active project decisions. **Open** means the question is intentionally unresolved. **Proposed** means a concrete direction has been documented for review but is not binding.

| ADR | Title | Status | Why or next step |
|---|---|---|---|
| [0001](adr/0001-project-constitution.md) | Project constitution | Accepted | Governing research objective and constraints from the project brief |
| [0002](adr/0002-shared-substrate-and-lane-boundaries.md) | Shared substrate and lane boundaries | Open | Compare structures used by existing harnesses before selecting one |
| [0003](adr/0003-initial-browser-backend.md) | Initial browser backend and action mechanisms | Open | Survey current browser harnesses, form hypotheses, and run a focused comparison |
| [0004](adr/0004-trace-storage.md) | Trace event log and artifact storage | Open | Study trace requirements and formats used by candidate harnesses and benchmarks |
| [0005](adr/0005-experiment-gating.md) | Experiment validity and acceptance gate | Open | Adapt and validate ideas from the two reference auto-research projects |
| [0006](adr/0006-live-site-testing-policy.md) | Live-site testing isolation and safety | Open | Define detailed operating controls before any live-site execution |
| [0007](adr/0007-nested-smoke-suite.md) | Smoke suite is nested in the primary suite | Accepted | Explicit project-owner direction; use the same audited tasks and settings in both roles |
| [0008](adr/0008-primary-benchmark-source-shortlist.md) | Primary evaluation benchmark-source portfolio | Proposed | Audit the revised multi-source portfolio—including WARC-Bench and conditional WebForge—before approving exact sources, counts, or task IDs |
| [0009](adr/0009-regression-suite-seeding-and-promotion.md) | Regression-suite seeding and promotion | Proposed | Calibrate initial seeding and promotion thresholds from repeated baseline runs before approval |
| [0010](adr/0010-task-difficulty-calibration-band.md) | Task difficulty calibration band | Superseded | Internal 35–70% proposal was never accepted; ADR-0011 records the owner-approved 40% minimum |
| [0011](adr/0011-minimum-success-floor-for-task-candidates.md) | Minimum success floor for task candidates | Accepted | Explicit project-owner direction: prioritize sources and tasks with at least 40% strong-system success; benchmark aggregates are sourcing evidence only |
