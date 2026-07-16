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
| AR-004 | software-complete on founder fast path; external identities pending | Symmetric run integrity and complete run identity | CONV-002; CONV-009; OPS-012 | The D1/E/F path binds symmetric admitted run identities and the accepted/candidate apparatus. Real browser/runtime/model identities remain owner-supplied activation inputs. |
| AR-005 | software-complete in D3/F offline path; external activation pending | Candidate activation and executed-tree binding | CONV-001; OPS-003 | Immutable D2/D3 materialization and conductor-observed harness/WARC-seam activation are exercised offline. No real browser or external WARC activation is claimed. |
| AR-006 | software-complete in D2/D3 | Exact causal commit and component-diff enforcement | CONV-007; CONV-008; OPS-001 | The trusted Git boundary enforces one exact causal commit, frozen component surface, and conductor-resolved evidence relationships. |
| AR-007 | software-complete in D2 | Trusted Git import boundary | OPS-001 | The conductor imports and validates the standalone bundle into owner-controlled Git without exposing common Git administration to the optimizer. |
| AR-008 | founder-fast-path deferred; external confinement proof pending | Candidate sandbox and hard live-site deny | OPS-002; OPS-005 | Offline/live prevention remains fail closed. Distinct conductor/optimizer UIDs, inbox ownership, and live confinement must be proved during owner-supplied activation; no broader sandbox framework is claimed. |
| AR-009 | software-complete admission path; external verifier admission pending | Verifier bundle identity, admission, and revocation | FOUND-007; CONV-004 | F implements closed verifier identity/checksum/admission and revocation checks. A real native verifier and successful admission remain external inputs. |
| AR-010 | software-complete for the single-campaign fast path; multi-source leases deferred | Safe store namespace, permissions, and locks | FOUND-008; OPS-007; OPS-008 | Safe campaign storage and one existing campaign/materialization lock protect the bounded path. Multi-source scheduling and environment leases are outside this slice. |
| AR-011 | software-complete in D3/G-I | Journaled exactly-once iteration recovery | OPS-006 | The one D3 publication intent/receipt plus existing repeated-arm/run directories and ref CAS recover accepted and non-advancing terminal outcomes without a second journal. |
| AR-012 | software-complete in committed G-I (`ec197f7`) | Preventative lifecycle driver and operator health | OPS-009; OPS-010; OPS-013 | Persisted foreground run/resume/pause/stop, closed budgets/deadline, cleanup health, and fail-closed status are complete for one campaign. |
| AR-013 | software-complete in committed E; real transfer evidence pending | Identity-bound transfer and failed-transfer pause | CONV-013; OPS-011 | E binds and evaluates the closed scheduled-transfer input. A real calibrated transfer result remains an activation input. |
| AR-014 | software-complete in committed E (`527fbdb`) | Inconclusive outcomes and indivisible attribution | CONV-006; CONV-015 | Infrastructure invalidity is behaviorally inert and partial candidates never advance wholesale. |
| AR-015 | software-complete in committed E (`527fbdb`) | Repeated paired statistical acceptance | FOUND-006; CONV-003 | The frozen four-valued repeated protocol is implemented; its values are not claimed calibrated for a real source. |
| AR-016 | software-complete in committed E (`527fbdb`) | Durable regression and champion protection | CONV-010 | Durable regression, champion, and scheduled-transfer protections are implemented; real evidence remains pending. |
| AR-017 | fast-path LearningRecord software-complete; real Analyst calibration deferred | Event-addressable Analyst, clusters, and learnings | CONV-011 | G-I requires one strict trace-cited LearningRecord before the next packet. Analyst remains `stub-0`; calibrated causal diagnosis waits for real retained traces. |
| AR-018 | founder-fast-path deferred | Judge trust identity and quarantine routing | CONV-012 | Existing T1/quarantine behavior is preserved. No T2 council or calibrated judge-trust corpus is implemented or claimed. |
| AR-019 | founder-fast-path deferred; source expansion pending | Source-aware scheduling and auditable task dispositions | FOUND-008; FOUND-010 | The fast path intentionally qualifies one WARC seam for one foreground campaign. All-five-source scheduling, leases, and all-140 execution follow external activation. |
| AR-020 | software-complete in committed G-I (`ec197f7`) | Generated commands, status prose, and decision metadata | FOUND-009; FOUND-012; CONV-016; OPS-014 | Packets, status, and the executable operator documentation use the real offline workflow and preserve the activation/reportability boundary. |

