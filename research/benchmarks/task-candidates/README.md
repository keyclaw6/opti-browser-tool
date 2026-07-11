# Batch 1 exact task candidates

This directory preserves the first 140 exact candidates and the source evidence used to find them. The rows are not final admissions.

## Accepted calibration rule

ADR-0012 requires repeated task-level reference success between **35% and 70%, inclusive** before final admission, absent an explicitly documented diagnostic exception.

The candidate files predate the correction and retain a legacy field named `public_benchmark_reference_at_least_40_percent`. That field is historical source-screening metadata, not the current decision rule. The active normalized catalog under `evals/catalog/` records the accepted 35–70% band and leaves every per-task rate empty.

## Contents

- `batch-1-candidates.jsonl` and `.csv`: all 140 exact raw candidate records.
- `batch-1-index.md`: human-readable task list.
- `batch-1-report.md`: selection rationale and limitations.
- `batch-1-source-audit.md`: source-manifest consistency checks.
- `batch-1-sources.lock.json`: pinned source revisions and checksums.
- `batch-1-selection.json`: historical selection program output.
- summary CSVs by source, site, and interaction class.
- `CALIBRATION_PLAN.md`: required validation stages.
- `UPSTREAM_LICENSES.md`: licensing notes.

## Current suite relationship

All 140 candidates are present in the active provisional candidate/primary manifests. The 20 smoke tasks are nested inside them. The superseded 100-task draft is preserved under `archive/superseded/runnable-suite-v0-100/`.
