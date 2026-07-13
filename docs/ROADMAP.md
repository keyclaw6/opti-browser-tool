# Roadmap

## Current progress

Phase 0 is complete. Phase 2 is active: the 140-task provisional pool and orchestration runner exist, but source bridges, real environment checks, verifier audits, repeated task-level calibration, and final filtering remain incomplete. Phase 1 baseline research and Phase 3 judge construction are still pending. The auto-research loop has not started.

This roadmap deliberately separates the prerequisites for trustworthy research from the later auto-research loop. Phases 1–3 may overlap where useful, but none should be treated as complete without its review gate.

## Phase 0 — Repository and alignment groundwork

Record the charter, decision process, open decisions, research workstreams, draft contracts, and terminology. Keep technical choices open unless explicitly approved.

Exit criterion: the repository clearly distinguishes accepted constraints, open questions, future research, and implementation work.

## Phase 1 — Existing-harness research and first-baseline decision

Inventory the browser-agent repositories collected for this project and other directly relevant implementations. Review each with a common rubric covering browser and control substrate, observation format, action mechanism, vision/DOM/accessibility use, native input, state handling, recovery, instrumentation, evaluation, maintenance, and licensing.

Produce:

- a sourced harness inventory;
- comparable architecture summaries;
- reusable implementation ideas;
- explicit failure and tradeoff hypotheses;
- a shortlist of candidate starting points; and
- a decision memo for the first baseline.

Exit criterion: the first baseline recommendation is supported by evidence and testable hypotheses, then explicitly approved. No backend is selected before this gate.

## Phase 2 — Evaluation-suite design and validation

Audit candidate benchmarks and individual tasks. Select tasks by interaction difficulty and failure-mode coverage rather than random sampling or benchmark reputation alone.

Build the evaluation layers in this order:

1. assess source benchmarks and propose a source allocation;
2. execute and validate the complete **140-task provisional candidate pool** under ADR-0014;
3. filter it into an approximately **100-task final primary suite** with a stable **20-task smoke subset inside it** under ADR-0007;
4. grow a separate **regression suite** when previously failing cases are fixed;
5. protect a disjoint **hidden holdout** whose traces and verifier internals are not exposed to the optimizer; and
6. keep permitted-account live-site transfer tests in a separately scored suite.

The smoke cases also serve as the first end-to-end bring-up cases for runners, reset logic, traces, and verifiers. Temporary diagnostic tasks may be used during development but are not an additional scored suite.

**Batch 2 requirement:** the current 140 candidates contain zero popup/interference and zero long-horizon-memory coverage — two of the charter's priority failure classes — and band filtering is expected to cut the pool toward 70–100 survivors against a ~100 target. A second sourcing batch covering those two classes must be planned concurrently with calibration, not after it.

Before freezing any suite, run the selected tasks through a known working harness and confirm setup, completion conditions, verifier behavior, reproducibility, and artifact capture.

Exit criterion: the 20-task smoke subset and all source bridges work end to end; the 140 candidates have recorded validation outcomes; an approximately 100-task final selection is justified; verifier defects and unstable tasks are not counted as agent failures.

## Phase 3 — Verifier and judge construction

Define objective browser-state measurements first. Then design specialized LLM judges only for interpretation that cannot be computed directly. Build a labeled calibration corpus containing true successes, false completion claims, near misses, tool failures, browser-state loss, judge disagreements, and intentionally misleading traces.

Validate false-positive and false-negative rates, evidence sufficiency, blinding, independence, adjudication, and resistance to evaluator gaming.

Exit criterion: the panel reliably distinguishes completion, process quality, root cause, implementation failure, and infrastructure failure on held-back calibration cases.

## Phase 4 — Auto-research substrate integration

Reuse the loop, regression, recording, and learning structure from `auto-harness`; reuse the trace-first analysis, component-level changes, activation checks, and predicted-impact manifests from `agentic-harness-engineering`; add browser-specific observation boundaries, synchronized artifacts, action-mechanism tracking, and evaluator safeguards.

Integrate only enough executor functionality to prove a vertical slice against the validated bring-up set. This phase does not assume the final hybrid architecture.

Exit criterion: baseline and treatment can be run, audited, judged, compared, and recorded without manual repair of the experiment record.

## Phase 5 — Controlled auto-research

Begin focused, falsifiable iterations on the validated suites. Promote fixed failures into regression coverage, protect the hidden holdout, and expand toward cross-browser, live-site, hybrid-routing, and cross-model studies only after the core loop is credible.
