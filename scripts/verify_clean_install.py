#!/usr/bin/env python3
"""Prove the three packages install and run without source-tree path injection.

uv builds in offline mode using its cached build backend, then resolves and
installs from a local wheelhouse with no index and an empty install cache. The
deterministic tests invoke no live backend; this is not an OS network sandbox.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


PACKAGES = ("eval_harness", "judge_harness", "loop_harness")
EXPECTED_DISTRIBUTIONS = {
    "opti-browser-eval": set(),
    "opti-judge": {"opti-browser-eval==0.1.0"},
    "opti-loop": {"opti-browser-eval==0.1.0", "opti-judge==0.1.0"},
}
EXPECTED_SCRIPTS = {
    "opti-browser-eval": ("opti-eval", "opti_eval.cli:main"),
    "opti-judge": ("opti-judge", "opti_judge.cli:main"),
    "opti-loop": ("opti-loop", "opti_loop.cli:main"),
}
COPY_IGNORES = (
    ".git",
    ".venv",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "*.egg-info",
    "*.pyc",
    "build",
    "dist",
    "runs",
)


class VerificationError(RuntimeError):
    """An installability assertion failed."""


def run(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and completed.returncode != 0:
        raise VerificationError(
            f"command failed ({completed.returncode}): {' '.join(command)}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed


def offline_env(*, cache: Path | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "UV_OFFLINE": "1",
            "UV_PYTHON_DOWNLOADS": "never",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    if cache is not None:
        env["UV_CACHE_DIR"] = str(cache)
    return env


def test_env(repo_root: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "OPTI_BROWSER_REPO_ROOT": str(repo_root),
        }
    )
    return env


def snapshot_working_tree(repo_root: Path, destination: Path) -> str:
    shutil.copytree(
        repo_root,
        destination,
        ignore=shutil.ignore_patterns(*COPY_IGNORES),
    )
    return "working-tree-copy"


def snapshot_head(repo_root: Path, destination: Path, scratch: Path) -> str:
    commit = run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        cwd=repo_root,
    ).stdout.strip()
    archive = scratch / "source.tar"
    run(
        [
            "git",
            "-C",
            str(repo_root),
            "archive",
            "--format=tar",
            "-o",
            str(archive),
            commit,
        ],
        cwd=repo_root,
    )
    destination.mkdir()
    with tarfile.open(archive) as bundle:
        bundle.extractall(destination, filter="data")
    return commit


def build_wheels(source: Path, wheels: Path, uv: str) -> list[Path]:
    wheels.mkdir()
    for package in PACKAGES:
        completed = run(
            [
                uv,
                "build",
                "--offline",
                "--wheel",
                "--no-create-gitignore",
                "--out-dir",
                str(wheels),
                str(source / package),
            ],
            cwd=source,
            env=offline_env(),
            check=False,
        )
        if completed.returncode != 0:
            raise VerificationError(
                "offline source-to-wheel build failed. This step requires "
                "setuptools>=68 to already exist in uv's build cache; no index "
                "or uv network fallback is permitted.\n"
                f"package: {package}\nstdout:\n{completed.stdout}\n"
                f"stderr:\n{completed.stderr}"
            )
    built = sorted(wheels.glob("*.whl"))
    if len(built) != 3 or any("-py3-none-any.whl" not in path.name for path in built):
        raise VerificationError(
            f"expected exactly three py3-none-any wheels, got {[path.name for path in built]}"
        )
    return built


def create_venv(uv: str, path: Path, cwd: Path) -> Path:
    run(
        [uv, "venv", "--python", sys.executable, str(path)],
        cwd=cwd,
        env=offline_env(),
    )
    python = path / "bin" / "python"
    run(
        [
            python.as_posix(),
            "-I",
            "-c",
            "import importlib.util; "
            "assert importlib.util.find_spec('setuptools') is None",
        ],
        cwd=cwd,
    )
    return python


def install_loop(
    uv: str,
    python: Path,
    wheels: Path,
    cache: Path,
    cwd: Path,
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    cache.mkdir()
    return run(
        [
            uv,
            "pip",
            "install",
            "--offline",
            "--python",
            str(python),
            "--no-index",
            "--find-links",
            str(wheels),
            "opti-loop==0.1.0",
        ],
        cwd=cwd,
        env=offline_env(cache=cache),
        check=check,
    )


def assert_installed_contract(python: Path, cwd: Path) -> None:
    payload = json.dumps(
        {
            "requirements": {
                name: sorted(values) for name, values in EXPECTED_DISTRIBUTIONS.items()
            },
            "scripts": {
                name: list(values) for name, values in EXPECTED_SCRIPTS.items()
            },
        }
    )
    code = r"""
import importlib.util
import json
from importlib.metadata import distribution, distributions, requires

