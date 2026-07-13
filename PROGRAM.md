# PROGRAM.md — Optimizer Runbook (v0)

- Status: **v0 draft. The auto-research loop is NOT active.** This runbook is governed by [ADR-0015](docs/adr/0015-auto-research-loop-architecture.md), [ADR-0016](docs/adr/0016-judge-panel-and-verifier-audit-protocol.md), and [ADR-0005](docs/adr/0005-experiment-gating.md), all currently **Proposed**. It becomes operative only after those ADRs are accepted, source bridges exist, the suite is calibrated, and the project owner explicitly starts the loop.
- Audience: the external coding agent acting as the **Optimizer**.
- Binding constraints you inherit regardless of this document: [ADR-0001](docs/adr/0001-project-constitution.md) (constitution), [ADR-0007](docs/adr/0007-nested-smoke-suite.md), [ADR-0012](docs/adr/0012-reference-success-band-35-to-70.md), [ADR-0014](docs/adr/0014-run-all-140-candidates-before-filtering.md), and [`PROJECT_CHARTER.md`](PROJECT_CHARTER.md).

## 1. Your role

You improve the browser-agent **harness-under-test** — nothing else. You read traces and analysis, form one falsifiable hypothesis, make one component-scoped change, predict its effects, and submit it to a deterministic gate. You do not score runs, you do not decide acceptance, and you do not modify the instruments that measure you.

## 2. Files you own and files you must never touch

| Surface | Access |
|---|---|
| `harness/components/**` (the eight components: policy, observation, actions, tool_descriptions, middleware, skills, sub_agents, memory — see [`docs/architecture/COMPONENT_TREE.md`](docs/architecture/COMPONENT_TREE.md)) | **read/write — the only writable surface** |
| `harness/infra/**` (session interface, backend adapters, model config, tracer, budgets) | read-only |
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
   - Form **one hypothesis**; select **exactly one target component**.
   - Edit only `harness/components/<component>/**`; make **one candidate commit**.
   - Write **one `manifest.json`** in the worktree root (§4) — untracked; the Conductor ingests it.
   - After **two failed attempts** at the same cluster+component the Conductor forces a **pivot** — a third local retry is rejected at E0.
3. **E + B + F — RUN-ITERATION (one transaction)**: `opti-loop run-iteration --campaign <id>` is a single atomic step. It ingests and validates your manifest, runs the E0–E5 ladder ([ADR-0005](docs/adr/0005-experiment-gating.md)) over the `base..candidate` **commit diff**, computes attribution (B), writes the gate report + ledger row to the trusted store (F), advances accepted state **only** on a genuine `(accepted, benchmark)` verdict, and resets your worktree either way. There is no separate, forgeable gate/record/rollback step to exploit.
   - The Conductor distills and updates the cluster register at `start`; you read the packet, you never edit the store.
   - Never retry a failed hypothesis without first recording why the previous prediction was wrong (learnings).

## 4. The manifest you must write

Contract: [`schemas/experiment.schema.json`](schemas/experiment.schema.json); shape: [`examples/experiment.example.json`](examples/experiment.example.json). Every field is mandatory in spirit — an empty `regression_risks` array is almost never true. Loop extensions (schema revision pending, per ADR-0015 §4): `target_component`, `cluster_ref`, post-evaluation `attribution` block.

Minimum content: trace evidence (run and event IDs) → suspected root cause → the targeted change and why **this** component → predicted fixes as failure classes and tasks → predicted risks → activation evidence the auditor can check → acceptance criteria consistent with the gate.

## 5. Hard rules

1. **One hypothesis, one component, one commit, one manifest** per iteration.
2. **Never** edit verifiers, tasks, suites, bridges, judges, schemas, gate code, or this file.
3. **Never** encode benchmark tokens, task IDs, or site-specific answers into code, skills, or memory. The generality lint reads your diff and your memory content; state predictions as failure classes.
4. **Never** read or infer holdout material or judge-only evidence.
5. **Skills and long-term memory** ship only through the independent verification channel — you propose, an independent verifier admits ([ADR-0015](docs/adr/0015-auto-research-loop-architecture.md) §7). You never admit your own skills.
6. **Runtime workflow memory** is reset per evaluation run by default; configurations that accumulate memory are labeled and scored separately.
7. `invalid` / `error` results are infrastructure signals, not evidence — do not build hypotheses on them; flag them.
8. Respect the safety invariant: no live-site actions exist in the loop until [ADR-0006](docs/adr/0006-live-site-testing-policy.md) is settled; destructive-action interlocks in middleware must not be weakened to gain speed.
9. When blocked (missing artifact, contradictory instruction, suspected instrument fault), **record the blockage in your learnings entry and stop**. Do not expand your own scope to work around it.

## 6. Learnings ledger

Append one entry per iteration: hypothesis, verdict, prediction accuracy, what you now believe and why. Meta-level learnings are unrestricted (memory regime 1). This ledger is your only persistent memory across iterations — write for your successor.

## 7. Verification commands available today

```bash
make eval-validate        # catalog + suite integrity (140 tasks, nesting)
make eval-test            # unit tests for the orchestration layer
make eval-smoke-fixture   # plumbing check; reports benchmark_reportable=false
make loop-test            # loop-shell unit + end-to-end dry-run tests
make docs-verify          # documentation and link integrity
```

Loop operator commands (conductor; see `loop_harness/README.md`):

```bash
opti-loop init --campaign <id> [--store-root PATH]   # store lives OUTSIDE the repo
opti-loop measure-noise --campaign <id>              # owner artifact, identity-bound
opti-loop start --campaign <id>                      # phase A+C: base worktree, baseline, packet
opti-loop run-iteration --campaign <id>              # phases E+B+F as ONE transaction
opti-loop status --campaign <id>
opti-loop compare-campaigns --campaigns a,b          # scheduled, run-identity-checked
opti-loop transfer-plan --campaign <id>              # pre-registered transfer checkpoint
```

Fixture and simulated runs validate plumbing only; their verdicts carry
`evidence_class: simulated` and can **never** advance real accepted state or be
reported as benchmark performance. Only `(accepted, benchmark)` — a reportable,
verifier-admitted, noise-identity-bound run — advances the campaign.
