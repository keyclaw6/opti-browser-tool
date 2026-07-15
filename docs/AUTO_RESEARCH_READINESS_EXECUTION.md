# Auto-research readiness execution

Status: active orchestration ledger. Milestones A/B/C, the pre-D decision
transition, and D1 exact protocol/run identity are complete. D1 is committed at
`e599c46`. The rejected five-file D2a0 attempt was discarded without commit,
is absent from the current tree, and must not be resurrected. Narrow retry
reviews returned clean only for the earlier six D2 correction dispositions.
Original D2 is committed at `e6866e0`. Its later broad-review and follow-up
findings are corrected in final D2 commit `c23d645`.
Final correctness session `019f67df-3022-7a12-9ecf-0a1f47e505d0` and final
elegance/YAGNI/vision session `019f67df-3092-71f3-bc7e-2537cf4530ee` both
returned exactly **CLEAN** for the settled D2 code. The three-file
documentation/evidence closeout is verified.
The overlapping D3 runner was terminated before production or test work, and
its four ledger edits were reversed. D3 is pending restart from a future clean
frozen HEAD; milestone D and Slice A are not complete.
Branch: `codex/auto-research-readiness`. ADR-0018 proposal commit: `544750b`.
This file records implementation direction and evidence; it does not authorize
a live campaign or turn fixture output into benchmark evidence.

## Charter goal and readiness boundary

Build a single-host factory that can repeatedly improve the browser
harness-under-test while holding the evaluation apparatus and the executor's
exact identity/settings fixed within each harness experiment. Every decision
must bind immutable accepted and candidate identities, independently prove
candidate activation, admit complete trace/result/artifact evidence, prefer the
objective verifier, estimate a prespecified repeated treatment effect, protect
regression and transfer populations, preserve trace-linked learning, and advance
accepted state atomically only for `accepted` benchmark evidence.

Readiness means that installation, configuration, safety gates, lifecycle,
offline deterministic verification, preflight, and operator commands are
complete. It does **not** mean that a source has been calibrated, a private
holdout has been fabricated, benchmark performance has been measured, or a
campaign has been authorized. Credentials, external source assets, real
calibration evidence, a genuine private holdout, and explicit owner activation
remain separate inputs.

## Current milestone

| Milestone | State | Exit condition |
|---|---|---|
| **A — reproduce verification and finish AR-003** | **Complete** | AR-003 closed at `72e73c2`; separate correctness and elegance reviewers returned no actionable findings; full verification and the regenerated file inventory/manifests pass. |
| **B — decide the three external reviews** | **Complete** | The matrix below retains, adapts, defers, or rejects each major proposal against current code, charter value, and YAGNI; separate correctness and elegance reviews are clean. |
| **C — clean installability** | **Complete** | Code commit `9d0a7ab` declares the actual package graph; evidence commit `ef0da6b` passes isolated source-to-wheel installation, transitive dependency, negative resolver, installed CLI/test, no-network-namespace, and full portable ZIP/bundle verification. The code and evidence slices have clean independent correctness and elegance/YAGNI reviews. |
| **Pre-D architecture transition** | **Complete; Accepted** | Proposal commit `544750b` passed separate correctness and elegance/YAGNI/vision re-reviews. On 2026-07-15 the owner-delegated coordinator, acting under the founder's delegated architecture-decision authority, approved it exactly: `Accept ADR-0018 as written.` ADR-0018 now binds the minimal repeated-decision, identity/activation, candidate-boundary, indivisible-build, atomic-publication, and reversible WARC/BrowserGym/Playwright qualification transition while ADR-0002/0003 remain Open. |
| **D — exact identity and trusted activation** | **In progress — D2 committed and code-review-clean; D3 pending** | D1 is committed at `e599c46`. Original D2 is committed at `e6866e0`; final review-follow-up correction commit `c23d645` resolves the later broad and follow-up findings. Final correctness session `019f67df-3022-7a12-9ecf-0a1f47e505d0` and final elegance/YAGNI/vision session `019f67df-3092-71f3-bc7e-2537cf4530ee` returned exactly CLEAN for the settled D2 code. The three-file evidence closeout is verified. D3 trusted activation proof remains required, so milestone D and Slice A are not complete. |

Milestones D-I remain ordered as identity/activation; repeated decision and
champion protection; concrete
source/backend readiness; safe single-host lifecycle; trace-backed
learning/operator flow; and final integration/adversarial verification.

### Founder fast path for the remaining work

The remaining readiness work is organized into four vertical slices: **A** is
D2 immutable Git-backed materialization followed by D3 trusted activation;
**B** is milestone E repeated decision and champion protection; **C** is
milestone F concrete source/backend readiness; and **D** is milestones G-I
single-host lifecycle, learning/operator flow, and final integration. Each
checkpoint has one bounded implementation owner and exactly two fresh
independent reviewers: one correctness reviewer and one
elegance/YAGNI/vision reviewer. Focused tests run during editing, one broader
suite runs when a checkpoint becomes a review candidate, and complete
repository gates run once per coherent milestone or final release candidate.
After both reviewers are clean, the checkpoint is committed promptly on this
branch without push or merge.

Every **new** worker must be launched with local
`codex exec -m gpt-5.6-sol -c 'model_reasoning_effort="medium"' -c
'approval_policy="never"' -C <repo>` and one self-contained prompt, plus
`--output-last-message`. Only the sole bounded implementer receives a writable
sandbox; the correctness and elegance/YAGNI/vision reviewers run in parallel
with read-only access. There is no collaboration-spawn fallback: an exact
runner failure stops that assignment and must be reported. The verified D2
evidence closeout is the current frozen checkpoint. No writable implementation
editor is active; D3 is pending restart from a future clean frozen HEAD.

