# ADR-0007: Smoke suite is nested in the primary suite

- Status: Accepted
- Date opened: 2026-07-11
- Date proposed: 2026-07-11
- Date accepted: 2026-07-11
- Decision source: explicit project-owner direction in the benchmark-selection discussion
- Supersedes: —
- Superseded by: —

## Context

The project needs a fast implementation gate and an approximately 100-task primary evaluation. Maintaining two unrelated task collections would duplicate setup and verifier work and could allow the smoke run to exercise mechanisms absent from the primary score.

The regression suite serves a different function: it protects stable invariants and capabilities already demonstrated by an accepted harness, and grows when previously failing tasks are fixed.

## Decision

1. The primary visible evaluation will contain approximately 100 tasks.
2. The smoke suite will contain approximately 20 tasks and will be a strict subset of the primary suite.
3. Every smoke task will use the same task definition, source revision, environment revision, initial state, verifier, action budget, timeout, and result semantics when run in smoke or primary mode.
4. A smoke result may be reused in a primary run only when the executor, model, task, environment, budget, and evaluator configurations are identical. Otherwise the task is rerun.
5. Smoke and primary scores will be reported separately. Passing smoke is an implementation-readiness signal, not an independent estimate of general capability.
6. The regression suite remains a separate, dynamic evaluation role. A task may belong to both smoke and regression, but membership in either does not imply membership in the other.
7. The hidden holdout remains disjoint from the visible primary and smoke suites.

## Why this decision was taken

- Every smoke task receives the same task-level audit and verifier maintenance as the primary suite.
- The smoke run catches failures in adapters and mechanisms that contribute to the primary score.
- Environment setup and reset work is not duplicated.
- A smoke failure has a direct interpretation inside the primary distribution.
- Keeping regression separate preserves the gate-and-promotion structure used by `auto-harness` instead of treating all visible tasks as permanent invariants.

## Alternatives considered

### Separate smoke tasks

Rejected for the initial system because it creates two maintenance pools and weakens the connection between a smoke pass and readiness for the primary run.

### A rotating random smoke sample

Not selected because changing membership makes implementation regressions harder to compare. Random subsampling may still be studied as an additional diagnostic after the stable suite exists.

## Consequences

- Passing smoke does not provide independent evidence that primary performance improved.
- The optimizer may see smoke tasks more frequently, so gains concentrated on them must not be overinterpreted.
- The smoke subset must represent every benchmark adapter and major interaction mechanism used by the primary suite.
- A change to primary-suite composition requires reviewing smoke coverage.

## Validation

The accepted suite manifest must:

- mark every smoke task explicitly;
- contain no smoke ID absent from the primary manifest;
- include every primary benchmark source unless a documented setup constraint prevents it;
- verify configuration identity before reusing a smoke result in a primary run; and
- report smoke and primary results separately.

## Revisit triggers

Revisit if the 20-task smoke run becomes too expensive for frequent gating, fails to detect integration defects, or becomes sufficiently overexposed that it no longer provides a useful readiness signal.

## Later implementation note

ADR-0014 temporarily places all 140 candidates in the provisional primary manifest before filtering. The accepted nesting rule remains unchanged: the 20 smoke tasks are contained in both the provisional pool and the eventual approximately 100-task primary suite.
