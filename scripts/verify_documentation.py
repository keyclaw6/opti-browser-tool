#!/usr/bin/env python3
"""Audit reviewer documentation and task-data claims.

The goal is to ensure a future archive contains enough material for another
agent to reconstruct decisions, distinguish active from historical state, and
locate the actual 140 task records without relying on the original chat.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import unquote

REQUIRED_DOCS = [
    "README.md",
    "PROJECT_CHARTER.md",
    "RECOVERY_MANIFEST.md",
    "docs/README.md",
    "docs/AGENT_HANDOFF.md",
    "docs/REVIEW_GUIDE.md",
    "docs/DECISION_PROCESS.md",
    "docs/DECISION_REGISTER.md",
    "docs/DECISION_TIMELINE.md",
    "docs/TASK_DATA_GUIDE.md",
    "docs/ROADMAP.md",
    "docs/OPEN_QUESTIONS.md",
    "docs/PRE_RESEARCH_WORKSTREAMS.md",
    "docs/evaluation/RUNNABLE_SUITE_V0.md",
    "eval_harness/README.md",
    "evals/catalog/README.md",
    "research/benchmarks/task-candidates/README.md",
    "research/benchmarks/candidate-benchmarks.yaml",
    "validation/README.md",
]

ADR_NUMBERS = range(1, 18)
LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
EXPECTED_SOURCE_COUNTS = {
    "real_v1": 30,
    "visualwebarena": 30,
    "warc_bench": 20,
    "webarena_verified": 30,
    "workarena_l2": 30,
}


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _link_target(raw: str) -> str:
    value = raw.strip()
    if value.startswith("<") and ">" in value:
        value = value[1 : value.index(">")]
    elif " " in value:
        # Local repository paths are space-free. Anything following a space is
        # treated as an optional Markdown link title.
        value = value.split(" ", 1)[0]
    return unquote(value).split("#", 1)[0].split("?", 1)[0]


def audit_documentation(root: Path) -> dict:
    root = root.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    checked_links = 0
    checked_markdown = 0

    for relative in REQUIRED_DOCS:
        if not (root / relative).is_file():
            errors.append(f"missing required documentation: {relative}")

    # Check active Markdown links. The superseded 100-task snapshot is an
    # intentionally partial historical capture and is excluded.
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root)
        if ".git" in rel.parts or rel.parts[:2] == ("archive", "superseded"):
            continue
        checked_markdown += 1
        text = path.read_text(encoding="utf-8")
        for raw_target in LINK_RE.findall(text):
            target = _link_target(raw_target)
            if not target or target.startswith(
                ("http://", "https://", "mailto:", "tel:", "sandbox:")
            ):
                continue
            checked_links += 1
            resolved = (path.parent / target).resolve()
            try:
                resolved.relative_to(root)
            except ValueError:
                errors.append(f"link escapes repository: {rel} -> {raw_target}")
                continue
            if not resolved.exists():
                errors.append(f"broken local link: {rel} -> {raw_target}")

    register_path = root / "docs/DECISION_REGISTER.md"
    adr_index_path = root / "docs/adr/README.md"
    register = register_path.read_text(encoding="utf-8") if register_path.is_file() else ""
    adr_index = adr_index_path.read_text(encoding="utf-8") if adr_index_path.is_file() else ""
    for number in ADR_NUMBERS:
        token = f"{number:04d}"
        matches = sorted((root / "docs/adr").glob(f"{token}-*.md"))
        if len(matches) != 1:
            errors.append(f"expected one ADR file for {token}, found {len(matches)}")
        if f"[{token}]" not in register:
            errors.append(f"ADR {token} missing from decision register")
        if f"[{token}]" not in adr_index:
            errors.append(f"ADR {token} missing from ADR index")

    raw_path = root / "research/benchmarks/task-candidates/batch-1-candidates.jsonl"
    normalized_path = root / "evals/catalog/tasks.jsonl"
    raw = read_jsonl(raw_path) if raw_path.is_file() else []
    normalized = read_jsonl(normalized_path) if normalized_path.is_file() else []
    if len(raw) != 140:
        errors.append(f"raw task count is {len(raw)}, expected 140")
    if len(normalized) != 140:
        errors.append(f"normalized task count is {len(normalized)}, expected 140")

    raw_by_id = {row.get("candidate_id"): row for row in raw}
    norm_by_id = {row.get("id"): row for row in normalized}
    if set(raw_by_id) != set(norm_by_id):
        errors.append("raw and normalized task ID sets differ")

    source_counts: dict[str, int] = {}
    for task in normalized:
        source = str(task.get("source"))
        source_counts[source] = source_counts.get(source, 0) + 1
    if source_counts != EXPECTED_SOURCE_COUNTS:
        errors.append(
            f"normalized source counts differ: {source_counts}, expected {EXPECTED_SOURCE_COUNTS}"
        )

    expected_band = {
        "minimum_percent": 35.0,
        "maximum_percent": 70.0,
        "inclusive": True,
    }
    for task_id in sorted(set(raw_by_id) & set(norm_by_id)):
        raw_row = raw_by_id[task_id]
        task = norm_by_id[task_id]
        goal = task.get("goal")
        if not isinstance(goal, str) or not goal.strip():
            errors.append(f"normalized task has empty goal: {task_id}")
        if goal != raw_row.get("task_intent"):
            errors.append(f"normalized goal differs from raw task_intent: {task_id}")
        band = task.get("difficulty_evidence", {}).get(
            "accepted_reference_band_percent", {}
        )
        if band != expected_band:
            errors.append(f"incorrect accepted band in normalized task: {task_id}")
        difficulty = task.get("difficulty_evidence", {})
        if difficulty.get("evidence_scope") != "benchmark_aggregate_not_task_level":
            errors.append(f"incorrect evidence scope: {task_id}")
        if difficulty.get("per_task_success_percent") is not None:
            errors.append(f"uncalibrated task has non-null per-task success: {task_id}")
        embedded = task.get("provenance", {}).get("raw_candidate_record")
        if embedded != raw_row:
            errors.append(f"embedded raw candidate record differs: {task_id}")

    # The readable by-ID files are derived views, but they make it obvious that
    # the actual normalized task bodies are inside the archive.
    by_id_paths = sorted((root / "evals/catalog/by-id").rglob("*.json"))
    if len(by_id_paths) != 140:
        errors.append(f"individual by-ID task count is {len(by_id_paths)}, expected 140")
    by_id_ids: set[str] = set()
    for path in by_id_paths:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"invalid by-ID task file {path.relative_to(root)}: {exc}")
            continue
        task_id = record.get("id")
        by_id_ids.add(task_id)
        if task_id in norm_by_id and record != norm_by_id[task_id]:
            errors.append(f"by-ID task differs from canonical catalog: {task_id}")
    if by_id_ids != set(norm_by_id):
        errors.append("by-ID task set differs from canonical normalized catalog")

    suite_counts: dict[str, int] = {}
    suite_ids: dict[str, set[str]] = {}
    expected_suite_counts = {
        "candidate-pool": 140,
        "primary": 140,
        "smoke": 20,
        "regression": 20,
    }
    for name, expected in expected_suite_counts.items():
        path = root / f"evals/suites/{name}.json"
        if not path.is_file():
            errors.append(f"missing suite manifest: {name}")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        ids = list(data.get("task_ids", []))
        suite_counts[name] = len(ids)
        suite_ids[name] = set(ids)
        if len(ids) != expected or data.get("task_count") != expected:
            errors.append(
                f"suite {name} count mismatch: ids={len(ids)}, "
                f"declared={data.get('task_count')}, expected={expected}"
            )
        unknown = set(ids) - set(norm_by_id)
        if unknown:
            errors.append(f"suite {name} references unknown tasks: {sorted(unknown)[:5]}")

    primary = suite_ids.get("primary", set())
    if suite_ids.get("candidate-pool", set()) != primary:
        errors.append("candidate-pool and provisional primary ID sets differ")
    if not suite_ids.get("smoke", set()) <= primary:
        errors.append("smoke is not a subset of primary")
    if not suite_ids.get("regression", set()) <= primary:
        errors.append("regression is not a subset of primary")

    required_claims = {
        "README.md": [
            "140 provisional task candidates",
            "35–70%",
            "docs/TASK_DATA_GUIDE.md",
            "does **not** vendor",
        ],
        "docs/AGENT_HANDOFF.md": [
            "ADR-0012",
            "ADR-0014",
            "fixture-adapter scores",
            "not vendored",
        ],
        "docs/TASK_DATA_GUIDE.md": [
            "batch-1-candidates.jsonl",
            "evals/catalog/tasks.jsonl",
            "VisualWebArena input images",
            "not a self-contained copy",
        ],
        "docs/PRE_RESEARCH_WORKSTREAMS.md": [
            "140-task provisional pool",
            "not finally admitted",
        ],
        "docs/DECISION_TIMELINE.md": [
            "35–70%, inclusive",
            "All 140 candidates retained",
        ],
        "validation/README.md": [
            "not",
            "benchmark_reportable",
            "must never be cited as agent performance",
        ],
    }
    for relative, fragments in required_claims.items():
        path = root / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for fragment in fragments:
            if fragment not in text:
                errors.append(
                    f"documentation claim missing from {relative}: {fragment!r}"
                )

    candidate_readme_path = root / "research/benchmarks/task-candidates/README.md"
    candidate_readme = (
        candidate_readme_path.read_text(encoding="utf-8")
        if candidate_readme_path.is_file()
        else ""
    )
    if "legacy field" not in candidate_readme or "35–70%" not in candidate_readme:
        errors.append("candidate README does not explain the legacy 40% field")

    # The human-readable index must actually enumerate every exact candidate,
    # rather than merely describe the benchmark families.
    candidate_index_path = root / "research/benchmarks/task-candidates/batch-1-index.md"
    candidate_index = (
        candidate_index_path.read_text(encoding="utf-8")
        if candidate_index_path.is_file()
        else ""
    )
    missing_index_ids = [task_id for task_id in sorted(raw_by_id) if f"`{task_id}`" not in candidate_index]
    if missing_index_ids:
        errors.append(
            "human-readable candidate index omits task IDs: "
            + ", ".join(missing_index_ids[:5])
        )

    # Guard against the stale planning YAML reactivating the superseded 40%
    # floor or the superseded 100-task draft. This file intentionally contains
    # historical proposals, but its current-status block must be unambiguous.
    planning_path = root / "research/benchmarks/candidate-benchmarks.yaml"
    planning = planning_path.read_text(encoding="utf-8") if planning_path.is_file() else ""
    planning_fragments = [
        "related_adr: docs/adr/0012-reference-success-band-35-to-70.md",
        "minimum_percent: 35",
        "maximum_percent: 70",
        "provisional_primary_size: 140",
        "historical_source_allocation_proposal:",
        "proposed_not_accepted_and_not_the_active_manifest",
    ]
    for fragment in planning_fragments:
        if fragment not in planning:
            errors.append(
                "benchmark planning YAML lacks current-status marker: " + repr(fragment)
            )

    return {
        "ok": not errors,
        "repo_root": str(root),
        "required_document_count": len(REQUIRED_DOCS),
        "checked_markdown_files": checked_markdown,
        "checked_local_links": checked_links,
        "adr_count": len(list(ADR_NUMBERS)),
        "raw_task_count": len(raw),
        "normalized_task_count": len(normalized),
        "individual_task_file_count": len(by_id_paths),
        "source_counts": source_counts,
        "suite_counts": suite_counts,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    args = parser.parse_args()
    report = audit_documentation(Path(args.repo_root))
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
