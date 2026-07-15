from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

ALLOWED_STATUSES = {"passed", "failed", "invalid", "error", "skipped"}
ALLOWED_ARTIFACT_VISIBILITY = {"executor", "judge", "orchestrator", "restricted"}
TASK_ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]{0,94}")
RFC3339_PATTERN = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})"
)
# Explicit union of Python and ECMA-262 edge whitespace, plus U+0085 NEL.
# U+FEFF BOM is deliberately classified as edge whitespace and rejected.
EDGE_WHITESPACE_SCHEMA_CLASS = (
    r"\u0009-\u000D\u001C-\u0020\u0085\u00A0\u1680"
    r"\u2000-\u200A\u2028\u2029\u202F\u205F\u3000\uFEFF"
)
EDGE_WHITESPACE_CHARS = frozenset(
    chr(codepoint)
    for start, end in (
        (0x0009, 0x000D),
        (0x001C, 0x0020),
        (0x0085, 0x0085),
        (0x00A0, 0x00A0),
        (0x1680, 0x1680),
        (0x2000, 0x200A),
        (0x2028, 0x2029),
        (0x202F, 0x202F),
        (0x205F, 0x205F),
        (0x3000, 0x3000),
        (0xFEFF, 0xFEFF),
    )
    for codepoint in range(start, end + 1)
)
PERSISTED_RESULT_FIELDS = {
    "schema_version",
    "run_id",
    "task_id",
    "source",
    "status",
    "reward",
    "verifier",
    "error",
    "trace_path",
    "artifacts",
    "metrics",
    "metadata",
    "timing",
}
TIMING_FIELDS = {"started_at", "finished_at", "elapsed_seconds"}


def validate_task_id(value: object, *, field_name: str = "task_id") -> str:
    """Return one non-coerced portable task ID safe for a path component."""
    if type(value) is not str or TASK_ID_PATTERN.fullmatch(value) is None:
        raise ValueError(
            f"{field_name} must match ^[a-z0-9][a-z0-9_-]*$ and be at most 95 characters"
        )
    return value


def validate_nonempty_string(value: object, *, field_name: str) -> str:
    if (
        type(value) is not str
        or not value
        or has_edge_whitespace(value)
    ):
        raise ValueError(f"{field_name} must be a non-empty string without edge whitespace")
    return value


def has_edge_whitespace(value: str) -> bool:
    """Whether a nonempty string starts or ends in the shared explicit class."""
    return bool(value) and (
        value[0] in EDGE_WHITESPACE_CHARS or value[-1] in EDGE_WHITESPACE_CHARS
    )


def validate_relative_uri(value: object, *, field_name: str) -> str:
    if type(value) is not str or not value or has_edge_whitespace(value):
        raise ValueError(f"{field_name} must be a non-empty relative POSIX path")
    if "\x00" in value or "\\" in value:
        raise ValueError(f"{field_name} must be a safe relative POSIX path")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or not path.parts
        or path.as_posix() != value
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError(f"{field_name} must be a safe relative POSIX path")
    return value


def validate_rfc3339(value: object, *, field_name: str) -> str:
    text = validate_nonempty_string(value, field_name=field_name)
    if RFC3339_PATTERN.fullmatch(text) is None:
        raise ValueError(f"{field_name} must be an RFC 3339 date-time")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an RFC 3339 date-time") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field_name} must include a timezone")
    return text


def canonical_json(value: object) -> str:
    """Canonical comparison form that preserves JSON scalar types."""
    validate_standard_json(value)
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"value is not canonical JSON: {exc}") from exc


def validate_standard_json(value: object, *, field_name: str = "value") -> None:
    """Require the finite, non-coerced data model defined by standard JSON."""
    if value is None or type(value) in {str, bool, int}:
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError(f"{field_name} contains a non-finite JSON number")
        return
    if type(value) is list:
        for index, item in enumerate(value):
            validate_standard_json(item, field_name=f"{field_name}[{index}]")
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise ValueError(f"{field_name} contains a non-string object key")
            validate_standard_json(item, field_name=f"{field_name}.{key}")
        return
    raise ValueError(
        f"{field_name} contains non-JSON value type {type(value).__name__}"
    )


def strict_json_loads(text: str, *, field_name: str = "JSON") -> object:
    """Parse standard JSON while rejecting constants and duplicate object keys."""

    def reject_constant(token: str) -> None:
        raise ValueError(f"{field_name} contains non-JSON numeric constant {token}")

    def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
        value: dict[str, object] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"{field_name} contains duplicate object key {key!r}")
            value[key] = item
        return value

    parsed = json.loads(
        text,
        parse_constant=reject_constant,
        object_pairs_hook=reject_duplicate_keys,
    )
    validate_standard_json(parsed, field_name=field_name)
    return parsed