## Current readiness execution order

### Final milestones G-I vertical-slice closeout

- **Frozen starting state:** exact clean HEAD
  `527fbdb1a197f39bcd89340e963256129e78a12c` on
  `codex/auto-research-readiness`.
- **Final writer:** GPT-5.6 Sol medium session
  `019f6af4-71be-7f20-bb31-6ea2aa227cd0` was the sole writable implementer.
  That local writer has ended; no implementation or review agent remains active
  after this closeout, and no overlapping editor exists.
- **Exact ownership:** the final minimal milestones G-I foreground,
  single-campaign vertical slice only: persisted lifecycle requests/state,
  closed iteration/attempt and wall-clock limits, reconciliation/status over
  the existing pending-iteration and accepted-publication transaction, one
  strict trace-cited LearningRecord consumed by the next packet, concise
  operator documentation, and deterministic offline/adversarial proof at the
  existing D3/F/E seams.
- **Explicit exclusions:** no daemon, service manager, worker queue, scheduler,
  database, second journal/recovery path, registry/plugin framework,
  multi-campaign concurrency, live source/browser/model/campaign, asset fetch,
  credential read, external spend, or performance/reportability claim.
- **State:** reviewer-clean, full-gate-green software is committed exactly at
  `ec197f72997e957f5c3c8a731c6cb87487a5296f`. Correctness reviewer session
  `019f6b2e-a93f-7c63-8907-e147c3f4dbec` returned FIX on three retained-
  integrity defects and, on the targeted corrected state, identified one
  remaining real P1: terminal validation conflated retained-artifact integrity
  with current campaign reconciliation. Final elegance/YAGNI/vision reviewer
  session `019f6b2e-a9b4-7293-b6ad-96efc0fd2365` subsequently returned FIX on
  one permissive, independently decoded CLI ledger summary. Those intermediate
  findings are retained below as correction history and are superseded by the
  final CLEAN reviews recorded in this closeout. The existing campaign lock,
  pending iteration, D3 publication intent/receipt, repeated-arm directories,
  and WARC cleanup remain the only execution/recovery authorities. The new
  foreground commands persist `run`/`pause`/`stop`, require owner-chosen closed
  iteration/attempt/deadline limits, meter each logical attempt once across
  interruption replay, expose state/ref/publication/WARC/limit/cleanup health,
  and block production when exact authorization or external metering is absent.
  One canonical JSONL LearningRecord per terminal iteration binds the exact
  campaign/base/candidate/protocol/decision/source disposition and rehashed
  retained gate/trace/artifact citations; the next packet refuses missing or
  invalid learning. Simulation records remain explicitly non-reportable.
- **P1 correction:** the two independent reviews found four unique P1s. The
  sole D3 publication intent/receipt now seals and idempotently reconciles
  accepted and every non-advancing terminal outcome, including pivot and
  cleanup replay; lifecycle requests acquire the existing campaign lock and
  reload before saving; status and CLI routing use the conductor's canonical
  publication loader; and LearningRecord source disposition contains only
  source/execution facts, with invalid benchmark outcomes restricted to their
  trusted gate citation and canonical non-reportable decision. No second
  journal, recovery family, lock, scheduler, supervisor, or status schema was
  added.
- **Targeted rereview correction:** every CLI `run` and `resume` now persists
  its request and selects start versus reconciliation from campaign state
  reloaded under the existing lock; `run` cannot clear pause/stop while
  `resume` can. Canonical read-only publication status now rejects a terminal
  receipt whose retained ledger row or required LearningRecord is missing,
  duplicated, or inconsistent. Learning execution disposition is derived from
  conductor-retained gate run identity, never trace-file presence; an invalid
  mocked benchmark result without that fact is gate-only with `executed=false`.
  This is a narrow correction inside the existing lifecycle, publication, and
  LearningRecord authorities; no new journal, decoder, registry, or flag was
  added.
