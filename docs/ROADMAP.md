# Roadmap

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

1. a provisional **20-task bring-up set** for validating runners, reset logic, traces, and verifiers;
2. a stable **10–20-task smoke suite**, likely drawn from the bring-up work, for fast implementation checks;
3. an approximately **100-task primary suite** for meaningful comparisons;
4. a separate **regression suite** that grows when previously failing cases are fixed; and
5. a **hidden holdout** whose traces and verifier internals are not exposed to the optimizer.

Before freezing any suite, run the selected tasks through a known working harness and confirm setup, completion conditions, verifier behavior, reproducibility, and artifact capture.

Exit criterion: the 20-task bring-up set works end to end; the 100-task selection and suite roles are documented; verifier defects and unstable tasks are identified rather than counted as agent failures.

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
