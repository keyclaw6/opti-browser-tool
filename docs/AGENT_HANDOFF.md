# Agent handoff: current project state

Date: 2026-07-11

## Purpose of this document

This is the shortest reliable handoff for another agent. It records what has actually been completed, what remains provisional, which decisions are binding, and where the evidence lives. It does not replace the ADRs or task records.

Use [`DECISION_TIMELINE.md`](DECISION_TIMELINE.md) to reconstruct why decisions changed, [`TASK_DATA_GUIDE.md`](TASK_DATA_GUIDE.md) to inspect task completeness, and [`REVIEW_GUIDE.md`](REVIEW_GUIDE.md) to verify the repository independently.

## Project objective

Build an auto-research system that can discover improvements to a browser-agent harness while holding the base executor model fixed within an experiment. The primary target is reliable completion of difficult browser interactions, not search or question answering in isolation.

The intended outer loop is adapted from two reference projects:

- `neosigmaai/auto-harness`: benchmark → analyze → improve → gate → record → update learnings → repeat;
- `china-qijizhifeng/agentic-harness-engineering`: trace-first diagnosis, constrained component changes, activation audits, predicted task flips, and falsifiable change attribution.

Browser-specific additions still need to be designed and validated: executor-versus-judge visibility boundaries, synchronized browser artifacts, action-mechanism tracking, dynamic-site variance, state reset, and verifier safeguards.

## Completed work

1. The project charter, decision process, roadmap, open questions, preliminary architecture decomposition, evaluation principles, and live-site safety direction are documented.
2. Existing benchmark families were compared and a provisional candidate portfolio was developed.
3. A raw inventory of 140 exact candidate records was created:
   - 30 REAL v1;
   - 30 WebArena-Verified;
   - 30 WorkArena++ Level 2;
   - 30 VisualWebArena; and
   - 20 WARC-Bench.
4. The 140 records were normalized into a common catalog with upstream locators, goals, source evidence, verification status, runtime bridge key, and complete raw provenance.
5. All 140 candidates are in the active provisional primary/candidate pool. Twenty are also in the nested smoke suite and provisional regression seed.
6. A backend-neutral orchestration runner exists with fixture, command, and source-registry adapters. It validates plumbing but does not yet provide the five real benchmark bridges.
7. The repository was reconstructed from earlier complete archives after an incomplete working directory was detected. The recovered Git history and superseded 100-task draft are preserved.

## Binding decisions

Only decisions marked **Accepted** in `docs/DECISION_REGISTER.md` are binding:

- ADR-0001 — governing objective and constraints;
- ADR-0004 — trace event log and artifact storage (accepted 2026-07-13);
- ADR-0005 — the E0–E5 experiment gate (accepted 2026-07-13; thresholds from measurement);
- ADR-0007 — smoke is a subset of primary;
- ADR-0012 — locally calibrated task-level success should be 35–70%, inclusive;
- ADR-0014 — execute all 140 candidates before filtering;
- ADR-0015 — auto-research loop architecture (accepted 2026-07-13);
- ADR-0016 — judge panel and verifier audit protocol (accepted 2026-07-13).

The 35–70 rule has an important evidence boundary: current public percentages are benchmark-family aggregates. They screened source families only. No individual task has yet been shown to fall inside the band.

## Implemented conventions that are not architecture selections

The normalized manifests, bridge result contract, fixture runner, and fail-closed handling are implemented so the evaluation work can proceed without choosing a browser-control substrate. Their existence does **not** select Playwright, Selenium, BrowserGym, CDP, native pointer input, a visual-only lane, or a CLI lane as the final foundation.

ADR-0013 is retained as a superseded historical record because its original active suite contained 100 tasks. The current 140-task definition is governed by ADR-0014. The bridge code is provisional infrastructure and may be revised after harness research.

## What is not complete

- No real benchmark source bridge is implemented or audited.
- Upstream website environments, WACZ archives, ServiceNow instances, images, credentials, browser profiles, and evaluator packages are not vendored.
- No task has a locally measured task-level success rate.
- No task has completed the full reset, known-good-run, adversarial-verifier, repetition, safety, and duplication audit.
- The final approximately 100-task primary suite is not frozen.
- The current 20-task regression manifest is only a seed, not a permanent regression gate.
- The browser/backend baseline, harness architecture, trace store, judge council, hidden holdout, and auto-research acceptance gate remain unresolved.

## Where the actual task records are

Read `docs/TASK_DATA_GUIDE.md` for the exact distinction between included task definitions and external runtime assets. In brief:

- canonical normalized task records: `evals/catalog/tasks.jsonl`;
- one file per normalized task: `evals/catalog/by-id/<source>/<task-id>.json`;
- raw candidate records: `research/benchmarks/task-candidates/batch-1-candidates.jsonl`;
- human-readable list of every task goal: `research/benchmarks/task-candidates/batch-1-index.md`;
- suite membership: `evals/suites/*.json`.

## Immediate next execution phase

1. Research existing browser harnesses and make an explicit first-baseline recommendation without silently choosing a backend.
2. Pin and install the five upstream benchmark environments.
3. Implement one source bridge per benchmark and prove reset, task resolution, trace capture, and native verifier execution.
4. Run known-good/oracle paths and adversarial verifier checks.
5. Run a pinned strong reference harness repeatedly over all 140 candidates.
6. Record task-level uncertainty and filter toward the final suite, documenting every exclusion.
7. Build and calibrate the completion, process, root-cause, implementation-audit, and adjudication judges.

## Rules for the next agent

- Do not convert an open or proposed ADR into a default through implementation convenience.
- Do not report fixture-adapter scores as benchmark performance.
- Do not copy a benchmark aggregate onto individual task records.
- Treat reset, account, environment, verifier, or adapter failure as invalid/error, not model failure.
- Preserve raw task provenance and record every task exclusion or replacement.
- Add or supersede ADRs rather than silently rewriting accepted historical rationale.