- **Final targeted correction:** the conductor's canonical terminal validator
  now layers immutable receipt/gate/snapshot/ledger/LearningRecord integrity
  separately from current campaign-state/ref checks. Status and direct
  `continue_campaign` routing always validate the retained artifacts, including
  for historical iteration N while N+1 is pending; only cleanup reconciliation
  of the current terminal receipt applies state/ref checks. A healthy historical
  receipt remains healthy, while removed, duplicated, or corrupted historical
  ledger/learning evidence blocks both `run` and `resume`. This reuses the same
  loader, D3 receipt, lock, and cleanup/recovery functions. At that intermediate
  checkpoint, targeted correctness rereview had not yet occurred.
- **Terminal-history rereview correction:** correctness reviewer session
  `019f6b2e-a93f-7c63-8907-e147c3f4dbec` found one remaining P1 in the
  historical layer: retained ledger and manifest bytes were not checked against
  every cross-artifact relationship enforced while the intent was pending. One
  shared pending/terminal evidence-graph validator now enforces the closed
  `LEDGER_ROW_FIELDS` shape; receipt/build/protocol/decision/advancement
  identity; gate rungs, comparison, attribution, eligibility, and promotions;
  frozen fixed variables; LearningRecord manifest identity; and the canonical
  normal or rejected manifest-snapshot shape and applicable relationships.
  Representative non-receipt ledger-field, extra-field, and manifest-snapshot
  corruption now makes historical status malformed and blocks locked `run` or
  `resume`. Historical/current layering and the sole D3 recovery authority are
  unchanged. At that intermediate checkpoint, final rereview had not occurred.
- **Reserved loop-gate correction:** the orchestrator's reserved source-tree
  loop discovery exposed one P1 regression after the shared validator landed:
  `test_committed_forbidden_edit_rejected` raised infrastructure invalidity
  instead of completing its canonical non-advancing rejection. The shared
  validator now distinguishes an admissible normal snapshot from the existing
  canonical `rejected_submission` evidence produced for a trusted E0
  diff/manifest rejection. Exact nonempty validation errors are derived from
  and checked against the retained gate rung; original submission, verdict,
  closed snapshot, ledger, LearningRecord, protocol, and receipt relationships
  remain fail closed. The focused failing test plus five terminal-history/
  routing/recovery tests pass, and complete loop discovery now runs 218 tests
  with 217 passing and the one existing optional `jsonschema` skip. The
  orchestrator-reported eval/WARC 68/68 and judge 28/28 passes were not rerun.
  At that intermediate checkpoint, targeted rereview and the reserved full-gate
  rerun had not occurred.
- **Forbidden-rejection rereview correction:** correctness reviewer session
  `019f6b2e-a93f-7c63-8907-e147c3f4dbec` found two remaining evidence-binding
  P1s: rejected `original_submission` was self-authenticating, and rejection
  errors were not closed to the immediate conductor-owned E0 failure. The sole
  publication schema is now `0.4.0` under digest domain v3 and carries one
  sealed `manifest_snapshot_digest` from pending intent through terminal
  receipt; retained normal and rejected snapshots must match it exactly. The
  one construction/validation helper now accepts only an immediate sole
  `E0`/`fail` with either exact nonempty string `manifest_errors` or the exact
  closed false `GuardReport` shape with typed lists and a real violation/dirty
  entry. Malformed, mixed, partial, extra, later-rung, and unrelated failures
  cannot mint `rejected_submission`. No sidecar, migration, second intent,
  registry, or compatibility path was added. Nine focused rejection/status/
  replay/history tests pass. The first complete loop run exposed only one stale
  closed-shape test assertion for the new terminal field; its focused rerun
  passed, and the final complete discovery ran 219 tests with 218 passing and
  the existing optional skip. At that intermediate checkpoint, targeted
  rereview and remaining full gates had not occurred.
- **Final elegance correction:** one exact closed ledger-row authority now
  lives in `opti_loop.ledger`. Its canonical reader uses duplicate-key-safe
  strict JSON for every physical record and reports physical row numbers for
  malformed, non-object, missing-field, and extra-field records. Conductor
  publication validation and idempotent ledger persistence, next-packet
  consumption, and CLI status all use that reader. Status performs canonical
  operation/publication projection first; an invalid ledger adds a clear
  blocker and omits `ledger_rows` and `last` instead of crashing or presenting
  a normalized summary. Seven focused ledger/status/packet/terminal tests pass,
  and complete loop discovery runs 221 tests with 220 passing and the existing
  optional `jsonschema` skip. No new decoder, status shape, or ledger authority
  was added. At that intermediate checkpoint, final targeted reviews and
  reserved gates had not occurred.
