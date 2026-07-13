#!/usr/bin/env python3
"""Regenerate FILE_INVENTORY.tsv and MANIFEST.sha256 deterministically."""
from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", "runs", "campaigns"}
EXCLUDED_FILES = {"FILE_INVENTORY.tsv", "MANIFEST.sha256"}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def included_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if any(part in EXCLUDED_DIRS for part in rel.parts):
            continue
        if rel.as_posix() in EXCLUDED_FILES:
            continue
        files.append(path)
    return sorted(files, key=lambda path: path.relative_to(ROOT).as_posix())


def main() -> None:
    files = included_files()
    inventory_lines = ["path\tsize_bytes\tsha256"]
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        inventory_lines.append(f"{rel}\t{path.stat().st_size}\t{digest(path)}")
    inventory = ROOT / "FILE_INVENTORY.tsv"
    inventory.write_text("\n".join(inventory_lines) + "\n", encoding="utf-8")

    manifest_files = files + [inventory]
    manifest_files.sort(key=lambda path: path.relative_to(ROOT).as_posix())
    manifest_lines = [
        f"{digest(path)}  {path.relative_to(ROOT).as_posix()}"
        for path in manifest_files
    ]
    (ROOT / "MANIFEST.sha256").write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")
    print(f"Inventory: {len(files)} files")
    print(f"Manifest: {len(manifest_files)} files")


if __name__ == "__main__":
    main()
