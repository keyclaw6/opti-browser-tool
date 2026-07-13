# Review Commission — Auto-Research Machinery (adversarial)

Copy everything below this line to the reviewing agent.

---

## OPTI-BROWSER-TOOL — ADVERSARIAL REVIEW OF THE AUTO-RESEARCH MACHINERY

Repository: https://github.com/keyclaw6/opti-browser-tool (branch `main`).
You are a hostile design reviewer with full repo access. You are NOT reviewing whether auto-research is a good idea, whether the docs read well, or whether the code is pretty. You are reviewing **whether this specific machine can do the one thing it exists to do**:

> Let an optimizer LLM repeatedly modify a browser-agent harness such that (a) a bad or dishonest change cannot get accepted, (b) a good change is accepted and correctly attributed, and (c) the resulting improvements are real — not artifacts of evaluator error, noise, memorized task knowledge, or gate-gaming.

Your mission is to **falsify that promise**. A review that finds nothing is a failed review; a review whose findings lack file-level evidence is also a failed review.

### Ground rules

1. **Verify, then attack.** For every claim you assess, first locate the enforcing code/test, then actively try to defeat it. Report both the attack and the outcome.
2. **Evidence standard:** every finding cites `file:line` (or a test name), gives a reproduction sketch, a severity — `blocking` / `risk` / `debt` / `nit` — and a concrete fix. Findings without evidence will be discarded.
3. **Run things.** Python ≥3.11: `make eval-validate eval-test loop-test judge-test docs-verify`. Read the end-to-end test (`loop_harness/tests/test_e2e_loop.py`) and check it actually tests what `loop_harness/README.md` claims.
4. **No validation theater.** Praise is only useful as "attack X failed because Y (file:line)". If, after genuine effort, a mechanism holds — say so and show the failed attack. Do not invent findings to fill quota; do not soften real ones.
5. **Out of scope** (deliberate, decided by the project owner — do NOT report as findings): the five benchmark bridges are unbuilt; the browser-control landscape research (ADR-0003) is deferred; judge/executor model pins are open (OQ-17); numeric thresholds are placeholders awaiting measurement; there is no CI. What IS in scope: whether the *stated* limitations are stated correctly, and whether anything claimed as enforced is actually only promised.

### Read order (~60–90 min)

`PROJECT_CHARTER.md` → `docs/DECISION_PROCESS.md` → ADR-0015, ADR-0016, ADR-0005, ADR-0004 (all Proposed — check they never claim acceptance) → `PROGRAM.md` → `loop_harness/README.md` + `loop_harness/src/opti_loop/` → `judge_harness/README.md` + `judge_harness/src/opti_judge/` → `harness/` + `docs/architecture/COMPONENT_TREE.md` + `ANALYST.md` → `evals/judges/roles/*.json` → both test suites.

### The eight load-bearing claims — attack each one

1. **Containment.** Claim: the optimizer can only write `harness/components/**` (git file guard, E0). Attack: symlinks into the eval plane; edits smuggled via `component.json`; `.gitignore` manipulation to hide files from `ls-files --others`; path traversal in manifest `change_scope`; abuse of the gitignored `campaigns/` surface (packet/manifest injection into conductor parsing); rollback as a write primitive (`conductor.rollback_iteration` deletes untracked files — can scope make it delete something it shouldn't?).
2. **Generality lint.** Claim: benchmark-token knowledge can't ship (`opti_loop/lint.py`, catalog-derived vocabulary). Attack: paraphrased task knowledge, encoded strings, URL fragments or CSS selectors unique to benchmark sites, site-specific logic keyed on page titles rather than source tokens, knowledge placed in files the lint never scans. Is the vocabulary actually derived from the live catalog, and what escapes it *structurally*?
3. **Gate soundness (E0–E5).** Claim: a change is accepted only with ≥1 verified predicted flip, regressions within a measured noise band, and non-inferior aggregate (`opti_loop/gates.py`). Attack: can `invalid` be laundered into `rejected` or vice versa (they have different epistemic meaning)? Can E3's targeted re-run pass while E5's full run would have caught a regression the manifest simply didn't predict? Can `measure-noise` be gamed (who runs it, when, is the band refreshable mid-campaign to widen tolerance)? Does the E4 denominator (`regression_last_results`) have holes on first iteration or after suite edits? Is `simulated:` watermark laundering possible anywhere (a fixture verdict recorded as real — check `acceptance_decision_eligible` propagation end to end)?
4. **Attribution honesty.** Claim: keep/partial/revert verdicts follow predictions ∩ flips (`opti_loop/attribution.py`). Attack: predict-everything gaming (does anything penalize shotgun predictions?); a lucky unrelated flip counting as "verified"; deterministic-fixture artifacts that make attribution look better than it could ever be with a stochastic executor. Judge whether the *synchronous* attribution design (treatment evaluated in-iteration, drift check next iteration) is sound under stochastic executors, or whether it needs k-repeat confirmation to mean anything.
5. **Judge-layer closure.** Claim: no single error type can corrupt a gate decision — verifiers are the only scorers; T1/T2 flag; unresolved disagreement quarantines; quarantine has no override-score resolution; untrusted judges are consumed by nothing (`opti_judge/*`, `evals/judges/roles/`). Attack: find any path where a judge output changes a score; where an FP reaches acceptance without touching quarantine (e.g., tasks with no assertions, no mutation expectations, and a rubber-stamp verifier); where the corpus can be poisoned by the optimizer or by systematically biased quarantine resolutions; where trust gating can be met vacuously (25 easy cases). Check the probe kit: are the six probe kinds sufficient, and what verifier failure mode passes all six?
6. **Fail-closed semantics.** Claim: `invalid`/`error`/`skipped` never count as agent failures, malformed evidence is `invalid` never `failed`, restricted/holdout material is structurally unloadable (`opti_judge/evidence.py`). Attack each; specifically try to construct an evidence path around the visibility filter (artifacts, payload embedding of restricted content, cluster-register leakage into the optimizer packet).
7. **Exploration policy.** Claim: divergence quota + plateau triggers + parallel campaigns prevent path lock-in (ADR-0015 §9, `conductor.start_iteration`, `compare_campaigns`). Attack: is the divergent flag actually enforced (what stops the optimizer targeting the top cluster anyway)? Do parallel campaigns share any mutable state that breaks independence? Is the cross-campaign report rankable when configs differ (ADR-0001 violation)?
8. **The transfer bet.** Claim: harness gains measured on a cheap fixed executor (MiniMax-M3) will transfer to stronger models (AHE evidence). Judge whether this design will produce *falsifiable evidence* for or against that bet — what measurement, recorded where, would tell the owner the bet failed? If nothing would, that is a blocking finding.

### Also answer directly

- Which single mechanism, if it silently broke, would corrupt the most downstream decisions — and how would anyone notice?
- Rank the three changes that would most raise the probability this loop produces real, transferable browser-harness improvements.
- Is anything claimed in `loop_harness/README.md` / `judge_harness/README.md` "Honest limitations" sections actually *worse* in the code than stated?

### Output format

1. **Verdict** (one paragraph): can this machine, once bridges exist, be trusted to accept only real improvements? What is the weakest link?
2. **Findings table**: ID · severity · claim attacked · evidence (file:line) · reproduction · fix.
3. **Attack log**: attacks attempted that failed, with the reason the mechanism held.
4. **Top-3 value-raising changes**, each with expected effect on the loop's ability to produce real improvements.
