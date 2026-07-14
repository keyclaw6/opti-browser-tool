# Review Commission 1 of 3 — Foundations and Bring-Up

Copy this entire file into a fresh reviewing-agent session.

---

## OPTI BROWSER TOOL — FOUNDATIONS AND BRING-UP AUDIT

Repository to download:

https://github.com/keyclaw6/opti-browser-tool

### Mission

Audit whether the project's stated objective, accepted decisions, benchmark
substrate, and bring-up plan form a coherent and executable foundation for a
real browser-agent auto-research campaign.

This part answers:

> Can the project get from this repository to trustworthy real browser runs,
> calibrated tasks, and complete evidence without hidden blockers, circular
> dependencies, or mistaking fixtures for readiness?

Do not audit the internal E0–E5 acceptance logic, statistical convergence
algorithm, OS security boundary, crash recovery, or autonomous scheduler in
depth. Those belong to Parts 2 and 3. Inspect those surfaces only when they are
consumers of a task, bridge, trace, model, or bring-up contract reviewed here.

### Repository and commit workflow

You have full local clone, inspection, test, file-write, commit, and push
capability. Use it to complete the audit and deliver the report through Git.
Do not change product code, tests, project documentation, manifests, or audit
prompts. The only tracked change on your branch must be this part's assigned
report. Temporary test output is allowed; clean any tracked changes it creates.

Keep the investigation inside this prompt's scope. Batch related reads and
searches, prefer `rg` and direct source inspection, and do not install the five
benchmark environments merely to expand the audit. Mark unavailable real
infrastructure `NOT VERIFIED`.

Start with a fresh clone:

```bash
git clone --branch main --single-branch https://github.com/keyclaw6/opti-browser-tool.git
cd opti-browser-tool
REVIEWED_SHA="$(git rev-parse HEAD)"
BRANCH="codex/audit-part-1-foundations-$(git rev-parse --short=12 HEAD)-$(date -u +%Y%m%d%H%M%S)"
git switch -c "$BRANCH"
git rev-parse "$REVIEWED_SHA"
git status --short --branch
```

Record `REVIEWED_SHA` in the report. The report is invalid without it.

### Evidence rules

- `PROJECT_CHARTER.md` and Accepted ADRs are binding.
- `docs/DECISION_REGISTER.md` is authoritative for ADR status.
- Code and tests show implementation; prose shows intent.
- `validation/` files are historical evidence until reproduced.
- Fixtures prove plumbing only and never prove browser performance.
- A disclosed missing prerequisite lowers readiness but is not automatically a
  code defect.
- Distinguish `verified-real`, `implemented-unverified`, `simulated-only`,
  `documented-only`, `missing`, `externally-blocked`, and `contradicted`.

Severity:

- **P0:** can invalidate task/evaluator identity or admit false benchmark evidence.
- **P1:** blocks real bring-up, calibration, or reproducible browser runs.
- **P2:** materially risks benchmark validity, coverage, cost, or feasibility.
- **P3:** documentation/contract drift or nonblocking debt.

Every finding needs `file:line` evidence, impact, smallest fix, and an
acceptance check. Do not invent findings.

### Targeted reading list

Read these files fully enough to understand their contracts:

1. `AGENTS.md`, `README.md`, `PROJECT_CHARTER.md`.
2. `docs/README.md`, `docs/AGENT_HANDOFF.md`,
   `docs/DECISION_REGISTER.md`, `docs/DECISION_TIMELINE.md`,
   `docs/ROADMAP.md`, `docs/OPEN_QUESTIONS.md`.
3. `docs/BRINGUP_RUNBOOK.md`, `docs/TASK_DATA_GUIDE.md`, and
   `docs/REVIEW_GUIDE.md`.
4. Accepted ADR-0001, ADR-0004, ADR-0007, ADR-0012, ADR-0014, and ADR-0017.
   Read open ADR-0002, ADR-0003, and ADR-0006 only for their unresolved
   boundaries.
5. `docs/architecture/OVERVIEW.md`,
   `docs/architecture/COMPONENT_TREE.md`, `harness/README.md`, and
   `harness/infra/README.md`.
6. `eval_harness/README.md` and the relevant `opti_eval` catalog, validation,
   runner, adapter, model, and summary sources.
