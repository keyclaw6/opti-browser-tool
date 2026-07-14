# Opti Browser Tool — Research Loop and Convergence Audit

## 1. Scope verdict

**Research-decision integrity and credible convergence: NO.**

The repository implements a deterministic loop shell with useful typed state, containment checks, comparison logic, and extensive control-flow tests. It does not yet implement a trustworthy adaptive research loop. In the reachable benchmark path, a command-backed or handwritten result with no usable trace can remain benchmark-eligible; E1 can pass with dynamic activation pending; only the E5 treatment receives the full eligibility assessment; and one unreplicated task flip can advance the accepted base. Those defects permit an inert, synthetic, or lucky candidate to be accepted.

No real benchmark bridge, admitted production verifier, stochastic browser run, real Analyst, hidden holdout, or identity-bound transfer experiment was exercised. Claims requiring those are **NOT VERIFIED**. Deterministic fixtures establish plumbing, not research validity.

Evidence-state summary:

- **verified-real:** none in this review.
- **implemented-unverified:** final-diff containment, paired status comparison, typed gate/verdict records, queueing, and deterministic T1 checks.
- **simulated-only:** all observed loop and judge test evidence, including the command/hash end-to-end bridge.
- **documented-only or missing:** real Analyst execution, trustworthy cluster creation, dynamic treatment activation, executable repeat design, calibrated statistical thresholds, hidden holdout scheduling, and bound transfer experiments.
- **contradicted:** E1's stated trace-backed activation invariant and fail-closed benchmark eligibility.

## 2. Reviewed SHA and test result

- Reviewed base SHA: **6cad1f09e0a1bf3f5a1a850bbd51d5a1600d585c**
- Audit target: that commit plus the pre-existing review-prompt/documentation working-tree snapshot supplied to this review; no pre-existing file was changed by this audit.
- Compact test batch: PYTHONDONTWRITEBYTECODE=1 make loop-test judge-test
- Result: **45 passed** — loop harness 26/26 and judge harness 19/19.
- Real-environment result: **NOT VERIFIED**.

Three focused diagnostics reproduced decision-boundary defects:

1. Missing and malformed trace inputs both produced acceptance_eligible=true, evidence_class=benchmark, and zero T1 flags.
2. The example experiment fails runtime validation because target_component and cluster_ref are absent, while those runtime-required fields and attribution are forbidden by the canonical schema's additionalProperties=false shape.
3. evaluate_checkpoint({"not-in-pinned-panel": 1.0}) returned transfer_supported, demonstrating that transfer values are not bound to an experiment, task set, model, or run.

## 3. Causal-loop map

| Arrow | Enforcing code and trusted boundary | State | Coverage and dominant error mode |
|---|---|---|---|
| Real failure trace → Analyst report | loop_harness/src/opti_loop/analyst.py:43-73 describes source/status extraction; loop_harness/src/opti_loop/conductor.py:128-136 instantiates StubAnalyst. | **missing** for real analysis; stub is **simulated-only** | No real trace-to-event-addressable diagnosis was run. A sparse or synthetic status can become an analysis input; a real causal divergence can be missed. |
| Analyst report → failure cluster | loop_harness/src/opti_loop/clusters.py:68-90 creates unclassified/unassigned clusters without event membership; conductor.py:138-147 consumes them. | **simulated-only** | Unit plumbing exists, but no tested evidence binds cluster membership, priority, component, or lifecycle to trace events. Fake or renamed clusters can steer work. |
| Failure cluster → optimizer packet | conductor.py:145-147 and loop_harness/src/opti_loop/packet.py:27-49 serialize ranked cluster data; packet.py:91-96 adds a ledger tail to the Markdown packet. | **implemented-unverified** | Packet generation is deterministic, but its inputs inherit stub analysis and unchecked cluster facts. |
| Optimizer packet → manifested hypothesis | loop_harness/src/opti_loop/manifest.py:27-175 performs runtime checks; schemas/experiment.schema.json:6-21 is the nominal contract. | **contradicted** | Runtime, schema, example, and program do not share a valid shape. The optimizer supplies cluster, trace, prediction, and activation assertions that are not resolved to trusted records. |
| Manifested hypothesis → candidate commit | loop_harness/src/opti_loop/fileguard.py:97-118 checks the final base-to-candidate diff; gitutil.py:53-66 exposes commit/diff helpers. | **implemented-unverified** | Allowed-file tests pass, but exact one non-merge, non-empty commit is not enforced. Zero, multi-commit, merge, empty, and net-zero histories can satisfy the final-diff rule. |
| Candidate commit → activation evidence | loop_harness/src/opti_loop/registration.py:58-90 checks static file registration; gates.py:122-133 allows E1 to pass while dynamic evidence is pending. | **contradicted** | The accepted end-to-end path indirectly exercises static registration, with no dedicated negative test. No candidate-bound execution event is required, so disabled, shadowed, unreachable, or inert treatment code can proceed. |
| Activation → smoke/target/regression/full evaluation | gates.py:135-195 calls the configured suites once; conductor.py:107-116 obtains a fresh baseline. | **simulated-only** | The deterministic accepted end-to-end path traverses the rungs once. There is no reset identity, randomization, interleaving, seed policy, or repeat confirmation. |
| Evaluation → benchmark eligibility | loop_harness/src/opti_loop/eligibility.py:47-171 and judge_harness/src/opti_judge/evidence.py:20-28,88-96 assess admission and T1 evidence. | **contradicted** | Missing/malformed traces and absent judge integration are skipped, not invalidated. The loader's required-field check also fails to enforce schema_version, timestamp, monotonic_ms, and artifact_refs required by the trace schema. |
| Eligibility → comparison | loop_harness/src/opti_loop/compare.py:66-131 compares task status; gates.py:183-208 applies eligibility only to treatment. | **implemented-unverified**, asymmetrically | Strict/quorum behavior has deterministic tests. Baseline, E4, smoke, and noise can influence the verdict without equivalent admission/T1 checks. |
| Comparison → attribution | loop_harness/src/opti_loop/attribution.py:56-79 intersects predicted task IDs with observed flips. | **simulated-only** | Exact ID plumbing works, but motivating cluster, mechanism, activation, and E3/E5 continuity are unbound. An unrelated lucky flip can be credited. |
| Attribution → typed verdict | gates.py:224-253 and loop_harness/src/opti_loop/verdict.py:19-20 create accepted/rejected/invalid decisions. | **implemented-unverified** | Deterministic states are recorded, but the decision vocabulary omits the charter's inconclusive outcome and accepts one noisy flip. |
| Verdict → accepted base/regression/learnings | conductor.py:267-294 advances base/counters; conductor.py:334-341 and loop_harness/src/opti_loop/ledger.py:33-52 persist placeholder learnings. | **implemented-unverified** | State transactions are tested, but invalid runs consume hypothesis attempts; regression memory is replaced by a fresh one-run baseline; learning fields are not required to contain causal evidence. |
| Accepted base/regression/learnings → next packet | conductor.py:93-96 warns about prior state and packet.py:91-96 renders a ledger tail. | **partial** | There is no demonstrated adaptive hypothesis update. Accepted code accumulates, but measured capabilities, verified causal learnings, and champion/ancestor comparisons do not. |

