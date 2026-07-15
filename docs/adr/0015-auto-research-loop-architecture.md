# ADR-0015: Auto-research loop architecture

- Status: Accepted
- Date opened: 2026-07-13
- Date proposed: 2026-07-13
- Amended: 2026-07-13 — §9 exploration policy added and executor confirmation recorded per project-owner direction; trusted-boundary containment added after adversarial review
- Date accepted: 2026-07-13
- Approval state: Accepted — explicit project-owner approval (2026-07-13). Loop activation remains separately gated on bridges, calibration, and the ADR-0005 injection catalog.
- Supersedes: —
- Superseded by: —
- Nonbinding transition proposal: [ADR-0018](0018-auto-research-readiness-protocol-transition.md) would broaden the explicit candidate-owned harness-build boundary and make exact evaluated builds indivisible; it has no effect unless explicitly accepted.
- Answers: Open Question 16
- Supporting specifications: [`../architecture/COMPONENT_TREE.md`](../architecture/COMPONENT_TREE.md), [`../architecture/ANALYST.md`](../architecture/ANALYST.md), [`../../PROGRAM.md`](../../PROGRAM.md)

## Question

How should the two reference auto-research frameworks — `neosigmaai/auto-harness` and `china-qijizhifeng/agentic-harness-engineering` (AHE) — be adapted into this project's auto-research loop rather than copied blindly?

## Proposed direction

### 1. Fork basis

Take the **auto-harness loop shape** as the skeleton and the **AHE method as process contracts**, not as a codebase:

- **From auto-harness**: the small, benchmark-agnostic outer loop whose driver is an external coding agent reading a runbook ([`PROGRAM.md`](../../PROGRAM.md)). Its benchmark layer is replaced wholesale by `opti-eval`; the runner contract it expects (`run(task_ids) → {task_id: reward}`) is already exceeded by the existing orchestration layer, which additionally reports fail-closed validity and `benchmark_reportable`.
- **From AHE**: component decomposition of the harness-under-test, one-hypothesis change manifests, prediction-based attribution, file-granular rollback, and activation audits — adopted as contracts. The AHE codebase itself is not forked: it is welded to NexAU, E2B, harbor, and a partially closed-source Agent Debugger, none of which this project uses.
- **From the auto-harness method article**: failure clusters as the unit of analysis, prioritized by frequency × unresolved-rate.

### 2. Five structurally separated planes

| Plane | Implemented as | May write to |
|---|---|---|
| Conductor | deterministic scripts; no LLM participates in any gate decision | loop sequencing, gate execution, manifest verification, rollback, promotion records |
| Evaluation plane | `opti-eval`, per-source bridges, verifiers, judge panel ([ADR-0016](0016-judge-panel-and-verifier-audit-protocol.md)) | tasks, environments, resets, scoring, traces; read-only to every other plane; never edited inside an iteration |
| Analyst | LLM pipeline specified in [`ANALYST.md`](../architecture/ANALYST.md) | layered analysis reports and the failure-cluster register only; non-scoring; no write access to harness or evaluation plane |
| Optimizer | external coding agent driven by [`PROGRAM.md`](../../PROGRAM.md) | the harness workspace only, enforced by a git file guard |
| Harness-under-test | component-decomposed browser agent per [`COMPONENT_TREE.md`](../architecture/COMPONENT_TREE.md) | its own runtime; judge-only evidence is structurally withheld from it via trace visibility tags |

Every accept/reject decision must be reproducible from recorded artifacts alone.

### 3. The iteration

- **A — EVALUATE.** Run `opti-eval` over the development suite. Repetition count per task follows per-task stability history (k=1 for stable tasks, k=3 for unstable tasks; exact values are open parameters). Requirement recorded for implementation: per-task resume, so a partially failed sweep continues rather than restarts.
- **B — ATTRIBUTE.** Intersect the previous manifest's predictions with observed task flips. Verdict per edit: keep, revert, or partial, with file-granular git rollback. Prediction accuracy is logged to the ledger.
- **C — DISTILL.** The Analyst produces the layered report and updates the failure-cluster register. Every claim must cite trace event IDs. Partial-pass and flipped tasks receive divergence analysis.
- **D — EVOLVE.** The optimizer targets the highest-priority unresolved cluster. One hypothesis per change; one commit plus one manifest entry containing evidence, suspected root cause, the fix, predicted fixes and risks, and why this component. After two failed attempts on the same cluster at the same component, the optimizer must pivot component level.
- **E — GATE.** The E0–E5 ladder defined in [ADR-0005](0005-experiment-gating.md).
- **F — RECORD.** Ledger row; regression-suite promotion only after repeated passes with a motivating trace and cluster ID (consistent with [ADR-0009](0009-regression-suite-seeding-and-promotion.md)); learnings appended whether the change passed or failed; holdout checkpoints are scheduled events, never per-change.

### 4. Manifest and attribution protocol

