# ADR-0002: Shared substrate and lane boundaries

- Status: Proposed
- Date proposed: 2026-07-11

## Context

The lanes need comparable results without being forced into one observation or action design. Building each lane as a separate product would create incompatible tasks, traces, and judges; building one universal agent too early would hide architectural differences.

## Decision

Use one monorepo with a narrow shared substrate and lane-specific adapters.

Shared components own task loading, environment setup, browser-session lifecycle, artifact storage, trace events, metrics, verifiers, judges, experiment manifests, and reporting.

Each lane owns its observation compiler, action vocabulary, prompt/policy, planning/recovery loop, and context-management strategy. The hybrid lane is disabled until visual-first and CLI lanes each pass an agreed baseline-readiness gate.

The executor receives only capabilities declared by its lane. Shared instrumentation may collect richer data for judges without exposing it to the executor.

Do not use long-lived Git branches as the primary lane boundary. Keep lanes in explicit directories or packages, pin every experiment to a commit and configuration, and use short-lived branches for reviewable changes. Long-lived lane branches would drift in shared evaluator and trace code and weaken comparisons.

## Alternatives considered

- Separate repositories per lane: clearer isolation but high duplication and weak comparability.
- One universal interface from day one: simpler code layout but likely premature convergence.
- Hybrid-first: may score well early but makes causal research difficult.

## Consequences

Common contracts become high-value, carefully versioned interfaces. Lane code can move quickly without changing evaluator semantics. Cross-pollination is implemented as explicit equivalent experiments rather than silent feature sharing.

## Validation and revisit trigger

Accept if a vertical slice can run the same task through at least two lanes and produce comparable result records without leaking lane-specific observations. Revisit if shared abstractions repeatedly block lane-specific experiments.
