# ADR-0013: Runnable evaluation suite v0 uses manifests and benchmark bridges

Status: **Superseded**

Date: 2026-07-11

Superseded by: [ADR-0014](0014-run-all-140-candidates-before-filtering.md)

## Context

The project needed an executable suite before selecting a browser backend or final harness architecture. The first implementation draft normalized 100 candidates, nested a 20-task smoke suite, and defined a bridge contract across five benchmark ecosystems.

## Historical decision

The draft used:

- a normalized 100-task primary manifest;
- a 20-task nested smoke manifest;
- a provisional 20-task regression seed;
- an immutable normalized task catalog preserving upstream IDs and raw provenance;
- a standard result contract;
- source-specific benchmark bridges;
- fixture and generic command adapters; and
- fail-closed treatment of missing environments, reset failures, and verifier failures.

## Current interpretation

ADR-0014 replaces the active suite definition with all 140 candidates. The codebase still uses the backend-neutral manifest, bridge, standardized-result, and fail-closed conventions because they allow task work to proceed without selecting a browser substrate. Their implementation is provisional infrastructure, not an accepted browser-foundation or final architecture decision.

The exact incomplete 100-task draft is preserved under `archive/superseded/runnable-suite-v0-100/`.
