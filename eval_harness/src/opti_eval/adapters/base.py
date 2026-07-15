from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..models import TaskResult


@dataclass(frozen=True, slots=True)
class AdapterExecutionContext:
    """Minimal runner-owned identifiers exposed to an adapter."""

    run_id: str
    run_context_digest: str


class Adapter(ABC):
    """Executes one normalized task and returns a standardized result."""

    name = "base"
    benchmark_reportable = False

    @abstractmethod
    def run(
        self,
        task: dict[str, Any],
        task_dir: Path,
        *,
        execution_context: AdapterExecutionContext,
    ) -> TaskResult:
        raise NotImplementedError

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "benchmark_reportable": self.benchmark_reportable,
        }