Bounded scope is qualitative, with no LOC or production-file-count target. A
larger direct implementation can be correct and elegant; a smaller one can
still be duplicated, speculative, or disconnected. Each slice must implement
one dependency-correct behavior with one editor, no speculative abstractions or
unused generality, and only the tests and validation required by current
invariants. Diff size may be recorded as neutral transparency, but never as a
budget, target, exception, acceptance rule, or evidence of elegance. No further
D2 hardening, generic filesystem machinery, or size-driven rewrite is allowed
without a concrete current test, accepted ADR, or actionable review finding.
D3 is not part of this checkpoint. D2 code is committed at `c23d645`, both
final targeted re-reviews returned exactly CLEAN, and the three-file evidence
closeout is verified.

## Three-review decision matrix

Review labels: **R1** vision/architecture, **R2** vertical slice/delivery, and
**R3** simplicity/migration. `Adapt` accepts the requirement but not the
review's proposed rewrite or timing.

| Major proposal | Review | Decision | Grounded reason |
|---|---|---|---|
| Preserve immutable accepted/candidate identity, evaluator independence, objective-verifier authority, fail-closed evidence, four outcomes, regression/transfer protection, trace-linked learning, and atomic advancement | R1/R2/R3 | **Keep** | These are charter/constitution invariants. Current typed verdict already makes only `(accepted, benchmark)` state-advancing; subsequent work must complete the missing identities and `inconclusive` behavior without weakening that predicate. |
| Implement architecture transitions from this execution ledger without amending the governing ADRs | R1/R2/R3 | **Reject** | This ledger does not silently amend accepted decisions or resolve open ones. ADR-0018 now supplies the accepted coherent amendment for the repeated E5 decision, candidate-build boundary, and indivisible-build semantics. ADR-0002/0003 remain Open, and any later contradiction still requires the decision process rather than implementation convenience. |
| Finish AR-003 before accepting or collecting reportable evidence | R1/R2/R3 | **Keep** | AR-003 completed at `72e73c2` after clean independent correctness and elegance reviews. Its strict trace closure, final browser state, artifact containment/hash, exact identity, and verifier evidence remain prerequisites for any later reportable path. |
| Replace the five-plane implementation with a new trusted research kernel | R1 | **Reject now** | The authority separation is useful, but a broad rewrite would discard working eval, judge, loop, evidence, gate, quarantine, and conductor code before a concrete integration failure proves that necessary. Treat the planes as trust roles and repair current integration. |
| Consolidate the three packages into one distribution | R1/R3 | **Reject unless audit evidence proves it is simpler** | Before `9d0a7ab`, package manifests incorrectly declared no dependencies and the Makefile supplied them through `PYTHONPATH`; that was a real installability defect. Commit `9d0a7ab` completed the explicit dependency repair and clean-install proof without consolidation. Preserve the package boundaries unless later evidence proves them materially worse. No fourth contracts package is planned. |
| Replace the current run layout with one new canonical bundle and delete `results.jsonl`, summaries, `EvalRun`, and replay checks | R3 | **Reject now** | The present redundancy is validated fail-closed and AR-003 relies on it. A greenfield persistence migration is not required for readiness. New code should avoid creating another authority; simplify existing records only when a demonstrated correctness or recovery problem requires it. |
| Split optimizer proposal from conductor decision and parse untrusted input strictly | R1/R3 | **Adapt** | Ownership separation and strict decoding are correct. Preserve the existing versioned manifest/history where useful, but ensure optimizer input cannot supply trusted activation, attribution, terminal decision, or state transition. Do not build a compatibility framework for non-production fixture records. |
| Broaden `harness/components/**` so the candidate can test the charter's real harness behavior | R1 | **Adapt and implement** | `harness/` currently contains registrations but no executable browser runtime. The frozen candidate allowlist is the sole path authority and may later include concrete harness-runtime surfaces; `harness/infra`, lanes, tasks, setup/reset, verifiers, secrets, evidence admission, safety policy, acceptance code, and the executor's exact model/provider identity/settings remain trusted and immutable. Model comparisons remain separate experiments. `target_component` remains attribution only and cannot narrow or expand the allowlist. |
| Remove the one-component causal rule and fixed taxonomy entirely | R1 | **Reject now** | One hypothesis and a bounded causal change remain valuable safeguards. Broaden only surfaces proven to be harness behavior; add a bounded multi-surface treatment only when a concrete irreducible change needs it. |
| Partially retain or roll back files/components from an evaluated candidate without a new experiment | R1 | **Reject** | Acceptance evidence belongs to the exact tested candidate build as an indivisible treatment. Removing or retaining only a subset creates a different, untested build; that rollback must be proposed as a new candidate and pass the complete identity, activation, evidence, repeated-decision, regression, and transfer protocol. |
| Supersede E0-E5 with a new undifferentiated experiment transaction | R1/R3 | **Reject** | E0-E5 are useful fail-fast checks and scheduling structure, and their substantive containment, activation, smoke, targeted, regression, and full-evaluation roles already work. Keep the ladder, but correct the final decision protocol and transaction/recovery semantics. |
| Replace single-treatment/noise-envelope acceptance with a prespecified repeated paired/interleaved protocol | R1/R2/R3 | **Accept and implement** | Current E5 runs one treatment and can accept luck. The protocol must bind arm order, matched identities, repeats/stopping, missing/invalid handling, estimator/uncertainty, minimum effect, regression/transfer conditions, and multiplicity policy before treatment results. A predicted flip remains a diagnostic causal check, not sufficient evidence by itself. |
| Adopt R2's universal `12` valid pairs, `p <= 0.05`, and `>= 0.25` effect as permanent thresholds | R2 | **Defer numeric selection; keep as a candidate first-source protocol** | ADR-0005 requires thresholds from measured real variance. Deterministic simulations can exercise an exact paired protocol, but fixture behavior must not calibrate production thresholds. The configured protocol must fail preflight until real identity-bound values are supplied. |
| Add explicit `inconclusive` and keep invalid evidence behaviorally inert | R1/R2/R3 | **Accept and implement** | `Verdict` currently exposes only accepted/rejected/invalid although the charter and manifest name four outcomes. Valid but insufficient evidence is not rejection; infrastructure/integrity failure is not behavioral evidence and must not consume promotion evidence. |
| Make observed activation a trusted dynamic fact rather than optimizer-authored prose or E1 `pending` | R1/R2/R3 | **Accept and implement** | E1 currently passes static registration while recording dynamic audit as pending. Treatment evidence must bind the executed candidate/build/component digest and cited trace events; a missing, baseline-present, or wrong-build activation proof makes the experiment invalid. No generic instrumentation plugin system is needed. |
| Retain T0/T1, verifier admission, quarantine, and no-score-override behavior; remove the generalized quarantine/admission state | R1/R3 | **Keep current machinery; defer only uncalibrated T2 use** | Existing evidence, T1, quarantine, and verifier code closes real evaluator-disagreement paths and has adversarial coverage. Do not delete it for conceptual neatness. Simplify only if concrete source integration exposes a correctness or operability cost. No LLM judge becomes trusted before identity-bound real-corpus calibration. |
| Simplify trace/event/schema rules and shrink the cross-surface adversarial corpus | R1/R3 | **Reject now** | Exact framing, identity, ordering, terminal verifier, final-state adjacency, visibility, containment, and digest rules protect decisions and are the point of AR-003. Source-specific extensions may be added, but no guarantee is relaxed merely because a smaller greenfield envelope is imaginable. Delete tests only after replacement coverage proves the same invariant. |
| Use SQLite or another database as the accepted-state transaction boundary | R1 | **Reject** | The current single-host scope does not justify a new database. Extend the existing owner-controlled filesystem store with safe paths, permissions, locks, staging, receipts/journal, and atomic compare-and-swap advancement only as needed for recoverable operation. |
| Build one thin source-native reportable adapter rather than making the generic command adapter reportable | R1/R2 | **Accept and implement** | `CommandAdapter` and `RegistryAdapter` are deliberately non-reportable and should remain so. One concrete adapter must own reset, exact task/source/runtime identity, constrained harness execution, final-state capture, native verification, evidence return, and actionable credential/asset preflight. |
| Prefer WARC-Bench `online.4` with BrowserGym/Playwright as a reversible first bring-up path | R2 | **Accept as the preferred readiness target, not a settled backend ADR** | The catalog already pins `online.4`, its source commit, WACZ path, and a native JavaScript verifier expectation. It is a smaller, credential-light seam than the stateful sources and its goal/verifier align better than the reviewed `online.51`. Accepted ADR-0018 records only this reversible readiness qualification while leaving ADR-0003's final backend selection open. Implement config/preflight and offline local tests; do not fetch assets, run a real task, claim reportability, or silently mark ADR-0003 accepted. |
| Adopt external framework capabilities selectively | R1/R2 | **Accept** | Reuse BrowserGym/WARC or other proven source/runtime capabilities when they delete custom work and preserve source-native reset/verifier semantics. Do not add a universal browser framework, registry, or adapter-to-adapter layer before the concrete seam requires it. |
| Run one real supervised vertical slice now | R2 | **Reject as an action; accept its qualification contract** | Current authority forbids live campaigns, platform access, external budget, and performance claims. Implement the same identity, reset, verifier, activation, evidence, and repeated-decision checks against deterministic local fixtures; leave precise preflight blockers for later owner-supplied assets/credentials and authorization. |
| Delay Git import, candidate isolation, lifecycle, recovery, locks, status, and operator commands until after supervised real cycles | R2/R3 | **Reject for readiness; adapt scope** | The requested deliverable is an operation-ready auto factory, so minimal single-host import/isolation, recoverable interruption, budgets/deadlines, locking, status, and executable operator documentation are required before handoff. Do not build distributed scheduling, services, broad observability, or multi-campaign machinery. |
| Keep visual-first and terminal/CLI as the constitutional lanes; treat structured interaction as a modality | R1 | **Accept, staged** | Preserve the constitutional lane distinction in identities/configuration. The first concrete adapter may qualify one lane; do not invent a hybrid/router or require both external runtimes for offline software readiness. |
| Defer all-five-source bridges, execution/calibration of all 140 candidates, Batch 2, private-holdout contents, parallel campaigns, distributed scheduling, and automatic regression promotion | R1/R2/R3 | **Defer, not supersede** | ADR-0014 remains binding: once the real source assets, admitted verifiers, and exact executor/runtime inputs exist, all 140 candidates must run before any filtering. Staged asset, launch, reset, oracle, and verifier preflight may precede those runs and record invalid dispositions, but it may not silently filter the pool or replace ADR-0014. The remaining items require real variance, measured gaps, secrecy, or demonstrated concurrency; prepare fail-closed contracts without fabricating evidence. Owner-controlled regression promotion remains appropriate until real repeated evidence defines safe policy. |
| Omit generated commands/status/documentation until a real run stabilizes | R2 | **Reject; implement minimal operator surfaces** | Readiness requires exact missing-input diagnostics and safe start/status/resume instructions. Implement direct commands and executable docs, not a command-generation framework or polished observability platform. |
| Use staging plus atomic publication and minimal journal/receipt recovery | R3 | **Accept and implement in the existing filesystem design** | Interrupted work must not become evidence and accepted state must not outrun its decision receipt. This supplies the needed single-host recovery without SQLite, distributed transactions, or a generic workflow engine. |

