# Task data guide

## Direct answer

The repository contains the **actual textual task goals, exact candidate IDs, upstream task locators, source versions, selection rationale, and expected verifier metadata for all 140 candidates**. They are not merely summarized in a prose report.

However, the repository is **not a self-contained copy of the five upstream benchmarks**. It does not vendor the browser websites, ServiceNow instances, WACZ archives, VisualWebArena input images, login state, browser profiles, credentials, or source verifier implementations. Those must be installed or fetched through pinned upstream benchmark packages before a real browser run.

This distinction is important:

- **Task inventory present:** yes.
- **Task goals present:** yes, subject to the source-specific caveats below.
- **Suite manifests present:** yes.
- **Orchestration runner present:** yes.
- **Complete standalone browser environments and native verifiers present:** no.

## Authoritative task files

### 1. Raw candidate inventory

`research/benchmarks/task-candidates/batch-1-candidates.jsonl`

This is the preserved source-of-truth inventory produced during candidate selection. It contains one JSON object per candidate, including:

- `candidate_id`;
- benchmark and pinned source version;
- native task ID and seed where applicable;
- site;
- `task_intent`;
- interaction class and expected state mutation;
- source difficulty label;
- expected evaluator type and strength;
- benchmark-family reference result and evidence scope;
- selection rationale and audit flags; and
- source manifest locator and checksum.

The equivalent review spreadsheet is:

`research/benchmarks/task-candidates/batch-1-candidates.csv`

The human-readable list of all goals is:

`research/benchmarks/task-candidates/batch-1-index.md`

### 2. Normalized runnable catalog

`evals/catalog/tasks.jsonl`

This is the authoritative input to `opti-eval`. It contains all 140 normalized records and embeds the complete raw candidate record under:

```text
provenance.raw_candidate_record
```

Important normalized fields include:

- `id` — stable Opti Browser Tool task ID;
- `goal` — copied from the raw `task_intent`;
- `upstream` — benchmark, version, native task ID, seed, source manifest, and checksum;
- `suite_membership`;
- `difficulty_evidence`;
- `verification` status and expected verifier class;
- `runtime.bridge_key`; and
- full provenance.

Other views are:

- `evals/catalog/by-id/<source>/<task-id>.json` — one pretty-printed file per task for direct review;
- `evals/catalog/tasks.csv` — flattened review table;
- `evals/catalog/task-index.json` — records keyed by task ID;
- `evals/catalog/by-source/*.jsonl` — source-specific partitions.

`tasks.jsonl` remains canonical. The by-ID files are generated review copies and automated validation requires every one to match the canonical record exactly.

### 3. Suite manifests

The files under `evals/suites/` contain task IDs and policies, not duplicate task bodies:

- `candidate-pool.json` — all 140 candidates;
- `primary.json` — currently the same 140 provisional candidates under ADR-0014;
- `smoke.json` — nested 20-task subset;
- `regression.json` — provisional 20-task seed, currently equal to smoke.

To resolve a suite ID into its full task record, load `evals/catalog/task-index.json` or use `opti-eval list`.

## Source-specific completeness

| Source | Included in this repository | Still required from upstream for a real run |
|---|---|---|
| REAL v1 | Exact selected IDs, textual goals, site, version, source checksum, evaluator category, and provenance | Website replicas, original task JSON/evaluator expressions, app state, and a source bridge |
| WebArena-Verified | Exact IDs, textual intents, site, version/checksum, evaluator category, and provenance | Environment containers/data, full task/evaluator configuration, authentication/reset setup, network-trace capture, and a source bridge |
| WorkArena++ L2 | Exact task class, seed, benchmark label, source version/checksum, and provenance | Gated ServiceNow instance, runtime-instantiated instruction and initial state, oracle/verifier implementation, and a source bridge |
| VisualWebArena | Exact IDs, textual intents, site, difficulty labels, version/checksum, and provenance | Referenced input images, website environments and data, full config/evaluator records, and a source bridge |
| WARC-Bench | Exact IDs, human-readable goals, site, version/checksum, evaluator category, and provenance | WACZ archives, full environment records, JavaScript/URL verifier scripts, replay runtime, and a source bridge |

### WorkArena and visual-task caveats

For WorkArena++, the user-facing instruction is instantiated by the upstream task class and seed. The local inventory preserves the exact class/seed identity and a human-readable task-family label, but not the generated ServiceNow state or fully instantiated instruction.

For VisualWebArena tasks that say “this image” or refer to an open tab, the text goal is present but the associated image or visual context is not vendored. The upstream task ID and pinned source version are required to recover it.

## Counts and distribution

- REAL v1: 30
- WebArena-Verified: 30
- WorkArena++ Level 2: 30
- VisualWebArena: 30
- WARC-Bench: 20
- Total: 140

The raw and normalized inventories have identical task ID sets. Automated validation also checks that every normalized `goal` matches the raw `task_intent` and that state-change flags match.

## Inspecting the tasks

Human-readable:

```bash
less research/benchmarks/task-candidates/batch-1-index.md
```

Machine-readable first record:

```bash
python - <<'PY'
import json
from pathlib import Path
line = Path('evals/catalog/tasks.jsonl').read_text().splitlines()[0]
print(json.dumps(json.loads(line), indent=2))
PY
```

List a suite through the runner:

```bash
PYTHONPATH=eval_harness/src python -m opti_eval list --suite smoke --repo-root .
PYTHONPATH=eval_harness/src python -m opti_eval list --suite primary --repo-root .
```

Verify counts and provenance:

```bash
python scripts/verify_repository_completeness.py --repo-root .
python scripts/verify_documentation.py --repo-root .
```

## Data safety note

Some simulated tasks contain example names, email addresses, phone numbers, and payment-card values supplied by upstream benchmarks. They are benchmark fixtures, not project credentials. No real account secrets or browser profiles are included in the repository.
