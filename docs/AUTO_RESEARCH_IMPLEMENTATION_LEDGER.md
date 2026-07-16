# Auto-research implementation ledger

Status: active coordinator ledger. The accepted project mission is to build a
browser-harness research factory whose accepted changes are real, attributable,
repeatable, cumulative, and safe. Passing fixture plumbing is not progress
toward that mission unless the same trust boundary can reject forged, missing,
stale, or statistically lucky evidence.

This ledger consolidates the three independent audits in
`docs/review-reports/`. Work is intentionally sequential: one implementation
package is active at a time, an independent reviewer must return no actionable
findings, and only then may the package be committed and the next package start.

## Operating rules

1. The coordinator owns scope, ordering, audit mapping, and sign-off.
2. An implementation agent owns code and tests for one package only.
3. A separate review agent examines the resulting diff, tests the acceptance
   criteria, and reports findings without editing it.
4. Review findings return to the same implementation agent. Review repeats
   until clean.
5. Every agent must index the current repository with codebase-memory-mcp and
   use graph search/impact traces before editing or reviewing. Direct file reads
   and `rg` remain required for exact contracts and verification.
6. No real or live campaign is authorized by completing scaffold work. The
   pre-activation requirements in `PROGRAM.md` remain binding.

## Dependency-ordered implementation queue

| ID | Status | Package | Audit findings consolidated | Completion boundary |
|---|---|---|---|---|
| AR-001 | complete (`eb25f62`) | Fail external bridge results closed | FOUND-001; CONV-001; OPS-004 | Command/registry output cannot become benchmark-reportable by omission or a minimal pass payload; explicit task identity is mandatory; negative tests prove no state advance. |
| AR-002 | complete (`f21038c`) | Canonical experiment manifest contract | CONV-005 | JSON Schema, runtime validator, example, and conductor-owned attribution agree on one format and one invalid corpus. |
| AR-003 | complete (`72e73c2`) | Required trace/artifact evidence bundle | FOUND-002; CONV-001; OPS-004 | One shared validator rejects missing, malformed, mixed-run, duplicate, out-of-order, identity-mismatched, or unsafe trace/artifact evidence and accepts a conforming positive control. |
| AR-004 | queued | Symmetric run integrity and complete run identity | CONV-002; CONV-009; OPS-012 | Baseline, treatment, smoke, targeted, regression, full, and noise inputs use the same integrity policy; identity binds resolved content, code, environment, verifier, browser, model, and accepted base. |
| AR-005 | queued | Candidate activation and executed-tree binding | CONV-001; OPS-003 | Treatment runs use an immutable materialization of the accepted candidate commit, reject ignored/untracked payloads, and prove candidate/component activation in the trace. |
| AR-006 | queued | Exact causal commit and component-diff enforcement | CONV-007; CONV-008; OPS-001 | Exactly one non-merge, non-empty child commit is accepted; safe in-component delete/rename works; trusted cluster/task/evidence references are conductor-resolved. |
| AR-007 | queued | Trusted Git import boundary | OPS-001 | Optimizer cannot mutate common Git administration; conductor imports and validates a standalone patch/bundle into owner-controlled Git. |
| AR-008 | queued | Candidate sandbox and hard live-site deny | OPS-002; OPS-005 | Candidate runs under a distinct constrained boundary with allowlisted environment/mounts/network/processes; live/destructive transport is denied until ADR-0006 authorization exists. |
| AR-009 | queued | Verifier bundle identity, admission, and revocation | FOUND-007; CONV-004 | Admission binds executable, dependencies, command, environment, task config, and version; any repair/change revokes it; six probes must pass before reuse. |
| AR-010 | queued | Safe store namespace, permissions, and locks | FOUND-008; OPS-007; OPS-008 | Safe campaign IDs, no-follow containment, owner-only modes, per-campaign mutation locks, and per-environment leases prevent escape and races. |
| AR-011 | queued | Journaled exactly-once iteration recovery | OPS-006 | A durable iteration UUID/journal/receipt and ref CAS recover every start/gate/accept failpoint to exactly one committed or aborted result without split brain. |
| AR-012 | queued | Preventative lifecycle driver and operator health | OPS-009; OPS-010; OPS-013 | A persisted driver resumes safely, honors running/paused/stopped plus budgets/deadlines, cleans descendants, and `status` diagnoses reconciliation failures without exposing secrets. |
| AR-013 | queued | Identity-bound transfer and failed-transfer pause | CONV-013; OPS-011 | Finite complete paired transfer evidence is bound to campaign/base/candidate/task/model/environment identities; rejection atomically pauses further starts. |
| AR-014 | complete in reviewer-clean Milestone-E software checkpoint; uncommitted | Inconclusive outcomes and indivisible attribution | CONV-006; CONV-015 | Infrastructure invalidity is behaviorally inert and does not consume attempts; partial candidates never advance wholesale. |
| AR-015 | complete in reviewer-clean Milestone-E software checkpoint; uncommitted | Repeated paired statistical acceptance | FOUND-006; CONV-003 | Prespecified paired/interleaved repeats, uncertainty, minimum effect, and campaign-level false-acceptance control reject a stochastic no-op and detect powered positive controls. |
| AR-016 | complete in reviewer-clean Milestone-E software checkpoint; uncommitted | Durable regression and champion protection | CONV-010 | Repeatedly supported capabilities remain protected across transient misses, and cumulative degradation from the declared champion cannot random-walk through local noise. |
| AR-017 | queued | Event-addressable Analyst, clusters, and learnings | CONV-011 | Benchmark campaigns reject the stub; clusters are trace-backed and trusted; completed causal learnings are required before the next packet. |
| AR-018 | queued | Judge trust identity and quarantine routing | CONV-012 | T2 trust is scoped to exact prompt/model/provider/settings/evidence/corpus identity; only trusted judgments may route; untrusted outputs are state-inert. |
| AR-019 | queued | Source-aware scheduling and auditable task dispositions | FOUND-008; FOUND-010 | Per-source concurrency/leases are enforced; every provisional task has one validated disposition; smoke/source/site/mechanism coverage is mechanically checked. |
| AR-020 | queued | Generated commands, status prose, and decision metadata | FOUND-009; FOUND-012; CONV-016; OPS-014 | Packets invoke the real workflow; accepted-contract versus activation-pending text matches the decision register; executable documentation tests prevent drift. |

