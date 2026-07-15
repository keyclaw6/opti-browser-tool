"""Strict trace and task-bundle loading with visibility enforcement.

This module is the single dependency-free evidence boundary used by judges and
benchmark eligibility.  It validates the canonical event stream in file order,
then applies the caller's visibility contract.  ``load_task_bundle`` adds the
result/trace/artifact linkage required before an otherwise reportable task may
influence a benchmark decision.

``restricted`` visibility (holdout material) is not loadable through the public
trace API.  Restricted events and artifact pointers are validated structurally
inside a bundle, but are never returned to consumers.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import math
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from opti_eval.models import (
    PERSISTED_RESULT_FIELDS,
    canonical_json,
    split_lf_jsonl_records,
    strict_json_loads,
    validate_nonempty_string,
    validate_persisted_result,
    validate_rfc3339,
    validate_standard_json,
    validate_task_id,
)

TRACE_SCHEMA_VERSION = "0.1-draft"
ALLOWED_VISIBILITY = ("executor", "judge", "orchestrator")
ALL_VISIBILITY = set(ALLOWED_VISIBILITY) | {"restricted"}
ALLOWED_ACTORS = {
    "executor",
    "browser",
    "tool",
    "orchestrator",
    "verifier",
    "judge",
    "infrastructure",
}
ALLOWED_EVENT_TYPES = {
    "model_observation",
    "model_response",
    "action_requested",
    "action_result",
    "browser_state",
    "browser_event",
    "page_transition",
    "tab_event",
    "network_event",
    "console_event",
    "artifact_created",
    "verifier_result",
    "judge_result",
    "error",
    "metric",
    "checkpoint",
}
EPOCH_EVENT_TYPES = {
    "model_observation",
    "action_requested",
    "action_result",
    "browser_state",
    "browser_event",
    "page_transition",
    "tab_event",
}
REQUIRED_EVENT_FIELDS = {
    "schema_version",
    "run_id",
    "task_id",
    "event_id",
    "sequence",
    "timestamp",
    "monotonic_ms",
    "actor",
    "event_type",
    "visibility",
    "payload",
    "artifact_refs",
}
OPTIONAL_EVENT_FIELDS = {
    "parent_event_id",
    "browser_state_epoch",
    "redaction",
}
ARTIFACT_FIELDS = {"kind", "uri", "sha256", "media_type", "visibility"}
RESULT_FIELDS = PERSISTED_RESULT_FIELDS


class EvidenceError(ValueError):
    """Malformed evidence. Consumers must classify it as invalid, never failed."""


@dataclass(slots=True)
class EvidenceContract:
    """What one judge role may see."""

    role: str
    visibility: tuple[str, ...] = ALLOWED_VISIBILITY
    event_types: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        illegal = set(self.visibility) - set(ALLOWED_VISIBILITY)
        if illegal:
            raise EvidenceError(
                f"contract for {self.role!r} requests non-loadable visibility: {sorted(illegal)}"
            )

    def admits(self, event: dict[str, Any]) -> bool:
        visibility = set(event["visibility"])
        if "restricted" in visibility:
            return False
        if not visibility & set(self.visibility):
            return False
        if self.event_types and event["event_type"] not in self.event_types:
            return False
        return True


@dataclass(slots=True)
class Trace:
    events: list[dict[str, Any]] = field(default_factory=list)

    def of_type(self, *event_types: str) -> list[dict[str, Any]]:
        wanted = set(event_types)
        return [event for event in self.events if event.get("event_type") in wanted]

    def final_of_type(self, event_type: str) -> dict[str, Any] | None:
        rows = self.of_type(event_type)
        return rows[-1] if rows else None


@dataclass(slots=True)
class TaskBundle:
    result: dict[str, Any]
    trace: Trace


@dataclass(slots=True)
class _TraceInfo:
    run_id: str
    task_id: str
    last_event: dict[str, Any]
    artifact_refs: list[dict[str, Any]]
    verifier_results: list[dict[str, Any]]
    final_state: dict[str, Any] | None


def validate_json_value(value: object, *, label: str = "value") -> None:
    """Reject non-JSON Python values and non-finite numbers recursively."""
    try:
        validate_standard_json(value, field_name=label)
    except ValueError as exc:
        raise EvidenceError(str(exc)) from exc


def _nonempty_string(value: object, *, label: str) -> str:
    try:
        return validate_nonempty_string(value, field_name=label)
    except ValueError as exc:
        raise EvidenceError(str(exc)) from exc


def _relative_uri(value: object, *, label: str) -> str:
    uri = _nonempty_string(value, label=label)
    if "\x00" in uri or "\\" in uri:
        raise EvidenceError(f"{label} must be a safe relative POSIX path")
    path = PurePosixPath(uri)
    if (
        path.is_absolute()
        or not path.parts
        or path.as_posix() != uri
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise EvidenceError(f"{label} must be a safe relative POSIX path")
    return uri


def _visibility(value: object, *, label: str) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, str) for item in value)
        or len(set(value)) != len(value)
        or set(value) - ALL_VISIBILITY
    ):
        raise EvidenceError(f"{label} must be a non-empty unique allowed-tag array")
    return list(value)


def _artifact_ref_shape(value: object, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EvidenceError(f"{label} must be an object")
    if set(value) != ARTIFACT_FIELDS:
        raise EvidenceError(
            f"{label} fields must be exactly: {', '.join(sorted(ARTIFACT_FIELDS))}"
        )
    kind = _nonempty_string(value.get("kind"), label=f"{label} kind")
    uri = _relative_uri(value.get("uri"), label=f"{label} uri")
    digest = value.get("sha256")
    if (
        not isinstance(digest, str)
        or len(digest) != 64
        or any(char not in "0123456789abcdef" for char in digest)
    ):
        raise EvidenceError(f"{label} sha256 must be 64 lowercase hexadecimal characters")
    media_type = _nonempty_string(value.get("media_type"), label=f"{label} media_type")
    visibility = _visibility(value.get("visibility"), label=f"{label} visibility")
    return {
        "kind": kind,
        "uri": uri,
        "sha256": digest,
        "media_type": media_type,
        "visibility": visibility,
    }


def _timestamp(value: object, *, line_number: int) -> _dt.datetime:
    try:
        text = validate_rfc3339(
            value, field_name=f"trace line {line_number} timestamp"
        )
    except ValueError as exc:
        raise EvidenceError(str(exc)) from exc
    return _dt.datetime.fromisoformat(text.replace("Z", "+00:00"))


def _validate_event(event: object, line_number: int) -> dict[str, Any]:
    label = f"trace event on line {line_number}"
    if not isinstance(event, dict):
        raise EvidenceError(f"{label} must be an object")
    validate_json_value(event, label=label)
    missing = REQUIRED_EVENT_FIELDS - set(event)
    if missing:
        raise EvidenceError(f"{label} is missing {', '.join(sorted(missing))}")
    extra = set(event) - REQUIRED_EVENT_FIELDS - OPTIONAL_EVENT_FIELDS
    if extra:
        raise EvidenceError(f"{label} has unsupported fields: {', '.join(sorted(extra))}")
    if event.get("schema_version") != TRACE_SCHEMA_VERSION:
        raise EvidenceError(f"{label} has unsupported schema_version")
    for key in ("run_id", "event_id"):
        _nonempty_string(event.get(key), label=f"{label} {key}")
    try:
        validate_task_id(event.get("task_id"), field_name=f"{label} task_id")
    except ValueError as exc:
        raise EvidenceError(str(exc)) from exc

    sequence = event.get("sequence")
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
        raise EvidenceError(f"{label} sequence must be a non-negative integer")
    monotonic_ms = event.get("monotonic_ms")
    if (
        isinstance(monotonic_ms, bool)
        or not isinstance(monotonic_ms, (int, float))
        or not math.isfinite(monotonic_ms)
        or monotonic_ms < 0
    ):
        raise EvidenceError(f"{label} monotonic_ms must be a finite non-negative number")
    _timestamp(event.get("timestamp"), line_number=line_number)

    if event.get("actor") not in ALLOWED_ACTORS:
        raise EvidenceError(f"{label} actor is not allowed")
    if event.get("event_type") not in ALLOWED_EVENT_TYPES:
        raise EvidenceError(f"{label} event_type is not allowed")
    _visibility(event.get("visibility"), label=f"{label} visibility")
    if not isinstance(event.get("payload"), dict):
        raise EvidenceError(f"{label} payload must be an object")
    if event.get("event_type") == "verifier_result":
        if event.get("actor") != "verifier":
            raise EvidenceError(f"{label} verifier_result must be verifier-owned")
        payload = event["payload"]
        if payload.get("status") not in {
            "passed",
            "failed",
            "invalid",
            "error",
            "skipped",
        }:
            raise EvidenceError(f"{label} verifier_result status is not recognized")
        _nonempty_string(
            payload.get("verifier_id"), label=f"{label} verifier_id"
        )
        _nonempty_string(
            payload.get("verifier_checksum"), label=f"{label} verifier_checksum"
        )
    refs = event.get("artifact_refs")
    if not isinstance(refs, list):
        raise EvidenceError(f"{label} artifact_refs must be an array")
    event["artifact_refs"] = [
        _artifact_ref_shape(ref, label=f"{label} artifact_refs[{index}]")
        for index, ref in enumerate(refs)
    ]

    parent = event.get("parent_event_id")
    if parent is not None:
        _nonempty_string(parent, label=f"{label} parent_event_id")
    epoch = event.get("browser_state_epoch")
    if event.get("event_type") in EPOCH_EVENT_TYPES and (
        isinstance(epoch, bool) or not isinstance(epoch, int) or epoch < 0
    ):
        raise EvidenceError(
            f"{label} browser_state_epoch is required for observation/action events"
        )
    if event.get("event_type") not in EPOCH_EVENT_TYPES and epoch is not None and (
        isinstance(epoch, bool) or not isinstance(epoch, int) or epoch < 0
    ):
        raise EvidenceError(f"{label} browser_state_epoch must be null or non-negative integer")
    if "redaction" in event and not isinstance(event["redaction"], dict):
        raise EvidenceError(f"{label} redaction must be an object")
    return event


def _filtered_event(
    event: dict[str, Any], contract: EvidenceContract
) -> dict[str, Any]:
    allowed = set(contract.visibility)
    refs = [
        ref
        for ref in event["artifact_refs"]
        if "restricted" not in ref["visibility"]
        and bool(set(ref["visibility"]) & allowed)
    ]
    return {**event, "artifact_refs": refs}


def _parse_trace_text(
    text: str,
    *,
    source: str,
    contract: EvidenceContract,
) -> tuple[Trace, _TraceInfo]:
    raw_events: list[dict[str, Any]] = []
    artifact_refs: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    trace_run_id: str | None = None
    trace_task_id: str | None = None
    previous_sequence: int | None = None
    previous_monotonic: float | None = None
    previous_timestamp: _dt.datetime | None = None
    previous_epoch: int | None = None
    verifier_results: list[dict[str, Any]] = []

    try:
        records = split_lf_jsonl_records(text, field_name=source)
    except ValueError as exc:
        raise EvidenceError(str(exc)) from exc
    for line_number, line in enumerate(records, start=1):
        try:
            decoded = strict_json_loads(
                line, field_name=f"{source} line {line_number}"
            )
        except ValueError as exc:
            raise EvidenceError(f"{source} line {line_number} is not valid JSON: {exc}") from exc
        event = _validate_event(decoded, line_number)
        event_id = event["event_id"]
        if event_id in seen_ids:
            raise EvidenceError(f"{source} line {line_number} duplicates event_id {event_id!r}")
        if previous_sequence is not None and event["sequence"] != previous_sequence + 1:
            raise EvidenceError(
                f"{source} line {line_number} sequence must be consecutive in file order"
            )
        if previous_monotonic is not None and event["monotonic_ms"] < previous_monotonic:
            raise EvidenceError(
                f"{source} line {line_number} monotonic_ms decreases in file order"
            )
        timestamp = _timestamp(event["timestamp"], line_number=line_number)
        if previous_timestamp is not None and timestamp < previous_timestamp:
            raise EvidenceError(
                f"{source} line {line_number} timestamp decreases in file order"
            )
        epoch = event.get("browser_state_epoch")
        if epoch is not None:
            if previous_epoch is not None and epoch < previous_epoch:
                raise EvidenceError(
                    f"{source} line {line_number} browser_state_epoch decreases in file order"
                )
            previous_epoch = epoch
        parent = event.get("parent_event_id")
        if parent is not None and parent not in seen_ids:
            raise EvidenceError(
                f"{source} line {line_number} parent_event_id must reference an earlier event"
            )
        if trace_run_id is None:
            trace_run_id = event["run_id"]
            trace_task_id = event["task_id"]
        elif event["run_id"] != trace_run_id or event["task_id"] != trace_task_id:
            raise EvidenceError(f"{source} mixes run_id or task_id values")

        seen_ids.add(event_id)
        previous_sequence = event["sequence"]
        previous_monotonic = float(event["monotonic_ms"])
        previous_timestamp = timestamp
        artifact_refs.extend(event["artifact_refs"])
        if event["event_type"] == "verifier_result":
            verifier_results.append(event)
        raw_events.append(event)

    if not raw_events:
        raise EvidenceError(f"{source} must contain at least one trace event")
    visible = [
        _filtered_event(event, contract)
        for event in raw_events
        if contract.admits(event)
    ]
    return (
        Trace(events=visible),
        _TraceInfo(
            run_id=str(trace_run_id),
            task_id=str(trace_task_id),
            last_event=raw_events[-1],
            artifact_refs=artifact_refs,
            verifier_results=verifier_results,
            final_state=next(
                (
                    event
                    for event in reversed(raw_events)
                    if event["event_type"] == "browser_state"
                ),
                None,
            ),
        ),
    )


def load_trace(path: Path, contract: EvidenceContract) -> Trace:
    """Load a strict trace under a role's visibility contract, preserving file order."""
    if not path.is_file():
        raise EvidenceError(f"trace not found: {path}")
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            text = handle.read()
    except (OSError, UnicodeError) as exc:
        raise EvidenceError(f"trace is unreadable: {path}: {exc}") from exc
    return _parse_trace_text(text, source=str(path), contract=contract)[0]


