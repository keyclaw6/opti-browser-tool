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

## Accepted direction

### 1. Canonical stream: append-only JSONL trace per run

One `trace.jsonl` per task run, written inside the existing opti-eval run layout
(`runs/<run>/tasks/<task-id>/trace.jsonl`). The persisted task result declares
`trace_path` and includes a matching hashed artifact reference. Events conform
to [`schemas/trace-event.schema.json`](../../schemas/trace-event.schema.json)
with explicit runner-owned `run_id`, `task_id`, visibility tags,
`browser_state_epoch`, closed actor/event vocabularies, structured artifact
references, and a redaction slot. The shared validator rejects non-standard
JSON constants, mixed identities, duplicate IDs, sequence gaps, backward wall
or monotonic time, and backward epochs on every event that supplies an epoch.
Observation/action events require a non-negative epoch. A benchmark bundle closes with exactly one final
verifier-owned result, immediately preceded by visible canonical
`browser_state` final-state evidence.

Physical records are separated only by LF. CRLF is accepted by stripping the
CR paired with each LF, and a complete final record need not end in LF. Blank
records, extra trailing delimiters, partial JSON, lone CR, and VT/FF/FS/NEL or
Unicode line/paragraph separators used as record delimiters fail closed; those
Unicode characters remain valid when they occur inside a JSON string. All
in-memory values must belong to standard finite JSON. Semantic nonempty fields
reject edge characters from one explicit shared class: U+0009–000D,
U+001C–0020, U+0085, U+00A0, U+1680, U+2000–200A, U+2028–2029, U+202F, U+205F,
U+3000, and U+FEFF.

JSONL is chosen for streaming append (a crashed run keeps every event up to the crash), schema evolution via `schema_version`, zero dependencies, and direct greppability. Columnar/queryable stores (DuckDB, Parquet) are **derived indexes** — rebuildable caches, never authoritative.

### 2. Large evidence: content-addressed artifact store

Screenshots, DOM/accessibility snapshots, network bodies, videos, and
backend-native traces (Playwright trace zips, HAR, CDP dumps) are **artifacts**,
not events: stored once per run tree under
`artifacts/<sha256[:2]>/<sha256>` and referenced from results/events via entries
carrying `kind`, task-relative `uri`, `sha256`, `media_type`, and an
artifact-level `visibility` class. The current shared validator enforces
task-root containment, regular-file/no-symlink resolution, exact hashes, and
result/event agreement without introducing a CAS service; the first real
bridge can adopt the specified content-addressed layout directly.

### 3. Visibility enforcement at the read boundary

Visibility is enforced where evidence is *consumed*: the evidence API (`judge_harness/src/opti_judge/evidence.py` is the reference implementation) filters events by contract, hard-denies any `restricted` material, and returns artifact references only when their visibility intersects the caller's contract. An export/redaction pass (driven by the schema's `redaction` field) is required before any trace leaves its trust domain — mandatory for later live-site work under ADR-0006.

### 4. Retention and the holdout boundary

- Traces and artifacts for accepted iterations, quarantine entries, and probe-kit archives are retained indefinitely (they are calibration and attribution evidence).
- Bulk artifacts of rejected iterations may be pruned after their ledger row and attribution records are written (open parameter).
- **Holdout runs never write into campaign or public run trees.** Their traces live only in the private holdout store; `restricted` is a between-store boundary, not just a tag.

## Why this direction was accepted

The requirements exist on the consumer side, written and tested: the Analyst
contract demands event-addressable claims, the judge layer demands visibility
contracts and epoch-scoped stale-reference evidence, gate E1's dynamic audit
demands declared activation events, and divergence analysis demands ordered
epochs. This schema is canonical. Artifact sizing remains an empirical
bring-up parameter, and first-real-bridge conformance remains a pre-activation
check rather than an unresolved ADR decision.

## Interaction with open decisions

- **ADR-0003**: whichever backend is chosen, its session adapter must emit this event stream; backend-native traces attach as artifacts. This ADR does not narrow the backend choice.
- **ADR-0006**: redaction-on-export and restricted storage domains are prerequisites for live-site evidence.
- **ADR-0015/0016**: consume this contract unchanged.

## Open parameters

Retention window for rejected-iteration artifacts; video capture default; compression; derived-index format; per-family artifact size budgets (measure during bridge bring-up).

## Pre-activation conformance check

Before loop activation, the first real source bridge must emit a conforming
`trace.jsonl` plus artifacts for a smoke task, and the probe kit, shared bundle
validator, and T1 cross-checks must run end-to-end over it. ADR acceptance does
not waive this empirical checkpoint or the project owner's explicit start.
