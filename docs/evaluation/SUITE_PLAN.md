# Evaluation Suite Plan

This document records suite roles and target sizes, not selected tasks.

## Provisional bring-up set — approximately 20 tasks

Used while building and validating the runner, reset logic, traces, action dispatch, and verifiers. Tasks may be replaced when defects are found. Results from this set are engineering evidence, not the main project score.

## Smoke suite — approximately 10–20 tasks

A stable, fast subset used to catch implementation and integration mistakes before expensive evaluation. It should cover core mechanisms but is not expected to estimate overall capability accurately.

## Primary suite — approximately 100 tasks

The principal visible evaluation used for meaningful baseline and treatment comparisons after the infrastructure is validated. Selection must be stratified by interaction failure mode and checked for reproducibility and verifier quality.

## Regression suite

A separate, growing set of important invariants and previously failing tasks that have been fixed. It protects learned capability and is not defined by a fixed size.

## Hidden holdout

A protected transfer check unavailable to the optimizing agent. Holdout traces and private verifier logic must not be used to invent changes.

## Validation requirement

Before a task set is frozen, run it through a known working harness and inspect setup, reset, completion state, verifier output, artifacts, and instability. Broken or ambiguous tasks must be repaired, replaced, or explicitly quarantined.
