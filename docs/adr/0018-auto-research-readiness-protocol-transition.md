# ADR-0018: Auto-research readiness protocol transition

- Status: Proposed
- Date proposed: 2026-07-15
- Date accepted: —
- Approval state: Not accepted; no project-owner approval has been recorded
- Proposes amendments to: [ADR-0005](0005-experiment-gating.md) and [ADR-0015](0015-auto-research-loop-architecture.md)
- Proposes a conforming writable-path amendment to: [ADR-0017](0017-model-and-infrastructure-pins.md) item 7; its two-user confinement remains unchanged
- Leaves open: [ADR-0002](0002-shared-substrate-and-lane-boundaries.md) and [ADR-0003](0003-initial-browser-backend.md)
- Supersedes: —
- Superseded by: —

## Context

The readiness reviews found that the accepted E0-E5 ladder and five-plane
boundary remain useful, but a single treatment observation can still be lucky,
the candidate boundary is narrower than the charter's permitted harness
research, and current identity and activation contracts do not yet bind the
exact evaluated build. This proposal records the smallest coherent transition
needed before milestones D-F can change those accepted contracts. It does not
authorize implementation, source acquisition, or a campaign.

## Proposed amendments

### 1. Keep E0-E5 and make E5 a prespecified repeated decision

E0-E5 retain their containment, activation, smoke, targeted, regression, and
development-evaluation roles. Before any treatment observation, an immutable
protocol record must bind:

- the exact task/suite universe and matched-block map, where each block binds
  task and source identity, stochastic seed, reset/environment instance, and
  paired/interleaved baseline/treatment arm order, with arms differing only by
  the candidate build;
- coverage and quorum rules, source-family presence rules, and their denominator
  against the original frozen universe so missing evidence cannot silently
  shrink the comparison;
- repeat counts, valid stopping rules, and a prohibition on optional stopping;
- handling of invalid, missing, quarantined, and valid-in-one-arm-only results;
- the treatment-effect estimator, uncertainty construction, minimum effect,
  and a separate explicit non-inferiority rule and margin;
- regression, champion, and scheduled transfer protection;
- the multiplicity or family-level false-acceptance rule; and
- evaluation budget, deadline, and exhaustion behavior.

Every numeric threshold, repeat count, stopping rule, and uncertainty parameter
is supplied by identity-bound campaign configuration and calibrated from real
evidence as ADR-0005 requires. Production preflight fails when a required value
or its calibration identity is absent. Deterministic simulations may validate
the machinery but may not calibrate those values or become benchmark evidence.
Budget or deadline exhaustion before a prespecified valid stop can never
accept: integrity-valid but incomplete or insufficient evidence is normally
`inconclusive`. Exhaustion alone is not `invalid`; only an evidence-integrity
or infrastructure-integrity failure is.

The deterministic decision has exactly four outcomes:

- `accepted`: sufficiently supported benefit with every protection satisfied;
- `rejected`: valid, sufficiently informative evidence fails the acceptance
  rule or establishes a protected regression;
- `inconclusive`: valid evidence is insufficient or too uncertain to decide;
- `invalid`: an evidence-integrity or infrastructure-integrity failure makes
  identity, activation, reset, verifier, trace, or artifact evidence
  untrustworthy.

ADR-0005's at-least-one prespecified predicted flip remains required as a
causal diagnostic for acceptance and is evaluated over the repeated E5
evidence. It is never sufficient, is not the treatment-effect estimator, and
cannot override the repeated treatment, non-inferiority, regression, champion,
transfer, coverage, or multiplicity decision. If valid evidence cannot resolve
the predicted flip, the result is `inconclusive`; a powered valid miss is
`rejected`. Invalid and inconclusive outcomes do not advance accepted state.

### 2. Bind exact identity, execution, and activation

Each arm/repeat run binds a unique run identity to the accepted and candidate
commit/tree identities, the materialized build digest, the frozen protocol
and campaign-allowlist digests, task/source/setup/reset/environment/browser
identity, the evaluator and admitted verifier bundle identity, and the executor
provider, model, snapshot/revision, and settings. Any trusted judge routing used
for diagnosis is separately identity-bound and remains non-scoring.

The candidate executes from an immutable materialization of the exact recorded
build. Immutable conductor-owned tracer and activation instrumentation must
show that build and the declared treatment surface actually executed.
Candidate-emitted telemetry is evidence input only, never activation authority;
registration, candidate telemetry alone, or optimizer-authored prose is not
proof. Missing, baseline-only, or wrong-build activation is `invalid`.

ADR-0015's candidate-owned surface is proposed to become an explicit,
campaign-pinned **harness-build allowlist**, rather than being permanently
limited to `harness/components/**`. The frozen campaign allowlist is E0's path
authority; the legacy directory and `target_component` are not path authority.
It may include only charter-permitted candidate-side harness behavior:
browser-control tools, observation/action interfaces, prompts and policies,
planning and recovery, tool descriptions, session management, error handling,
context handling, routing, candidate-side backend/control behavior, and
harness-side action/state checks used for planning and recovery. The
source/evaluation adapter, source setup and reset, tasks, objective verifiers,
evaluator code, and source-native oracle remain outside the candidate boundary.

