from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

TERMINAL_VALID_STATUSES = {"passed", "failed"}
INVALIDATING_STATUSES = {"invalid", "error", "skipped"}


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
        if result.get("metadata", {}).get("benchmark_reportable") is False
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
                "One or more bridge results explicitly marked the run as synthetic or non-reportable."
                if not results_reportable
                else (
                    "Eligible for benchmark comparison."
                    if benchmark_reportable
                    else "Not eligible for benchmark comparison because one or more tasks were invalid, errored, or skipped."
                )
            )
        ),
    }
