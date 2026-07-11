# ADR-0005: Experiment validity and acceptance gate

- Status: Proposed
- Date proposed: 2026-07-11

## Context

A treatment can appear ineffective because it was not activated, can appear effective because of environment drift, and can improve aggregate score while causing important regressions.

## Decision

Every experiment is paired with an immutable baseline configuration and passes these stages:

1. **Manifest validation:** hypothesis, evidence, predicted improvements, regression risks, fixed variables, task selector, repeats, budget, and acceptance criteria are complete before evaluation.
2. **Implementation audit:** changed components are present, loaded, reachable, and exercised by at least one audit or smoke task. Failure here makes the experiment `invalid`.
3. **Smoke gate:** deterministic fast tasks detect broken setup, browser launch, tracing, action dispatch, and verifier wiring.
4. **Regression gate:** critical tasks have zero tolerance; the broader regression suite uses an explicitly versioned threshold.
5. **Main paired evaluation:** baseline and treatment run under matched environment conditions with repeats appropriate to task instability.
6. **Holdout gate:** used only for candidates that pass visible gates; optimizing agents receive scores and limited diagnostics, not holdout traces.
7. **Decision:** `accepted`, `rejected`, `inconclusive`, or `invalid`.

Primary acceptance is based on task success. Efficiency can break ties or reject pathological waste among treatments with comparable reliability. Infrastructure-affected runs are rerun or excluded under a predeclared policy.

## Alternatives considered

- Accept any higher mean score: fast but highly vulnerable to noise and regressions.
- Require every metric to improve: overly strict and blocks reliability gains.
- Let an LLM judge choose globally: weak reproducibility and hard-to-audit incentives.

## Consequences

Early iterations cost more but produce interpretable evidence. Acceptance thresholds must be calibrated after baseline variance is measured rather than invented once and treated as universal.

## Validation and revisit trigger

Validate by injecting a treatment that is present but disabled, an infrastructure failure, a targeted improvement with a known regression, and an evaluator false positive. The gate should classify each correctly.
