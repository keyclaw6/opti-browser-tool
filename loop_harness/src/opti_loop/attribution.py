"""Attribution: falsify the manifest's predictions against observed flips.

From agentic-harness-engineering: every change predicts the tasks it should
fix; the evaluation falsifies it, and the verdict is KEEP / PARTIAL /
REVERT. Per ADR-0015 §8 the regression-risk list is measured for prediction
accuracy but never used to protect the gate.

Fixes from the review (F09):

- **Correct metric definitions.** ``prediction_precision`` = verified /
  predicted (of what you predicted, how much came true); ``flip_recall`` =
  verified / actually-fixed (of the real flips, how many you predicted). The
  old code swapped these labels, hiding shotgun predictions.
- **Shotgun guard.** Predicting the whole catalog to catch one lucky flip now
  scores near-zero precision; the gate enforces a precision floor, so a broad
  prediction net cannot buy acceptance.
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
    predicted_count: int = 0
    verified_fixes: list[str] = field(default_factory=list)
    missed_predictions: list[str] = field(default_factory=list)
    unpredicted_fixes: list[str] = field(default_factory=list)
    predicted_risks: list[str] = field(default_factory=list)
    materialized_regressions: list[str] = field(default_factory=list)
    prediction_precision: float | None = None  # verified / predicted
    flip_recall: float | None = None           # verified / actually-fixed

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "predicted_count": self.predicted_count,
            "verified_fixes": self.verified_fixes,
            "missed_predictions": self.missed_predictions,
            "unpredicted_fixes": self.unpredicted_fixes,
            "predicted_risks": self.predicted_risks,
            "materialized_regressions": self.materialized_regressions,
            "prediction_precision": self.prediction_precision,
            "flip_recall": self.flip_recall,
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

    # Correct definitions (F09): precision over predictions, recall over flips.
    prediction_precision = round(len(verified) / len(predicted), 4) if predicted else None
    flip_recall = round(len(verified) / len(fixed), 4) if fixed else None

    if verified and not regressed:
        verdict = "keep"
    elif verified or (fixed and not regressed):
        verdict = "partial"
    else:
        verdict = "revert"

    return Attribution(
        verdict=verdict,
        predicted_count=len(predicted),
        verified_fixes=verified,
        missed_predictions=missed,
        unpredicted_fixes=unpredicted,
        predicted_risks=sorted(risks),
        materialized_regressions=sorted(regressed),
        prediction_precision=prediction_precision,
        flip_recall=flip_recall,
    )
