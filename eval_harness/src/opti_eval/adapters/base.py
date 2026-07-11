from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from ..models import TaskResult


class Adapter(ABC):
    """Executes one normalized task and returns a standardized result."""

    name = "base"
    benchmark_reportable = True

    @abstractmethod
    def run(self, task: dict[str, Any], task_dir: Path) -> TaskResult:
        raise NotImplementedError

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "benchmark_reportable": self.benchmark_reportable,
        }