- **Final ledger-framing correction:** correctness reviewer session
  `019f6b2e-a93f-7c63-8907-e147c3f4dbec` returned FIX on one remaining strict-
  framing P1: the shared reader skipped blank records and used Unicode-aware
  `splitlines()`. It now preserves raw newlines and uses the existing strict LF
  JSONL splitter. A missing or exactly empty pre-iteration ledger remains
  valid; LF, CRLF, and no final delimiter are accepted, while blank or
  whitespace records, an extra trailing delimiter, raw CR, and U+2028/U+2029
  record separators fail with physical record/row diagnostics. Four focused
  ledger/status/packet tests and complete loop discovery (220 passed plus the
  existing optional skip) are green. The contemporaneous elegance rereview was
  CLEAN; final framing correctness/elegance review followed later. LearningRecord
  framing and every publication/packet/status consumer are unchanged.
- **Final independent reviews:** final framing correctness session
  `019f6b2e-a93f-7c63-8907-e147c3f4dbec` returned CLEAN with no findings on
  full dirty digest
  `ee5ca8c64fe951a51e836458388f2717a5eca1e35860081ab99f7615a92545e4`.
  Final framing elegance/YAGNI/vision session
  `019f6b2e-a9b4-7293-b6ad-96efc0fd2365` also returned CLEAN with no findings
  on that exact digest. These final results supersede the intermediate review
  conclusions without erasing their correction history. No software task
  remains in the authorized founder fast-path slice.
- **Final current-byte evidence:** source eval/WARC passes 68/68; source judge
  passes 28/28; source loop runs 221 tests with 220 passing and the one existing
  optional `jsonschema` skip. Catalog validation passes 140 catalog/primary,
  smoke/regression 20/20, and source counts 30/30/30/30/20. The cached offline
  schema audit passes 531 documents with zero errors. Documentation passes 86
  Markdown files, 176 local links, 18 ADRs, and 140 raw, normalized, and by-ID
  tasks. Repository completeness passes 55 required files plus package,
  catalog, and Git checks. The 394-file manifest, changed-Python Ruff, Python
  compilation, and `git diff --check` pass.
- **Clean-install evidence:** a working-tree copy passes under Python 3.14.5
  and uv 0.11.6: exactly three pure-Python wheels; offline/no-index installation
  of `opti-loop==0.1.0` and the exact eval/judge/loop dependency graph; the
  missing-judge negative control; installed CLI help, eval validation, cwd
  discovery, and pure transfer checks; and all three installed suites. It ran
  no live backend and records `benchmark_evidence=false`.
- **Offline evidence history:** corrected complete loop discovery ran 221 tests with
  220 passing
  and the existing optional `jsonschema` skip; the focused WARC evaluator suite
  remains at its prior 21-test pass. The latest six focused regressions cover
  locked stale-running/concurrent-pending routing, run-versus-resume owner
  requests, malformed structural and retained-artifact receipt routing, valid
  trusted execution disposition, and invalid benchmark gate-only learning.
  Earlier focused P1 regressions continue to cover ordinary and pivot terminal
  failpoint replay and cleanup retry. The final targeted pass ran only five
  terminal status/routing/recovery tests; all five passed after the terminal-
  history correction, covering healthy and corrupted historical receipts,
  closed/full ledger and snapshot relationships, plus current accepted/non-
  accepted cleanup.
  Targeted Ruff, Python compilation, `git diff --check`, repository
  completeness, and documentation checks pass. One exploratory repo-wide Ruff
  invocation found six pre-existing style findings outside the changed
  surfaces; repo-wide Ruff is not a defined repository gate and is not an
  activation/readiness blocker. The standalone WARC
  command was first invoked without `OPTI_BROWSER_REPO_ROOT` and produced 21
  setup-only `KeyError`s; the corrected required invocation passed all 21.
  No complete repository or clean-install gate was run, per the handoff scope.
- **Activation boundary:** no live source/browser/model/campaign, external
  asset, credential value, or paid request was accessed. External WACZ,
  verifier/admission, provenance/license/checksums, pinned runtime/browser,
  two-UID confinement/inbox, calibrated protocol/transfer evidence, approved
  spend meter, credentials where required, and explicit campaign authorization
  remain honest blockers.