## Current readiness execution order

### Reviewer-clean milestone-E software checkpoint

- **Frozen starting state:** reviewer-clean milestone F is committed at
  `7c245e5402d03563f3ec98e067c612963c0a7725`.
- **Active writer:** GPT-5.6 Sol medium session
  `019f6aa3-ec13-70c1-a980-e661f21272aa` is the sole Milestone-E writer;
  `/root` remains orchestrator; no overlapping editor exists.
- **Implemented boundary:** the current consumer executes frozen repeated
  paired/interleaved development and regression arms with symmetric exact run
  identities/admission, four outcomes, prespecified stopping/budget/deadline,
  one supported paired-mean/observed-range/all-blocks rule, repeatedly supported
  predicted flips, post-arm deadline enforcement, protocol-owned quorum and
  fixed policy identifiers, durable accepted-state regression/champion
  evidence, and a canonically digested scheduled-transfer input evaluated by
  the existing transfer decision. Completed WARC arms
  reconstruct and revalidate conductor-owned activation from their existing
  closed artifacts. The legacy noise band is diagnostic only. Existing D3/F
  materialization, T1/quarantine/verifier admission, and recoverable accepted
  publication remain the authorities.
- **State boundary:** only `(accepted, benchmark)` may enter publication;
  simulated/local-fixture evidence and every rejected/inconclusive/invalid
  result are state-inert.
