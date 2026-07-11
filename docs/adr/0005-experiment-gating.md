# ADR-0005: Experiment validity and acceptance gate

- Status: Open
- Date opened: 2026-07-11
- Approval state: Not accepted

## Question

What sequence of implementation checks, evaluations, regression tests, repeats, and holdout tests is strong enough to accept or reject a harness change without confusing noise, broken implementation, or evaluator error with research evidence?

## Source ideas to adapt

`neosigmaai/auto-harness` supplies a useful benchmark → analyze → improve → gate → record → learn structure with regression promotion. `china-qijizhifeng/agentic-harness-engineering` supplies trace-driven diagnosis, constrained component changes, implementation activation concerns, predicted task flips, and change attribution.

The browser project will reuse these ideas, but their exact gate is not yet selected. Browser tasks introduce extra issues including dynamic state, failed clicks, session loss, screenshots, action-mechanism fallbacks, and evaluator visibility boundaries.

## Candidate stages to investigate

Potential stages include manifest validation, implementation activation audit, smoke tests, regression checks, paired primary evaluation, hidden holdout, infrastructure classification, and a result category such as accepted, rejected, inconclusive, or invalid. These remain candidates pending calibration.

## Research required

- Map the two reference projects' gates and records into browser-specific requirements.
- Measure variance and infrastructure failure on the validated bring-up set before setting thresholds or repeats.
- Inject disabled changes, broken tools, targeted regressions, evaluator false positives, and infrastructure failures to test classification.
- Decide how the 10–20-task smoke suite, approximately 100-task primary suite, regression suite, and holdout interact.

## Decision gate

Approve the gate only after it correctly handles known synthetic and real failure cases on the bring-up infrastructure. Explicit project approval is required.