### Sentinel missing-publication readiness correction

- **Final state:** this correction and its later readiness fixes are included in
  implementation commit `04ca532b078d31a1ad0959c7bcf94302e7362abb` by writer
  session `019f6bf0-e541-7952-9cb2-4aa547786a35`. Correctness reviewer session
  `019f6bf7-deca-79a0-96b1-57c1df08e0b6` and elegance/YAGNI/vision reviewer
  session `019f6bf7-df19-7070-b594-7c421a0e956c` both returned CLEAN on frozen
  production/test digest
  `f53db249a45600168a45392efdd800cdb209dbf799798125f705b98ab05f2d75`.
  The complete gate and external-boundary evidence is recorded in the final
  checkpoint below.

### Sentinel readiness defects final review checkpoint

- **Writer/base/review state:** writer session
  `019f6bf0-e541-7952-9cb2-4aa547786a35` produced exact implementation commit
  `04ca532b078d31a1ad0959c7bcf94302e7362abb`. Frozen implementation/test digest
  `f53db249a45600168a45392efdd800cdb209dbf799798125f705b98ab05f2d75`
  received final CLEAN from correctness reviewer session
  `019f6bf7-deca-79a0-96b1-57c1df08e0b6` and elegance/YAGNI/vision reviewer
  session `019f6bf7-df19-7070-b594-7c421a0e956c`.
- **Exact implementation:** baseline and regression preparation precede the one
  campaign save that publishes equal current/pending iteration N; in-suite
  reloads observe only the healthy prior publication. The canonical evaluation
  identity validator now directly governs WARC nested repeated-protocol
  preflight, while shared required-field definitions drive recursive production
  template drift checks. Root and loop-harness rehearsal initialization both
  carry the three required limits and execute through the dependency-complete
  eval/judge/loop package path. The sole publication record, rollback/recovery,
  retained receipt checks, and deletion fail-close are preserved. The existing
  start rollback now spans distillation, packet creation, delayed register
  persistence, and the final paired-iteration state save; packet, register, and
  state-save faults restore prior state/register bytes, remove iteration
  artifacts/worktrees, preserve the prior publication, and retry the same
  iteration. Rollback now durably restores `state_before` immediately under the
  campaign lock before any fallible cluster/artifact/worktree cleanup. A
  combined state-write and later-cleanup fault retains prior current/pending
  numbering and publication projection, then makes the next route fail closed.
  The unused `Campaign.open_iteration()` early-save authority is deleted; no
  journal or recovery path was added.
- **Final orchestrator evidence:** full eval passes 70/70; judge passes 28/28;
  loop ran 227 tests: 226 passed and one documented optional `jsonschema` test
  skipped. Catalog validation passes 140
  candidates and 140 catalog tasks, with primary 140, smoke 20, and regression
  20. Schema validation passes 531 documents, including the 180-case experiment
  corpus and 195-case evidence corpus. Documentation passes 86 Markdown files
  and 177 links; repository completeness passes 55 required files; the file
  manifest verifies 395 entries. Changed-surface Ruff, `py_compile`, and
  `git diff --check` pass.
- **Clean-install evidence:** normal `scripts/verify_clean_install.py` passes
  with Python 3.14.5 and uv 0.11.6: three wheels, offline/no-index resolution,
  negative control, CLIs, and all suites. The same proof under `unshare -Urn`
  also passes. Neither proof used a live backend, and both retain
  `benchmark_evidence=false`.
- **Honest boundary/blockers:** no live operation, external spend, merge, push,
  performance, or reportability claim occurred. `benchmark_reportable=false`
  remains the boundary. Remaining external activation inputs are owner-supplied
  WACZ and checksum with provenance and license; native verifier executable
  identity/checksum and positive admission; exact BrowserGym, Playwright,
  browser/runtime, and model-transport identities; credentials only if the
  selected source requires them; optimizer UID, inbox, and runtime confinement;
  real reset/final-state/trace/artifact evidence; calibration, transfer, and
  holdout evidence; metering and owner decisions; and explicit campaign
  authorization.

### Final bounded Sentinel correction — committed and reviewer-clean