## Current orchestration roster

| Agent | Status | Bounded ownership |
|---|---|---|
| `/root` | Active coordinator; D2 evidence closeout verified | Owns closeout commit sequencing and the clean D3 restart; no production, test, D3, E, or F implementation in this pass. |
| Overlapping D3 runner | Terminated before production or test work | Its four ledger edits were reversed; D3 is inactive and pending restart from a future clean frozen HEAD. |
| `019f67df-3022-7a12-9ecf-0a1f47e505d0` | Complete; final D2 follow-up correctness re-review **CLEAN** | Local GPT-5.6 Sol medium, read-only re-review after all three follow-up findings were corrected. |
| `019f67df-3092-71f3-bc7e-2537cf4530ee` | Complete; final D2 follow-up elegance/YAGNI/vision re-review **CLEAN** | Local GPT-5.6 Sol medium, read-only qualitative re-review after all three follow-up findings were corrected. |
| `019f67df-1563-7711-a839-aa3105d85999` | Complete; superseded D2 follow-up correctness finding pass | Reported the allowlist/digest and unsafe-ancestor findings; its result was superseded by correction and final session `019f67df-3022-7a12-9ecf-0a1f47e505d0`. |
| `019f67df-15b0-7832-b8a8-0590777cef3a` | Complete; superseded D2 follow-up elegance/YAGNI/vision finding pass | Reported the canonical-publication binding finding; its result was superseded by correction and final session `019f67df-3092-71f3-bc7e-2537cf4530ee`. |
| `019f67c9-753d-7ed2-8f9b-a9db72a8c418` | Complete; narrow D2 correctness retry CLEAN | Local GPT-5.6 Sol medium, read-only retry limited to the earlier six correction dispositions; it did not review the three later broad findings or their corrections. |
| `019f67c9-7589-7212-aaaa-6a0b8b11b392` | Complete; narrow D2 elegance/YAGNI/vision retry CLEAN | Local GPT-5.6 Sol medium, read-only qualitative retry limited to the earlier six correction dispositions; it did not review the three later broad findings or their corrections. |
| `/root/adr_transition_impl` | Complete | Proposed ADR-0018 and decision/documentation support; no D/E/F code. |
| `/root/adr0018_acceptance_impl` | Complete; final D1 elegance/YAGNI/vision result CLEAN | Independently re-reviewed the corrected D1 slice after its earlier actionable findings; no actionable finding remains. |
| `/root/installability_audit` | Complete; final D1 correctness result CLEAN | Independently re-reviewed the corrected D1 slice after its earlier actionable findings; no actionable finding remains. |
| `/root/milestone_a_verify` | Complete; elegance clean after wording fixes | Independent elegance/YAGNI/vision review of the proposal and acceptance-only slice. |
| `/root/milestone_d_impact_scout` | Complete; read-only | Post-acceptance D impact discovery only; no implementation authority. |
| `/root/d2_materialization_scout` | Complete; read-only | Bounded D2 immutable materialization/import and recovery design; no implementation or shared-surface edits. |
| `/root/d3_activation_scout` | Complete; read-only | Bounded D3 trusted activation design; no implementation or shared-surface edits. |
| `/root/milestone_d1_identity_impl` | Complete; D1 committed at `e599c46` | Sole D1 editor for frozen protocol/run identity, replay binding, tests, and this ledger; no D2 immutable materialization, D3 activation, or milestone-E decision implementation. |
| `/root/d2a0_receipt_impl` | Stopped; attempt rejected and discarded without commit | Produced the rejected five-file D2a0 attempt. Its same-UID descriptor/race-hardening boundary was rejected; the files are absent from the current tree and must not be resurrected. |
| `/root/d2_rework_ledger_impl` | Complete; documentation only | Recorded the coordinator's D2 rejection and Git-backed replacement direction in this ledger; no production code, tests, inventory, manifest, or commit authority. |
| `/root/d2_git_materialization_impl` | Complete; initial uncommitted review candidate handed off | Built the initial Git-backed D2 candidate; it is no longer editing. |

