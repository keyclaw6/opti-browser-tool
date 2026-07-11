# ADR-0012: Reference success band is 35–70%

Status: **Accepted**

Date: 2026-07-11

Decision owner: Project owner

## Context

The suite must leave enough headroom for harness improvements without concentrating on tasks so difficult that changes are difficult to measure. A prior record incorrectly used a 40% floor.

## Decision

Candidate tasks are sourced from benchmark families whose strongest relevant public reference result is between **35% and 70%, inclusive**.

Before the suite is frozen, every task must also be calibrated locally with a pinned strong reference harness. Tasks whose measured task-level success is below 35% or above 70% are replaced unless a separately documented diagnostic reason justifies retaining them.

Benchmark-level results may screen a source family, but may not be presented as task-level success evidence.

## Why

- Below 35%, many repeated trials are needed to distinguish modest improvements from noise.
- Above 70%, the remaining headroom may be too small and saturation becomes a larger concern.
- The band supports measurable improvement while retaining substantial failure evidence for the auto-research loop.

## Consequences

The current 140-task candidate/primary pool is provisional until per-task calibration is complete; it will later be filtered toward the final approximately 100-task suite. Source-level results are stored separately from the empty per-task calibration field.