- **Writer/commit/review state:** sole implementation writer session
  `019f6c34-7664-7a33-95f0-2a8a182b0ed2` produced the final correction committed
  at exact commit `10831715041b455357d36fcc90cb9f33254b1bc3`. On unchanged
  reviewed production/test slice digest
  `1bc3486a052696692146df98cdded2203f218a515f44d7409262312770df154b`,
  correctness session `019f6c3d-06ab-7a72-9810-a6f71e722088` returned CLEAN
  after actively running all five focused regressions and independently
  matching all 44 closed WARC dictionary objects plus rejecting all five
  representative deletions. Elegance/YAGNI/vision session
  `019f6c3d-06c3-7bd2-a35e-b43b1e8ab459` returned CLEAN with no new recovery
  or configuration machinery; its read-only sandbox prevented temp-backed
  tests, while the correctness review supplied the dynamic reproduction.
- **Exact correction:** the existing start-preparation rollback catches
  `BaseException` only at that transaction, restores durable trusted state
  first, then restores cluster bytes and removes iteration/worktree artifacts.
  Cleanup failures persist their exact detail through the existing
  `cleanup_health` authority before re-raise. Separate regressions interrupt
  the first baseline `run_suite` through its real evaluation path during fresh
  iteration 1 and during iteration 2 after a normal terminal rejection of
  iteration 1. They prove exact trusted-state/register restoration, preservation
  of the complete iteration-1 publication, cleanup health/status, and
  same-number retry. The WARC production template now has one recursively
  complete closed-object key shape comparison derived from the
  preflight-validated fixture, including representative required nested leaf
  deletions. No recovery framework, schema/registry/generator, compatibility
  layer, or second authority was added.
- **Focused evidence:** the two genuine iteration-level interruption tests,
  combined state-write plus cleanup-failure blocker, existing
  packet/register/state rollback, and recursive WARC template behavior pass in
  one focused 5-test invocation and were actively reproduced by correctness.
- **Final current-candidate orchestrator evidence:** eval ran 70 and passed 70;
  judge ran 28 and passed 28; loop ran 229, passed 228, and recorded one
  documented optional `jsonschema` skip. Catalog validation passed 140
  candidates and 140 catalog tasks, with primary 140, smoke 20, and regression
  20. Schema validation passed 531 documents, including experiment 180 and
  evidence 195. Documentation passed 86 Markdown files and 177 links;
  completeness passed 55 required files; the manifest passed 395 files; Ruff,
  `py_compile`, and `git diff --check` passed. Normal clean install and
  `unshare -Urn` clean install both passed with Python 3.14.5 and uv 0.11.6:
  three wheels, offline no-index resolution, negative dependency control,
  installed CLIs, and all installed suites. Neither clean-install proof used a
  live backend, and both retained `benchmark_evidence=false`.
- **Honest boundary:** no live source, browser, model, campaign, credential,
  external asset, paid request, external budget, merge, or push was used.
  Evidence is offline fixture plumbing only and is not benchmark reportable.
  Existing external activation and explicit authorization blockers remain
  unchanged.

### Committed milestone-E software checkpoint

- **Frozen starting state:** reviewer-clean milestone F is committed at
  `7c245e5402d03563f3ec98e067c612963c0a7725`.
- **Commit state:** Milestone E is committed at
  `527fbdb1a197f39bcd89340e963256129e78a12c`; its implementation/review agents
  are no longer active.
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
  one existing optional skip. This is committed reviewer-clean software,
  not a performance or reportability claim. No calibrated real evidence,
  closed external transfer evidence, live WARC assets/runtime/credentials,
  verifier admission, or campaign authorization exists; external operation
  still depends on owner-supplied activation inputs.

### Committed milestone-F qualification slice

- **Frozen starting state:** D3 is committed at
  `9d6b39c361b1c7c9616884a055f59eaa5ce571fd` (`9d6b39c`), and the milestone-F
  worktree was clean before this ledger update.
- **Writer state:** session `019f6a00-be3a-7220-b4df-8b22c6da3f0c` was the sole
  bounded milestone-F writer; it is no longer active.
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

