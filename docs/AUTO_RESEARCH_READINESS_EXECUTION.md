# Auto-research readiness execution

Status: active orchestration ledger on branch
`codex/auto-research-readiness`. This file records implementation direction
and evidence; it does not authorize a live campaign or turn fixture output
into benchmark evidence.

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
| **D — exact identity and trusted activation** | **D3 committed at `9d6b39c`; fixture-backed checkpoint only** | D3 connects static-bundle import, D2 materialized execution, immutable treatment identity, conductor-observed harness-fixture activation through E1-E5, and recoverable accepted publication. It is the frozen milestone-F starting point, not browser activation, reportability, or operation readiness. |
| **F — WARC `online.4` qualification** | **Committed at `7c245e5`; software qualification checkpoint only** | The reviewer-clean software checkpoint is frozen in commit `7c245e5402d03563f3ec98e067c612963c0a7725`. No external WACZ/verifier/runtime/license/credential input or live/reportable qualification has been supplied or run; milestone F external completion and operation readiness remain incomplete. |
| **E — repeated decision and champion protection** | **Committed at `527fbdb`; reviewer-clean software checkpoint** | Milestone E is contained in exact HEAD `527fbdb1a197f39bcd89340e963256129e78a12c`. Its final correctness and elegance/YAGNI/vision reviews are CLEAN. The four-valued repeated decision and champion/transfer protections are software-complete; real calibration and transfer evidence remain external activation inputs. |
| **G-I — lifecycle, learning, and operator integration** | **Committed at `ec197f7`; reviewer-clean and full-gate green** | The coherent G-I software readiness slice is committed exactly at `ec197f72997e957f5c3c8a731c6cb87487a5296f`. Sole writer GPT-5.6 Sol medium session `019f6af4-71be-7f20-bb31-6ea2aa227cd0` completed the bounded slice from exact HEAD `527fbdb1a197f39bcd89340e963256129e78a12c`. Final framing correctness session `019f6b2e-a93f-7c63-8907-e147c3f4dbec` and final framing elegance/YAGNI/vision session `019f6b2e-a9b4-7293-b6ad-96efc0fd2365` both returned CLEAN with no findings on frozen full dirty digest `ee5ca8c64fe951a51e836458388f2717a5eca1e35860081ab99f7615a92545e4`. These supersede the retained intermediate FIX/CLEAN history. Defined current-byte gates are green. No implementation or review agent remains active after this closeout, and no overlapping editor exists. |

The founder-authorized fast-path software sequence is committed and offline-ready
through D3 (`9d6b39c`), F (`7c245e5`), E (`527fbdb`), and G-I
(`ec197f72997e957f5c3c8a731c6cb87487a5296f`). Numeric milestone labels do not
override that dependency order. Remaining work is deliberately external or
deferred.

### Founder fast path disposition

The completed readiness software work is organized into four vertical slices: **A** is
D2 immutable Git-backed materialization followed by D3 trusted activation;
**B** is milestone F concrete WARC-Bench `online.4` source/backend
qualification; **C** is milestone E repeated decision and champion protection;
and **D** is milestones G-I single-host lifecycle, learning/operator flow, and
final integration. Each checkpoint has one bounded implementation owner and
exactly two fresh
independent reviewers: one correctness reviewer and one
elegance/YAGNI/vision reviewer. Focused tests run during editing, one broader
suite runs when a checkpoint becomes a review candidate, and complete
repository gates run once per coherent milestone or final release candidate.
The clean G-I slice is contained in exact commit
`ec197f72997e957f5c3c8a731c6cb87487a5296f`. This ledger closeout does not
commit, push, or merge.

## Final readiness report

- **Software checkpoint: READY TO OPERATE OFFLINE and READY FOR OWNER-SUPPLIED
  ACTIVATION INPUTS.** The deterministic path covers initialization; exact
  accepted/candidate Git identity; immutable materialization; observed harness
  and local WARC-seam activation; fail-closed evidence; repeated four-valued
  decisions; regression, champion, and transfer protection; exactly-once
  terminal publication for accepted and non-advancing outcomes; atomic
  accepted-state CAS; one strict trace-cited LearningRecord; foreground
  run/resume/pause/stop/status; interruption recovery; closed budgets and
  deadlines; and explicit nonreportability of fixtures/local fakes.
- **External activation: BLOCKED, deliberately.** The exact operating commands
  and boundary are in the <a href="AUTO_RESEARCH_OPERATOR_RUNBOOK.md">operator
  runbook</a>, and the source-specific contract is in the
  <a href="WARC_ONLINE4_QUALIFICATION.md">WARC `online.4` qualification
  document</a>.
  Passing the offline path is not real browser activation, external WARC
  qualification, benchmark reportability, or campaign authorization.
- **Required activation inputs:** owner-supplied WACZ plus provenance, license,
  and checksum; native verifier plus checksum and successful admission; pinned
  BrowserGym, Playwright, browser, WARC, and runtime identities; provider/model
  settings and named credentials where required; an approved external meter;
  distinct conductor/optimizer UIDs, inbox ownership, and confinement proof;
  real reset/oracle/noise/calibration/difficulty/transfer evidence; a genuine
  private holdout and ADR-0003 owner decision where required; and explicit
  campaign authorization.
- All-140 execution follows activation under ADR-0014 and was not run. No
  benchmark performance is known or claimed; fixture and local-fake results are
  simulated and nonreportable.

Every **new** worker must be launched with local
`codex exec -m gpt-5.6-sol -c 'model_reasoning_effort="medium"' -c
'approval_policy="never"' -C <repo>` and one self-contained prompt, plus
`--output-last-message`. Only the sole bounded implementer receives a writable
sandbox; the correctness and elegance/YAGNI/vision reviewers run in parallel
with read-only access. There is no collaboration-spawn fallback: an exact
runner failure stops that assignment and must be reported.

