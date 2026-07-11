# Opti Browser Tool

Research infrastructure for discovering which browser-agent harness designs produce the most reliable computer and browser use.

## Current status

This repository contains the complete planning and benchmark-selection work produced so far, together with a runnable backend-neutral evaluation runner.

- **140 exact provisional task candidates** are normalized in `evals/catalog/tasks.jsonl`.
- The active provisional `primary` and `candidate-pool` manifests both include all 140 tasks, following ADR-0014.
- A **20-task smoke suite** is nested in the 140-task pool.
- The same 20 tasks form a provisional regression seed until repeated baseline runs establish stable permanent gates.
- The accepted reference-success band is **35–70%, inclusive**. Published benchmark aggregates screen source families only; every task still needs local repeated calibration.
- No browser backend, control library, agent lane, trace store, final experiment gate, or detailed live-site operating policy has yet been selected.
- Real browser execution requires source bridges for REAL v1, WebArena-Verified, WorkArena++ L2, VisualWebArena, and WARC-Bench. Missing environments or verifiers fail closed rather than counting as model failures.

The incomplete 100-task runnable-suite draft is preserved exactly under `archive/superseded/runnable-suite-v0-100/` for audit.

## Mission

Optimize the complete harness around a mostly fixed language model so that an agent can navigate difficult, dynamic websites, understand interface state, perform useful actions, recover from mistakes, and complete tasks consistently.

Task success and repeatability come first. Time, tokens, cost, action count, retries, and latency are measured to explain behavior and compare equally reliable systems; lower cost does not compensate for lower reliability.

## Quick validation

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ./eval_harness

opti-eval validate
opti-eval list --suite smoke
opti-eval run \
  --suite primary \
  --adapter fixture \
  --max-workers 8 \
  --output runs/all-140-fixture
```

The fixture adapter verifies orchestration only. Its output is marked `benchmark_reportable=false` and must never be presented as browser-agent performance.

See `eval_harness/README.md` for the command and registry bridge contracts.

## Decision discipline

Accepted decisions currently include:

- ADR-0001: project constitution;
- ADR-0007: smoke tasks are nested in the primary set;
- ADR-0012: reference success must be calibrated in the 35–70% band; and
- ADR-0014: execute all 140 provisional candidates before filtering the final suite.

ADR-0002 through ADR-0006 remain open. ADR-0008 and ADR-0009 remain proposed. ADR-0011's 40% floor and ADR-0013's 100-task active count are retained as superseded history.

See `docs/DECISION_PROCESS.md` and `docs/DECISION_REGISTER.md`.

## Repository map

```text
docs/                         charter, roadmap, evaluation policy, ADRs
research/benchmarks/          benchmark-source research and exact 140-task batch
research/harnesses/           future harness landscape work
research/judges/              future verifier and judge work
evals/catalog/                normalized 140-task catalog and source partitions
evals/suites/                 active 140-task, smoke, and regression manifests
evals/schemas/                task, suite, bridge-result, and summary schemas
eval_harness/                 installable `opti-eval` runner and tests
scripts/                      catalog generation and completeness checks
archive/superseded/           preserved incomplete/superseded implementation
schemas/ and examples/        earlier draft cross-project contracts
RECOVERY_MANIFEST.md          reconstruction and preservation audit
```

## Reference projects

- `neosigmaai/auto-harness`: benchmark → analyze → improve → gate → record → learnings.
- `china-qijizhifeng/agentic-harness-engineering`: trace-first observability, component-level evolution, change manifests, and falsifiable predictions.

See `docs/REFERENCES.md` for the ideas to reuse and browser-specific additions under consideration.
