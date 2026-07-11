# Batch 1 calibration plan

## Purpose

Determine which of the 140 candidates satisfy the accepted **35–70% task-level success band** under a pinned strong reference system, while separating genuine agent failures from environment, reset, account, and evaluator failures.

## Required stages

1. **Source installation audit** — pin package/repository, website data, credentials, environment revision, browser version, and verifier revision.
2. **Task materialization** — resolve every upstream ID and seed to a complete immutable task record.
3. **Known-good completion** — run an oracle, human trace, or audited successful trajectory and verify that completion scores correctly.
4. **Adversarial verifier audit** — test non-completion, near misses, partial completion, premature stop, harmful extra actions, stale traces, and malformed outputs.
5. **Reset and repeatability audit** — repeat initial-state restoration and check for cross-task contamination.
6. **Reference calibration** — run a pinned strong harness repeatedly and estimate task-level success with uncertainty.
7. **Boundary expansion** — add trials for tasks near 35% or 70%, tasks with inconsistent resets, and dynamic tasks.
8. **Admission review** — retain, reject, quarantine, or approve an explicit exception, recording the reason.

## Evidence to store per trial

- task and environment revisions;
- model and complete harness configuration;
- seed, initial state, browser, viewport, locale, and region;
- observation/action protocol and budgets;
- trace and synchronized browser artifacts;
- native verifier result and any independent audit result;
- infrastructure validity classification; and
- tokens, time, tool calls, actions, retries, and cost.

## Still open

- reference model and harness;
- trial count and interval estimator;
- rule when an interval overlaps 35% or 70%;
- separate references for visual and structured lanes;
- treatment of unstable but strategically important tasks; and
- maximum number of justified out-of-band diagnostic exceptions.
