# ADR-0009: Regression-suite seeding and promotion

- Status: Proposed
- Date opened: 2026-07-11
- Date proposed: 2026-07-11
- Date accepted: —
- Approval state: Not accepted
- Supersedes: —
- Superseded by: —

## Question

How should the first regression suite be seeded, and when should newly fixed browser tasks be promoted into it?

## Proposed direction

Treat regression as an evaluation role rather than a separate benchmark source.

1. Execute and validate the 140-task provisional pool, then filter the final approximately 100-task primary suite.
2. Seed the regression suite only with tasks that have deterministic or independently validated verifiers, stable resets, and repeated successful reference runs.
3. Include a small set of integration invariants from the nested smoke suite, but do not automatically place all smoke or primary tasks into regression.
4. Promote a previously failing primary task after a treatment fixes it, implementation audit confirms that the treatment was active, repeated reruns support the flip, and the broader primary gate does not regress materially.
5. Preserve the motivating failure trace, root-cause classification, accepted change, verifier revision, and promotion evidence with each regression entry.
6. Quarantine rather than silently remove regression tasks that become invalid because of environment or verifier drift.

## Why this is proposed

This follows the useful structure from `auto-harness`: fixed failures become permanent protection, while the broader test set prevents narrow optimization. It also follows `agentic-harness-engineering` by retaining trace evidence, predicted impact, and change attribution rather than storing only a pass/fail ID.

A fixed regression list selected before a baseline exists would be arbitrary. The initial seed therefore depends on repeated reference runs and task validation.

## Open parameters

The following remain undecided and require empirical calibration:

- the number of repeated passes required for initial seeding;
- the number of successful treatment reruns required for promotion;
- whether the regression gate is all-pass or threshold based;
- how to handle dynamic tasks whose success probability is below one;
- when an invalid task is repaired, replaced, or retired; and
- whether regression tasks remain in the visible primary score after promotion.

## Decision gate

Accept or amend this ADR only after the first candidate baseline has been run repeatedly on the audited smoke and primary tasks, allowing stability and promotion thresholds to be chosen from observed variance rather than intuition.