Bounded scope is qualitative, with no LOC or production-file-count target. A
larger direct implementation can be correct and elegant; a smaller one can
still be duplicated, speculative, or disconnected. Each slice must implement
one dependency-correct behavior with one editor, no speculative abstractions or
unused generality, and only the tests and validation required by current
invariants. Diff size may be recorded as neutral transparency, but never as a
budget, target, exception, acceptance rule, or evidence of elegance. No further
D2 hardening, generic filesystem machinery, or size-driven rewrite is allowed
without a concrete current test, accepted ADR, or actionable review finding.

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
| Make observed activation a trusted dynamic fact rather than optimizer-authored prose or E1 `pending` | R1/R2/R3 | **Accept and implement** | D3 qualified the conductor-observed harness-fixture seam; committed milestone F reuses that authority for only WARC `online.4`. Other adapters fail closed. Treatment evidence binds the executed candidate/build, frozen surface, run identity, trusted result metrics, and baseline observation. Missing, baseline-build, wrong-build, wrong-path/surface, or unconsumed observation is invalid; behavior-neutral output remains valid activation and proceeds to the efficacy decision. No generic instrumentation plugin system is needed. |
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
  accepted materialized digest. Those findings are corrected in D1. A
  subsequent review found that real noise bands retained
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
  Existing owner artifacts are preserved. D2 now supplies immutable
  materialization; benchmark start remains blocked until D3 wires
  the exact materialized candidate to execution and conductor-observed
  activation; no benchmark performance is claimed.

### D3 committed checkpoint (`9d6b39c`)

- **Bounded closeout writer:** local Codex session
  `019f69de-0b03-7333-adf2-579a6a2b5432`, GPT-5.6 Sol medium, was the sole
  writable D3 closeout implementer. `/root` is the orchestrator, not the
  implementer. This handback is implementation evidence only, not an
  independent-review claim or authorization for external activation.
- At the committed D3 checkpoint, the only qualified activation seam was
  `harness-fixture` consuming
  `harness/components/policy/quality.txt`. At that checkpoint, all shipped
  adapters were non-reportable, and accepted benchmark publication was mocked
  in tests.

- The current consumer turns a same-user simulated optimizer worktree handback
  into one static Git bundle, while benchmark mode requires an independent
  static bundle plus manifest sidecar. It imports the bundle with
  `materialize_candidate_bundle` under the campaign lock, projects the treatment
  context only through `project_build_identity`, and executes every treatment
  run from the exact read-only tree inside one `consume_materialization`
  boundary. In benchmark mode D2's receipt supplies candidate identity, E0
  derives changed paths from the sealed D2 tree against the trusted accepted
  commit, and the sidecar is read once into the one manifest snapshot used for
  validation, execution, and persistence. The mutable worktree is neither
  benchmark candidate nor manifest authority.
- `run_iteration` now holds one existing campaign lock from a fresh trusted
  pending-state reload through D2, evaluation, terminal recording, pending
  reset, and accepted publication. It verifies the pending base against the
  freshly loaded accepted identity. Advancing publication imports the exact
  D2 commit/tree first and compare-and-swaps the accepted ref from the identity
  observed under that lock; contention and a ref race are deterministic
  regressions, without adding the later milestone-G recovery journal/service.
- `start_iteration` uses the same campaign lock and reloads trusted campaign
  state before deciding what may open. It refuses a pending publication without
  consuming N+1; a current complete/failed receipt is validated and cleaned
  before the next iteration opens. `run_iteration` owns pending recovery and
  terminal replay, so cleanup after the final receipt is interruption-safe.
- Accepted benchmark advancement now writes one campaign-owned pending
  publication intent after the verified staging ref roots the exact candidate.
  Under the same campaign lock, one idempotent recovery path couples the
  accepted-ref CAS, canonical gate/snapshot, cluster register, ledger,
  learnings, final campaign state, and completion receipt. The next
  `run_iteration` reloads trusted state and finishes a pending intent before
  normal pending processing. Deterministic interruption after intent, ref,
  each artifact/register/ledger/learnings boundary, and state converges to the
  same ref/state/evidence receipt without duplicate rows. The intent and
  terminal receipt have closed versioned shapes and canonical digests. Recovery
  validates every duplicated identity, the exact accepted-state and cluster
  transitions, frozen protocol/manifest diff, canonical result, and current
  campaign state before the first mutation. Pre-intent construction/write
  failures compare-and-swap-delete staging; once a valid intent is durable, it
  alone owns cleanup. Before an attempt without a durable intent, one canonical
  cleanup rule removes only the conductor-derived trusted handback and treatment
  evaluation outputs while preserving the frozen protocol and accepted-build
  baselines. A regression injects failure after real E1-E5 gate execution but
  before intent serialization, retries real gate execution, and converges
  without stale outputs or a staging ref. Complete/failed receipts retain only
  transaction identity, intent digest, result summary, and failure text when
  applicable. This is only the D accepted-publication seam, not milestone-G
  lifecycle recovery.
- The P1 recovery correction narrows invalid-publication handling to an explicit
  accepted-ref contention exception at the pre-CAS/CAS boundary. A Git failure
  during terminal cleanup now leaves the already-durable accepted ref, state,
  evidence, complete receipt, and single ledger row intact for replay. Intent
  readback is conservative: staging is deleted only when readback positively
  establishes that the persisted record is not the just-written intent;
  indeterminate read failure preserves staging for recovery. These corrections
  reuse the same publication record and replay path rather than adding another
  recovery mechanism.
- The remaining P1 CAS correction rereads the accepted ref after a CAS Git
  error. A demonstrated move to another commit is contention and remains
  invalid; reaching the candidate continues idempotently; an unchanged or
  unavailable ref propagates the original Git error with pending intent and
  staging intact for replay. This keeps unrelated Git failures retryable
  without weakening the genuine-race decision.
