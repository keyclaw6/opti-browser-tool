# Decision timeline

This timeline explains the sequence of decisions and corrections. The authoritative current status remains [`DECISION_REGISTER.md`](DECISION_REGISTER.md); this document exists so a reviewer can understand *why* the repository contains apparently conflicting historical statements.

All events below occurred on 2026-07-11 unless noted otherwise.

## 1. Project constitution accepted

**ADR-0001 — Accepted.**

The project owner established that the work optimizes the complete browser-agent harness around a mostly fixed executor model, with task success and repeatability ahead of efficiency. Visual-first and terminal/CLI lanes remain distinct until there is evidence for a hybrid. Deterministic state verification is preferred, and live-site work must use permitted accounts.

Reason: the project needed a durable objective and evaluation boundary before implementation choices could be made.

## 2. Early architecture directions deliberately left open

**ADR-0002 through ADR-0006 — Open.**

Initial drafts proposed a shared substrate, Chromium/Playwright research baseline, trace storage, experiment gating, and live-site controls. The project owner explicitly declined to accept these choices before reviewing existing browser harnesses and benchmark requirements.

Reason: familiarity with Playwright or Chromium is not evidence that it is the best first foundation. The project must first extract hypotheses and implementation lessons from existing systems.

## 3. Smoke-suite nesting accepted

**ADR-0007 — Accepted.**

The 20-task smoke suite must be contained in the primary suite rather than maintained as an unrelated collection.

Reason: nesting avoids duplicated setup and verifier work and ensures the fast gate exercises mechanisms that matter to the primary evaluation.

## 4. Benchmark-source and regression policies proposed

**ADR-0008 and ADR-0009 — Proposed, not binding.**

A benchmark-source portfolio and a regression seeding/promotion process were documented for review.

Reason: source quotas and regression thresholds require task-level evidence and repeated baseline runs. They should not be treated as accepted merely because candidate files were implemented.

## 5. Difficulty-band correction

**ADR-0010 — originally proposed.** It described a 35–70% task-level calibration band.

**ADR-0011 — superseded.** A later interpretation incorrectly recorded a 40% minimum.

**ADR-0012 — Accepted.** The project owner explicitly corrected the range to **35–70%, inclusive**, with a 35% floor.

Reason: tasks below the band provide too little success signal for efficient comparison, while tasks above the band risk saturation. Source-family aggregate scores may screen benchmarks, but they may never be copied onto individual tasks as if they were per-task measurements.

The superseded files are retained rather than rewritten so the mistake and correction remain reviewable.

## 6. Runnable-suite architecture implemented, initial count superseded

**ADR-0013 — Superseded.**

The first runnable draft normalized 100 tasks and introduced backend-neutral manifests, a standard result contract, fixture and command adapters, source registry adapters, and fail-closed infrastructure handling.

Reason: the project needed an executable orchestration layer without prematurely selecting Playwright, Selenium, BrowserGym, CDP, native input, or another browser substrate. ADR-0014 superseded the active 100-task definition. The bridge code remains provisional implementation infrastructure, not an accepted browser-foundation decision.

## 7. All 140 candidates retained for initial execution

**ADR-0014 — Accepted.**

The project owner directed that all 140 sourced candidates remain in the active provisional primary pool until they have been run and audited. The target final suite remains approximately 100 tasks.

Reason: removing 40 candidates before environment, verifier, reset, duplication, and task-level calibration checks would make exclusions heuristic and difficult to review.

## Current accepted decisions

- ADR-0001: project constitution.
- ADR-0007: smoke is nested in primary.
- ADR-0012: task-level reference-success band is 35–70%, inclusive.
- ADR-0014: run all 140 provisional candidates before filtering.

## Current non-decisions

The repository has **not** selected:

- a browser engine or control library;
- visual-first, CLI, or hybrid as the first winning architecture;
- native input versus DOM-triggered actions as a default;
- the final trace format and artifact store;
- the final baseline/treatment gate;
- permanent regression promotion thresholds;
- the hidden holdout tasks;
- executor or judge models;
- detailed live-site procedures; or
- the final approximately 100 admitted tasks.

These items remain open because the required evidence has not yet been gathered.
