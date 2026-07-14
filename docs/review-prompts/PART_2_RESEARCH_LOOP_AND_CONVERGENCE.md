# Review Commission 2 of 3 — Research Loop and Convergence

Copy this entire file into a fresh reviewing-agent session.

---

## OPTI BROWSER TOOL — RESEARCH CORRECTNESS AND CONVERGENCE AUDIT

Repository to download:

https://github.com/keyclaw6/opti-browser-tool

### Mission

Audit whether the proposed and implemented research loop can distinguish a
causal, repeatable, general browser-harness improvement from an inert change,
an evaluator defect, infrastructure failure, noise, adaptive overfitting, or
gate gaming—and whether it has enough liveness to discover and accumulate good
changes rather than merely reject bad ones.

This part answers:

> If real environments and bridges supply trustworthy runs, will the
> manifest → analysis → hypothesis → treatment → E0–E5 → attribution →
> accepted-baseline feedback loop produce credible evidence of improvement and
> know when that evidence does not generalize?

Do not deeply audit environment installation/task provenance (Part 1) or OS
privilege, crash consistency, concurrency, unattended scheduling, secrets, and
live-site controls (Part 3). Cover those only where their outputs cross the
research decision boundary.

### Repository and commit workflow

You have full local clone, inspection, test, file-write, commit, and push
capability. Use it to complete the audit and deliver the report through Git.
Do not change product code, tests, project documentation, manifests, or audit
prompts. The only tracked change on your branch must be this part's assigned
report. You may run existing tests and use temporary analysis artifacts;
propose—but do not implement—product fixes or missing attack tests.

Keep the investigation inside this prompt's scope and batch related reads and
searches. Do not install real benchmark environments or models merely to expand
the audit. Mark claims requiring real stochastic/browser evidence
`NOT VERIFIED`.

Start with:

```bash
git clone --branch main --single-branch https://github.com/keyclaw6/opti-browser-tool.git
cd opti-browser-tool
REVIEWED_SHA="$(git rev-parse HEAD)"
BRANCH="codex/audit-part-2-convergence-$(git rev-parse --short=12 HEAD)-$(date -u +%Y%m%d%H%M%S)"
git switch -c "$BRANCH"
git rev-parse "$REVIEWED_SHA"
git status --short --branch
```

Record `REVIEWED_SHA` in the report.

### Evidence and severity

- `PROJECT_CHARTER.md` and Accepted ADRs are binding.
- `docs/DECISION_REGISTER.md` is authoritative for ADR status.
- Deterministic fixtures prove control-flow plumbing only.
- “Tests pass” is not proof of stochastic power, a real trace, or an admitted
  verifier.
- Distinguish `verified-real`, `implemented-unverified`, `simulated-only`,
  `documented-only`, `missing`, and `contradicted`.

Severity:

- **P0:** reachable false benchmark acceptance or evaluator corruption.
- **P1:** prevents a valid treatment from being activated, evaluated, or recorded.
- **P2:** major risk to statistical validity, attribution, liveness, generality,
  cumulative improvement, or transfer.
- **P3:** documentation/schema/test debt without a demonstrated wrong decision.

Each finding needs `file:line`, expected versus actual behavior, causal impact,
smallest fix, and a regression/acceptance test. Do not report purely
hypothetical attacks without a reachable path.

### Targeted reading list

1. `PROJECT_CHARTER.md`, `docs/DECISION_REGISTER.md`, and accepted ADR-0001,
   ADR-0004, ADR-0005, ADR-0015, and ADR-0016.
2. `PROGRAM.md`, `loop_harness/README.md`, and
   `docs/architecture/COMPONENT_TREE.md` and `ANALYST.md`.
3. All `opti_loop` source, prioritizing manifest, registration, lint,
   fileguard, gates, eligibility, compare, attribution, analyst, clusters,
   conductor, verdict, campaign, and transfer.
4. `judge_harness/README.md` and all `opti_judge` source, prioritizing evidence,
   probekit, T1 checks, corpus, panel, router, and quarantine.