**Classification:** a deterministic loop shell, not a functional adaptive loop and not merely a paper contract.

## 4. E0–E5 matrix

| Rung | Invariant and inputs | Current deterministic decision | Invalid versus rejected | Positive evidence | Reachable bypass or false rejection |
|---|---|---|---|---|---|
| **E0 containment/generality** | Candidate final diff must be clean, manifest-scoped, component-allowed, and lint-clean. fileguard.py:97-118; lint.py:19-21,80-94. | A GuardError is invalid; a normal guard violation, manifest error, or lint finding is rejected; an allowed final diff passes (gates.py:93-119). | Only exceptional guard failure is invalid; ordinary structural candidate defects consume a rejection. | Unit tests exercise clean/dirty and allowed/disallowed paths. | Commit cardinality and parentage are not checked; manifest facts are self-asserted; deleted/renamed registered files cannot pass; lint detects literal catalog vocabulary but explicitly cannot establish semantic/site generality. |
| **E1 activation** | Static registration and candidate-bound dynamic execution must both hold. registration.py:58-90; gates.py:122-133. | Static registration can pass while dynamic activation is merely pending. | Registration error is invalid; missing dynamic execution is not. | The accepted end-to-end path indirectly exercises static registration; no dedicated registration-failure or dynamic-activation test. | Inert, disabled, shadowed, unreachable, or spoofed treatment proceeds. This directly contradicts the accepted activation requirement. |
| **E2 smoke** | A valid smoke run must avoid behavioral collapse. gates.py:135-146. | One run; invalid run becomes invalid, otherwise a fixed collapse rule rejects. | Infrastructure invalidity is distinguished here. | The accepted end-to-end path traverses E2 once; no dedicated collapse/invalid rung test. | Threshold is not empirically calibrated; no repeat or symmetric evidence-integrity check; stochastic good changes can be rejected and lucky bad changes pass. |
| **E3 targeted screen** | Predicted tasks should flip under the activated mechanism and later reappear in E5. gates.py:148-165. | One screen of manifest-supplied task IDs; any observed predicted flip passes; no target skips. | run_valid is not checked before no-flip rejection. | The accepted end-to-end path exercises a deterministic predicted flip; no dedicated E3 invalid/no-flip rung test. | Arbitrary task IDs need not belong to the motivating cluster; E3 and E5 need not flip the same predicted task; infrastructure failure is counted as behavioral rejection. |
| **E4 regression** | Accepted, repeatedly stable capabilities must remain passing under admissible evidence. gates.py:167-181. | One treatment regression run is compared with one freshly sampled baseline's passed tasks. | Invalid run becomes invalid; a new failure rejects. | The accepted end-to-end path exercises E4 pass; no dedicated new-regression/invalid rung test. | Denominator is not an admitted, repeated, durable capability registry; no T1/admission/quarantine check is applied; a baseline miss drops protection, while a fixture pass can add it. |
| **E5 full comparison** | Same-identity valid baseline/treatment, complete predicted fixes, aggregate non-inferiority, regression bound, bound noise, and benchmark evidence. gates.py:183-253; compare.py:66-131. | One strict/quorum paired status table plus treatment eligibility and configured noise thresholds. | Comparison/noise ineligibility is invalid; treatment non-reportability or failed admission downgrades the verdict to simulated; behavioral conditions reject. | Component tests cover strict/quorum comparison and attribution; end-to-end tests cover acceptance, simulation, and shotgun behavior, not a full E5 condition matrix. | Baseline is unaudited; treatment-only evidence class controls the pair; one flip is enough; repeat config is unused; stale noise and changing denominators are possible; local non-inferiority allows cumulative drift. |

Registration and boundary detail: the optimizer can edit the target component's component.json and use it to self-register any new existing file inside that same component; check_tree trusts the candidate list and check_change_registered exempts component.json itself (registration.py:58-67,71-90). Manifest prefix checks and the final-diff guard block cross-component paths, but no finer file authority exists. The manifest's activation_evidence is likewise an unresolved optimizer assertion, so neither self-registration nor that field proves execution.

Case disposition:

| Case | Current disposition | Reason |
|---|---|---|
| No, malformed, or incomplete trace | **Permitted as benchmark evidence** | eligibility.py:134-154 skips absent/malformed evidence; the focused diagnostic returned benchmark eligibility. |
| Admitted-looking verifier with missing T1 evidence | **Permitted** | Admission identity is weak and absence of usable T1 is fail-open. |
| Infrastructure error | **Mixed and unsafe** | E2/E4/E5 can return invalid, but E3 can reject; every non-advance, including invalid/simulated, increments failed-attempt state in conductor.py:267-290. |
| Inert treatment | **Permitted to reach acceptance** | E1 allows activation pending. A lucky one-run flip can satisfy E3/E5. |
| Seeded regression | **Blocked only if visible once** | A single exact pass-to-fail in the current baseline denominator blocks; there is no confirmation, stable registry, or injection evidence. |
| Shotgun prediction | **Partially blocked** | A high precision setting is tested, but the default minimum precision of 0.1 permits one flip among ten predictions. |
| Lucky unrelated flip | **Permitted** | Task, cluster, activation, and mechanism are not causally bound. |
| Aggregate gain with no predicted fix | **Blocked** | E5 requires at least one verified predicted flip. |
| Predicted fix with net degradation | **Blocked beyond configured noise; permitted within it** | Local aggregate/regression tolerances apply only against the immediate baseline. |
| Fixture/nonreportable result relabeled benchmark | **Permitted through the command path** | Command results are intrinsically reportable and may omit a verifier/trace; the repository end-to-end test uses a deterministic hash command. Native fixture metadata is blocked, but that does not close this route. |
| One real positive-control improvement | **NOT VERIFIED** | No real browser positive control with candidate-bound activation and admitted trace evidence exists in the test corpus. |

## 5. Evaluator T0–T3 matrix

| Tier | Required closure | Implemented behavior | State and bypass |
|---|---|---|---|
| **T0 verifier admission** | Six blinded probes; identity must cover verifier code, dependencies, command, environment, task configuration, and version; repair revokes admission. | judge_harness/src/opti_judge/probekit.py:74-82,105-113,148-200,225-229 implements six probe kinds, missing-probe rejection, filename blinding, and an archive record. | **simulated-only/partial.** The checksum covers caller-selected files, not the whole executable bundle. AdmissionRecord has no version. The CLI prints a result rather than atomically admitting it (judge_harness/src/opti_judge/cli.py:114-130), tests hand-write admission, the malformed probe accepts error as well as invalid and all probes ignore reward semantics, and verifier-defect resolution does not revoke admission (quarantine.py:119-166). |
| **T1 deterministic checks** | No-action pass, mutation/side effects, action/loop/stale-epoch/expected-state anomalies; missing/malformed evidence invalid; FP/FN route without score override. | judge_harness/src/opti_judge/t1_checks.py implements the named checks; router.py routes false-positive/false-negative/side-effect families; evidence.py loads a reduced event shape. | **implemented-unverified and fail-open at integration.** The informational action-count flag and, critically, suspicion-level loop and missing-final-state anomaly flags are not router families (t1_checks.py:104-149,192-203; router.py:35-37). Missing/malformed traces and missing judge module are skipped. T1 does not directly override score, but an unrouted suspicion or absent evidence also does not invalidate benchmark evidence. |
| **T2 LLM flaggers** | Trust must bind benchmark, role, prompt, model/provider/snapshot, settings, evidence contract, corpus version/split, and operating point; untrusted output inert. | judge_harness/src/opti_judge/corpus.py:49-78,96-168 implements narrow task/run deduplication and role-level fixture measurement; panel.py:83-111,136-170 runs roles and records model provenance; llm.py:33-45,84-95 supports model overrides. | **simulated standalone.** Trust is pooled by role ID, so a different model/prompt can inherit calibration. Narrow task_id/run_ref deduplication exists, but no held-back split, corpus version/drift policy, or benchmark-scoped operating point is enforced. Direct page evidence is prompt-injection exposed. T2 is not called by E5; panel CLI output is not fed into the loop queue. |
| **T3 quarantine** | Unresolved disputes never alter scores; family-wide denominator effects and owner resolution are auditable; repairs feed calibration and re-admission. | judge_harness/src/opti_judge/quarantine.py:119-166 and panel.py:186-220 queue/adjudicate cases; compare.py:75-90,104-131 can exclude quarantined tasks. | **implemented-unverified and disconnected from full closure.** Corpus is optional, resolver identity/authority is not bound, repair does not invalidate T0, E4 ignores quarantine, and removing a task changes the comparison denominator. T1 auto-routing can queue; T2 is not connected. panel.py:198-213 labels even an untrusted disagreement for quarantine while router.py:39-45 requires trust; the panel CLI does not enqueue it, so this inconsistency does not currently mutate loop state. |

T0–T3 therefore exists as useful library plumbing, not as an end-to-end benchmark evidence closure. A successful E5 treatment does not prove that its baseline, treatment, regression, smoke, and noise observations all passed the same admitted verifier and T1/T2/T3 policy.

## 6. Statistical and convergence assessment

### Estimand actually implemented

The implemented primary quantity is a **single-run difference in strict binary task success**, plus exact task-level pass/fail flips. It is not an estimate of the change in task success probability across independent resets. The comparison is paired only by task label; baseline is collected first and treatment later, after intervening E2–E4 work. There is no randomized/interleaved order, reset identifier, seed schedule, or covariance/discordance estimate.

The nominal repeat setting in loop_harness/src/opti_loop/campaign.py:43-44 is not consumed by the gate. E2, E3, E4, and E5 each call their suite once (gates.py:135-185). No confidence interval, sequential boundary, multiple-testing correction, declared minimum detectable effect, or power target controls acceptance.

### Quantified false-positive and sensitivity illustration

Suppose, illustratively, that an unchanged task passes independently with probability 0.55. The probability that the baseline fails while both the E3 and E5 treatment observations pass is 0.45 × 0.55² = **13.6%** for one prediction. Across ten opportunistic predictions, the chance of at least one such pattern is about **76.9%**, before applying other gates. This is not an estimate of the project's real task variance; it demonstrates why one raw flip is not confirmation. Actual per-task reset variance and E3/E5 dependence are required.

