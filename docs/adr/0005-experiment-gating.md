# ADR-0005: Experiment validity and acceptance gate

- Status: Proposed
- Date opened: 2026-07-11
- Date proposed: 2026-07-13
- Date accepted: —
- Approval state: Not accepted
- Supersedes: —
- Superseded by: —

## Question

What sequence of implementation checks, evaluations, regression tests, repeats, and holdout tests is strong enough to accept or reject a harness change without confusing noise, broken implementation, or evaluator error with research evidence?

## Source ideas adapted

`neosigmaai/auto-harness` supplies a useful benchmark → analyze → improve → gate → record → learn structure with regression promotion. `china-qijizhifeng/agentic-harness-engineering` supplies trace-driven diagnosis, constrained component changes, implementation activation concerns, predicted task flips, and change attribution.

Browser tasks introduce extra issues including dynamic state, failed clicks, session loss, screenshots, action-mechanism fallbacks, and evaluator visibility boundaries. The gate below adapts the reference ideas to those conditions; it belongs to the loop architecture proposed in [ADR-0015](0015-auto-research-loop-architecture.md) and consumes scores and flags as defined in [ADR-0016](0016-judge-panel-and-verifier-audit-protocol.md).

## Proposed direction: the E0–E5 gate ladder

A change advances through the ladder in order; failing a rung stops the evaluation early and cheaply. Every rung's decision is computed by deterministic Conductor code from recorded artifacts — no LLM participates in an accept/reject decision.

- **E0 — static containment.** The diff touches only the optimizer's allowlisted harness workspace (git file guard); the generality lint finds no benchmark tokens, task-ID literals, or site-specific answer shortcuts in code, memory, or skill content; the change manifest validates against [`schemas/experiment.schema.json`](../../schemas/experiment.schema.json) with exactly one hypothesis and one target component.
- **E1 — activation audit.** Trace evidence from a cheap run must show the changed component actually executed (registration present, code path hit, declared activation events emitted). An inert change makes the experiment `invalid`, not `rejected`: it falsifies nothing.
- **E2 — smoke.** The 20-task nested smoke suite ([ADR-0007](0007-nested-smoke-suite.md)) must not collapse. `invalid`/`error` results are excluded from denominators per the fail-closed result semantics.
- **E3 — targeted cluster re-evaluation.** The tasks of the motivating failure cluster are re-run at the repetition count their stability history requires. The manifest's predicted fixes are checked here first.
- **E4 — regression suite, near-zero tolerance.** Any regression-suite failure confirmed by repetition blocks acceptance. A regression flagged as verifier-suspect by the panel goes to quarantine rather than silently passing or failing ([ADR-0016](0016-judge-panel-and-verifier-audit-protocol.md)). The optimizer's self-declared at-risk list is never used to narrow this rung.
- **E5 — paired development evaluation.** Baseline and treatment are compared on the **valid-in-both intersection** of the development suite (quorum semantics: a comparison is valid only when coverage of the suite stays above a floor and no source family is entirely absent — exact numbers are open parameters). Acceptance requires **all three**:
  1. at least one predicted flip verified (the hypothesis did what it claimed);
  2. no unexplained regression outside the measured noise band;
  3. aggregate success non-inferior within the noise band.

Results are classified `accepted`, `rejected`, `inconclusive`, or `invalid` per the charter. Infrastructure failure invalidates; it never falsifies the hypothesis.

### Deliberate divergence from auto-harness

The reference gate ratchets on `val_score ≥ best`. On stochastic browser tasks that design lets one lucky run raise the bar permanently and then lock all progress. E5 instead compares paired runs against a **measured noise band** estimated from repeated baseline runs, and accepts on verified predictions plus non-inferiority rather than a new high-water mark.

### Holdout

The hidden holdout is evaluated at **scheduled checkpoints only**, never per-change, so it cannot leak into iteration pressure. Holdout tasks and traces stay outside this public repository (see ADR-0015, requirement 4).

## Requirements recorded for implementation (deferred, not scheduled)

1. Quorum validity semantics for E5: valid-in-both intersection, a coverage floor (provisionally ≥90%, to be set from measurement), and no absent source family.
2. Per-task resume so partial sweeps do not force whole-run invalidity (loop phase A).
3. Noise-band estimation from repeated baseline runs on the calibrated suite.
4. Per-source concurrency limits so environment contention does not masquerade as instability.

## Open parameters — thresholds are TBD from measurement

The following numbers are deliberately not chosen here and must come from observed variance on the bring-up set before the loop activates: repetition counts per stability class; the noise-band width and its estimator; the E5 coverage floor; the E2 smoke collapse threshold; the E4 confirmation repeat count; the non-inferiority margin; holdout checkpoint cadence.

## Decision gate

Approve the ladder's structure now only as a proposal; accept it only after it correctly classifies known synthetic and real failure cases on the bring-up infrastructure:

- a deliberately disabled change must be caught at E1 as `invalid`;
- a broken tool or reset failure must classify as `invalid`, not `rejected`;
- an injected targeted regression must be caught at E4;
- a seeded verifier false positive must be caught by the probe kit or cross-examiner ([ADR-0016](0016-judge-panel-and-verifier-audit-protocol.md));
- a benchmark-token shortcut must be caught at E0.

Explicit project-owner approval is required.