- The harness-fixture smoke run is the bounded E1 activation probe. Immutable
  conductor code carries the smallest observation on `EvalRun`: consumed path,
  checksum, parsed value, and cited `run.json`. E1 verifies it against the exact
  materialized candidate tree, D2 treatment identity, frozen changed/allowed
  surface, existing protocol/run/adapter identity and result metrics, plus the
  trusted accepted-build observation. There is no duplicate activation file,
  schema, or digest. Missing baseline/candidate observations, a baseline build,
  wrong build/digest/path/surface, unconsumed bytes, or receipt mismatch are
  invalid and stop later treatment runs. Exact candidate bytes/build and
  declared-surface consumption remain valid when treatment output equals the
  baseline; behavior-neutral mode and numeric-text candidates now pass E1 and
  reach the existing efficacy decision, where the focused fixtures reject them
  for no verified flip. D2 before/after
  consumption verification remains the tamper boundary.
- Local fixture handback and all fixture results remain simulated,
  nonreportable, and state-inert. Benchmark mode requires an explicit static
  bundle and manifest sidecar whose files and inbox share a separate optimizer
  UID. Manifest structure is evaluated first at E0; ownership is checked only
  immediately before the conductor takes its trusted bundle copy and enters D2.
  The manifest and every inbox directory component are opened with no-follow
  semantics, its bytes are read exactly once from a pinned descriptor, and the
  bundle is opened relative to the same pinned inbox. Ownership uses `fstat`
  on those descriptors and the trusted copy reads exactly the initially
  bounded bundle byte count, rejecting append, short, or metadata-change races.
  Manifest snapshots are capped at 256 KiB and likewise reject size/metadata
  change while preserving the one-read E0 ordering. Path replacement, symlink
  substitution, or append-driven trusted-disk growth therefore cannot change
  or enlarge the admitted handback.
  Expected ownership failures terminate at E1 invalid with the complete trusted
  gate report, canonical experiment snapshot, ledger, and safe reset. The
  successful end-to-end static handback regression uses real D2
  import/materialization and narrowly mocks only ownership validation; it is
  not evidence of deployed UID isolation.
- One exact conductor-owned handback copy now survives D2 quarantine cleanup
  through the verdict. Before an advancing benchmark verdict writes terminal
  artifacts, the conductor imports that same bundle into a temporary trusted
  ref and verifies its commit and tree against both the D2 receipt and projected
  treatment build. Accepted-ref publication is compare-and-swap over the
  already-present object. A separate-clone regression exercises real object
  absence, bundle import, D2 materialization, prepublication import, and ref
  publication; only admission/verdict and the ownership boundary are mocked, so
  it is not full benchmark or two-user deployment evidence.
- Structurally invalid manifests terminate authoritatively at E0 before bundle
  import. After E0 structure passes, handback/import/materialization failures
  remain E1 invalid and are never relabeled rejected. Simulated automatic bundle
  creation preserves any pre-existing `refs/heads/candidate` with compare-and-
  swap restoration and fails closed on a concurrent ref change. Manifest JSON
  uses the repository strict parser in both conductor ingestion and the public
  `load_and_validate` loader, so duplicate keys and NaN/Infinity are E0
  rejected submissions rather than silently normalized trusted snapshots.
  Optimizer-authored repetition counts are bounded identically by runtime and
  schema at 1 through 10,000; arbitrarily large JSON integers are rejected at
  E0 without lossy float conversion.
- Component registration now strictly decodes each changed component exactly
  once and requires the complete closed `component.json` shape. Root arrays,
  scalars/null, missing/unknown fields, duplicate keys, non-JSON numbers,
  malformed or duplicate file entries, and missing registered files fail E1
  without a second permissive parse.
- The accepted harness component now ships and registers
  `harness/components/policy/quality.txt` with the numeric baseline rate. Public
  CLI initialization requires the harness-fixture path and rejects unsafe,
  out-of-allowlist/current-accepted-surface, nonregular, symlinked, unreadable,
  non-finite, or out-of-range file/default-rate inputs;
  a repository-level CLI `init` then `start` regression uses the shipped file
  without mocks.
- Expected adapter, evaluation, registration/preflight, and materialization
  failures after E0 become active-rung invalid terminal evidence, write the
  canonical gate/snapshot/ledger, and reset pending state. The boundary catches
  only declared runner/configuration, value, filesystem, Git, guard, and D2
  failures; programmer exceptions are not swallowed broadly. Numeric behavior
  values `2.0`, `NaN`, and `Infinity` are covered.
- The conductor's outer preparation boundary now catches only declared
  handback/import/D2/guard failures. `run_gate` executes outside that broad
  catch: expected evaluation errors terminate locally at E1/E3/E4/E5, while
  unexpected `MaterializationError`, `ValueError`, and `OSError` exceptions from
  `run_gate` propagate with pending state intact instead of creating false E1
  evidence.
- At the committed D3 checkpoint, only the instrumented `harness-fixture`
  adapter could start treatment execution. Other adapters stopped at E1 invalid
  with `run_suite` uncalled.
  Simulated accept/reject/invalid outcomes and the simulated pivot path clear
  pending fields but preserve `iterations_since_accept`, `failed_attempts`, and
  `iterations_since_divergent`; only valid benchmark accept/reject evidence may
  mutate those research-continuation counters.
- This is fixture-backed trusted activation/publication infrastructure only,
  not milestone-D, Slice-A, browser-activation, reportability,
  or operation-readiness. Targeted rereviews in correctness session
  `019f6823-fc0a-7873-a189-85724ca6682d` and elegance/YAGNI/vision session
  `019f6823-fbb9-7953-b606-5f0c31c24166` found the external-object publication,
  shipped-fixture/CLI, and canonical-preflight-order gaps corrected in this
  pass. These were historical actionable findings; the final reviews below
  supersede their review status. This pass accessed no live source, external
  benchmark asset, credential, model, or paid API.
