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
| REAL | 25 | 5 | LinkedIn-like professional networking, checkout, booking, email, calendar, travel, rides, and other modern application workflows |
| WebArena-Verified Hard | 20 | 4 | Audited, deterministic Reddit, shopping, administration, GitLab, and multi-site state-changing tasks |
| VisualWebArena | 15 | 3 | Visual grounding and screenshot-dependent social, shopping, and classifieds interaction |
| WorkArena++ | 20 | 4 | Hard enterprise forms, records, filters, catalogs, menus, configuration, and compositional workflows |
| WebChoreArena | 10 | 2 | Tedious long-horizon work involving memory, calculation, and multi-page state |
| WebForge Level 3 | Up to 10 | Up to 2 | Popups, cookie dialogs, latency, layout noise, and risk-heavy tasks, conditional on deterministic verification |
| **Total** | **100** | **20** | The smoke set is nested in the primary set under ADR-0007 |

This is a source-allocation hypothesis, not a frozen suite. The exact counts may change after task audits. WebForge has zero guaranteed slots: any rejected WebForge slot should first be offered to a runnable WARC-Bench release, then reallocated to the other approved sources if necessary.

## Proposal revision history

The first draft allocated 25 tasks to WebArena-Verified Hard and up to 5 to WebForge Level 3. Before acceptance, this was revised to 20 and up to 10 respectively. The reason was to cap the combined WebArena-derived family at 45 tasks instead of 50 and to reserve enough candidate capacity for the project's explicit popup, cookie-dialog, delay, and interface-noise requirements. The WebForge increase does not weaken the verifier standard: all ten slots remain conditional and must be replaced if independent deterministic verification is not achieved.

## Why this is proposed

No single benchmark covers the project objective without serious blind spots.

- **REAL** is the best controlled match for LinkedIn-like interaction and realistic consumer workflows such as checkout, booking, messaging, calendars, travel, and rides.
- **WebArena-Verified Hard** provides the strongest audited deterministic-evaluation foundation among the candidates and includes difficult Reddit-like, commerce, administration, GitLab, and cross-site tasks.
- **VisualWebArena** prevents the suite from rewarding a harness that succeeds only when hidden structure or accessibility text makes the interface easy to parse.
- **WorkArena++** contributes difficult configuration-heavy enterprise workflows and has substantial unsolved Level 3 headroom.
- **WebChoreArena** adds long-horizon memory and calculation pressures that are weakly represented elsewhere.
- **WebForge Level 3** uniquely exposes controlled popups, cookie dialogs, delays, and interface noise, but its default LLM answer judge is not sufficient for primary-gate use.

The allocation caps every source at 25 tasks and limits the combined WebArena-derived family to 45 tasks. This reduces dependence on any one UI stack, task-writing style, action vocabulary, or evaluator family.

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
4. WebForge tasks have deterministic state or operation-code verification independent of its default LLM answer judge;
5. WorkArena access and reproducible instance reset are demonstrated;
6. selected tasks are run with both a simple baseline and a known strong harness under recorded protocols;
7. saturated, broken, unsafe, judge-fragile, or benchmark-leaking tasks are rejected;
8. the exact 100-task manifest, replacement pool, and nested 20-task smoke subset are reviewed; and
9. the project owner explicitly accepts this ADR or a revised portfolio.

Until then, this portfolio guides research only.

## First replacement candidate

WARC-Bench is the preferred replacement candidate because it offers archived real webpages, deterministic rewards, and difficult GUI subtasks across many sites. It is not in the proposed allocation because a runnable public release and licensing path were not located during this review. That operational fact must be rechecked before the final manifest is frozen.

## Revisit triggers

Revisit the allocation if task-level auditing finds insufficient hard tasks, correlated templates, evaluator defects, inaccessible infrastructure, licensing restrictions, or local strong-harness success above the desired discrimination range.