5. `schemas/experiment.schema.json`, `schemas/trace-event.schema.json`,
   result/summary schemas, examples, component registrations, lane files, and
   judge role JSON.
6. Loop and judge unit/end-to-end tests. Inspect whether each named test
   exercises the production claim it appears to prove.
7. Read Part 1 domains only as inputs: task/suite manifests, bridge-result
   contract, and trace contract.

Run this compact test batch if permitted:

```bash
PYTHONDONTWRITEBYTECODE=1 make loop-test judge-test
```

Do not spend actions rerunning documentation or catalog checks owned by Part 1.

## Audit scope A — complete causal feedback loop

Trace this path through actual code:

`real failure trace → Analyst report → failure cluster → optimizer packet →
manifested hypothesis → candidate commit → activation evidence → smoke/target/
regression/full evaluation → eligibility → comparison → attribution → typed
verdict → accepted base/regression/learnings → next packet`

For every arrow identify:

- enforcing code;
- trusted input and output;
- whether it exists, is simulated, or is missing;
- positive and negative test coverage;
- the likely false-positive and false-negative mode.

Answer whether the current system is a functional adaptive loop, a
deterministic loop shell, or only a contract for one.

## Audit scope B — manifest, component, and activation validity

1. Compare `schemas/experiment.schema.json`,
   `examples/experiment.example.json`, `PROGRAM.md`, and
   `opti_loop.manifest`. Validate whether they accept the same shape.
2. Check binding of manifest claims to trusted facts:
   - campaign and iteration;
   - base and candidate SHA;
   - fixed variables and run identity;
   - exactly one hypothesis/component/commit;
   - changed files and target component;
   - trace/run/event evidence;
   - motivating cluster;
   - predictions, regression risks, and evaluation plan;
   - activation evidence;
   - conductor-appended attribution.
3. Determine whether zero, multiple, merge, empty, net-zero, or unrelated
   commits satisfy the runtime contract.
4. Verify every changed runtime file must be registered and scanned.
5. Test by inspection whether a component can register arbitrary new files or
   cross its intended boundary.
6. Separate static registration from dynamic activation. A disabled,
   unreachable, shadowed, or behaviorally inert change must be `invalid`.
7. Determine whether an optimizer can spoof an activation event without the
   changed behavior executing.
8. Assess whether one-component/one-commit improves causal attribution without
   blocking necessary contract-spanning or interacting mechanisms. Identify
   the minimal approved path for such changes.

Hand OS/file-permission enforcement to Part 3; review only the gate's logical
containment invariant here.

## Audit scope C — E0–E5 decision soundness

For every rung state:

`invariant · inputs · deterministic decision · invalid/rejected distinction ·
positive test · bypass risk`

### E0 — containment and generality

Verify commit-diff authority, worktree cleanliness, registration, manifest
scope, and whole-tree lint. Determine what literal/encoded benchmark leakage
the lint can detect and what must be caught by held-out transfer.

### E1 — activation

Verify dynamic trace-backed execution is required before benchmark acceptance.
Static wiring alone cannot establish that the treatment ran.

### E2 — smoke

Check that infrastructure failure becomes `invalid`, behavioral collapse
becomes rejection, and the threshold is measured rather than an unexplained
constant. Analyze stochastic repeat needs without re-auditing task selection.

### E3 — targeted screen

Confirm E3 is screening only. A targeted/lucky pass must reappear as a
predicted verified fix in full E5 evidence. Check task selection against the
motivating cluster rather than arbitrary manifest IDs.

### E4 — regression

Verify the denominator comes only from accepted, repeatedly passing evidence.
Check confirmation repeats, admission/T1 eligibility, quarantine, drift, suite
changes, and rejected-treatment isolation. Determine how fixed tasks are
promoted and cumulative capabilities protected.

### E5 — full comparison

