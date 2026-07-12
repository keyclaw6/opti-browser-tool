#!/usr/bin/env python3
"""Build and independently verify a complete repository ZIP including .git."""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {".venv", "__pycache__", ".pytest_cache", "runs"}


def run(command: list[str], *, cwd: Path) -> None:
    completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise SystemExit(
            f"Command failed ({completed.returncode}): {' '.join(command)}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def included_files(root: Path, output: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in EXCLUDED_DIRS for part in rel.parts):
            continue
        if path.resolve() == output.resolve():
            continue
        files.append(path)
    return sorted(files, key=lambda p: p.relative_to(root).as_posix())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--bundle", action="store_true")
    args = parser.parse_args()
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT, text=True, capture_output=True, check=True
    ).stdout.strip()
    if status and not args.allow_dirty:
        raise SystemExit("Refusing to archive a dirty repository. Commit or use --allow-dirty.")

    run([sys.executable, "scripts/verify_documentation.py", "--repo-root", "."], cwd=ROOT)
    run([sys.executable, "scripts/verify_repository_completeness.py", "--repo-root", "."], cwd=ROOT)
    run([sys.executable, "scripts/verify_file_manifest.py", "--repo-root", "."], cwd=ROOT)

    if output.exists():
        output.unlink()
    root_name = ROOT.name
    files = included_files(ROOT, output)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            archive.write(path, f"{root_name}/{path.relative_to(ROOT).as_posix()}")
    with zipfile.ZipFile(output) as archive:
        bad = archive.testzip()
        if bad:
            raise SystemExit(f"ZIP CRC failure: {bad}")

    with tempfile.TemporaryDirectory(prefix="opti-browser-archive-check-") as tmp:
        tmp_path = Path(tmp)
        with zipfile.ZipFile(output) as archive:
            archive.extractall(tmp_path)
        extracted = tmp_path / root_name
        run(["git", "fsck", "--full", "--no-dangling"], cwd=extracted)
        run([sys.executable, "scripts/verify_documentation.py", "--repo-root", "."], cwd=extracted)
        run([sys.executable, "scripts/verify_repository_completeness.py", "--repo-root", "."], cwd=extracted)
        run([sys.executable, "scripts/verify_file_manifest.py", "--repo-root", "."], cwd=extracted)

    digest = sha256(output)
    sidecar = output.with_name(output.name + ".sha256")
    sidecar.write_text(f"{digest}  {output.name}\n", encoding="utf-8")

    if args.bundle:
        bundle = output.with_suffix(".bundle")
        if bundle.exists():
            bundle.unlink()
        run(["git", "bundle", "create", str(bundle), "--all"], cwd=ROOT)
        run(["git", "bundle", "verify", str(bundle)], cwd=ROOT)
        bundle.with_name(bundle.name + ".sha256").write_text(
            f"{sha256(bundle)}  {bundle.name}\n", encoding="utf-8"
        )

    print(f"Archive: {output}")
    print(f"Files: {len(files)}")
    print(f"SHA-256: {digest}")
    print("Extraction and repository checks: PASS")


if __name__ == "__main__":
    main()
