from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .base import Adapter
from ..models import TaskResult


class FixtureAdapter(Adapter):
    """Deterministic synthetic adapter used only to test runner plumbing."""

    name = "fixture"
    benchmark_reportable = False

    def __init__(self, pass_rate: float = 0.55, seed: int = 0) -> None:
        if not 0.0 <= pass_rate <= 1.0:
            raise ValueError("Fixture pass rate must lie in [0, 1]")
        self.pass_rate = float(pass_rate)
        self.seed = int(seed)

    def run(self, task: dict[str, Any], task_dir: Path) -> TaskResult:
        task_id = str(task["id"])
        digest = hashlib.sha256(f"{self.seed}:{task_id}".encode("utf-8")).digest()
        value = int.from_bytes(digest, "big") / float(2 ** (8 * len(digest)))
        passed = value < self.pass_rate
        return TaskResult(
            task_id=task_id,
            source=str(task["source"]),
            status="passed" if passed else "failed",
            reward=1.0 if passed else 0.0,
            verifier={
                "kind": "synthetic_fixture",
                "valid": True,
                "detail": "Deterministic hash-based fixture; not a browser benchmark verifier.",
            },
            metrics={"fixture_value": value, "fixture_pass_rate": self.pass_rate},
            metadata={
                "synthetic": True,
                "fixture_seed": self.seed,
                "benchmark_reportable": False,
            },
        )

    def describe(self) -> dict[str, Any]:
        payload = super().describe()
        payload.update({"pass_rate": self.pass_rate, "seed": self.seed})
        return payload