D2a0 review cleanliness cannot override the coordinator's architecture
correction. The earlier correction pass completed six bounded dispositions and
its narrow retries returned clean. Final correction commit `c23d645` resolves
the three broad-review findings and the three actionable findings from their
fresh follow-up finding passes. Final sessions
`019f67df-3022-7a12-9ecf-0a1f47e505d0` and
`019f67df-3092-71f3-bc7e-2537cf4530ee` supersede those finding passes and both
returned exactly CLEAN. The overlapping D3 runner was terminated before
production or test work; D3 is pending restart from a future clean frozen HEAD.
D1 is committed and its separate reviews are clean.

### Milestone D2 architecture correction record

- **Rejected and discarded without commit:** the five-file D2a0 attempt
  included an approximately 1,145-line materialization module and 704 lines of
  tests. It defended an arbitrary concurrently mutable same-UID filesystem
  tree with extensive descriptor-based race-hardening machinery, inode/ctime
  checks, hardlink and concurrent-final scenarios, and raw `ctypes`
  `renameat2`. That is not the accepted threat boundary and still let
  caller-supplied commit/tree hex create immutable identity for an arbitrary
  non-Git staging tree. The attempt is absent from the current tree, must not
  be resurrected, and could not become acceptable through review cleanliness.
- **Accepted threat model:** one host; a separate optimizer UID; an owner-only
  conductor and trusted store; one required single-campaign lock; and build
  provenance derived from exact trusted Git objects. Hostile same-UID mutation
  of conductor-owned paths is not in the accepted ADR-0017/0018 model. Expanding
  that threat model would require an explicit decision amendment, not
  implementation complexity.
- **Retain in the rework:** one closed canonical receipt/digest, exact binding
  to D1's frozen candidate allowlist, a read-only materialization seal, tamper
  verification, and before/after consumption rehashing.
- **Remove or replace:** caller-supplied commit/tree authority, arbitrary
  non-Git staging trees, same-UID descriptor/race machinery,
  hardlink/concurrent-final tests, and `ctypes` `renameat2`.
- **Replacement architecture:** import and validate trusted Git objects first
  and derive commit/tree internally; enumerate the raw Git tree and accept only
  blob modes `100644` and `100755`, rejecting symlinks and gitlinks; materialize
  those blobs once into an owner-only unique stage while holding the campaign
  lock. Under that lock, first verify and reuse an exact valid existing final;
  fail closed on a conflicting or invalid final; otherwise require the
  destination to be absent and rename the fully written and verified
  same-filesystem stage into it. Share one canonical build-row/digest authority
  with D1 `protocol.build_identity()`. Fresh correctness and
  elegance/YAGNI/vision reviewers must assess this Git-backed design before any
  D2 commit.
- **Committed D2 checkpoint:** the conductor-facing import API accepts
  the validated frozen D1 protocol snapshot, trusted repository, bundle, and
  held store lock. It derives the base commit and candidate allowlist only from
  that snapshot, and identity projection rechecks the same authority. Before
  invoking Git it resolves `.git`/`commondir` itself, rejects uncontrolled,
  symlinked, or group/world-writable administration, and fetches only from the
  canonical conductor-controlled common directory. Sanitized Git bundle
  verification plus an explicit `refs/heads/candidate` refspec replaces the
  deleted bundle-wire parser. Direct-parent/nonmerge/nonempty, allowlist, strict
  fsck, object format, full raw tree, and `100644`/`100755` checks remain.
