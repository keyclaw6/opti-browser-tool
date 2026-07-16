"""Iteration packet: what the optimizer receives at the start of phase D.

Mirrors AHE's "read analysis first" discipline: the packet points the
optimizer at the pre-built analysis, the ranked clusters, the ledger tail,
and the runbook — and stamps whether this iteration is divergent
(ADR-0015 §9). The packet is data for the optimizer; PROGRAM.md is law.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .ledger import read_rows


def build_packet(
    *,
    iteration_dir: Path,
    iteration: int,
    campaign_id: str,
    divergent: bool,
    ranked_clusters: list[tuple[str, dict[str, Any]]],
    ledger_path: Path,
    baseline_summary: dict[str, Any],
    candidate_allowlist: list[str],
    latest_learning_record: dict[str, Any] | None,
) -> Path:
    top = ranked_clusters[:5]
    ledger_tail = read_rows(ledger_path)[-3:]
    payload = {
        "iteration": iteration,
        "campaign": campaign_id,
        "divergent": divergent,
        "top_clusters": [
            {
                "cluster_id": cid,
                "priority": round(
                    float(c.get("total_failures", 0)) * (1.0 - float(c.get("resolution_rate", 0.0))), 2
                ),
                "status": c.get("status"),
                "suspected_component": c.get("suspected_component"),
                "member_count": len(c.get("members", [])),
            }
            for cid, c in top
        ],
        "baseline": {
            "strict_success_rate": baseline_summary.get("strict_success_rate"),
            "status_counts": baseline_summary.get("status_counts"),
        },
        "candidate_allowlist": list(candidate_allowlist),
        "latest_learning_record": latest_learning_record,
    }
    (iteration_dir / "packet.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )

    lines = [
        f"# Iteration packet — {campaign_id} / iter-{iteration:04d}",
        "",
        "Read `PROGRAM.md` at the repository root before acting. It is the law;",
        "this packet is the situation.",
        "",
        f"**Mode:** {'DIVERGENT — do not target the top cluster; test an architecture-class hypothesis (ADR-0015 §9)' if divergent else 'cluster-targeted — attack the highest-priority unresolved cluster below'}",
        "",
        f"Baseline strict success rate: {baseline_summary.get('strict_success_rate')}",
        "",
        "## Ranked unresolved clusters",
        "",
    ]
    if top:
        for cid, cluster in top:
            lines.append(
                f"- `{cid}` — priority {payload['top_clusters'][[c[0] for c in top].index(cid)]['priority']}, "
                f"status {cluster.get('status')}, members {len(cluster.get('members', []))}, "
                f"suspected component `{cluster.get('suspected_component')}`"
            )
    else:
        lines.append("- (register is empty — first iteration)")
    lines += [
        "",
        "## Where to read",
        "",
        "- Analysis: `analysis/overview.md` (+ `analysis/analysis.json`) in this iteration directory",
        "- Baseline evaluation artifacts: `eval/dev_baseline/`",
        "- Recent ledger rows: `packet.json` → see campaign `ledger.jsonl` for full history",
        "- Latest validated learning: `packet.json` → `latest_learning_record`",
        "",
        "## What to produce",
        "",
        "1. One hypothesis and one commit whose complete diff stays inside the frozen candidate allowlist: "
        + ", ".join(f"`{prefix}`" for prefix in candidate_allowlist),
        "2. `manifest.json` in the candidate worktree root; the optimizer-input experiment branch of canonical `schemas/experiment.schema.json` requires `target_component` and `cluster_ref`. `target_component` is attribution only, not path authority.",
        "3. Then ask the conductor to gate: `opti-loop run-iteration --campaign <id>`.",
        "",
    ]
    if ledger_tail:
        lines += ["## Ledger tail", ""]
        for row in ledger_tail:
            lines.append(
                f"- iter {row.get('iteration')}: {row.get('verdict')} — {row.get('hypothesis', '')[:100]}"
            )
        lines.append("")
    path = iteration_dir / "PACKET.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
