#!/usr/bin/env python3
"""Build the normalized 140-task catalog and runnable suite manifests.

The source of truth is the exact Batch 1 candidate inventory. This script does
not claim task-level calibration; it preserves that status explicitly.
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "research/benchmarks/task-candidates/batch-1-candidates.jsonl"
ARCHIVED = ROOT / "archive/superseded/runnable-suite-v0-100/evals/suites"
CATALOG_DIR = ROOT / "evals/catalog"
SUITE_DIR = ROOT / "evals/suites"

SOURCE_MAP = {
    "REAL": ("real_v1", "REAL v1"),
    "WebArena-Verified": ("webarena_verified", "WebArena-Verified"),
    "WorkArena++ L2": ("workarena_l2", "WorkArena++ Level 2"),
    "VisualWebArena": ("visualwebarena", "VisualWebArena"),
    "WARC-Bench": ("warc_bench", "WARC-Bench"),
}

CATALOG_CREATED_AT = "2026-07-11T23:24:37Z"

DEFAULT_TIMEOUTS = {
    "real_v1": 900,
    "webarena_verified": 900,
    "workarena_l2": 1200,
    "visualwebarena": 900,
    "warc_bench": 600,
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_manifest_ids(path: Path) -> list[str]:
    if not path.is_file():
        return []
    return list(json.loads(path.read_text(encoding="utf-8"))["task_ids"])


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_jsonl(path: Path, values: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(value, ensure_ascii=False) + "\n" for value in values),
        encoding="utf-8",
    )


def upstream_locator(raw: dict[str, Any]) -> dict[str, Any]:
    locator: dict[str, Any] = {
        "benchmark": raw["source"],
        "version": raw["source_version"],
        "native_task_id": str(raw["native_task_id"]),
        "site": raw["site"],
        "source_manifest": raw["source_manifest"],
        "source_checksum": raw["source_checksum"],
    }
    for key in ("seed", "data_path", "task_revision", "intent_template_id", "task_family_description"):
        value = raw.get(key)
        if value not in (None, "", [], {}):
            locator[key] = value
    return locator


def main() -> None:
    candidates = read_jsonl(CANDIDATES)
    if len(candidates) != 140:
        raise SystemExit(f"Expected 140 candidate rows, found {len(candidates)}")

    previous_primary = set(read_manifest_ids(ARCHIVED / "primary.json"))
    smoke_ids = read_manifest_ids(ARCHIVED / "smoke.json")
    if len(smoke_ids) != 20:
        raise SystemExit("Expected preserved smoke manifest with 20 tasks")
    smoke_set = set(smoke_ids)

    catalog: list[dict[str, Any]] = []
    by_source: dict[str, list[dict[str, Any]]] = {key: [] for key, _ in SOURCE_MAP.values()}
    for raw in candidates:
        source_key, display_name = SOURCE_MAP[raw["source"]]
        task_id = raw["candidate_id"]
        memberships = ["candidate-pool", "primary"]
        if task_id in smoke_set:
            memberships.extend(["smoke", "regression"])
        reference = float(raw["public_benchmark_reference_percent"])
        task = {
            "schema_version": "0.2.0",
            "id": task_id,
            "source": source_key,
            "source_display_name": display_name,
            "upstream": upstream_locator(raw),
            "goal": raw["task_intent"],
            "site": raw["site"],
            "interaction_class": raw["interaction_class"],
            "state_change_expected": str(raw["mutates_state"]).lower() == "yes",
            "source_difficulty": raw["source_difficulty"],
            "candidate_priority": raw["candidate_priority"],
            "audit_flags": [flag for flag in str(raw.get("audit_flags", "")).split(";") if flag],
            "suite_membership": memberships,
            "selection_history": {
                "included_in_superseded_100_task_draft": task_id in previous_primary,
                "included_in_current_140_task_candidate_pool": True,
            },
            "difficulty_evidence": {
                "accepted_reference_band_percent": {
                    "minimum_percent": 35.0,
                    "maximum_percent": 70.0,
                    "inclusive": True,
                },
                "reference_success_percent": reference,
                "reference_system": raw["public_benchmark_reference_system"],
                "reference_date": raw["public_reference_date"],
                "reference_source": raw["score_source"],
                "reference_status": raw["public_reference_status"],
                "source_reference_in_accepted_band": 35.0 <= reference <= 70.0,
                "evidence_scope": "benchmark_aggregate_not_task_level",
                "per_task_success_percent": None,
                "per_task_calibration_status": "pending",
                "note": "The published score screens the benchmark family only. This task must be calibrated locally before final admission.",
            },
            "verification": {
                "status": "pending",
                "expected_verifier_type": raw["evaluator_type"],
                "expected_verifier_strength": raw["evaluator_strength"],
                "environment_reset_status": "pending",
                "oracle_or_known_good_run_status": "pending",
                "adversarial_verifier_audit_status": "pending",
                "fail_closed": True,
            },
            "runtime": {
                "bridge_key": source_key,
                "default_timeout_seconds": DEFAULT_TIMEOUTS[source_key],
            },
            "provenance": {
                "candidate_inventory": "research/benchmarks/task-candidates/batch-1-candidates.jsonl",
                "raw_candidate_record": raw,
            },
        }
        catalog.append(task)
        by_source[source_key].append(task)

    CATALOG_DIR.mkdir(parents=True, exist_ok=True)
    write_jsonl(CATALOG_DIR / "tasks.jsonl", catalog)
    write_json(CATALOG_DIR / "task-index.json", {task["id"]: task for task in catalog})

    # Materialize one pretty-printed record per task for audit and handoff.
    # These are derived review copies; tasks.jsonl remains canonical.
    by_id_dir = CATALOG_DIR / "by-id"
    if by_id_dir.exists():
        for path in sorted(by_id_dir.rglob("*.json")):
            path.unlink()
    for task in catalog:
        write_json(by_id_dir / task["source"] / f"{task['id']}.json", task)

    by_source_dir = CATALOG_DIR / "by-source"
    by_source_dir.mkdir(parents=True, exist_ok=True)
    for source, tasks in by_source.items():
        write_jsonl(by_source_dir / f"{source}.jsonl", tasks)

    csv_fields = [
        "id", "source", "source_display_name", "native_task_id", "seed", "site", "goal",
        "interaction_class", "state_change_expected", "source_difficulty", "candidate_priority",
        "reference_success_percent", "evidence_scope", "per_task_success_percent",
        "per_task_calibration_status", "verification_status", "suite_membership",
        "included_in_superseded_100_task_draft", "source_version", "source_manifest", "source_checksum",
    ]
    with (CATALOG_DIR / "tasks.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=csv_fields)
        writer.writeheader()
        for task in catalog:
            writer.writerow(
                {
                    "id": task["id"],
                    "source": task["source"],
                    "source_display_name": task["source_display_name"],
                    "native_task_id": task["upstream"]["native_task_id"],
                    "seed": task["upstream"].get("seed", ""),
                    "site": task["site"],
                    "goal": task["goal"],
                    "interaction_class": task["interaction_class"],
                    "state_change_expected": task["state_change_expected"],
                    "source_difficulty": task["source_difficulty"],
                    "candidate_priority": task["candidate_priority"],
                    "reference_success_percent": task["difficulty_evidence"]["reference_success_percent"],
                    "evidence_scope": task["difficulty_evidence"]["evidence_scope"],
                    "per_task_success_percent": "",
                    "per_task_calibration_status": "pending",
                    "verification_status": "pending",
                    "suite_membership": ";".join(task["suite_membership"]),
                    "included_in_superseded_100_task_draft": task["selection_history"]["included_in_superseded_100_task_draft"],
                    "source_version": task["upstream"]["version"],
                    "source_manifest": task["upstream"]["source_manifest"],
                    "source_checksum": task["upstream"]["source_checksum"],
                }
            )

    all_ids = [task["id"] for task in catalog]
    counts = Counter(task["source"] for task in catalog)
    created = CATALOG_CREATED_AT
    common_policy = {
        "reference_success_band_percent": {
            "minimum_percent": 35.0,
            "maximum_percent": 70.0,
            "inclusive": True,
        },
        "source_aggregate_screening_complete": True,
        "per_task_calibration_required_before_freeze": True,
        "task_verification_required_before_freeze": True,
        "missing_environment_or_verifier_invalidates_run": True,
        "smoke_is_subset_of_primary": True,
        "current_primary_is_unfiltered_candidate_pool": True,
    }
    pool_manifest = {
        "schema_version": "0.2.0",
        "id": "opti-browser-candidate-pool-v0",
        "kind": "candidate_pool",
        "status": "provisional_runnable_unfiltered",
        "created_at": created,
        "task_count": len(all_ids),
        "task_ids": all_ids,
        "source_quotas": dict(sorted(counts.items())),
        "policy": common_policy,
        "note": "All 140 sourced candidates. Tasks remain provisional until environment, verifier, reset, oracle, and per-task calibration checks pass.",
    }
    primary_manifest = dict(pool_manifest)
    primary_manifest.update(
        {
            "id": "opti-browser-primary-candidates-v0",
            "kind": "primary",
            "note": "The active primary manifest intentionally contains all 140 provisional candidates for initial execution. It will be filtered to the final target after calibration.",
        }
    )
    smoke_counts = Counter(next(task["source"] for task in catalog if task["id"] == task_id) for task_id in smoke_ids)
    smoke_manifest = {
        "schema_version": "0.2.0",
        "id": "opti-browser-smoke-v0",
        "kind": "smoke",
        "status": "provisional_runnable",
        "created_at": created,
        "task_count": len(smoke_ids),
        "task_ids": smoke_ids,
        "source_quotas": dict(sorted(smoke_counts.items())),
        "policy": common_policy,
        "note": "A 20-task nested smoke subset for fast implementation checks. It remains provisional pending task validation.",
    }
    regression_manifest = dict(smoke_manifest)
    regression_manifest.update(
        {
            "id": "opti-browser-regression-seed-v0",
            "kind": "regression",
            "note": "Provisional regression seed equal to smoke. Tasks become permanent gates only after repeated baseline verification and demonstrated fixes.",
        }
    )
    SUITE_DIR.mkdir(parents=True, exist_ok=True)
    write_json(SUITE_DIR / "candidate-pool.json", pool_manifest)
    write_json(SUITE_DIR / "primary.json", primary_manifest)
    write_json(SUITE_DIR / "smoke.json", smoke_manifest)
    write_json(SUITE_DIR / "regression.json", regression_manifest)

    print(f"Wrote {len(catalog)} normalized tasks")
    print("Source counts:", dict(sorted(counts.items())))
    print(f"Smoke/regression: {len(smoke_ids)}")


if __name__ == "__main__":
    main()
