# Production activation handover prompt

Copy the prompt below into a new Codex thread whose working directory is the
canonical Opti Browser Tool checkout.

---

You are taking ownership of the final production-activation mission for Opti
Browser Tool. Work against the real repository and runtime state; do not stop
at a plan, another placeholder, or an offline simulation. Use YAGNI: implement
the smallest source-by-source path that produces trustworthy real evidence,
while preserving every fail-closed boundary.

## Repository and starting point

- Repository: `https://github.com/keyclaw6/opti-browser-tool.git`
- Canonical local checkout: `/home/kab/opti-browser-tool`
- Start from a clean, fetched `main`, confirm it matches `origin/main`, and
  record the starting commit.
- Read `AGENTS.md` before changing anything. Never expose or commit secrets;
  follow the repository's dotenvx rules for real `.env*` files.
- Load and follow `$orchestrate-mission` because this is a substantial mission.
  Keep this parent thread responsible for scope, integration, evidence, and the
  final completion decision.

Read these sources before deciding that an older handoff or roadmap is current:

1. `PROJECT_CHARTER.md`
2. `docs/AUTO_RESEARCH_READINESS_EXECUTION.md`
3. `docs/AUTO_RESEARCH_IMPLEMENTATION_LEDGER.md`
4. `docs/AUTO_RESEARCH_OPERATOR_RUNBOOK.md`
5. `docs/WARC_ONLINE4_QUALIFICATION.md`
6. `docs/adr/0014-run-all-140-candidates-before-filtering.md`
7. `docs/adr/0016-judge-panel-and-verifier-audit-protocol.md`
8. `docs/adr/0018-auto-research-readiness-protocol-transition.md`
9. `docs/architecture/ANALYST.md`
10. `loop_harness/README.md`, `eval_harness/README.md`, and
    `judge_harness/README.md`

Treat accepted ADRs and the current readiness/implementation ledgers as
authoritative. Reconcile stale documentation when it materially misdirects an
operator, but do not create documentation churn.

## Current truth you must preserve

The repository is an offline software-ready, fail-closed research factory for
improving browser-agent components. It is not yet a live, calibrated, authorized
benchmark service. Fixture and simulated results are non-reportable.

T0 native verifiers are the only scorers. T1 deterministic checks flag
disagreement and route it to quarantine. T2 is currently inactive by design:
the real Analyst is still `stub-0`, there are no conforming retained real
browser traces for causal analysis, no sufficient per-benchmark labeled corpus,
and no pinned and measured T2 operating points. Never make T2 score, average a
disagreement, or override a native verifier.

The repeated-decision machinery exists, but production values are deliberately
unset. A matched block contains a baseline arm and a treatment arm; those are
different experimental conditions, not two attempts at the same condition.
The production repeat count must be measured, frozen before treatment results,
and applied to complete paired block sets. It is not necessarily two. Do not
use the simulated default of one repeat as production calibration, do not stop
early after favorable results, and return `inconclusive` when the frozen
coverage or evidence requirements are not met.

## Mission

Make the system genuinely usable for authorized browser-agent research in two
honest stages:

1. Deliver the first production-ready vertical slice: a real, reproducible,
   reportable WARC `online.4` qualification and bounded campaign with an
   admitted native verifier, complete trace retention, calibrated repeated
   decisions, calibrated non-scoring T2 flaggers, quarantine/T3 review, exact
   identities, and auditable evidence.
2. Then complete charter-wide activation source by source. Once real source
   assets and admitted verifiers exist, run all 140 provisional candidates
   before filtering, as required by ADR-0014. Do not call the first WARC slice
   five-source or all-140 readiness.

Do not invent assets, credentials, calibration samples, private-holdout
contents, authorization, benchmark scores, or success evidence. If a required
owner-controlled input is absent, prove the exact blocker early, finish every
safe implementation and validation task that does not depend on it, and hand
back a precise request naming the missing input and the command it unblocks.

## Required work

### 1. Establish the real activation boundary

