# Task candidate inventory

This directory contains versioned task candidates for the browser-agent evaluation suite. A candidate is not an admitted primary-suite task.

## Batch 1

Batch 1 contains 140 exact task identities from five benchmark families:

- 30 REAL v1 tasks;
- 30 WorkArena++ L2 task-and-seed pairs;
- 30 WebArena-Verified tasks;
- 30 VisualWebArena tasks; and
- 20 WARC-Bench held-out-test candidates.

All five public benchmark-level reference scores are at least 40%, satisfying ADR-0011's source-screening floor. Public evidence does not establish that each individual task clears the 40% task-level floor. Every row therefore carries:

- `score_evidence_scope=benchmark_aggregate_not_task_level`;
- an empty `per_task_reference_success_percent`; and
- `per_task_calibration_status=required_before_final_admission`.

For calibration order, 117 candidates are Priority A and 23 are Priority B. Priority B consists of 14 metadata-flagged harder tasks and nine visual navigation/search tasks. This is an audit sequence, not a result or admission decision.

## Files

- `batch-1-index.md` — human-readable table of every exact candidate.
- `batch-1-candidates.csv` — review-friendly table with exact IDs, goals, versions, score provenance, evaluator metadata, and audit flags.
- `batch-1-candidates.jsonl` — machine-readable equivalent.
- `batch-1-selection.json` — the exact selectors used to construct the batch.
- `batch-1-sources.lock.json` — package versions, source paths, and manifest checksums.
- `batch-1-summary-by-*.csv` — generated coverage summaries.
- `batch-1-report.md` — rationale, limitations, and calibration plan.
- `batch-1-source-audit.md` — source-manifest identity checks and their limitations.
- `UPSTREAM_LICENSES.md` — source-version and upstream-license notices for the task metadata.

## Admission status

No Batch 1 task is yet part of the frozen 100-task primary suite, smoke suite, hidden holdout, or regression suite. The next gate is task-level calibration plus verifier and environment auditing.
