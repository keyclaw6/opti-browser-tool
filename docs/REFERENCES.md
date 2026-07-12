# Reference Projects

## neosigmaai/auto-harness

Adopted ideas:

- program the research loop explicitly;
- make focused, reversible iterations;
- gate changes against a growing regression suite and broader evaluation;
- record iteration results and persistent learnings; and
- prevent the optimizer from freely editing evaluation infrastructure.

Browser-agent adaptation:

- more than one harness component must be evolvable;
- implementation activation needs a dedicated audit;
- dynamic tasks require repeated paired trials; and
- browser state and action traces are first-class artifacts.

## china-qijizhifeng/agentic-harness-engineering

Adopted ideas:

- hold the base model fixed while evolving the harness;
- treat traces as the primary diagnostic object;
- require failure evidence, root cause, targeted fix, and predicted impact;
- track changes by component level;
- attribute later task flips back to prior changes; and
- distinguish component, experience, and decision observability.

Browser-agent adaptation:

- executor-visible observations must be separated from judge-only browser instrumentation;
- action mechanism, tab/session state, and page mutations need explicit trace representation; and
- deterministic browser-state verifiers should lead when available.

Source repositories:

- https://github.com/neosigmaai/auto-harness
- https://github.com/china-qijizhifeng/agentic-harness-engineering

## Benchmark and task-source provenance

The benchmark-family findings are recorded in `research/benchmarks/2026-07-11-benchmark-source-selection-report.md`. Exact source revisions, manifests, and checksums for the 140 candidates are pinned in `research/benchmarks/task-candidates/batch-1-sources.lock.json`; task-level rationale and audit flags are in the adjacent candidate files. Public aggregate results are source-screening evidence only and must not be treated as task-level success.
