# Benchmark and task research

This area records benchmark-source comparisons, exact task candidates, provenance, licensing notes, and the evidence required before final admission.

## Current state

Batch 1 contains 140 exact candidates:

- 30 REAL v1;
- 30 WebArena-Verified;
- 30 WorkArena++ Level 2;
- 30 VisualWebArena; and
- 20 WARC-Bench.

All 140 are normalized into the runnable provisional candidate pool under ADR-0014. The source-family reference results lie in the accepted 35–70% band, but they are not per-task rates. Every candidate remains pending environment, reset, solvability, verifier, duplication, and repeated task-level calibration checks.

The final primary target remains approximately 100 tasks, with a nested 20-task smoke suite. Filtering occurs only after the 140-task pool has validation evidence and every exclusion has a documented reason.

## Files

- `2026-07-11-benchmark-source-selection-report.md`: source-level analysis and proposed portfolio.
- `benchmark-candidate-matrix.csv`: compact source comparison.
- `candidate-benchmarks.yaml`: early source inventory.
- `TASK_AUDIT_TEMPLATE.md`: review template for task admission.
- `task-candidates/`: exact Batch 1 records, summaries, provenance locks, and calibration plan.
- `scripts/`: generation and consistency checks for the candidate batch.

## Evidence boundary

Benchmark-level scores may screen a source family. They must not be copied onto every task. Final task admission requires a pinned reference harness, repeated runs, uncertainty reporting, and verifier/environment validity.
