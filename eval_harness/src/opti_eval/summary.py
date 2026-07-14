from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

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


def _validate_persisted_results(results: list[dict[str, Any]]) -> list[str]:
    if not results:
        return ["results.jsonl must contain at least one result object"]

    errors: list[str] = []
    seen_task_ids: set[str] = set()
    for index, result in enumerate(results, start=1):
        task_id = result.get("task_id")
        if not isinstance(task_id, str) or not task_id.strip():
            errors.append(f"result {index} has no non-empty string task_id")
        elif task_id in seen_task_ids:
            errors.append(f"result {index} duplicates task_id {task_id!r}")
        else:
            seen_task_ids.add(task_id)

        status = result.get("status")
        if not isinstance(status, str) or status not in KNOWN_STATUSES:
            errors.append(f"result {index} has no recognized lowercase status")

        if "metadata" in result and not isinstance(result["metadata"], dict):
            errors.append(f"result {index} metadata must be an object")
    return errors


def load_run_artifacts(
    run_dir: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Rebuild persisted run artifacts through one fail-closed replay path.

    Persisted summary flags and adapter records are diagnostic only. Replay is
    non-authoritative until AR-003 adds a concrete trusted evidence validator.
    """
    errors: list[str] = []
    persisted: dict[str, Any] = {}
    try:
        raw_summary = read_json(run_dir / "summary.json")
        if isinstance(raw_summary, dict):
            persisted = raw_summary
        else:
            errors.append("summary.json must contain an object")
    except (OSError, ValueError) as exc:
        errors.append(f"summary.json is unreadable: {exc}")

    results: list[dict[str, Any]] = []
    try:
        results = read_jsonl(run_dir / "results.jsonl")
    except (OSError, ValueError) as exc:
        errors.append(f"results.jsonl is unreadable: {exc}")
    errors.extend(_validate_persisted_results(results))

    if errors:
        return (
            _invalid_replay_summary(
                persisted,
                errors=errors,
                task_count=len(results),
            ),
            [],
        )

    rebuilt = summarize_results(results, adapter_reportable=False)

    for key in ("run_id", "suite_id"):
        if key in persisted:
            rebuilt[key] = persisted[key]
    return rebuilt, results


def load_run_summary(run_dir: Path) -> dict[str, Any]:
    return load_run_artifacts(run_dir)[0]