- **Finding dispositions:** (1) the complete tree is capped at 10,000 files,
  each blob at 16 MiB, and expanded bytes at 256 MiB; sizes are batch-queried
  before strict fsck or blob-body reads, and accepted blobs stream to files
  while hashing; (2) canonical trusted Git administration is preflighted as
  above, with a linked-worktree unsafe-mode negative test; (3) the decorative
  optimizer UID parameter/assertion was deleted because D2 cannot establish
  inbox provenance from a caller-provided integer; (4) frozen protocol base
  and allowlist are now the only import/projection authority; (5) the custom
  bundle-header parser and its cross-product test were deleted because the
  explicit candidate refspec and retained commit/tree validation supply the
  required provenance; and (6) the closed canonical receipt now stores one
  domain-separated `git_tree_digest`, the allowlisted `materialized_digest`,
  Git identities, and frozen allowlist, then recomputes both digests from the
  sealed tree on every verification.
- **Broad-review correction dispositions:** (7) a canonical domain-separated
  receipt digest now covers every authoritative receipt field except the digest
  itself and is checked on every receipt read before projection or consumption;
  deterministic tests substitute each of `base_commit_sha`, `commit_sha`, and
  `tree_sha` and fail closed; (8) the D2 projection seam no longer accepts a
  role and can emit only a `candidate` build identity; and (9) a normalized
  frozen allowlist may name a charter-permitted root absent from the accepted
  base and first populated by the candidate. The overall projection must remain
  nonempty, and both build rows and candidate diffs outside the allowlist remain
  rejected.
- **Follow-up correction dispositions:** (10) every public verify, consume, and
  projection path now binds the receipt commit to canonical
  `build-{commit_sha}` publication, while the private pre-rename verifier uses
  the internally derived commit; a valid receipt from an identical-tree second
  commit cannot be substituted. (11) the shared D1/D2 build digest hashes one
  closed payload containing the normalized allowlist and canonical rows, so an
  otherwise empty frozen prefix changes identity. (12) worktree projection
  walks allowlist components with `lstat`, rejects file and symlink ancestors,
  and skips only genuinely missing paths beneath verified real directories.
- **Deliberate D3 residual:** configured separate-account and inbox ownership
  preflight belongs to the next lifecycle/activation checkpoint, where a real
  handback path and optimizer account exist. Retaining a D2 caller-invented UID
  would falsely claim that proof. D3 activation, campaign wiring, and any live
  source/model operation remain untouched.
- **Checkpoint evidence and review state:** diff and file size remain neutral
  transparency only, never an acceptance or elegance criterion. Twenty-one
  focused D2 tests plus 35 affected D1/unit tests pass for this follow-up.
  Lint, compilation, diff, and final manifest evidence are recorded below.
  The two narrow retry reports returned **CLEAN** for the earlier six
  dispositions. Final correctness session
  `019f67df-3022-7a12-9ecf-0a1f47e505d0` and final elegance/YAGNI/vision
  session `019f67df-3092-71f3-bc7e-2537cf4530ee` supersede the follow-up
  finding passes and both returned exactly **CLEAN**. D3, milestone D, and
  Slice A completion are not claimed.

### Milestone D1 implementation and correction record

- Final independent correctness result: **CLEAN**. Final independent
  elegance/YAGNI/vision result: **CLEAN**. Earlier passes found open task/suite
  scheduling, duplicated context identity, weak adapter/verifier authorization, insufficient
  trusted-code/admissions drift checks, caller-free replay promotion, broad
  placeholder matching, stale cleanup/comparison semantics, and duplicated
  allowlist authority. The latest P1 pass additionally required AR-003 to be
  the only reportability/decision authority; independent admission of both
  benchmark arms and every real noise sample; durable revalidation of accepted
  evidence; one frozen candidate path authority over the complete diff;
  count-insensitive calibration binding; and rejection of a treatment with the
  accepted materialized digest. Those findings are corrected in D1 commit
  `e599c46`. A subsequent review found that real noise bands retained
  only digest-shaped receipt strings, so missing or stale calibration evidence
  was not replayed before reuse, and that generality lint still had a hidden
  component-only default. Real bands now carry closed per-sample evidence
  anchors and must reproduce every AR-003 receipt before the gate will consume
  them; lint requires the frozen allowlist explicitly. The final bounded P1
  review then showed that valid anchors could accompany mutated persisted
  margins, flip allowances, or task counts. Revalidation now retains the
  freshly reloaded/admitted runs, canonically remeasures their real noise band,
  and requires exact equality of every serialized authoritative field before
  setting the transient validation flag. Both final re-reviews found no
  remaining actionable issue.
- The conductor now resolves and atomically freezes one full, self-contained,
  closed protocol snapshot before baseline. Keeping the full normalized
  snapshot is intentional: an archived run can validate its complete apparatus
  without mutable campaign configuration. Per-run context stays small and
  contains only run ID, mode, arm, suite role, exact ordered task subset,
  repeat, seed, protocol digest, build, and run digest.
- The protocol binds exact ordered suite/task records, every declared dev
  task/seed matched block and arm order, source reset/environment/browser
  identities, normalized live adapter identity, verifier checksum/bundle and
  exact admissions bytes, executor identity/settings, instrumentation, lane,
  one normalized non-overlapping candidate allowlist, accepted build, repeated
  protocol, and the complete Python source trees of `opti_eval`, `opti_loop`,
  and `opti_judge` where the loop consumes them.
- Before E2, any scheduled E3, E4, E5, and again immediately before eligibility,
  the gate recomputes trusted code/admissions bindings. Drift is invalid, not a
  treatment result. The runner also requires actual adapter and verifier
  bindings to equal the frozen identities before issuing a typed in-memory
  receipt.
