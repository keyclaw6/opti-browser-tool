# Harness-Under-Test Component Tree

- Status: specification under [ADR-0015](../adr/0015-auto-research-loop-architecture.md) (Accepted 2026-07-13) — the binding component-tree contract. This document does **not** select a browser backend or control library; [ADR-0003](../adr/0003-initial-browser-backend.md) remains open, and this layout must be implementable over any backend that satisfies the session interface.
- Purpose: define the directory layout, file contracts, registration format, trace hooks, and seed harness so that (a) the optimizer's writable surface is mechanically checkable, (b) every failure cluster maps to exactly one component, and (c) attribution stays clean.

## 1. Layout

```text
harness/
  components/               # optimizer-writable (the ONLY writable surface)
    policy/                 # 1 — system prompt and decision policy
    observation/            # 2 — page representation offered to the executor
    actions/                # 3 — action vocabulary and validation
    tool_descriptions/      # 4 — how tools present themselves to the model
    middleware/             # 5 — cross-cutting runtime behavior
    skills/                 # 6 — verified site-general workflows
    sub_agents/             # 7 — delegated specialist roles
    memory/                 # 8 — long-term lessons and runtime workflow memory
  infra/                    # optimizer read-only (infrastructure mounts)
    session/                # browser-neutral session interface + backend adapters
    model/                  # executor model configuration (pinned per experiment)
    tracer/                 # trace-event emission per schemas/trace-event.schema.json
    budgets/                # step, token, and time ceilings
  lanes/                    # pinned lane configurations (see §5)
    structured.lane.json
    visual.lane.json
```

Verifiers, bridges, suites, and judge assets live outside `harness/` entirely (evaluation plane).

## 2. Component contracts

Each component is a file-level git-tracked mount point. Every failure cluster in the register maps to **exactly one** component; a cluster that seems to span two components is split by the Analyst before it reaches the optimizer.

1. **policy/** — the system prompt and top-level decision policy. Nothing else hides prompt text; if it steers the model, it lives here. (Evidence note: AHE ablation found system-prompt-only optimization *negative*; expect this component to earn few accepted changes.)
2. **observation/** — DOM/accessibility-tree distillation, hierarchical page structuring, screenshot and set-of-marks policy, and element references. **Element references carry an observation epoch** (`browser_state_epoch`); after a page mutation, stale references must fail explicitly rather than resolve to a different control.
3. **actions/** — primitive actions plus compound actions. Every action declares **pre-execution validation** and **postconditions** that the runtime can verify after dispatch; silent failure is a defect of this component.
4. **tool_descriptions/** — the model-facing descriptions of the action/tool surface, separated from implementation so wording experiments are attributable.
5. **middleware/** — context compaction, retry and recovery, the destructive-action interlock with the HTTP-method monitor, post-action state verification, and loop detection.
6. **skills/** — verified, site-general workflows. The solver proposes; an **independent verifier admits** (never the optimizer or executor itself); admission requires the generality lint plus transfer evidence.
7. **sub_agents/** — delegated roles (for example a dedicated form-filler), each with its own visibility boundary.
8. **memory/** — long-term lessons (generality-gated) and runtime workflow memory (reset per evaluation run by default; accumulating configurations are labeled and scored separately).

## 3. Registration format

Each component directory contains a `component.json`:

```json
{
  "component": "observation",
  "version": "0.1.0",
  "files": ["distiller.py", "epochs.py", "som_policy.py"],
  "interfaces": ["Observation.render(session) -> ExecutorView"],
  "activation_events": ["model_observation.payload.component == 'observation'"],
  "emits": ["model_observation", "browser_state"]
}
```

- `activation_events` is the machine-checkable promise the E1 activation audit verifies: a change to this component must be observable in traces as these events.
- `emits` binds the component to trace `event_type` values so the Analyst can attribute events to components without heuristics.
- The Conductor rejects (E0) any diff that changes files not listed in some `component.json`, and any manifest whose `target_component` does not match the diff.

## 4. Trace hooks

All components emit through `infra/tracer/` per [`schemas/trace-event.schema.json`](../../schemas/trace-event.schema.json):

- every event carries `actor`, `event_type`, `visibility`, and (for observation/action events) `browser_state_epoch`;
- executor-visible content is tagged `executor`; diagnostic captures (network, console, full DOM) are tagged `judge`/`orchestrator` and never re-enter executor context;
- action events record intent, mechanism, target reference **with epoch**, declared postconditions, and the post-dispatch verification result — this is what makes divergence analysis and H-class hypotheses testable.

## 5. Lanes are pinned configurations, not codebases

A lane is a frozen configuration over components 2 and 3:

- `structured.lane.json` — accessibility-tree observation with epoch-scoped element references; DOM-triggered actions.
- `visual.lane.json` — screenshot + set-of-marks observation; coordinate-based actions.

Both lanes share components 1 and 4–8 and all contracts, satisfying the charter's comparability requirement. A hybrid lane is a third configuration added only per the charter's maturity condition. This section records the proposed resolution direction for [ADR-0002](../adr/0002-shared-substrate-and-lane-boundaries.md); that ADR remains open until explicitly moved.

## 6. Seed harness definition

The first harness the loop ever evaluates is deliberately minimal, in the style of the reproducible BrowserGym reference agent:

- `policy/`: a plain task-following system prompt;
- `observation/`: structured lane; flat distilled accessibility tree with epoch-scoped references;
- `actions/`: primitives only (click, type, select, scroll, navigate, tab ops), each with basic postconditions;
- `tool_descriptions/`: direct descriptions of the primitives;
- `middleware/`, `skills/`, `sub_agents/`: **empty**;
- `memory/`: disabled.

Rationale: a minimal seed protects attribution — early gains are attributable to single added mechanisms rather than interactions among a pre-loaded stack (AHE's minimal-seed finding). An optional one-shot explore pass over the surveyed browser-agent codebases may propose initial skill/middleware candidates; they enter through the normal manifest + gate channel and receive no special protection.

## 7. What this scaffold deliberately defers

Backend selection (ADR-0003, open), the concrete session-interface API surface,
and implementation of the harness-component directories above remain deferred.
The eval/judge/loop boundary now implements ADR-0004's strict task-local
result/trace/artifact validation and fail-closed benchmark admission; emission
from the first real source bridge is still a pre-activation requirement. This
document constrains the component shape; it does not build those components.
