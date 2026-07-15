# Bring-Up Runbook — from accepted architecture to a running loop

**Audience: the bring-up agent (the owner's Codex harness).** You are being
handed this repository to (1) build the remaining instruments, (2) pass the
pre-activation requirements, and (3) run the auto-research loop until stopped
by the rules in §9. This document is your execution order. The law you operate
under is the accepted ADR set — 0001, 0004, 0005, 0007, 0012, 0014, 0015,
0016, 0017 — plus [`PROGRAM.md`](../PROGRAM.md) for the optimizer role.

**The one exclusion:** the browser-harness landscape research and the
ADR-0003 first-baseline decision are handled separately by the owner's
direction. Step B7 blocks on it; everything else does not.

---

## 0. Role architecture — read this before touching anything

You will play multiple roles. **They must run as separate principals, or the
trusted experiment boundary (ADR-0015 §5) is silently void:**

| Role | Runs as | May write |
|---|---|---|
| **Conductor/operator** (you, privileged) | owner-side OS user | trusted store, repo main, environments |
| **Optimizer** (phase D) | a SEPARATE confined session/OS user | ONLY the campaign's frozen candidate allowlist + its `manifest.json` |
| **Judges/Analyst** (T2) | sub-agents you spawn, preset GPT-5.6 Sol Ultra (ADR-0017) | analysis artifacts only — never scores, never the harness |

Hard rules:
1. **Never run the optimizer with conductor permissions.** The commit-diff
   guard, owner-only store, and atomic transaction assume the optimizer cannot
   reach the store, the eval plane, or `.git` internals of the main repo. One
   merged process voids all three.
2. The **trusted store** lives OUTSIDE the repo (`OPTI_STORE_ROOT`, default
   `<repo>/../opti-store`), owned by the conductor user, unreadable by the
   optimizer user.
3. **T3 stays human where it matters** (§8): you may operate everything else
   autonomously.

## 1. Host + secrets (Day 0)

- One dedicated Linux host (ADR-0017 item 7): Docker + Compose, Python ≥3.11,
  git, ~150 GB disk, stable uptime for multi-hour calibration runs.
- Two OS users: `opti-conductor` (store owner) and `opti-optimizer` (worktree
  only). Judges run under the conductor account as spawned sub-agents.
- Secrets via the repo's dotenvx workflow: OpenCode Go auth (executor,
  MiniMax-M3), Codex auth (judges, GPT-5.6 Sol Ultra preset), ServiceNow
  instance credentials, REAL access. Subscription auth must persist across
  restarts (owner requirement) — keep auth state on the conductor user's
  encrypted home, never in the repo or traces.
- Verify non-interactive invocation BEFORE building on it:
  (a) OpenCode Go can serve MiniMax-M3 calls programmatically;
  (b) Codex can spawn a Sol-Ultra sub-agent as a one-shot command reading
  JSON on stdin and writing JSON to stdout (the `command` provider contract in
  `judge_harness/src/opti_judge/llm.py`). Record the exact identifiers in the
  campaign config (ADR-0017 requires it; the run-identity hash pins it).

**Acceptance:** `make eval-validate eval-test loop-test judge-test docs-verify`
green on the host; both model paths answer a hello-world call.

## 2. B1 — Benchmark environments (the long pole)

Provision the five families pinned by
`research/benchmarks/task-candidates/batch-1-sources.lock.json`:
WebArena-Verified and VisualWebArena container stacks; a WorkArena++ L2
ServiceNow developer instance (gated signup; serialize access — per-source
concurrency limit is a recorded requirement); REAL v1 access; WARC-Bench
archive replay. **Acceptance:** each environment resets to a known state on
command, twice in a row, with identical observable state.

## 3. B2 — Tracer + five source bridges

Implement ADR-0004 emission (append-only `trace.jsonl` per task run +
content-addressed artifacts, visibility tags, `browser_state_epoch`) and one
bridge per family against the documented contract
(`eval_harness/README.md`): reset → resolve task → run harness → native
verifier → result JSON + trace + artifacts. Bridges are eval-plane code —
built by you as conductor, never touched inside iterations.
**Acceptance:** for each family, a smoke task produces a conforming trace
(schema-valid, epochs monotonic, artifacts hashed) and a fail-closed result;
`opti-judge t1` runs over it without EvidenceError.

## 4. B3 — Probe kits + verifier admission

Author the six probe trajectories per family (oracle, near-miss,
premature-stop, harmful-extra-action, stale/fabricated, malformed) and run
every verifier through `opti-judge probe` (blinded filenames; checksum
mandatory). Archive admissions to the store (`admissions.jsonl`) — eligibility
refuses benchmark evidence without a checksum-matched admission per task.
This is the largest manual-authoring block; budget accordingly. Every probe
seeds the calibration corpus for free.
**Acceptance:** 100% of tasks entering calibration have admitted verifiers.

## 5. B4 — Reference calibration, suite freeze, holdout

