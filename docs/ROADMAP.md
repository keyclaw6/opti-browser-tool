# Roadmap

## Phase 0 — Alignment and contracts

Accept or amend ADRs 0002–0006. Finalize versioned task, experiment, trace-event, and result contracts. Choose repository visibility and license. Define benchmark-source inventory and task-selection rubric.

Exit criterion: two people can read the same experiment record and agree on what is fixed, what changes, what evidence is allowed, and how the result will be classified.

## Phase 1 — Minimal vertical slice

Implement one browser backend, deterministic environment reset, artifact recording, one visual observation adapter, one CLI observation adapter, explicit action mechanisms, deterministic verifiers, and a small smoke suite.

Start with approximately 12–20 tasks chosen to exercise popups, dynamic updates, scrolling, tabs, forms, content-editable controls, stale references, and recovery. Do not begin with a 100-task suite or uncontrolled live sites.

Exit criterion: the same versioned tasks run through both lanes, traces replay coherently, evaluator mistakes can be detected, and implementation activation can be audited.

## Phase 2 — Credible baseline suite

Audit candidate benchmarks and licenses, select roughly 100 difficult interaction tasks by failure-mode coverage, measure instability, create hidden holdout handling, and establish baseline distributions.

Exit criterion: task coverage and variance are understood well enough to predeclare meaningful acceptance gates.

## Phase 3 — Auto-research loop

Add trace summarization, root-cause clustering, hypothesis generation, constrained implementation, activation audit, paired scheduling, gating, experiment ledger, and learning updates.

Exit criterion: at least three consecutive research iterations are executed without manual repair of the experiment record, and accepted changes survive regression plus holdout.

## Phase 4 — Expansion

Add Firefox/WebKit or other backends, permitted live-site suites, stronger recovery policies, model routing, hybrid architecture, code-generated repetitive workflows, and cross-model transfer studies.
