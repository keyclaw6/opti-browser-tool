#!/usr/bin/env python3
"""Build and independently verify committed HEAD as a ZIP including .git."""

from __future__ import annotations

import argparse
import hashlib
import os
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".codebase-memory",
    "runs",
    "build",
    "dist",
}


def run(
    command: list[str], *, cwd: Path, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command, cwd=cwd, env=env, text=True, capture_output=True, check=False
    )
    if completed.returncode != 0:
        raise SystemExit(
            f"Command failed ({completed.returncode}): {' '.join(command)}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed


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
        if rel.parts[0] != ".git" and any(
            part in EXCLUDED_DIRS or part.endswith(".egg-info") for part in rel.parts
        ):
            continue
        if path.resolve() == output.resolve():
            continue
        files.append(path)
    return sorted(files, key=lambda p: p.relative_to(root).as_posix())


def extract_archive(archive: zipfile.ZipFile, destination: Path) -> None:
    """Extract the archive inside destination and restore stored Unix modes."""
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    members: list[tuple[zipfile.ZipInfo, Path]] = []
    for info in archive.infolist():
        relative = PurePosixPath(info.filename)
        if relative.is_absolute() or ".." in relative.parts:
            raise SystemExit(f"Unsafe ZIP member path: {info.filename}")
        target = (root / Path(*relative.parts)).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            raise SystemExit(
                f"ZIP member escapes extraction root: {info.filename}"
            ) from None
        members.append((info, target))

    archive.extractall(root)
    for info, target in members:
        if not target.exists():
            raise SystemExit(f"ZIP member was not extracted: {info.filename}")
        if info.create_system == 3:
            os.chmod(target, stat.S_IMODE(info.external_attr >> 16))


def assert_standalone_git(root: Path) -> None:
    git_dir = root / ".git"
    if not git_dir.is_dir():
        raise SystemExit(f"Archived checkout must contain a .git directory: {git_dir}")

    common_dir_text = run(
        ["git", "rev-parse", "--git-common-dir"], cwd=root
    ).stdout.strip()
    common_dir = Path(common_dir_text)
    if not common_dir.is_absolute():
        common_dir = root / common_dir
    common_dir = common_dir.resolve()
    try:
        common_dir.relative_to(root.resolve())
    except ValueError:
        raise SystemExit(
            f"Git common directory escapes archived checkout: {common_dir}"
        ) from None

    alternates = git_dir / "objects" / "info" / "alternates"
    if alternates.exists():
        raise SystemExit(
            f"Archived checkout depends on external Git objects: {alternates}"
        )


def clone_committed_root(destination: Path) -> str:
    commit = run(["git", "rev-parse", "HEAD"], cwd=ROOT).stdout.strip()
    run(
        ["git", "clone", "--no-hardlinks", str(ROOT), str(destination)],
        cwd=destination.parent,
    )
    cloned_commit = run(["git", "rev-parse", "HEAD"], cwd=destination).stdout.strip()
    if cloned_commit != commit:
        raise SystemExit(f"Clone HEAD mismatch: expected {commit}, got {cloned_commit}")
    run(["git", "remote", "remove", "origin"], cwd=destination)
    if run(["git", "remote"], cwd=destination).stdout.strip():
        raise SystemExit("Archived checkout retains a Git remote")
    if run(["git", "status", "--porcelain"], cwd=destination).stdout.strip():
        raise SystemExit("Archived checkout is not clean")
    assert_standalone_git(destination)
    return commit


def verify_tree(root: Path) -> None:
    """Run preservation and clean-install checks without live use."""
    clean_env = os.environ.copy()
    clean_env.pop("PYTHONPATH", None)
    clean_env.pop("OPTI_BROWSER_REPO_ROOT", None)
    clean_env["PYTHONDONTWRITEBYTECODE"] = "1"
    run(
        [
            sys.executable,
            "scripts/verify_repository_completeness.py",
            "--repo-root",
            ".",
        ],
        cwd=root,
        env=clean_env,
    )
    run(
        [sys.executable, "scripts/verify_file_manifest.py", "--repo-root", "."],
        cwd=root,
        env=clean_env,
    )
    run(
        [sys.executable, "scripts/verify_clean_install.py", "--repo-root", "."],
        cwd=root,
        env=clean_env,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--bundle", action="store_true")
    args = parser.parse_args()
    output = Path(args.output).resolve()

    status = run(["git", "status", "--porcelain"], cwd=ROOT).stdout.strip()
    if status:
        raise SystemExit(
            "Refusing to archive a dirty worktree because the archive contains "
            "committed HEAD only. Commit or otherwise clean all changes first."
        )

    output.parent.mkdir(parents=True, exist_ok=True)

    if output.exists():
        output.unlink()
    root_name = ROOT.name
    with tempfile.TemporaryDirectory(prefix="opti-browser-archive-build-") as tmp:
        tmp_path = Path(tmp)
        clone = tmp_path / "clone" / root_name
        clone.parent.mkdir()
        clone_committed_root(clone)

        files = included_files(clone, output)
        with zipfile.ZipFile(
            output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as archive:
            for path in files:
                archive.write(path, f"{root_name}/{path.relative_to(clone).as_posix()}")
        with zipfile.ZipFile(output) as archive:
            bad = archive.testzip()
            if bad:
                raise SystemExit(f"ZIP CRC failure: {bad}")

        extraction_root = tmp_path / "extracted"
        with zipfile.ZipFile(output) as archive:
            extract_archive(archive, extraction_root)
        extracted = extraction_root / root_name
        status = run(["git", "status", "--porcelain"], cwd=extracted).stdout.strip()
        if status:
            raise SystemExit(
                f"Extracted checkout differs from committed HEAD:\n{status}"
            )
        assert_standalone_git(extracted)
        verify_tree(extracted)

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
