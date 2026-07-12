# Pre-Research Workstreams

## Current status

The workstream structure remains active, but the project is no longer at the initial planning-only boundary. Workstream B has produced a 140-task provisional pool and orchestration runner; those candidates are selected for validation, not finally admitted. Environment, verifier, calibration, and final-filtering work remain. Workstreams A and C remain largely unexecuted, and the auto-research loop has not started.

## Purpose

The project has several difficult prerequisites. They should be solved as separate research and engineering workstreams before the auto-research loop is allowed to optimize the browser harness. This document defines how each workstream will be approached; it does not perform the research or settle its conclusions.

## Common method

Each workstream should use the same disciplined sequence:

1. state the decision or capability question;
2. define an evidence-collection rubric before reviewing candidates;
3. inventory relevant sources and implementations;
4. extract comparable facts and trace them to sources;
5. turn observations into explicit hypotheses;
6. identify a small validation or counterexample test;
7. record uncertainty, dependencies, and likely regressions;
8. write a decision or readiness memo; and
9. require explicit approval where the outcome changes project direction.

This prevents the project from choosing a familiar tool first and inventing reasons afterward.

## Workstream A — Existing browser harnesses and baseline hypotheses

### Question

Which existing implementation, control substrate, or combination of ideas should form the first experimental baseline?

### Inputs

- the browser-agent repositories already saved for this project;
- mature open-source browser and computer-use harnesses;
- relevant papers, benchmark reference agents, and technical reports; and
- runnable examples and traces where available.

### Method

Review every candidate through one shared rubric. At minimum, record its browser engine, control layer, observation representation, action vocabulary, screenshot/vision path, DOM/accessibility path, native input support, tab and session handling, recovery behavior, tracing, evaluator integration, installation burden, maintenance state, and license.

Separate three outputs that are often incorrectly mixed together:

- **reusable ideas**, which may transfer even if the repository is not used as a base;
- **testable hypotheses**, such as when native input or structured references should improve reliability; and
- **candidate foundations**, which must also be maintainable and suitable for controlled experiments.

### Readiness output

A comparative report, hypothesis backlog, shortlist, and explicit first-baseline decision memo. ADR-0003 remains open until that memo is reviewed.

## Workstream B — Evaluation sets and regression design

### Question

Which tasks measure difficult browser interaction reliably enough to guide optimization without rewarding information retrieval, memorization, or evaluator weaknesses?

### Method

First audit benchmarks at the environment and verifier level. Then audit individual tasks. Map every candidate task to a browser-interaction failure taxonomy such as dynamic updates, popups, scrolling, tabs, forms, visual-only controls, stale references, state recovery, and premature completion.

Use stratified selection rather than random sampling. Reject or quarantine tasks with broken setup, ambiguous success conditions, unavailable dependencies, excessive information-retrieval emphasis, or instability that cannot be measured.

Use the 20-task smoke subset to prove task reset, trace capture, verifier correctness, and repeatability, then execute the full 140-task provisional pool. Filter the validated pool into the final approximately 100-task primary suite. Keep regression and hidden-holdout roles distinct from both.

### Validation

Run selected tasks through a known working harness. Inspect both passes and failures. A task is not considered valid merely because a benchmark package executes; its intended success state, verifier, artifacts, and reset behavior must be checked.

### Readiness output

A benchmark inventory, task-selection rubric, failure-mode coverage matrix, validated bring-up set, proposed primary suite, regression policy, and holdout protocol.

## Workstream C — Verifiers and council of judges

### Question

How can the evaluation system detect real completion and diagnose failures without introducing unacceptable false positives, false negatives, or hidden information leakage?

### Method

Start with deterministic state evidence whenever possible. Define the exact inputs and prohibited information for each judge. Build specialized judges for completion, visual/process interpretation, trace root cause, implementation activation, and adjudication only where those roles add information beyond objective metrics.

Create a labeled calibration collection with deliberately difficult cases: claimed success without state change, correct state reached by an odd path, near completion, stale screenshots, popup interference, disabled treatments, infrastructure failures, and conflicting evidence. Measure judge behavior against labels and against one another. Use blinded baseline/treatment comparisons where appropriate.

### Readiness output

Versioned judge prompts or programs, evidence contracts, calibration results, disagreement rules, adjudication rules, and documented failure limits.

## Workstream D — Integration of the auto-research loop

### Question

How should the proven auto-harness structures be adapted to browser-agent experiments after the first three workstreams are ready?

### Method

Reuse rather than reinvent:

- from `auto-harness`: the benchmark → analyze → improve → gate → record → learn cycle, protected regression tasks, and persistent learnings;
- from `agentic-harness-engineering`: traces as the main analysis object, constrained component changes, evidence-backed hypotheses, predicted task flips, implementation activation checks, and change attribution;
- for this project: browser-state synchronization, executor-versus-judge visibility boundaries, action-mechanism tracking, dynamic-site variance handling, and counterfactual diagnosis.

Integrate these parts only after a baseline candidate, valid bring-up tasks, and calibrated evaluators exist. Otherwise the loop would optimize against an unstable substrate.

### Readiness output

A minimal end-to-end baseline/treatment run on the bring-up set, with complete trace evidence, implementation audit, evaluation, classification, regression handling, and recorded learnings.

## Current boundary

The project has moved beyond initial benchmark discovery: 140 exact provisional candidates have been selected, normalized, and placed in a runnable orchestration suite. They are not finally admitted, and this is not a frozen benchmark. The tasks still require real environment setup, reset checks, known-good runs, adversarial verifier audits, repeated task-level calibration, and filtering.

The repository still does not select the browser foundation, approve judge prompts, freeze the final primary/regression/holdout suites, or start the auto-research loop. Those choices require the remaining workstream evidence and explicit decisions.
