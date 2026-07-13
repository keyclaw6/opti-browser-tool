"""Calibration corpus and judge trust gating (ADR-0016).

The corpus accumulates labeled cases from three sources — probe-kit archives,
quarantine resolutions, and deliberate manual labels — and is the ONLY basis
on which a T2 judge earns trust. ``measure`` computes per-judge, per-source
precision/recall against ground truth; ``trusted`` applies the role's
operating point plus a minimum case count.

Until a judge is trusted, its flags are diagnostic text with
``trusted: false`` — no consumer may branch on them (the loop gate never
reads untrusted flags).
"""
from __future__ import annotations

import datetime as _dt
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

GROUND_TRUTHS = ("success", "failure", "undecidable")


class CorpusStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def _rows(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        return [
            json.loads(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def add_case(
        self,
        *,
        source: str,
        task_id: str,
        run_ref: str,
        ground_truth: str,
        detail: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if ground_truth not in GROUND_TRUTHS:
            raise ValueError(f"ground_truth must be one of {GROUND_TRUTHS}")
        row = {
            "case_id": uuid.uuid4().hex[:12],
            "source": source,  # probe | quarantine | manual
            "task_id": task_id,
            "run_ref": run_ref,
            "ground_truth": ground_truth,
            "detail": detail or {},
            "judge_outputs": {},
            "created_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
        return row

    def record_judge_output(self, case_id: str, judge_id: str, opinion: str) -> None:
        """Attach a judge's opinion (success|failure|undecidable) to a case."""
        rows = self._rows()
        hit = False
        for row in rows:
            if row["case_id"] == case_id:
                row["judge_outputs"][judge_id] = opinion
                hit = True
        if not hit:
            raise KeyError(f"no corpus case {case_id}")
        self.path.write_text(
            "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows),
            encoding="utf-8",
        )

    def stats(self) -> dict[str, Any]:
        rows = self._rows()
        by_source: dict[str, int] = {}
        by_truth: dict[str, int] = {}
        for row in rows:
            by_source[row["source"]] = by_source.get(row["source"], 0) + 1
            by_truth[row["ground_truth"]] = by_truth.get(row["ground_truth"], 0) + 1
        return {"cases": len(rows), "by_source": by_source, "by_ground_truth": by_truth}

    # ── measurement ──────────────────────────────────────────────────────
    def measure(self, judge_id: str, *, positive: str = "success") -> dict[str, Any]:
        """Precision/recall of one judge's recorded opinions vs ground truth.

        ``positive`` defines the direction being measured (a cross-examiner
        hunting false positives is measured with positive='failure' — how
        reliably it catches wrong passes).
        """
        rows = [
            row
            for row in self._rows()
            if judge_id in row["judge_outputs"]
            and row["ground_truth"] in {"success", "failure"}
        ]
        tp = fp = fn = tn = 0
        for row in rows:
            truth_positive = row["ground_truth"] == positive
            judged_positive = row["judge_outputs"][judge_id] == positive
            if judged_positive and truth_positive:
                tp += 1
            elif judged_positive and not truth_positive:
                fp += 1
            elif not judged_positive and truth_positive:
                fn += 1
            else:
                tn += 1
        precision = tp / (tp + fp) if (tp + fp) else None
        recall = tp / (tp + fn) if (tp + fn) else None
        return {
            "judge_id": judge_id,
            "positive_class": positive,
            "cases_measured": len(rows),
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "tn": tn,
            "precision": round(precision, 4) if precision is not None else None,
            "recall": round(recall, 4) if recall is not None else None,
        }


@dataclass(slots=True)
class OperatingPoint:
    min_cases: int = 25
    min_precision: float | None = None
    min_recall: float | None = None


def trusted(measurement: dict[str, Any], point: OperatingPoint) -> bool:
    """Trust gate: enough cases AND the role's operating point is met."""
    if measurement["cases_measured"] < point.min_cases:
        return False
    if point.min_precision is not None:
        if measurement["precision"] is None or measurement["precision"] < point.min_precision:
            return False
    if point.min_recall is not None:
        if measurement["recall"] is None or measurement["recall"] < point.min_recall:
            return False
    return True