Verify baseline/treatment identity, valid denominators, full predicted flips,
aggregate non-inferiority, regression tolerance, noise binding, evidence class,
and typed verdict. Baseline, treatment, smoke, regression, and noise runs
should not receive materially different evidence-integrity checks.

Explicitly disposition these cases:

- no/malformed/incomplete trace;
- admitted-looking verifier with missing T1 evidence;
- infrastructure error;
- inert treatment;
- seeded regression;
- shotgun prediction;
- lucky unrelated flip;
- aggregate gain with no causal predicted fix;
- predicted fix with net degradation;
- fixture or nonreportable result relabeled as benchmark;
- one real positive-control improvement.

For each state whether current code blocks it, permits it, or lacks enough
implementation to know.

## Audit scope D — benchmark eligibility and evaluator closure

Audit the complete T0–T3 chain:

1. **T0 verifier admission**
   - six required probe types;
   - blinding;
   - checksum coverage of verifier code, dependencies, command, environment,
     task configuration, and version;
   - invalidation/re-admission after any verifier repair.
2. **T1 deterministic checks**
   - no-action pass, mutation/side effects, action anomalies, loops, stale
     epochs, expected state;
   - missing/malformed trace behavior;
   - false-positive and false-negative routing;
   - no direct score override.
3. **T2 LLM flaggers**
   - trust bound to benchmark, role, prompt, model/provider/snapshot, settings,
     evidence contract, and corpus version;
   - fixture/model override/prompt edit cannot inherit trust;
   - class balance, deduplication, held-back measurement, operating points,
     and drift;
   - prompt-injection exposure;
   - untrusted judgments have no trusted-state effect.
4. **T3 quarantine**
   - unresolved disagreement never changes score;
   - denominator and family-wide effects;
   - owner resolution and audit trail;
   - feedback to calibration without leakage to optimizer.

Prove T2 and quarantine are connected to the intended loop rather than merely
standalone library features.

## Audit scope E — statistics and adaptive-search validity

1. Identify the primary estimand and verify consistent use.
2. Review paired design, reset identity, ordering/interleaving, random seeds,
   repeat counts, uncertainty intervals, non-inferiority margin, minimum
   detectable effect, and power.
3. Audit noise-band construction: minimum real runs, invalid/outlier handling,
   task-set identity, immutability, and remeasurement triggers.
4. Determine whether run identity binds the contents—not just labels—of suite,
   catalog, environment/runtime images, bridge code, model snapshot/settings,
   browser, budgets, verifier/admission set, judge configuration, and policy
   thresholds.
5. Analyze repeated adaptive testing:
   - multiple comparisons across iterations;
   - optional stopping and selective reruns;
   - winner's curse and lucky flips;
   - dev-suite overfitting;
   - changing invalid/quarantine denominators;
   - environmental nonstationarity;
   - cumulative type-I and type-II errors.
6. Determine whether k-repeat confirmation is executable or only prose.
7. Test conceptually whether a small real improvement of the expected size
   would be detected, and whether a no-op would occasionally pass after many
   attempts.
8. Check that “two five-iteration windows inside noise” distinguishes genuine
   diminishing returns from an insensitive gate, blind Analyst, broken
   optimizer, or exhausted budget.

Quantify where possible; otherwise state exactly which real measurements are
needed.

## Audit scope F — Analyst, clusters, attribution, and learning

1. Separate the real Analyst contract from any current stub.
2. Verify event-addressable claims, earliest divergence, uncertainty, and
   non-scoring behavior.
3. Check cluster existence, membership evidence, one-component mapping,
   reproducible priority, status transitions, and quarantine routing.
4. Determine whether the optimizer must target the highest-priority cluster or
   can name an arbitrary/fake cluster.
5. Ensure infrastructure invalidity does not count as a behavioral hypothesis
   failure or force a pivot.
6. Audit predict-everything, arbitrary task targeting, cluster renaming, repeat
   hypotheses, and unrelated lucky flips.
7. Verify keep/partial/revert attribution reflects treatment activation and
   predicted causal mechanism.
