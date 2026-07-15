# Opti Browser Tool evaluation runner

This package provides a backend-neutral runner for the current **140-task provisional candidate suite**, its nested 20-task smoke subset, and the provisional 20-task regression seed. It deliberately does not select Playwright, Selenium, BrowserGym, native pointer input, CDP, or another browser architecture.

The suite is runnable at the orchestration layer now. Real browser evaluation still requires one audited bridge for each benchmark family.

All exact task records and upstream locators are included. See [`docs/TASK_DATA_GUIDE.md`](../docs/TASK_DATA_GUIDE.md) for what is present and which runtime assets remain external.

## Install

From the repository root:

```bash
python -m venv .venv
. .venv/bin/activate
make install
opti-eval validate
opti-eval list --suite smoke
```

This installs the evaluator, judge, and loop using their explicit local
dependency graph. For an evaluator-only environment, use
`python -m pip install -e ./eval_harness`. The evaluator itself has no runtime
dependency outside the Python standard library. `make install-check` performs
the uv-offline/no-index wheel and transitive-install proof described in the
root README, then runs deterministic installed tests without a live backend.
It is not an OS-level network sandbox.

## Verify runner plumbing

Run the 20-task smoke subset with the deterministic fixture adapter:

```bash
opti-eval run \
  --suite smoke \
  --adapter fixture \
  --fixture-pass-rate 0.55 \
  --output runs/smoke-fixture
```

Run all 140 candidates:

```bash
opti-eval run \
  --suite primary \
  --adapter fixture \
  --fixture-pass-rate 0.55 \
  --max-workers 8 \
  --output runs/all-140-fixture
```

Fixture scores are synthetic plumbing checks and are marked `benchmark_reportable=false`.

## External bridge contract

A bridge receives a normalized task JSON path and must write one result JSON file:

```bash
opti-eval run \
  --suite smoke \
  --adapter command \
  --command "python eval_harness/examples/fixture_bridge.py --task-json {task_json} --result-json {result_json}" \
  --output runs/smoke-command-fixture
```

Supported placeholders are `{task_json}`, `{result_json}`, `{task_id}`, `{source}`, and `{output_dir}`.
The runner also supplies its authoritative identity as `OPTI_RUN_ID`; bridges
copy that value into every trace event but must not write a `run_id` into the
bridge-result JSON. The runner adds it to persisted task results itself.

The included `fixture_bridge.py` marks every result synthetic and non-reportable. A command-adapter run using that example verifies the bridge contract only; the summary remains `benchmark_reportable=false`.

A real bridge must reset its source environment, resolve the upstream task, run the chosen browser harness, invoke the native or audited verifier, and write:

```json
{
  "task_id": "real-v1-networkin-1",
  "status": "passed",
  "reward": 1.0,
  "verifier": {
    "id": "real-v1-upstream-programmatic-state-v1",
    "checksum": "789abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456",
    "outcome": "passed"
  },
  "trace_path": "trace.jsonl",
  "artifacts": [
    {
      "kind": "trace",
      "uri": "trace.jsonl",
      "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
      "media_type": "application/x-ndjson",
      "visibility": ["judge", "orchestrator"]
    },
    {
      "kind": "final_screenshot",
      "uri": "artifacts/final.png",
      "sha256": "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
      "media_type": "image/png",
      "visibility": ["judge", "orchestrator"]
    }
  ],
  "metrics": {
    "tool_calls": 17,
    "browser_actions": 25
  }
}
```

Allowed statuses are `passed`, `failed`, `invalid`, `error`, and `skipped`.
Infrastructure, reset, account, and verifier failures must use `invalid` or
`error`, never `failed`. Artifact URIs are task-relative POSIX paths; the
eligibility boundary rejects traversal, symlinks, missing files, hash
mismatches, malformed visibility, undeclared event artifacts, and a trace that
does not match the runner-owned run/task/result. Replay and eligibility also
require one exact ordered task manifest across `run.json`, `results.jsonl`,
the task directories, every `task.json`, and every task-local `result.json`;
missing, duplicate, unexpected, or reordered tasks fail closed. Task IDs use
the portable `^[a-z0-9][a-z0-9_-]*$` form (95 characters maximum) before any
task path is constructed. The verifier values above are illustrative: a real
bridge must copy the exact admitted verifier ID and checksum into its result
and sole terminal trace event.

Command and registry bridge outputs are diagnostic and non-reportable by default. Bridge-authored metadata cannot promote them into benchmark evidence; a later trusted evidence path must validate and explicitly promote each result before a run can become benchmark-reportable or acceptance-decision-eligible.

## Source registry

Copy the disabled template and configure bridge commands:

```bash
cp evals/config.example.json evals/config.local.json
opti-eval doctor --config evals/config.local.json
opti-eval run \
  --suite primary \
  --adapter registry \
  --config evals/config.local.json \
  --output runs/all-140-real
```

The registry fails closed while a source is disabled or missing.

## Artifacts

Every run writes:

```text
runs/<run-name>/
├── run.json
├── results.jsonl
├── summary.json
└── tasks/
    └── <task-id>/
        ├── task.json
        ├── result.json
        ├── trace.jsonl           # required only for benchmark eligibility
        ├── bridge-result.json   # command/registry adapters
        ├── stdout.log
        └── stderr.log
```

A run containing `invalid`, `error`, or `skipped` results is not eligible for
benchmark comparison or experiment acceptance. Fixture and command rehearsals
remain useful without traces because they are explicitly non-reportable. An
otherwise reportable terminal result fails evidence integrity if its declared
trace bundle or T1 execution is missing or invalid. For such a result, the
scheduled source and pinned verifier ID/checksum must agree across runner task
metadata, admission/config, aggregate and local results, and the sole final
verifier-owned trace event. Trace events remain in append order with unique
IDs, consecutive sequences, nondecreasing RFC 3339/monotonic clocks and every
supplied browser epoch, required epochs on observation/action events, canonical JSON values,
and a visible final `browser_state` immediately before the verifier. T1 task
expectations are closed and type strict; malformed expectations invalidate the
evidence instead of silently coercing values.

Trace JSONL uses physical LF records; CRLF is accepted by removing only the CR
paired with each LF, and the final LF is optional. Blank records, extra trailing
LFs, lone CR, VT/FF/FS/NEL/Unicode line separators used as record delimiters,
partial records, duplicate keys, and non-finite numbers are rejected. Raw
NEL/U+2028/U+2029 characters inside a valid JSON string remain data. Semantic
nonempty strings use one explicit Python/ECMA edge-whitespace union (including
NEL and BOM), shared by runtime validation and all evidence schemas.

## Current evidence boundary

All 140 task definitions preserve their exact candidate provenance. Their benchmark-family reference results are within the accepted 35–70% band, but these are **not per-task success rates**. Task-level calibration, reset checks, known-good runs, and adversarial verifier tests remain pending.
