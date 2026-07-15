#!/usr/bin/env python3
"""Validate active documents and the experiment contract corpus against Schemas.

This is a preservation and contract check, not a browser-agent evaluation.
Install the optional dependency with `python -m pip install jsonschema`.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import math
import re
import sys
from pathlib import Path


def _reject_json_constant(token: str) -> None:
    raise ValueError(f"non-standard JSON numeric constant {token}")


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON object key {key!r}")
        value[key] = item
    return value


def _validate_finite_json(value: object, *, field_name: str = "JSON document") -> None:
    if value is None or type(value) in {bool, str, int}:
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError(f"{field_name} contains a non-finite JSON number")
        return
    if type(value) is list:
        for index, item in enumerate(value):
            _validate_finite_json(item, field_name=f"{field_name}[{index}]")
        return
    if type(value) is dict:
        for key, item in value.items():
            _validate_finite_json(item, field_name=f"{field_name}.{key}")
        return
    raise ValueError(f"{field_name} contains a non-standard JSON value")


def strict_json_loads(text: str) -> object:
    value = json.loads(
        text,
        parse_constant=_reject_json_constant,
        object_pairs_hook=_reject_duplicate_keys,
    )
    _validate_finite_json(value)
    return value


def load_json(path: Path) -> object:
    return strict_json_loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[object]:
    from opti_eval.models import split_lf_jsonl_records

    with path.open("r", encoding="utf-8", newline="") as handle:
        records = split_lf_jsonl_records(
            handle.read(), field_name=f"schema input JSONL {path}"
        )
    return [
        strict_json_loads(record)
        for record in records
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    sys.path.insert(0, str(root / "eval_harness/src"))

    from opti_eval.models import validate_standard_json

    try:
        from jsonschema import Draft202012Validator, FormatChecker
    except ImportError:
        raise SystemExit(
            "jsonschema is required for this optional check; "
            "install it with `python -m pip install jsonschema`."
        )

    task_schema_path = root / "evals/schemas/normalized-task.schema.json"
    suite_schema_path = root / "evals/schemas/suite.schema.json"
    summary_schema_path = root / "evals/schemas/run-summary.schema.json"
    result_schema_path = root / "schemas/result.schema.json"
    trace_schema_path = root / "schemas/trace-event.schema.json"
    bridge_schema_path = root / "evals/schemas/bridge-result.schema.json"
    experiment_schema_path = root / "schemas/experiment.schema.json"
    format_checker = FormatChecker()

    @format_checker.checks("date-time", raises=(TypeError, ValueError))
    def strict_rfc3339(value: object) -> bool:
        if not isinstance(value, str):
            return True  # the schema's type keyword reports this separately
        if re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})",
            value,
        ) is None:
            return False
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.tzinfo is not None
    task_schema = load_json(task_schema_path)
    suite_schema = load_json(suite_schema_path)
    summary_schema = load_json(summary_schema_path)
    result_schema = load_json(result_schema_path)
    trace_schema = load_json(trace_schema_path)
    bridge_schema = load_json(bridge_schema_path)
    assertion_schema = task_schema["properties"]["judge_expectations"][
        "properties"
    ]["state_assertions"]["items"]
    for schema in (
        task_schema,
        suite_schema,
        summary_schema,
        result_schema,
        trace_schema,
        bridge_schema,
    ):
        Draft202012Validator.check_schema(schema)
    task_validator = Draft202012Validator(task_schema, format_checker=format_checker)
    suite_validator = Draft202012Validator(suite_schema, format_checker=format_checker)
    assertion_validator = Draft202012Validator(
        assertion_schema, format_checker=format_checker
    )
    summary_validator = Draft202012Validator(
        summary_schema, format_checker=format_checker
    )
    result_validator = Draft202012Validator(
        result_schema, format_checker=format_checker
    )
    trace_validator = Draft202012Validator(trace_schema, format_checker=format_checker)
    trace_sequence_validator = Draft202012Validator(
        {"type": "array", "items": trace_schema},
        format_checker=format_checker,
    )
    bridge_validator = Draft202012Validator(
        bridge_schema, format_checker=format_checker
    )
    experiment_schema = load_json(experiment_schema_path)
    experiment_validator = Draft202012Validator(
        experiment_schema, format_checker=format_checker
    )

    def branch_schema(name: str) -> dict:
        return {
            "$schema": experiment_schema["$schema"],
            "$defs": experiment_schema["$defs"],
            "$ref": f"#/$defs/{name}",
        }

    branch_validators = {
        "experiment": Draft202012Validator(
            branch_schema("experiment"), format_checker=format_checker
        ),
        "rejected_submission": Draft202012Validator(
            branch_schema("rejected_submission"), format_checker=format_checker
        ),
    }

    checks: list[dict] = []
    errors: list[str] = []

    def record(
        label: str,
        schema: str,
        validator: Draft202012Validator,
        value: object,
        *,
        expected_valid: bool = True,
        expected_json_domain_valid: bool = True,
        canonical_branch: str | None = None,
    ) -> bool:
        domain_error: str | None = None
        try:
            validate_standard_json(value, field_name=label)
        except ValueError as exc:
            domain_error = str(exc)
        json_domain_valid = domain_error is None
        item_errors = (
            []
            if not json_domain_valid
            else sorted(
                validator.iter_errors(value), key=lambda error: list(error.path)
            )
        )
        actual_valid = json_domain_valid and not item_errors
        check = {
            "label": label,
            "schema": schema,
            "status": "checked",
            "expected_valid": expected_valid,
            "actual_valid": actual_valid,
            "expected_json_domain_valid": expected_json_domain_valid,
            "actual_json_domain_valid": json_domain_valid,
            "error_count": len(item_errors) + int(domain_error is not None),
        }
        checks.append(check)
        local_errors: list[str] = []
        if json_domain_valid != expected_json_domain_valid:
            local_errors.append(
                f"{label}: expected standard JSON domain valid="
                f"{expected_json_domain_valid}, got {json_domain_valid}"
            )
        if actual_valid != expected_valid:
            check["validation_errors"] = []
            local_errors.append(
                f"{label}: expected schema valid={expected_valid}, got {actual_valid}"
            )
            if domain_error is not None:
                check["validation_errors"].append({
                    "path": "<root>",
                    "message": domain_error,
                    "validator": "standard-json-domain",
                })
            for error in item_errors:
                location = "/".join(str(part) for part in error.absolute_path) or "<root>"
                check["validation_errors"].append({
                    "path": location,
                    "message": error.message,
                    "validator": error.validator,
                })
                local_errors.append(f"{label} at {location}: {error.message}")

        if canonical_branch is not None:
            branch_results = {
                branch: json_domain_valid
                and not list(branch_validator.iter_errors(value))
                for branch, branch_validator in branch_validators.items()
            }
            matching_branches = [
                branch for branch, valid in branch_results.items() if valid
            ]
            canonical_root_valid = json_domain_valid and not list(
                experiment_validator.iter_errors(value)
            )
            expected_matches = [canonical_branch] if expected_valid else []
            check.update({
                "canonical_branch": canonical_branch,
                "canonical_branch_matches": matching_branches,
                "canonical_root_valid": canonical_root_valid,
            })
            if matching_branches != expected_matches:
                local_errors.append(
                    f"{label}: expected canonical branch matches {expected_matches}, "
                    f"got {matching_branches}"
                )
            if canonical_root_valid != expected_valid:
                local_errors.append(
                    f"{label}: expected canonical root valid={expected_valid}, "
                    f"got {canonical_root_valid}"
                )
            if canonical_root_valid != (len(matching_branches) == 1):
                local_errors.append(
                    f"{label}: canonical oneOf result disagrees with branch match count"
                )
            if local_errors and "validation_errors" not in check:
                check["validation_errors"] = [{
                    "path": "<root>",
                    "message": local_errors[0],
                    "validator": "canonical-branch",
                }]

        errors.extend(local_errors)
        return not local_errors

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

    from evidence_contract_corpus import build_evidence_contract_corpus

    evidence_validators = {
        "result": (
            result_schema_path.relative_to(root).as_posix(),
            result_validator,
        ),
        "bridge": (
            bridge_schema_path.relative_to(root).as_posix(),
            bridge_validator,
        ),
        "task": (
            task_schema_path.relative_to(root).as_posix(),
            task_validator,
        ),
        "suite": (
            suite_schema_path.relative_to(root).as_posix(),
            suite_validator,
        ),
        "assertion": (
            task_schema_path.relative_to(root).as_posix()
            + "#/properties/judge_expectations/properties/state_assertions/items",
            assertion_validator,
        ),
        "event": (
            trace_schema_path.relative_to(root).as_posix(),
            trace_validator,
        ),
        "raw_event": (
            trace_schema_path.relative_to(root).as_posix() + "#raw-json",
            trace_validator,
        ),
        "raw_trace": (
            trace_schema_path.relative_to(root).as_posix() + "#raw-jsonl",
            trace_validator,
        ),
        "trace": (
            trace_schema_path.relative_to(root).as_posix() + "#sequence",
            trace_sequence_validator,
        ),
    }
    evidence_corpus = build_evidence_contract_corpus()
    for case in evidence_corpus:
        schema_name, validator = evidence_validators[case["target"]]
        record(
            f"evidence-corpus:{case['label']}",
            schema_name,
            validator,
            case["value"],
            expected_valid=case["schema_valid"],
            expected_json_domain_valid=case["json_domain_valid"],
        )

    experiment = load_json(root / "examples/experiment.example.json")
    optimizer_example_valid = record(
        "experiment:optimizer-input",
        experiment_schema_path.relative_to(root).as_posix(),
        branch_validators["experiment"],
        experiment,
        canonical_branch="experiment",
    )

    corpus_report: dict[str, object]
    if optimizer_example_valid:
        # Use the actual conductor producers for representative enriched and
        # rejected shapes. Derived cases are never built from an invalid seed.
        sys.path[:0] = [
            str(root / "loop_harness/src"),
            str(root / "eval_harness/src"),
            str(root / "scripts"),
        ]
        from opti_loop.attribution import Attribution
        from opti_loop.manifest import rejected_submission_record
        from opti_loop.verdict import Verdict

        enriched_experiment = dict(experiment)
        enriched_experiment["status"] = Verdict("accepted", "benchmark").label
        enriched_experiment["attribution"] = Attribution(
            verdict="keep",
            predicted_count=2,
            verified_fixes=["dynamic-menu"],
            missed_predictions=["infinite-feed-action"],
            unpredicted_fixes=[],
            predicted_risks=["static-form"],
            materialized_regressions=[],
            prediction_precision=0.5,
            flip_recall=1.0,
        ).to_dict()
        record(
            "experiment:conductor-enriched",
            experiment_schema_path.relative_to(root).as_posix(),
            branch_validators["experiment"],
            enriched_experiment,
            canonical_branch="experiment",
        )

        malformed_prediction = copy.deepcopy(experiment)
        malformed_prediction["predicted_improvements"] = ["not-an-object"]
        context_invalid_path = copy.deepcopy(experiment)
        context_invalid_path["treatment"]["change_scope"] = [
            "harness/components/observation/../policy/quality.txt"
        ]
        rejected_inputs = (
            ("array", []),
            ("null", None),
            ("string", "manifest"),
            ("number", 7),
            ("boolean", True),
            ("malformed-prediction", malformed_prediction),
            ("context-invalid-path", context_invalid_path),
        )
        for label, original_submission in rejected_inputs:
            rejected = rejected_submission_record(
                original_submission=original_submission,
                validation_errors=[f"rejected {label} optimizer submission"],
                verdict=Verdict("rejected", "simulated").to_dict(),
            )
            record(
                f"experiment:rejected-submission:{label}",
                experiment_schema_path.relative_to(root).as_posix(),
                branch_validators["rejected_submission"],
                rejected,
                canonical_branch="rejected_submission",
            )
        benchmark_rejected = rejected_submission_record(
            original_submission=[],
            validation_errors=["rejected array optimizer submission"],
            verdict=Verdict("rejected", "benchmark").to_dict(),
        )
        record(
            "experiment:rejected-submission:benchmark",
            experiment_schema_path.relative_to(root).as_posix(),
            branch_validators["rejected_submission"],
            benchmark_rejected,
            canonical_branch="rejected_submission",
        )

        from experiment_contract_corpus import build_contract_corpus

        corpus = build_contract_corpus(
            experiment,
            experiment_schema,
            enriched_experiment["attribution"],
        )
        for case in corpus:
            branch = case["branch"]
            record(
                f"experiment-corpus:{case['label']}",
                experiment_schema_path.relative_to(root).as_posix(),
                branch_validators[branch],
                case["value"],
                expected_valid=case["schema_valid"],
                canonical_branch=branch,
            )
        corpus_report = {"status": "completed", "case_count": len(corpus)}
    else:
        reason = "optimizer example is schema-invalid; derived contract corpus was not generated"
        checks.append({
            "label": "experiment:conductor-enriched",
            "schema": experiment_schema_path.relative_to(root).as_posix(),
            "status": "skipped",
            "reason": "optimizer example is schema-invalid; enriched record was not generated",
        })
        checks.append({
            "label": "experiment-corpus:generation",
            "schema": experiment_schema_path.relative_to(root).as_posix(),
            "status": "skipped",
            "reason": reason,
        })
        corpus_report = {"status": "skipped", "case_count": 0, "reason": reason}

    report = {
        "ok": not errors,
        "validated_document_count": len(checks),
        "experiment_corpus": corpus_report,
        "evidence_corpus": {
            "status": "completed",
            "case_count": len(evidence_corpus),
        },
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