7. `evals/config.example.json`, task/suite/result/trace schemas, benchmark
   source lock, and the four suite manifests.
8. Evaluation tests and integrity scripts only as needed to verify claims.

Run this compact validation batch if the read-only environment permits it:

```bash
PYTHONDONTWRITEBYTECODE=1 make eval-validate docs-verify archive-verify
PYTHONDONTWRITEBYTECODE=1 python scripts/verify_file_manifest.py --repo-root .
```

If a command cannot run, report `NOT RUN` and why.

## Audit scope A — project truth and decision coherence

1. State the actual project objective and definition of success in your own
   words. Confirm that reliability and repeatable task completion dominate
   efficiency.
2. Build a compact status table for all Accepted and relevant Open ADRs.
3. Find contradictions among the decision register, ADR headers/prose,
   README, handoff, roadmap, runbook, code comments, package metadata, and
   current implementation.
4. Check that provisional code has not silently settled the open browser
   backend, lane-boundary, or live-site decisions.
5. Identify any accepted requirement whose wording is too incomplete to test.
6. Classify the repository today: research specification, orchestration
   scaffold, bring-up-ready platform, or real evaluation system. Cite evidence.

## Audit scope B — bring-up dependency graph

Audit each runbook prerequisite:

1. dedicated Linux host, Docker/Compose, disk and runtime requirements;
2. exact executor, judge, research, reference, and transfer model invocation;
3. five benchmark environments and deterministic resets;
4. five source bridges;
5. canonical trace writer and artifact store;
6. verifier probe cases and admissions;
7. all-140 reference calibration;
8. final suite filtering, exclusions, smoke coverage, and regression seed;
9. hidden holdout creation before optimizer exposure;
10. real noise measurement and threshold derivation;
11. calibrated judges and real Analyst as dependencies, not their internals;
12. browser-substrate decision and minimal seed harness;
13. injection rehearsal and owner authorization.

For each item report:

`implementation state · prerequisites · evidence present · missing evidence ·
external access needed · acceptance test`

Look for circular dependencies and incorrect ordering. Produce the shortest
valid dependency graph from HEAD to:

1. one real smoke task from each source;
2. all-140 reference calibration;
3. a frozen suite and safe iteration 1.

Do not assume a checklist item is feasible because it is documented.

## Audit scope C — task corpus and suite validity

Verify, primarily through code and machine-readable files:

- 140 raw and 140 normalized task records with identical IDs;
- 30 REAL, 30 WebArena-Verified, 30 WorkArena L2, 30 VisualWebArena, and
  20 WARC-Bench tasks;
- complete provenance, upstream locators, pinned revisions, and source checksums;
- 140-task provisional primary/candidate pool and nested 20-task smoke;
- the provisional—not permanent—meaning of the current regression seed;
- null per-task calibration and correct labeling of source-family aggregates;
- the intended 35–70% local task-level calibration rule;
- recorded exclusion reasons when filtering toward approximately 100 tasks.

Then assess whether the admission plan actually covers:

- task solvability and known-good paths;
- reset determinism and account/state contamination;
- native verifier fidelity and adversarial verifier checks;
- repetitions, instability, duplicates, safety, and source-specific flake;
- smoke representation across sources and mechanisms;
- configuration identity if smoke results are reused;
- current gaps in popup/interference and long-horizon coverage;
- whether calibration with the strong reference creates a useful difficulty
  distribution for the cheaper fixed executor.

Do not rederive gate statistics; record statistical questions for Part 2.

## Audit scope D — real environments and source bridges

For each of the five sources, make one row covering:

`upstream revision · external assets/access · reset mechanism · task resolver ·
browser/session requirements · native verifier · concurrency limit · expected
artifacts · known blocker · evidence currently present`

Review the intended bridge lifecycle:

`reset → resolve exact task → run pinned harness/model → invoke verifier →
emit fail-closed result and evidence`

Check:

- whether task IDs and source versions can resolve unambiguously;
- whether missing websites, images, WACZ files, credentials, profiles, or
  ServiceNow state are accurately disclosed;
