# Opti Browser Tool

Research infrastructure for discovering which browser-agent harness designs produce the most reliable computer and browser use.

**Repository status:** pre-research groundwork. The project charter is accepted. No browser backend, control library, lane architecture, trace store, experiment gate, or detailed live-site operating policy has been selected yet.

## Mission

Optimize the complete harness around a mostly fixed language model so that an agent can navigate difficult, dynamic websites, understand interface state, perform useful actions, recover from mistakes, and complete tasks consistently.

Task success and repeatability come first. Time, tokens, cost, action count, retries, and latency are measured to explain behavior and compare equally reliable systems; lower cost does not compensate for lower reliability.

## Work required before auto-research begins

The project will not start the outer optimization loop until four prerequisite workstreams are complete enough to support trustworthy experiments:

1. **Harness landscape and baseline selection.** Study existing browser-agent implementations, including the repositories collected for this project. Extract their browser/control stack, observation and action interfaces, recovery methods, instrumentation, and known tradeoffs. Turn those findings into falsifiable hypotheses and select the first baseline only after review.
2. **Evaluation-suite construction.** Audit relevant benchmarks and tasks by failure-mode coverage. Build a provisional 20-task bring-up set, then a stable 10–20-task smoke suite and an approximately 100-task primary suite. Define regression and hidden-holdout handling separately. Verify the selected tasks by running them through a known working harness before treating the suite as valid.
3. **Verifier and judge construction.** Prefer deterministic state verifiers, define the evidence available to each judge, calibrate the judge panel on labeled traces, and test false-positive, false-negative, disagreement, and evaluator-gaming cases.
4. **Research-loop integration.** Reuse the proven loop structure from `neosigmaai/auto-harness` and the trace-driven, falsifiable change process from `china-qijizhifeng/agentic-harness-engineering`, then add the browser-specific observability, implementation-audit, and evaluator safeguards required here.

These workstreams are described in `docs/PRE_RESEARCH_WORKSTREAMS.md`. They are planning boundaries, not completed research.

## Decision discipline

Only ADR-0001, the project constitution, is accepted. ADR-0002 through ADR-0006 are open questions and contain candidate directions or research requirements only. Nothing in an open ADR is active policy until explicitly accepted.

See `docs/DECISION_PROCESS.md` and `docs/DECISION_REGISTER.md`.

## Repository map

```text
docs/adr/                    accepted and open architecture decisions
docs/architecture/           provisional problem decomposition
docs/evaluation/             evaluation principles and suite planning
docs/PRE_RESEARCH_WORKSTREAMS.md
research/harnesses/           future harness surveys and hypotheses
research/benchmarks/          future benchmark and task reviews
research/judges/              future verifier and judge studies
schemas/                      draft machine-readable contracts
examples/                     example task and experiment records
```

## Reference projects

- `neosigmaai/auto-harness`: benchmark → analyze → improve → gate → record → learnings.
- `china-qijizhifeng/agentic-harness-engineering`: trace-first observability, component-level evolution, change manifests, and falsifiable predictions.

See `docs/REFERENCES.md` for the ideas to reuse and the browser-specific additions under consideration.
