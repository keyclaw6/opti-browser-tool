from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .models import split_lf_jsonl_records, strict_json_loads


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def slug(value: str) -> str:
    allowed = []
    for char in value.lower():
        allowed.append(char if char.isalnum() or char in {"-", "_"} else "-")
    result = "".join(allowed)
    while "--" in result:
        result = result.replace("--", "-")
    return result.strip("-") or "run"


def read_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            text = handle.read()
        return strict_json_loads(text, field_name=f"JSON document {path}")
    except (UnicodeError, ValueError) as exc:
        raise ValueError(f"Invalid JSON at {path}: {exc}") from exc


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            records = split_lf_jsonl_records(
                handle.read(), field_name=f"JSONL document {path}"
            )
    except (UnicodeError, ValueError) as exc:
        raise ValueError(f"Invalid JSONL at {path}: {exc}") from exc

    rows: list[dict[str, Any]] = []
    for line_no, record in enumerate(records, start=1):
        try:
            value = strict_json_loads(
                record, field_name=f"JSONL record {path}:{line_no}"
            )
        except ValueError as exc:
            raise ValueError(f"Invalid JSONL at {path}:{line_no}: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"Expected object at {path}:{line_no}")
        rows.append(value)
    return rows


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, indent=2, ensure_ascii=False, sort_keys=False) + "\n"
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=False) + "\n")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
