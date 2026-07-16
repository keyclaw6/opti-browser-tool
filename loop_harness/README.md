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
| Git file guard | auto-harness `gating.py` | v2: authoritative over the `base..candidate` **commit diff** (not the mutable working tree), frozen campaign harness-build allowlist, path-safety, no disable switch |
| Regression suite memory + promotion of newly-fixed tasks | auto-harness | promotion produces **candidates** only; auto-promotion stays off pending ADR-0009 |
| Sequential cheap-to-expensive gate, exit-code contract | auto-harness | expanded to the E0–E5 ladder of ADR-0005 |
| Change manifest (evidence → root cause → fix → predicted fixes/risks → why this component) | agentic-harness-engineering | one canonical `schemas/experiment.schema.json` requires `target_component` and `cluster_ref`; conductor alone appends `attribution` or writes the discriminated `rejected_submission` record for invalid input |
| KEEP / PARTIAL / REVERT attribution | AHE | computed synchronously; a `revert` attribution can never be accepted, and the flip must be verified in FULL E5 evidence (not E3 screening) |
| Iteration folders with pre-built analysis read first | AHE (`runs/iteration_NNN/`) | `<store>/<id>/iterations/iter-NNNN/` with `analysis/`, `PACKET.md`, `eval/*` — in the trusted store |
| Registration validation before evaluation | AHE `validate_agent.py` | `component.json` checks remain supporting E1 metadata; `harness-fixture` and the one concrete WARC `online.4` seam have conductor-observed activation, and other adapters fail closed pending concrete trusted instrumentation |
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
  record + accept/reset in a single step under one campaign lock acquired
  before a fresh trusted-state reload. Concurrent consumers cannot reuse one
  pending iteration; accepted-ref publication compare-and-swaps from the
  freshly observed accepted identity before any advancing terminal record.
  `start` uses the same lock and a fresh state reload: it refuses a pending
  publication, validates and cleans a current terminal receipt, then opens the
  next iteration.
- **Typed verdict** (`verdict.py`) — only `(accepted, benchmark)` advances
  state; every `simulated` verdict is inert for promotion, drift, and ranking.
- **Benchmark admission** (`eligibility.py`) — raw evaluator summaries always
  remain non-reportable and decision-ineligible. Every terminal task in a
  benchmark run must have an admitted, checksum-matched verifier, a
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
  rehearsals remain simulated. A clean review issues an evidence-bound AR-003
  receipt; both comparison arms, every real noise sample, and accepted-state
  replay require exact receipts.

## Honest limitations (current)

1. **The Analyst is a stub** (`stub-0`, no root causes) — needs traces (ADR-0004).
2. **E1 observed activation is qualified only for `harness-fixture` and the
   concrete WARC `online.4` path** — the
   conductor binds one compact behavior-file observation (path, checksum,
   parsed value, and cited `run.json`) to the exact D2 build, frozen changed
   surface, run/protocol/adapter identity, and the trusted accepted-build
   baseline observation. Missing observation, baseline/wrong build, wrong
   path/surface, or unconsumed bytes stop at E1 invalid. A behavior-neutral
   candidate with proven exact build/surface consumption passes E1 and reaches
   the efficacy decision. The WARC path additionally requires its trusted
   repository lifecycle trace to show the exact treatment load and
   exact candidate-bearing applied model-request digest, with task-trace and `run.json`
   citations; its local fake remains simulated and state-inert. Other adapters fail E1 until their concrete trusted
   instrumentation exists. T2 judges are owner-invoked; only T1 auto-runs in
   eligibility today.
3. **k-repeat paired confirmation is specified but runs once** under the
   deterministic fixture; wire k>1 when a stochastic adapter exists.
4. **Thresholds are placeholders** (`min_prediction_precision`, smoke floor,
   noise band) — TBD-from-measurement once real bridges calibrate.