expected = json.loads(__import__("sys").argv[1])
actual_names = {item.metadata["Name"] for item in distributions()}
assert actual_names == set(expected["requirements"]), actual_names
for name, wanted in expected["requirements"].items():
    assert set(requires(name) or []) == set(wanted), (name, requires(name))
for name, (script_name, target) in expected["scripts"].items():
    entries = {
        item.name: item.value
        for item in distribution(name).entry_points
        if item.group == "console_scripts"
    }
    assert entries == {script_name: target}, (name, entries)
assert importlib.util.find_spec("setuptools") is None
import opti_eval
import opti_judge
import opti_loop
"""
    run([str(python), "-I", "-c", code, payload], cwd=cwd)


def assert_missing_dependency_fails(
    uv: str, built: list[Path], scratch: Path, cwd: Path
) -> None:
    broken_wheels = scratch / "broken-wheels"
    broken_wheels.mkdir()
    for wheel in built:
        if wheel.name.startswith(("opti_browser_eval-", "opti_loop-")):
            shutil.copy2(wheel, broken_wheels / wheel.name)
    broken_python = create_venv(uv, scratch / "broken-venv", cwd)
    completed = install_loop(
        uv,
        broken_python,
        broken_wheels,
        scratch / "broken-cache",
        cwd,
        check=False,
    )
    detail = (completed.stdout + completed.stderr).lower()
    if completed.returncode == 0 or "opti-judge" not in detail:
        raise VerificationError(
            "negative resolver control did not fail specifically for missing opti-judge\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )


def installed_cli_checks(venv: Path, source: Path, outside: Path) -> None:
    env = test_env(source)
    env.pop("OPTI_BROWSER_REPO_ROOT", None)
    for script in ("opti-eval", "opti-judge", "opti-loop"):
        run([str(venv / "bin" / script), "--help"], cwd=outside, env=env)
    run(
        [str(venv / "bin" / "opti-eval"), "validate", "--repo-root", str(source)],
        cwd=outside,
        env=env,
    )
    run([str(venv / "bin" / "opti-eval"), "validate"], cwd=source, env=env)
    unused_store = outside / "unused-store"
    run(
        [
            str(venv / "bin" / "opti-loop"),
            "--store-root",
            str(unused_store),
            "transfer-eval",
            "--deltas",
            "noop=0",
        ],
        cwd=source,
        env=env,
    )
    if unused_store.exists():
        raise VerificationError(
            "pure transfer-eval unexpectedly created the configured store"
        )


def installed_test_checks(python: Path, source: Path) -> None:
    env = test_env(source)
    for tests in ("eval_harness/tests", "judge_harness/tests", "loop_harness/tests"):
        run(
            [str(python), "-m", "unittest", "discover", "-s", tests, "-v"],
            cwd=source,
            env=env,
        )


def verify(repo_root: Path, snapshot: str) -> dict[str, object]:
    uv = shutil.which("uv")
    if uv is None:
        raise VerificationError("uv is required for the offline clean-install proof")
    with tempfile.TemporaryDirectory(prefix="opti-clean-install-") as tmp:
        scratch = Path(tmp)
        source = scratch / "source"
        snapshot_id = (
            snapshot_working_tree(repo_root, source)
            if snapshot == "working"
            else snapshot_head(repo_root, source, scratch)
        )
        wheels = scratch / "wheels"
        built = build_wheels(source, wheels, uv)
        venv = scratch / "venv"
        python = create_venv(uv, venv, source)
        install_loop(uv, python, wheels, scratch / "install-cache", source)
        outside = scratch / "outside"
        outside.mkdir()
        assert_installed_contract(python, outside)
        assert_missing_dependency_fails(uv, built, scratch, outside)
        installed_cli_checks(venv, source, outside)
        installed_test_checks(python, source)
        uv_version = run([uv, "--version"], cwd=outside).stdout.strip()
        return {
            "status": "pass",
            "snapshot": snapshot_id,
            "python": sys.version.split()[0],
            "uv": uv_version,
            "wheels": [path.name for path in built],
            "requested_install": "opti-loop==0.1.0",
            "installed_distributions": sorted(EXPECTED_DISTRIBUTIONS),
            "negative_control": "missing opti-judge rejected",
            "cli_checks": [
                "help",
                "eval validate",
                "cwd discovery",
                "pure transfer-eval",
            ],
            "test_suites": list(PACKAGES),
            "dependency_resolution": "offline/no-index",
            "test_execution": "no live backend",
            "benchmark_evidence": False,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--snapshot", choices=("working", "head"), default="working")
    args = parser.parse_args()
    repo_root = Path(args.repo_root).expanduser().resolve()
    try:
        result = verify(repo_root, args.snapshot)
    except (OSError, VerificationError, tarfile.TarError) as exc:
        print(f"Clean install verification: FAIL\n{exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    print("Clean install verification: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