Run all 140 candidates (ADR-0014) through the pinned reference —
**BrowserGym GenericAgent + GPT-5.6 Sol Ultra** (ADR-0017) — with repeats
(k≥3 near the 35/70 band edges), record per-task success, then:
filter to the ~100-task primary suite inside the 35–70 band (ADR-0012),
keep smoke-20 nested (ADR-0007), record every exclusion with reasons,
**carve the hidden holdout conductor-side into `<store-root>/holdout/`
BEFORE any optimizer session exists** (ADR-0017 item 6 — the optimizer never
learns this location), seed the regression suite from repeatedly-passing
tasks, and present ADR-0008/0009 to the owner for acceptance with this
evidence. Start Batch-2 sourcing (popup/interference, long-horizon) in
parallel — the roadmap requires it concurrently, not after.
**Acceptance:** frozen suite manifests + calibration report + holdout carved
+ owner ping sent for 0008/0009.

## 6. B5 — Noise band + measured thresholds

`opti-loop measure-noise` (≥5 runs) on the frozen dev suite with the real
executor (MiniMax-M3 via OpenCode Go) — the band binds to the run identity and
must be non-synthetic for benchmark verdicts. Replace placeholder thresholds
(smoke floor, `min_prediction_precision`, regression repeats, quorum floor)
with values derived from observed variance; record the derivation in the
store. **Acceptance:** non-synthetic, identity-bound band in campaign config.

## 7. B6 — Judge wiring + calibration · B7 — Seed harness

- **B6:** switch the four LLM roles from `fixture` to the `command` provider
  invoking your Sol-Ultra sub-agent (the `pinned_target` in
  `evals/judges/roles/*.json`). Calibrate on the corpus accumulated from B3/B4
  (`opti-judge corpus measure`); trust opens only at each role's operating
  point on distinct, class-balanced cases. Replace the stub Analyst with the
  [`ANALYST.md`](architecture/ANALYST.md) pipeline over real traces.
  **Acceptance:** measured precision/recall per role per family, stored;
  cross-examiner trusted at its recall point before the loop starts.
- **B7 (blocked on ADR-0003):** implement the session interface + the minimal
  structured-lane seed agent per `COMPONENT_TREE.md` §6 on the substrate the
  landscape research selects. Do not pre-empt the decision.

## 8. Dress rehearsal, then launch

Run the ADR-0005 injection catalog on real infrastructure — a deliberately
disabled change must land `invalid` (not rejected), a broken tool `invalid`,
a seeded regression must die at E4, a seeded verifier false-positive must be
caught by probe kit or quarantined, a benchmark-token shortcut must die at E0.
**The gate passes its own exam before it judges anything real.**
Then: `opti-loop init` (structured-lane campaign; optionally a second
visual-lane campaign per ADR-0015 §9), transfer checkpoints scheduled
(every 5 accepted iterations, panel per ADR-0017), and start the
`start → optimizer session → run-iteration` cycle.

**Escalate to the owner (T3) — do not decide yourself:**
1. quarantine resolutions (`verifier_defect` / `task_defect` / `undecidable`) —
   batch them; the owner reviews asynchronously;
2. suite composition changes and judge-threshold changes;
3. a failed transfer checkpoint (bet-rejection criterion fired);
4. budget-ceiling breaches;
5. anything touching live sites (forbidden until ADR-0006 is accepted).

Everything else — iterations, rejections, rollbacks, learnings, reports — you
run autonomously.

## 9. Operating rules: budgets, stopping, reporting

- **Budgets (defaults; owner-adjustable):** per-iteration executor spend
  ≤ $10; campaign ceiling $500 per 25 iterations; judges are exempt but
  metered. Log spend per ledger row.
- **Stop/pause conditions:** (a) 10 consecutive non-accepted iterations
  including forced divergents → pause + diminishing-returns report;
  (b) transfer checkpoint rejects the bet → PAUSE EVERYTHING + escalate (the
  charter's core bet just failed); (c) budget ceiling → pause + report;
  (d) owner says stop. "Best harness possible" operationally = two consecutive
  5-iteration windows whose accepted aggregate gain is inside the noise band →
  deliver the final report instead of iterating further.
- **Reporting:** after every iteration, one ledger row (automatic); after
  every 5 iterations or any acceptance, a short owner-facing summary (score
  trajectory, accepted changes with attribution, cluster movement, spend);
  push repo `main` after each accepted iteration so the public repo tracks
  the accepted harness.
- **Never** weaken a gate, edit thresholds mid-campaign without re-measuring
  the noise band (identity binding will reject stale bands anyway), or let
  the optimizer role read the store, the holdout, or judge-only evidence.

## 10. Definition of done (bring-up)

Every box below is checkable mechanically; the loop may start only when all
are true:

- [ ] host + two-user confinement + secrets verified (§1)
- [ ] five environments reset deterministically (§2)
- [ ] five bridges emit conforming traces + fail-closed results (§3)
- [ ] every calibrated task has a checksum-matched verifier admission (§4)
- [ ] ~100-task suite frozen with recorded exclusions; holdout carved
      conductor-side; regression seeded; 0008/0009 sent to the owner (§5)
- [ ] non-synthetic identity-bound noise band + measured thresholds (§6)
- [ ] judges wired to Sol Ultra, calibrated, cross-examiner trusted;
      real Analyst live (§7 B6)
- [ ] seed harness built on the ADR-0003 substrate (§7 B7)
- [ ] injection catalog green on real infrastructure (§8)
- [ ] owner explicitly authorizes iteration 1 (ADR-0015: activation is an
      owner decision — this checklist does not self-authorize)
