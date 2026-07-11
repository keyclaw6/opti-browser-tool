# ADR-0004: Trace event log and artifact storage

- Status: Proposed
- Date proposed: 2026-07-11

## Context

Browser runs produce structured events and large binary artifacts. The project needs exact reconstruction, efficient cross-run analysis, privacy controls, and schema evolution.

## Decision

Make an append-only JSONL event stream the canonical trace. Store screenshots, DOM/accessibility snapshots, Playwright traces, HAR files, console logs, network summaries, and video as immutable content-addressed artifacts referenced from events.

Build derived DuckDB/Parquet indexes for analysis and dashboards. Derived stores are disposable; the event stream and referenced artifacts are authoritative.

Every event includes a schema version, run and event identifiers, sequence and timestamps, actor, visibility class, browser-state epoch, payload, artifact references, and redaction metadata.

Separate visibility classes include `executor`, `judge`, `orchestrator`, and `secret`. Executor prompts are constructed only from `executor`-visible events and artifacts.

## Alternatives considered

- One large JSON document per run: simple but fragile for streaming and partial failures.
- Database-only canonical storage: queryable but harder to inspect, migrate, and recover.
- Playwright trace as the sole trace: valuable but insufficient for model calls, judge evidence, and backend neutrality.

## Consequences

Trace volume will be substantial, so retention and compression policies are required. Canonical traces remain human-inspectable. Debug data can be collected without accidentally becoming executor-visible.

## Validation and revisit trigger

A replay/debug tool must locate the browser state before and after an action, connect it to the relevant model observation, and identify missing or corrupted artifacts. Revisit if JSONL throughput or schema migration becomes a bottleneck.