For an independent Bernoulli task with p=0.55 and 140 tasks per arm, the rough standard error of a difference is 0.0595, corresponding to an approximately **16.6 percentage-point** two-sided 5%/80%-power detectable effect. With 20 tasks it is roughly **44 percentage points**. True pairing can improve this materially, but the repository does not measure discordant-pair rate or within-task correlation. Therefore sensitivity to a plausible small improvement is **NOT VERIFIED**.

### Noise and identity

conductor.py:60-71 hashes suite labels, adapter configuration, fixed-variable strings, and the full task-catalog bytes. It does not bind suite-manifest contents/resolved task selection, base or harness SHA, runtime/environment image, browser, bridge contents, model snapshot/settings, budgets, verifier/admission set, judge configuration, quarantine state, or decision thresholds. compare.py:150-224 permits as few as two noise samples and carries no base SHA/run timestamp; aggregate margin uses max-minus-min, but the task-flip bound compares every later run only with the first rather than the maximum pairwise disagreement. An accepted new base does not force remeasurement.

acceptance_decision_eligible — validity plus adapter/result reportability — is the only noise-run integrity input (conductor.py:345-357); T0 admission and T1 closure are not checked. Benchmark E5 rejects a band explicitly labeled synthetic (gates.py:213-216), but a contaminated command-backed/no-T1 band can remain non-synthetic. A comparison's simulated flag also does not itself make the comparison ineligible (compare.py:66-69,93-103). Thus contaminated apparently benchmark-grade noise can affect benchmark advancement, while synthetic noise affects simulated verdicts only.

### Adaptive search and convergence

Repeated visible-suite iteration creates unbudgeted multiple comparisons, optional stopping, winner's curse, and selective prediction. Changing invalid/quarantine denominators and environment nonstationarity compound both type-I and type-II error. There is no campaign-horizon no-op false-acceptance bound.

The documented “two five-iteration windows inside noise” stopping concept is not executable. State tracks iterations since acceptance and local failure counters, not two comparable five-iteration effect windows. Even if implemented literally, it could not distinguish true diminishing returns from a blind Analyst, inactive treatment, underpowered gate, broken optimizer, or exhausted budget without positive controls and sensitivity checks.

Parallel-campaign comparability is **implemented-unverified and incomplete**: compare_campaigns hashes suite label, executor, adapter, and fixed variables, then compares historical accepted-treatment scores rather than running a fresh shared evaluation (conductor.py:367-400). It avoids a per-iteration race, but does not bind the full evaluation identity or temporal conditions. Mechanism transplantation is only a note in that report; it must be manually manifested through the receiving gate and has no executable receiving re-evaluation workflow beyond the same defective E0–E5 path.

Most likely false-improvement path:

1. Stub analysis yields an unchecked or renamed cluster.
2. The optimizer predicts one or more visible tasks and makes an inert or site-specific allowed edit.
3. E1 records static registration while dynamic activation stays pending.
4. One noisy task fails in baseline and passes in E3/E5; missing trace/T1 remains benchmark-eligible.
5. Stale noise tolerates aggregate churn and the candidate advances.
6. The cluster is renamed or visible predictions change, repeating adaptive selection without holdout pressure.

Most likely false-rejection/non-discovery path:

1. A small class-wide improvement has no single deterministic task flip, or requires a neutral cross-component prerequisite.
2. One-shot E3/E5 misses the effect; an infrastructure error counts against the hypothesis.
3. Two failures force a pivot, while the one-component immediate-flip rule prevents the enabling step.
4. Stub analysis and placeholder learnings do not generate a better causal hypothesis.

## 7. Findings

### CONV-001 — P0 — Missing trace and dynamic activation can still produce an accepted benchmark iteration

**Evidence.** The command adapter marks results reportable by construction (eval_harness/src/opti_eval/adapters/command.py:15-20); summary construction remains reportable when verifier metadata is absent (eval_harness/src/opti_eval/summary.py:22-28). E1 passes with dynamic activation pending (loop_harness/src/opti_loop/gates.py:122-133). Eligibility skips absent, malformed, or unavailable judge evidence and returns benchmark class (eligibility.py:112-118,134-154). Its required-field validator does not enforce schema_version, timestamp, monotonic_ms, or artifact_refs required by schemas/trace-event.schema.json:6-18 (judge_harness/src/opti_judge/evidence.py:20-28,88-96). Even a present trace can escape closure: loop_detector and missing-final-state checks emit suspicion-level direction=anomaly flags (t1_checks.py:121-149,192-203), but router.py:35-57 routes only fp_suspect, side_effect, or fn_suspect; eligibility merely counts the unrouted flags and still returns benchmark. The end-to-end test's “bridge” is a deterministic hash command with handwritten admission and no real trace, yet advances the base (loop_harness/tests/test_e2e_loop.py:34-49,87-101,131-152).

**Expected versus actual and impact.** Accepted ADR behavior requires candidate-bound dynamic execution and fail-closed T1 evidence. Actual code permits synthetic, inert, or unsafe code to be called benchmark evidence and accepted after a lucky result.

**Smallest fix.** Require a registered production bridge, per-result admitted verifier identity, schema-valid trace/T1 receipt for every result in every acceptance-affecting run, and an activation event binding component, candidate SHA, and executed path. Missing/invalid evidence must make the rung invalid.

**Regression test.** Convert the current no-trace end-to-end case to an invalid/no-advance negative test; add malformed, incomplete, inert, and shadowed negatives. A passed verifier paired with a loop-suspicion or required-final-state-missing trace must quarantine/invalidate. Add one real-bridge positive control.

### CONV-002 — P0 — Baseline, E4, smoke, and noise evidence are audited less strictly than E5 treatment

