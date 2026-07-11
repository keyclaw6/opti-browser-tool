#!/usr/bin/env python3
"""Validate the committed Batch 1 candidate artifacts.

This validates manifest identity and internal consistency only. It does not prove
that benchmark environments launch or that any individual task falls inside ADR-0012's
35–70% local strong-system success band.
"""
from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
DIR = ROOT / "research" / "benchmarks" / "task-candidates"


def as_csv_string(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return str(value)


def main() -> None:
    csv_path = DIR / "batch-1-candidates.csv"
    jsonl_path = DIR / "batch-1-candidates.jsonl"
    selection_path = DIR / "batch-1-selection.json"
    lock_path = DIR / "batch-1-sources.lock.json"
    index_path = DIR / "batch-1-index.md"

    assert b"\r\n" not in csv_path.read_bytes(), "candidate CSV must use LF line endings"
    with csv_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    jsonl = [
        json.loads(line)
        for line in jsonl_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    locks = json.loads(lock_path.read_text(encoding="utf-8"))

    assert len(rows) == 140, f"expected 140 CSV rows, found {len(rows)}"
    assert len(jsonl) == 140, f"expected 140 JSONL rows, found {len(jsonl)}"

    csv_ids = [row["candidate_id"] for row in rows]
    jsonl_ids = [row["candidate_id"] for row in jsonl]
    assert csv_ids == jsonl_ids, "CSV and JSONL order or identity differs"
    assert len(csv_ids) == len(set(csv_ids)), "duplicate candidate_id"

    for csv_row, json_row in zip(rows, jsonl, strict=True):
        for field in fieldnames:
            assert csv_row[field] == as_csv_string(json_row.get(field, "")), (
                json_row["candidate_id"],
                field,
                csv_row[field],
                json_row.get(field, ""),
            )

    expected_counts = {
        "REAL": 30,
        "WorkArena++ L2": 30,
        "WebArena-Verified": 30,
        "VisualWebArena": 30,
        "WARC-Bench": 20,
    }
    actual_counts = Counter(row["source"] for row in rows)
    assert actual_counts == expected_counts, (actual_counts, expected_counts)
    assert Counter(row["candidate_priority"] for row in rows) == {"A": 117, "B": 23}
    assert Counter(row["mutates_state"] for row in rows) == {"yes": 131, "no": 9}

    for row in rows:
        score = float(row["public_benchmark_reference_percent"])
        assert 35.0 <= score <= 70.0, (row["candidate_id"], score)
        assert row["public_reference_date"], row["candidate_id"]
        assert row["public_reference_status"] == (
            "latest_verified_public_aggregate_in_this_pass_not_exhaustive_sota_proof"
        )
        assert row["score_evidence_scope"] == "benchmark_aggregate_not_task_level"
        assert row["per_task_reference_success_percent"] == ""
        assert row["per_task_calibration_status"] == "required_before_final_admission"
        assert row["public_benchmark_reference_at_least_40_percent"].lower() == "true"

    # The selection manifest is preserved as historical input and still records
    # the superseded 40% interpretation. The active rule is validated above.
    assert selection["candidate_source_screening_rule"][
        "minimum_public_strong_system_aggregate_percent"
    ] == 40.0
    assert selection["task_level_admission_preference"][
        "minimum_strong_system_success_percent"
    ] == 40.0
    assert locks["lock_schema_version"] == "0.2"
    assert len(locks["sources"]) == 5
    lock_by_source = {item["source"]: item for item in locks["sources"]}
    assert set(lock_by_source) == set(expected_counts)
    for row in rows:
        lock = lock_by_source[row["source"]]
        assert row["source_checksum"] == lock["source_checksum"]
        assert lock["source_checksum_type"]
        assert lock["source_checksum_note"]

    selected_ids: list[str] = []
    for task_id in selection["sources"]["real_v1"]["selected_task_ids"]:
        selected_ids.append(f"real-v1-{task_id}")
    for item in selection["sources"]["workarena_l2"]["selected_task_seed_pairs"]:
        native = item["task_id"].removeprefix("workarena.servicenow.")
        selected_ids.append(f"workarena-l2-{native}-seed-{item['seed']}")
    for task_id in selection["sources"]["webarena_verified"]["selected_task_ids"]:
        selected_ids.append(f"webarena-verified-{task_id}")
    for task_id in selection["sources"]["visualwebarena"]["selected_task_ids"]:
        selected_ids.append(f"visualwebarena-{task_id}")
    for item in selection["sources"]["warc_bench"]["selected_tasks"]:
        selected_ids.append(f"warc-bench-{item['task_id'].replace('.', '-')}")
    assert selected_ids == csv_ids, "selection manifest and canonical inventory differ"

    index_text = index_path.read_text(encoding="utf-8")
    index_rows = re.findall(
        r"^\| `(?P<id>[^`]+)` \| `[^`]+` \| .*? \| .*? \| (?P<priority>[AB]) \|",
        index_text,
        flags=re.MULTILINE,
    )
    assert len(index_rows) == 140, f"expected 140 index rows, found {len(index_rows)}"
    assert index_rows == [(row["candidate_id"], row["candidate_priority"]) for row in rows]

    print("Batch 1 candidate artifacts are internally consistent.")
    print(f"Candidates: {len(rows)}")
    print("By source:")
    for source, count in expected_counts.items():
        print(f"  {source}: {count}")
    print("Priority A/B: 117/23")
    print("State-changing/navigation-or-search: 131/9")
    print("Important: task-level calibration remains required for every candidate.")


if __name__ == "__main__":
    main()