def split_lf_jsonl_records(text: str, *, field_name: str) -> list[str]:
    """Split JSONL only on LF, accepting LF, CRLF, or no final delimiter.

    One terminal CR is removed from each LF-delimited physical record. Raw CR
    elsewhere is rejected. Empty and edge-whitespace-only physical records are
    never skipped, including extra trailing delimiters.
    """
    if type(text) is not str:
        raise ValueError(f"{field_name} must be decoded text")
    has_final_lf = text.endswith("\n")
    physical = text.split("\n")
    if has_final_lf:
        physical.pop()
    if not physical:
        raise ValueError(f"{field_name} must contain at least one JSON record")
    records: list[str] = []
    for line_number, raw_record in enumerate(physical, start=1):
        lf_delimited = line_number < len(physical) or has_final_lf
        record = (
            raw_record[:-1]
            if lf_delimited and raw_record.endswith("\r")
            else raw_record
        )
        if "\r" in record:
            raise ValueError(
                f"{field_name} record {line_number} contains a non-CRLF carriage return"
            )
        if not record or all(char in EDGE_WHITESPACE_CHARS for char in record):
            raise ValueError(
                f"{field_name} record {line_number} is blank or whitespace-only"
            )
        records.append(record)
    return records


def validate_artifact_ref_shape(ref: object) -> dict[str, Any]:
    """Validate the dependency-free artifact-reference structure.

    File containment and hash verification happen at the shared evidence
    boundary.  The evaluation runner only guarantees that it persists the same
    closed structure declared by the schemas.
    """
    if not isinstance(ref, dict):
        raise ValueError("artifact reference must be an object")
    required = {"kind", "uri", "sha256", "media_type", "visibility"}
    if set(ref) != required:
        raise ValueError(
            "artifact reference fields must be exactly: " + ", ".join(sorted(required))
        )
    kind = validate_nonempty_string(ref.get("kind"), field_name="artifact kind")
    media_type = validate_nonempty_string(
        ref.get("media_type"), field_name="artifact media_type"
    )
    digest = ref.get("sha256")
    visibility = ref.get("visibility")
    uri = validate_relative_uri(ref.get("uri"), field_name="artifact uri")
    if (
        not isinstance(digest, str)
        or len(digest) != 64
        or any(ch not in "0123456789abcdef" for ch in digest)
    ):
        raise ValueError("artifact sha256 must be 64 lowercase hexadecimal characters")
    if (
        not isinstance(visibility, list)
        or not visibility
        or any(not isinstance(item, str) for item in visibility)
        or len(set(visibility)) != len(visibility)
        or set(visibility) - ALLOWED_ARTIFACT_VISIBILITY
    ):
        raise ValueError("artifact visibility must be a non-empty unique allowed-tag array")
    return {
        "kind": kind,
        "uri": uri,
        "sha256": digest,
        "media_type": media_type,
        "visibility": list(visibility),
    }