- Run the documented clean install and offline operator path first. Distinguish
  `make install-check` (disposable packaging proof) from the persistent `.venv`
  plus `make install` needed for direct CLI use.
- Audit the real WARC assets, WACZ checksum/provenance/license, source-native
  reset and final-state behavior, admitted native verifier bundle, pinned
  BrowserGym/Playwright/browser/WARC/runtime identities, executor and judge
  provider/model/settings identities, named credential availability, external
  meter, and campaign authorization.
- Prove distinct conductor and optimizer OS identities, confinement, trusted
  store ownership, inbox permissions, worktree boundary, and recovery behavior
  on the actual host. Do not weaken a guard to pass preflight.
- Keep credentials out of logs, traces, manifests, diffs, and final reports.

### 2. Produce conforming, complete, reviewable traces

- Wire the real browser bridge to emit the accepted trace-event schema with
  stable `run_id`, `event_id`, `browser_state_epoch`, visibility, artifact
  addresses, lifecycle events, actions, observations, verifier evidence,
  resets, errors, and final state.
- Prove trace completeness and ordering against real oracle, near-miss,
  premature-stop, harmful-extra-action, stale/fabricated-trace, malformed-input,
  and representative agent trajectories. Missing or truncated evidence must
  fail closed or be reported as an instrumentation gap.
- The Analyst may consume all executor-visible events and events visible to the
  judge or orchestrator. It must never receive restricted material or private
  holdout traces.

### 3. Replace `StubAnalyst` with the real Analyst

- Implement the contract in `docs/architecture/ANALYST.md` without granting the
  Analyst score authority or write access to the harness/evaluation plane.
- L0 must account for the complete run: outcome deltas, validity, flips, and T1
  anomalies.
- L1 must reconstruct event-cited timelines for every failure, flip, partial
  pass, and flagged pass. Ordinary clean passes do not need speculative L1
  prose.
- L2 must maintain the failure-cluster register. L3 must compare changed or
  partial trajectories and identify the first divergent epoch/event.
- Every factual diagnosis must resolve to stored `run_id` plus `event_id`
  evidence, state uncertainty, and report insufficient evidence instead of
  guessing. Add adversarial tests for fabricated citations, visibility leaks,
  incomplete traces, stale epochs, and evaluator-suspect clusters.

### 4. Activate the T2 judge council only through calibration

Implement and calibrate the five ADR-0016 roles for each active benchmark:

1. completion cross-examiner;
2. side-effect and safety judge;
3. root-cause analyst;
4. implementation-activation auditor;
5. adjudicator.

For each role, define and enforce its evidence contract; pin the prompt, model
snapshot, settings, code, and calibration-corpus digest. Build the labeled
corpus from archived oracle runs, near-miss probes, harmful-extra-action probes,
and resolved quarantine cases. Measure precision/recall and freeze the approved
per-benchmark operating point before consuming flags. Re-score on the accepted
cadence and after any prompt/model change.

T2 remains a non-scoring flagging layer. Unresolved disagreement quarantines;
it never changes a T0 score. A false-negative suspicion must lead to verifier or
task repair, probe-kit readmission, and re-evaluation, never a score override.
Require explicit owner approval before the calibrated council becomes trusted.

### 5. Calibrate luck resistance and freeze the repeated protocol

- Use real source runs to estimate reset noise and outcome variance. Select the
  repeat count, seeds, required coverage/quorum, valid-after point, minimum
  effect, uncertainty rule, non-inferiority margin, regression allowance,
  champion floor, transfer cadence, maximum runs, and deadline from that
  evidence. Do not copy fixture values or choose “two” by intuition.
- Freeze and digest the calibration samples and production protocol before
  treatment results are visible. Run baseline and treatment in paired,
  interleaved task/seed blocks with reset per task arm and unique run identities.
- Enforce fixed complete block sets, no optional stopping, one-arm-only as
  inconclusive, and exact identity binding. Demonstrate with tests that a lucky
  first result, missing arm, changed seed/repeat/order, stale calibration, or
  incomplete coverage cannot promote a candidate.
