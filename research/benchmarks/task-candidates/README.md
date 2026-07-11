# Task candidate inventory

This directory contains versioned task candidates for the browser-agent evaluation suite. A candidate is not an admitted primary-suite task.

## Batch 1

Batch 1 contains 140 exact task identities from five benchmark families:

- 30 REAL v1 tasks;
- 30 WorkArena++ L2 task-and-seed pairs;
- 30 WebArena-Verified tasks;
- 30 VisualWebArena tasks; and
- 20 WARC-Bench held-out-test candidates.

All five public benchmark-level reference scores fall inside the 35–70% sourcing band established in ADR-0010. Public evidence does not establish that each individual task falls inside that band. Every row therefore carries:

- `score_evidence_scope=benchmark_aggregate_not_task_level`;
- an empty `per_task_reference_success_percent`; and
- `per_task_calibration_status=required_before_final_admission`.

## Files

- `batch-1-index.md` — human-readable table of every exact candidate.
- `batch-1-candidates.csv` — review-friendly table with exact IDs, goals, versions, score provenance, evaluator metadata, and audit flags.
- `batch-1-candidates.jsonl` — machine-readable equivalent.
- `batch-1-selection.json` — the exact selectors used to construct the batch.
- `batch-1-sources.lock.json` — package versions, source paths, and manifest checksums.
- `batch-1-summary-by-*.csv` — generated coverage summaries.
- `batch-1-report.md` — rationale, limitations, and calibration plan.
- `UPSTREAM_LICENSES.md` — source-version and upstream-license notices for the task metadata.

## Admission status

No Batch 1 task is yet part of the frozen 100-task primary suite, smoke suite, hidden holdout, or regression suite. The next gate is task-level calibration plus verifier and environment auditing.