**Evidence.** The conductor records baseline and regression memory directly (conductor.py:107-116); E2–E4 use raw suite outputs (gates.py:135-181); only E5 treatment calls the eligibility assessor (gates.py:183-208). Noise uses acceptance_decision_eligible without T0/T1 assessment (conductor.py:345-357). compare.py:66-69,93-103 can mark a comparison simulated without making it ineligible, and E4's denominator is just the current baseline's passed statuses (gates.py:173-177).

**Expected versus actual and impact.** Every observation affecting acceptance should satisfy the same verifier/trace/run-identity policy. A false or nonreportable baseline, regression, or noise observation can currently manufacture a treatment improvement or tolerance.

**Smallest fix.** Apply one symmetric run-integrity assessment to baseline, treatment, smoke, targeted, regression, and every noise sample; classify the comparison by its weakest evidence and invalidate mixed classes.

**Regression test.** A nonreportable or T1-missing baseline paired with a valid treatment must be invalid; repeat for E4 and noise. A fully admitted pair remains eligible.

### CONV-003 — P0 — One unreplicated raw flip allows a no-op to win adaptive search

**Evidence.** campaign.py:43-44 declares repeats but the value is unused. gates.py:135-185 runs each suite once. attribution.py:56-79 credits set intersection, while gates.py:224-253 accepts one predicted flip with default prediction precision 0.1 and immediate local non-inferiority. E3 and E5 need not reproduce the same predicted flip.

**Expected versus actual and impact.** A causal, repeatable improvement should change a prespecified estimand with adequate confirmation. Here a noisy no-op can be selected after repeated visible-suite attempts. The illustrative no-op calculation in Section 6 reaches 13.6% for one task pattern and 76.9% across ten opportunities.

**Smallest fix.** Execute k paired repeats with reset identity, randomized/interleaved order, confidence bounds, a prespecified minimum effect, and a campaign-level sequential/multiple-testing policy. Require the same predicted causal effect to replicate in full evidence.

**Regression test.** Run a seeded stochastic no-op across the allowed campaign horizon and enforce a declared false-acceptance bound; add seeded positive controls at the minimum supported effect and verify target power.

### CONV-004 — P0 — T0 admission is not bound to the production verifier and is not revoked after repair

**Evidence.** AdmissionRecord has no version (judge_harness/src/opti_judge/probekit.py:74-82). Its checksum covers caller-supplied files only (probekit.py:105-113,184-200), omitting command, dependency closure, environment, task configuration, and explicit version. Eligibility trusts an admitted record for the verifier_id/task_id pair plus a matching caller-supplied checksum (loop_harness/src/opti_loop/eligibility.py:47-98). The probe CLI prints but does not atomically append admission (judge_harness/src/opti_judge/cli.py:114-130); the end-to-end test hand-writes it. Verifier-defect resolution does not invalidate admission (quarantine.py:119-166); the malformed probe permits error as well as invalid, and all probes classify status/side-effect fields without validating reward semantics (probekit.py:148-180).

**Expected versus actual and impact.** Admission must describe the exact executable verifier bundle that scored a result. A different or repaired verifier can inherit old admission and create evaluator corruption.

**Smallest fix.** Have the conductor compute and transactionally store a full verifier-bundle identity, bind every result to it, and revoke/re-probe on any verifier-defect repair.

**Regression test.** Mutating command, dependency, environment, task configuration, or version must invalidate admission; resolving verifier_defect must block benchmark use until all six probes pass again.

### CONV-005 — P1 — No experiment manifest can satisfy both the canonical schema and runtime validator

**Evidence.** schemas/experiment.schema.json:6-21 requires its declared shape and forbids extra fields, but omits target_component, cluster_ref, and attribution. Runtime validation requires target_component and cluster_ref (loop_harness/src/opti_loop/manifest.py:27-44), rejects optimizer-supplied attribution (manifest.py:163-166), and the conductor appends attribution after evaluation (conductor.py:235-241), making the enriched snapshot schema-invalid. examples/experiment.example.json:1-67 lacks the runtime-required fields. PROGRAM.md:41-45 acknowledges a pending schema revision, while scripts/validate_json_schemas.py:41-46,62-87 does not load the experiment schema.

**Expected versus actual and impact.** One canonical manifest should pass producer, schema, and runtime validation. Instead, a schema-valid producer fails runtime, while a runtime-valid object is schema-invalid, preventing a reliable optimizer-to-conductor handoff.

**Smallest fix.** Publish one canonical schema matching runtime fields, reserve attribution for conductor append only, validate it at runtime, and update the example.

**Regression test.** Feed the same valid/invalid corpus through JSON Schema and runtime validation and require identical outcomes.

### CONV-006 — P1 — Infrastructure invalidity can become behavioral failure and force a pivot

**Evidence.** E3 does not inspect run_valid before rejecting no flip (gates.py:151-161). All non-advancing verdicts, including invalid and simulated, increment failed-attempt state (conductor.py:267-290); two attempts trigger pivot logic (conductor.py:204-211). Verdict decisions omit the charter's inconclusive state (loop_harness/src/opti_loop/verdict.py:19-20; PROJECT_CHARTER.md:43).

**Expected versus actual and impact.** Infrastructure-invalid or inconclusive observations must be inert to a hypothesis's behavioral record. Current behavior can exhaust or pivot away from a genuinely good treatment without evidence about it.

**Smallest fix.** Add inconclusive, make E3 invalid on invalid runs, and increment hypothesis/divergence/plateau counters only for valid, activated behavioral rejections.

**Regression test.** Two infrastructure failures followed by a valid run must not force a pivot or consume the hypothesis attempt budget.

### CONV-007 — P1 — Registered component deletion and rename cannot satisfy E0

