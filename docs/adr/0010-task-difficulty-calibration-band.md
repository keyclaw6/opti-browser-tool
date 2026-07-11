# ADR-0010: Task difficulty calibration band

- Status: Accepted
- Date opened: 2026-07-11
- Date accepted: 2026-07-11
- Decision owner: project owner
- Supersedes: no earlier ADR

## Context

The evaluation suite must leave enough headroom for harness improvements while still producing enough successful runs to detect regressions and diagnose why a treatment helped. Tasks that nearly every strong system passes are saturated. Tasks that nearly every strong system fails give weak experimental resolution because most harness changes still produce a zero.

The project owner first discussed a broader range and then explicitly corrected the desired target on 2026-07-11.

## Decision

Prioritize tasks whose **task-level success rate under a current strong reproducible reference system is between 35% and 70% inclusive**.

This is a final-suite admission preference, not permission to assign a benchmark's aggregate score to every task in that benchmark.

The evidence hierarchy is:

1. repeated task-level results from the exact model, harness, benchmark revision, and protocol we intend to use;
2. public per-task results under a sufficiently comparable strong system;
3. task-level estimates aggregated from several comparable public systems or trajectories; and
4. benchmark-level aggregate scores, which may be used only to source candidates before task-level calibration.

A candidate selected using level 4 evidence must be marked `calibration_required` and cannot be described as having a known 35–70% task success rate.

## Why

A 35–70% band should give the research loop both kinds of evidence it needs:

- enough failures to reveal weaknesses and leave improvement headroom; and
- enough successes to compare successful and failed traces, detect regressions, and estimate whether a treatment changes reliability.

The band is deliberately asymmetric around 50%. The upper bound allows useful, stable tasks into smoke and regression roles without accepting near-saturated tasks. The lower bound avoids filling the suite with tasks so difficult that ordinary improvements remain statistically invisible.

## Consequences

- The exact 100-task primary suite cannot be frozen from benchmark metadata alone.
- Public benchmark scores may screen benchmark families, but every selected task still needs a local calibration run.
- Task-level rates must be tied to a versioned reference protocol and accompanied by the number of trials and uncertainty.
- Tasks above 70% or below 35% may remain in a replacement pool or be retained for a specifically documented role, but they require an explicit exception and must not dominate the primary score.
- The 20-task smoke subset remains nested in the primary suite under ADR-0007. Its tasks may be selected from the more stable part of the accepted band after calibration.

## Still open

This ADR does not decide:

- which model and harness constitute the calibration reference system;
- how many repeated trials are required for stable and dynamic tasks;
- the confidence-interval rule around the 35% and 70% boundaries;
- whether separate calibration systems are needed for visual-first and structured-action lanes; or
- how many deliberate out-of-band exception tasks may be retained.
