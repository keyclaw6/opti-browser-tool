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

## Evidence sources for the loop and judge proposals

The quantitative claims in ADR-0015, ADR-0016, and ADR-0005 trace to:

- AHE paper (method and transfer/ablation/attribution numbers): https://arxiv.org/abs/2604.25850 (also bundled as a PDF in the AHE repository);
- auto-harness method article (failure-cluster prioritization, regression growth): https://www.neosigma.ai/blog/self-improving-agentic-systems
- AgentRewardBench (verifier and LLM-judge precision/recall on 1,302 expert-labeled trajectories): https://arxiv.org/abs/2504.08942
- Online-Mind2Web / WebJudge (key-point judging recipe and agreement rates): https://arxiv.org/abs/2504.01382
- Mind2Web-2 (Agent-as-a-Judge tree rubrics): https://arxiv.org/abs/2506.21506

These citations ground design choices only; none of them supplies task-level difficulty evidence for this project's candidates.

## Benchmark and task-source provenance

The benchmark-family findings are recorded in `research/benchmarks/2026-07-11-benchmark-source-selection-report.md`. Exact source revisions, manifests, and checksums for the 140 candidates are pinned in `research/benchmarks/task-candidates/batch-1-sources.lock.json`; task-level rationale and audit flags are in the adjacent candidate files. Public aggregate results are source-screening evidence only and must not be treated as task-level success.
