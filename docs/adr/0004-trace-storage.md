# ADR-0004: Trace event log and artifact storage

- Status: Open
- Date opened: 2026-07-11
- Approval state: Not accepted

## Question

What trace and artifact representation will let the project reconstruct runs, analyze failures, protect restricted evidence, and compare different browser harnesses without excessive complexity?

## Candidate direction under consideration

A possible design is an append-oriented structured event stream with separately stored screenshots, browser traces, DOM or accessibility snapshots, network records, console logs, video, and other artifacts. Visibility metadata could separate executor-visible evidence from judge-only or restricted evidence. Analytical indexes could be derived from the canonical trace.

JSONL, content-addressed artifacts, DuckDB, Parquet, Playwright traces, HAR, CDP events, and equivalent formats are candidates rather than accepted choices.

## Research required

- Inspect trace formats and debuggers used by existing browser harnesses and the two reference auto-research projects.
- Derive concrete replay and diagnosis requirements from the candidate evaluation tasks.
- Compare streaming, partial-failure recovery, schema evolution, queryability, storage cost, redaction, and cross-browser neutrality.
- Prototype only the minimum needed to validate synchronized model, action, browser-state, verifier, and infrastructure evidence.

## Decision gate

Select the canonical trace only after the baseline candidates and bring-up task requirements are understood. Explicit project approval is required.
