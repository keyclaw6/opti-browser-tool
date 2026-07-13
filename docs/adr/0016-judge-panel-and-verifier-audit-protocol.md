# ADR-0016: Judge panel and verifier audit protocol

- Status: Accepted
- Date opened: 2026-07-13
- Date proposed: 2026-07-13
- Date accepted: 2026-07-13
- Approval state: Accepted — explicit project-owner approval (2026-07-13). Calibration-before-trust remains operative: no judge flag is consumed until its measured operating point is met.
- Supersedes: —
- Superseded by: —
- Answers: Open Question 14 (Workstream C)
- Supporting specification: [`../architecture/ANALYST.md`](../architecture/ANALYST.md)

## Question

Which completion verifiers and LLM judges are needed, what evidence may each see, and how will false-positive and false-negative rates be calibrated so that evaluation errors do not corrupt gate decisions?

## Engineering target

The goal "no false positives or false negatives" is made precise as: **no single error type can corrupt a gate decision** — zero *unmodeled* error, not zero error. Published measurements show absolute zero is not attainable: deterministic verifiers over-reject (rule-based official verifiers: 83.8% precision, 55.9% recall on expert-labeled trajectories) and LLM judges over-accept (no judge above 70% precision; best ≈69.8%). The two measured failure directions are therefore wired against each other, and every unresolved disagreement is quarantined for human review instead of being averaged away.

## Proposed direction

### Layer structure

| Layer | Role | Specification |
|---|---|---|
| **T0 — native verifiers** (per source family) | the **only** scorers | Fail-closed admission per verifier: it enters service only after passing the probe kit (below). Verifier version and checksum pinned per run. Malformed or missing evidence yields `invalid`, never `failed`. |
| **T1 — deterministic cross-checks** | cheap flags | Browser-side expected-state assertions derived from task records; an HTTP-method side-effect monitor (a mutation where none is expected, or none where one is expected, raises suspicion); action-count and loop anomalies. Disagreement with T0 sends the run to the quarantine queue. |
| **T2 — LLM judge panel** | non-scoring, calibrated flaggers | Five roles, each with an explicit evidence contract and per-benchmark measured precision/recall **before its flags are trusted**: (1) completion cross-examiner — a WebJudge-style key-point → key-screenshot → judgment recipe applied over verifier passes hunting false positives **and** verifier fails hunting false negatives, with deliberately simple inputs (final accessibility tree or screenshot; captioning pipelines measurably underperform); (2) side-effect and safety judge; (3) root-cause analyst (the Analyst of [ADR-0015](0015-auto-research-loop-architecture.md)); (4) implementation-activation auditor; (5) adjudicator, whose tie rule is fixed: unresolved disagreement always quarantines and never adjusts a score. |
| **T3 — human checkpoint** | authority | The project owner consumes the quarantine queue and verifier-repair proposals, and approves suite-composition and judge-threshold changes. |

Judge outputs adopt the three expert-annotation axes shown to matter: task success, side effects, and repetitiveness.

### The probe kit (T0 admission)

A verifier is admitted per task only when:

1. a known-good oracle trajectory scores 1;
2. a near-miss trajectory scores 0;
3. a premature-stop trajectory scores 0;
4. a harmful-extra-action trajectory is detected (side-effect axis);
5. a stale or fabricated trace is rejected;
6. malformed input produces `invalid`, never `failed`.

Probe artifacts are archived at creation and become the seed of the calibration corpus.

### Error-direction closure

- **False-positive defense** (scores that should not have passed): probe kit at admission → T1 mutation cross-check → cross-examiner audits concentrated on *flipped* tasks, where FP pressure is highest inside the loop → quarantine.
- **False-negative recovery** (real successes scored as failures): the cross-examiner reviews verifier fails → FN-suspect queue → the fix is **always a verifier or task repair, never a score override** → the repaired verifier re-runs the full probe kit before re-admission.
- **Regression blindness**: covered structurally by gate E4 ([ADR-0005](0005-experiment-gating.md)), a whole-suite flip scan, and the side-effect judge — never by the optimizer's self-declared at-risk lists.

