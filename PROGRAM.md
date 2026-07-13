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

1. **A — EVALUATE**: the Conductor runs the development suite via `opti-loop start --campaign <id>` (baseline evaluation + analysis + your iteration packet at `campaigns/<id>/iterations/iter-NNNN/PACKET.md`). Repetition counts follow per-task stability history (k=1 until real stochastic adapters exist).
2. **B — ATTRIBUTE**: the Conductor intersects your previous manifest's predictions with observed flips and issues keep / revert / partial per edit. Rollbacks are file-granular and are themselves manifested changes.
3. **C — DISTILL**: the Analyst publishes the layered report and updated failure-cluster register ([`docs/architecture/ANALYST.md`](docs/architecture/ANALYST.md)). You read; you do not edit.
4. **D — EVOLVE (you)**:
   - Take the **highest-priority unresolved cluster** from the register unless the Conductor directs otherwise.
   - **If the Conductor marks the iteration divergent** (exploration quota or plateau trigger, [ADR-0015](docs/adr/0015-auto-research-loop-architecture.md) §9): do not target the top cluster. Select an architecture-class hypothesis (for example from the hypothesis backlog) under the same manifest and gate discipline, and record what was learned regardless of verdict.
   - Form **one hypothesis**; select **exactly one target component**.
   - Implement the change as **one commit**.
   - Write **one manifest entry** (§4).
   - After **two failed attempts** on the same cluster at the same component, you must **pivot component level** — do not try a third variation in place.
   - Never retry a failed hypothesis without first recording why the previous prediction was wrong.
5. **E — GATE**: `opti-loop gate --campaign <id>` runs the E0–E5 ladder of [ADR-0005](docs/adr/0005-experiment-gating.md) deterministically and appends attribution to your manifest. You receive the verdict and artifacts (`gate-report.json`); you do not negotiate with it. On rejection, `opti-loop rollback --campaign <id>` reverts exactly your manifest's change scope.
6. **F — RECORD**: `opti-loop record --campaign <id>` writes the ledger row and a learnings template — complete the learnings entry **whether the change passed or failed**.

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
opti-loop init --campaign <id>       # create a campaign (fixture adapter by default)
opti-loop measure-noise --campaign <id>
opti-loop start --campaign <id>      # phase A+C: baseline, analysis, your packet
opti-loop gate --campaign <id>       # phases E+B: E0–E5 ladder + attribution
opti-loop record --campaign <id>     # phase F: ledger + learnings template
opti-loop rollback --campaign <id>   # file-granular revert of the manifest scope
```

Fixture and simulated runs validate plumbing only; their gate verdicts are
watermarked `simulated:` and must never be reported as benchmark performance
or real acceptances.