def validate_persisted_result(
    value: object,
    *,
    expected_run_id: str | None = None,
    expected_task_id: str | None = None,
    expected_source: str | None = None,
    expected_status: str | None = None,
    expected_verifier_id: str | None = None,
    expected_verifier_checksum: str | None = None,
    terminal_only: bool = False,
) -> dict[str, Any]:
    """Validate the closed persisted-result contract without JSON Schema.

    The same validator is used for aggregate replay and task-local benchmark
    evidence, so Python's ``True == 1`` behavior can never mask a forged row.
    """
    if not isinstance(value, dict):
        raise ValueError("persisted task result must be an object")
    if set(value) != PERSISTED_RESULT_FIELDS:
        missing = sorted(PERSISTED_RESULT_FIELDS - set(value))
        extra = sorted(set(value) - PERSISTED_RESULT_FIELDS)
        raise ValueError(
            f"persisted task result fields mismatch; missing={missing}, unsupported={extra}"
        )
    if value.get("schema_version") != "0.1.0":
        raise ValueError("persisted task result has unsupported schema_version")
    run_id = validate_nonempty_string(value.get("run_id"), field_name="result run_id")
    task_id = validate_task_id(value.get("task_id"), field_name="result task_id")
    source = validate_nonempty_string(value.get("source"), field_name="result source")
    if expected_run_id is not None and run_id != expected_run_id:
        raise ValueError("persisted task result run_id does not match the trusted run")
    if expected_task_id is not None and task_id != expected_task_id:
        raise ValueError("persisted task result task_id does not match the scheduled task")
    if expected_source is not None and source != expected_source:
        raise ValueError("persisted task result source does not match the scheduled task")

    status = value.get("status")
    if not isinstance(status, str) or status not in ALLOWED_STATUSES:
        raise ValueError("persisted task result status is not recognized")
    if terminal_only and status not in {"passed", "failed"}:
        raise ValueError("benchmark task result must have a passed/failed terminal status")
    if expected_status is not None and status != expected_status:
        raise ValueError("persisted task result status does not match the terminal run outcome")
    reward = value.get("reward")
    if status in {"passed", "failed"}:
        if (
            isinstance(reward, bool)
            or not isinstance(reward, (int, float))
            or not math.isfinite(reward)
            or not 0.0 <= reward <= 1.0
        ):
            raise ValueError("terminal task result reward must be a finite number in [0, 1]")
    elif reward is not None:
        raise ValueError(f"{status} task result reward must be null")

    verifier = value.get("verifier")
    if not isinstance(verifier, dict):
        raise ValueError("persisted task result verifier must be an object")
    if "id" in verifier:
        validate_nonempty_string(verifier["id"], field_name="result verifier id")
    if "checksum" in verifier:
        validate_nonempty_string(
            verifier["checksum"], field_name="result verifier checksum"
        )
    if expected_verifier_id is not None and verifier.get("id") != expected_verifier_id:
        raise ValueError("result verifier id does not match the pinned verifier")
    if (
        expected_verifier_checksum is not None
        and verifier.get("checksum") != expected_verifier_checksum
    ):
        raise ValueError("result verifier checksum does not match the pinned verifier")
    error = value.get("error")
    if error is not None and not isinstance(error, dict):
        raise ValueError("persisted task result error must be null or an object")

    trace_path = value.get("trace_path")
    if trace_path is not None:
        trace_path = validate_relative_uri(trace_path, field_name="task result trace_path")
    if terminal_only and trace_path is None:
        raise ValueError("benchmark task result trace_path must be a safe relative path")
    artifacts = value.get("artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("persisted task result artifacts must be an array")
    validated_artifacts = [validate_artifact_ref_shape(ref) for ref in artifacts]

    metrics = value.get("metrics")
    metadata = value.get("metadata")
    if not isinstance(metrics, dict):
        raise ValueError("persisted task result metrics must be an object")
    if not isinstance(metadata, dict):
        raise ValueError("persisted task result metadata must be an object")
    if "benchmark_reportable" in metadata and not isinstance(
        metadata["benchmark_reportable"], bool
    ):
        raise ValueError("result metadata benchmark_reportable must be a boolean")

    timing = value.get("timing")
    if not isinstance(timing, dict) or set(timing) != TIMING_FIELDS:
        raise ValueError(
            "persisted task result timing fields must be exactly: "
            + ", ".join(sorted(TIMING_FIELDS))
        )
    validate_rfc3339(timing.get("started_at"), field_name="result timing started_at")
    validate_rfc3339(timing.get("finished_at"), field_name="result timing finished_at")
    elapsed = timing.get("elapsed_seconds")
    if (
        isinstance(elapsed, bool)
        or not isinstance(elapsed, (int, float))
        or not math.isfinite(elapsed)
        or elapsed < 0
    ):
        raise ValueError("result timing elapsed_seconds must be a finite non-negative number")

    canonical = copy.deepcopy(value)
    canonical["trace_path"] = trace_path
    canonical["artifacts"] = validated_artifacts
    canonical_json(canonical)
    return canonical


def artifact_ref(
    path: Path,
    *,
    evidence_root: Path,
    kind: str,
    media_type: str,
    visibility: tuple[str, ...] = ("orchestrator",),
) -> dict[str, Any]:
    """Build a structured reference for a runner-owned diagnostic artifact."""
    uri = path.relative_to(evidence_root).as_posix()
    return validate_artifact_ref_shape(
        {
            "kind": kind,
            "uri": uri,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "media_type": media_type,
            "visibility": list(visibility),
        }
    )


@dataclass(slots=True)
class TaskResult:
    task_id: str
    source: str
    status: str
    reward: float | None
    verifier: dict[str, Any] = field(default_factory=dict)
    error: dict[str, Any] | None = None
    trace_path: str | None = None
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        validate_task_id(self.task_id)
        validate_nonempty_string(self.source, field_name="source")
        if self.status not in ALLOWED_STATUSES:
            raise ValueError(f"Unsupported result status: {self.status}")
        if self.status == "passed" and self.reward is None:
            self.reward = 1.0
        if self.status == "failed" and self.reward is None:
            self.reward = 0.0
        if self.reward is not None:
            if isinstance(self.reward, bool) or not isinstance(self.reward, (int, float)):
                raise ValueError("Reward must be a number or null")
            if not math.isfinite(self.reward) or not 0.0 <= self.reward <= 1.0:
                raise ValueError(f"Reward must be in [0, 1], got {self.reward!r}")
        if self.status in {"invalid", "error", "skipped"} and self.reward is not None:
            raise ValueError(f"{self.status} result must not have a reward")
        if not isinstance(self.verifier, dict):
            raise ValueError("verifier must be an object")
        if self.error is not None and not isinstance(self.error, dict):
            raise ValueError("error must be null or an object")
        if not isinstance(self.metrics, dict):
            raise ValueError("metrics must be an object")
        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be an object")
        if self.trace_path is not None:
            validate_relative_uri(self.trace_path, field_name="trace_path")
        if not isinstance(self.artifacts, list):
            raise ValueError("artifacts must be an array")
        self.artifacts = [validate_artifact_ref_shape(ref) for ref in self.artifacts]
        canonical_json(self.verifier)
        canonical_json(self.error)
        canonical_json(self.metrics)
        canonical_json(self.metadata)

    def to_dict(self, *, run_id: str) -> dict[str, Any]:
        validate_nonempty_string(run_id, field_name="runner-owned run_id")
        self.validate()
        return {
            "schema_version": "0.1.0",
            "run_id": run_id,
            "task_id": self.task_id,
            "source": self.source,
            "status": self.status,
            "reward": self.reward,
            "verifier": self.verifier,
            "error": self.error,
            "trace_path": self.trace_path,
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
        expected_task_id = validate_task_id(
            expected_task_id, field_name="expected task_id"
        )
        source = validate_nonempty_string(source, field_name="source")
        if "run_id" in payload:
            raise ValueError("Bridge result must not set the runner-owned run_id")
        allowed_fields = {
            "task_id",
            "status",
            "reward",
            "verifier",
            "error",
            "trace_path",
            "artifacts",
            "metrics",
            "metadata",
        }
        unsupported = set(payload) - allowed_fields
        if unsupported:
            raise ValueError(
                "Bridge result has unsupported fields: " + ", ".join(sorted(unsupported))
            )
        raw_task_id = payload.get("task_id")
        try:
            task_id = validate_task_id(raw_task_id, field_name="bridge task_id")
        except ValueError as exc:
            raise ValueError(
                "Bridge result must contain a safe non-empty string task_id"
            ) from exc
        if task_id != expected_task_id:
            raise ValueError(
                f"Bridge returned task_id={task_id!r}; expected {expected_task_id!r}"
            )
        raw_status = payload.get("status")
        status = raw_status if isinstance(raw_status, str) else ""
        reward = payload.get("reward")
        if reward is not None and (
            isinstance(reward, bool) or not isinstance(reward, (int, float))
        ):
            raise ValueError("Bridge result reward must be a number or null")
        for field_name in ("verifier", "metrics", "metadata"):
            field_value = payload.get(field_name)
            if field_name in payload and not isinstance(field_value, dict):
                raise ValueError(f"Bridge result {field_name} must be an object")
        raw_verifier = payload.get("verifier") or {}
        for key in ("id", "checksum"):
            if key in raw_verifier:
                validate_nonempty_string(
                    raw_verifier[key], field_name=f"bridge verifier {key}"
                )
        metadata = dict(payload.get("metadata") or {})
        if "benchmark_reportable" in metadata and not isinstance(
            metadata["benchmark_reportable"], bool
        ):
            raise ValueError("Bridge result benchmark_reportable marker must be boolean")
        # External bridge output is diagnostic plumbing until a later trusted
        # evidence path validates and promotes it.  Never let bridge-authored
        # JSON promote itself into benchmark evidence.
        metadata["benchmark_reportable"] = False
        raw_trace_path = payload.get("trace_path")
        if raw_trace_path is not None:
            raw_trace_path = validate_relative_uri(
                raw_trace_path, field_name="bridge trace_path"
            )
        raw_artifacts = payload.get("artifacts", [])
        if not isinstance(raw_artifacts, list):
            raise ValueError("Bridge result artifacts must be an array")
        raw_error = payload.get("error")
        if raw_error is not None and not isinstance(raw_error, dict):
            raise ValueError("Bridge result error must be null or an object")
        result = cls(
            task_id=task_id,
            source=source,
            status=status,
            reward=reward,
            verifier=dict(payload.get("verifier") or {}),
            error=dict(raw_error) if raw_error is not None else None,
            trace_path=raw_trace_path,
            artifacts=[validate_artifact_ref_shape(ref) for ref in raw_artifacts],
            metrics=dict(payload.get("metrics") or {}),
            metadata=metadata,
        )
        result.validate()
        return result
