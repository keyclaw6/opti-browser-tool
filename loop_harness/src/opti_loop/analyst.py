"""Analyst interface and the deterministic stub that stands in for it.

The real Analyst is the LLM trace-analysis pipeline specified in
``docs/architecture/ANALYST.md`` — non-scoring, event-addressable, pinned
like a verifier. It cannot exist before conforming real traces exist (ADR-0004
is accepted, but first-bridge conformance is still pending and no browser
bridges exist yet).

Until then, ``StubAnalyst`` produces the same *artifacts* (L0 overview,
cluster assignments) from result records alone, and labels every product
with ``analyst_version: "stub-0"`` so nothing downstream can mistake
placeholder clustering for root-cause analysis. Cluster keys degrade to
``<source>/<status>`` grouping — deliberately crude, structurally honest.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .evaluate import EvalRun

STUB_VERSION = "stub-0"


class Analyst(Protocol):
    version: str

    def distill(
        self, *, iteration: int, run: EvalRun, task_sources: dict[str, str], out_dir: Path
    ) -> dict[str, Any]: ...


@dataclass(slots=True)
class StubAnalyst:
    """Deterministic placeholder for phase C (DISTILL)."""

    version: str = STUB_VERSION

    def distill(
        self, *, iteration: int, run: EvalRun, task_sources: dict[str, str], out_dir: Path
    ) -> dict[str, Any]:
        failed = sorted(
            tid for tid, status in run.statuses.items() if status == "failed"
        )
        infrastructure = sorted(
            tid
            for tid, status in run.statuses.items()
            if status in {"invalid", "error", "skipped"}
        )
        failed_by_cluster: dict[str, list[str]] = {}
        for task_id in failed:
            source = task_sources.get(task_id, "unknown")
            cluster_id = f"stub/{source}/failed"
            failed_by_cluster.setdefault(cluster_id, []).append(task_id)

        analysis = {
            "analyst_version": self.version,
            "iteration": iteration,
            "suite": run.suite_name,
            "summary": {
                "strict_success_rate": run.summary.get("strict_success_rate"),
                "status_counts": run.summary.get("status_counts"),
                "run_valid": run.run_valid,
            },
            "failed_tasks": failed,
            "infrastructure_tasks": infrastructure,
            "failed_by_cluster": failed_by_cluster,
            "limitations": (
                "stub-0 groups failures by source family only; it reads no traces "
                "and identifies no root causes. Replace with the ANALYST.md "
                "pipeline once traces exist. Claims here are NOT root-cause claims."
            ),
        }
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "analysis.json").write_text(
            json.dumps(analysis, indent=2) + "\n", encoding="utf-8"
        )
        (out_dir / "overview.md").write_text(
            _render_overview(analysis), encoding="utf-8"
        )
        return analysis


def _render_overview(analysis: dict[str, Any]) -> str:
    lines = [
        f"# L0 overview — iteration {analysis['iteration']} ({analysis['suite']})",
        "",
        f"- Analyst: `{analysis['analyst_version']}` — placeholder; no trace access, no root causes.",
        f"- Strict success rate: {analysis['summary']['strict_success_rate']}",
        f"- Status counts: {analysis['summary']['status_counts']}",
        f"- Run valid: {analysis['summary']['run_valid']}",
        "",
        "## Failing tasks by (stub) cluster",
        "",
    ]
    for cluster_id, members in sorted(analysis["failed_by_cluster"].items()):
        lines.append(f"- `{cluster_id}` — {len(members)} task(s): {', '.join(members[:6])}"
                     + (" …" if len(members) > 6 else ""))
    if analysis["infrastructure_tasks"]:
        lines += [
            "",
            "## Infrastructure (invalid/error/skipped — never agent failures)",
            "",
            "- " + ", ".join(analysis["infrastructure_tasks"]),
        ]
    lines += ["", f"> {analysis['limitations']}", ""]
    return "\n".join(lines)
