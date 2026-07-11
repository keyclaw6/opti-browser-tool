# Opti Browser Tool

Research infrastructure for discovering which browser-agent harness designs produce the most reliable computer and browser use.

**Repository status:** groundwork. The project charter is accepted from the initiating brief. Technical choices not explicitly accepted are recorded as proposals, not as settled policy.

## Mission

Optimize the complete harness around a mostly fixed language model so that an agent can navigate difficult, dynamic websites, understand interface state, perform useful actions, recover from mistakes, and complete tasks consistently.

Task success and repeatability come first. Time, tokens, cost, action count, retries, and latency are measured to explain behavior and compare equally reliable systems; lower cost does not compensate for lower reliability.

## First milestone

Build a trustworthy auto-research substrate before attempting a final hybrid browser agent. The milestone is complete when the project can:

1. run a versioned browser task against an immutable baseline and a treatment;
2. emit synchronized, replayable traces and browser artifacts;
3. verify completion without trusting the executor's claim;
4. distinguish executor failure, browser/tool failure, evaluator failure, and invalid implementation;
5. gate a proposed change through smoke, regression, main-suite, and holdout evaluation; and
6. record a falsifiable experiment and its result for the next research iteration.

## Research lanes

- **Visual-first:** screenshots and visible state are primary.
- **Terminal/CLI:** concise observations and a compact command language are primary.
- **Hybrid:** deferred until the first two lanes have credible independent baselines.

The lanes share task, trace, metric, verifier, and experiment contracts but keep their observation and action policies separate.

## Decision discipline

Accepted decisions live in `docs/adr/`. Proposals remain marked `Proposed` until explicitly accepted. See `docs/DECISION_PROCESS.md` and `docs/DECISION_REGISTER.md`.

## Repository map

```text
docs/adr/                 accepted and proposed architecture decisions
docs/architecture/        shared system design
docs/evaluation/          evaluation and gating rules
docs/safety/              permitted live-site testing policy
schemas/                  draft machine-readable contracts
examples/                 example task and experiment records
```

## Reference projects

- `neosigmaai/auto-harness`: benchmark → analyze → improve → gate → record → learnings.
- `china-qijizhifeng/agentic-harness-engineering`: trace-first observability, component-level evolution, change manifests, and falsifiable predictions.

See `docs/REFERENCES.md` for the ideas adopted and the differences required for browser agents.
