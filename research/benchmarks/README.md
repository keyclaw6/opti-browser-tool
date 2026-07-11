# Benchmark and Task Research

## Current benchmark-level result

- [Benchmark source selection report, 2026-07-11](2026-07-11-benchmark-source-selection-report.md)
- [ADR-0008: proposed primary benchmark-source portfolio](../../docs/adr/0008-primary-benchmark-source-shortlist.md)
- [Candidate comparison matrix](benchmark-candidate-matrix.csv)
- [Machine-readable candidate record](candidate-benchmarks.yaml)
- [Task audit template](TASK_AUDIT_TEMPLATE.md)

The source portfolio is proposed, not accepted. Individual task IDs have not been selected. The latest revision promotes WARC-Bench into the candidate allocation after locating its public archived environments and programmatic evaluators; EntWorld and RiskWebWorld remain unallocated until authoritative runnable releases can be verified.

## Next execution step

Build a versioned candidate pool of roughly 200–250 tasks using the proposed allocation as a sampling guide. Audit each task for interaction relevance, difficulty, reset, verifier behavior, duplication, licensing, safety, and shortcut susceptibility. Then run a simple baseline and a known strong harness before presenting an exact 100-task manifest and nested 20-task smoke subset for approval.

## Required final outputs

- benchmark-level environment and licensing audit;
- one audit record per candidate task;
- browser-interaction failure taxonomy and coverage matrix;
- approximately 100-task primary suite;
- 20-task smoke subset nested in the primary suite under ADR-0007;
- replacement pool;
- separate regression and hidden-holdout protocols; and
- validation results from a known working harness.
