# PROGRAM.md — Optimizer Runbook (v0)

- Status: **The auto-research loop is NOT yet active.** This runbook is governed by [ADR-0015](docs/adr/0015-auto-research-loop-architecture.md), [ADR-0016](docs/adr/0016-judge-panel-and-verifier-audit-protocol.md), [ADR-0018](docs/adr/0018-auto-research-readiness-protocol-transition.md), [ADR-0005](docs/adr/0005-experiment-gating.md), and [ADR-0004](docs/adr/0004-trace-storage.md). It becomes operative only after the pre-activation requirements pass: source bridges emitting conforming traces, verifiers admitted via probe kits, the suite and noise band calibrated, the ADR-0005 injection catalog green, and the project owner explicitly starting the loop.
- Audience: the external coding agent acting as the **Optimizer**.
- Binding constraints you inherit regardless of this document: [ADR-0001](docs/adr/0001-project-constitution.md) (constitution), [ADR-0007](docs/adr/0007-nested-smoke-suite.md), [ADR-0012](docs/adr/0012-reference-success-band-35-to-70.md), [ADR-0014](docs/adr/0014-run-all-140-candidates-before-filtering.md), and [`PROJECT_CHARTER.md`](PROJECT_CHARTER.md).

## 1. Your role

You improve the browser-agent **harness-under-test** — nothing else. You read traces and analysis, form one falsifiable hypothesis, make one causal treatment inside the frozen candidate boundary, predict its effects, and submit it to a deterministic gate. You do not score runs, you do not decide acceptance, and you do not modify the instruments that measure you.

## 2. Files you own and files you must never touch

| Surface | Access |
|---|---|
| Exact paths printed by `opti-loop start` from the frozen `candidate_allowlist` | **read/write — the only writable surfaces** |
| `harness/infra/**`, `harness/lanes/**`, activation instrumentation, executor/model pins, safety and evidence contracts | read-only |
| `evals/**`, `schemas/**`, `eval_harness/**`, verifiers, bridges, suite manifests | read-only; never edited inside an iteration |
| `docs/**`, `scripts/**`, `PROGRAM.md`, ledger and manifest history | read-only |
| Holdout tasks, holdout traces, judge-only evidence, verifier internals | **no access — do not attempt to locate or infer** |

Gate E0 enforces this with a git file guard. A diff outside the allowlist is rejected before evaluation, and the attempt is recorded.

## 3. The iteration you run

Phases per [ADR-0015](docs/adr/0015-auto-research-loop-architecture.md); commands marked *(future)* do not exist yet and will be pinned here when implemented.

Campaign identity (harness workspace branch, base lane, ledger, cluster register) is fixed in run configuration. You never switch, fork, or merge campaigns yourself; mechanisms from other campaigns arrive as normal manifested changes through your gate.

1. **A — EVALUATE**: `opti-loop start --campaign <id>` captures the trusted base SHA, creates your **isolated candidate worktree**, runs the baseline + regression baseline there, distills, and writes your packet into the owner-only trusted store. The command prints the worktree path — that is your only writable surface.
2. **D — EVOLVE (you)**: work **inside the worktree**:
   - Take the **highest-priority unresolved cluster** from the packet unless the Conductor directs otherwise.
   - **If the iteration is marked divergent** (exploration quota or plateau, [ADR-0015](docs/adr/0015-auto-research-loop-architecture.md) §9): do not target the top cluster; select an architecture-class hypothesis and set `cluster_ref` to `divergent/...`.
   - Form **one hypothesis** and name one `target_component` for attribution. That label is not path authority.
   - Edit only the exact frozen allowlist paths printed by `start`; make **one candidate commit**. An irreducible cross-surface treatment must predeclare every changed file.
   - Write **one `manifest.json`** in the worktree root (§4) — untracked; the Conductor ingests it.
   - After **two failed attempts** at the same cluster+component the Conductor forces a **pivot** — a third local retry is rejected at E0.
3. **E + B + F — RUN-ITERATION (one transaction)**: `opti-loop run-iteration --campaign <id>` is a single atomic step. It ingests and validates your manifest, runs the E0–E5 ladder ([ADR-0005](docs/adr/0005-experiment-gating.md)) over the `base..candidate` **commit diff**, computes attribution (B), writes the gate report + ledger row to the trusted store (F), advances accepted state **only** on a genuine `(accepted, benchmark)` verdict, and resets your worktree either way. There is no separate, forgeable gate/record/rollback step to exploit.
   - The Conductor distills and updates the cluster register at `start`; you read the packet, you never edit the store.
   - Never retry a failed hypothesis without first recording why the previous prediction was wrong (learnings).

## 4. The manifest you must write

