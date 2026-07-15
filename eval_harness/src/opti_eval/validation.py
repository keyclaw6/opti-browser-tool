from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .catalog import load_catalog, load_suite
from .util import read_json, read_jsonl

EXPECTED_SOURCE_COUNTS = {
    "real_v1": 30,
    "webarena_verified": 30,
    "workarena_l2": 30,
    "visualwebarena": 30,
    "warc_bench": 20,
}
EXPECTED_CANDIDATE_COUNT = 140
EXPECTED_SMOKE_COUNT = 20
REFERENCE_MIN = 35.0
REFERENCE_MAX = 70.0


def _check(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def validate_repository(repo_root: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    candidate_path = (
        repo_root
        / "research"
        / "benchmarks"
        / "task-candidates"
        / "batch-1-candidates.jsonl"
    )
    candidates = read_jsonl(candidate_path)
    candidate_index = {str(row.get("candidate_id")): row for row in candidates}
    _check(len(candidates) == EXPECTED_CANDIDATE_COUNT, f"Expected 140 candidate rows, found {len(candidates)}", errors)
    _check(len(candidate_index) == len(candidates), "Candidate IDs are not unique", errors)

    catalog_rows, catalog_index = load_catalog(repo_root)
    _check(len(catalog_rows) == EXPECTED_CANDIDATE_COUNT, f"Expected 140 catalog rows, found {len(catalog_rows)}", errors)
    _check(set(catalog_index) == set(candidate_index), "Catalog IDs do not exactly match candidate IDs", errors)

    source_counts = Counter(str(task.get("source")) for task in catalog_rows)
    _check(dict(source_counts) == EXPECTED_SOURCE_COUNTS, f"Unexpected catalog source counts: {dict(source_counts)}", errors)

    by_id_root = repo_root / "evals" / "catalog" / "by-id"
    by_id_paths = sorted(by_id_root.rglob("*.json")) if by_id_root.is_dir() else []
    _check(len(by_id_paths) == EXPECTED_CANDIDATE_COUNT, f"Expected 140 individual by-ID task files, found {len(by_id_paths)}", errors)
    by_id_ids: set[str] = set()
    for path in by_id_paths:
        try:
            record = read_json(path)
        except (OSError, ValueError) as exc:
            errors.append(f"Invalid individual task file {path}: {exc}")
            continue
        if not isinstance(record, dict):
            errors.append(f"Invalid individual task file {path}: expected object")
            continue
        task_id = str(record.get("id"))
        by_id_ids.add(task_id)
        if task_id in catalog_index:
            _check(record == catalog_index[task_id], f"{task_id}: individual task file differs from canonical catalog", errors)
    _check(by_id_ids == set(catalog_index), "Individual by-ID task files do not exactly match catalog IDs", errors)

    for task_id, task in catalog_index.items():
        raw = task.get("provenance", {}).get("raw_candidate_record")
        _check(isinstance(raw, dict), f"{task_id}: missing raw candidate provenance", errors)
        if not isinstance(raw, dict):
            continue
        _check(str(raw.get("candidate_id")) == task_id, f"{task_id}: raw candidate ID mismatch", errors)
        _check(task.get("goal") == raw.get("task_intent"), f"{task_id}: normalized goal does not match task_intent", errors)
        expected_mutation = str(raw.get("mutates_state", "")).lower() == "yes"
        _check(bool(task.get("state_change_expected")) == expected_mutation, f"{task_id}: state_change_expected mismatch", errors)
        evidence = task.get("difficulty_evidence", {})
        reference = evidence.get("reference_success_percent")
        _check(isinstance(reference, (int, float)), f"{task_id}: missing numeric source reference success", errors)
        if isinstance(reference, (int, float)):
            _check(REFERENCE_MIN <= float(reference) <= REFERENCE_MAX, f"{task_id}: reference {reference} outside 35–70 band", errors)
        _check(evidence.get("evidence_scope") == "benchmark_aggregate_not_task_level", f"{task_id}: benchmark aggregate incorrectly scoped", errors)
        _check(evidence.get("per_task_success_percent") is None, f"{task_id}: uncalibrated task has a per-task success value", errors)
        _check(task.get("verification", {}).get("status") == "pending", f"{task_id}: task should remain pending verification", errors)

    primary = load_suite(repo_root, "primary")
    candidate_pool = load_suite(repo_root, "candidate-pool")
    smoke = load_suite(repo_root, "smoke")
    regression = load_suite(repo_root, "regression")

    primary_ids = list(primary.get("task_ids", []))
    pool_ids = list(candidate_pool.get("task_ids", []))
    smoke_ids = list(smoke.get("task_ids", []))
    regression_ids = list(regression.get("task_ids", []))

    _check(len(primary_ids) == EXPECTED_CANDIDATE_COUNT, f"Primary manifest should contain all 140 provisional candidates, found {len(primary_ids)}", errors)
    _check(len(pool_ids) == EXPECTED_CANDIDATE_COUNT, f"Candidate-pool manifest should contain 140 tasks, found {len(pool_ids)}", errors)
    _check(primary_ids == pool_ids, "Primary and candidate-pool manifests should be identical before filtering", errors)
    _check(set(primary_ids) == set(catalog_index), "Primary task IDs do not exactly match catalog", errors)
    _check(len(primary_ids) == len(set(primary_ids)), "Primary manifest contains duplicate task IDs", errors)
    _check(len(smoke_ids) == EXPECTED_SMOKE_COUNT, f"Smoke manifest should contain 20 tasks, found {len(smoke_ids)}", errors)
    _check(len(regression_ids) == EXPECTED_SMOKE_COUNT, f"Regression seed should contain 20 tasks, found {len(regression_ids)}", errors)
    _check(set(smoke_ids).issubset(primary_ids), "Smoke tasks are not a subset of primary", errors)
    _check(set(regression_ids).issubset(primary_ids), "Regression tasks are not a subset of primary", errors)
    _check(smoke_ids == regression_ids, "Provisional regression seed should equal smoke in this version", errors)

    for path in sorted((repo_root / "evals" / "schemas").glob("*.json")):
        try:
            read_json(path)
        except (OSError, ValueError) as exc:
            errors.append(f"Invalid JSON schema file {path}: {exc}")

    historical = repo_root / "archive" / "superseded" / "runnable-suite-v0-100"
    if not historical.is_dir():
        warnings.append("Superseded 100-task implementation was not preserved")

    return {
        "ok": not errors,
        "repo_root": str(repo_root),
        "candidate_count": len(candidates),
        "catalog_count": len(catalog_rows),
        "individual_task_file_count": len(by_id_paths),
        "source_counts": dict(sorted(source_counts.items())),
        "primary_count": len(primary_ids),
        "smoke_count": len(smoke_ids),
        "regression_count": len(regression_ids),
        "errors": errors,
        "warnings": warnings,
    }
