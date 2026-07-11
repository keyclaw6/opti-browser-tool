#!/usr/bin/env python3
"""Validate the committed Batch 1 candidate artifacts.

This intentionally validates internal consistency only. It does not claim that
benchmark environments run or that individual tasks satisfy the 35–70% band.
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DIR = ROOT / "research" / "benchmarks" / "task-candidates"


def main() -> None:
    csv_path = DIR / "batch-1-candidates.csv"
    jsonl_path = DIR / "batch-1-candidates.jsonl"
    selection_path = DIR / "batch-1-selection.json"
    lock_path = DIR / "batch-1-sources.lock.json"

    rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
    jsonl = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines()]
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    locks = json.loads(lock_path.read_text(encoding="utf-8"))

    assert len(rows) == 140, f"expected 140 CSV rows, found {len(rows)}"
    assert len(jsonl) == 140, f"expected 140 JSONL rows, found {len(jsonl)}"

    csv_ids = [row["candidate_id"] for row in rows]
    jsonl_ids = [row["candidate_id"] for row in jsonl]
    assert csv_ids == jsonl_ids, "CSV and JSONL order or identity differs"
    assert len(csv_ids) == len(set(csv_ids)), "duplicate candidate_id"

    expected_counts = {
        "REAL": 30,
        "WorkArena++ L2": 30,
        "WebArena-Verified": 30,
        "VisualWebArena": 30,
        "WARC-Bench": 20,
    }
    actual_counts = Counter(row["source"] for row in rows)
    assert actual_counts == expected_counts, (actual_counts, expected_counts)

    for row in rows:
        score = float(row["public_benchmark_reference_percent"])
        assert 35.0 <= score <= 70.0, (row["candidate_id"], score)
        assert row["public_reference_date"], row["candidate_id"]
        assert row["public_reference_status"] == "latest_verified_public_aggregate_in_this_pass_not_exhaustive_sota_proof"
        assert row["score_evidence_scope"] == "benchmark_aggregate_not_task_level"
        assert row["per_task_reference_success_percent"] == ""
        assert row["per_task_calibration_status"] == "required_before_final_admission"
        assert row["public_benchmark_reference_within_35_70_band"].lower() == "true"

    assert selection["task_level_target_success_rate_percent"] == {
        "minimum": 35.0,
        "maximum": 70.0,
    }
    assert len(locks["sources"]) == 5

    print("Batch 1 candidate artifacts are internally consistent.")
    print(f"Candidates: {len(rows)}")
    print("By source:")
    for source, count in expected_counts.items():
        print(f"  {source}: {count}")
    print("Important: task-level calibration remains required for every candidate.")


if __name__ == "__main__":
    main()