The trusted tracer/activation instrumentation, result/trace/artifact schemas,
evidence admission, frozen protocol, E0-E5 gates, decision transaction,
executor model configuration, safety policy, secrets, and trusted evidence
store are also immutable and conductor-owned.

ADR-0017's separate-OS-user confinement remains: the optimizer may write only
the campaign-pinned harness-build allowlist. The proposal changes the literal
`harness/components/**` path restriction, not the confinement or secret/store
boundary.

One hypothesis and one causal treatment remain the default. The manifest keeps
`target_component` when meaningful as attribution metadata. Only a genuinely
irreducible treatment may span multiple allowlisted surfaces, and then the
manifest must predeclare the exact surfaces/build and explain the dependency
before evaluation. That whole build is one treatment; its parts receive no
independent attribution or partial acceptance. This is a narrow exception, not
repeal of the component taxonomy.

The executor provider/model/snapshot/settings remain fixed within a harness
experiment. A model change is a separate experiment. The exact evaluated build
is indivisible: retaining or rolling back only part of it creates a new build,
candidate, and experiment that must pass the complete protocol.

### 3. Advance accepted state atomically

Gate, decision receipt, regression/champion update, learning record, and
accepted-ref compare-and-swap publish as one recoverable transaction. Accepted
state advances only for `(accepted, benchmark)` evidence over the exact build;
`rejected`, `inconclusive`, `invalid`, and all fixture/simulated evidence are
state-inert.

### 4. Reversible first-adapter qualification

For readiness work only, qualify one adapter path for WARC-Bench candidate
`warc-bench-online-4` (`online.4`) with the minimum BrowserGym/Playwright
capability needed by that path. The repository pins the upstream source/manifest
identity and WACZ path and records the native-JavaScript-verifier expectation;
it does **not** contain or pin the WACZ or verifier bytes/checksums. External
configuration and preflight must pin and validate the exact asset, verifier,
and runtime identities/checksums plus provenance and license. This is a
reversible bring-up qualification pin, not a final backend selection, not
acceptance of ADR-0003, and not evidence that this task is admitted or
benchmark-reportable.

Implementation after acceptance is limited initially to configuration,
actionable credential/asset/runtime preflight, reset/verifier/artifact
contracts, and offline/local deterministic integration tests. It must not fetch
external assets, access a live platform, run a campaign, spend model/API budget,
or claim performance.

If the assets, license, runtime, or native verifier cannot satisfy the identity,
reset, evidence, and admission contracts, replace this qualification target
through the decision record rather than weakening the contract or silently
substituting a backend. ADR-0003 remains Open.

### 5. Preserve lane and scope boundaries

The constitutional visual-first and terminal/CLI lanes remain distinct and use
common contracts. Qualifying one adapter may prepare one lane; it does not
resolve how lanes are packaged or combined, so ADR-0002 remains Open. A hybrid
or router still waits for evidence from mature independent lanes.

Structured DOM/accessibility/reference interaction is a modality and pinned
configuration inside a constitutional lane. It is neither a third lane nor a
replacement or redefinition of the terminal/CLI lane.

This proposal defers parallel campaigns, databases, plugin systems, generic
registries, distributed scheduling, execution/calibration of all 140 tasks,
private-holdout construction, and numeric protocol calibration. Deferral does
not cancel ADR-0014: all 140 candidates still run before filtering once the
required real assets, admitted verifiers, resets, and exact runtime inputs
exist.

## Consequences

The protocol prevents a lucky treatment run, a shadowed change, a partial
rollback, or fixture output from advancing the champion. Candidate research can
reach the full charter-permitted harness while evaluation authority remains
immutable. The cost is more identity metadata and repeated evaluation, with
production activation remaining blocked until externally calibrated parameters
and source inputs exist.

## Validation before activation

Offline deterministic tests must cover a powered positive treatment, stochastic
no-op, regression, inconclusive evidence, infrastructure invalidity, missing or
wrong-build activation, identity mismatch, partial-build rollback, interrupted
publication recovery, and proof that only `(accepted, benchmark)` advances
state. Real activation additionally requires the existing ADR-0004/0005/0016
preconditions, owner-supplied external inputs, and explicit campaign
authorization.

## Owner decision gate

This proposal is nonbinding until the project owner explicitly says:

> Accept ADR-0018 as written.

An unmistakable approval of the complete substance is also valid under the
decision process. Only then, before milestones D-F implement the changes:

1. change this ADR to Accepted, fill `Date accepted`, and record the approval;
2. update the decision register and timeline; and
3. replace the nonbinding transition-proposal line in each of ADR-0005,
   ADR-0015, and ADR-0017 with an `Amended by ADR-0018` relationship and the
   acceptance date.

ADR-0018 amends those decisions rather than superseding them. ADR-0002 and
ADR-0003 remain Open.
