"""Typed gate verdict (F04).

The old design carried the verdict as a string and tested
``verdict.endswith("accepted")`` — so ``simulated:accepted`` (a fixture
rehearsal that can never be benchmark evidence) mutated real campaign state:
it advanced ``accepted_iterations``, set the drift baseline, and emitted
promotion candidates. The end-to-end test even asserted that bug.

The fix is a closed, typed verdict. **Only** ``decision == "accepted"`` AND
``evidence_class == "benchmark"`` may advance real accepted state. Every other
combination — including any ``simulated`` rehearsal — is inert for promotion,
drift baselining, cross-campaign ranking, and campaign continuation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DECISIONS = ("accepted", "rejected", "inconclusive", "invalid")
EVIDENCE_CLASSES = ("benchmark", "simulated")


@dataclass(slots=True, frozen=True)
class Verdict:
    decision: str          # accepted | rejected | inconclusive | invalid
    evidence_class: str    # benchmark | simulated

    def __post_init__(self) -> None:
        if self.decision not in DECISIONS:
            raise ValueError(f"decision must be one of {DECISIONS}: {self.decision!r}")
        if self.evidence_class not in EVIDENCE_CLASSES:
            raise ValueError(
                f"evidence_class must be one of {EVIDENCE_CLASSES}: {self.evidence_class!r}"
            )

    @property
    def advances_accepted_state(self) -> bool:
        """The single predicate that may mutate real accepted campaign state."""
        return self.decision == "accepted" and self.evidence_class == "benchmark"

    @property
    def label(self) -> str:
        prefix = "simulated:" if self.evidence_class == "simulated" else ""
        return f"{prefix}{self.decision}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "evidence_class": self.evidence_class,
            "label": self.label,
            "advances_accepted_state": self.advances_accepted_state,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Verdict":
        return cls(decision=str(payload["decision"]), evidence_class=str(payload["evidence_class"]))
