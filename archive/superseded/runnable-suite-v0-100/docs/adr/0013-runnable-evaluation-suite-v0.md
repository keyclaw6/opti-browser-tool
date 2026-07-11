# ADR-0013: Runnable evaluation suite v0 uses manifests and benchmark bridges

Status: **Accepted for v0 implementation**

Date: 2026-07-11

## Context

The project needs an executable 100-task suite before selecting a browser backend or final harness architecture. The tasks come from five benchmark ecosystems with different setup, reset, task, and verifier interfaces.

## Decision

Implement the suite as:

- one normalized 100-task primary manifest;
- one 20-task smoke manifest that is a strict subset of primary;
- one provisional 20-task regression seed, initially equal to smoke;
- an immutable normalized task catalog preserving upstream IDs and raw candidate provenance;
- a standard result contract;
- a benchmark bridge interface that invokes each source's environment and native verifier;
- fixture and generic command adapters for plumbing tests;
- fail-closed treatment of missing environments, reset failures, and verifier failures.

Do not bind the suite itself to Playwright, BrowserGym, Selenium, CDP, or a particular agent lane.

## Why

A bridge boundary makes task selection and scoring stable while the browser-control architecture remains an open research question. It also lets visual-first, CLI, and hybrid systems run the exact same suite and produce comparable result records.

## Alternatives considered

### Hardwire all tasks to BrowserGym

Rejected for v0 because it would make an architectural decision before the browser-harness research is complete and does not natively cover every selected source.

### Maintain one independent runner per benchmark

Rejected because result formats, failure classification, artifact paths, and experiment validity would drift.

### Treat unavailable environments as task failures

Rejected because that would confound infrastructure reliability with agent capability.

## Consequences

Five real benchmark bridges still need to be implemented and audited. Until then, fixture runs prove runner plumbing only; they do not measure browser-agent performance.
