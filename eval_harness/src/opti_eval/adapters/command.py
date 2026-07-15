from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from .base import Adapter, AdapterExecutionContext
from ..models import (
    TaskResult,
    artifact_ref,
    validate_nonempty_string,
    validate_task_id,
)
from ..util import atomic_write_json, read_json


class CommandAdapter(Adapter):
    """Runs an external benchmark bridge using a format-string command."""

    name = "command"
    benchmark_reportable = False

    def __init__(
        self,
        command_template: str,
        *,
        timeout_seconds: int = 900,
        extra_env: dict[str, str] | None = None,
        label: str | None = None,
    ) -> None:
        if not command_template.strip():
            raise ValueError("Command template must not be empty")
        self.command_template = command_template
        self.timeout_seconds = int(timeout_seconds)
        self.extra_env = dict(extra_env or {})
        self.label = label or self.name

    def run(
        self,
        task: dict[str, Any],
        task_dir: Path,
        *,
        execution_context: AdapterExecutionContext,
    ) -> TaskResult:
        run_id = execution_context.run_id
        task_id = validate_task_id(task.get("id"))
        source = validate_nonempty_string(task.get("source"), field_name="source")
        task_path = task_dir / "task.json"
        bridge_result_path = task_dir / "bridge-result.json"
        stdout_path = task_dir / "stdout.log"
        stderr_path = task_dir / "stderr.log"
        atomic_write_json(task_path, task)

        substitutions = {
            "task_json": str(task_path.resolve()),
            "result_json": str(bridge_result_path.resolve()),
            "task_id": task_id,
            "source": source,
            "output_dir": str(task_dir.resolve()),
        }
        try:
            command = self.command_template.format(**substitutions)
        except KeyError as exc:
            return TaskResult(
                task_id=task_id,
                source=source,
                status="invalid",
                reward=None,
                error={
                    "kind": "command_template_error",
                    "message": f"Unknown command placeholder: {exc}",
                },
            )

        env = os.environ.copy()
        env.update(self.extra_env)
        env.update(
            {
                "OPTI_TASK_ID": task_id,
                "OPTI_RUN_ID": run_id,
                "OPTI_TASK_JSON": substitutions["task_json"],
                "OPTI_RESULT_JSON": substitutions["result_json"],
                "OPTI_TASK_OUTPUT_DIR": substitutions["output_dir"],
                "OPTI_RUN_CONTEXT_DIGEST": execution_context.run_context_digest,
            }
        )
        started = time.monotonic()
        try:
            completed = subprocess.run(
                command,
                shell=True,
                executable="/bin/bash",
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                env=env,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            stdout_path.write_text(exc.stdout or "", encoding="utf-8")
            stderr_path.write_text(exc.stderr or "", encoding="utf-8")
            return TaskResult(
                task_id=task_id,
                source=source,
                status="error",
                reward=None,
                error={
                    "kind": "bridge_timeout",
                    "message": f"Bridge exceeded {self.timeout_seconds}s timeout",
                },
                metrics={"elapsed_seconds": time.monotonic() - started},
            )

        stdout_path.write_text(completed.stdout, encoding="utf-8")
        stderr_path.write_text(completed.stderr, encoding="utf-8")
        elapsed = time.monotonic() - started
        if completed.returncode != 0:
            return TaskResult(
                task_id=task_id,
                source=source,
                status="error",
                reward=None,
                error={
                    "kind": "bridge_process_error",
                    "message": f"Bridge exited with code {completed.returncode}",
                },
                artifacts=self._diagnostic_refs(task_dir, stdout_path, stderr_path),
                metrics={"elapsed_seconds": elapsed, "returncode": completed.returncode},
            )
        if not bridge_result_path.is_file():
            return TaskResult(
                task_id=task_id,
                source=source,
                status="invalid",
                reward=None,
                error={
                    "kind": "missing_bridge_result",
                    "message": f"Bridge did not write {bridge_result_path.name}",
                },
                artifacts=self._diagnostic_refs(task_dir, stdout_path, stderr_path),
                metrics={"elapsed_seconds": elapsed, "returncode": completed.returncode},
            )
        try:
            payload = read_json(bridge_result_path)
            result = TaskResult.from_external(
                payload,
                expected_task_id=task_id,
                source=source,
            )
        except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
            return TaskResult(
                task_id=task_id,
                source=source,
                status="invalid",
                reward=None,
                error={"kind": "malformed_bridge_result", "message": str(exc)},
                artifacts=self._diagnostic_refs(
                    task_dir, bridge_result_path, stdout_path, stderr_path
                ),
                metrics={"elapsed_seconds": elapsed, "returncode": completed.returncode},
            )
        for ref in self._diagnostic_refs(
            task_dir, bridge_result_path, stdout_path, stderr_path
        ):
            result.artifacts = [
                existing
                for existing in result.artifacts
                if existing.get("uri") != ref["uri"]
            ]
            result.artifacts.append(ref)
        result.metrics.setdefault("elapsed_seconds", elapsed)
        result.metrics.setdefault("returncode", completed.returncode)
        result.metadata.setdefault("bridge_label", self.label)
        return result

    @staticmethod
    def _diagnostic_refs(task_dir: Path, *paths: Path) -> list[dict[str, Any]]:
        kinds = {
            "bridge-result.json": ("bridge_result", "application/json"),
            "stdout.log": ("stdout", "text/plain"),
            "stderr.log": ("stderr", "text/plain"),
        }
        refs: list[dict[str, Any]] = []
        for path in paths:
            if not path.is_file():
                continue
            kind, media_type = kinds[path.name]
            refs.append(
                artifact_ref(
                    path,
                    evidence_root=task_dir,
                    kind=kind,
                    media_type=media_type,
                )
            )
        return refs

    def describe(self) -> dict[str, Any]:
        payload = super().describe()
        payload.update(
            {
                "label": self.label,
                "timeout_seconds": self.timeout_seconds,
                "command_template": self.command_template,
                "extra_env_keys": sorted(self.extra_env),
            }
        )
        return payload