### Calibration protocol

1. **The labeled corpus is a by-product of bridge bring-up**: every oracle run, near-miss probe, and quarantine resolution is archived at creation, so calibration material accumulates without a separate labeling project.
2. **Per-benchmark operating points**: the cross-examiner is tuned high-recall (it is a flagger; its false alarms cost review time, not scores); the activation auditor is tuned high-precision (its flags invalidate experiments).
3. **Scheduled drift re-scoring**: judges are re-measured against the growing corpus at fixed intervals and after any prompt or model change.
4. **Pinning**: judge prompts and model snapshots are versioned exactly like verifiers; a judge change is a recorded evaluation-plane change, never silent.
5. **Visibility**: judges may see judge-only evidence (trace `visibility` tags per [`schemas/trace-event.schema.json`](../../schemas/trace-event.schema.json)); executor- and optimizer-visible context never includes judge-only material.

### Judge model economics

Judge roles are exempt from the loop's cheap-executor economy and run on strong pinned models; a cheap executor with a blind gate would corrupt every downstream decision. Exact judge model pinning falls under Open Question 17.

## Why this is proposed

Evidence (sources in [`../REFERENCES.md`](../REFERENCES.md)):

- **AgentRewardBench** (1,302 expert-labeled trajectories across WebArena, VisualWebArena, WorkArena and others): no LLM judge exceeded 70% precision; rule-based official verifiers reached 83.8% precision at 55.9% recall — exact-match rules reject valid successes. This grounds both the "verifiers score, judges flag" split and the FN-repair channel.
- **Simple judge inputs win**: final-state accessibility tree or screenshot inputs beat captioning pipelines in the same study — adopted for the cross-examiner contract.
- **WebJudge** (Online-Mind2Web): key-point extraction → key-screenshot selection → judgment achieves ≈85–87% agreement with humans (≈3.8 pp gap to inter-human agreement), and the distilled WebJudge-7B holds ≈87% including out-of-distribution tasks — the recipe is robust enough to serve as a calibrated flagger, and a small distilled judge is a candidate second opinion.
- **Mind2Web-2** demonstrates Agent-as-a-Judge with per-task tree rubrics — the right shape for REAL-family retrieval tasks and a later live-site suite.
- The constitution ([ADR-0001](0001-project-constitution.md)) already requires deterministic verification preferred, judges for interpretation, and executor/judge evidence separation; this ADR is its concrete protocol.

## Interaction with open decisions

- **ADR-0004** (trace storage): this protocol requires visibility tags and artifact-addressable evidence; it does not select the store.
- **ADR-0005** (gate): T0 scores and T1/T2 flags feed gates E1–E5; quarantine interacts with run validity as defined there.
- **ADR-0008/0014** (sources/filtering): probe-kit results per task are part of the 140-candidate audit evidence that drives final filtering.
- **Open Question 17**: judge model identifiers, snapshots, and settings remain to be pinned.

## Requirements recorded for implementation (deferred, not scheduled)

1. Quarantine queue tooling and its review workflow (T3).
2. Per-benchmark judge calibration harness and drift re-scoring schedule.
3. Probe-kit trajectory authoring per source family during bridge bring-up.
4. Corpus storage with restricted visibility (quarantine resolutions include judge-only evidence).

## Open parameters

Per-benchmark judge operating thresholds; corpus size targets per source family; drift re-scoring cadence; quarantine review service objectives; whether a distilled open-weight judge (WebJudge-7B class) is added as a permanent second opinion.

## Decision gate

Accept this ADR only after review of the layer structure and closure argument. Before any judge flag is trusted in gate decisions (a separate, later step), the judge must have measured per-benchmark precision/recall on the calibration corpus, and every active verifier must have passed its probe kit. Explicit project-owner approval is required.
