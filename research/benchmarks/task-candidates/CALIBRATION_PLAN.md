# Batch 1 task-level calibration plan

This plan describes the next gate. It is not yet an accepted experimental protocol.

## Objective

Determine which Batch 1 candidates actually fall in the 35–70% task-level success band under a pinned strong reference system, while separating genuine agent failures from environment and evaluator failures.

## Minimum record per run

Record the candidate ID, benchmark and environment revision, reset result, browser and viewport, locale and time zone, account state identifier, model snapshot, harness commit, observation mode, action mode, prompt version, maximum steps, wall-clock timeout, final verifier result, failure class, and trace artifact IDs.

## Suggested staged procedure

1. **Oracle and reset check** — run the official cheat/oracle path or a manually verified trajectory twice from clean state.
2. **Verifier challenge set** — construct success, near-miss, partial-completion, false-claim, harmful-extra-action, and infrastructure-failure cases.
3. **One-pass reference screen** — run every candidate once with the chosen strong system to eliminate obvious breakage and saturation.
4. **Initial calibration** — run surviving tasks three times under identical protocol.
5. **Boundary expansion** — add trials for tasks near 35% or 70%, tasks with inconsistent resets, and dynamic tasks.
6. **Admission review** — accept, reject, or hold each task with trace evidence and an estimated success interval.

## Required classifications

Every unsuccessful run must distinguish at least:

- executor perception or grounding failure;
- planning failure;
- action-selection or input failure;
- recovery failure;
- premature completion;
- evaluator false negative;
- evaluator false positive;
- environment/reset failure;
- implementation/configuration failure; and
- safety or policy stop.

## Open protocol decisions

Before running the calibration at scale, decide:

- the strong reference model and harness;
- whether visual and structured lanes use one shared reference or separate references;
- the minimum trial count and confidence-interval rule;
- how to handle tasks whose interval overlaps a boundary;
- how much environment-instability evidence causes rejection; and
- whether any deliberate out-of-band tasks are allowed.
