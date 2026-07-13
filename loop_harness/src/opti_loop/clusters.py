"""Failure-cluster register: the loop's unit of analysis.

From the neosigma method article: every failure enters a candidates pool,
is grouped by shared root-cause mechanism, and clusters are prioritized by
high ``total_failures`` × low ``resolution_rate``. Record shape per
``docs/architecture/ANALYST.md`` §4.

The register is data; the intelligence that fills ``taxonomy_class`` and
``suspected_component`` correctly is the Analyst's job (LLM pipeline,
pending). The stub Analyst in this package produces placeholder clusters
that are explicitly labeled as such.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

RESOLUTION_STATUSES = (
    "unresolved",
    "improving",
    "resolved",
    "reopened",
    "quarantined-verifier-suspect",
)


def load_register(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"schema_version": "0.1-draft", "clusters": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def save_register(path: Path, register: dict[str, Any]) -> None:
    path.write_text(json.dumps(register, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def priority(cluster: dict[str, Any]) -> float:
    total = int(cluster.get("total_failures", 0))
    resolution_rate = float(cluster.get("resolution_rate", 0.0))
    return total * (1.0 - resolution_rate)


def ranked_unresolved(register: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    rows = [
        (cluster_id, cluster)
        for cluster_id, cluster in register.get("clusters", {}).items()
        if cluster.get("status") in {"unresolved", "improving", "reopened"}
    ]
    return sorted(rows, key=lambda row: (-priority(row[1]), row[0]))


def update_after_iteration(
    register: dict[str, Any],
    *,
    iteration: int,
    failed_by_cluster: dict[str, list[str]],
    fixed_task_ids: set[str],
    analyst_version: str,
) -> dict[str, Any]:
    """Fold one iteration's outcomes into the register.

    ``failed_by_cluster``: cluster_id -> member task_ids observed failing this
    iteration (as assigned by the Analyst). ``fixed_task_ids``: tasks that
    flipped fail->pass in an accepted change this iteration.
    """
    clusters = register.setdefault("clusters", {})
    for cluster_id, members in failed_by_cluster.items():
        cluster = clusters.setdefault(
            cluster_id,
            {
                "cluster_id": cluster_id,
                "taxonomy_class": "unclassified",
                "suspected_component": "unassigned",
                "members": [],
                "first_seen": f"iter-{iteration:04d}",
                "total_failures": 0,
                "resolution_rate": 0.0,
                "status": "unresolved",
                "resolution_history": [],
                "analyst_version": analyst_version,
            },
        )
        known = {member["task_id"] for member in cluster["members"]}
        for task_id in members:
            if task_id not in known:
                cluster["members"].append(
                    {"task_id": task_id, "first_failed": f"iter-{iteration:04d}"}
                )
        cluster["total_failures"] = int(cluster["total_failures"]) + len(members)
        cluster["analyst_version"] = analyst_version
        if cluster["status"] == "resolved":
            cluster["status"] = "reopened"

    for cluster in clusters.values():
        member_ids = {member["task_id"] for member in cluster["members"]}
        if not member_ids:
            continue
        fixed_here = member_ids & fixed_task_ids
        if fixed_here:
            cluster["resolution_rate"] = round(len(fixed_here) / len(member_ids), 4)
            cluster["status"] = (
                "resolved" if fixed_here == member_ids else "improving"
            )
            cluster["resolution_history"].append(
                {
                    "iteration": f"iter-{iteration:04d}",
                    "fixed": sorted(fixed_here),
                    "outcome": cluster["status"],
                }
            )
    return register
