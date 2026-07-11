# Architecture Overview

## System layers

```text
research orchestrator
  ├─ experiment planner and manifest
  ├─ implementation auditor
  ├─ scheduler and baseline/treatment pairing
  └─ gate and decision recorder

evaluation plane
  ├─ deterministic verifiers
  ├─ completion judge
  ├─ visual/process judge
  ├─ trace/root-cause judge
  └─ adjudicator

executor plane
  ├─ visual-first lane
  ├─ terminal/CLI lane
  └─ later hybrid/router lane

shared runtime
  ├─ task and environment manager
  ├─ browser-neutral session interface
  ├─ backend adapters
  ├─ trace/event recorder
  ├─ artifact store
  └─ metrics collector
```

## Core contracts

- **Task:** public executor goal plus private setup, verifier, and teardown.
- **Observation:** lane-specific executor view with an explicit visibility boundary.
- **Action:** intent, mechanism, target, parameters, preconditions, and result.
- **Trace event:** ordered record linking model, browser, tool, judge, and infrastructure behavior.
- **Result:** objective outcome, metrics, infrastructure validity, judge diagnoses, and artifact references.
- **Experiment:** predeclared hypothesis, evidence, treatment, predictions, fixed variables, evaluation plan, and gate.

## Browser session interface

A session exposes lifecycle, observation, action, tab, state, and artifact operations. Backends advertise capabilities. The interface must not imply that a DOM reference is available to a visual-only lane.

## Observation epochs

Every structured element reference belongs to a browser-state epoch. Dynamic page changes advance the epoch or mark references stale. An action using a stale reference must fail explicitly rather than clicking an unintended replacement.

## Executor and judge separation

The runtime may capture DOM, network, console, or CDP evidence even when the executor is screenshot-only. Visibility metadata prevents that evidence from entering executor context while allowing diagnostics and counterfactual analysis.

## Failure boundaries

At minimum, failures are separated into task/environment setup, model perception, target grounding, planning, action dispatch, browser/tool execution, state/session management, recovery, premature completion, verifier/evaluator, and infrastructure.