- The subsequent R2 correctness session
  `019f6824-4020-7863-bf69-2ec5a60e2193` and elegance/YAGNI/vision session
  `019f6824-3fdc-7223-b3e1-08fdeb554b7c` identified the seven remaining
  lock/CAS, handback TOCTOU, strict-JSON, terminal-failure, CLI preflight,
  simulated-inertia, and unsupported-adapter findings corrected above. These
  were historical actionable rereviews, not clean sign-offs; the final reviews
  below supersede their review status.
- Fresh R3 correctness session `019f684a-fea8-7753-aba4-d2efb46a6423`
  and elegance/YAGNI/vision session
  `019f684a-fef0-7fb0-ab5b-332f4d14f55b` identified four actionable findings:
  recoverable accepted publication, bounded pinned snapshots, the active-rung
  exception boundary, and duplicate strict-manifest authority. The bounded
  corrections are recorded above. These were historical actionable sessions,
  not clean sign-offs; the final reviews below supersede their review status.
- R4 correctness reviewer `/root/d3_r4_correctness` and elegance/YAGNI/vision
  reviewer `/root/d3_r4_elegance` identified the remaining publication-contract,
  start serialization/replay, gate exception, total registration, established-ref,
  pre-intent cleanup, huge-integer, sole-authority integration, and receipt-size
  findings. Implementer `/root/d3_r4_fixes` made the bounded corrections above
  and added failure-injection, resealed-tamper/no-mutation, real separate-clone,
  and malformed-registration regressions. These were actionable reviews, not
  clean sign-offs; the final reviews below supersede their review status.
- The frozen P1 reviews authorized the two bounded publication-recovery
  findings corrected in this pass. They are actionable finding inputs, not
  clean-review claims. The correction writer is the local Codex session named
  above; `/root` remains the orchestrator.
- The targeted correctness and elegance rereviews identically reported the
  remaining CAS-error classification finding corrected above. This records an
  actionable historical correction, not a clean rereview result.
- Final targeted correctness session
  `019f69e9-6517-7d71-ab89-406a46abdc64` returned **CLEAN** for CAS outcomes,
  transient retry, genuine contention, staging preservation, single-row replay,
  and adjacent cleanup/readback interactions. Final targeted
  elegance/YAGNI/vision session
  `019f69e9-6824-77e3-9cb7-ca6e24439122` returned **CLEAN** and found no added
  journal, taxonomy, recovery abstraction, or duplicated authority. Both
  reviewed frozen dirty-diff SHA-256
  `768c8b6ed2c9b81ee7274ad37106f01d0df084fb1adea8bb30a0eb84e543cba4`
  with no drift. D3 was therefore a review-clean commit candidate for the
  fixture-backed trusted activation/publication infrastructure only; no commit
  hash or milestone-D completion is claimed.

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
| `497a492` | D2 documentation/evidence closeout from the frozen final D2 code; its verification gates passed. |
| `9d6b39c` | D3 trusted fixture-backed activation and the sole recoverable publication transaction checkpoint. |
| `7c245e5` | F reversible WARC `online.4` software qualification path; external assets and live qualification remain absent. |
| `527fbdb` | E four-valued repeated decision plus durable regression, champion, and scheduled-transfer protection. |
| `ec197f72997e957f5c3c8a731c6cb87487a5296f` | G-I lifecycle, learning, operator integration, and coherent software-readiness checkpoint. |

Current branch: `codex/auto-research-readiness`.

## Verification evidence

### Final G-I current-byte gates

- source eval/WARC: 68/68 passed;
- source judge: 28/28 passed;
- source loop: 221 run, 220 passed, and one existing optional `jsonschema`
  skip;
- eval catalog validation: PASS with 140 catalog/primary tasks,
  smoke/regression 20/20, and source counts 30/30/30/30/20;
- cached offline `jsonschema` audit: 531 documents and zero errors;
- documentation: PASS for 86 Markdown files, 176 local links, 18 ADRs, and 140
  raw, normalized, and by-ID tasks;
- repository completeness: PASS for 55 required files plus package, catalog,
  and Git checks;
- file manifest: PASS for 394 files; changed Python surfaces pass Ruff; Python
  compilation and `git diff --check` pass; and
- clean-install working-tree copy: PASS with Python 3.14.5 and uv 0.11.6,
  exactly three pure-Python wheels, offline/no-index installation of
  `opti-loop==0.1.0` and the exact eval/judge/loop dependency graph, the
  missing-judge negative control, installed CLI help/eval validation/cwd
  discovery/pure transfer checks, and all three installed suites. No live
  backend ran and the proof records `benchmark_evidence=false`.

An exploratory repo-wide Ruff invocation found six pre-existing style findings
outside the changed surfaces. Repo-wide Ruff is not a defined repository gate,
so this observation does not expand the closeout scope or create an activation
or readiness blocker.

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

The committed D1 slice passed 46 eval tests, 28 judge tests, and
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

The D3 checkpoint committed at `9d6b39c` has the following offline
verification evidence:

- this remaining P1 correction pass ran seven focused tests covering transient
  CAS retry, genuine CAS contention, terminal cleanup, intent readback, real-
  gate pre-intent retry, and both behavior-neutral activation cases: all seven
  passed;
- broader loop-harness discovery ran 184 tests: 183 passed and one skipped for
  the deliberately optional `jsonschema` dependency;
- targeted `ruff check` and `py_compile` over the corrected conductor and
  focused test module passed;
