"""Ledger and learnings: phase F (RECORD).

One JSONL row per iteration — machine-readable history (auto-harness's
results.tsv, upgraded to carry attribution and gate evidence). One learnings
entry per iteration, pass or fail — the optimizer's only persistent memory
(auto-harness learnings.md; AHE evolution_history.md).
"""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Any


def append_row(ledger_path: Path, row: dict[str, Any]) -> None:
    row = dict(row)
    row.setdefault("recorded_at", _dt.datetime.now(_dt.timezone.utc).isoformat())
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def read_rows(ledger_path: Path) -> list[dict[str, Any]]:
    if not ledger_path.is_file():
        return []
    return [
        json.loads(line)
        for line in ledger_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def learnings_template(
    *,
    iteration: int,
    verdict: str,
    hypothesis: str,
    target_component: str,
    cluster_ref: str,
    divergent: bool,
) -> str:
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    kind = "divergent (exploration)" if divergent else "cluster-targeted"
    return (
        f"\n## Iteration {iteration:04d} — {verdict} — {stamp}\n\n"
        f"- Kind: {kind}\n"
        f"- Cluster: `{cluster_ref}` · Component: `{target_component}`\n"
        f"- Hypothesis: {hypothesis}\n"
        f"- What the evidence showed: <fill in — required even on failure>\n"
        f"- Why the prediction was right/wrong: <fill in before any retry>\n"
        f"- Needs from human: <or 'none'>\n"
    )


def append_learnings(learnings_path: Path, entry: str) -> None:
    with learnings_path.open("a", encoding="utf-8") as handle:
        handle.write(entry)
