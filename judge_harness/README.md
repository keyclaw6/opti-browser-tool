# opti-judge — evaluation-plane judge instrumentation

**Status: reference implementation of accepted architecture.** Implements the
T0–T3 layering of [ADR-0016](../docs/adr/0016-judge-panel-and-verifier-audit-protocol.md)
(**Accepted 2026-07-13**). Calibration-before-trust remains operative: no judge
model is pinned yet (Open Question 17), no judge is calibrated, and no verifier
exists yet to admit — what exists is the machinery that makes those steps
mechanical when bridges arrive, and nothing downstream consumes an
uncalibrated judge.

## What is real today

| Layer | Component | State |
|---|---|---|
| T0 | **Probe-kit admission harness** (`probekit.py`) | Working. Runs a verifier command against the six probe kinds (oracle → 1, near-miss → 0, premature-stop → 0, harmful-extra-action detected, stale/fabricated rejected, malformed → `invalid` never `failed`), pins version+checksum, writes admission records, archives probes as calibration-corpus seeds. **This file is the contract every bridge verifier must pass.** |
| T1 | **Deterministic cross-checks** (`t1_checks.py`) | Working over trace JSONL per `schemas/trace-event.schema.json`: HTTP-method side-effect monitor, zero-action-pass, action-count anomaly, loop detector, stale-epoch check, expected-state assertions. Flags carry direction (`fp_suspect` / `fn_suspect` / `side_effect` / `anomaly`) and event citations. |
| T2 | **Panel scaffolding** (`panel.py`, `llm.py`, role assets in [`evals/judges/roles/`](../evals/judges/roles/)) | Five roles as versioned JSON. Pluggable model client (`fixture`/`command`/`openai-compatible`). **Trust gating** (F12): a judgment is `trusted` only after the role meets its operating point on **distinct, class-balanced** corpus cases (25 copies of one case cannot certify trust). Untrusted judgments **never certify trust and never touch a score**; they *may* still raise a quarantine via the deterministic adjudicator (unresolved disagreement always quarantines). |
| T3 | **Quarantine queue** (`quarantine.py`) + **calibration corpus** (`corpus.py`) | Routing (`router.py`) implements FP defense and FN recovery; the resolution vocabulary deliberately has no "override score". The corpus dedupes by `(task_id, run_ref)` fingerprint (F12); resolutions append automatically. |
| Loop wiring | `opti_loop.eligibility` + gate | **Auto-T1 now runs inside the loop** (F10): before a treatment run can be benchmark evidence it must have an admitted, checksum-matched verifier, and T1 runs over each task trace and routes disagreements to quarantine; a pending quarantine then fails the E5 comparison closed (strict) or excludes it (quorum). T2 remains owner-invoked. |

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
   ADR-0004 territory; the evidence API enforces visibility contracts and
   refuses any event OR artifact reference bearing `restricted`, even when
   co-tagged (F13) — holdout material is never loadable here.

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
