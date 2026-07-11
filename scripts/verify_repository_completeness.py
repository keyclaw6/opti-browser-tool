#!/usr/bin/env python3
"""Fail-closed completeness check for the reconstructed repository."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REQUIRED_FILES = [
    "README.md",
    "RECOVERY_MANIFEST.md",
    "PROJECT_CHARTER.md",
    "docs/DECISION_PROCESS.md",
    "docs/DECISION_REGISTER.md",
    "docs/adr/0001-project-constitution.md",
    "docs/adr/0012-reference-success-band-35-to-70.md",
    "docs/adr/0014-run-all-140-candidates-before-filtering.md",
    "research/benchmarks/task-candidates/batch-1-candidates.jsonl",
    "research/benchmarks/task-candidates/batch-1-candidates.csv",
    "research/benchmarks/task-candidates/batch-1-sources.lock.json",
    "evals/catalog/tasks.jsonl",
    "evals/catalog/tasks.csv",
    "evals/catalog/task-index.json",
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
    "archive/superseded/runnable-suite-v0-100/README.md",
    "validation/repository-validation.json",
    "validation/fixture-140-summary.json",
    "validation/unit-tests.txt",
]


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

    sys.path.insert(0, str(root / "eval_harness" / "src"))
    try:
        from opti_eval.validation import validate_repository

        report = validate_repository(root)
        errors.extend(report["errors"])
    except Exception as exc:
        errors.append(f"suite validation crashed: {type(exc).__name__}: {exc}")
        report = None

    if not args.skip_git:
        if not (root / ".git").is_dir():
            errors.append("missing .git directory")
        else:
            completed = subprocess.run(
                ["git", "-C", str(root), "fsck", "--full"],
                text=True,
                capture_output=True,
                check=False,
            )
            if completed.returncode != 0:
                errors.append(f"git fsck failed: {completed.stderr.strip()}")

    payload = {
        "ok": not errors,
        "repo_root": str(root),
        "required_file_count": len(REQUIRED_FILES),
        "suite_validation": report,
        "errors": errors,
    }
    print(json.dumps(payload, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
