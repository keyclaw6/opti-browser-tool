from __future__ import annotations

import shlex
import shutil
from pathlib import Path
from typing import Any

from .util import read_json


def inspect_registry(config_path: Path) -> dict[str, Any]:
    payload = read_json(config_path)
    sources = payload.get("sources") if isinstance(payload, dict) else None
    if not isinstance(sources, dict):
        raise ValueError("Registry config must contain an object named 'sources'")
    results: dict[str, Any] = {}
    overall_ok = True
    for source, raw_entry in sorted(sources.items()):
        entry = raw_entry if isinstance(raw_entry, dict) else {}
        enabled = bool(entry.get("enabled", False))
        command = str(entry.get("command", "")).strip()
        executable: str | None = None
        executable_found: bool | None = None
        parse_error: str | None = None
        if command:
            try:
                parts = shlex.split(command)
                if parts:
                    executable = parts[0]
                    executable_found = shutil.which(executable) is not None
            except ValueError as exc:
                parse_error = str(exc)
        ok = (not enabled) or (
            bool(command) and parse_error is None and executable_found is not False
        )
        overall_ok = overall_ok and ok
        results[str(source)] = {
            "enabled": enabled,
            "has_command": bool(command),
            "executable": executable,
            "executable_found": executable_found,
            "parse_error": parse_error,
            "ok": ok,
        }
    return {"ok": overall_ok, "config": str(config_path), "sources": results}
