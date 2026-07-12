# Opti Browser Tool evaluation runner

This package provides a backend-neutral runner for the current **140-task provisional candidate suite**, its nested 20-task smoke subset, and the provisional 20-task regression seed. It deliberately does not select Playwright, Selenium, BrowserGym, native pointer input, CDP, or another browser architecture.

The suite is runnable at the orchestration layer now. Real browser evaluation still requires one audited bridge for each benchmark family.

All exact task records and upstream locators are included. See [`docs/TASK_DATA_GUIDE.md`](../docs/TASK_DATA_GUIDE.md) for what is present and which runtime assets remain external.

## Install

From the repository root:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ./eval_harness
opti-eval validate
opti-eval list --suite smoke
```

The package has no runtime dependency outside the Python standard library.

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

The included `fixture_bridge.py` marks every result synthetic and non-reportable. A command-adapter run using that example verifies the bridge contract only; the summary remains `benchmark_reportable=false`.

A real bridge must reset its source environment, resolve the upstream task, run the chosen browser harness, invoke the native or audited verifier, and write:

```json
{
  "task_id": "real-v1-networkin-1",
  "status": "passed",
  "reward": 1.0,
  "verifier": {
    "kind": "upstream_programmatic_state",
    "valid": true
  },
  "artifacts": {
    "trace": "trace.zip",
    "final_screenshot": "final.png"
  },
  "metrics": {
    "tool_calls": 17,
    "browser_actions": 25
  }
}
```

Allowed statuses are `passed`, `failed`, `invalid`, `error`, and `skipped`. Infrastructure, reset, account, and verifier failures must use `invalid` or `error`, never `failed`.

A bridge may set `metadata.benchmark_reportable=false` for synthetic or diagnostic results. The run summary honors that marker even when the generic command adapter itself is capable of reportable execution.

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
        ├── bridge-result.json   # command/registry adapters
        ├── stdout.log
        └── stderr.log
```

A run containing `invalid`, `error`, or `skipped` results is not eligible for benchmark comparison or experiment acceptance.

## Current evidence boundary

All 140 task definitions preserve their exact candidate provenance. Their benchmark-family reference results are within the accepted 35–70% band, but these are **not per-task success rates**. Task-level calibration, reset checks, known-good runs, and adversarial verifier tests remain pending.