- **Final review evidence:** correctness session
  `019f6ade-3396-7303-afe6-afbf3e4e6083` returned CLEAN with no remaining P1;
  both hashes matched and nine focused read-only checks passed. Elegance/YAGNI/
  vision session `019f6ade-3492-78a2-8226-24d39ee6c825` returned CLEAN with no
  findings and matching hashes. Writer evidence passes 17 identity, 15
  repeated, 36 unit, 45 evidence/admission, 21 offline WARC, 21 materialization,
  and 68 E2E tests; the broader loop suite ran 205 tests, with 204 passing and
  one existing optional skip. This is reviewer-clean software ready to commit,
  not a performance or reportability claim. No calibrated real evidence,
  closed external transfer evidence, live WARC assets/runtime/credentials,
  verifier admission, or campaign authorization exists; Milestone D and overall
  operation readiness still depend on external activation and later G-I.

### Active milestone-F qualification slice

- **Frozen starting state:** D3 is committed at
  `9d6b39c361b1c7c9616884a055f59eaa5ce571fd` (`9d6b39c`), and the milestone-F
  worktree was clean before this ledger update.
- **Active writer:** session `019f6a00-be3a-7220-b4df-8b22c6da3f0c`, running
  GPT-5.6 Sol at medium reasoning effort, is the sole bounded milestone-F
  implementation writer. No overlapping editor exists.
- **Exact ownership:** one concrete `warc-bench-online-4` qualification path,
  including production code, focused deterministic tests, the minimum operator
  runbook/CLI surface, and the ledger/manifests needed by that slice.
- **Current status:** correctness rereview session
  `019f6a56-5b43-7442-a54a-091c1697a15b` and elegance rereview session
  `019f6a56-5a3f-7062-9d52-8f7a5dc4e342` returned FIX on the guessed upstream
  Gym constructor, post-close reconstructed-JSON scoring, runtime pins that did
  not govern actual imports, and blocking/leaky source-worker IPC. The bounded
  correction uses the pinned handler/CDP constructor shape, the admitted matcher
  on the live page, executed-module/replay/Node/browser identity checks, and
  deadline-bounded terminate/kill/reap cleanup. It is locally implemented and
  verified by 18 focused WARC tests, 64-test evaluator discovery, and the
  78-test affected loop end-to-end/CLI suite. Subsequent orchestrator source
  inspection found that the handler constructor/setup call was still invented;
  the targeted P1 correction now uses the pinned keyword constructor, mutates
  only the consumed `online.4` `task_config.env.data_path/start_url`, preserves
  the rest of that config, and calls `setup_webreplay_server(run_headless=True)`.
  The final correctness/elegance handbacks then found noisy upstream output on
  the JSON control channel, an unverified consumed task manifest, decorative
  snapshot/revision fields, an unbound resolved Gym environment/Playwright
  driver, and HTTP timeouts that could outlive the lifecycle. This one bounded
  pass now redirects diagnostics away from IPC, binds the installed manifest
  blob and exact original row, derives protocol snapshot/revision aliases from
  the one endpoint-consumed model ID, checks the resolved environment and
  Playwright driver bytes, and clips transport timeouts to the remaining
  deadline. The permitted rereview of that state returned FIX because the real
  CLI omitted derived model aliases, a drip-fed urllib response could exceed
  the lifecycle, verifier calls were not bound to one Page object, and the
  adapter kept a second post-hoc clock. The additional correction derives both
  aliases from the one configured model ID, bounds connect plus complete read
  with the lifecycle remainder, retains and rechecks the reset-time Page through
  steps and both verifier calls, and removes the adapter timer. Twenty-one
  focused WARC tests, 67 evaluator tests, and the 79-test loop E2E/CLI suite
  pass. Final resumed GPT-5.6 Sol medium correctness session
  `019f6a8c-ecc7-79c1-9fe3-d0eec9e97ad0` returned CLEAN, confirming the
  full-response deadline and timer restoration, retained reset-time Page, real
  CLI alias/operator traversal, removal of the adapter clock, and accepted-state
  restriction to accepted benchmark evidence. Final elegance/YAGNI/vision
  session `019f6a8c-ecb0-78e0-8db2-c2eee89f1d0c` returned CLEAN, confirming one
  timing authority, one Page authority, the connected CLI path, and no new
  recovery/scheduler/retry/duplicate framework. Frozen digest
  `fe53a6c0e9ea405c0835e80cd090abefc620bae26a59381fc3bd7ea5583e3bc8`
  is the reviewer-clean software qualification checkpoint; its containing
  milestone-F commit will carry that checkpoint identity. The
  software candidate is a reversible, identity-bound software qualification
  path connected to the normal conductor and D3 materialized-candidate
  activation seam. It is not milestone-F
  completion evidence, benchmark reportability, performance evidence, a live
  qualification, campaign authorization, or a decision on ADR-0003. External
  WACZ, native-verifier, runtime/browser, license/provenance, credential, and
  exact executor inputs remain blockers until owner supplied and verified.

