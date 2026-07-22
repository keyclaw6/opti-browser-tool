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
11. [`WARC_ONLINE4_QUALIFICATION.md`](WARC_ONLINE4_QUALIFICATION.md) — the reversible milestone-F config/preflight/operator path and its external blockers.
12. [`PRODUCTION_ACTIVATION_HANDOVER_PROMPT.md`](PRODUCTION_ACTIVATION_HANDOVER_PROMPT.md) — a complete prompt for the next agent to turn the offline checkpoint into honestly calibrated real operation.

## Authoritative current records

- The project charter and **Accepted** ADRs are binding.
- The decision register is the authoritative index of ADR status.
- `evals/catalog/tasks.jsonl` is the canonical normalized 140-task catalog.
- `evals/suites/*.json` are the active suite-membership manifests.
- `research/benchmarks/task-candidates/batch-1-candidates.jsonl` is the immutable raw candidate inventory from which the normalized catalog is generated.
- `MANIFEST.sha256` and `FILE_INVENTORY.tsv` describe the checked repository contents at the recorded commit.

## Historical and nonbinding records

- Open and proposed ADRs are not defaults.
- `loop_harness/` (the auto-research loop conductor), `harness/` (the component-tree scaffold), and `judge_harness/` (probe-kit admission, T1 cross-checks, quarantine, calibration corpus, T2 panel scaffolding) are reference implementations of the **Accepted** ADR-0015/0005/0016 architecture — but the loop is NOT yet authorized to run: pre-activation requirements stand, no judge is calibrated or trusted, and no verdict over synthetic adapters is benchmark evidence.
- The loop runs against a **trusted experiment boundary** (v2, after an earlier adversarial review): conductor state lives in an owner-only store OUTSIDE the repo, the optimizer works in an isolated worktree, the file guard is authoritative over the base→candidate commit diff, and only a typed `(accepted, benchmark)` verdict advances state. The current three-part audit commissions are indexed in [`AUTO_RESEARCH_REVIEW_PROMPT.md`](AUTO_RESEARCH_REVIEW_PROMPT.md). See `loop_harness/README.md`.
- Superseded ADRs remain only to explain how the project changed.
- `archive/superseded/runnable-suite-v0-100/` preserves the incomplete 100-task implementation for audit; it is not active.
- Research reports may contain proposals that were later corrected or superseded. Their current-status notices and the decision register take precedence.

## Current accepted decisions

- ADR-0001: project constitution.
- ADR-0004: trace event log and artifact storage (JSONL stream + content-addressed artifacts).
- ADR-0005: the E0–E5 experiment gate (thresholds TBD-from-measurement; injection catalog before activation).
- ADR-0007: the smoke suite is nested in the primary suite.
- ADR-0012: the target task-level reference-success band is 35–70%, inclusive.
- ADR-0014: run all 140 provisional candidates before filtering toward the final suite.
- ADR-0015: the auto-research loop architecture (trusted experiment boundary, exploration policy).
- ADR-0016: the judge panel and verifier audit protocol (probe-kit admission, calibration-before-trust).
- ADR-0017: model and infrastructure pins (MiniMax-M3 executor; GPT-5.6 Sol Ultra judges; confined single-host deployment).
- ADR-0018: the repeated decision, exact identity/activation,
  candidate-boundary, indivisible-build, atomic advancement, and reversible
  first-adapter readiness transition.

ADR-0018 is accepted for readiness implementation. Its WARC `online.4` with
BrowserGym/Playwright path is a reversible qualification target, not a final
backend selection. ADR-0002 and ADR-0003 remain Open.

No browser backend, browser-control library, final lane architecture, or live-site operating policy has been accepted, and the auto-research loop is not yet authorized to run (pre-activation requirements in ADR-0004/0005 stand).
