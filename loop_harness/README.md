# opti-loop — the Auto Research harness shell

**Status: provisional infrastructure.** This package implements the loop
architecture proposed in [ADR-0015](../docs/adr/0015-auto-research-loop-architecture.md),
the gate ladder proposed in [ADR-0005](../docs/adr/0005-experiment-gating.md),
and the evaluation-layer boundaries proposed in
[ADR-0016](../docs/adr/0016-judge-panel-and-verifier-audit-protocol.md).
Those ADRs are **Proposed, not Accepted** — per
[`docs/DECISION_PROCESS.md`](../docs/DECISION_PROCESS.md), the existence of this
code does not settle them. Like the eval-harness bridge code before it
(ADR-0013 pattern), this shell exists so the design can be exercised and
falsified, not to pre-empt the decision.

## What it is

A **deterministic conductor** for the loop
`EVALUATE → ATTRIBUTE → DISTILL → EVOLVE → GATE → RECORD`. The optimizer
(an external coding agent reading [`PROGRAM.md`](../PROGRAM.md)) is the only
intelligent actor inside an iteration; every accept/reject decision here is
plain code over recorded artifacts. **No LLM participates in any gate
decision.**

## Hybrid provenance (the project-owner brief: auto-harness's simple loop + AHE's observability-driven evolution)

| Piece | Taken from | Adaptation here |
|---|---|---|
| Loop skeleton driven by a runbook (`PROGRAM.md`), workspace files, learnings log | neosigmaai/auto-harness | campaign directories under `campaigns/` (gitignored, like their `workspace/`) |
| Git file guard (tracked diff + untracked scan minus allowlist) | auto-harness `gating.py` | allowlist is the component tree `harness/components/`; no config switch to disable |
| Regression suite memory + promotion of newly-fixed tasks | auto-harness | promotion produces **candidates** only; auto-promotion stays off pending ADR-0009 |
| Sequential cheap-to-expensive gate, exit-code contract | auto-harness | expanded to the E0–E5 ladder of ADR-0005 |
| Change manifest (evidence → root cause → fix → predicted fixes/risks → why this component) | agentic-harness-engineering | carried by the repo's own `schemas/experiment.schema.json` + `target_component`, `cluster_ref`; conductor appends `attribution` |
| KEEP / IMPROVE(partial) / ROLLBACK+PIVOT attribution | AHE | computed synchronously — the gate runs the treatment eval in-iteration, so predictions are falsified in the same iteration record |
| Iteration folders with pre-built analysis read first | AHE (`runs/iteration_NNN/`) | `campaigns/<id>/iterations/iter-NNNN/` with `analysis/`, `PACKET.md`, `eval/*` |
| Registration validation before evaluation | AHE `validate_agent.py` | `component.json` checks = the static half of E1; the dynamic (trace) half is **pending** until a tracer exists and is reported as such, never silently passed |
| Failure clusters prioritized by `total_failures × (1 − resolution_rate)` | neosigma method article | cluster register per `docs/architecture/ANALYST.md`; the stub Analyst labels itself `stub-0` and claims no root causes |
| **Replaced:** monotonic `val_score ≥ best` ratchet | auto-harness | paired baseline/treatment comparison inside a measured noise band (ADR-0015 §8) |
| **Replaced:** at-risk lists as regression protection | AHE manifests | risk lists are measured for prediction accuracy but never protect the gate |
| **Added:** generality lint | — (ADR-0015 §5.2) | diffs/memory scanned for task IDs, source tokens, benchmark hosts derived from the live catalog |
| **Added:** exploration policy | — (ADR-0015 §9) | divergence quota + plateau trigger stamp iterations divergent; parallel campaigns are separate campaign dirs over the shared read-only eval plane |
| **Added:** fail-closed validity | opti-eval semantics | `invalid`/`error`/`skipped` never count as agent failures; fixture/simulated runs can never yield a real acceptance (`simulated:` watermark) |

## Honest limitations (v0)

1. **The Analyst is a stub.** `stub-0` groups failures by source family from
   result records; it reads no traces and finds no root causes. The real
   pipeline is specified in `docs/architecture/ANALYST.md` and needs traces
   (ADR-0004) and bridges to exist.
2. **E1 is half-implemented.** Registration consistency is enforced; trace
   evidence of activation is reported `pending` until a tracer exists.
3. **No judges.** T1/T2 of ADR-0016 need browser artifacts. The gate today is
   T0-analogous only, over synthetic adapters.
4. **Acceptance requires task-level predictions.** Failure-class-only
   predictions can't be flip-verified until the Analyst can map flips to
   classes — the gate stays strict rather than guessing.
5. **Thresholds are placeholders** marked in campaign config; real values are
   TBD-from-measurement (ADR-0005) once bridges and calibration exist.
6. **k-repeats default to 1** — per-task repetition policy activates with real
   (stochastic) adapters; the fixture is deterministic.

## Use

```bash
make loop-test          # unit + end-to-end dry run (scripted optimizer, fixture)
make loop-init-dryrun   # create a demo campaign, measure noise, start iteration 1
```

Operator commands (see `opti-loop --help`): `init`, `snapshot-guard`,
`measure-noise`, `start`, `gate`, `record`, `rollback`, `status`.
The optimizer's contract lives in [`PROGRAM.md`](../PROGRAM.md).
