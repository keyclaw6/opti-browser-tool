# Evaluation Suite Plan

This document separates the currently runnable candidate pool from the eventual frozen evaluation suites.

## Provisional candidate pool — 140 tasks

ADR-0014 directs the project to execute all 140 sourced candidates before filtering. `evals/suites/candidate-pool.json` and the current provisional `primary.json` therefore contain the same 140 tasks.

This pool exists to measure setup reliability, reset behavior, verifier validity, duplication, instability, and task-level reference success. It is not yet the final benchmark.

## Final primary suite — target approximately 100 tasks

After validation, select approximately 100 tasks stratified by interaction failure mode and checked for reproducibility, verifier quality, 35–70% task-level reference success, safety, and redundancy. Every exclusion and exception must have a recorded reason.

## Smoke suite — 20 tasks nested in the candidate/primary set

ADR-0007 establishes that every smoke case is also a primary-suite case. The smoke set is a stable, fast implementation gate covering every source adapter and principal interaction mechanism.

A smoke result may be reused in a larger run only when execution and evaluation settings are identical. Smoke performance is not an independent estimate of general capability.

## Regression suite

A separate growing set of important invariants and previously failing tasks that have been fixed. The current 20-task regression manifest is only a provisional seed equal to smoke. Permanent capability regressions are promoted with trace evidence after repeated verification. Exact promotion policy remains proposed in ADR-0009.

## Hidden holdout

A protected transfer check unavailable to the optimizing agent. Holdout traces and private verifier logic must not be used to invent changes. The holdout is disjoint from visible optimization tasks.

## Separate live-site transfer suite

Permitted-account live tasks are scored separately because account state, regional interfaces, bot defenses, and website drift create a different validity regime. No live task runs before ADR-0006 is accepted.

## Validation requirement

Before any task set is frozen, run it through known working harnesses and inspect setup, reset, completion state, verifier output, artifacts, and instability. Broken or ambiguous tasks must be repaired, replaced, or quarantined. Using an existing framework to validate a benchmark does not select that framework as the final browser substrate.
