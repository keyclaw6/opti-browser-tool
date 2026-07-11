# Candidate task inventory — Batch 1

- Date: 2026-07-11
- Status: Provisional candidate pool; not a frozen evaluation suite
- Related decision: [ADR-0010](../../../docs/adr/0010-task-difficulty-calibration-band.md)
- Machine-readable inventory: [`batch-1-candidates.csv`](batch-1-candidates.csv)

## Executive finding

Batch 1 identifies **140 exact candidates** from five benchmark families whose latest strong public aggregate result verified in this research pass lies within the project's 35–70% sourcing band. The batch is intentionally larger than the planned 100-task primary suite so that tasks can be rejected during environment, verifier, duplication, safety, and difficulty audits without forcing weak replacements into the final set.

The batch contains 131 state-changing tasks and nine visual navigation or search tasks. It spans 26 source/site combinations and 66 labeled interaction classes. It includes professional social interaction, Reddit-like forums, checkout and ordering, flight and accommodation booking, payment and address forms, enterprise configuration, calendars, email, rich-text editing, repository workflows, visual product selection, custom dropdowns, date pickers, table filters, and dashboard controls.

## Critical evidence boundary

The public evidence is **benchmark-level**, not task-level. For example, a 58.3% score on all VisualWebArena tasks does not imply that VisualWebArena task 635 itself has a 58.3% success rate.

The exact tasks below are therefore candidates because:

1. their source benchmark's strong-system aggregate score is within 35–70%;
2. their metadata indicates medium or compositional difficulty where that metadata exists;
3. they exercise interactions central to this project; and
4. they have a programmatic or structured evaluator worth auditing.

They cannot enter the final 100 until local runs establish a task-level rate in or near the accepted band.

### Score freshness and SOTA wording

The source scores are dated public references, not proof that an exhaustive search found the absolute current best result for every benchmark. The artifact records the source date and marks each reference `latest_verified_public_aggregate_in_this_pass_not_exhaustive_sota_proof`. Final admission will use a pinned current strong reference system and local repeated trials, because that is the only way to establish the task-level 35–70% condition consistently across all sources.

## Source composition

| Source | Candidates | Public strong-system result used for sourcing | Reference date | Why this slice was selected |
|---|---:|---:|---|---|
| REAL v1 | 30 | at most 41% in the published REAL study | 2025-04-15 | Exact version alignment with the published result; medium/hard action and retrieval-action tasks; deterministic state checks; modern consumer and professional apps |
| WorkArena++ L2 | 30 | 69.4% ± 3.0 | 2025-08-07 | At the top of the target band; exact task-class and seed pairs; compositional enterprise workflows without using L3's much lower, non-standard-budget result |
| WebArena-Verified | 30 | 53.7% | 2026-06-06 | Audited structured and network-trace verification; state-changing Reddit, shopping, administration, and GitLab workflows; mixed hard and non-hard tasks |
| VisualWebArena | 30 | 58.3% | 2026-05-24 | Overall-medium tasks with medium or hard visual difficulty; visual classifieds, Reddit, and shopping; programmatic HTML, URL, or image-query evaluation |
| WARC-Bench | 20 | 64.8% held-out test | 2025-10-10 | Archived real interfaces and deterministic JavaScript rewards for date pickers, dropdowns, forms, rich text, filters, tree navigation, and dashboard widgets |

## Why these sources appear in Batch 1

### REAL v1

REAL directly supplies the modern workflows the project cares about: LinkedIn-like professional networking, e-commerce, food delivery, flights, calendar, email, restaurant and accommodation booking, freelance job workflows, rides, and property tours. Only action or retrieval-action tasks labeled medium or hard were considered. Tasks with known broken evaluators were excluded. Tasks with an LLM Boolean component are downgraded to priority B until that component is replaced or validated.

The batch pins REAL v1 because the public benchmark result applies to the original 112-task release. REAL v2 remains useful, but using it before a comparable result exists would break score-to-task-version alignment.

### WorkArena++ L2

WorkArena++ L2 contributes enterprise interactions that are poorly represented by consumer benchmarks: list filtering, duplicate marking, workload and priority assignment, change scheduling, dashboard reasoning followed by record creation, expense workflows, catalog ordering, table sorting, hardware assets, and onboarding or offboarding.

The official L2 result sits at 69.4%, just inside the accepted band. The batch therefore selects medium-sized or clearly compositional task families and records an exact seed for every task. Each generated natural-language goal still has to be materialized and archived from the pinned ServiceNow instance before admission.

### WebArena-Verified