- Preserve whole-suite regression, champion, transfer, multiplicity, and budget
  protections. Report the measured evidence and rationale for the selected
  repeat count.

### 6. Run the real qualification and campaign

- Before spending money or touching a live/external source, show the owner the
  exact frozen protocol, identities, metering limit, expected scope, and rollback
  path, and obtain explicit campaign authorization.
- Run the admitted WARC `online.4` oracle/probe qualification, a bounded real
  smoke, calibration, and one end-to-end baseline/treatment campaign through
  evaluate, T0, T1, calibrated T2, quarantine/T3, E0-E5, analysis, learning
  record, and atomic accepted-state advancement or rejection.
- Exercise interruption/recovery and prove that no partial or invalid evidence
  advances trusted state. Archive content-addressed evidence and produce a
  reproducible report that distinguishes pass, fail, invalid, quarantined, and
  inconclusive outcomes.
- Only after the first source is genuinely admitted and stable, add the next
  concrete source bridge. Do not build a generalized scheduler or compatibility
  layer before a second real source demonstrates the need.
- When the required source assets are available, execute and disposition all
  140 provisional candidates before filtering. Preserve private-holdout secrecy
  and the accepted suite-composition authority.

## Validation and independent review

Run the repository's focused and full gates in proportion to the changes,
including at minimum:

```bash
make install-check
make eval-validate
python3 scripts/verify_documentation.py --repo-root .
uv run --with jsonschema python scripts/validate_json_schemas.py --repo-root .
python3 scripts/verify_repository_completeness.py --repo-root .
python3 scripts/verify_file_manifest.py --repo-root .
```

Run the complete eval, judge, and loop harness tests and the documented
clean-install/unshared confinement checks. Add real-source acceptance tests and
adversarial failure tests for every newly trusted boundary. Record exact
commands, exit codes, evidence paths/digests, and justified skips.

After implementation is frozen, launch separate bounded read-only reviewer
agents. Each must load `$review-elegance`, receive the exact commit, mission
record, acceptance criteria, and evidence paths, and independently review:

- real source/runtime/verifier correctness and containment;
- trace completeness, Analyst claims, T2 calibration, visibility, and
  quarantine behavior;
- repeated-decision statistics, identity binding, recovery, and anti-luck
  behavior;
- YAGNI, operator usability, documentation truth, and readiness claims.

Consolidate findings before editing. If a reviewer finds a real defect, apply
only the smallest evidence-backed correction, rerun affected and full gates,
then rereview the exact final bytes. Do not reuse an approval tied to an older
commit or digest.

## Completion contract

Do not declare the first stage complete until all of the following are true:

- a real WARC `online.4` source and native verifier are admitted and pinned;
- a persistent operator install and actual-host confinement work;
- complete real traces are retained and the real Analyst produces resolvable
  event-cited outputs;
- every active T2 role has measured, approved, identity-bound calibration and
  remains non-scoring;
- the production repeat count and decision thresholds are evidence-derived,
  frozen, and proven resistant to a lucky run and incomplete paired evidence;
- an explicitly authorized bounded real campaign completed through the trusted
  state transition or honest rejection/inconclusive path;
- recovery, metering, quarantine, private-data boundaries, and evidence
  reproduction are demonstrated;
- full validation and exact-state independent reviews pass;
- the operator docs and readiness ledger state exactly what was proved and what
  remains blocked.

Do not declare charter-wide readiness until all required source bridges are
admitted and all 140 candidates have been run and dispositioned under the
accepted protocol. If external inputs prevent either completion level, return a
blocker handoff rather than a readiness claim.

At handoff, provide: final commit and remote branch, dirty-state proof, commands
and results, runtime identities, calibration and protocol digests, evidence and
quarantine locations, authorization record reference, reviewer verdicts, exact
claims now justified, remaining blockers, and the safest next command. Commit
and push completed work intentionally; leave the canonical checkout clean and
remove temporary worktrees/branches after their commits are integrated.

---
