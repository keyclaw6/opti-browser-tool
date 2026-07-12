#!/usr/bin/env python3
"""Validate active evaluation documents against the repository JSON Schemas.

This is a preservation and contract check, not a browser-agent evaluation.
Install the optional dependency with `python -m pip install jsonschema`.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[object]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()

    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        raise SystemExit(
            "jsonschema is required for this optional check; "
            "install it with `python -m pip install jsonschema`."
        )

    task_schema_path = root / "evals/schemas/normalized-task.schema.json"
    suite_schema_path = root / "evals/schemas/suite.schema.json"
    summary_schema_path = root / "evals/schemas/run-summary.schema.json"
    task_validator = Draft202012Validator(load_json(task_schema_path))
    suite_validator = Draft202012Validator(load_json(suite_schema_path))
    summary_validator = Draft202012Validator(load_json(summary_schema_path))

    checks: list[dict] = []
    errors: list[str] = []

    def record(label: str, schema: str, validator: Draft202012Validator, value: object) -> None:
        item_errors = sorted(validator.iter_errors(value), key=lambda error: list(error.path))
        checks.append({
            "label": label,
            "schema": schema,
            "error_count": len(item_errors),
        })
        for error in item_errors:
            location = "/".join(str(part) for part in error.absolute_path) or "<root>"
            errors.append(f"{label} at {location}: {error.message}")

    for index, task in enumerate(load_jsonl(root / "evals/catalog/tasks.jsonl"), start=1):
        record(
            f"tasks.jsonl:{index}",
            task_schema_path.relative_to(root).as_posix(),
            task_validator,
            task,
        )

    for name in ("candidate-pool", "primary", "smoke", "regression"):
        record(
            f"suite:{name}",
            suite_schema_path.relative_to(root).as_posix(),
            suite_validator,
            load_json(root / f"evals/suites/{name}.json"),
        )

    for label, relative in (
        ("fixture-140-summary", "validation/fixture-140-summary.json"),
        ("command-bridge-summary", "validation/command-bridge-summary.json"),
    ):
        record(
            label,
            summary_schema_path.relative_to(root).as_posix(),
            summary_validator,
            load_json(root / relative),
        )

    report = {
        "ok": not errors,
        "validated_document_count": len(checks),
        "checks": checks,
        "errors": errors,
    }
    rendered = json.dumps(report, indent=2) + "\n"
    if args.output:
        output = Path(args.output)
        if not output.is_absolute():
            output = root / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
