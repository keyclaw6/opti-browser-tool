# Auto-Research Audit Prompts

The former single comprehensive commission was too large for one reviewer pass.
It is now split into three standalone prompts with deliberately narrow overlap:

1. [Part 1 — foundations and bring-up](review-prompts/PART_1_FOUNDATIONS_AND_BRINGUP.md)
   reviews project truth, accepted decisions, tasks, environments, bridges,
   browser runtime, traces, artifacts, and calibration readiness.
2. [Part 2 — research loop and convergence](review-prompts/PART_2_RESEARCH_LOOP_AND_CONVERGENCE.md)
   reviews manifests, activation, E0–E5, statistics, attribution, verifier and
   judge integrity, and whether improvements can accumulate and generalize.
3. [Part 3 — security and operations](review-prompts/PART_3_SECURITY_AND_OPERATIONS.md)
   reviews privilege boundaries, trusted state, crash/concurrency recovery,
   unattended operation, stop/budget/transfer enforcement, secrets, and
   live-site safety.

Each prompt:

- includes the public repository URL and requires a fresh clone of `main`;
- gives the reviewer full local inspection and test authority while limiting
  tracked changes to its assigned report;
- favors targeted source inspection within its bounded scope;
- uses a unique finding prefix to make later merging mechanical;
- requires a predictably named Markdown report committed on a unique branch;
- treats its neighboring parts only as interface boundaries.

## Running the review

Run the three prompts in separate fresh agent sessions. They can run in any
order, but Part 1 → Part 2 → Part 3 is the clearest sequence. Do not paste a
previous part's report into the next reviewer's context; independence is useful.

## Committing the reports

Ask the reviewer to return or export these exact files:

- `docs/review-reports/opti-audit-part-1-foundations.md`
- `docs/review-reports/opti-audit-part-2-convergence.md`
- `docs/review-reports/opti-audit-part-3-operations.md`

Each reviewer creates a unique `codex/audit-*` branch from the reviewed `main`,
commits only its assigned report, and pushes that branch to `origin`. It then
returns only the reviewed SHA, report path, branch name, report commit SHA, and
push status—never the full report text. The durable destination and delivery
contract are documented in [`review-reports/README.md`](review-reports/README.md).

## Final synthesis

The three reviewers are not asked for one project-wide verdict. After all
report branches arrive, the primary agent will:

1. fetch and preserve each committed report unchanged;
2. deduplicate interface findings;
3. verify high-severity claims against the reviewed SHA;
4. build one dependency-ordered remediation plan; and
5. answer whether the project is safe to activate.
