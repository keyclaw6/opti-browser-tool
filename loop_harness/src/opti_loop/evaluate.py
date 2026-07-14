"""Run the evaluation plane (opti-eval) and read back per-task outcomes.

The loop consumes opti-eval strictly as a read-only instrument: it selects
tasks, runs an adapter, and parses the artifacts opti-eval wrote. It never
modifies catalogs, suites, or verifier assets (ADR-0015 plane boundaries).

Result semantics are opti-eval's fail-closed vocabulary:
``passed | failed | invalid | error | skipped`` — invalid/error/skipped are
infrastructure signals, never agent failures.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from opti_eval.adapters.command import CommandAdapter
from opti_eval.adapters.fixture import FixtureAdapter
from opti_eval.catalog import select_tasks
from opti_eval.runner import run_evaluation
from opti_eval.summary import load_run_artifacts


@dataclass(slots=True)
class EvalRun:
    """Parsed view of one opti-eval run directory."""

    output_dir: Path
    suite_name: str
    summary: dict[str, Any]
    statuses: dict[str, str]  # task_id -> status
    rewards: dict[str, float | None]

    @property
    def run_valid(self) -> bool:
        return bool(self.summary.get("run_valid"))

    @property
    def acceptance_decision_eligible(self) -> bool:
        return bool(self.summary.get("acceptance_decision_eligible"))

    @property
    def passed_ids(self) -> set[str]:
        return {tid for tid, status in self.statuses.items() if status == "passed"}

    @property
    def valid_ids(self) -> set[str]:
        return {
            tid
            for tid, status in self.statuses.items()
            if status in {"passed", "failed"}
        }


def build_adapter(adapter_config: dict[str, Any], *, repo_root: Path | None = None):
    kind = adapter_config.get("kind", "fixture")
    if kind == "fixture":
        return FixtureAdapter(
            pass_rate=float(adapter_config.get("pass_rate", 0.55)),
            seed=int(adapter_config.get("seed", 0)),
        )
    if kind == "harness-fixture":
        # Dry-run simulator: the fixture pass rate is read from a file inside
        # the optimizer's writable surface, so a component edit deterministically
        # changes outcomes. Results remain synthetic and non-reportable
        # (inherits FixtureAdapter semantics); verdicts computed over them are
        # watermarked `simulated:` by the gate. Plumbing rehearsal only.
        default_rate = float(adapter_config.get("default_pass_rate", 0.55))
        rate = default_rate
        rel = adapter_config.get("file")
        if rel and repo_root is not None:
            path = repo_root / str(rel)
            if path.is_file():
                try:
                    rate = float(path.read_text(encoding="utf-8").strip())
                except ValueError:
                    rate = default_rate
        return FixtureAdapter(pass_rate=rate, seed=int(adapter_config.get("seed", 0)))
    if kind == "command":
        return CommandAdapter(
            adapter_config["command"],
            timeout_seconds=int(adapter_config.get("timeout_seconds", 1800)),
        )
    raise ValueError(
        f"unsupported adapter kind {kind!r} (registry adapters arrive with the source bridges)"
    )


def run_suite(
    *,
    repo_root: Path,
    suite_name: str,
    adapter_config: dict[str, Any],
    output_dir: Path,
    task_ids: list[str] | None = None,
    max_workers: int = 4,
) -> EvalRun:
    suite, tasks = select_tasks(repo_root, suite_name, task_ids=task_ids)
    run_evaluation(
        repo_root=repo_root,
        suite=suite,
        tasks=tasks,
        adapter=build_adapter(adapter_config, repo_root=repo_root),
        output_dir=output_dir,
        max_workers=max_workers,
        overwrite=False,
    )
    return _parse_run(output_dir, suite_name)


def load_run(output_dir: Path, suite_name: str) -> EvalRun:
    return _parse_run(output_dir, suite_name)


def _parse_run(output_dir: Path, suite_name: str) -> EvalRun:
    summary, results = load_run_artifacts(output_dir)
    statuses: dict[str, str] = {}
    rewards: dict[str, float | None] = {}
    for row in results:
        task_id = row["task_id"]
        statuses[task_id] = row["status"]
        rewards[task_id] = row.get("reward")
    return EvalRun(
        output_dir=output_dir,
        suite_name=suite_name,
        summary=summary,
        statuses=statuses,
        rewards=rewards,
    )
