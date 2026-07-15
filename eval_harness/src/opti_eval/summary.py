from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models import (
    canonical_json,
    validate_nonempty_string,
    validate_persisted_result,
    validate_task_id,
)
from .util import read_json, read_jsonl

TERMINAL_VALID_STATUSES = {"passed", "failed"}
INVALIDATING_STATUSES = {"invalid", "error", "skipped"}
KNOWN_STATUSES = TERMINAL_VALID_STATUSES | INVALIDATING_STATUSES


def summarize_results(
    results: list[dict[str, Any]],
    *,
    adapter_reportable: bool,
) -> dict[str, Any]:
    counts = Counter(str(result.get("status")) for result in results)
    total = len(results)
    passed = counts["passed"]
    failed = counts["failed"]
    valid_count = passed + failed
    invalid_count = sum(counts[status] for status in INVALIDATING_STATUSES)
    run_valid = invalid_count == 0 and total > 0
    non_reportable_result_count = sum(
        1
        for result in results
        if not (
            isinstance(result.get("metadata"), dict)
            and result["metadata"].get("benchmark_reportable") is True
        )
    )
    results_reportable = non_reportable_result_count == 0
    benchmark_reportable = run_valid and adapter_reportable and results_reportable

    source_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for result in results:
        source_counts[str(result.get("source", "unknown"))][str(result.get("status"))] += 1

    by_source: dict[str, Any] = {}
    for source, source_counter in sorted(source_counts.items()):
        source_total = sum(source_counter.values())
        source_valid = source_counter["passed"] + source_counter["failed"]
        by_source[source] = {
            "total": source_total,
            "status_counts": dict(sorted(source_counter.items())),
            "strict_success_rate": source_counter["passed"] / source_total if source_total else None,
            "valid_outcome_success_rate": (
                source_counter["passed"] / source_valid if source_valid else None
            ),
        }

    return {
        "schema_version": "0.1.0",
        "task_count": total,
        "status_counts": dict(sorted(counts.items())),
        "strict_success_rate": passed / total if total else None,
        "valid_outcome_success_rate": passed / valid_count if valid_count else None,
        "valid_outcome_count": valid_count,
        "invalidating_outcome_count": invalid_count,
        "non_reportable_result_count": non_reportable_result_count,
        "run_valid": run_valid,
        "benchmark_reportable": benchmark_reportable,
        "acceptance_decision_eligible": benchmark_reportable,
        "by_source": by_source,
        "interpretation": (
            "Fixture/plumbing result; never report as benchmark performance."
            if not adapter_reportable
            else (
                "One or more results lack an explicit trusted reportability marker."
                if not results_reportable
                else (
                    "Eligible for benchmark comparison."
                    if benchmark_reportable
                    else "Not eligible for benchmark comparison because one or more tasks were invalid, errored, or skipped."
                )
            )
        ),
    }


def _invalid_replay_summary(
    persisted: dict[str, Any],
    *,
    errors: list[str],
    task_count: int,
) -> dict[str, Any]:
    summary = summarize_results([], adapter_reportable=False)
    summary.update(
        {
            "task_count": task_count,
            "invalidating_outcome_count": max(1, len(errors)),
            "non_reportable_result_count": task_count,
            "run_valid": False,
            "benchmark_reportable": False,
            "acceptance_decision_eligible": False,
            "interpretation": "Persisted run artifacts are invalid.",
            "replay_errors": errors,
        }
    )
    for key in ("run_id", "suite_id"):
        if key in persisted:
            summary[key] = persisted[key]
    return summary


