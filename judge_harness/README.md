# opti-judge — evaluation-plane judge instrumentation

**Status: provisional infrastructure.** Implements the T0–T3 layering proposed
in [ADR-0016](../docs/adr/0016-judge-panel-and-verifier-audit-protocol.md)
(Proposed, not Accepted — per [`docs/DECISION_PROCESS.md`](../docs/DECISION_PROCESS.md)
this code settles nothing). No judge model is pinned (Open Question 17), no
judge is calibrated, and no verifier exists yet to admit — what exists is the
machinery that makes those steps mechanical when bridges arrive.

## What is real today

| Layer | Component | State |
|---|---|---|
| T0 | **Probe-kit admission harness** (`probekit.py`) | Working. Runs a verifier command against the six probe kinds (oracle → 1, near-miss → 0, premature-stop → 0, harmful-extra-action detected, stale/fabricated rejected, malformed → `invalid` never `failed`), pins version+checksum, writes admission records, archives probes as calibration-corpus seeds. **This file is the contract every bridge verifier must pass.** |
| T1 | **Deterministic cross-checks** (`t1_checks.py`) | Working over trace JSONL per `schemas/trace-event.schema.json`: HTTP-method side-effect monitor, zero-action-pass, action-count anomaly, loop detector, stale-epoch check, expected-state assertions. Flags carry direction (`fp_suspect` / `fn_suspect` / `side_effect` / `anomaly`) and event citations. |
| T2 | **Panel scaffolding** (`panel.py`, `llm.py`, role assets in [`evals/judges/roles/`](../evals/judges/roles/)) | Five roles defined as versioned JSON (prompt, evidence contract, operating point). Pluggable model client (`fixture` for tests, `command` for the owner's runner, `openai-compatible` via env vars). **Trust gating:** every judgment carries `trusted: false` until the role meets its operating point on the calibration corpus — untrusted flags are diagnostic text, consumed by nothing. The adjudicator is deterministic code: unresolved disagreement always quarantines, never adjusts a score. |
| T3 | **Quarantine queue** (`quarantine.py`) + **calibration corpus** (`corpus.py`) | Working. Disagreement routing (`router.py`) implements both closure chains: FP defense (pass + contrary evidence → quarantine) and FN recovery (fail + fn-suspect → queue whose only remedies are verifier/task repair — there is deliberately no "override score" resolution). Resolutions append to the corpus automatically; `measure` computes per-judge precision/recall. |
| Loop wiring | `opti_loop` gate | A pending quarantine entry on a compared task makes the E5 comparison **ineligible under the strict validity policy** (fail-closed) and is excluded under quorum. The loop never reads untrusted judge flags. |

## What is deliberately NOT here yet

1. **Real verifiers** — they arrive with the five benchmark bridges; each must
   pass this probe kit before scoring anything.
2. **Judge model pins** — Open Question 17; judges run on strong pinned models,
   never the loop's cheap executor. Until pinned, roles default to the
   `fixture` provider and cannot produce trusted output.
3. **Calibration measurements** — the corpus fills from probe archives and
   quarantine resolutions during bridge bring-up; per-benchmark operating
   points are measured then, not invented now.
4. **Judge-only evidence streams** (screenshots, full DOM, network bodies) —
   ADR-0004 territory; the evidence API already enforces visibility contracts
   and structurally refuses `restricted` (holdout) material.

## Use

```bash
make judge-test    # full test suite (probe kit, T1, routing, corpus, panel)

# deterministic cross-checks over a trace, with quarantine routing:
opti-judge t1 --trace run.jsonl --status passed --expect-side-effects none \
  --task-id real-v1-x --queue runs/quarantine/queue.jsonl

# verifier admission (bridges will ship probe kits in this layout):
opti-judge probe --verifier-id wa-verifier --command "python verify.py --trace {trace_json} --result {result_json}" \
  --task-id webarena-verified-423 --kit probes/webarena-verified-423/

# the owner's T3 seat:
opti-judge quarantine list --queue runs/quarantine/queue.jsonl
opti-judge quarantine resolve --queue ... --entry-id X --resolution verifier_defect \
  --note "..." --corpus runs/calibration-corpus/corpus.jsonl
```
