from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import Adapter, AdapterExecutionContext
from .command import CommandAdapter
from ..models import TaskResult, validate_nonempty_string, validate_task_id
from ..util import read_json


class RegistryAdapter(Adapter):
    """Dispatches tasks to source-specific external command bridges."""

    name = "registry"
    benchmark_reportable = False

    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path
        payload = read_json(config_path)
        sources = payload.get("sources") if isinstance(payload, dict) else None
        if not isinstance(sources, dict):
            raise ValueError("Registry config must contain an object named 'sources'")
        self.config = payload
        self.sources: dict[str, dict[str, Any]] = {
            str(key): dict(value) for key, value in sources.items() if isinstance(value, dict)
        }

    def run(
        self,
        task: dict[str, Any],
        task_dir: Path,
        *,
        execution_context: AdapterExecutionContext,
    ) -> TaskResult:
        task_id = validate_task_id(task.get("id"))
        source = validate_nonempty_string(task.get("source"), field_name="source")
        entry = self.sources.get(source)
        if entry is None:
            return TaskResult(
                task_id=task_id,
                source=source,
                status="invalid",
                reward=None,
                error={
                    "kind": "missing_source_bridge",
                    "message": f"No registry entry for source {source!r}",
                },
            )
        if not bool(entry.get("enabled", False)):
            return TaskResult(
                task_id=task_id,
                source=source,
                status="invalid",
                reward=None,
                error={
                    "kind": "disabled_source_bridge",
                    "message": f"Source bridge {source!r} is disabled",
                },
            )
        command = entry.get("command")
        if not isinstance(command, str) or not command.strip():
            return TaskResult(
                task_id=task_id,
                source=source,
                status="invalid",
                reward=None,
                error={
                    "kind": "missing_source_command",
                    "message": f"Source bridge {source!r} has no command",
                },
            )
        adapter = CommandAdapter(
            command,
            timeout_seconds=int(entry.get("timeout_seconds", 900)),
            extra_env={str(k): str(v) for k, v in dict(entry.get("env") or {}).items()},
            label=f"registry:{source}",
        )
        return adapter.run(task, task_dir, execution_context=execution_context)

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "benchmark_reportable": self.benchmark_reportable,
            "config_path": str(self.config_path),
            "sources": {
                source: {
                    "enabled": bool(entry.get("enabled", False)),
                    "timeout_seconds": int(entry.get("timeout_seconds", 900)),
                    "has_command": bool(str(entry.get("command", "")).strip()),
                }
                for source, entry in sorted(self.sources.items())
            },
        }