**Evidence.** registration.py:58-62 requires every registered path to exist in the candidate and registration.py:79-90 requires all changed paths in candidate registration. gitutil.py:58-66 decomposes renames into delete/add paths.

**Expected versus actual and impact.** A causally narrow cleanup, replacement, rollback, or rename inside one component should be representable. Deleting a registered defect or renaming its implementation is invalid even when containment is correct.

**Smallest fix.** Validate deleted paths against base registration and present paths against candidate registration, while keeping the one-component boundary.

**Regression test.** Add allowed deletion and rename cases, plus cross-component and unregistered deletion negatives.

### CONV-008 — P2 — Exact commit and trusted manifest attribution are not enforced

**Evidence.** gitutil.commits_between exists but is unused (gitutil.py:53-55); fileguard.py:97-118 checks ancestry/final diff only. A candidate equal to base passes a unit guard (loop_harness/tests/test_units.py:78-83). manifest.py:88-175 mostly validates presence/path relationships; normal cluster references, trace evidence, predicted tasks, baseline_ref, fixed variables, evaluation plan, and activation assertions are not resolved to conductor-owned facts. Only a divergent-prefix cluster has a special check (manifest.py:136-148).

**Expected versus actual and impact.** The loop's causal unit is exactly one non-merge, non-empty commit against a stamped base, motivated by an existing cluster and trace. Zero, multiple, merge, empty, net-zero descendant histories, causally unrelated allowed diffs, and self-asserted evidence can currently satisfy the contract, breaking attribution. A non-descendant history is correctly rejected.

**Smallest fix.** Enforce candidate parent=base, exactly one non-merge commit, and a non-empty tree delta. Conductor-stamp campaign/base/candidate and resolve trace, cluster, task, component, scope, and activation IDs from trusted stores.

**Regression test.** Reject zero/two/merge/empty/net-zero histories, fake clusters, wrong base, unrelated predicted tasks, and optimizer-written activation; accept one correctly bound commit.

### CONV-009 — P2 — Run identity is incomplete and permits stale or contaminated noise

**Evidence.** conductor.py:60-71 omits most identity-bearing contents beyond adapter/configured labels, fixed variables, and catalog bytes. campaign.py:28-32 pins descriptions rather than resolved artifacts. compare.py:150-224 permits two samples, lacks base/run IDs, and compares every later sample only with the first for the flip-count bound; its aggregate margin does use max-minus-min. Acceptance does not invalidate the noise estimate (conductor.py:267-294).

**Expected versus actual and impact.** Noise must characterize the same task, runtime, evaluator, policy, and accepted base as the comparison. Stale or inflated noise can excuse regressions; stale narrow noise can reject real improvements.

**Smallest fix.** Hash canonical contents for all identity-bearing inputs, bind noise to accepted base and admitted evaluator set, audit every sample, use a defined interval/pairwise estimator, and remeasure on any identity/base change.

**Regression test.** Mutate each identity input and require invalidation; include a three-run case where the largest pairwise drift does not involve the first sample.

### CONV-010 — P2 — Accepted code accumulates, but durable capabilities do not

**Evidence.** Each iteration replaces regression memory with one fresh baseline run (conductor.py:107-116). E4 protects only tasks passing that observation (gates.py:167-181). Accepted statuses are saved and then replaced next start (conductor.py:274-279). Fixes enter promotion_candidates (conductor.py:243-264), but automatic promotion is explicitly off (loop_harness/README.md:28-31). E5 permits a local decrease within the same noise margin at each ancestor step (gates.py:235-247).

**Expected versus actual and impact.** Repeatedly admitted capabilities and meaningful champions/ancestors should remain protected. A transient baseline miss silently drops a capability, and locally tolerated losses can compound into a random walk.

**Smallest fix.** Maintain a monotonic, evidence-backed regression registry with drift/quarantine handling and compare candidates to immediate base plus declared champion/ancestor checkpoints.

**Regression test.** A promoted repeatedly passing task must remain protected after a single baseline miss; multiple individually tolerated steps must be rejected when cumulative champion degradation exceeds the bound.

### CONV-011 — P2 — Stub analysis and unchecked clusters cannot drive adaptive learning

**Evidence.** conductor.py:128-136 hardcodes StubAnalyst. analyst.py:43-73 extracts source/status without event-addressable causal claims. clusters.py:68-90 emits unclassified/unassigned clusters without member events, yet conductor.py:145-147 ranks them. manifest.py:136-148 validates only a special divergent prefix; a caller-supplied fingerprint drives repeat policy (conductor.py:207-210). Learnings are placeholder fields (ledger.py:33-52; conductor.py:334-341) and are not required to explain the next hypothesis.

**Expected versus actual and impact.** A real iteration should target a reproducible, highest-priority trace-backed cluster and update causal memory. Stub/fake/renamed clusters can instead steer visible-task experimentation, bypass repeat policy, and produce no useful next hypothesis.

**Smallest fix.** Block benchmark campaigns while the Analyst is a stub; bind cluster membership, priority, component, status, and fingerprint to trace events; require complete learning records before the next packet.

**Regression test.** Reject fake, renamed, non-top, wrong-component, and eventless clusters; verify a real trace's earliest divergence produces a stable cluster and a causally updated next packet.

### CONV-012 — P2 — T2 trust is role-wide, pooled, and disconnected from E5

**Evidence.** corpus.py:49-78,96-147 narrowly deduplicates task_id/run_ref but identifies calibration primarily by role ID. panel.py:136-170 permits model override and then measures the role; llm.py:33-45,84-95 records provenance but allows environment/model changes. E5 does not invoke T2 (gates.py:23-29,183-204), eligibility's T1 route contains no panel judgment (eligibility.py:165-171), and the panel CLI only prints results (judge_harness/src/opti_judge/cli.py:158-175). Corpus balance is minimal and has no enforced held-back/drift/version split (corpus.py:159-168). The standalone panel labels even untrusted disagreement for quarantine (panel.py:198-213), while router.py:39-45 uses only trusted disagreement; because the panel CLI does not enqueue, this inconsistency does not currently mutate loop state.