The founder-authorized D3/F/E/G-I software fast path is committed and
offline-ready through exact G-I checkpoint
`ec197f72997e957f5c3c8a731c6cb87487a5296f`. The AR table above distinguishes
software-complete behavior from external qualification/evidence and
founder-fast-path deferrals; it does not silently complete T2, all-five-source
scheduling, private holdout, live confinement, or real calibration. The durable
sequence is governed jointly with
`docs/AUTO_RESEARCH_READINESS_EXECUTION.md`: milestone C is complete through
code commit `9d0a7ab`, evidence commit `ef0da6b`, and the successful full
portable-archive proof from that clean evidence commit. The minimal required ADR
transition was proposed at `544750b` and accepted as ADR-0018 on 2026-07-15 by
the owner-delegated coordinator acting under the founder's delegated
architecture-decision authority: `Accept ADR-0018 as written.` D3 is committed
at `9d6b39c`; milestone F is committed at `7c245e5`; milestone E is committed
at `527fbdb`; and reviewer-clean, full-gate-green G-I is committed exactly at
`ec197f72997e957f5c3c8a731c6cb87487a5296f`. Real browser/source qualification,
reportability, calibration, external assets, credentials, runtime identities,
confinement, metering, ADR-0003 decisions where required, and explicit campaign
authorization remain blockers. No D/E/F implementation was included in the
proposal or acceptance slice itself. Deferred work starts only when its real
dependency and authorization exist.

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

The founder-authorized fast-path software checkpoint is complete when its
implemented AR dispositions have independent clean review and the defined
repository gates are green. That condition is met by committed G-I checkpoint
`ec197f72997e957f5c3c8a731c6cb87487a5296f`. Deferred AR/EXT work remains
deferred rather than silently complete and does not block the offline
checkpoint. External activation still requires the exact owner-supplied inputs,
real qualification/calibration evidence, and explicit campaign authorization
recorded in the readiness execution ledger.

### Retained start-worktree rollback correction — uncommitted commit candidate

- **Frozen reviewed state:** base
  `e238113c3d531faaa033d169930533160d9d37b4` plus binary diff
  `14736128d5045bd4432d19b40f3a5dbd8ee01c26ed1c17650f893000984fe50e`.
  Production/test SHA-256 values remain
  `d4c40467053dcdb9f50573f6c1b5cbd1e009f98e11321d6e5e47e3b70d6cf099`
  and `b760af7d1037f918638283efd760aa208e4aca9450a821806539d4254b977a74`.
  Writer was GPT-5.6 Sol medium session
  `019f6c71-e557-79c1-b8ef-d04ead28b6e8`.
- **Implementation slice:** the existing start rollback now verifies that its
  worktree removal left neither a path nor symlink. A retained worktree becomes
  the exact existing cleanup-health failure, so status/preflight blocks and the
  next transition fails closed. The focused regression preserves the real
  `gitutil.worktree_remove` helper while injecting its suppressed nonzero Git
  result; no helper, recovery mechanism, or gitutil change was added.
- **Correctness review:** GPT-5.6 Sol medium session
  `019f6c77-248b-7470-8328-e2786b2c0bbe` returned CLEAN with no findings. It
  actively ran the focused five tests in 5.112s and two adjacent tests in
  0.739s, verifying the real-helper suppressed-nonzero boundary, exact cleanup
  health, status/preflight/transition blockers, successful first/later cleanup,
  and same-number retry.
- **Elegance/YAGNI/vision review:** GPT-5.6 Sol medium session
  `019f6c77-24ec-7da0-a0cc-3ae6998487cd` returned CLEAN with no findings. It
  confirmed the boundary-local postcondition, state-first ordering, existing
  single cleanup authority, retained paths/symlinks, and no new helper,
  journal, configuration, or recovery machinery. Its read-only sandbox could
  not create temporary directories; correctness supplied the dynamic proof.
- **Full candidate gates:** eval 70/70; judge 28/28; loop ran 230, passed 229,
  with one documented optional `jsonschema` skip; catalog 140/140 with primary
  140, smoke 20, and regression 20; schema via `uv run --with jsonschema`
  passed 531 documents, experiment corpus 180, and evidence corpus 195; docs
  passed 86 Markdown files, 177 links, and 18 ADRs; completeness passed 55;
  changed-surface Ruff, `py_compile`, and `git diff --check` passed.
- **Boundary:** this remains an uncommitted commit candidate. Clean-install
  proofs remain pending until an exact implementation commit exists. No final
  docs closeout, live readiness, external activation, reportability, or live
  operation is claimed; the existing external activation blockers remain.
