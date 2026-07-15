#!/usr/bin/env python3
"""Fail-closed completeness check for the reconstructed repository."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tomllib
from pathlib import Path

REQUIRED_FILES = [
    "README.md",
    "RECOVERY_MANIFEST.md",
    "PROJECT_CHARTER.md",
    "docs/README.md",
    "docs/AGENT_HANDOFF.md",
    "docs/REVIEW_GUIDE.md",
    "docs/DECISION_PROCESS.md",
    "docs/DECISION_REGISTER.md",
    "docs/DECISION_TIMELINE.md",
    "docs/TASK_DATA_GUIDE.md",
    "docs/ROADMAP.md",
    "docs/OPEN_QUESTIONS.md",
    "docs/adr/0001-project-constitution.md",
    "docs/adr/0012-reference-success-band-35-to-70.md",
    "docs/adr/0014-run-all-140-candidates-before-filtering.md",
    "docs/adr/0018-auto-research-readiness-protocol-transition.md",
    "research/benchmarks/task-candidates/batch-1-candidates.jsonl",
    "research/benchmarks/task-candidates/batch-1-candidates.csv",
    "research/benchmarks/task-candidates/batch-1-index.md",
    "research/benchmarks/task-candidates/batch-1-sources.lock.json",
    "research/benchmarks/candidate-benchmarks.yaml",
    "evals/catalog/tasks.jsonl",
    "evals/catalog/tasks.csv",
    "evals/catalog/task-index.json",
    "evals/catalog/by-id/real_v1/real-v1-dashdish-4.json",
    "evals/suites/candidate-pool.json",
    "evals/suites/primary.json",
    "evals/suites/smoke.json",
    "evals/suites/regression.json",
    "eval_harness/pyproject.toml",
    "eval_harness/src/opti_eval/cli.py",
    "eval_harness/src/opti_eval/runner.py",
    "eval_harness/src/opti_eval/adapters/fixture.py",
    "eval_harness/src/opti_eval/adapters/command.py",
    "eval_harness/src/opti_eval/adapters/registry.py",
    "eval_harness/tests/test_repository_validation.py",
    "judge_harness/pyproject.toml",
    "judge_harness/src/opti_judge/cli.py",
    "loop_harness/pyproject.toml",
    "loop_harness/src/opti_loop/cli.py",
    "scripts/verify_documentation.py",
    "scripts/validate_json_schemas.py",
    "scripts/build_file_manifest.py",
    "scripts/build_repository_archive.py",
    "scripts/verify_clean_install.py",
    "archive/superseded/runnable-suite-v0-100/README.md",
    "validation/README.md",
    "validation/documentation-validation.json",
    "validation/repository-validation.json",
    "validation/fixture-140-summary.json",
    "validation/command-bridge-summary.json",
    "validation/registry-doctor.json",
    "validation/schema-validation.json",
    "validation/compileall.txt",
    "validation/unit-tests.txt",
]

PACKAGE_CONTRACTS = {
    "eval_harness/pyproject.toml": {
        "name": "opti-browser-eval",
        "dependencies": [],
        "script": ("opti-eval", "opti_eval.cli:main"),
    },
    "judge_harness/pyproject.toml": {
        "name": "opti-judge",
        "dependencies": ["opti-browser-eval==0.1.0"],
        "script": ("opti-judge", "opti_judge.cli:main"),
    },
    "loop_harness/pyproject.toml": {
        "name": "opti-loop",
        "dependencies": ["opti-browser-eval==0.1.0", "opti-judge==0.1.0"],
        "script": ("opti-loop", "opti_loop.cli:main"),
    },
}


def audit_package_metadata(root: Path) -> dict:
    """Check the exact three-package dependency and CLI contract."""
    errors: list[str] = []
    packages: list[dict] = []
    for relative, expected in PACKAGE_CONTRACTS.items():
        path = root / relative
        if not path.is_file():
            errors.append(f"missing package metadata: {relative}")
            continue
        try:
            project = tomllib.loads(path.read_text(encoding="utf-8"))["project"]
        except (OSError, KeyError, tomllib.TOMLDecodeError) as exc:
            errors.append(f"invalid package metadata {relative}: {exc}")
            continue
        name = project.get("name")
        version = project.get("version")
        dependencies = project.get("dependencies")
        script_name, script_target = expected["script"]
        scripts = project.get("scripts", {})
        if name != expected["name"]:
            errors.append(
                f"{relative}: expected project name {expected['name']!r}, got {name!r}"
            )
        if version != "0.1.0":
            errors.append(f"{relative}: expected version '0.1.0', got {version!r}")
        if dependencies != expected["dependencies"]:
            errors.append(
                f"{relative}: expected dependencies {expected['dependencies']!r}, "
                f"got {dependencies!r}"
            )
        if scripts.get(script_name) != script_target:
            errors.append(
                f"{relative}: expected script {script_name}={script_target!r}, "
                f"got {scripts.get(script_name)!r}"
            )
        packages.append(
            {
                "name": name,
                "version": version,
                "dependencies": dependencies,
                "script": script_name,
            }
        )
    return {"ok": not errors, "packages": packages, "errors": errors}


def audit_git_repository(root: Path) -> list[str]:
    """Validate Git metadata for either a checkout or a linked worktree."""
    try:
        discovered = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        return [f"git rev-parse failed: {exc}"]
    if discovered.returncode != 0:
        detail = discovered.stderr.strip() or discovered.stdout.strip()
        message = "repo root has no Git work-tree toplevel"
        return [message + (f": {detail}" if detail else "")]
    expected_root = root.resolve()
    discovered_root = Path(discovered.stdout.strip()).resolve()
    if discovered_root != expected_root:
        return [
            f"repo root is not the Git work-tree toplevel: expected {expected_root}, "
            f"got {discovered_root}"
        ]

    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "fsck", "--full", "--no-dangling"],
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        return [f"git fsck failed: {exc}"]
    if completed.returncode != 0:
        return [
            "git fsck failed: "
            + (completed.stderr.strip() or completed.stdout.strip())
        ]
    return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--skip-git", action="store_true")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    errors: list[str] = []

    for relative in REQUIRED_FILES:
        path = root / relative
        if not path.is_file():
            errors.append(f"missing required file: {relative}")

    package_report = audit_package_metadata(root)
    errors.extend(package_report["errors"])

    sys.path.insert(0, str(root / "eval_harness" / "src"))
    suite_report = None
    try:
        from opti_eval.validation import validate_repository

        suite_report = validate_repository(root)
        errors.extend(suite_report["errors"])
    except Exception as exc:
        errors.append(f"suite validation crashed: {type(exc).__name__}: {exc}")

    sys.path.insert(0, str(root / "scripts"))
    documentation_report = None
    try:
        from verify_documentation import audit_documentation

        documentation_report = audit_documentation(root)
        errors.extend(documentation_report["errors"])
    except Exception as exc:
        errors.append(f"documentation audit crashed: {type(exc).__name__}: {exc}")

    if not args.skip_git:
        errors.extend(audit_git_repository(root))

    payload = {
        "ok": not errors,
        "repo_root": str(root),
        "required_file_count": len(REQUIRED_FILES),
        "package_metadata_validation": package_report,
        "suite_validation": suite_report,
        "documentation_validation": documentation_report,
        "errors": errors,
    }
    print(json.dumps(payload, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