def _regular_file(root: Path, uri: str, *, label: str) -> Path:
    if not root.is_dir() or root.is_symlink():
        raise EvidenceError(f"{label} evidence root must be a real directory")
    current = root
    for part in PurePosixPath(uri).parts:
        current = current / part
        try:
            mode = os.lstat(current).st_mode
        except OSError as exc:
            raise EvidenceError(f"{label} does not exist: {uri}") from exc
        if stat.S_ISLNK(mode):
            raise EvidenceError(f"{label} must not traverse a symlink: {uri}")
    if not stat.S_ISREG(mode):
        raise EvidenceError(f"{label} must reference a regular file: {uri}")
    resolved_root = root.resolve()
    resolved = current.resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise EvidenceError(f"{label} escapes the task evidence root: {uri}")
    return current


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise EvidenceError(f"artifact became unreadable: {path}") from exc
    return digest.hexdigest()


def _validate_result(
    value: object,
    *,
    expected_run_id: str,
    expected_task_id: str,
    expected_source: str,
    expected_status: str,
    expected_verifier_id: str,
    expected_verifier_checksum: str,
) -> dict[str, Any]:
    try:
        return validate_persisted_result(
            value,
            expected_run_id=expected_run_id,
            expected_task_id=expected_task_id,
            expected_source=expected_source,
            expected_status=expected_status,
            expected_verifier_id=expected_verifier_id,
            expected_verifier_checksum=expected_verifier_checksum,
            terminal_only=True,
        )
    except ValueError as exc:
        raise EvidenceError(str(exc)) from exc