8. Check learnings persistence and the three memory regimes without auditing
   filesystem security.
9. Determine whether failure evidence is rich enough to generate useful next
   hypotheses, not merely categorize outcomes.

## Audit scope G — accumulation, exploration, holdout, and transfer validity

Review research validity; Part 3 reviews whether controls actually execute.

- Can accepted small gains accumulate against meaningful ancestors/champions?
- Are regressions protected cumulatively rather than only against a noisy
  predecessor?
- Does forced divergence explore a different hypothesis class?
- Do parallel campaigns preserve comparability and avoid a per-iteration race?
- Is mechanism transplantation re-evaluated through the receiving gate?
- Is hidden holdout scheduled and insulated from iteration pressure?
- Are discovery-excluded tasks and unseen sites/layouts truly excluded?
- Is transfer evidence bound to base/treatment, task set, model snapshots,
  repeats, uncertainty, and cost?
- What result falsifies the cheap-executor transfer bet?
- Could the loop appear to converge while merely overfitting visible tasks?
- Could a strict gate get stuck at a local optimum by rejecting temporarily
  neutral enabling changes?

Provide the most likely false-improvement path and the most likely
false-rejection/non-discovery path.

## High-risk hypotheses requiring explicit disposition

Report each as `HELD`, `DEFEATED`, `NOT IMPLEMENTED`, or `NOT TESTABLE`:

1. Benchmark eligibility can survive missing or malformed trace/T1 evidence.
2. E1 can pass while dynamic activation remains pending.
3. Exactly one commit is documented but not enforced.
4. Runtime manifest validation disagrees with the canonical schema.
5. Baseline, E4, or noise evidence is audited less strictly than E5 treatment.
6. Run identity omits identity-bearing contents and permits stale noise.
7. Judge trust is too broadly scoped or an untrusted judgment affects state.
8. Stub analysis or unchecked cluster references can steer real iterations.
9. A single lucky flip can pass without adequate repeat confirmation.
10. Invalid infrastructure attempts count against a hypothesis and force pivot.
11. The transfer criterion can be satisfied by unbound external deltas.
12. The loop is safe against false positives but too insensitive to improve.

## Required report

Write the Markdown report at:

`docs/review-reports/opti-audit-part-2-convergence.md`

Use this structure:

1. **Scope verdict** — research-decision integrity and credible convergence:
   `YES / CONDITIONAL / NO`.
2. **Reviewed SHA and test result**.
3. **Causal-loop map** — each arrow and implementation state.
4. **E0–E5 matrix**.
5. **Evaluator T0–T3 matrix**.
6. **Statistical/convergence assessment**.
7. **Findings** — IDs `CONV-001` onward, P0→P3.
8. **High-risk hypothesis disposition**.
9. **Positive and negative controls still required**.
10. **Top three changes most likely to increase real improvement probability**.
11. **Cross-part handoff** — no more than five interface questions for Parts 1
    or 3.
12. **Direct answers**:
    - Can a bad/lucky change be falsely accepted?
    - Can a small good change be detected and attributed?
    - Can accepted gains accumulate without visible-suite overfitting?
    - What falsifies transfer?
    - What minimum evidence would change this part's verdict?

Be concise enough to finish. Spend report space on causal paths and evidence,
not on restating project prose.

### Commit and push the report

Before committing, ensure no tracked file except the assigned report changed.
Discard only changes generated by your own inspection commands.

```bash
git status --short
git add docs/review-reports/opti-audit-part-2-convergence.md
git diff --cached --name-only
git diff --cached --check
git commit -m "docs: add convergence audit report"
git push -u origin HEAD
git branch --show-current
git rev-parse HEAD
```

The staged-name output must contain exactly the report path. Do not commit
generated files or fixes discovered during the audit.

After pushing, reply with only:

- reviewed base SHA;
- report path;
- pushed branch name;
- report commit SHA; and
- push status.

Do not paste the report into chat. If pushing is impossible, create a one-commit
`git format-patch` artifact and return that file instead of its text.