[`schemas/experiment.schema.json`](../../schemas/experiment.schema.json) is the canonical manifest-record contract ([`examples/experiment.example.json`](../../examples/experiment.example.json) shows the optimizer-input branch). The experiment branch requires `target_component` (exactly one component from the component tree) and `cluster_ref` (the motivating cluster ID), and defines the optional post-evaluation `attribution` block (predicted vs. observed flips, per-edit verdict, prediction accuracy). A separately discriminated conductor-only `rejected_submission` branch preserves an invalid original JSON value, its validation errors, and the actual terminal verdict without fabricating experiment fields. The optimizer must emit only the experiment branch and omit `attribution`; the Conductor alone writes trusted terminal records. A rollback is itself a manifested change. The optimizer must not retry a failed hypothesis without first recording why the previous prediction was wrong.

### 5. Containment

**Trusted experiment boundary (added 2026-07-13 after adversarial review).** The optimizer runs against an owner-controlled boundary, not a shared mutable tree: the conductor captures a trusted `accepted_base_sha`, the optimizer edits only `harness/components/**` inside an isolated **git worktree** and produces exactly one candidate commit, and E0's authority is the `base..candidate` **commit diff** (immune to working-tree hiding, `assume-unchanged`, and `.git/info/exclude`). All conductor-owned artifacts — config, state, ledger, gate reports, noise band, quarantine, corpus — live in a store **outside the repo** the optimizer can write. Gate → attribute → record → accept/reset execute as **one atomic transaction**; there is no separable, forgeable record step. Advancing accepted state requires a typed `(accepted, benchmark)` verdict; a `simulated` (fixture) verdict is structurally inert. In production the optimizer is mounted with only the worktree's `harness/components` writable — the design enforces the boundary given that confinement.

1. **File guard**: the optimizer's writable surface is an explicit allowlist (the harness workspace); everything else — evaluation plane, schemas, suites, verifiers, bridges, documentation, `PROGRAM.md` itself — is rejected at gate E0, over commit objects, with path-safety (no traversal, symlinks, or absolute paths).
2. **Generality lint**: diffs and memory/skill content are linted for benchmark tokens, task-ID literals, and site-specific shortcuts that encode task answers; predictions must be stated as failure classes, not task IDs alone.
3. **No LLM in gate decisions**: judges flag and diagnose; deterministic verifiers score; the Conductor's gate logic is plain code.
4. **Visibility boundary**: judge-only evidence never enters executor or optimizer context (trace `visibility` tags per [`schemas/trace-event.schema.json`](../../schemas/trace-event.schema.json)).

### 6. Harness-under-test structure

The harness is decomposed into eight optimizer-evolvable components — policy, observation, actions, tool descriptions, middleware, skills, sub-agents, memory — over optimizer-untouchable infrastructure mounts (session interface, backend adapters, model configuration, tracer, verifiers, bridges, budgets). Every failure cluster maps to exactly one component. The seed harness is deliberately minimal (structured lane only; no skills, memory, middleware, or sub-agents) to protect early attribution. Details and file contracts: [`COMPONENT_TREE.md`](../architecture/COMPONENT_TREE.md).

Research lanes are represented as **pinned observation/action configurations over the one component tree** (structured lane = accessibility tree + element references; visual lane = screenshot + set-of-marks + coordinates). This is recorded here as the proposed resolution direction for the core of [ADR-0002](0002-shared-substrate-and-lane-boundaries.md); ADR-0002 itself remains open until explicitly moved.

### 7. Memory three-regime rule

1. **Optimizer learnings** (meta-level notes about the research process): unrestricted, appended pass or fail.
2. **Harness long-term memory and skills** (ship with the harness): admitted only through generality lint, independent verification, and transfer checks — the solver never admits its own skills.
3. **Runtime workflow memory** (accumulated during execution): a legitimate mechanism, but benchmark evaluation resets accumulated content per run by default; configurations that carry accumulated memory are labeled and scored separately.

### 8. Deliberate divergences from the reference designs

1. **No monotonic best-score ratchet.** auto-harness gates on `val_score ≥ best`. On stochastic browser tasks a lucky run ratchets the bar and then locks progress. Replaced by E5's paired comparison against a measured noise band.
2. **At-risk predictions are never used for regression protection.** AHE's own data shows regression prediction barely beats chance (see evidence below); regression safety is structural (gate E4, whole-suite flip scan, side-effect checks per ADR-0016), never taken from the optimizer's self-declared risk list.
3. **No LLM anywhere in gate decisions**, stricter than both references.

### 9. Exploration policy: divergent hypotheses and parallel campaigns

Cluster-driven iteration (§3.D) is deliberately exploitative and can lock a campaign onto the first workable path. Two mechanisms counter this, both built from machinery already in this proposal:

