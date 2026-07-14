from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

ALLOWED_STATUSES = {"passed", "failed", "invalid", "error", "skipped"}


@dataclass(slots=True)
class TaskResult:
    task_id: str
    source: str
    status: str
    reward: float | None
    verifier: dict[str, Any] = field(default_factory=dict)
    error: dict[str, Any] | None = None
    artifacts: dict[str, str] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if self.status not in ALLOWED_STATUSES:
            raise ValueError(f"Unsupported result status: {self.status}")
        if self.status == "passed" and self.reward is None:
            self.reward = 1.0
        if self.status == "failed" and self.reward is None:
            self.reward = 0.0
        if self.reward is not None and not 0.0 <= float(self.reward) <= 1.0:
            raise ValueError(f"Reward must be in [0, 1], got {self.reward!r}")
        if self.status in {"invalid", "error", "skipped"} and self.reward is not None:
            raise ValueError(f"{self.status} result must not have a reward")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "schema_version": "0.1.0",
            "task_id": self.task_id,
            "source": self.source,
            "status": self.status,
            "reward": self.reward,
            "verifier": self.verifier,
            "error": self.error,
            "artifacts": self.artifacts,
            "metrics": self.metrics,
            "metadata": self.metadata,
        }

    @classmethod
    def from_external(
        cls,
        payload: dict[str, Any],
        *,
        expected_task_id: str,
        source: str,
    ) -> "TaskResult":
        if not isinstance(payload, dict):
            raise ValueError("Bridge result must be a JSON object")
        raw_task_id = payload.get("task_id")
        if not isinstance(raw_task_id, str) or not raw_task_id.strip():
            raise ValueError("Bridge result must contain a non-empty string task_id")
        task_id = raw_task_id
        if task_id != expected_task_id:
            raise ValueError(
                f"Bridge returned task_id={task_id!r}; expected {expected_task_id!r}"
            )
        status = str(payload.get("status", "")).lower()
        reward = payload.get("reward")
        if reward is not None:
            reward = float(reward)
        metadata = dict(payload.get("metadata") or {})
        # External bridge output is diagnostic plumbing until a later trusted
        # evidence path validates and promotes it.  Never let bridge-authored
        # JSON promote itself into benchmark evidence.
        metadata["benchmark_reportable"] = False
        result = cls(
            task_id=task_id,
            source=source,
            status=status,
            reward=reward,
            verifier=dict(payload.get("verifier") or {}),
            error=dict(payload["error"]) if isinstance(payload.get("error"), dict) else None,
            artifacts={str(k): str(v) for k, v in dict(payload.get("artifacts") or {}).items()},
            metrics=dict(payload.get("metrics") or {}),
            metadata=metadata,
        )
        result.validate()
        return result