**Expected versus actual and impact.** Trust should attach to the exact judge system and its held-back operating point. Today T2 provides no closure; if connected naively, a changed model, prompt, or evidence contract could inherit trust, including prompt-injected page evidence.

**Smallest fix.** Key trust by benchmark/role/version/prompt/model/provider/snapshot/settings/evidence contract/corpus split and version; connect panel → router → quarantine; make untrusted output state-inert consistently.

**Regression test.** A calibrated role with changed model, prompt, provider family, settings, or evidence contract must be untrusted; only the exact held-back-calibrated identity may route.

### CONV-013 — P2 — Generality, holdout, and transfer evidence are not implemented

**Evidence.** lint.py:19-21 acknowledges residual semantic/site leakage and its vocabulary scan covers task/source/upstream-host literals, not the full site/goal semantics (lint.py:80-94). campaign.py:123-145 and store.py:68-125 provide no hidden holdout initialization or schedule. transfer.py:28-64 stores a prose plan without SHAs/task/model identities; evaluate_checkpoint accepts any non-empty numeric mapping and returns a median-based decision (transfer.py:67-85). The focused arbitrary-key diagnostic returned transfer_supported.

**Expected versus actual and impact.** Holdout and transfer must be discovery-insulated and bound to the exact treatment, base, tasks/sites, models, repeats, uncertainty, environment, admission, and cost. Visible-suite overfit or arbitrary external numbers can currently masquerade as generalization.

**Smallest fix.** Add an owner-controlled holdout attestation/scheduler and a structured, identity-bound transfer result manifest with paired repeated estimates and uncertainty.

**Regression test.** Unknown model keys, one-off/unbound deltas, mismatched SHAs/tasks/environments, and discovery-exposed tasks must be insufficient; bound positive and sign-reversal controls must decide as specified.

### CONV-014 — P2 — Immediate one-component task-flip policy can trap the loop at a local optimum

**Evidence.** manifest.py:109-134 enforces one component, while gates.py:227-247 requires an immediate predicted verified task flip. There is no bounded staged-enabling or compound-mechanism exception. A failure-class-only prediction can pass manifest validation (manifest.py:150-175) but yields no E3 target and cannot satisfy E5.

**Expected versus actual and impact.** Narrow causal units are valuable, but some contract-spanning mechanisms require a neutral prerequisite or irreducible observation/action pair. The present policy rejects these before their effect can exist and encourages naming visible task IDs rather than mechanism classes.

**Smallest fix.** Provide an owner/conductor-authorized, bounded compound or staged-enabling path that remains non-champion until the full mechanism passes all gates and ablation checks; resolve class claims from the trusted cluster.

**Regression test.** Ordinary cross-component changes remain invalid; an authorized prerequisite stays inconclusive/non-accepted until its bounded paired change produces replicated causal evidence.

### CONV-015 — P2 — Attribution is activation-agnostic, and partial attribution retains the whole candidate

**Evidence.** attribute() receives only manifest task IDs and the comparison's fixed/regressed sets; it receives no activation trace, cluster membership, changed-file identity, or mechanism evidence (loop_harness/src/opti_loop/attribution.py:56-90). A candidate with a verified predicted fix plus a regression is labeled partial (attribution.py:74-79). E5 accepts any attribution other than revert when the regression remains inside the noise band (gates.py:224-247), and the conductor advances the entire candidate SHA (conductor.py:267-279).

**Expected versus actual and impact.** Keep/partial/revert should describe the activated causal mechanism and support the promised edit-level disposition. Actual partial attribution can accept a mixed candidate wholesale, retaining an unrelated or harmful edit under a noisy tolerance.

**Smallest fix.** Until edit-level activation and rollback exist, treat the one-commit candidate as indivisible and reject partial. If partial promotion is retained later, bind conductor-owned edit IDs to activation/mechanism evidence and construct a re-gated reduced commit containing only supported edits.

**Regression test.** A two-file candidate with one replicated causal fix and one seeded regression must not advance wholesale under partial; a reduced, re-evaluated causal edit may pass.

### CONV-016 — P3 — Generated optimizer instructions contradict the executable workflow

**Evidence.** packet.py:86-88 instructs the optimizer to place the manifest in the iteration directory and run opti-loop gate, while PROGRAM.md:29-38 specifies the worktree root and run-iteration command.

**Expected versus actual and impact.** Generated instructions should invoke the actual manifest location and CLI. Following the packet can produce a missing manifest or nonexistent command, wasting an iteration but not by itself creating a wrong benchmark verdict.

**Smallest fix.** Generate the program's canonical path and command from one constant.

**Regression test.** A packet contract test should parse its command/location and successfully enter the real CLI's dry validation path.

## 8. High-risk hypothesis disposition

