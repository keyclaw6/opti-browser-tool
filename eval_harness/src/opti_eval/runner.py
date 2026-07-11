from __future__ import annotations

import concurrent.futures
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

from .adapters.base import Adapter
from .models import TaskResult
from .summary import summarize_results
from .util import atomic_write_json, utc_now_iso, write_jsonl


def _safe_result(
    adapter: Adapter,
    task: dict[str, Any],
    task_dir: Path,
) -> dict[str, Any]:
    task_id = str(task["id"])
    source = str(task["source"])
    task_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(task_dir / "task.json", task)
    started_at = utc_now_iso()
    started = time.monotonic()
    try:
        result = adapter.run(task, task_dir)
        if result.task_id != task_id:
            raise ValueError(
                f"Adapter returned task_id={result.task_id!r}; expected {task_id!r}"
            )
        if result.source != source:
            raise ValueError(f"Adapter returned source={result.source!r}; expected {source!r}")
    except Exception as exc:  # fail closed at task boundary
        result = TaskResult(
            task_id=task_id,
            source=source,
            status="error",
            reward=None,
            error={"kind": type(exc).__name__, "message": str(exc)},
        )
    payload = result.to_dict()
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
) -> dict[str, Any]:
    if output_dir.exists():
        if not overwrite:
            raise FileExistsError(
                f"Output directory already exists: {output_dir}. Use --overwrite to replace it."
            )
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "tasks").mkdir()

    run_id = f"{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{uuid.uuid4().hex[:8]}"
    run_record: dict[str, Any] = {
        "schema_version": "0.1.0",
        "run_id": run_id,
        "status": "running",
        "created_at": utc_now_iso(),
        "repo_root": str(repo_root),
        "suite": {
            "id": suite.get("id"),
            "kind": suite.get("kind"),
            "task_count_requested": len(tasks),
        },
        "task_ids": [task["id"] for task in tasks],
        "adapter": adapter.describe(),
        "max_workers": max_workers,
    }
    atomic_write_json(output_dir / "run.json", run_record)

    if max_workers < 1:
        raise ValueError("max_workers must be at least 1")

    indexed_results: dict[str, dict[str, Any]] = {}
    if max_workers == 1:
        for task in tasks:
            task_id = str(task["id"])
            indexed_results[task_id] = _safe_result(
                adapter, task, output_dir / "tasks" / task_id
            )
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_task = {
                executor.submit(
                    _safe_result,
                    adapter,
                    task,
                    output_dir / "tasks" / str(task["id"]),
                ): task
                for task in tasks
            }
            for future in concurrent.futures.as_completed(future_to_task):
                task = future_to_task[future]
                task_id = str(task["id"])
                indexed_results[task_id] = future.result()

    results = [indexed_results[str(task["id"])] for task in tasks]
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
