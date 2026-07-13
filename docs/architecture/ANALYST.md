# The Analyst — Trace Analysis Pipeline Specification

- Status: specification under [ADR-0015](../adr/0015-auto-research-loop-architecture.md) and [ADR-0016](../adr/0016-judge-panel-and-verifier-audit-protocol.md) (both Accepted 2026-07-13).
- Role: the loop's phase-C DISTILL pipeline and, identically, the **root-cause analyst** seat on the T2 judge panel. The Analyst is the browser-native equivalent of AHE's Agent Debugger, rebuilt on this project's trace contract instead of the reference project's closed tooling.

## 1. Guarantees

1. **Non-scoring.** The Analyst never produces or modifies a score, never overrides a verifier, and has no vote in any gate. Its outputs are diagnostic artifacts.
2. **No write access** to the harness workspace or the evaluation plane. Its writable surface is the analysis output directory and the failure-cluster register only.
3. **Event-addressable claims.** Every factual claim in every report must cite `run_id` + `event_id` references that a reviewer can resolve in the stored trace. A claim without an address is a defect.
4. **Pinned like a verifier.** Analyst prompts and model snapshots are versioned; a change to either is a recorded evaluation-plane change ([ADR-0016](../adr/0016-judge-panel-and-verifier-audit-protocol.md) calibration rule 4). Judge roles run on strong pinned models, exempt from the executor cost economy.

## 2. Input contract

Per [`schemas/trace-event.schema.json`](../../schemas/trace-event.schema.json):

- trace events whose `visibility` includes `judge` or `orchestrator`, plus all executor-visible events — never `restricted` material, and never holdout traces;
- result records (fail-closed statuses: `passed`, `failed`, `invalid`, `error`, `skipped` — `invalid`/`error` are infrastructure, not behavior);
- task records (goals and public metadata; **not** private verifier internals);
- manifest history and the current failure-cluster register;
- `browser_state_epoch` on observation/action events, which the Analyst uses to detect stale-reference and wrong-target failures mechanically before interpretation.

## 3. Layered outputs

- **L0 — run overview**: suite-level outcome deltas vs. the previous iteration, validity accounting (how many `invalid`/`error` and why), flip list (pass→fail, fail→pass), anomaly flags from T1 cross-checks.
- **L1 — per-task reports** (for failures, flips, and partial passes): a reconstructed timeline naming the first divergent event, the failure boundary crossed (taxonomy class), the suspected component, and the evidence addresses. Passes get L1 reports only when flagged (for example a pass with unexpected mutations).
- **L2 — failure-cluster register update**: clusters of L1 findings sharing a taxonomy class and suspected component (see §4).
- **L3 — divergence analysis** on partial-pass and flipped tasks: where the trajectory left the previously working path — same task, prior run vs. current run, first divergent epoch/event, with the epoch's page-state evidence.
- **Attribution embedding**: for the previous manifest, predicted-vs-observed flips per edit, feeding phase B's keep/revert/partial verdicts and the prediction-accuracy ledger.

## 4. Failure-cluster register

Draft record shape (to be promoted into `schemas/` at implementation time):

```json
{
  "cluster_id": "clu-0007-stale-ref-after-filter",
  "taxonomy_class": "dynamic-update/stale-reference",
  "suspected_component": "observation",
  "members": [
    {"task_id": "workarena-l2-...", "run_id": "iter-012-r1", "event_refs": ["evt-0812"]}
  ],
  "first_seen": "iter-009",
  "total_failures": 11,
  "resolution_rate": 0.18,
  "priority": "total_failures x (1 - resolution_rate); exact weighting is an ADR-0015 open parameter",
  "status": "unresolved",
  "resolution_history": [
    {"manifest": "exp-0031", "outcome": "partial", "note": "fixed list views, table views still fail"}
  ]
}
```

Rules: one suspected component per cluster (the Analyst splits multi-component clusters); `status` ∈ unresolved / improving / resolved / reopened / quarantined-verifier-suspect; a cluster whose failures smell like evaluator error is routed to the quarantine queue, not to the optimizer.

## 5. Failure taxonomy

The taxonomy starts from the failure boundaries in [`OVERVIEW.md`](OVERVIEW.md) (setup, perception, grounding, planning, dispatch, execution, state/session, recovery, premature completion, verifier/evaluator, infrastructure), refined by the charter's browser-priority classes: dynamic updates, popups/interference, scrolling, tabs, forms, visual-only controls, stale references, state recovery, premature completion, and long-horizon memory. The taxonomy is versioned data, not code; extending it is an evaluation-plane change.

## 6. Reporting discipline

- The Analyst proposes **explanations and cluster priorities**, never changes; the optimizer owns hypotheses, the Conductor owns decisions.
- Uncertainty is stated per finding (`confident` / `probable` / `speculative`), and speculative findings never raise a cluster's priority on their own.
- When evidence is insufficient (missing artifacts, truncated traces), the Analyst reports the instrumentation gap explicitly instead of guessing — those reports are how [ADR-0004](../adr/0004-trace-storage.md) requirements accumulate.