1. **Divergence quota.** Each campaign reserves a fraction of iterations (open parameter) as *divergent iterations*. In a divergent iteration the optimizer does not attack the top cluster with a local edit; it selects an architecture-class hypothesis — for example from the landscape hypothesis backlog: alternative page representation, compound actions, a different action mechanism, hybrid escalation — and carries it through the **same** manifest and gate discipline. The expected value of a divergent iteration is information: the ledger entry must record what was learned even when the change is rejected. A plateau trigger (top clusters unresolved for K consecutive iterations, or aggregate movement within the noise band for M consecutive iterations — open parameters) forces the next iteration to be divergent.
2. **Parallel campaigns.** A campaign is a branch of the harness workspace with its own ledger and cluster register, sharing the frozen evaluation plane, suites, judges, and executor pin. Two to three campaigns may run as a population, started from deliberately different bases (for example: the minimal structured-lane seed; a visual-lane seed; one wildcard base). Because the evaluation plane is read-only to every campaign, campaigns are independent by construction. Cross-campaign comparison is a scheduled report over the same suite — never a per-iteration race — and transplanting a winning mechanism from one campaign into another is itself a manifested change through the receiving campaign's normal gate. Campaign count is bounded by budget, not by architecture.

Rationale: the project owner has observed path lock-in across auto-research harnesses, and the reference evidence points the same way — component gains are non-additive, and single-path optimization plateaus. The component-pivot rule (§3.D) counters lock-in at the component level; this section counters it at the architecture level.

## Why this is proposed

Evidence (sources in [`../REFERENCES.md`](../REFERENCES.md)):

- **The loop shape works and transfers.** AHE: Terminal-Bench-2 pass@1 69.7% → 77.0% in 10 iterations with the executor fixed; the frozen harness transferred to SWE-bench-verified (+0.4 pp, −12% tokens) and to five alternative models (+2.3 to +10.1 pp, largest on weaker bases), while prompt-only baselines regressed on transfer. This supports optimizing harness artifacts around a fixed, inexpensive executor.
- **Component gains are non-additive.** AHE ablations: memory-only +5.6, tools-only +3.3, middleware-only +2.2, system-prompt-only −2.3 (negative); single-component gains sum to +11.1 vs. +7.3 for the full harness. Combinations must be gated, not stacked — hence one component per change and gate E5 on the combination.
- **Regression blindness is real.** AHE fix-prediction precision/recall 33.7%/51.4% (~5× random) vs. regression-prediction 11.8%/11.1% (~2× random). Optimizers can predict what they fix but not what they break — hence divergence 2.
- **Cluster-driven prioritization compounds.** The auto-harness method grew a regression suite from 0 to 17 protected cases over 18 batches by fixing prioritized clusters and promoting fixes.
- **Self-generated skills are dangerous.** Curated skills averaged +16.2 pp, but self-generated skills contributed ≈0 and were harmful in roughly one-third of tasks — hence regime 2 of the memory rule and independent skill verification.

## Interaction with open decisions

- **ADR-0002** (lanes): §6 records the proposed direction; acceptance is a separate decision.
- **ADR-0003** (browser backend): untouched. The harness-under-test's control layer remains the research subject; the evaluation infrastructure's substrate is a separate, reversible default to be recorded when bridges are built.
- **ADR-0004** (trace storage): this architecture imposes requirements on whichever store is chosen — visibility tags, `browser_state_epoch`, event-addressable claims — without selecting the store.
- **ADR-0005** (gate): the E0–E5 ladder is specified there; this ADR depends on it.
- **ADR-0006** (live sites): unaffected; the loop runs on benchmark suites until ADR-0006 is settled.
- **ADR-0016** (judge panel): the evaluation plane's scoring and audit protocol.

## Requirements recorded for implementation (deferred, not scheduled)

1. Per-task resume in phase A.
2. Quorum validity semantics for E5 comparisons (valid-in-both intersection; coverage floor; no source family absent) — defined in ADR-0005, implemented later.
3. Per-source concurrency limits (the gated ServiceNow instance behind WorkArena++ must serialize).
4. The hidden holdout must be carved **before** the first optimizer run and cannot live in this public repository: under [ADR-0014](0014-run-all-140-candidates-before-filtering.md) all 140 candidates burn as optimizer-visible.
5. A one-shot explore pass over the surveyed browser-agent codebases may seed initial skill/middleware candidates before iteration 1; seeds receive no special protection afterward.
6. Executor model: the project owner confirmed **MiniMax-M3** as the loop executor (2026-07-13, direction given in project scope). Exact API identifier, snapshot, settings, and data-policy pinning remain under Open Question 17 and [`../models/CANDIDATES.md`](../models/CANDIDATES.md). Judges are exempt from executor cost economy per ADR-0016.
7. Future objective axes beyond reliability — efficiency (cost, latency, tokens, action count) per the charter's optimization order, and **bot-detection/stealth outcomes** for later live-site suites under [ADR-0006](0006-live-site-testing-policy.md) — must be representable in the trace/result metric contracts from the start so later campaigns can optimize them without re-architecting. They are recorded as diagnostics now and are not gate criteria.

## Open parameters

Repetition counts (k) and the stability history that selects them; noise-band measurement protocol; cluster-priority weighting; per-iteration and per-campaign budgets; holdout checkpoint cadence; divergence quota; plateau triggers (K, M); campaign population size.

## Decision gate

Accept this ADR only after review of the loop structure against the decision process. Before the loop is ever activated (a separate, later decision), it must additionally pass the synthetic failure-injection catalog defined in ADR-0005 on the fixture adapter, and real source bridges plus suite calibration must exist. Explicit project-owner approval is required.
