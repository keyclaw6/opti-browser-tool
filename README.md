# Opti Browser Tool

Research infrastructure for discovering which browser-agent harness designs produce the most reliable computer and browser use.

**Repository status:** benchmark-source research has produced a first exact candidate batch of 140 tasks, but no task has entered the frozen evaluation suite. The next gate is task-level calibration and verifier/environment auditing under the accepted 40% minimum success floor. The project charter, nested smoke-suite rule, and minimum task-success floor are accepted. The benchmark source portfolio and regression-seeding policy remain proposed. No browser backend, control library, lane architecture, trace store, experiment gate, or detailed live-site operating policy has been selected yet.

## Mission

Optimize the complete harness around a mostly fixed language model so that an agent can navigate difficult, dynamic websites, understand interface state, perform useful actions, recover from mistakes, and complete tasks consistently.

Task success and repeatability come first. Time, tokens, cost, action count, retries, and latency are measured to explain behavior and compare equally reliable systems; lower cost does not compensate for lower reliability.

## Work required before auto-research begins

The project will not start the outer optimization loop until four prerequisite workstreams are complete enough to support trustworthy experiments:

1. **Harness landscape and baseline selection.** Study existing browser-agent implementations, including the repositories collected for this project. Extract their browser/control stack, observation and action interfaces, recovery methods, instrumentation, and known tradeoffs. Turn those findings into falsifiable hypotheses and select the first baseline only after review.
2. **Evaluation-suite construction.** Audit relevant benchmarks and tasks by failure-mode coverage. Build an approximately 100-task primary suite containing a nested 20-task smoke subset. Define regression and hidden-holdout handling separately. Batch 1 records 140 exact provisional candidates under `research/benchmarks/task-candidates/`; none is admitted until its environment, verifier, and task-level strong-system success rate are calibrated.
3. **Verifier and judge construction.** Prefer deterministic state verifiers, define the evidence available to each judge, calibrate the judge panel on labeled traces, and test false-positive, false-negative, disagreement, and evaluator-gaming cases.
4. **Research-loop integration.** Reuse the proven loop structure from `neosigmaai/auto-harness` and the trace-driven, falsifiable change process from `china-qijizhifeng/agentic-harness-engineering`, then add the browser-specific observability, implementation-audit, and evaluator safeguards required here.

These workstreams are described in `docs/PRE_RESEARCH_WORKSTREAMS.md`. They are planning boundaries, not completed research.

## Decision discipline

ADR-0001 (project constitution), ADR-0007 (the smoke suite is a subset of the primary suite), and ADR-0011 (use 40% strong-system success as the minimum candidate floor) are accepted. ADR-0002 through ADR-0006 remain open. ADR-0008 (benchmark sources) and ADR-0009 (regression seeding and promotion) are proposed and are not binding until explicitly accepted.

See `docs/DECISION_PROCESS.md` and `docs/DECISION_REGISTER.md`.

The benchmark evidence and proposed source allocation are in [`research/benchmarks/2026-07-11-benchmark-source-selection-report.md`](research/benchmarks/2026-07-11-benchmark-source-selection-report.md). The exact Batch 1 inventory and its evidence limitations are in [`research/benchmarks/task-candidates/batch-1-report.md`](research/benchmarks/task-candidates/batch-1-report.md) and [`batch-1-index.md`](research/benchmarks/task-candidates/batch-1-index.md).

## Repository map

```text
docs/adr/                    accepted and open architecture decisions
docs/architecture/           provisional problem decomposition
docs/evaluation/             evaluation principles and suite planning
docs/PRE_RESEARCH_WORKSTREAMS.md
research/harnesses/           future harness surveys and hypotheses
research/benchmarks/          benchmark-source report, comparison matrix, and future task reviews
research/judges/              future verifier and judge studies
schemas/                      draft machine-readable contracts
examples/                     example task and experiment records
```

## Reference projects

- `neosigmaai/auto-harness`: benchmark → analyze → improve → gate → record → learnings.
- `china-qijizhifeng/agentic-harness-engineering`: trace-first observability, component-level evolution, change manifests, and falsifiable predictions.

See `docs/REFERENCES.md` for the ideas to reuse and the browser-specific additions under consideration.
