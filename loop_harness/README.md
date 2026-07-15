# opti-loop — the Auto Research harness shell

**Status: reference implementation of accepted architecture; loop NOT yet
authorized to run.** This package implements the loop architecture of
[ADR-0015](../docs/adr/0015-auto-research-loop-architecture.md), the gate
ladder of [ADR-0005](../docs/adr/0005-experiment-gating.md), and the
evaluation-layer boundaries of
[ADR-0016](../docs/adr/0016-judge-panel-and-verifier-audit-protocol.md) — all
**Accepted 2026-07-13**. Activation is separately gated: bridges must emit
conforming traces (ADR-0004), verifiers must pass probe-kit admission, the
suite and noise band must be calibrated, and the ADR-0005 synthetic
failure-injection catalog must pass on real infrastructure before the first
campaign runs.

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
| Loop skeleton driven by a runbook (`PROGRAM.md`), workspace files, learnings log | neosigmaai/auto-harness | campaign state in an owner-only trusted store OUTSIDE the repo (v2); optimizer works in an isolated worktree |
| Git file guard | auto-harness `gating.py` | v2: authoritative over the `base..candidate` **commit diff** (not the mutable working tree), allowlist `harness/components/`, path-safety, no disable switch |
| Regression suite memory + promotion of newly-fixed tasks | auto-harness | promotion produces **candidates** only; auto-promotion stays off pending ADR-0009 |
| Sequential cheap-to-expensive gate, exit-code contract | auto-harness | expanded to the E0–E5 ladder of ADR-0005 |
| Change manifest (evidence → root cause → fix → predicted fixes/risks → why this component) | agentic-harness-engineering | one canonical `schemas/experiment.schema.json` requires `target_component` and `cluster_ref`; conductor alone appends `attribution` or writes the discriminated `rejected_submission` record for invalid input |
| KEEP / PARTIAL / REVERT attribution | AHE | computed synchronously; a `revert` attribution can never be accepted, and the flip must be verified in FULL E5 evidence (not E3 screening) |
| Iteration folders with pre-built analysis read first | AHE (`runs/iteration_NNN/`) | `<store>/<id>/iterations/iter-NNNN/` with `analysis/`, `PACKET.md`, `eval/*` — in the trusted store |
| Registration validation before evaluation | AHE `validate_agent.py` | `component.json` checks = the static half of E1; the dynamic (trace) half is **pending** until a tracer exists and is reported as such, never silently passed |
| Failure clusters prioritized by `total_failures × (1 − resolution_rate)` | neosigma method article | cluster register per `docs/architecture/ANALYST.md`; the stub Analyst labels itself `stub-0` and claims no root causes |
| **Replaced:** monotonic `val_score ≥ best` ratchet | auto-harness | paired baseline/treatment comparison inside a measured noise band (ADR-0015 §8) |
| **Replaced:** at-risk lists as regression protection | AHE manifests | risk lists are measured for prediction accuracy but never protect the gate |
| **Added:** generality lint | — (ADR-0015 §5.2) | diffs/memory scanned for task IDs, source tokens, benchmark hosts derived from the live catalog |
| **Added:** exploration policy | — (ADR-0015 §9) | divergence quota + plateau trigger stamp iterations divergent; parallel campaigns are separate campaign dirs over the shared read-only eval plane |
| **Added:** fail-closed validity | opti-eval semantics | `invalid`/`error`/`skipped` never count as agent failures |

## Trusted experiment boundary (v2, post-review)

The v1 review found the machine could be fooled: the guard trusted the mutable
working tree, campaign state was gitignored inside the repo, gate/record were
separable, and `simulated:accepted` mutated real state. v2 closes these:

- **Owner-only store outside the repo** (`store.py`) — config, state, ledger,
  gate reports, noise band, quarantine, corpus live where a repo-confined
  optimizer cannot address them (refuses any store under `repo_root`).
- **Base SHA + candidate worktree + commit-diff guard** (`gitutil.py`,
  `fileguard.check_candidate`) — the optimizer commits in an isolated worktree;
  the guard reads `base..candidate` commit objects, so committing an edit no
  longer hides it, and path-safety rejects traversal/symlink/absolute paths.
- **One atomic transaction** (`conductor.run_iteration`) — gate + attribute +
  record + accept/reset in a single step; no forgeable gate report to plant.
- **Typed verdict** (`verdict.py`) — only `(accepted, benchmark)` advances
  state; every `simulated` verdict is inert for promotion, drift, and ranking.
- **Benchmark eligibility** (`eligibility.py`) — every terminal task in an
  otherwise reportable run must have an admitted, checksum-matched verifier, a
  strict runner/task/result-linked trace and hashed task-local artifact bundle,
  an exact runner-owned ordered task manifest, pinned source/verifier identity,
  consecutive trace sequence, ordered wall/monotonic time and every supplied
  browser epoch,
  canonical final browser state, and a successful T1 run. Missing/malformed/
  spliced/reordered evidence, unavailable T1, unsafe artifacts, malformed task
  expectations, or an unclosed T1 flag is an explicit E5 integrity-invalid
  outcome. Missing quarantine storage is empty; any present but unavailable or
  malformed quarantine storage is integrity-invalid. A defect/undecidable
  quarantine resolution remains blocking for the
  exact old run; favorable confirmation alone clears it. Fixture/command
  rehearsals remain simulated.

## Honest limitations (current)

1. **The Analyst is a stub** (`stub-0`, no root causes) — needs traces (ADR-0004).
2. **E1 dynamic half is pending** — registration is enforced; trace-activation
   is reported `pending` until a tracer exists. T2 judges are owner-invoked;
   only T1 auto-runs in eligibility today.
3. **k-repeat paired confirmation is specified but runs once** under the
   deterministic fixture; wire k>1 when a stochastic adapter exists.
4. **Thresholds are placeholders** (`min_prediction_precision`, smoke floor,
   noise band) — TBD-from-measurement once real bridges calibrate.
5. **Deployment isolation is a requirement, not code**: in production the
   optimizer must be mounted with only `<worktree>/harness/components`
   writable. The store-outside-repo + commit-diff design enforces the boundary
   *given* that confinement; a shared filesystem with an unconfined optimizer
   is out of the threat model this code can close alone.

## Use

```bash
make install     # install eval + judge + loop from their explicit package graph
make loop-test   # unit + transactional end-to-end tests (real command bridge)
make install-check  # uv-offline/no-index install + deterministic installed tests
```

`opti-loop==0.1.0` declares exact dependencies on
`opti-browser-eval==0.1.0` and `opti-judge==0.1.0`. Global options precede the
subcommand, for example
`opti-loop --store-root /safe/path init --campaign rehearsal`.
`install-check` invokes no live backend, but it is not an OS-level network
sandbox.

Operator commands (see `opti-loop --help`): `init`, `measure-noise`, `start`,
`run-iteration`, `status`, `compare-campaigns`, `transfer-plan`.
The optimizer's contract lives in [`PROGRAM.md`](../PROGRAM.md).