| # | Hypothesis | Disposition | Basis |
|---|---|---|---|
| 1 | Benchmark eligibility can survive missing or malformed trace/T1 evidence. | **HELD** | Reproduced directly; eligibility skips both. |
| 2 | E1 can pass while dynamic activation remains pending. | **HELD** | gates.py:122-133. |
| 3 | Exactly one commit is documented but not enforced. | **HELD** | Final diff/ancestry only; commit enumeration unused. |
| 4 | Runtime manifest validation disagrees with the canonical schema. | **HELD** | Reproduced on the example; runtime-required fields are schema-forbidden. |
| 5 | Baseline, E4, or noise evidence is audited less strictly than E5 treatment. | **HELD** | Only treatment runs eligibility assessment. |
| 6 | Run identity omits identity-bearing contents and permits stale noise. | **HELD** | Content omissions and no base-triggered remeasurement. |
| 7 | Judge trust is too broadly scoped or an untrusted judgment affects state. | **HELD** | Role-wide T2 trust is too broad. The standalone panel labels untrusted disagreement for quarantine but is disconnected and does not currently enqueue it. |
| 8 | Stub analysis or unchecked cluster references can steer real iterations. | **HELD** | StubAnalyst is hardcoded and normal cluster references are unresolved. |
| 9 | A single lucky flip can pass without adequate repeat confirmation. | **HELD** | One run and unused repeat setting. |
| 10 | Invalid infrastructure attempts count against a hypothesis and force pivot. | **HELD** | E3 and conductor counters reproduce this path. |
| 11 | The transfer criterion can be satisfied by unbound external deltas. | **HELD** | Reproduced with an arbitrary key/value. |
| 12 | The loop is safe against false positives but too insensitive to improve. | **DEFEATED as worded** | It is not safe against false positives. Sensitivity to a real small effect is separately **NOT TESTABLE** without reset variance, repeat design, and a real positive control. |

## 9. Positive and negative controls still required

Negative controls:

- Missing, malformed, incomplete, or schema-incompatible trace; missing judge module; missing per-result admitted verifier.
- Candidate-bound inert, disabled, shadowed, unreachable, and spoofed activation.
- Zero, two, merge, empty, and net-zero commit histories; causally unrelated allowed diffs; fake cluster/wrong base/wrong task.
- Nonreportable or unadmitted baseline with valid treatment; equivalent contaminated E4 and noise samples.
- Verifier command, dependency, environment, task configuration, and version mutation; verifier-defect repair without re-admission.
- Two infrastructure failures followed by a valid retry, which must not consume hypothesis budget.
- Confirmed seeded regression and one-off apparent regression, separated by repeats.
- Stochastic no-op across the full adaptive campaign horizon; ten-prediction shotgun.
- Literal, semantic, encoded, and site-specific visible-suite overfit checked on a discovery-excluded holdout/unseen site.
- Calibrated T2 role with model, prompt, settings, provider family, evidence contract, and corpus-version substitutions.
- Unbound transfer values, wrong SHA/task/model/environment, and single-run deltas.

Positive controls:

- One real browser treatment whose causal mechanism, candidate SHA, component execution, admitted verifier, T1 trace, predicted class/task, and effect are known end to end.
- Seeded effects around 2, 5, and 10 percentage points to measure power and identify the smallest supported effect.
- A real no-op campaign to measure campaign-level false acceptance under the actual reset distribution.
- Identity-bound transfer with a positive effect and a sign-reversal control on the receiving model/site.
- An infrastructure repair proving the same hypothesis can resume without pivot or behavioral penalty.

The present 45 passing tests are valuable deterministic controls, but none substitute for these stochastic and real-bridge controls.

## 10. Top three changes most likely to increase real improvement probability

1. **Close evidence uniformly and require real activation.** Apply one fail-closed, candidate-bound admission/trace/T1 assessment to every baseline, smoke, targeted, regression, full, and noise observation. This removes the largest false-acceptance surface and makes later statistics meaningful.
2. **Make the statistical design executable.** Run prespecified paired repeats with reset identity and randomized/interleaved order, uncertainty and minimum-effect rules, adaptive-search error control, stable regression memory, and champion/ancestor comparison. Calibrate it with real no-op and positive controls.
3. **Replace synthetic learning with bound generalization evidence.** Use a real event-addressable Analyst and trusted cluster registry, then add an insulated holdout and identity-bound transfer record. This gives the optimizer useful causal feedback and a credible way to discover visible-suite overfit.

## 11. Cross-part handoff

Questions for Part 1:

1. Can every production bridge guarantee a schema-valid, candidate/run-bound trace and artifact receipt, with missing/malformed data mapped to invalid before summary creation?
2. Which resolved content hashes identify suite/tasks, environment/runtime image, browser/reset protocol, bridge, verifier/admission, model/settings, budgets, judge configuration, and thresholds?
3. Which production task verifiers are actually admitted, and what reset-to-reset success variance and stochastic dependence have been measured?

Questions for Part 3:

4. Can owner-only atomic state enforce admission/revocation, quarantine resolution, and trusted cluster/holdout records without optimizer mutation?
5. How will the hidden holdout be scheduled and insulated, and how will receiving transfer evidence be authenticated without leaking discovery traces?

## 12. Direct answers

**Can a bad/lucky change be falsely accepted?**

Yes. A no-trace command result can remain benchmark-eligible, E1 can pass an inert candidate, and one unreplicated predicted flip can advance the base.

**Can a small good change be detected and attributed?**

Not credibly today. It may create a raw flip, but repeat count, reset variance, power, candidate-bound activation, cluster binding, and uncertainty are absent. Detection and causal attribution of a small effect are **NOT VERIFIED**.

**Can accepted gains accumulate without visible-suite overfitting?**

No demonstrated mechanism ensures that. Code commits accumulate, but the durable regression set is replaced by a one-run baseline; holdout scheduling and bound transfer are missing; local noise tolerance can compound degradation.

**What falsifies transfer?**

A prespecified, identity-bound paired transfer experiment whose receiving-model/site effect has an upper confidence bound at or below the required benefit (or a credible sign reversal), while costs remain measured under the same protocol. The current arbitrary-delta median interface cannot credibly falsify or support transfer.

**What minimum evidence would change this part's verdict?**

At minimum: one real conforming bridge with exact T0/T1 closure on every acceptance-affecting run; candidate-bound dynamic activation; executable repeated paired statistics calibrated by a real campaign-horizon no-op and adequately powered positive control; durable regression/champion protection; a real event-addressable Analyst with trusted clusters; and an insulated, identity-bound holdout/transfer result. Those controls must both reject the reachable counterexamples above and accept a known causal improvement.