The earlier plan emphasized the Hard subset, but that is not appropriate as the default after ADR-0010: the maintainers report that a large fraction of that subset has predicted success at or below 20%. Batch 1 instead samples the full verified set and includes only five Hard-subset tasks among 30 candidates.

The selected tasks cover forum creation and posting, subscription, cross-forum image reposting, constrained product selection and checkout, refund and review forms, address updates, catalog administration, order notification, web-editor commits, collaborator management, milestones, issues, merge requests, and project creation.

### VisualWebArena

All selected tasks are labeled overall-medium. Their visual difficulty is medium or hard. The batch favors tasks that change state through comments, votes, subscriptions, wish lists, carts, comparisons, reviews, or checkout. Nine URL-only visual search tasks are retained as priority B because they may still provide useful perception signal, but they should not displace action-heavy tasks unless local calibration shows that they are discriminative.

Every selected task requires a screenshot ablation. A task advertised as visual should be rejected if a structured-only executor can solve it through hidden labels or metadata that bypass the intended evidence.

### WARC-Bench

The selected WARC tasks use archived real pages rather than the synthetic pages also present in the benchmark. They cover Alaska Airlines, American Airlines, Zendesk, GitHub, NetSuite, Airbnb, and Wellcare. Every task uses a JavaScript state matcher. The selection excludes every task listed in the repository's known environment-issue skip list.

WARC remains a component-skill slice, not the core long-horizon score. Its tasks are useful because a failed workflow can often be traced back to one of these primitives, but allowing too many short tasks would distort the project toward local clicking rather than complete browser work.

## Candidate examples

The full list is in the CSV and JSONL files. Representative examples include:

- `real-v1-networkin-9`: find a Stanford attendee, send a connection request, and message them;
- `real-v1-omnizon-9`: purchase a specific controller after changing payment details;
- `workarena-l2-off-board-user-l2-seed-466`: execute a seeded multi-application offboarding workflow;
- `webarena-verified-610`: create a book review post and comment on it;
- `webarena-verified-531`: prepare a refund contact form from order history without submitting;
- `visualwebarena-428`: visually locate a dated keyboard post and add a specified comment;
- `visualwebarena-714`: identify a visually described lamp, add it to the cart, and reach checkout without ordering;
- `warc-bench-online-12`: enter and bold text in a Zendesk rich-text editor;
- `warc-bench-online-26`: navigate a GitHub file tree using only expansion arrows; and
- `warc-bench-online-51`: adjust Airbnb guest counters while preserving the required dropdown state.

## What has been validated in this pass

The construction script checked that:

- all 30 REAL IDs exist in `agisdk 0.3.5`'s v1 manifests;
- no selected REAL task contains the package's known broken-evaluator marker;
- all 30 WorkArena task-and-seed pairs exist in the L2 sampled inventory generated from `browsergym-workarena 0.5.3`;
- all 30 WebArena-Verified IDs exist in version 1.2.3;
- all 30 VisualWebArena IDs exist in version 0.0.15 and are labeled overall-medium;
- none of the 20 WARC candidates appears in the repository's known environment-issue skip list;
- every source's public aggregate score is inside 35–70%; and
- all 140 candidate IDs are unique.

This is a manifest validation, not proof that the environments launch, reset, or score correctly.

## Required calibration before final selection

For each candidate:

1. pin the benchmark version, browser image, account state, viewport, locale, time zone, action budget, model snapshot, and harness commit;
2. run an oracle or official cheat path and verify reset reproducibility;
3. test the evaluator against success, near miss, partial completion, plausible false claim, harmful extra action, and infrastructure failure;
4. run a simple baseline and the chosen strong reference system;
5. repeat sufficiently to estimate task-level success and uncertainty;
6. reject tasks with an estimated strong-system rate materially below 35% or above 70%, unless an explicit exception is approved;
7. reject tasks dominated by environment or evaluator failures;
8. deduplicate equivalent templates and action paths; and
9. select the final 100 only after coverage and correlation analysis.

The trial count and boundary confidence rule remain open decisions. A sensible first measurement pass is three trials per task for deterministic replicas, followed by additional trials for tasks near 35% or 70% and for any task showing state instability.

## Planned Batch 2

Batch 1 deliberately stops at 140 tasks. A second candidate pass should be created only after reviewing coverage gaps. Its likely focus is:

- WebChoreArena tasks where substantial navigation, rather than arithmetic alone, drives difficulty;
- deterministic replacements for WebForge popup, cookie-dialog, delay, and layout-noise tasks;
- additional WARC tasks if missing UI primitives are identified; and
- permitted live-site or high-fidelity replica tasks for behaviors not represented by the controlled set.

Batch 2 should add replacements, not force the final suite above 100.