- whether each environment can be reset twice to identical observable state;
- whether per-source concurrency and shared-account constraints are specified;
- whether timeout, reset failure, bridge failure, and verifier failure map to
  `invalid/error` rather than agent failure;
- whether result schemas, runner models, examples, and bridge contract agree;
- whether a real bridge can attest exact model, harness, browser, environment,
  task, verifier, and configuration identity.

Flag any step that depends on undocumented manual repair.

## Audit scope E — browser runtime and evolvable harness foundation

Determine what browser/harness code exists today versus what is only a
component registration or design.

Map the charter's important dimensions to an intended implementation surface:

- browser/session lifecycle;
- structured and visual observations;
- epoch-scoped element references;
- DOM, coordinate, keyboard, and tab actions;
- dialogs, popups, downloads/uploads, authentication, scrolling, and forms;
- post-action verification, retry, recovery, loop detection, and safety;
- tracing, budgets, model configuration, skills, memory, and sub-agents.

Answer:

1. Can the minimal structured seed be implemented after ADR-0003 without
   violating existing component contracts?
2. Are infrastructure/component boundaries complete enough for a real bridge?
3. Are any required browser capabilities missing from the contracts?
4. How can backend or lane experiments be conducted if infrastructure is
   optimizer read-only?
5. Is the proposed first vertical slice small enough to build and verify?

Do not choose the backend. Audit readiness to make and implement that decision.

## Audit scope F — trace and artifact contract

Audit the contract expected from the first real bridge:

- append-only `trace.jsonl`;
- ordered, unique, single-run events;
- actor, type, visibility, timestamps, sequence, and browser-state epoch;
- executor/judge/orchestrator/restricted separation;
- content-addressed artifacts with integrity metadata;
- safe artifact resolution and result linkage;
- redaction/export, retention, and physical holdout separation;
- sufficient final-state, action, network, and side-effect evidence.

Compare ADR-0004, `schemas/trace-event.schema.json`, result schemas,
`opti_eval` artifacts, evidence consumers, and the runbook acceptance test.

Report what is:

- specified and schema-enforced;
- enforced only by a consumer;
- not implemented;
- impossible to validate with current metadata.

Hand trace-consumer or benchmark-eligibility risks to Part 2 rather than
re-auditing that gate.

## Audit scope G — feasibility and readiness

Estimate orders of magnitude, not false precision:

- environment setup effort;
- wall time for smoke, all-140 calibration, and repeated runs;
- executor/reference/judge usage;
- storage growth from traces/screenshots/videos;
- operator work for probe cases and task exclusions;
- external account, rate-limit, and availability risks.

Compare these estimates with documented budgets and schedule assumptions.
Identify the critical long pole and the most likely bring-up failure.

## Required report

Write the Markdown report at:

`docs/review-reports/opti-audit-part-1-foundations.md`

Use this structure:

1. **Scope verdict** — foundations coherent: `YES / CONDITIONAL / NO`; current
   foundation readiness: `R0 unreviewable / R1 scaffold / R2 bring-up-ready /
   R3 real calibration-ready`.
2. **Reviewed SHA and checks** — commands, results, skipped work.
3. **Decision/status contradictions**.
4. **Bring-up readiness matrix** — one row per prerequisite.
5. **Five-source environment/bridge matrix**.
6. **Task/suite findings**.
7. **Browser/runtime and trace-contract findings**.
8. **Findings table** — IDs `FOUND-001` onward, sorted P0→P3.
9. **Dependency-ordered path** — HEAD → real smoke → calibration → iteration 1.
10. **Cross-part handoff** — at most five concise questions for Parts 2 or 3;
    do not answer their scopes.
11. **Direct answers**:
    - What can be truthfully run today?
    - What is the first missing executable vertical slice?
    - Which prerequisite is the long pole?
    - Are the 140 tasks ready for calibration?
    - What minimum evidence would change this part's verdict?

Be concise enough to finish. Prioritize P0–P2 evidence over exhaustive prose.

### Commit and push the report

Before committing, ensure no tracked file except the assigned report changed.
Discard only changes generated by your own inspection commands.

```bash
git status --short
git add docs/review-reports/opti-audit-part-1-foundations.md
git diff --cached --name-only
git diff --cached --check
git commit -m "docs: add foundations audit report"
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