5. **Deployment isolation is a requirement, not code**: in production the
   optimizer must be mounted with only the frozen campaign candidate allowlist
   writable. The store-outside-repo + commit-diff design enforces the boundary
   *given* that confinement; a shared filesystem with an unconfined optimizer
   is out of the threat model this code can close alone.
6. **Benchmark bundle handback requires real two-user deployment**:
   `run-iteration --candidate-bundle PATH --candidate-manifest PATH` requires
   both files and their inbox to share a separate optimizer UID. Benchmark
   candidate identity and changed paths come from the imported D2 build, and
   the exact sidecar bytes are read once; the mutable worktree is not benchmark
   authority. Manifest structure is decided at E0 before ownership or D2
   import. The manifest and inbox are opened component-by-component without
   following symlinks; its bytes are read exactly once from the pinned
   descriptor. The bundle is opened relative to that same pinned inbox and its
   descriptor supplies the conductor-owned copy, so optimizer paths are never
   reopened after ownership validation. Manifest input is capped at 256 KiB;
   bundle staging copies exactly the bounded size initially reported by
   `fstat`, rejecting append/short/change races. An advancing verdict imports
   and verifies that copy's exact commit/tree before publication. One narrow
   accepted-publication intent then recovers interruptions across the ref CAS,
   canonical artifacts, register, ledger, learnings, and campaign state on the
   next locked `run-iteration`. The intent is closed, strictly decoded,
   digested, and fully cross-validated before recovery mutates anything;
   terminal receipts retain only identity, intent digest, result summary, and
   an error for failure. Pre-intent failures delete their exact staging ref,
   while a durable intent owns later cleanup. This is not a general campaign
   recovery journal. Same-user automatic bundle creation is a simulated
   rehearsal only.

## Use

```bash
make install     # install eval + judge + loop from their explicit package graph
make loop-test   # unit + transactional end-to-end tests (real command bridge)
make install-check  # uv-offline/no-index install + deterministic installed tests
```

`opti-loop==0.1.0` declares exact dependencies on
`opti-browser-eval==0.1.0` and `opti-judge==0.1.0`. Global options precede the
subcommand, for example
`opti-loop --store-root /safe/path init --campaign rehearsal
--max-iterations 3 --max-attempts 6 --deadline-seconds 3600`.
`install-check` invokes no live backend, but it is not an OS-level network
sandbox.

The operable offline D3 rehearsal is initialized directly with, for example:

```bash
opti-loop --store-root /safe/path init --campaign rehearsal \
  --adapter harness-fixture \
  --harness-file harness/components/policy/quality.txt \
  --pass-rate 0.55 --seed 0 \
  --max-iterations 3 --max-attempts 6 --deadline-seconds 3600
```

`--harness-file` is required for `harness-fixture`; `--pass-rate` supplies its
accepted-build fallback/default and defaults to `0.55`, while `--seed` defaults
to `0`. The shipped `harness/components/policy/quality.txt` is registered in its
component and contains the accepted-build rate. Initialization validates that
the path is safe, allowed, present in the accepted Git surface, regular,
non-symlink, readable, finite, and a rate in `[0, 1]`; the fallback pass rate
has the same finite range. Fixture evidence remains simulated, cannot advance
accepted state, and cannot change research-continuation counters. Unsupported
adapters stop at E1 before any treatment execution.

Operator commands (see `opti-loop --help`): `init`, `preflight`, `run`,
`resume`, `pause`, `stop`, `measure-noise`, `start`, `run-iteration`, `status`,
`compare-campaigns`, `transfer-plan`, and the
non-executing `warc-online4-preflight`. See
[`docs/AUTO_RESEARCH_OPERATOR_RUNBOOK.md`](../docs/AUTO_RESEARCH_OPERATOR_RUNBOOK.md)
for the exact foreground workflow and external activation checklist, and
[`docs/WARC_ONLINE4_QUALIFICATION.md`](../docs/WARC_ONLINE4_QUALIFICATION.md)
for the exact external-input and operator contract.
The optimizer's contract lives in [`PROGRAM.md`](../PROGRAM.md).
