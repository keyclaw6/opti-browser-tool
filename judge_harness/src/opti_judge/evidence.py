"""Evidence loading with enforced visibility contracts.

Judges consume recorded artifacts only — trace-event JSONL per
``schemas/trace-event.schema.json``, result records, and task records. This
module is the single door: every judge role loads evidence through
``load_trace``, which applies the role's evidence contract.

``restricted`` visibility (holdout material) is not loadable here at all —
there is no parameter that admits it. That is deliberate.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

ALLOWED_VISIBILITY = ("executor", "judge", "orchestrator")  # 'restricted' is structurally excluded

REQUIRED_EVENT_FIELDS = (
    "run_id",
    "event_id",
    "sequence",
    "actor",
    "event_type",
    "visibility",
    "payload",
)


class EvidenceError(ValueError):
    """Malformed evidence. Consumers must treat this as `invalid`, never `failed`."""


@dataclass(slots=True)
class EvidenceContract:
    """What one judge role may see."""

    role: str
    visibility: tuple[str, ...] = ALLOWED_VISIBILITY
    event_types: tuple[str, ...] = ()  # empty = all event types

    def __post_init__(self) -> None:
        illegal = set(self.visibility) - set(ALLOWED_VISIBILITY)
        if illegal:
            raise EvidenceError(
                f"contract for {self.role!r} requests non-loadable visibility: {sorted(illegal)}"
            )

    def admits(self, event: dict[str, Any]) -> bool:
        vis = set(event.get("visibility", []))
        # F13: ANY event bearing `restricted` is unavailable through this API,
        # regardless of co-tags. Mixed ["restricted","judge"] no longer leaks.
        if "restricted" in vis:
            return False
        if not vis & set(self.visibility):
            return False
        if self.event_types and event.get("event_type") not in self.event_types:
            return False
        return True


@dataclass(slots=True)
class Trace:
    events: list[dict[str, Any]] = field(default_factory=list)

    def of_type(self, *event_types: str) -> list[dict[str, Any]]:
        wanted = set(event_types)
        return [e for e in self.events if e.get("event_type") in wanted]

    def final_of_type(self, event_type: str) -> dict[str, Any] | None:
        rows = self.of_type(event_type)
        return rows[-1] if rows else None


def _drop_restricted_artifacts(event: dict[str, Any]) -> list[dict[str, Any]]:
    """Redact any artifact_ref tagged restricted (F13): a judge-visible event
    must not carry a pointer to holdout/restricted evidence."""
    kept: list[dict[str, Any]] = []
    for ref in event.get("artifact_refs", []) or []:
        vis = set(ref.get("visibility", []) or [])
        if "restricted" in vis:
            continue
        kept.append(ref)
    return kept


def _validate_event(event: dict[str, Any], line_number: int) -> None:
    for fieldname in REQUIRED_EVENT_FIELDS:
        if fieldname not in event:
            raise EvidenceError(
                f"trace event on line {line_number} is missing {fieldname!r}"
            )
    if not isinstance(event["visibility"], list) or not event["visibility"]:
        raise EvidenceError(f"trace event on line {line_number} has no visibility tags")


def load_trace(path: Path, contract: EvidenceContract) -> Trace:
    """Load a trace JSONL under a role's evidence contract.

    Raises ``EvidenceError`` on malformed input — per the probe kit, malformed
    evidence must classify as `invalid`, never as a task failure.
    """
    if not path.is_file():
        raise EvidenceError(f"trace not found: {path}")
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise EvidenceError(f"trace line {line_number} is not valid JSON: {exc}") from exc
        _validate_event(event, line_number)
        # Any event carrying `restricted` (even co-tagged) is dropped entirely.
        if contract.admits(event):
            events.append({**event, "artifact_refs": _drop_restricted_artifacts(event)})
    events.sort(key=lambda e: (int(e.get("sequence", 0)), str(e.get("event_id"))))
    return Trace(events=events)


def event_refs(events: Iterable[dict[str, Any]]) -> list[str]:
    """Compact run_id/event_id citations for flag records."""
    return [f"{e.get('run_id')}/{e.get('event_id')}" for e in events]