- this P1 correction pass ran the two new recovery regressions plus the three
  existing pre-intent retry and behavior-neutral activation closeout tests: all
  five passed;
- broader loop-harness discovery ran 183 tests: 182 passed and one skipped for
  the deliberately optional `jsonschema` dependency;
- targeted `ruff check` and `py_compile` over the corrected conductor and
  focused test module passed;
- this bounded closeout's nine focused retry, publication-recovery, neutral-
  activation, and invalid-activation regressions passed; the pre-intent retry
  executes real E1-E5 gates twice around the injected failure and converges;
- broader loop-harness discovery ran 181 tests: 180 passed and one skipped for
  the deliberately optional `jsonschema` dependency;
- targeted `ruff check` and `py_compile` over the two changed production
  modules and focused test module passed;

- focused affected CLI, transaction, eligibility, and manifest-contract run:
  124 tests ran, 123 passed, and one skipped for optional `jsonschema`;
- the earlier pre-closeout broader loop-harness discovery ran 180 tests: 179
  passed and one skipped for the deliberately optional `jsonschema` dependency;
- unchanged eval-harness and judge-harness regression suites passed 46 and 28
  tests respectively;
- production-module `ruff check` and Python compilation passed;
- required adversarial coverage includes static-bundle import through exact
  materialized execution, immutable run-context identity, observed behavior
  activation, invalid missing/wrong activation, valid behavior-neutral activation,
  stop-after-E1, D2 tamper before and after consumption, manifest snapshot
  swap, malformed-manifest/materialization ordering, terminal benchmark
  handback preflight, real static bundle/sidecar import with mocked ownership,
  separate-clone object publication, shipped-file CLI `init` then `start`,
  candidate-ref preservation, full transaction-lock/ref-CAS races, pinned-path
  replacement/symlinks, strict JSON, terminal expected failures, unsupported
  adapter nonexecution, full simulated counter inertia, bounded append/short/
  oversize snapshots, true later-rung errors, nine accepted-publication
  interruption/recovery boundaries, strict/digested publication shapes,
  resealed intent tamper with zero recovery mutation, pre-intent staging
  cleanup, start/replay serialization, established-ref deletion, malformed
  registrations, and huge repetition integers; and
- no live source/campaign, external asset, credential, or model/API budget was
  used;
- repository completeness passed 55 required files, package metadata, and all
  140 cataloged candidates; documentation passed 84 Markdown files, 172 local
  links, 18 ADRs, and all 140 normalized task files;
- the optional schema audit was attempted but could not run because
  `jsonschema` is unavailable in this environment. The changed repetition
  schema/runtime ceiling is instead covered by alignment, public-loader, and
  canonical E0 regression tests; and
- final inventory/manifest counts and verification are recorded below after the
  durable ledger bytes settle.

The initial candidate's offline clean-install proof was not rerun for this
bounded correction because no package metadata or dependency surface changed.
After all corrected source, test, README, and ledger bytes settled, production
and touched-test `ruff check`, Python compilation, and `git diff --check`
passed. Repository completeness passed 55 required files, all package metadata,
and all 140 cataloged candidates without errors or warnings. Documentation
verification passed 84 Markdown files, 172 local links, 18 ADRs, and all 140
normalized task files without errors or warnings. Final
`python scripts/build_file_manifest.py` regeneration produced 382 inventory
rows and 383 manifest entries; `python scripts/verify_file_manifest.py
--repo-root .` passed all 383 entries.

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
- **Implemented behavior:** iteration start now completes accepted-base
  development and regression preparation before one campaign save publishes
  `current_iteration=N` with `pending_iteration=N`. Reloaded status during both
  first and later real suite execution therefore sees only the prior stable
  publication state; existing rollback, recovery, receipt validation, sole
  publication authority, and fail-closed missing-terminal-receipt behavior are
  unchanged. That same rollback now covers distillation, packet creation,
  delayed register persistence, and final paired-iteration state persistence.
  Injected packet, register-after-write, and state-after-write failures restore
  prior state/register bytes, remove iteration artifacts/worktrees, preserve
  the prior healthy publication, and retry the same iteration. Rollback now
  durably restores `state_before` immediately under the campaign lock before
  fallible cluster/artifact/worktree cleanup. A combined state-write and later
  cleanup fault retains prior current/pending numbering and publication
  projection, then makes the next route fail closed. The obsolete unused
  `Campaign.open_iteration()` early-save authority is deleted; no new journal
  or recovery path exists. WARC preflight delegates the complete nested
  repeated protocol to the evaluation identity validator, including an exact
  missing `effect.minimum_effect` diagnostic; production-template drift
  coverage walks
  shared required fields through representative verifier, runtime, limits,
  source-runtime, and repeated-protocol leaves. Both root and loop-harness
  rehearsal instructions now bind all closed limits and execute with the
  dependency-complete three-package path.
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
- **Boundary/blockers:** no live operation, external spend, merge, push,
  performance, or reportability claim occurred. `benchmark_reportable` remains
  false without admitted real evidence. Remaining external activation inputs
  are owner-supplied WACZ and checksum with provenance and license; native
  verifier executable identity/checksum and positive admission; exact
  BrowserGym, Playwright, browser/runtime, and model-transport identities;
  credentials only if the selected source requires them; optimizer UID, inbox,
  and runtime confinement; real reset/final-state/trace/artifact evidence;
  calibration, transfer, and holdout evidence; metering and owner decisions;
  and explicit campaign authorization.

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
  tests, while correctness supplied the dynamic reproduction.
- **Bounded correction:** only the existing start-preparation transaction now
  catches `BaseException`, restores trusted campaign state before fallible
  cleanup, restores cluster bytes, removes iteration artifacts and the
  candidate worktree, and re-raises an interruption unchanged. Any failure in
  those existing cleanup steps is saved through the sole `cleanup_health`
  failed/detail authority before it is re-raised. No signal handling,
  supervisor, journal, recovery framework, or second cleanup authority was
  added. The WARC production-template test now compares the recursively
  complete closed-object key shape with the already preflight-validated local
  fixture and proves representative nested deletions fail.