def load_task_bundle(
    *,
    task_root: Path,
    expected_run_id: str,
    expected_task_id: str,
    expected_source: str,
    expected_status: str,
    expected_result: dict[str, Any],
    expected_verifier_id: str,
    expected_verifier_checksum: str,
    contract: EvidenceContract,
) -> TaskBundle:
    """Validate and load one terminal result/trace/artifact bundle.

    The trusted caller supplies the runner-owned run ID, scheduled task ID,
    terminal status, and the exact aggregate result row.  The task-local
    ``result.json`` must be byte-semantically identical to that aggregate row.
    All referenced files stay inside ``task_root`` and are hash checked before
    the trace can reach T1.
    """
    result_path = _regular_file(task_root, "result.json", label="task result")
    try:
        raw_result = strict_json_loads(
            result_path.read_text(encoding="utf-8"),
            field_name="persisted task result",
        )
    except (OSError, UnicodeError, ValueError) as exc:
        raise EvidenceError(f"persisted task result is unreadable: {exc}") from exc
    aggregate = _validate_result(
        expected_result,
        expected_run_id=expected_run_id,
        expected_task_id=expected_task_id,
        expected_source=expected_source,
        expected_status=expected_status,
        expected_verifier_id=expected_verifier_id,
        expected_verifier_checksum=expected_verifier_checksum,
    )
    result = _validate_result(
        raw_result,
        expected_run_id=expected_run_id,
        expected_task_id=expected_task_id,
        expected_source=expected_source,
        expected_status=expected_status,
        expected_verifier_id=expected_verifier_id,
        expected_verifier_checksum=expected_verifier_checksum,
    )
    if canonical_json(result) != canonical_json(aggregate):
        raise EvidenceError("task result.json does not match its results.jsonl row")

    by_uri: dict[str, dict[str, Any]] = {}
    paths: dict[str, Path] = {}
    for ref in result["artifacts"]:
        uri = ref["uri"]
        if uri in by_uri:
            raise EvidenceError(f"task result declares duplicate artifact uri {uri!r}")
        path = _regular_file(task_root, uri, label="artifact")
        if _sha256(path) != ref["sha256"]:
            raise EvidenceError(f"artifact sha256 mismatch: {uri}")
        by_uri[uri] = ref
        paths[uri] = path

    trace_path = result["trace_path"]
    trace_ref = by_uri.get(trace_path)
    if trace_ref is None or trace_ref["kind"] != "trace":
        raise EvidenceError("trace_path must name one declared artifact of kind 'trace'")
    if (
        "restricted" in trace_ref["visibility"]
        or not set(trace_ref["visibility"]) & set(contract.visibility)
    ):
        raise EvidenceError("trace artifact is not visible to the T1 evidence contract")
    trace_file = paths[trace_path]
    try:
        trace_bytes = trace_file.read_bytes()
    except OSError as exc:
        raise EvidenceError(f"trace became unreadable: {trace_path}") from exc
    if hashlib.sha256(trace_bytes).hexdigest() != trace_ref["sha256"]:
        raise EvidenceError(f"trace sha256 mismatch: {trace_path}")
    try:
        trace_text = trace_bytes.decode("utf-8")
    except UnicodeError as exc:
        raise EvidenceError(f"trace is not UTF-8: {trace_path}") from exc
    trace, info = _parse_trace_text(trace_text, source=trace_path, contract=contract)

    if info.run_id != expected_run_id or info.task_id != expected_task_id:
        raise EvidenceError("trace run_id/task_id does not match the trusted result")
    if not trace.events:
        raise EvidenceError("trace has no events visible to the T1 evidence contract")
    if len(info.verifier_results) != 1:
        raise EvidenceError("trace must contain exactly one verifier_result event")
    terminal = info.verifier_results[0]
    if terminal["event_id"] != info.last_event["event_id"]:
        raise EvidenceError("the sole verifier_result event must be the final trace event")
    if not contract.admits(terminal):
        raise EvidenceError("terminal verifier event is not visible to T1")
    if terminal["event_type"] != "verifier_result" or terminal["actor"] != "verifier":
        raise EvidenceError("trace must end with a verifier-owned verifier_result event")
    if terminal["payload"].get("status") != expected_status:
        raise EvidenceError("terminal verifier event outcome does not match task result status")
    if terminal["payload"].get("verifier_id") != expected_verifier_id:
        raise EvidenceError("terminal verifier id does not match the pinned verifier")
    if terminal["payload"].get("verifier_checksum") != expected_verifier_checksum:
        raise EvidenceError("terminal verifier checksum does not match the pinned verifier")
    if info.final_state is None:
        raise EvidenceError("trace must contain canonical browser_state final-state evidence")
    if info.final_state["sequence"] != terminal["sequence"] - 1:
        raise EvidenceError(
            "canonical browser_state final-state evidence must immediately precede "
            "the verifier result"
        )
    if not contract.admits(info.final_state):
        raise EvidenceError("browser_state final-state evidence is not visible to T1")

    for ref in info.artifact_refs:
        declared = by_uri.get(ref["uri"])
        if declared is None:
            raise EvidenceError(
                f"trace event references undeclared artifact uri {ref['uri']!r}"
            )
        if ref != declared:
            raise EvidenceError(
                f"trace artifact reference does not match result declaration: {ref['uri']}"
            )
    visible_result = {
        **result,
        "artifacts": [
            ref
            for ref in result["artifacts"]
            if "restricted" not in ref["visibility"]
            and bool(set(ref["visibility"]) & set(contract.visibility))
        ],
    }
    return TaskBundle(result=visible_result, trace=trace)


def event_refs(events: Iterable[dict[str, Any]]) -> list[str]:
    """Compact run_id/event_id citations for flag records."""
    return [f"{event.get('run_id')}/{event.get('event_id')}" for event in events]
