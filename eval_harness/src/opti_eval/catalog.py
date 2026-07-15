from __future__ import annotations

from pathlib import Path
from typing import Any

from .errors import ValidationError
from .models import (
    validate_nonempty_string,
    validate_standard_json,
    validate_task_id,
)
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
    path = repo_root / "evals" / "catalog" / "tasks.jsonl"
    try:
        rows = read_jsonl(path)
    except (OSError, ValueError) as exc:
        raise ValidationError(f"Malformed catalog {path}: {exc}") from exc
    index: dict[str, dict[str, Any]] = {}
    for task in rows:
        try:
            validate_standard_json(task, field_name="catalog task")
            task_id = validate_task_id(task.get("id"), field_name="catalog task id")
            validate_nonempty_string(task.get("source"), field_name="catalog task source")
            validate_nonempty_string(task.get("goal"), field_name="catalog task goal")
            validate_nonempty_string(task.get("site"), field_name="catalog task site")
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
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
    try:
        suite = read_json(path)
    except (OSError, ValueError) as exc:
        raise ValidationError(f"Malformed suite manifest {path}: {exc}") from exc
    if not isinstance(suite, dict) or not isinstance(suite.get("task_ids"), list):
        raise ValidationError(f"Malformed suite manifest: {path}")
    try:
        validate_standard_json(suite, field_name="suite manifest")
        validate_nonempty_string(suite.get("id"), field_name="suite id")
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    task_ids: list[str] = []
    seen: set[str] = set()
    for index, value in enumerate(suite["task_ids"]):
        try:
            task_id = validate_task_id(value, field_name=f"suite task_ids[{index}]")
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        if task_id in seen:
            raise ValidationError(f"Suite contains duplicate task id: {task_id}")
        seen.add(task_id)
        task_ids.append(task_id)
    task_count = suite.get("task_count")
    if (
        isinstance(task_count, bool)
        or not isinstance(task_count, int)
        or task_count != len(task_ids)
    ):
        raise ValidationError(
            f"Suite task_count must equal its ordered task_ids length: {path}"
        )
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
        try:
            requested_order = [
                validate_task_id(value, field_name="requested task id")
                for value in task_ids
            ]
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        if len(set(requested_order)) != len(requested_order):
            raise ValidationError("Requested task IDs must be unique")
        requested = set(requested_order)
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