- **Focused evidence:** separate regressions interrupt the first baseline
  `run_suite` through its real evaluation path while preparing fresh iteration
  1 and while preparing iteration 2 after a normal terminal rejection of
  iteration 1. They prove exact trusted-state/register restoration, preservation
  of the complete iteration-1 publication, artifact/worktree cleanup, clean
  cleanup health, no blockers, and retry of iteration 1 or 2 respectively. The
  two interruption regressions, combined state-write plus cleanup-failure
  blocker regression, existing packet/register/state rollback regression, and
  recursively complete WARC template regression pass (5 focused tests) and
  were actively reproduced by correctness.
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
  Fixture evidence remains non-live and nonreportable; all previously documented
  owner-supplied activation inputs and authorization blockers remain.

The milestone-F software checkpoint committed at `7c245e5` has the following
local verification evidence; none is live/reportable qualification evidence:

- **Bounded writer:** session `019f6a00-be3a-7220-b4df-8b22c6da3f0c`, GPT-5.6
  Sol medium, is the sole bounded milestone-F implementation writer with no
  overlapping editor;
- **Latest review status:** correctness session
  `019f6a56-5b43-7442-a54a-091c1697a15b` and elegance session
  `019f6a56-5a3f-7062-9d52-8f7a5dc4e342` each returned FIX. Their batch found
  the guessed production Gym constructor, post-close JSON verifier authority,
  preflight files that did not govern actual imports, and blocking/leaky worker
  IPC. Subsequent orchestrator source inspection found that the first correction
  still used an invented handler constructor/setup signature. This P1 is now
  corrected to the pinned keyword API plus the narrow in-memory `online.4`
  `task_config.env` adaptation. The final reviewer pair then found control-IPC
  contamination, missing consumed-manifest authority, decorative model identity,
  incomplete resolved-environment/Playwright binding, and an overlong HTTP
  timeout. The permitted rereview of that state returned FIX because the real
  CLI omitted derived model aliases, a drip-fed urllib response could exceed
  the lifecycle, verifier calls were not bound to one Page object, and the
  adapter kept a second post-hoc clock. Final resumed GPT-5.6 Sol medium
  correctness session `019f6a8c-ecc7-79c1-9fe3-d0eec9e97ad0` returned CLEAN,
  confirming the absolute full-response deadline and timer restoration, retained
  reset-time Page, real CLI model-alias/operator traversal, removed adapter
  clock, and accepted-state restriction to accepted benchmark evidence. Final
  elegance/YAGNI/vision session `019f6a8c-ecb0-78e0-8db2-c2eee89f1d0c`
  returned CLEAN, confirming one timing authority, one Page observation
  authority, a connected CLI path, and no new recovery, scheduler, retry, or
  duplicate framework. Frozen digest
  `fe53a6c0e9ea405c0835e80cd090abefc620bae26a59381fc3bd7ea5583e3bc8`
  is therefore the reviewer-clean software qualification checkpoint; its
  containing milestone-F commit will carry that checkpoint identity;
- evaluator discovery passes 67 tests, including all 21 focused WARC
  config/preflight/admission/lifecycle/live-verifier/runtime-identity/
  subprocess-cleanup cases;
- the positive normal-conductor traversal, negative echo-only traversal, and
  negative dropped-treatment traversal passed: exact candidate bytes are part
  of the applied model body and its cited digest, while echo-only or omitted
  candidate evidence is invalid and state-inert;
- the broader affected loop end-to-end/CLI suite passes 79 tests, including
  strict admission reuse and proof that admission failure prevents campaign
  initialization. It also proves actual CLI `init` -> `start` -> local WARC
  execution derives both protocol aliases without test-only injection, remains
  non-reportable, and cannot advance accepted state; the earlier pre-correction
  full loop discovery is historical
  evidence only and is not a correctness claim for this correction;
- the WARC local fake traversed the normal conductor, D2 materialized candidate,
  WARC treatment load/replay/reset/model-request/action/native-verifier/final-state/
  trace/artifact/cleanup
  shapes, D3-derived E1 activation, E2, and the efficacy screening path;
- the fake remained `benchmark_reportable=false`, used local-fixture evidence,
  and left accepted state unchanged;
- representative failures cover WACZ, verifier, pinned source, actual loaded
  runtime/browser identity,
  executor, provenance/license, credential, protocol identity, optimizer UID/
  inbox, wrong task/source, reset, verifier, final state, trace, artifact,
  activation, echo-only rejection, exact handler keyword/setup calls, missing
  handler task-config shape, manifest blob/row mismatch, noisy upstream worker
  output, wrong resolved Gym environment, wrong Playwright driver, clipped late
  model calls, absolute drip-fed response timeout, reset-time Page substitution,
  unsupported Gym kwargs, artifact symlink containment,
  malformed/hung reset, hung close, terminate-resistant worker reaping, and
  production preflight with zero lifecycle execution; and
- the offline schema audit passed 531 documents, 195 evidence cases, and 180
  experiment cases; documentation passed 85 Markdown files and 175 local links;
  repository completeness passed 55 required files; the regenerated inventory
  and digest manifest passed at 388 and 389 files; targeted changed-surface
  Ruff, source compilation, and `git diff --check` passed; and
- no live source, browser task, external benchmark asset, credential value,
  model/API budget, fetch, or network access was used.

Committed milestone E adds the prespecified repeated decision authority
directly to the existing conductor:

