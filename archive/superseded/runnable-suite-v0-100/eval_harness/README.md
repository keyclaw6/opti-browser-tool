# Opti Browser Tool runnable evaluation suite

This package runs the provisional 100-task primary suite, its nested 20-task smoke subset, and the provisional 20-task regression seed. It deliberately does not choose a browser backend or agent architecture.

## Quick start

From the repository root:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ./eval_harness
opti-eval validate
opti-eval list --suite smoke
```

Verify the complete runner plumbing without launching browsers:

```bash
opti-eval run   --suite smoke   --adapter fixture   --fixture-pass-rate 0.55   --output runs/smoke-fixture
```

Exercise the external command contract:

```bash
opti-eval run   --suite smoke   --adapter command   --command "python eval_harness/examples/fixture_bridge.py --task-json {task_json} --result-json {result_json}"   --output runs/smoke-command-fixture
```

Run real benchmark bridges after copying and editing the registry:

```bash
cp evals/config.example.json evals/config.local.json
opti-eval doctor --config evals/config.local.json
opti-eval run   --suite smoke   --adapter registry   --config evals/config.local.json   --output runs/smoke-real
```

The registry is intentionally disabled by default. A real run fails closed until every source has a working bridge.

## Output contract

Every run writes:

- `run.json`: immutable run configuration plus final summary;
- `results.jsonl`: one standardized result per task;
- `summary.json`: validity and success metrics;
- `tasks/<task-id>/task.json`: exact normalized task passed to the bridge;
- `tasks/<task-id>/result.json`: verifier result;
- `stdout.log` and `stderr.log`: bridge process logs.

A run with an `invalid`, `error`, or `skipped` task has `run_valid=false` and cannot be used to accept or reject a harness change.

## Provisional status

All 100 tasks are source-audited candidates, not yet fully admitted tasks. The benchmark-family reference results lie in the owner-approved 35–70% band, but task-level calibration, reset checks, oracle runs, and verifier adversarial tests remain pending.
