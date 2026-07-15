from __future__ import annotations

import copy
import concurrent.futures
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

from .adapters.base import Adapter
from .models import (
    TaskResult,
    validate_nonempty_string,
    validate_task_id,
)
from .summary import summarize_results
from .util import atomic_write_json, utc_now_iso, write_jsonl


def _safe_result(
    adapter: Adapter,
    task: dict[str, Any],
    task_id: str,
    source: str,
    task_dir: Path,
    run_id: str,
) -> dict[str, Any]:
    task_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(task_dir / "task.json", task)
    started_at = utc_now_iso()
    started = time.monotonic()
    try:
        result = adapter.run(task, task_dir, run_id=run_id)
        if result.task_id != task_id:
            raise ValueError(
                f"Adapter returned task_id={result.task_id!r}; expected {task_id!r}"
            )
        if result.source != source:
            raise ValueError(f"Adapter returned source={result.source!r}; expected {source!r}")
        payload = result.to_dict(run_id=run_id)
    except Exception as exc:  # fail closed at task boundary
        result = TaskResult(
            task_id=task_id,
            source=source,
            status="error",
            reward=None,
            error={"kind": type(exc).__name__, "message": str(exc)},
        )
        payload = result.to_dict(run_id=run_id)
    payload["timing"] = {
        "started_at": started_at,
        "finished_at": utc_now_iso(),
        "elapsed_seconds": time.monotonic() - started,
    }
    atomic_write_json(task_dir / "result.json", payload)
    return payload


def run_evaluation(
    *,
    repo_root: Path,
    suite: dict[str, Any],
    tasks: list[dict[str, Any]],
    adapter: Adapter,
    output_dir: Path,
    max_workers: int = 1,
    overwrite: bool = False,
    verifier_binding: dict[str, str] | None = None,
) -> dict[str, Any]:
    if max_workers < 1:
        raise ValueError("max_workers must be at least 1")

    binding: dict[str, str] | None = None
    if verifier_binding is not None:
        if not isinstance(verifier_binding, dict) or set(verifier_binding) != {
            "id",
            "checksum",
        }:
            raise ValueError("verifier_binding fields must be exactly id and checksum")
        binding = {
            "id": validate_nonempty_string(
                verifier_binding.get("id"), field_name="pinned verifier id"
            ),
            "checksum": validate_nonempty_string(
                verifier_binding.get("checksum"),
                field_name="pinned verifier checksum",
            ),
        }

    scheduled: list[tuple[str, str, dict[str, Any]]] = []
    seen_task_ids: set[str] = set()
    for index, raw_task in enumerate(tasks):
        if not isinstance(raw_task, dict):
            raise ValueError(f"scheduled task {index} must be an object")
        task_id = validate_task_id(
            raw_task.get("id"), field_name=f"scheduled task {index} id"
        )
        source = validate_nonempty_string(
            raw_task.get("source"), field_name=f"scheduled task {task_id} source"
        )
        if task_id in seen_task_ids:
            raise ValueError(f"scheduled task IDs must be unique: {task_id}")
        seen_task_ids.add(task_id)
        task = copy.deepcopy(raw_task)
        if binding is not None:
            verification = task.get("verification")
            if verification is None:
                verification = {}
            if not isinstance(verification, dict):
                raise ValueError(f"scheduled task {task_id} verification must be an object")
            task["verification"] = {
                **verification,
                "verifier_id": binding["id"],
                "verifier_checksum": binding["checksum"],
            }
        scheduled.append((task_id, source, task))
    if not scheduled:
        raise ValueError("an evaluation run must schedule at least one task")

    if output_dir.exists():
        if not overwrite:
            raise FileExistsError(
                f"Output directory already exists: {output_dir}. Use --overwrite to replace it."
            )
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "tasks").mkdir()

    run_id = f"{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{uuid.uuid4().hex[:8]}"
    ordered_task_ids = [task_id for task_id, _, _ in scheduled]
    run_record: dict[str, Any] = {
        "schema_version": "0.1.0",
        "run_id": run_id,
        "status": "running",
        "created_at": utc_now_iso(),
        "repo_root": str(repo_root),
        "suite": {
            "id": suite.get("id"),
            "kind": suite.get("kind"),
            "task_count_requested": len(scheduled),
        },
        "task_count": len(scheduled),
        "task_ids": ordered_task_ids,
        "task_manifest": [
            {"task_id": task_id, "source": source}
            for task_id, source, _ in scheduled
        ],
        "adapter": adapter.describe(),
        "max_workers": max_workers,
    }
    if binding is not None:
        run_record["verifier"] = binding
    atomic_write_json(output_dir / "run.json", run_record)

    indexed_results: dict[str, dict[str, Any]] = {}
    if max_workers == 1:
        for task_id, source, task in scheduled:
            indexed_results[task_id] = _safe_result(
                adapter, task, task_id, source, output_dir / "tasks" / task_id, run_id
            )
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_task = {
                executor.submit(
                    _safe_result,
                    adapter,
                    task,
                    task_id,
                    source,
                    output_dir / "tasks" / task_id,
                    run_id,
                ): (task_id, source, task)
                for task_id, source, task in scheduled
            }
            for future in concurrent.futures.as_completed(future_to_task):
                task_id, _, _ = future_to_task[future]
                indexed_results[task_id] = future.result()

    results = [indexed_results[task_id] for task_id in ordered_task_ids]
    write_jsonl(output_dir / "results.jsonl", results)
    summary = summarize_results(
        results,
        adapter_reportable=bool(adapter.benchmark_reportable),
    )
    summary.update({"run_id": run_id, "suite_id": suite.get("id")})
    atomic_write_json(output_dir / "summary.json", summary)

    run_record.update(
        {
            "status": "completed",
            "finished_at": utc_now_iso(),
            "summary": summary,
        }
    )
    atomic_write_json(output_dir / "run.json", run_record)
    return run_record
