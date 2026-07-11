# ADR-0008: Primary evaluation benchmark-source portfolio

- Status: Proposed
- Date opened: 2026-07-11
- Last updated: 2026-07-11
- Date accepted: —
- Decision owner: project owner
- Evidence report: [Benchmark source selection report](../../research/benchmarks/2026-07-11-benchmark-source-selection-report.md)

## Question

Which benchmark families should supply candidate tasks for the first approximately 100-task primary browser-agent evaluation suite?

## Proposed direction

Advance the following allocation to task-level audit:

| Source | Proposed primary tasks | Proposed smoke tasks | Role |
|---|---:|---:|---|
| REAL | 20 | 4 | LinkedIn-like professional networking, checkout, booking, email, calendar, travel, rides, and other modern application workflows |
| WebArena-Verified Hard | 20 | 4 | Audited, deterministic Reddit, shopping, administration, GitLab, and multi-site state-changing tasks |
| VisualWebArena | 15 | 3 | Visual grounding and screenshot-dependent social, shopping, and classifieds interaction |
| WorkArena++ | 20 | 4 | Hard enterprise forms, records, filters, catalogs, menus, configuration, and compositional workflows |
| WebChoreArena | 10 | 2 | Tedious long-horizon work involving memory, calculation, and multi-page state |
| WARC-Bench | 10 | 2 | Archived real-site date pickers, menus, nested scrolling, forms, hover, sliders, and dynamic controls with programmatic rewards |
| WebForge Level 3 | Up to 5 | Up to 1 | Popups, cookie dialogs, latency, layout noise, and risk-heavy tasks, conditional on deterministic verification |
| **Total** | **100** | **20** | The smoke set is nested in the primary set under ADR-0007 |

This is a source-allocation hypothesis, not a frozen suite. The exact counts may change after task audits. WebForge has zero guaranteed slots: rejected WebForge tasks must be replaced by another audited source rather than admitted with its default LLM judge.

## Proposal revision history

The first draft allocated 25 tasks to WebArena-Verified Hard and up to 5 to WebForge Level 3. It was revised to 20 and up to 10 respectively to cap the combined WebArena-derived family at 45 tasks and reserve capacity for popup, cookie-dialog, delay, and interface-noise requirements.

A second review located the public WARC-Bench repository, bundled task files and archived environments, an MIT package declaration, and per-task programmatic JavaScript evaluators. The allocation was therefore revised again: WARC-Bench received 10 proposed slots, REAL was reduced from 25 to 20, and WebForge returned to up to 5 conditional slots. The reason is to obtain real-UI component diversity and deterministic rewards from WARC-Bench while reserving WebForge only for nuisance conditions not otherwise represented. Neither revision has been accepted by the project owner.

## Why this is proposed

No single benchmark covers the project objective without serious blind spots.

- **REAL** is the best controlled match for LinkedIn-like interaction and realistic consumer workflows such as checkout, booking, messaging, calendars, travel, and rides.
- **WebArena-Verified Hard** provides the strongest audited deterministic-evaluation foundation among the candidates and includes difficult Reddit-like, commerce, administration, GitLab, and cross-site tasks.
- **VisualWebArena** prevents the suite from rewarding a harness that succeeds only when hidden structure or accessibility text makes the interface easy to parse.
- **WorkArena++** contributes difficult configuration-heavy enterprise workflows and has substantial unsolved Level 3 headroom.
- **WebChoreArena** adds long-horizon memory and calculation pressures that are weakly represented elsewhere.
- **WARC-Bench** adds archived real-site GUI primitives such as date pickers, nested scrolling, menus, hover, sliders, forms, and dynamic controls, each with a programmatic reward.
- **WebForge Level 3** uniquely exposes controlled popups, cookie dialogs, delays, and interface noise, but its default LLM answer judge is not sufficient for primary-gate use.

The allocation caps every source at 20 tasks and limits the combined WebArena-derived family to 45 tasks. This reduces dependence on any one UI stack, task-writing style, action vocabulary, or evaluator family.

## What this ADR does not decide

This proposal does not:

- select individual task IDs;
- select REAL v1 or v2;
- approve WebForge's default evaluator;
- select a browser engine, automation library, observation format, or action interface;
- define the hidden holdout;
- admit live-site tasks to the primary score; or
- establish the final regression-promotion gate.

## Evidence and score interpretation

The supporting report records current public score examples and protocol caveats. Published benchmark scores are **system scores**, not model-only scores: they combine model, prompt, observations, actions, memory, planning, step budget, retries, and evaluator. Results using human assistance, accumulated benchmark-specific workflows, changed action budgets, or different benchmark revisions must be labeled rather than compared directly.

## Admission gate

ADR-0008 may be accepted only after:

1. a versioned candidate pool materially larger than 100 tasks is exported;
2. REAL v1 versus v2 is resolved and evaluator semantics are pinned;
3. every proposed task passes licensing, safety, reset, oracle-solvability, verifier, duplication, and shortcut checks;
4. WARC-Bench tasks are deduplicated by site and UI mechanism, and their JavaScript rewards survive shortcut and near-miss tests;
5. WebForge tasks have deterministic state or operation-code verification independent of its default LLM answer judge;
6. WorkArena access and reproducible instance reset are demonstrated;
7. selected tasks are run with both a simple baseline and a known strong harness under recorded protocols;
8. saturated, broken, unsafe, judge-fragile, or benchmark-leaking tasks are rejected;
9. the exact 100-task manifest, replacement pool, and nested 20-task smoke subset are reviewed; and
10. the project owner explicitly accepts this ADR or a revised portfolio.

Until then, this portfolio guides research only.

## High-priority unallocated candidates

**EntWorld** is the first enterprise replacement candidate. Its paper reports 1,756 tasks across six enterprise domains, SQL-based deterministic verification, and 47.61% GPT-4.1 success. No authoritative public code or dataset repository was located, so access and reproducibility remain unverified.

**RiskWebWorld** is the first hostile-interface replacement candidate. Its paper reports 1,513 e-commerce risk tasks, uncooperative sites, partial environmental hijackings, and 49.1% success for top generalist systems. No authoritative public release was located.

## Revisit triggers

Revisit the allocation if task-level auditing finds insufficient hard tasks, correlated templates, evaluator defects, inaccessible infrastructure, licensing restrictions, WARC-Bench shortcut susceptibility, or local strong-harness success above the desired discrimination range. Also revisit when EntWorld, RiskWebWorld, or another better-verified source becomes runnable.
