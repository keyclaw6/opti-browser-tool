# ADR-0001: Project constitution

- Status: Accepted
- Date proposed: 2026-07-11
- Date accepted: 2026-07-11
- Source: initiating project brief

## Context

The project needs a stable objective and research method before implementation choices begin. Browser-agent reliability is easy to obscure with aggregate scores, evaluator mistakes, benchmark overfitting, or changes to the underlying model.

## Decision

1. Optimize reliable browser and computer interaction, not primarily search or question answering.
2. Treat task success as the primary metric. Efficiency metrics are diagnostic and secondary unless reliability is comparable.
3. Normally hold the executor model fixed within a harness experiment.
4. Maintain separate visual-first and terminal/CLI research lanes, with a later hybrid lane or router.
5. Share task, trace, metric, verifier, and evaluation contracts across lanes.
6. Use a trace-driven, falsifiable outer loop: baseline, diagnose, hypothesize, predict, implement, audit, smoke test, evaluate, gate, record, and repeat.
7. Maintain smoke, main, regression, and hidden-holdout sets; repeat unstable tasks.
8. Prefer deterministic browser-state verification and use specialized judges for interpretation and diagnosis.
9. Keep executor-visible observations separate from judge-only debugging instrumentation.
10. Use only permitted accounts for real-platform testing and respect platform rules and access controls.
11. Make the auto-research infrastructure—not the final hybrid agent—the first milestone.

## Consequences

A faster or cheaper treatment cannot be accepted merely by reducing cost if it lowers reliability. A model change and a harness change cannot be attributed in the same experiment. Hybrid features cannot erase the independent lane baselines. Holdout evidence and private verifier details are unavailable to the optimizing executor.

## Validation and revisit trigger

Revisit only if the project's central objective changes. Individual implementation choices do not supersede this constitution.
