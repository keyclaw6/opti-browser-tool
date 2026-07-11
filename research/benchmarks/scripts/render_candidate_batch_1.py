#!/usr/bin/env python3
"""Render deterministic Batch 1 review artifacts from the canonical JSONL inventory.

The JSONL file is the canonical row-level inventory. This script regenerates the
CSV export, source/site/interaction summaries, and the human-readable exact task
index. It does not select tasks or infer task-level success rates.
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
DIR = ROOT / "research" / "benchmarks" / "task-candidates"
JSONL_PATH = DIR / "batch-1-candidates.jsonl"
CSV_PATH = DIR / "batch-1-candidates.csv"
INDEX_PATH = DIR / "batch-1-index.md"
SUMMARY_SOURCE_PATH = DIR / "batch-1-summary-by-source.csv"
SUMMARY_SITE_PATH = DIR / "batch-1-summary-by-site.csv"
SUMMARY_INTERACTION_PATH = DIR / "batch-1-summary-by-interaction.csv"

SOURCE_ORDER = [
    "REAL",
    "WorkArena++ L2",
    "WebArena-Verified",
    "VisualWebArena",
    "WARC-Bench",
]

CSV_FIELDS = [
    "candidate_id",
    "source",
    "source_version",
    "native_task_id",
    "seed",
    "site",
    "task_intent",
    "source_difficulty",
    "interaction_class",
    "mutates_state",
    "evaluator_type",
    "evaluator_strength",
    "public_benchmark_reference_percent",
    "public_benchmark_reference_system",
    "public_reference_date",
    "public_reference_status",
    "score_evidence_scope",
    "public_benchmark_reference_at_least_40_percent",
    "per_task_reference_success_percent",
    "per_task_calibration_status",
    "candidate_priority",
    "selection_rationale",
    "audit_flags",
    "score_source",
    "source_manifest",
    "source_checksum",
    "task_family_description",
    "task_revision",
    "intent_template_id",
    "data_path",
]


def load_rows() -> list[dict[str, Any]]:
    rows = [
        json.loads(line)
        for line in JSONL_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    missing = [
        (row.get("candidate_id", "<unknown>"), field)
        for row in rows
        for field in CSV_FIELDS[:26]
        if field not in row
    ]
    if missing:
        raise ValueError(f"canonical JSONL is missing required fields: {missing[:10]}")
    return rows


def csv_value(value: Any) -> Any:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return value


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fields})


def clean_md(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\r", " ").replace("\n", " ").strip()


def write_index(rows: list[dict[str, Any]]) -> None:
    lines = [
        "# Batch 1 exact candidate index",
        "",
        "All entries are provisional. `Public benchmark reference` is source-level evidence; "
        "the individual task rate remains unknown until calibration.",
        "",
    ]
    for source in SOURCE_ORDER:
        group = [row for row in rows if row["source"] == source]
        if not group:
            continue
        score = group[0]["public_benchmark_reference_percent"]
        lines.extend(
            [
                f"## {source} — {len(group)} candidates (public benchmark reference: {score}%)",
                "",
                "| Candidate ID | Native ID / seed | Site | Source difficulty | Priority | Task |",
                "|---|---|---|---|---|---|",
            ]
        )
        for row in group:
            native = clean_md(row["native_task_id"])
            if str(row.get("seed", "")).strip():
                native = f"{native} / {clean_md(row['seed'])}"
            lines.append(
                "| `{candidate}` | `{native}` | {site} | {difficulty} | {priority} | {task} |".format(
                    candidate=clean_md(row["candidate_id"]),
                    native=native,
                    site=clean_md(row["site"]),
                    difficulty=clean_md(row["source_difficulty"]),
                    priority=clean_md(row["candidate_priority"]),
                    task=clean_md(row["task_intent"]),
                )
            )
        lines.append("")
    INDEX_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_summaries(rows: list[dict[str, Any]]) -> None:
    source_rows = []
    for source in SOURCE_ORDER:
        group = [row for row in rows if row["source"] == source]
        if group:
            source_rows.append(
                {
                    "source": source,
                    "candidate_count": len(group),
                    "public_benchmark_reference_percent": group[0][
                        "public_benchmark_reference_percent"
                    ],
                    "score_scope": "benchmark aggregate; task calibration required",
                }
            )
    write_csv(
        SUMMARY_SOURCE_PATH,
        [
            "source",
            "candidate_count",
            "public_benchmark_reference_percent",
            "score_scope",
        ],
        source_rows,
    )

    site_counts = Counter((row["source"], row["site"]) for row in rows)
    site_rows = [
        {"source": source, "site": site, "candidate_count": count}
        for source in SOURCE_ORDER
        for (src, site), count in sorted(site_counts.items(), key=lambda item: item[0][1].lower())
        if src == source
    ]
    write_csv(SUMMARY_SITE_PATH, ["source", "site", "candidate_count"], site_rows)

    interaction_counts = Counter(row["interaction_class"] for row in rows)
    interaction_rows = [
        {"interaction_class": interaction, "candidate_count": count}
        for interaction, count in sorted(interaction_counts.items())
    ]
    write_csv(
        SUMMARY_INTERACTION_PATH,
        ["interaction_class", "candidate_count"],
        interaction_rows,
    )


def main() -> None:
    rows = load_rows()
    write_csv(CSV_PATH, CSV_FIELDS, rows)
    write_index(rows)
    write_summaries(rows)
    print(f"Rendered Batch 1 artifacts from {len(rows)} canonical JSONL rows.")


if __name__ == "__main__":
    main()