- E0-E4 remain fail-fast scheduling/screens; E5 now executes frozen
  paired/interleaved baseline and treatment arms for development and regression
  suites, with symmetric run-context identity, accepted/candidate build checks,
  exact AR-003 admission, fixed dev/regression block-set stopping, budget,
  pre/post-arm deadline enforcement, one supported
  paired-mean/observed-range/all-blocks decision rule, protocol-owned quorum and
  fixed policy identifiers, repeatedly supported predicted flips, durable
  accepted-state regression and champion evidence, and canonically digested
  protocol-bound transfer inputs evaluated by the existing transfer decision;
- the deterministic decision has exactly `accepted`, `rejected`,
  `inconclusive`, and `invalid`; the legacy noise envelope is recorded only as
  a diagnostic and cannot decide acceptance;
- deterministic run IDs and retained exact run directories resume completed
  arms after interruption without re-execution; completed WARC arms reconstruct
  and revalidate conductor-owned activation from existing closed run/trace
  artifacts; the existing recoverable accepted-publication transaction remains
  the only state-advance path, persists the minimal durable protection record,
  and still advances only `(accepted, benchmark)`;
- final correctness session `019f6ade-3396-7303-afe6-afbf3e4e6083` returned
  CLEAN with no remaining P1, matching hashes, and nine focused read-only
  checks. Final elegance/YAGNI/vision session
  `019f6ade-3492-78a2-8226-24d39ee6c825` returned CLEAN with no findings and
  matching hashes. Writer evidence passes 17 identity, 15 repeated, 36 unit,
  45 evidence/admission, 21 offline WARC, 21 materialization, and 68 E2E tests;
  the broader loop suite ran 205 tests, with 204 passing and one existing
  optional skip. This is a committed reviewer-clean software checkpoint,
  not calibrated real, live, performance, reportability, or operation-readiness
  evidence; and
- no asset was fetched, credential read, model/browser/live-source task run,
  external budget spent, or performance/reportability claim made.

## Blockers

### Cleared architecture decision gate

- ADR-0018 is Accepted under the exact owner-delegated coordinator approval
  recorded in the ADR. No architecture decision blocker remains before
  milestone D. This does not clear any external activation blocker or authorize
  a live campaign.

### Software checkpoint boundary

- No software task remains in the founder-authorized D3/F/E/G-I fast path.
  D3 remains the fixture-backed infrastructure checkpoint at `9d6b39c`; F is
  committed at `7c245e5`; E is committed at `527fbdb`; and reviewer-clean,
  full-gate-green G-I is committed exactly at
  `ec197f72997e957f5c3c8a731c6cb87487a5296f`.
- D3 plus F now exercises exact immutable Git materialization and observed
  activation through the concrete local WARC seam in offline tests. This is not
  real browser activation, external WARC qualification, reportability, known
  performance, or live readiness.
- G-I reuses the one D3 publication/recovery authority for accepted and
  non-advancing terminal outcomes, and adds the bounded foreground lifecycle,
  status, limits, LearningRecord, and operator flow. Final correctness session
  `019f6b2e-a93f-7c63-8907-e147c3f4dbec` and final elegance/YAGNI/vision session
  `019f6b2e-a9b4-7293-b6ad-96efc0fd2365` both returned CLEAN with no findings
  on digest
  `ee5ca8c64fe951a51e836458388f2717a5eca1e35860081ab99f7615a92545e4`.
- Founder-fast-path deferrals remain explicit: Analyst is `stub-0`; no T2
  council, all-five-source scheduler, private holdout contents, multi-campaign
  machinery, live confinement proof, native-verifier admission, or real
  calibration/transfer evidence is claimed.

### External activation inputs that must remain honest blockers

- Owner-supplied WACZ with provenance, license, and checksum.
- Native verifier with checksum and successful admission.
- Pinned BrowserGym, Playwright, browser, WARC, and runtime identities.
- Provider/model settings and named credentials where required, plus an
  approved external meter.
- Distinct conductor/optimizer UIDs, correct inbox ownership, and confinement
  proof.
- Real reset/oracle/noise/calibration/difficulty/transfer evidence, a genuine
  private holdout, and the ADR-0003 owner decision where required.
- Explicit campaign authorization. All-140 execution follows activation under
  ADR-0014 and was not run.

## Next steps

1. Preserve committed D3 (`9d6b39c`) as fixture-backed trusted
   activation/publication infrastructure; do not infer browser reportability
   or operation readiness from it.
2. Preserve committed F (`7c245e5`), E (`527fbdb`), and G-I
   (`ec197f72997e957f5c3c8a731c6cb87487a5296f`) without treating offline
   simulation as calibration, benchmark, performance, reportability, external
   qualification, or live-run evidence.
3. Stop at software readiness. External owners must supply and verify the
   required browser/source assets, credentials, identities, confinement,
   metering, verifier admission, calibration evidence, and ADR-0003 decisions
   where required before explicitly authorizing any campaign.

### Retained start-worktree rollback correction — implementation committed

- **Committed and frozen reviewed state:** implementation commit
  `6340ffe00b46410dcc9d870900292affd09d2370` has subject
  `Fail closed on retained start worktree`. Its reviewed implementation state
  is base
  `e238113c3d531faaa033d169930533160d9d37b4` plus binary diff
  `14736128d5045bd4432d19b40f3a5dbd8ee01c26ed1c17650f893000984fe50e`.
  Production/test SHA-256 values remain
  `d4c40467053dcdb9f50573f6c1b5cbd1e009f98e11321d6e5e47e3b70d6cf099`
  and `b760af7d1037f918638283efd760aa208e4aca9450a821806539d4254b977a74`.
  Writer was GPT-5.6 Sol medium session
  `019f6c71-e557-79c1-b8ef-d04ead28b6e8`.
