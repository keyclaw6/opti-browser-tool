# Opti Browser Tool

Research infrastructure for discovering which browser-agent harness designs produce the most reliable computer and browser use.

## Start here

A new implementation or review agent should read these in order:

1. [`docs/README.md`](docs/README.md) — documentation map and authority order;
2. [`docs/AGENT_HANDOFF.md`](docs/AGENT_HANDOFF.md) — current state, completed work, evidence boundaries, and next steps;
3. [`docs/DECISION_REGISTER.md`](docs/DECISION_REGISTER.md) — authoritative ADR status;
4. [`docs/TASK_DATA_GUIDE.md`](docs/TASK_DATA_GUIDE.md) — exactly which task material is included; and
5. [`docs/REVIEW_GUIDE.md`](docs/REVIEW_GUIDE.md) — independent review procedure.

## Current status

- **140 provisional task candidates** are preserved in raw and normalized machine-readable form.
- The active provisional `primary` and `candidate-pool` manifests both contain all 140 tasks under ADR-0014.
- A **20-task smoke suite** is nested in the 140-task pool under ADR-0007.
- The same 20 tasks currently form a provisional regression seed; permanent regression policy remains proposed.
- The accepted task-level reference-success band is **35–70%, inclusive** under ADR-0012.
- Public percentages currently stored on tasks are benchmark-family aggregates used for source screening, not per-task measurements.
- The evaluation runner is executable at the orchestration layer. Real browser evaluation still requires audited source bridges and upstream benchmark environments.
- Accepted trace, experiment-gate, judge, and auto-research-loop architectures
  now have reference implementations. No audited real source bridge, calibrated
  judge council, private holdout, or activated production loop exists yet.
  Browser backend, control library, lane architecture, and detailed live-site
  operating policy remain open.

The incomplete 100-task draft is preserved under `archive/superseded/runnable-suite-v0-100/` for audit and is not active.

## Are the actual tasks included?

Yes, with an important boundary.

The repository includes every selected task's textual goal or task-family identity, exact upstream ID, source version, site, provenance, selection rationale, expected verifier category, and suite membership. The main locations are:

- `research/benchmarks/task-candidates/batch-1-candidates.jsonl` — immutable raw candidate inventory;
- `research/benchmarks/task-candidates/batch-1-index.md` — readable list of all 140 goals;
- `evals/catalog/tasks.jsonl` — canonical normalized runner catalog; and
- `evals/catalog/by-id/<source>/<task-id>.json` — one pretty-printed normalized file per task.

The repository does **not** vendor every upstream runtime asset. Website containers, VisualWebArena images, WARC archives, the gated ServiceNow instance, credentials, browser profiles, and native verifier implementations remain external. WorkArena instructions are instantiated upstream from task class and seed. See [`docs/TASK_DATA_GUIDE.md`](docs/TASK_DATA_GUIDE.md) for the source-by-source completeness matrix.

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

The fixture adapter validates catalog, scheduling, result, and artifact plumbing only. Its output is marked `benchmark_reportable=false` and must never be presented as browser-agent performance.

Run the preservation and documentation checks with:

```bash
python scripts/verify_documentation.py --repo-root .
python scripts/verify_repository_completeness.py --repo-root .
python scripts/verify_file_manifest.py --repo-root .
```

## Accepted decisions

- ADR-0001: project constitution;
- ADR-0004: trace event log and artifact storage;
- ADR-0005: experiment validity and acceptance gate;
- ADR-0007: smoke is nested in primary;
- ADR-0012: task-level reference success is calibrated in the 35–70% band;
- ADR-0014: execute all 140 provisional candidates before filtering;
- ADR-0015: auto-research loop architecture;
- ADR-0016: judge panel and verifier audit protocol; and
- ADR-0017: model and infrastructure pins for loop bring-up.

ADR-0002, ADR-0003, and ADR-0006 remain open. ADR-0008 and ADR-0009 remain
proposed. ADR-0011's 40% floor and ADR-0013's active 100-task count are
superseded history. See `docs/DECISION_TIMELINE.md` for the sequence.

## Repository map

```text
docs/                         documentation map, handoff, decision history, review guide, roadmap, ADRs
research/benchmarks/          benchmark-source research and exact 140-task candidate batch
research/harnesses/           future harness landscape research
research/judges/              future verifier and judge research
evals/catalog/                normalized catalog, by-ID records, source partitions, and review CSV
evals/suites/                 active 140-task, smoke, and provisional regression manifests
evals/schemas/                task, suite, bridge-result, and summary schemas
eval_harness/                 installable `opti-eval` orchestration runner and tests
judge_harness/                strict evidence boundary, T0/T1 checks, quarantine, and T2 scaffold
loop_harness/                 deterministic auto-research conductor and acceptance gates
scripts/                      catalog generation and integrity/documentation checks
archive/superseded/           preserved historical implementation drafts
validation/                   stored validation outputs
RECOVERY_MANIFEST.md          reconstruction and preservation record
```

## Reference projects

- `neosigmaai/auto-harness`: benchmark → analyze → improve → gate → record → learnings.
- `china-qijizhifeng/agentic-harness-engineering`: trace-first observability, component-level evolution, change manifests, and falsifiable predictions.

See `docs/REFERENCES.md` for the ideas to reuse and browser-specific additions under consideration.
