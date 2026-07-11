#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    manifest = root / "MANIFEST.sha256"
    errors: list[str] = []
    checked = 0
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split("  ", 1)
        path = root / relative
        if not path.is_file():
            errors.append(f"missing: {relative}")
            continue
        actual = sha256(path)
        if actual != expected:
            errors.append(f"checksum mismatch: {relative}")
        checked += 1
    if errors:
        print("File manifest: FAIL")
        for error in errors:
            print(error)
        return 1
    print(f"File manifest: PASS ({checked} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
