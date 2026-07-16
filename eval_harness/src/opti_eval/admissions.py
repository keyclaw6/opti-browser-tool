"""Strict verifier-admission loading shared by preflight and AR-003."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import (
    split_lf_jsonl_records,
    strict_json_loads,
    validate_nonempty_string,
    validate_task_id,
)


def load_admissions(path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    index: dict[tuple[str, str], dict[str, Any]] = {}
    if not path.exists():
        return index
    if path.is_symlink() or not path.is_file():
        raise ValueError("admissions path must be a regular file, not a symlink")
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            records = split_lf_jsonl_records(
                handle.read(), field_name="admissions JSONL"
            )
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"admissions file is unreadable: {exc}") from exc
    except ValueError as exc:
        raise ValueError(f"admissions JSONL framing is invalid: {exc}") from exc
    for line_number, record in enumerate(records, start=1):
        try:
            row = strict_json_loads(
                record, field_name=f"admissions line {line_number}"
            )
        except ValueError as exc:
            raise ValueError(f"admissions line {line_number} is invalid: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"admissions line {line_number} must be an object")
        if not isinstance(row.get("admitted"), bool):
            raise ValueError(f"admissions line {line_number} admitted must be boolean")
        try:
            verifier_id = validate_nonempty_string(
                row.get("verifier_id"),
                field_name=f"admissions line {line_number} verifier_id",
            )
            task_id = validate_task_id(
                row.get("task_id"),
                field_name=f"admissions line {line_number} task_id",
            )
            validate_nonempty_string(
                row.get("verifier_checksum"),
                field_name=f"admissions line {line_number} verifier_checksum",
            )
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        if row["admitted"]:
            key = (verifier_id, task_id)
            previous = index.get(key)
            if previous is not None and previous.get("verifier_checksum") != row.get(
                "verifier_checksum"
            ):
                raise ValueError(
                    f"admissions contains conflicting checksums for {verifier_id}/{task_id}"
                )
            index[key] = row
    return index


def require_verifier_admission(
    path: Path, *, verifier_id: str, task_id: str, verifier_checksum: str
) -> dict[str, Any]:
    """Require one exact positive admission, with actionable mismatch errors."""
    admissions = load_admissions(path)
    row = admissions.get((verifier_id, task_id))
    if row is None:
        raise ValueError(
            f"no admitted verifier record for {verifier_id}/{task_id}"
        )
    admitted_checksum = row.get("verifier_checksum")
    if admitted_checksum != verifier_checksum:
        raise ValueError(
            f"admitted verifier checksum mismatch for {verifier_id}/{task_id}: "
            f"expected {verifier_checksum}, got {admitted_checksum}"
        )
    return row
