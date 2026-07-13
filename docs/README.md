# Documentation map

This directory is the review surface for Opti Browser Tool. A new implementation or review agent should not infer project policy from code alone; read the accepted decisions and current-state documents first.

## Recommended reading order

1. [`../PROJECT_CHARTER.md`](../PROJECT_CHARTER.md) — objective, scope, invariants, and definition of success.
2. [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md) — current state, completed work, evidence boundaries, and next execution steps.
3. [`DECISION_PROCESS.md`](DECISION_PROCESS.md) — how a suggestion becomes a binding decision.
4. [`DECISION_REGISTER.md`](DECISION_REGISTER.md) — authoritative status of every ADR.
5. [`DECISION_TIMELINE.md`](DECISION_TIMELINE.md) — chronological explanation of corrections and supersessions.
6. [`TASK_DATA_GUIDE.md`](TASK_DATA_GUIDE.md) — exactly which task material is included and which upstream assets are not.
7. [`evaluation/RUNNABLE_SUITE_V0.md`](evaluation/RUNNABLE_SUITE_V0.md) — current 140-task runner and validation boundary.
8. [`REVIEW_GUIDE.md`](REVIEW_GUIDE.md) — independent checks for a review agent.
9. [`../validation/README.md`](../validation/README.md) — what each stored validation artifact proves and does not prove.
10. [`ROADMAP.md`](ROADMAP.md) and [`OPEN_QUESTIONS.md`](OPEN_QUESTIONS.md) — remaining work and unresolved choices.

## Authoritative current records

- The project charter and **Accepted** ADRs are binding.
- The decision register is the authoritative index of ADR status.
- `evals/catalog/tasks.jsonl` is the canonical normalized 140-task catalog.
- `evals/suites/*.json` are the active suite-membership manifests.
- `research/benchmarks/task-candidates/batch-1-candidates.jsonl` is the immutable raw candidate inventory from which the normalized catalog is generated.
- `MANIFEST.sha256` and `FILE_INVENTORY.tsv` describe the checked repository contents at the recorded commit.

## Historical and nonbinding records

- Open and proposed ADRs are not defaults.
- `loop_harness/` (the auto-research loop conductor), `harness/` (the component-tree scaffold), and `judge_harness/` (probe-kit admission, T1 cross-checks, quarantine, calibration corpus, T2 panel scaffolding per **Proposed** ADR-0016) are provisional implementation shells; their existence does not accept any ADR, no judge is calibrated or trusted, and no loop verdict over synthetic adapters is benchmark evidence.
- The loop runs against a **trusted experiment boundary** (v2, after the adversarial review in `docs/AUTO_RESEARCH_REVIEW_PROMPT.md`): conductor state lives in an owner-only store OUTSIDE the repo, the optimizer works in an isolated worktree, the file guard is authoritative over the base→candidate commit diff, and only a typed `(accepted, benchmark)` verdict advances state. See `loop_harness/README.md`.
- Superseded ADRs remain only to explain how the project changed.
- `archive/superseded/runnable-suite-v0-100/` preserves the incomplete 100-task implementation for audit; it is not active.
- Research reports may contain proposals that were later corrected or superseded. Their current-status notices and the decision register take precedence.

## Current accepted decisions

- ADR-0001: project constitution.
- ADR-0007: the smoke suite is nested in the primary suite.
- ADR-0012: the target task-level reference-success band is 35–70%, inclusive.
- ADR-0014: run all 140 provisional candidates before filtering toward the final suite.

No browser backend, browser-control library, final lane architecture, trace store, complete experiment gate, or live-site operating policy has been accepted.
