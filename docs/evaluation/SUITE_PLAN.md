# Evaluation Suite Plan

This document records accepted suite relationships and current target sizes. Exact benchmark sources and task IDs remain subject to ADR-0008 and task-level audit.

## Primary suite — approximately 100 tasks

The principal visible evaluation used for meaningful baseline and treatment comparisons after the infrastructure is validated. Selection must be stratified by interaction failure mode and checked for reproducibility, verifier quality, difficulty headroom, and safety.

The primary task manifest is constructed first. Every task receives a source revision, environment revision, evaluator revision, seed or initial state, action budget, timeout, and failure-mode tags.

## Smoke suite — approximately 20 tasks, nested in primary

ADR-0007 establishes that every smoke case is also a primary-suite case. The smoke set is a stable, fast implementation gate covering every benchmark adapter and the principal interaction mechanisms.

A smoke result may be reused in the primary run only when every execution and evaluation setting is identical. Smoke performance is not an independent estimate of general capability.

During bring-up, these same cases are used to validate runners, reset logic, traces, action dispatch, and verifiers; there is no separate disposable task pool unless a temporary diagnostic case is explicitly labeled as such.

## Regression suite

A separate, growing set of important invariants and previously failing tasks that have been fixed. The smoke cases provide stable integration regressions, while capability regressions are promoted with their motivating trace evidence after fixes survive repeated verification. Exact promotion policy is proposed in ADR-0009 and remains unaccepted; final gating also depends on ADR-0005.

## Hidden holdout

A protected transfer check unavailable to the optimizing agent. Holdout traces and private verifier logic must not be used to invent changes. The holdout is disjoint from both visible suites.

## Separate live-site transfer suite

Permitted-account live tasks are scored separately from the controlled primary suite because account state, regional interfaces, bot defenses, and website drift create a different validity regime. No live task runs before ADR-0006 is accepted.

## Validation requirement

Before a task set is frozen, run it through a known working harness and inspect setup, reset, completion state, verifier output, artifacts, and instability. Broken or ambiguous tasks must be repaired, replaced, or explicitly quarantined. Using an existing framework to validate a benchmark does not select that framework as the project's final browser substrate.