- **Bounded correction:** after the existing start-preparation
  `worktree_remove`, the conductor now fails cleanup when the worktree path or
  symlink remains. The existing `cleanup_health` authority records the exact
  failure and existing operation gates block status/preflight and transition.
  One regression uses the real helper with an injected nonzero underlying Git
  result. No cleanup framework or broad Git behavior changed.
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
- **Clean-install evidence:** from exact clean implementation commit
  `6340ffe00b46410dcc9d870900292affd09d2370`, normal verification passed with
  `TMPDIR=/home/kab/.cache/opti-clean-tmp-normal python scripts/verify_clean_install.py --repo-root "$PWD"`;
  network-isolated verification passed with
  `TMPDIR=/home/kab/.cache/opti-clean-tmp-unshare unshare -Urn python scripts/verify_clean_install.py --repo-root "$PWD"`.
  Both used Python 3.14.5 and uv 0.11.6 and passed three-wheel construction,
  offline/no-index dependency resolution, negative dependency control,
  installed CLIs, and all three installed test suites. Neither used a live
  backend, and both retained `benchmark_evidence=false`.
- **Discarded environmental execution evidence:** initial concurrent attempts
  using the nearly full 7.7GB `/tmp` tmpfs failed in Git with `Disk quota
  exceeded`; the repository remained clean. Isolated reruns with the explicit
  home-filesystem `TMPDIR` values above passed. This was an environmental
  execution failure, not a code or test acceptance failure.
- **Boundary:** the correction is implementation-committed and reviewer-clean.
  The four-file docs closeout was independently reviewed CLEAN with no findings
  by GPT-5.6 Sol medium read-only session
  `019f6c87-c36c-70e0-a4bf-11964415c70e` on implementation HEAD
  `6340ffe00b46410dcc9d870900292affd09d2370` plus binary diff SHA-256
  `387593cffb23a9eae82c3a7a252ac2219a802ceb3f830146546e46d734539356`
  and was committed as `82447c39e366abd43033be575f3cc0aa7eb5fb52`.
  No external activation, live readiness, reportability, performance, merge,
  push, or live operation is claimed; the existing external activation
  blockers remain exact.

### Post-materialization start interruption — implementation committed

- **Committed and frozen reviewed state:** implementation commit
  `5fdcadab25de7cc273952f8e2fdc1c162ea89e2a`; writer GPT-5.6 Sol medium
  session `019f6c9c-4e0d-7c60-b23e-b1100d26ba2f`; base
  `82447c39e366abd43033be575f3cc0aa7eb5fb52` plus binary diff SHA-256
  `b7a886661a51369cad5fcfaf67446a039602a9607fe564812442c1a096112e3f`.
  Production/test SHA-256 values are
  `1687e18527026c12751d6bfdbd5eb4348a6cf62a9bdde07c94581f3f1b7dfed0`
  and `87caad61da1fe930b961f67052d0998b2c81fd517605d24f67792530a80998a5`.
- **Correction:** start-preparation rollback unconditionally calls the existing
  idempotent best-effort `worktree_remove`, retains the path-or-symlink
  postcondition, and removes the obsolete `worktree_created` flag. One
  regression interrupts after the real add helper materializes the worktree.
  The writer's six focused tests passed in 5.271s.
- **Correctness review:** GPT-5.6 Sol medium session
  `019f6ca0-7d20-7231-997c-6074978f3eb4` returned CLEAN with no findings. Its
  six focused tests passed in 5.205s, proving harmless retry after real
  pre-materialization add failure, cleanup and retry after real
  post-materialization interruption, the exact suppressed-removal blocker,
  first/later interruption retry, and state-first cleanup authority.
- **Elegance/YAGNI/vision review:** GPT-5.6 Sol medium read-only session
  `019f6ca0-7d26-7222-b3f3-f5eeab31ef47` returned CLEAN with no findings. It
  confirmed deletion-first flag removal, unconditional existing cleanup, one
  cleanup authority with state-first ordering, the retained postcondition, the
  truthful historical `82447c3` ledger correction, and no helper, marker,
  journal, or recovery machinery. Correctness supplied the dynamic proof.
- **Full gates:** eval 70/70; judge 28/28; loop ran 231 and passed 230 with one
  documented optional `jsonschema` skip; catalog passed 140; schema experiment
  corpus 180 and evidence corpus 195; docs passed 86 Markdown files, 177 links,
  and 18 ADRs; completeness passed 55; manifest verified 395 entries; Ruff,
  `py_compile`, and `git diff --check` passed.
- **Clean-install evidence:** normal verification passed with
  `TMPDIR=/home/kab/.cache/opti-postadd-clean-normal python scripts/verify_clean_install.py --repo-root "$PWD"`;
  network-isolated verification passed with
  `TMPDIR=/home/kab/.cache/opti-postadd-clean-unshare unshare -Urn python scripts/verify_clean_install.py --repo-root "$PWD"`.
  Both proved offline/no-index installation, used no live backend, and retained
  `benchmark_evidence=false`.
- **Independent docs review:** sole reviewer GPT-5.6 Sol session
  `019f6cb2-dbe2-7493-8829-2d2fbc816069` returned CLEAN with no findings on
  reviewed two-ledger binary diff SHA-256
  `7ea25005f9b0b37bd5c3e9272ed6bee179ec50f886b4abfe4f6eec39415e6106`.
  It independently reproduced docs 86, links 177, ADRs 18, completeness 55,
  committed manifest 395 with zero mismatches, exact HEAD/file hashes/diff,
  historical `82447c3` wording, committed `5fdcada` status, and the external
  boundaries. Its read-only sandbox could not rerun dynamic tests; those remain
  linked to the writer and correctness evidence above.
- **Boundary:** the implementation and evidence-only closeout are independently
  reviewer-clean.
  No live readiness, reportability, performance, merge, push, or live operation
  is claimed; existing external activation blockers remain exact.