@dataclass(slots=True)
class RunDirectoryValidation:
    run_record: dict[str, Any] = field(default_factory=dict)
    summary_record: dict[str, Any] = field(default_factory=dict)
    task_ids: list[str] = field(default_factory=list)
    task_sources: dict[str, str] = field(default_factory=dict)
    results: list[dict[str, Any]] = field(default_factory=list)
    results_by_task: dict[str, dict[str, Any]] = field(default_factory=dict)
    tasks_by_id: dict[str, dict[str, Any]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _read_object(path: Path, *, label: str, errors: list[str]) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        errors.append(f"{label} must be a real regular file")
        return {}
    try:
        value = read_json(path)
    except (OSError, ValueError) as exc:
        errors.append(f"{label} is unreadable: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{label} must contain an object")
        return {}
    return value


def validate_run_directory(run_dir: Path) -> RunDirectoryValidation:
    """Validate one exact runner-owned persisted task manifest.

    This dependency-free boundary is shared by replay and benchmark
    eligibility.  It closes count/order/completeness, task metadata, local vs
    aggregate result parity, and task-directory containment before any task is
    allowed to reach the evidence validator.
    """
    checked = RunDirectoryValidation()
    errors = checked.errors
    if run_dir.is_symlink() or not run_dir.is_dir():
        errors.append("run directory must be a real directory")
        return checked
    try:
        resolved_run = run_dir.resolve(strict=True)
    except OSError as exc:
        errors.append(f"run directory is unresolvable: {exc}")
        return checked

    run_record = _read_object(run_dir / "run.json", label="run.json", errors=errors)
    checked.run_record = run_record
    try:
        run_id = validate_nonempty_string(
            run_record.get("run_id"), field_name="run.json run_id"
        )
    except ValueError as exc:
        errors.append(str(exc))
        run_id = "<invalid-run-id>"
    if run_record.get("status") != "completed":
        errors.append("run.json status must be 'completed'")

    raw_task_ids = run_record.get("task_ids")
    if not isinstance(raw_task_ids, list):
        errors.append("run.json task_ids must be an ordered array")
        raw_task_ids = []
    task_ids: list[str] = []
    seen: set[str] = set()
    for index, value in enumerate(raw_task_ids):
        try:
            task_id = validate_task_id(
                value, field_name=f"run.json task_ids[{index}]"
            )
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if task_id in seen:
            errors.append(f"run.json task_ids duplicates {task_id!r}")
            continue
        seen.add(task_id)
        task_ids.append(task_id)
    checked.task_ids = task_ids
    task_count = run_record.get("task_count")
    if isinstance(task_count, bool) or not isinstance(task_count, int):
        errors.append("run.json task_count must be an integer")
    elif task_count != len(raw_task_ids):
        errors.append("run.json task_count does not match task_ids length")
    if not raw_task_ids:
        errors.append("run.json must schedule at least one task")
    suite = run_record.get("suite")
    if not isinstance(suite, dict):
        errors.append("run.json suite must be an object")
    else:
        requested_count = suite.get("task_count_requested")
        if isinstance(requested_count, bool) or not isinstance(requested_count, int):
            errors.append("run.json suite task_count_requested must be an integer")
        elif requested_count != len(raw_task_ids):
            errors.append("run.json suite task_count_requested does not match task_ids")

    raw_manifest = run_record.get("task_manifest")
    if not isinstance(raw_manifest, list):
        errors.append("run.json task_manifest must be an ordered array")
        raw_manifest = []
    manifest_ids: list[str] = []
    for index, row in enumerate(raw_manifest):
        if not isinstance(row, dict) or set(row) != {"task_id", "source"}:
            errors.append(
                f"run.json task_manifest[{index}] fields must be exactly task_id and source"
            )
            continue
        try:
            task_id = validate_task_id(
                row.get("task_id"), field_name=f"task_manifest[{index}] task_id"
            )
            source = validate_nonempty_string(
                row.get("source"), field_name=f"task_manifest[{index}] source"
            )
        except ValueError as exc:
            errors.append(str(exc))
            continue
        manifest_ids.append(task_id)
        if task_id in checked.task_sources:
            errors.append(f"run.json task_manifest duplicates {task_id!r}")
        else:
            checked.task_sources[task_id] = source
    if manifest_ids != raw_task_ids:
        errors.append("run.json task_manifest order does not exactly match task_ids")

    run_verifier = run_record.get("verifier")
    run_verifier_id: str | None = None
    run_verifier_checksum: str | None = None
    if run_verifier is not None:
        if not isinstance(run_verifier, dict) or set(run_verifier) != {"id", "checksum"}:
            errors.append("run.json verifier fields must be exactly id and checksum")
        else:
            try:
                run_verifier_id = validate_nonempty_string(
                    run_verifier.get("id"), field_name="run.json verifier id"
                )
                run_verifier_checksum = validate_nonempty_string(
                    run_verifier.get("checksum"),
                    field_name="run.json verifier checksum",
                )
            except ValueError as exc:
                errors.append(str(exc))
                run_verifier_id = None
                run_verifier_checksum = None

    summary = _read_object(
        run_dir / "summary.json", label="summary.json", errors=errors
    )
    checked.summary_record = summary
    if summary.get("run_id") != run_id:
        errors.append("summary.json run_id does not match run.json")
    summary_task_count = summary.get("task_count")
    if isinstance(summary_task_count, bool) or not isinstance(summary_task_count, int):
        errors.append("summary.json task_count must be an integer")
    elif summary_task_count != len(raw_task_ids):
        errors.append("summary.json task_count does not match run.json task_ids")

    results_path = run_dir / "results.jsonl"
    results: list[dict[str, Any]] = []
    if results_path.is_symlink() or not results_path.is_file():
        errors.append("results.jsonl must be a real regular file")
    else:
        try:
            results = read_jsonl(results_path)
        except (OSError, ValueError) as exc:
            errors.append(f"results.jsonl is unreadable: {exc}")
    if len(results) != len(raw_task_ids):
        errors.append("results.jsonl count does not match run.json task_count")
    aggregate_ids: list[str] = []
    for index, row in enumerate(results):
        expected_task_id = raw_task_ids[index] if index < len(raw_task_ids) else None
        expected_source = (
            checked.task_sources.get(expected_task_id)
            if isinstance(expected_task_id, str)
            else None
        )
        try:
            validated = validate_persisted_result(
                row,
                expected_run_id=run_id,
                expected_task_id=expected_task_id,
                expected_source=expected_source,
            )
        except ValueError as exc:
            errors.append(f"results.jsonl row {index + 1}: {exc}")
            continue
        aggregate_ids.append(validated["task_id"])
        if validated["task_id"] in checked.results_by_task:
            errors.append(
                f"results.jsonl duplicates task_id {validated['task_id']!r}"
            )
        else:
            checked.results_by_task[validated["task_id"]] = validated
        checked.results.append(validated)
    if aggregate_ids != raw_task_ids:
        errors.append("results.jsonl task order does not exactly match run.json task_ids")

    tasks_root = run_dir / "tasks"
    actual_names: set[str] = set()
    resolved_tasks: Path | None = None
    if tasks_root.is_symlink() or not tasks_root.is_dir():
        errors.append("tasks must be a real directory")
    else:
        try:
            resolved_tasks = tasks_root.resolve(strict=True)
        except OSError as exc:
            errors.append(f"tasks directory is unresolvable: {exc}")
        else:
            if resolved_tasks.parent != resolved_run:
                errors.append("tasks directory escapes the run root")
        try:
            entries = list(tasks_root.iterdir())
        except OSError as exc:
            errors.append(f"tasks directory is unreadable: {exc}")
            entries = []
        for entry in entries:
            actual_names.add(entry.name)
            if entry.is_symlink() or not entry.is_dir():
                errors.append(f"tasks entry {entry.name!r} must be a real directory")
    expected_names = set(task_ids)
    missing = sorted(expected_names - actual_names)
    unexpected = sorted(actual_names - expected_names)
    if missing:
        errors.append(f"tasks directory is missing scheduled task(s): {', '.join(missing)}")
    if unexpected:
        errors.append(
            f"tasks directory contains unexpected task(s): {', '.join(unexpected)}"
        )

    for task_id in task_ids:
        source = checked.task_sources.get(task_id)
        if source is None:
            continue
        task_root = tasks_root / task_id
        if task_root.is_symlink() or not task_root.is_dir():
            continue
        try:
            resolved_task = task_root.resolve(strict=True)
        except OSError as exc:
            errors.append(f"task directory {task_id!r} is unresolvable: {exc}")
            continue
        if resolved_tasks is None or resolved_task.parent != resolved_tasks:
            errors.append(f"task directory {task_id!r} escapes the run root")
            continue

        task = _read_object(
            task_root / "task.json",
            label=f"task {task_id} task.json",
            errors=errors,
        )
        if task.get("id") != task_id:
            errors.append(f"task {task_id} task.json id does not match the schedule")
        if task.get("source") != source:
            errors.append(f"task {task_id} task.json source does not match the schedule")
        verification = task.get("verification")
        if run_verifier_id is not None and run_verifier_checksum is not None:
            if not isinstance(verification, dict):
                errors.append(f"task {task_id} verification must be an object")
            elif (
                verification.get("verifier_id") != run_verifier_id
                or verification.get("verifier_checksum") != run_verifier_checksum
            ):
                errors.append(
                    f"task {task_id} verifier metadata does not match run.json"
                )
        checked.tasks_by_id[task_id] = task

        local = _read_object(
            task_root / "result.json",
            label=f"task {task_id} result.json",
            errors=errors,
        )
        aggregate = checked.results_by_task.get(task_id)
        try:
            validated_local = validate_persisted_result(
                local,
                expected_run_id=run_id,
                expected_task_id=task_id,
                expected_source=source,
            )
        except ValueError as exc:
            errors.append(f"task {task_id} result.json: {exc}")
            continue
        if aggregate is None:
            errors.append(f"task {task_id} has no aggregate results.jsonl row")
        else:
            try:
                equal = canonical_json(validated_local) == canonical_json(aggregate)
            except ValueError as exc:
                errors.append(f"task {task_id} result comparison failed: {exc}")
            else:
                if not equal:
                    errors.append(
                        f"task {task_id} result.json does not exactly match results.jsonl"
                    )
    return checked


def load_run_artifacts(
    run_dir: Path,
    *,
    adapter_reportable: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Rebuild persisted run artifacts through one fail-closed replay path.

    Persisted summary flags and adapter records are diagnostic only. The loop's
    separate shared bundle validator is the authority for trace/artifact
    integrity; ordinary replay deliberately remains non-reportable.
    """
    checked = validate_run_directory(run_dir)
    persisted = checked.summary_record
    if checked.errors:
        return (
            _invalid_replay_summary(
                persisted,
                errors=checked.errors,
                task_count=len(checked.results),
            ),
            [],
        )

    rebuilt = summarize_results(
        checked.results, adapter_reportable=adapter_reportable
    )

    rebuilt["run_id"] = checked.run_record["run_id"]
    if "suite_id" in persisted:
        rebuilt["suite_id"] = persisted["suite_id"]
    return rebuilt, checked.results


def load_run_summary(run_dir: Path) -> dict[str, Any]:
    return load_run_artifacts(run_dir)[0]
