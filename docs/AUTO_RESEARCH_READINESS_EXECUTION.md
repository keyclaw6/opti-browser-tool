# Auto-research readiness execution

Status: active orchestration ledger. Milestones A/B/C and the pre-D decision
transition are complete; milestone D is next.
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
| **D — exact identity and trusted activation** | **Next; not started** | Bind exact run/build/protocol/environment/verifier/executor identity, immutable candidate execution, and conductor-authoritative activation proof with deterministic negative and positive coverage. |

Milestones D-I remain ordered as identity/activation; repeated decision and
champion protection; concrete
source/backend readiness; safe single-host lifecycle; trace-backed
learning/operator flow; and final integration/adversarial verification.

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
| Broaden `harness/components/**` so the candidate can test the charter's real harness behavior | R1 | **Adapt and implement** | `harness/` currently contains contracts and registrations but no browser code; `harness/infra` freezes backend/session behavior plus model-interface and harness-local routing surfaces that the charter permits as harness treatments. Define an explicit candidate-owned harness-build boundary while keeping tasks, setup/reset, verifiers, secrets, evidence admission, safety policy, acceptance code, and the executor's exact model/provider identity and settings immutable within a harness experiment. Model comparisons remain separate experiments. Retain `target_component` and one causal treatment where they aid attribution; do not force every valid treatment into an artificially narrow file taxonomy. |
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
| `/root` | Active | Orchestration, integration, milestone sequencing, and final authority. |
| `/root/adr_transition_impl` | Complete | Proposed ADR-0018 and decision/documentation support; no D/E/F code. |
| `/root/adr0018_acceptance_impl` | Complete | Acceptance-only decision metadata, cross-links, ledgers, final wording corrections, and regenerated manifests; no D/E/F code. |
| `/root/installability_audit` | Complete; correctness clean | Independent correctness review of the proposal and acceptance-only slice. |
| `/root/milestone_a_verify` | Complete; elegance clean after wording fixes | Independent elegance/YAGNI/vision review of the proposal and acceptance-only slice. |
| `/root/milestone_d_impact_scout` | Complete; read-only | Post-acceptance D impact discovery only; no implementation authority. |

No D/E/F implementation sub-agent is active. The acceptance-only documentation
slice is clean after separate correctness and elegance/YAGNI/vision reviews and
is ready for its own commit.

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
- Full run/build/protocol/environment/verifier/model identity is incomplete;
  immutable candidate execution and trusted dynamic activation are not proven.
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

1. Implement milestone D exact identity, immutable candidate execution, and
   trusted activation in a bounded implementation/review loop.
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