Contract: [`schemas/experiment.schema.json`](schemas/experiment.schema.json); optimizer-input shape: [`examples/experiment.example.json`](examples/experiment.example.json). The canonical schema requires `target_component` and `cluster_ref`, defines the optional post-evaluation `attribution` block, and has a separately discriminated `rejected_submission` record that preserves invalid optimizer JSON plus its validation errors without inventing experiment fields. The Optimizer must emit only the experiment input shape and omit `attribution`; the Conductor alone writes trusted terminal records. Every field is mandatory in spirit — an empty `regression_risks` array is almost never true.

Minimum content: trace evidence (run and event IDs) → suspected root cause → the targeted change and why **this** component → predicted fixes as failure classes and tasks → predicted risks → activation evidence the auditor can check → acceptance criteria consistent with the gate.

## 5. Hard rules

1. **One hypothesis, one causal treatment, one commit, one manifest** per iteration.
2. **Never** edit verifiers, tasks, suites, bridges, judges, schemas, gate code, or this file.
3. **Never** encode benchmark tokens, task IDs, or site-specific answers into code, skills, or memory. The generality lint reads your diff and your memory content; state predictions as failure classes.
4. **Never** read or infer holdout material or judge-only evidence.
5. **Skills and long-term memory** ship only through the independent verification channel — you propose, an independent verifier admits ([ADR-0015](docs/adr/0015-auto-research-loop-architecture.md) §7). You never admit your own skills.
6. **Runtime workflow memory** is reset per evaluation run by default; configurations that accumulate memory are labeled and scored separately.
7. `invalid` / `error` results are infrastructure signals, not evidence — do not build hypotheses on them; flag them.
8. Respect the safety invariant: no live-site actions exist in the loop until [ADR-0006](docs/adr/0006-live-site-testing-policy.md) is settled; destructive-action interlocks in middleware must not be weakened to gain speed.
9. When blocked (missing artifact, contradictory instruction, suspected instrument fault), **record the blockage in your learnings entry and stop**. Do not expand your own scope to work around it.

## 6. Learning records

The Conductor writes one closed, versioned, trace-cited `LearningRecord` per
terminal iteration. It binds campaign, iteration, base/candidate/protocol,
decision, source disposition, and retained gate/trace/artifact checksums. The
next packet includes only the latest revalidated record. Missing, malformed, or
stale citations block the next packet. Simulated records are explicitly
`simulation-only` and never become benchmark learning or performance evidence.

## 7. Verification commands available today

```bash
make eval-validate        # catalog + suite integrity (140 tasks, nesting)
make eval-test            # unit tests for the orchestration layer
make eval-smoke-fixture   # plumbing check; reports benchmark_reportable=false
make loop-test            # loop-shell unit + end-to-end dry-run tests
make install-check        # uv-offline/no-index install + deterministic installed tests
make docs-verify          # documentation and link integrity
```

`install-check` invokes no live backend, but it is not an OS-level network
sandbox. Its package build, resolution, and install steps are constrained to
uv's offline mode, a local wheelhouse, and no index.

Loop operator commands (conductor; see `loop_harness/README.md`):

```bash
opti-loop --store-root PATH init --campaign <id>     # global flags precede the subcommand
opti-loop preflight --campaign <id>                  # read-only actionable readiness
opti-loop run --campaign <id>                        # one foreground start/resume step
opti-loop pause --campaign <id>                      # preventative safe-boundary request
opti-loop resume --campaign <id>                     # clear pause and advance one step
opti-loop stop --campaign <id>                       # terminal owner request
opti-loop measure-noise --campaign <id>              # owner artifact, identity-bound
opti-loop start --campaign <id>                      # phase A+C: base worktree, baseline, packet
opti-loop run-iteration --campaign <id>              # phases E+B+F as ONE transaction
opti-loop status --campaign <id>
opti-loop compare-campaigns --campaigns a,b          # scheduled, run-identity-checked
opti-loop transfer-plan --campaign <id>              # pre-registered transfer checkpoint
```

The optional global flags are `--repo-root PATH` and `--store-root PATH`; put
either before `init`, `status`, or another subcommand. When `--repo-root` and
`OPTI_BROWSER_REPO_ROOT` are absent, the installed CLI discovers the repository
from the current directory and its parents.

Raw evaluator summaries never grant benchmark reportability or decision
eligibility. Only the Conductor's complete AR-003 result/trace/artifact,
verifier-admission, T1, and quarantine review can issue an admission receipt.
Both paired benchmark arms and every real noise sample require one.

Fixture and simulated runs validate plumbing only; their verdicts carry
`evidence_class: simulated` and can **never** advance real accepted state or be
reported as benchmark performance. Only `(accepted, benchmark)` — a reportable,
verifier-admitted, noise-identity-bound run — advances the campaign.
