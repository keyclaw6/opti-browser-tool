"""Machine-readable decision ledger: phase F (RECORD).

One JSONL row per iteration. Canonical learning persistence lives in
``learning.py`` and is cited into the next optimizer packet.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from opti_eval.models import split_lf_jsonl_records, strict_json_loads

LEDGER_ROW_FIELDS = frozenset({
    "iteration",
    "campaign",
    "verdict",
    "decision",
    "evidence_class",
    "advances_accepted_state",
    "divergent",
    "base_sha",
    "candidate_sha",
    "protocol_digest",
    "hypothesis",
    "target_component",
    "cluster_ref",
    "gate_rungs",
    "comparison",
    "attribution",
    "eligibility",
    "fixed_variables",
    "promotion_candidates",
})


def _validate_row(row: object, *, row_number: int) -> dict[str, Any]:
    if type(row) is not dict:
        raise ValueError(f"ledger row {row_number} must be a JSON object")
    missing = sorted(LEDGER_ROW_FIELDS - set(row))
    extra = sorted(set(row) - LEDGER_ROW_FIELDS)
    if missing or extra:
        details = []
        if missing:
            details.append("missing fields: " + ", ".join(missing))
        if extra:
            details.append("extra fields: " + ", ".join(extra))
        raise ValueError(
            f"ledger row {row_number} has an invalid closed shape; "
            + "; ".join(details)
        )
    return row


def append_row(ledger_path: Path, row: dict[str, Any]) -> None:
    existing = read_rows(ledger_path)
    checked = _validate_row(row, row_number=len(existing) + 1)
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(checked, sort_keys=True) + "\n")


def read_rows(ledger_path: Path) -> list[dict[str, Any]]:
    if not ledger_path.is_file():
        return []
    with ledger_path.open("r", encoding="utf-8", newline="") as handle:
        text = handle.read()
    if text == "":
        return []
    records = split_lf_jsonl_records(text, field_name="ledger JSONL")
    rows: list[dict[str, Any]] = []
    for line_number, record in enumerate(records, start=1):
        try:
            parsed = strict_json_loads(
                record, field_name=f"ledger row {line_number}"
            )
        except ValueError as exc:
            raise ValueError(f"ledger row {line_number} is invalid: {exc}") from exc
        rows.append(_validate_row(parsed, row_number=line_number))
    return rows
