from __future__ import annotations

from pathlib import Path
from typing import Any

from .errors import ValidationError
from .util import read_json, read_jsonl

SUITE_ALIASES = {
    "all": "candidate-pool",
    "candidates": "candidate-pool",
    "candidate_pool": "candidate-pool",
    "candidate-pool": "candidate-pool",
    "primary": "primary",
    "smoke": "smoke",
    "regression": "regression",
}


def load_catalog(repo_root: Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    rows = read_jsonl(repo_root / "evals" / "catalog" / "tasks.jsonl")
    index: dict[str, dict[str, Any]] = {}
    for task in rows:
        task_id = task.get("id")
        if not isinstance(task_id, str) or not task_id:
            raise ValidationError("Every catalog task must have a non-empty string id")
        if task_id in index:
            raise ValidationError(f"Duplicate catalog task id: {task_id}")
        index[task_id] = task
    return rows, index


def load_suite(repo_root: Path, name: str) -> dict[str, Any]:
    normalized = SUITE_ALIASES.get(name, name)
    path = repo_root / "evals" / "suites" / f"{normalized}.json"
    if not path.is_file():
        available = sorted(p.stem for p in (repo_root / "evals" / "suites").glob("*.json"))
        raise ValidationError(f"Unknown suite {name!r}; available: {', '.join(available)}")
    suite = read_json(path)
    if not isinstance(suite, dict) or not isinstance(suite.get("task_ids"), list):
        raise ValidationError(f"Malformed suite manifest: {path}")
    return suite


def select_tasks(
    repo_root: Path,
    suite_name: str,
    *,
    source: str | None = None,
    task_ids: list[str] | None = None,
    limit: int | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    _, index = load_catalog(repo_root)
    suite = load_suite(repo_root, suite_name)
    selected_ids = list(suite["task_ids"])
    if task_ids:
        requested = set(task_ids)
        missing = sorted(requested - set(selected_ids))
        if missing:
            raise ValidationError(
                f"Requested task IDs are not in suite {suite_name!r}: {', '.join(missing)}"
            )
        selected_ids = [task_id for task_id in selected_ids if task_id in requested]
    tasks: list[dict[str, Any]] = []
    for task_id in selected_ids:
        if task_id not in index:
            raise ValidationError(f"Suite references missing catalog task: {task_id}")
        task = index[task_id]
        if source and task.get("source") != source and task.get("source_display_name") != source:
            continue
        tasks.append(task)
    if limit is not None:
        if limit < 0:
            raise ValidationError("--limit must be non-negative")
        tasks = tasks[:limit]
    return suite, tasks
