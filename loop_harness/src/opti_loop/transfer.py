"""Transfer-bet falsification protocol (F17).

The charter bets that harness deltas found on a cheap fixed executor
(MiniMax-M3) transfer to stronger models and unseen sites/layouts. The review's
blocking finding: nothing in the loop could ever tell the owner the bet FAILED
— the only comparator declared different executors non-comparable, so a long
run of executor-specific "wins" would look like progress forever.

This module makes the bet falsifiable. It does not need stronger models to
exist yet; it pre-registers WHAT will be measured and the sign-reversal
criterion that rejects the bet, and evaluates that criterion once transfer
results are supplied (by the owner's external stronger-model runs, since those
models are OQ-17 and not wired here).

A checkpoint compares an ACCEPTED harness version against its base on:
  - discovery-excluded tasks (never used to invent the change),
  - unseen site/layout families, and
  - a fixed panel of stronger executors,
storing per-model and per-failure-class deltas, repeats, uncertainty, and cost.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class TransferCheckpointPlan:
    campaign_id: str
    accepted_iterations: list[int]
    checkpoint_every: int
    reject_criterion: str
    measures: list[str] = field(default_factory=lambda: [
        "per-model pass@1 delta (accepted harness vs its base) on discovery-excluded tasks",
        "per-failure-class delta on unseen site/layout families",
        "repeats and uncertainty band per model",
        "token/cost delta per model",
    ])
    stronger_model_panel: list[str] = field(default_factory=lambda: [
        "<pin stronger executors here — OQ-17; e.g. a frontier model + one mid-tier>",
    ])

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaign": self.campaign_id,
            "accepted_iterations": self.accepted_iterations,
            "checkpoint_every": self.checkpoint_every,
            "reject_criterion": self.reject_criterion,
            "measures": self.measures,
            "stronger_model_panel": self.stronger_model_panel,
            "status": "pre-registered; awaiting stronger-model runs (OQ-17)",
        }


def plan_checkpoint(campaign) -> TransferCheckpointPlan:
    cfg = campaign.config.get("transfer", {})
    return TransferCheckpointPlan(
        campaign_id=campaign.campaign_id,
        accepted_iterations=list(campaign.state.get("accepted_iterations", [])),
        checkpoint_every=int(cfg.get("checkpoint_every", 5)),
        reject_criterion=str(cfg.get("reject_bet_if", "median per-model transfer delta <= 0")),
    )


def evaluate_checkpoint(deltas_by_model: dict[str, float]) -> dict[str, Any]:
    """Apply the predeclared criterion to supplied per-model transfer deltas.

    ``deltas_by_model``: stronger-model → (accepted − base) pass@1 delta on the
    discovery-excluded / unseen-family transfer set. The bet is REJECTED when
    the median transfer delta is non-positive: gains did not transfer.
    """
    if not deltas_by_model:
        return {"decision": "insufficient_evidence", "reason": "no stronger-model deltas supplied"}
    median = statistics.median(deltas_by_model.values())
    positive = sum(1 for d in deltas_by_model.values() if d > 0)
    bet_rejected = median <= 0.0
    return {
        "median_transfer_delta": round(median, 4),
        "models_with_positive_transfer": positive,
        "models_total": len(deltas_by_model),
        "bet_rejected": bet_rejected,
        "decision": "REJECT_TRANSFER_BET" if bet_rejected else "transfer_supported",
        "note": "non-positive median transfer delta means the cheap-executor bet failed (F17)",
    }