- Adapters receive only `run_id` and `run_context_digest`. Callers must supply
  the exact protocol and context; persisted replay without the caller-held
  receipt is diagnostic and non-reportable. Receipt mismatch, protocol/run/task
  substitution, stale accepted anchors, and simulated accepted anchors fail
  closed. Cross-campaign ranking additionally requires one shared comparison-
  apparatus digest and a live benchmark-eligible accepted anchor.
- Raw runner summaries now always persist
  `benchmark_reportable=false`/`acceptance_decision_eligible=false`. Only a
  closed in-memory AR-003 admission receipt can authorize a benchmark
  comparison or decision. Baseline and treatment arms, regression runs, and
  every real noise sample are independently assessed; the accepted-run loader
  reloads the exact evidence directory, reruns AR-003, and requires the full
  receipt to equal the durable anchor.
- The normalized frozen candidate allowlist is shared by protocol freeze and
  replay and rejects trusted harness surfaces. It controls containment,
  identity hashing, lint, registration, the exact full-diff manifest scope,
  and optimizer instructions. `target_component` is attribution only. The
  optimizer packet now records and prints the exact frozen allowlist instead
  of hard-coding `harness/components/<target_component>/`.
- Calibration identity ignores only the repeat count and its count-derived
  `valid_after`/`max_runs` scheduling values; apparatus changes still drift the
  binding. Treatment identity rejects equal accepted/candidate materialized
  bytes even when Git commit/tree fields differ.
- A persisted real noise band now contains one closed campaign-relative
  evidence-directory/full-AR-003-receipt anchor per ordered sample. Decision
  preflight reloads the frozen calibration protocol and every sample with its
  derived live identity, reruns AR-003/T1 against current admissions and
  quarantine state, and requires exact receipt equality. Unsafe, duplicate,
  missing, tampered, stale, fabricated, reordered, symlinked, or wrong-protocol
  samples invalidate the decision. Digest-only bands are rejected; synthetic
  fixture bands remain anchor-free and nonreportable.
- Production identity validation is positive and field-scoped: exact sentinel
  values/namespaces are rejected case-insensitively without rejecting legitimate
  identities such as `model-latest-stable`. Accepted-build and arm-specific
  roles are enforced. Fixture/direct paths remain explicitly simulated.
- Start preflights the next iteration path before creating a worktree and rolls
  back only state/directories it created if identity or baseline setup fails.
  Existing owner artifacts are preserved. The current conductor still emits a
  mutable build receipt, so benchmark start remains blocked until D2 supplies
  immutable materialization; no benchmark performance is claimed.

### ADR-0018 acceptance record

- The exact reviewed proposal is committed at `544750b`; both independent
  proposal re-reviews returned clean before acceptance.
- On 2026-07-15 the owner-delegated coordinator, acting under the founder's
  delegated architecture-decision authority, approved the exact proposal:
  `Accept ADR-0018 as written.`
- This acceptance-only slice changes status, approval, relationships, current
  state documentation, and manifests. It changes no substantive ADR-0018 clause
  and contains no milestone D/E/F implementation.
- Acceptance correctness is clean. Acceptance elegance/YAGNI/vision is clean
  after making proposal-only implementation authority and the absence of D/E/F
  changes precise.

### Completed ADR-0018 review/fix loop

- `/root/installability_audit` returned seven correctness findings covering the
  frozen matched-block protocol, exact amendment/taxonomy semantics, trusted
  activation/evaluation boundaries, constitutional modality, timeline drift,
  ADR metadata/relationships, and durable roster. This implementation agent
  applied the corrections; correctness re-review found the substance clean and
  requested only this roster closeout.
- `/root/milestone_a_verify` challenged timeline wording,
  amendment/taxonomy clarity, and the unsupported implication that WACZ and
  verifier bytes were already pinned. The correction now makes those external
  identities preflight requirements and gives the reversible target a narrow
  revisit rule. Its final re-review found only the EXT-002 ledger inconsistency
  corrected in this closeout.
- `/root/milestone_d_impact_scout` concluded that post-acceptance milestone D
  should compose one frozen conductor protocol snapshot, one immutable build
  receipt/materialization path, and one trusted E1 activation record—not expand
  a disconnected collection of hashes. This is read-only preparation, not D
  implementation or authorization.

### Completed-review history

The milestone-C evidence review found
manifest portability, exact loop-count accounting, stale package-rationale,
and durable-roster findings. `/root/milestone_c_evidence_impl` corrected those
findings without changing package, CLI, or archive logic; the only code change
was the manifest-builder exclusion correction. `/root/installability_audit`
then independently reproduced the exact committed-HEAD install,
network-namespace, count, and byte-identical 374/375 manifest claims.
`/root/milestone_a_verify` found the corrected slice concise, nonduplicative,
and internally consistent after explicitly challenging clean-install verifier
overlap with archive/completeness logic. Both final re-reviews are clean.
`/root/installability_audit` returned a clean archive-closure correctness
review after independently verifying the archive, manifest, milestone, queue,
ADR-gate, roster, and evidence-boundary claims. `/root/milestone_a_verify`
confirmed the archive proof is distinct from the clean-install proof and found
the closure slice otherwise clean; its sole commit-stability finding was the
ephemeral future-rerun narration removed in this correction. With that
correction applied, both archive-closure reviews are clean.

- `/root/milestone_a_verify` found the original numeric/order and Git-worktree
  gaps, then returned a clean post-correction correctness sign-off.
- `/root/ar003_elegance_review` returned a clean final YAGNI/vision sign-off
  after the supported numeric range and exact Git-root checks were aligned.
- `/root/matrix_correctness_review` reported four documentation findings and
  returned clean after correction.
- `/root/matrix_elegance_review` returned clean milestone-B
  elegance/YAGNI/vision sign-off.
- `/root/installability_audit` completed the read-only package/installability
  audit, returned a clean code-slice correctness review, and returned a clean
  final evidence review after independently reproducing its exact claims. Its
  archive-closure correctness review also returned clean.