AR-001 through AR-003 and AR-014 through AR-016 are complete as software
readiness packages; the reviewer-clean Milestone-E checkpoint remains
uncommitted. The other
AR-004 through AR-020 packages remain queued. The
active sequence is now governed jointly with
`docs/AUTO_RESEARCH_READINESS_EXECUTION.md`: milestone C is complete through
code commit `9d0a7ab`, evidence commit `ef0da6b`, and the successful full
portable-archive proof from that clean evidence commit. The minimal required ADR
transition was proposed at `544750b` and accepted as ADR-0018 on 2026-07-15 by
the owner-delegated coordinator acting under the founder's delegated
architecture-decision authority: `Accept ADR-0018 as written.` D3 is committed
at `9d6b39c`; milestone F is committed at `7c245e5`; and the Milestone-E
candidate recorded above is active. No D/E/F implementation was included in
the proposal or acceptance slice itself. Remaining queued packages are pulled
only when their dependencies and review boundaries align; this ordering does
not skip or silently supersede them.

## Required work deferred by real dependencies

These are not rejected. Implementing pretend versions would make the factory
less trustworthy, so they start only when their dependency is real.

| ID | State | Work | Why deferred / activation condition |
|---|---|---|---|
| EXT-001 | blocked-external | Pin, deploy, reset, and bridge all five benchmark sources | FOUND-003. Requires upstream runtime assets, credentials/access, native verifiers, and observable reset state. Start source-by-source when an environment is actually available. |
| EXT-002 | decision-required | Accept the first browser baseline and build the minimal seed | FOUND-005 and ADR-0003. Complete the required research and obtain the owner's explicit decision before treating any backend as the accepted baseline. ADR-0018's reversible WARC `online.4` / BrowserGym / Playwright qualification work is separate, keeps ADR-0003 Open, and does not complete EXT-002. |
| EXT-003 | blocked-external | Create a private disjoint holdout | FOUND-004; CONV-013. Requires a genuinely private source and owner-controlled commitment; moving public tasks is not a holdout. |
| EXT-004 | blocked-by-EXT-001/002 | Calibrate all 140, filter/freeze suites, and source Batch 2 | FOUND-006/010. Requires real resets, admitted verifiers, a reference protocol, and the exact cheap-executor seed. |
| EXT-005 | blocked-by-real-traces | Calibrate real Analyst/T2 roles | CONV-011/012. Code identity/routing comes first; statistical trust requires held-back real trace corpora. |
| EXT-006 | blocked-by-real-smoke | Measure capacity, cost, retention, and exact-seed noise | FOUND-011. Values must come from five-source smoke and frozen iteration identity, not constants invented in code. |

## Deliberately not implementing now

- A general compound/multi-component acceptance exception (CONV-014). The
  one-component causal rule protects attribution. Add only a bounded staged
  mechanism if real experiments demonstrate a specific irreducible dependency.
- Automatic regression promotion. Keep promotion owner-controlled until real
  verifier, flake, and repeat evidence establishes safe thresholds.
- A distributed transaction system, database platform, broad observability
  stack, or cloud scheduler. The accepted scope is a single-host factory; a
  small journal, filesystem locks, receipts, and direct health checks suffice.
- Live-site authorization machinery beyond the hard deny in AR-008. ADR-0006
  remains open, so the only correct current behavior is prevention.

## Completion definition

The code-only queue is complete when AR-001 through AR-020 have independent
review sign-off and the full repository verification is green. That still does
not authorize auto-research. Activation additionally requires the EXT work,
the real injection/fault rehearsal, and the project owner's explicit start.
