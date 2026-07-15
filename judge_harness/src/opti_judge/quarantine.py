"""T3 quarantine queue: unresolved disagreement goes to the project owner.

The adjudication tie rule (ADR-0016) is structural here: nothing in this
module can modify a score. A quarantine entry is created when layers
disagree (T0 pass + fp_suspect flags; T0 fail + fn_suspect flags; verifier
vs assertion conflicts), and only a human resolution closes it.

Resolutions append to the calibration corpus automatically — the corpus is
a by-product of operating the system, not a separate labeling project.

FN recovery discipline: when a resolution says the verifier was wrong, the
recorded remedy is a *verifier or task repair* (which must re-run its probe
kit), never a score override — the ``resolution`` vocabulary has no
"override score" option on purpose.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import os
import stat
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from opti_eval.models import (
    canonical_json,
    split_lf_jsonl_records,
    strict_json_loads,
    validate_nonempty_string,
    validate_rfc3339,
    validate_standard_json,
    validate_task_id,
)

from .corpus import CorpusStore

RESOLUTIONS = (
    "true_success",       # T0 was right; flags were false alarms (labels judge errors)
    "true_failure",       # T0 was right; fn-suspicion unfounded
    "verifier_defect",    # T0 wrong → repair verifier, re-run probe kit
    "task_defect",        # task/assertion wrong → repair task record
    "undecidable",        # insufficient evidence → instrumentation gap recorded
)
CLEARING_RESOLUTION_BY_STATUS = {
    "passed": "true_success",
    "failed": "true_failure",
}
VERIFIER_STATUSES = frozenset(CLEARING_RESOLUTION_BY_STATUS)
ENTRY_STATUSES = frozenset({"pending", "resolved"})
ENTRY_FIELDS = frozenset(
    {
        "entry_id",
        "task_id",
        "run_ref",
        "verifier_status",
        "reason",
        "flags",
        "status",
        "resolution",
        "resolution_note",
        "created_at",
        "resolved_at",
    }
)


class QuarantineStateError(ValueError):
    """The disposition store cannot be trusted as readable regular state."""


def _compute_flag_fingerprint(
    *, task_id: str, run_ref: str, flag: dict[str, Any]
) -> str:
    canonical_flag = {
        key: value
        for key, value in flag.items()
        if key not in {"fingerprint", "recorded_at"}
    }
    payload = {
        "task_id": task_id,
        "run_ref": run_ref,
        "flag": canonical_flag,
    }
    encoded = canonical_json(payload).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def flag_fingerprint(*, task_id: str, run_ref: str, flag: dict[str, Any]) -> str:
    """Stable disposition key for one validated run/task/flag tuple."""
    validate_task_id(task_id, field_name="quarantine task_id")
    validate_nonempty_string(run_ref, field_name="quarantine run_ref")
    if type(flag) is not dict:
        raise ValueError("quarantine flag must be an object")
    validate_standard_json(flag, field_name="quarantine flag")
    return _compute_flag_fingerprint(task_id=task_id, run_ref=run_ref, flag=flag)


@dataclass(slots=True)
class QuarantineEntry:
    entry_id: str
    task_id: str
    run_ref: str
    verifier_status: str
    reason: str
    flags: list[dict[str, Any]] = field(default_factory=list)
    status: str = "pending"  # pending | resolved
    resolution: str | None = None
    resolution_note: str | None = None
    created_at: str = ""
    resolved_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "task_id": self.task_id,
            "run_ref": self.run_ref,
            "verifier_status": self.verifier_status,
            "reason": self.reason,
            "flags": self.flags,
            "status": self.status,
            "resolution": self.resolution,
            "resolution_note": self.resolution_note,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
        }


def _validate_flag(
    value: object,
    *,
    task_id: str,
    run_ref: str,
    label: str,
) -> dict[str, Any]:
    if type(value) is not dict:
        raise ValueError(f"{label} must be an object")
    validate_standard_json(value, field_name=label)
    for key in value:
        validate_nonempty_string(key, field_name=f"{label} key")
    if "recorded_at" in value:
        validate_rfc3339(value["recorded_at"], field_name=f"{label} recorded_at")
    if not set(value) - {"fingerprint", "recorded_at"}:
        raise ValueError(f"{label} must contain evidence fields")
    fingerprint = value.get("fingerprint")
    if (
        type(fingerprint) is not str
        or len(fingerprint) != 64
        or any(char not in "0123456789abcdef" for char in fingerprint)
    ):
        raise ValueError(f"{label} fingerprint must be 64 lowercase hex characters")
    expected = _compute_flag_fingerprint(
        task_id=task_id,
        run_ref=run_ref,
        flag=value,
    )
    if fingerprint != expected:
        raise ValueError(f"{label} fingerprint does not match its evidence")
    return dict(value)


def _validate_entry(value: object, *, label: str) -> QuarantineEntry:
    row = value.to_dict() if type(value) is QuarantineEntry else value
    if type(row) is not dict:
        raise ValueError(f"{label} must be an object")
    validate_standard_json(row, field_name=label)
    if set(row) != ENTRY_FIELDS:
        missing = sorted(ENTRY_FIELDS - set(row))
        extra = sorted(set(row) - ENTRY_FIELDS)
        raise ValueError(
            f"{label} fields mismatch; missing={missing}, unsupported={extra}"
        )

    entry_id = validate_nonempty_string(row["entry_id"], field_name=f"{label} entry_id")
    task_id = validate_task_id(row["task_id"], field_name=f"{label} task_id")
    run_ref = validate_nonempty_string(row["run_ref"], field_name=f"{label} run_ref")
    reason = validate_nonempty_string(row["reason"], field_name=f"{label} reason")
    verifier_status = row["verifier_status"]
    if type(verifier_status) is not str or verifier_status not in VERIFIER_STATUSES:
        raise ValueError(f"{label} verifier_status must be passed or failed")
    status = row["status"]
    if type(status) is not str or status not in ENTRY_STATUSES:
        raise ValueError(f"{label} status must be pending or resolved")
    raw_flags = row["flags"]
    if type(raw_flags) is not list:
        raise ValueError(f"{label} flags must be an array")
    flags = [
        _validate_flag(
            flag,
            task_id=task_id,
            run_ref=run_ref,
            label=f"{label} flags[{index}]",
        )
        for index, flag in enumerate(raw_flags)
    ]
    fingerprints = [flag["fingerprint"] for flag in flags]
    if len(set(fingerprints)) != len(fingerprints):
        raise ValueError(f"{label} flags must have unique fingerprints")
    created_at = validate_rfc3339(
        row["created_at"], field_name=f"{label} created_at"
    )

    resolution = row["resolution"]
    resolution_note = row["resolution_note"]
    resolved_at = row["resolved_at"]
    if status == "pending":
        if resolution is not None or resolution_note is not None or resolved_at is not None:
            raise ValueError(
                f"{label} pending entries require null resolution, note, and resolved_at"
            )
    else:
        if type(resolution) is not str or resolution not in RESOLUTIONS:
            raise ValueError(f"{label} resolved entry has an unknown resolution")
        if type(resolution_note) is not str:
            raise ValueError(f"{label} resolved entry resolution_note must be a string")
        resolved_at = validate_rfc3339(
            resolved_at, field_name=f"{label} resolved_at"
        )
        created_time = _dt.datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        resolved_time = _dt.datetime.fromisoformat(
            resolved_at.replace("Z", "+00:00")
        )
        if resolved_time < created_time:
            raise ValueError(f"{label} resolved_at must not precede created_at")
        if resolution == "true_success" and verifier_status != "passed":
            raise ValueError(f"{label} true_success requires verifier_status passed")
        if resolution == "true_failure" and verifier_status != "failed":
            raise ValueError(f"{label} true_failure requires verifier_status failed")

    return QuarantineEntry(
        entry_id=entry_id,
        task_id=task_id,
        run_ref=run_ref,
        verifier_status=verifier_status,
        reason=reason,
        flags=flags,
        status=status,
        resolution=resolution,
        resolution_note=resolution_note,
        created_at=created_at,
        resolved_at=resolved_at,
    )


def _validate_entries(entries: object, *, label: str) -> list[QuarantineEntry]:
    if type(entries) is not list or not entries:
        raise ValueError(f"{label} must contain at least one entry")
    validated = [
        _validate_entry(entry, label=f"{label} row {index}")
        for index, entry in enumerate(entries, start=1)
    ]
    entry_ids = [entry.entry_id for entry in validated]
    if len(set(entry_ids)) != len(entry_ids):
        raise ValueError(f"{label} contains duplicate entry_id values")
    return validated


class QuarantineQueue:
    def __init__(self, path: Path) -> None:
        self.path = path

    # ── storage ──────────────────────────────────────────────────────────
    def _load_all(self) -> list[QuarantineEntry]:
        try:
            metadata = self.path.lstat()
        except FileNotFoundError:
            return []
        except OSError as exc:
            raise QuarantineStateError(
                f"quarantine state cannot be inspected: {self.path}: {exc}"
            ) from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise QuarantineStateError(
                f"quarantine state must not be a symlink: {self.path}"
            )
        if not stat.S_ISREG(metadata.st_mode):
            raise QuarantineStateError(
                f"quarantine state must be a regular file: {self.path}"
            )
        try:
            with self.path.open("r", encoding="utf-8", newline="") as handle:
                text = handle.read()
        except (OSError, UnicodeError) as exc:
            raise QuarantineStateError(
                f"quarantine state is unreadable: {self.path}: {exc}"
            ) from exc

        try:
            records = split_lf_jsonl_records(
                text, field_name=f"quarantine state {self.path}"
            )
        except ValueError as exc:
            raise QuarantineStateError(str(exc)) from exc
        entries: list[QuarantineEntry] = []
        for line_number, line in enumerate(records, start=1):
            try:
                row = strict_json_loads(
                    line,
                    field_name=f"quarantine state line {line_number}",
                )
                entries.append(
                    _validate_entry(row, label=f"quarantine state line {line_number}")
                )
            except (TypeError, ValueError) as exc:
                raise QuarantineStateError(
                    f"quarantine state line {line_number} is malformed: {exc}"
                ) from exc
        try:
            return _validate_entries(entries, label=f"quarantine state {self.path}")
        except ValueError as exc:
            raise QuarantineStateError(str(exc)) from exc

    def _write_all(self, entries: list[QuarantineEntry]) -> None:
        try:
            validated = _validate_entries(entries, label="quarantine write")
            rendered = "".join(
                canonical_json(entry.to_dict()) + "\n" for entry in validated
            )
        except ValueError as exc:
            raise QuarantineStateError(f"refusing invalid quarantine write: {exc}") from exc

        temporary_path: Path | None = None
        descriptor: int | None = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                dir=self.path.parent,
            )
            temporary_path = Path(temporary_name)
            with os.fdopen(
                descriptor,
                "w",
                encoding="utf-8",
                newline="\n",
            ) as handle:
                descriptor = None
                handle.write(rendered)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, self.path)
            temporary_path = None
        except (OSError, UnicodeError) as exc:
            raise QuarantineStateError(
                f"quarantine state could not be written atomically: {self.path}: {exc}"
            ) from exc
        finally:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass

    # ── operations ───────────────────────────────────────────────────────
    def enqueue(
        self,
        *,
        task_id: str,
        run_ref: str,
        verifier_status: str,
        reason: str,
        flags: list[dict[str, Any]] | None = None,
    ) -> QuarantineEntry:
        task_id = validate_task_id(task_id, field_name="quarantine task_id")
        run_ref = validate_nonempty_string(run_ref, field_name="quarantine run_ref")
        reason = validate_nonempty_string(reason, field_name="quarantine reason")
        if type(verifier_status) is not str or verifier_status not in VERIFIER_STATUSES:
            raise ValueError("quarantine verifier_status must be passed or failed")
        if flags is None:
            raw_flags: list[dict[str, Any]] = []
        elif type(flags) is list:
            raw_flags = flags
        else:
            raise ValueError("quarantine flags must be an array or null")
        fingerprinted: list[dict[str, Any]] = []
        for index, flag in enumerate(raw_flags):
            if type(flag) is not dict:
                raise ValueError("quarantine flags must be objects")
            validate_standard_json(flag, field_name=f"quarantine flags[{index}]")
            if "fingerprint" in flag:
                _validate_flag(
                    flag,
                    task_id=task_id,
                    run_ref=run_ref,
                    label=f"quarantine flags[{index}]",
                )
            row = {key: value for key, value in flag.items() if key != "fingerprint"}
            if not set(row) - {"recorded_at"}:
                raise ValueError("quarantine flags must contain evidence fields")
            row["fingerprint"] = flag_fingerprint(
                task_id=task_id, run_ref=run_ref, flag=row
            )
            fingerprinted.append(row)
        entry = QuarantineEntry(
            entry_id=uuid.uuid4().hex[:12],
            task_id=task_id,
            run_ref=run_ref,
            verifier_status=verifier_status,
            reason=reason,
            flags=fingerprinted,
            created_at=_dt.datetime.now(_dt.timezone.utc).isoformat(),
        )
        entry = _validate_entry(entry, label="new quarantine entry")
        entries = self._load_all()
        entries.append(entry)
        self._write_all(entries)
        return entry

    def pending(self) -> list[QuarantineEntry]:
        return [e for e in self._load_all() if e.status == "pending"]

    def validate_state(self) -> None:
        """Validate the complete queue without applying task-only policy."""
        self._load_all()

    def pending_task_ids(self) -> set[str]:
        return {e.task_id for e in self.pending()}

    def flag_fingerprints(self, *, task_id: str, run_ref: str) -> set[str]:
        """Every stored fingerprint for exact-run dedupe, regardless of outcome."""
        fingerprints: set[str] = set()
        for entry in self._load_all():
            if entry.task_id != task_id or entry.run_ref != run_ref:
                continue
            for flag in entry.flags:
                fingerprints.add(flag["fingerprint"])
        return fingerprints

    def exact_run_dispositions(
        self, *, task_id: str, run_ref: str
    ) -> list[dict[str, Any]]:
        """Validated disposition records bound to one exact evidence run."""
        return [
            entry.to_dict()
            for entry in self._load_all()
            if entry.task_id == task_id and entry.run_ref == run_ref
        ]

    def run_is_blocked(self, *, task_id: str, run_ref: str) -> bool:
        """Whether this exact evidence run still has an uncleared disposition.

        Storing or resolving a flag is not the same as clearing its evidence.
        Only a resolution that affirms the verifier's terminal outcome clears
        that entry.  Repair/defect/undecidable resolutions remain blocking for
        this run reference; a repair must produce a new run.
        """
        for entry in self._load_all():
            if entry.task_id != task_id or entry.run_ref != run_ref:
                continue
            clearing = CLEARING_RESOLUTION_BY_STATUS.get(entry.verifier_status)
            if entry.status != "resolved" or entry.resolution != clearing:
                return True
        return False

    def resolve(
        self,
        entry_id: str,
        *,
        resolution: str,
        note: str,
        corpus: CorpusStore | None = None,
    ) -> QuarantineEntry:
        entry_id = validate_nonempty_string(entry_id, field_name="quarantine entry_id")
        if type(resolution) is not str or resolution not in RESOLUTIONS:
            raise ValueError(
                f"unknown resolution {resolution!r}; allowed: {', '.join(RESOLUTIONS)} "
                "(there is deliberately no 'override score' option)"
            )
        if type(note) is not str:
            raise ValueError("quarantine resolution note must be a string")
        entries = self._load_all()
        target = next((e for e in entries if e.entry_id == entry_id), None)
        if target is None:
            raise KeyError(f"no quarantine entry {entry_id}")
        if target.status == "resolved":
            raise ValueError(f"entry {entry_id} is already resolved")
        if target.verifier_status not in CLEARING_RESOLUTION_BY_STATUS:
            raise ValueError(
                "quarantine resolution requires a terminal passed/failed verifier status"
            )
        if resolution == "true_success" and target.verifier_status != "passed":
            raise ValueError("true_success may resolve only a verifier-passed entry")
        if resolution == "true_failure" and target.verifier_status != "failed":
            raise ValueError("true_failure may resolve only a verifier-failed entry")
        target.status = "resolved"
        target.resolution = resolution
        target.resolution_note = note
        target.resolved_at = _dt.datetime.now(_dt.timezone.utc).isoformat()
        target = _validate_entry(target, label=f"resolved quarantine entry {entry_id}")
        entries = [target if entry.entry_id == entry_id else entry for entry in entries]
        self._write_all(entries)

        if corpus is not None:
            ground_truth = {
                "true_success": "success",
                "true_failure": "failure",
                "verifier_defect": (
                    "success" if target.verifier_status == "failed" else "failure"
                ),
                "task_defect": "undecidable",
                "undecidable": "undecidable",
            }[resolution]
            corpus.add_case(
                source="quarantine",
                task_id=target.task_id,
                run_ref=target.run_ref,
                ground_truth=ground_truth,
                detail={
                    "entry_id": target.entry_id,
                    "resolution": resolution,
                    "note": note,
                    "verifier_status": target.verifier_status,
                    "flags": target.flags,
                },
            )
        return target