- `/root/milestone_a_verify` returned a clean focused review of the committed
  code slice's archive portability, path safety, dirty-root refusal, and
  verification flow, then its evidence review found the manifest portability,
  count-accounting, stale-rationale, and roster issues. Its final
  elegance/YAGNI re-review found the corrected eight-file slice concise,
  nonduplicative, internally consistent, and clean. Its archive-closure review
  confirmed that the archive proof is distinct and found only the ephemeral
  commit-stability prose corrected here; the closure review is clean after that
  correction.
- `/root/review_matrix_ledger` completed the initial documentation-only matrix
  draft and its bounded corrections before the separate final reviews.

At most one implementation agent should edit a shared code surface at a time.
Each later milestone requires a separate correctness reviewer and a separate
elegance/YAGNI/vision reviewer; both must return no actionable findings before
the milestone is complete.

## Completed commits

| Commit | Evidence-bearing completion |
|---|---|
| `2fffe08`, `7995f06`, `420925b`, `1f888ae` | Three repository audits were recorded and consolidated into the original implementation program. |
| `eb25f62` | AR-001: external bridge evidence fails closed. |
| `f21038c` | AR-002: experiment manifest schema/runtime/example/conductor contract unified. |
| `57f402b` | AR-003 handoff snapshot only: substantial evidence-bundle hardening, explicitly **not** final independent sign-off. |
| `72e73c2` | AR-003 completion: exact numeric and RFC3339 ordering, bounded finite-real evidence, and normal/linked-worktree completeness gaps closed; final correctness and elegance reviews are clean. |
| `382a255` | Milestones A/B documentation closure: durable execution ledger, three-review decision matrix, completed AR-003 records, and regenerated manifests. |
| `9d0a7ab` | Milestone-C code: explicit package dependencies, clean-install proof surface, repository-root CLI discovery, and portable archive/completeness integration. |
| `ef0da6b` | Milestone-C evidence closure: reviewed manifests and install evidence committed; full portable ZIP/extraction and standalone Git-bundle verification subsequently pass from this clean commit. |
| `762226a` | Milestone-C documentation closure and regenerated manifests; current-HEAD portable archive verification subsequently passed. |
| `544750b` | Independently reviewed ADR-0018 proposal and its nonbinding decision/documentation relationships; no D/E/F code. |
| `07f98b9` | ADR-0018 acceptance record under the exact owner-delegated coordinator approval; no D/E/F code. |
| `e599c46` | D1 exact closed protocol/run identity, frozen candidate allowlist, AR-003 admission authority, durable benchmark-anchor revalidation, and independent clean reviews. |
| `e6866e0` | Original Git-backed D2 materialization checkpoint and its earlier six correction dispositions. The narrow retry reports were clean for those six only. |
| `c23d645` | Final D2 review-follow-up correction. The settled code passed final correctness and elegance/YAGNI/vision re-reviews, each returning exactly CLEAN. |

Current branch: `codex/auto-research-readiness`.

## Verification evidence

The milestone-A/B/C closure state has current verification:

- eval tests: 30 passed;
- judge tests: 28 passed;
- loop tests: 77 run; 76 passed and one skipped for the deliberately optional
  `jsonschema` dependency;
- schema audit: 531 documents, including 195 evidence-contract cases and 180
  experiment-contract cases, with zero errors, run with an already-cached
  offline `jsonschema` environment;
- documentation audit: 84 Markdown files, 171 local links, and 18 ADRs;
- repository completeness passes from this linked worktree while rejecting a
  repository child as the requested Git root;
- regenerated `FILE_INVENTORY.tsv` and `MANIFEST.sha256` pass verification;
- Python compilation and `git diff --check` pass;
- committed HEAD `9d0a7ab` builds exactly the three expected pure-Python
  wheels with cached `setuptools>=68`, requests only `opti-loop==0.1.0` into an
  empty-setuptools environment, installs exactly eval/judge/loop through their
  declared transitive graph, and rejects the missing-judge negative control;
- installed CLI help, explicit and discovered eval-root validation, and pure
  transfer evaluation pass without repository `PYTHONPATH`; the same complete
  verifier passes under `unshare -Urn`, proving the workflow with no network
  namespace access;
- clean commit `ef0da6b` builds a 446-file portable ZIP using
  `python scripts/build_repository_archive.py --output
  /tmp/opti-browser-tool-milestone-c.zip --bundle`; extraction and repository
  checks pass, and the ZIP digest is
  `2201dc360dde833723cc067bd78e1244223a9fe264b760df6146cb3bcb96a557`;
- the standalone Git bundle verifies, and both ZIP and bundle SHA-256 sidecars
  match their artifacts;
- independent AR-003 correctness and elegance reviews, plus independent
  milestone-B correctness and elegance reviews, report no actionable findings.

The D1 slice committed at `e599c46` passed 46 eval tests, 28 judge tests, and
112 loop tests (111 passed plus the existing optional-`jsonschema` skip). The
cached offline schema environment passes 531 documents with zero errors (195
evidence-contract and 180 experiment-contract cases). Documentation passes 84
Markdown files, 171 local links, and 18 ADRs. Repository/package/catalog
completeness, Python compilation, and `git diff --check` passed. Its
clean-install proof builds all three wheels, installs only the declared
eval/judge/loop dependency graph through offline/no-index resolution, runs
installed CLI checks and all three installed test suites, rejects the
missing-judge negative control, and records `benchmark_evidence=false`.
The D1 commit-time inventory catalogs 379 files and the digest manifest
verifies 380 files.
The final codebase-memory index contains 12,210 nodes and 19,038 edges.

The committed, review-clean D2 code has the following offline verification
evidence; none is milestone-D or Slice-A completion evidence:

- the implementation handoff reports `python -m unittest loop_harness.tests.test_materialization
  loop_harness.tests.test_units` with the three package source roots and
  `OPTI_BROWSER_REPO_ROOT` set: 56 tests passed (21 D2 plus 35 affected units);
- the implementation handoff also reports standalone `ruff check` and
  `py_compile` over the two changed production modules and focused test module:
  passed; this documentation closeout did not rerun those focused gates;
