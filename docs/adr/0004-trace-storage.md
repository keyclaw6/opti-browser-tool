# ADR-0004: Trace event log and artifact storage

- Status: Accepted
- Date opened: 2026-07-11
- Date proposed: 2026-07-13
- Date accepted: 2026-07-13
- Approval state: Accepted — explicit project-owner approval (2026-07-13). The decision gate's empirical check (first real bridge emits a conforming trace, probe kit + T1 run over it) carries forward as a pre-activation requirement.
- Supersedes: —
- Superseded by: —

## Question

What trace and artifact representation will let the project reconstruct runs, analyze failures, protect restricted evidence, and compare different browser harnesses without excessive complexity?

## Proposed direction

### 1. Canonical stream: append-only JSONL trace per run

One `trace.jsonl` per task run, written inside the existing opti-eval run layout (`runs/<run>/tasks/<task-id>/trace.jsonl`, referenced from the bridge result's `artifacts` map). Events conform to [`schemas/trace-event.schema.json`](../../schemas/trace-event.schema.json) — already drafted with the load-bearing fields this architecture depends on: `visibility` tags, `browser_state_epoch`, `actor`/`event_type` vocabularies, `artifact_refs`, and a `redaction` slot.

JSONL is chosen for streaming append (a crashed run keeps every event up to the crash), schema evolution via `schema_version`, zero dependencies, and direct greppability. Columnar/queryable stores (DuckDB, Parquet) are **derived indexes** — rebuildable caches, never authoritative.

### 2. Large evidence: content-addressed artifact store

Screenshots, DOM/accessibility snapshots, network bodies, videos, and backend-native traces (Playwright trace zips, HAR, CDP dumps) are **artifacts**, not events: stored once per run tree under `artifacts/<sha256[:2]>/<sha256>` and referenced from events via `artifact_refs` entries carrying `kind`, `uri`, `sha256`, `media_type`, and an artifact-level `visibility` class. Content addressing gives deduplication, immutability, and integrity checking for free. Backend-native trace formats ride along as artifacts — the canonical stream stays backend-neutral, so ADR-0003 remains unconstrained.

### 3. Visibility enforcement at the read boundary

Visibility is enforced where evidence is *consumed*: the evidence API (`judge_harness/src/opti_judge/evidence.py` is the reference implementation) filters events by contract and structurally refuses purely `restricted` material; the same rule applies to artifact fetches. An export/redaction pass (driven by the schema's `redaction` field) is required before any trace leaves its trust domain — mandatory for later live-site work under ADR-0006.

### 4. Retention and the holdout boundary

- Traces and artifacts for accepted iterations, quarantine entries, and probe-kit archives are retained indefinitely (they are calibration and attribution evidence).
- Bulk artifacts of rejected iterations may be pruned after their ledger row and attribution records are written (open parameter).
- **Holdout runs never write into campaign or public run trees.** Their traces live only in the private holdout store; `restricted` is a between-store boundary, not just a tag.

## Why this is proposed

The requirements now exist on the consumer side, written and tested: the Analyst contract demands event-addressable claims (`docs/architecture/ANALYST.md`), the judge layer demands visibility contracts and epoch-scoped stale-reference evidence (ADR-0016; `opti_judge` consumes exactly this shape today), gate E1's dynamic audit demands declared activation events, and divergence analysis demands ordered epochs. The schema those consumers were built against is the one this ADR makes canonical. What remains genuinely open is sizing (artifact volumes per benchmark family), which bridge bring-up will measure — hence Proposed now, accepted only against real bridge output.

## Interaction with open decisions

- **ADR-0003**: whichever backend is chosen, its session adapter must emit this event stream; backend-native traces attach as artifacts. This ADR does not narrow the backend choice.
- **ADR-0006**: redaction-on-export and restricted storage domains are prerequisites for live-site evidence.
- **ADR-0015/0016**: consume this contract unchanged.

## Open parameters

Retention window for rejected-iteration artifacts; video capture default; compression; derived-index format; per-family artifact size budgets (measure during bridge bring-up).

## Decision gate

Accept only after the first real source bridge emits a conforming `trace.jsonl` (+ artifacts) for a smoke task, and the probe kit plus T1 cross-checks run end-to-end over it. Explicit project-owner approval is required.
