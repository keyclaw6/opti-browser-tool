# Project Charter

## Central research question

What combination of browser backend, observation format, action interface, planning policy, recovery behavior, and model produces the most reliable general-purpose web agent?

## Primary objective

Reliable computer and browser use. Search quality and question answering matter only when they are necessary to complete an interaction task.

## Optimization order

1. Correct task completion.
2. Reliability across repeats and changing page state.
3. Transfer to tasks not used to invent the change.
4. Recovery from predictable interface and tool failures.
5. Efficiency among solutions with comparable reliability.

## Scope

The harness may evolve browser-control tools, observation representations, screenshots and vision use, DOM and accessibility use, prompts and policies, planning and recovery loops, tool descriptions, browser/session state management, input interfaces, error handling, context compression, routing, browser backend, verification, and judging.

The base executor model normally remains fixed within an experiment. Model comparisons are separate experiments and must not be mixed with harness-change attribution.

## Required research lanes

Visual-first and terminal/CLI approaches are developed as distinct lanes. A hybrid lane or router is introduced only after the independent lanes are mature enough to reveal what should be combined.

All lanes use common versioned contracts for tasks, traces, results, metrics, and evaluation.

## Research-loop invariant

Every treatment must state, before its main evaluation:

- trace evidence;
- suspected root cause;
- targeted change;
- tasks or failure classes expected to improve;
- tasks or failure classes that may regress;
- implementation surface and activation evidence; and
- acceptance criteria.

Results are classified as `accepted`, `rejected`, `inconclusive`, or `invalid`. An implementation or infrastructure failure makes an experiment invalid; it does not falsify the underlying hypothesis.

## Evaluation invariant

Deterministic browser-state verifiers take precedence where feasible. LLM judges interpret evidence and diagnose behavior; they do not replace objective measurements without an explicit reason.

Visible development tasks, permanent regression tasks, and a hidden holdout are separated. The optimizing agent must not receive holdout traces or private verifier details.

## Safety invariant

Live-platform testing uses permitted accounts and respects platform rules and access controls. Credentials and sensitive user data are not placed in model-visible traces. Destructive or externally visible actions require explicit task authorization and cleanup behavior.

## Definition of project success

The auto-research process repeatedly produces improvements that increase task-completion reliability, transfer beyond discovery tasks, survive regressions and repeated runs, have trace-supported explanations, do not exploit weak evaluators, and respect platform constraints.
