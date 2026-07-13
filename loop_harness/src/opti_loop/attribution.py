"""Attribution: falsify the manifest's predictions against observed flips.

From agentic-harness-engineering: every change predicts the tasks it should
fix; the next evaluation falsifies it, and the verdict is KEEP / IMPROVE
(partial) / ROLLBACK+PIVOT. This project computes attribution synchronously
— the gate runs the treatment evaluation inside the same iteration — so the
verdict lands in the same iteration record rather than one loop later.

Per ADR-0015 §8 the risk list is measured for prediction accuracy but never
used to protect the gate.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .compare import Comparison
from .manifest import predicted_task_ids

VERDICTS = ("keep", "partial", "revert")


@dataclass(slots=True)
class Attribution:
    verdict: str
    verified_fixes: list[str] = field(default_factory=list)
    missed_fixes: list[str] = field(default_factory=list)
    unpredicted_fixes: list[str] = field(default_factory=list)
    predicted_risks: list[str] = field(default_factory=list)
    materialized_regressions: list[str] = field(default_factory=list)
    fix_precision: float | None = None
    fix_recall: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "verified_fixes": self.verified_fixes,
            "missed_fixes": self.missed_fixes,
            "unpredicted_fixes": self.unpredicted_fixes,
            "predicted_risks": self.predicted_risks,
            "materialized_regressions": self.materialized_regressions,
            "fix_precision": self.fix_precision,
            "fix_recall": self.fix_recall,
            "note": "risk list is diagnostic only; it never protects the gate (ADR-0015 §8)",
        }


def attribute(manifest: dict, comparison: Comparison) -> Attribution:
    predicted = predicted_task_ids(manifest)
    risks: set[str] = set()
    for entry in manifest.get("regression_risks", []) or []:
        for task in entry.get("tasks", []) or []:
            risks.add(str(task))

    fixed = set(comparison.fixed)
    regressed = set(comparison.regressed)

    verified = sorted(predicted & fixed)
    missed = sorted(predicted - fixed)
    unpredicted = sorted(fixed - predicted)

    fix_precision = round(len(verified) / len(fixed), 4) if fixed else None
    fix_recall = round(len(verified) / len(predicted), 4) if predicted else None

    if verified and not regressed:
        verdict = "keep"
    elif verified or (fixed and not regressed):
        verdict = "partial"
    else:
        verdict = "revert"

    return Attribution(
        verdict=verdict,
        verified_fixes=verified,
        missed_fixes=missed,
        unpredicted_fixes=unpredicted,
        predicted_risks=sorted(risks),
        materialized_regressions=sorted(regressed),
        fix_precision=fix_precision,
        fix_recall=fix_recall,
    )