- this closeout ran broader `loop_harness` unittest discovery once with the
  same three package source roots and `OPTI_BROWSER_REPO_ROOT`: 133 tests ran,
  132 passed, and one skipped for the deliberately optional `jsonschema`
  dependency; and
- this closeout's diff, completeness, documentation, and generated-manifest
  gates are recorded after the final ledger bytes settled.

The initial candidate's offline clean-install proof was not rerun for this
bounded correction because no package metadata or dependency surface changed.
After all source, test, and ledger changes, `python
scripts/build_file_manifest.py` regenerated 381 inventory rows and 382 manifest
entries. `python scripts/verify_file_manifest.py --repo-root .` then passed all
382 entries. `git diff --check c23d645` passed. Repository completeness passed
55 required files, package metadata, and all 140 cataloged candidates without
errors or warnings. Documentation verification passed 84 Markdown files, 171
local links, 18 ADRs, and all 140 normalized task files without errors or
warnings.

Adversarial D1 coverage includes exact ordered task subsets and suite roles;
undeclared seed/repeat/order rejection; exact matched blocks and arm order;
accepted/baseline, candidate/treatment, and diagnostic role enforcement;
case-folded production sentinels without substring false positives; minimal
adapter-visible context; actual adapter/verifier mismatch; caller-held receipt
and bundle-substitution rejection; ordinary non-reportable replay; complete
eval/loop/judge code drift and admissions drift; gate rechecks between runs and
before eligibility; frozen-config mutation; protocol tamper/overwrite refusal;
normalized allowlist overlap rejection; stale-noise binding; existing-iteration
preflight preservation; failure cleanup; comparison-apparatus exclusion of
campaign/iteration/build; missing/different comparison identity; and rejection
of simulated accepted anchors. The P1 correction coverage additionally proves
raw-summary nonauthority; independent admission of paired arms and every real
noise sample; accepted evidence-directory/receipt replay; strict persisted
noise evidence-class/admission types; positive real-noise restart/reuse;
missing/deleted, tampered, stale-admission, fabricated-anchor, wrong-order,
symlink, changed-calibration-protocol/current-binding, unvalidated-gate, and digest-only
real-noise rejection; full-diff manifest equality; `target_component`
nonauthority; lint and identity across every frozen allowed root; required
explicit lint allowlist; trusted harness-surface rejection; exact
optimizer-packet allowlist;
count-derived calibration equivalence; and same-materialized-bytes treatment
rejection. It also reproduces the reviewer's exact zero-margin/zero-flip band
mutation to a `1.0` margin and task-count flip allowance, plus task-count and
anchor-order controls; all fail closed while positive restart revalidation
remains green. No fixture artifact becomes benchmark evidence.

The ordinary clean-install verifier enforces uv offline mode, `--no-index`, a
local wheelhouse, and an empty install cache; it is not by itself an OS network
sandbox. The separate successful `unshare -Urn` run supplies that stronger
proof. Neither invocation accessed a live backend, source platform, campaign,
credential, paid API, or external benchmark asset.

The archive proof likewise used no live backend, platform, campaign,
credential, paid API, or external benchmark asset.

Fixture and deterministic simulation results are plumbing evidence only and
must always remain `benchmark_reportable=false` / `evidence_class=simulated`.

## Blockers

### Cleared architecture decision gate

- ADR-0018 is Accepted under the exact owner-delegated coordinator approval
  recorded in the ADR. No architecture decision blocker remains before
  milestone D. This does not clear any external activation blocker or authorize
  a live campaign.

### Software blockers to close in milestones D-I

- `harness/` is a scaffold with no executable browser harness; the current loop
  can construct only fixture, harness-fixture, and non-reportable command
  adapters.
- D1 supplies closed protocol and run-context identity. The rejected five-file
  D2a0 attempt did not derive candidate identity from trusted Git objects; it
  was discarded without commit, is absent from the current tree, and must not
  be resurrected. Original D2 commit `e6866e0` and its review-clean final
  correction at `c23d645` remain unwired;
  D3 must connect immutable candidate execution and trusted dynamic activation.
- E5 executes one treatment run; the four-valued repeated paired/interleaved
  protocol, durable champion/regression protection, and deterministic
  positive/no-op/regression/invalid simulations are incomplete.
- No concrete reportable source adapter, reset contract, credential/asset
  preflight, or local browser-fixture integration path is complete.
- Interrupted-iteration recovery, atomic state/receipt advancement, minimal
  locks/permissions, budgets/deadlines, and operator status are not yet at the
  requested single-host readiness boundary.
- The Analyst is explicitly `stub-0`; trace-linked learning, trusted judge
  identity/routing where used, source dispositions, and executable operator
  workflow remain incomplete.

### External activation inputs that must remain honest blockers

- Exact credentials/subscription authentication, provider/model identifiers,
  snapshots/settings, quota and data-retention policy.
- Pinned WARC WACZ/runtime assets (or another explicitly approved source),
  browser/runtime binaries, license/provenance confirmation, and any required
  account/environment access.
- Real reset/oracle/probe-kit evidence, verifier admission, source capacity,
  real variance/noise calibration, and task-level difficulty calibration.
- A genuinely private disjoint holdout under owner-only control; public or
  fixture tasks cannot substitute for it.
- Platform-specific permissions and explicit authorization for any live,
  destructive, externally visible, paid, or unattended campaign action.

## Next steps

1. Resume D3 trusted activation from a future clean frozen HEAD with one
   writable GPT-5.6 Sol medium implementer
   and its own bounded implementation/review loop.
2. Implement the four-valued repeated protocol in milestone E, with positive,
   no-op, regression, invalid, and interruption simulations.
3. Implement the reversible WARC `online.4` readiness path in milestone F (or document the
   evidence that forces a different concrete source): precise preflight,
   reset/verifier/artifact/config contracts, constrained execution seam, and
   offline/local fixture integration only.
4. Finish single-host lifecycle, analyst/learning, source dispositions,
   status/operator commands, adversarial integration, manifest regeneration,
   and final independent correctness plus elegance reviews.
5. Stop at software readiness and publish the exact external activation
   checklist. Do not run or imply a real campaign without owner-supplied inputs
   and explicit authorization.
