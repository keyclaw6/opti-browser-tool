"""Disagreement routing: where the error-direction closure becomes code.

ADR-0016's two chains:

- **FP defense**: verifier ``passed`` + fp_suspect/side_effect suspicion
  → quarantine ("possible false positive").
- **FN recovery**: verifier ``failed`` + fn_suspect suspicion → quarantine
  tagged for the FN-suspect queue; the remedy on resolution is a verifier or
  task repair (which must re-run its probe kit), never a score override.

Routing consumes T1 flags always, and T2 judgments only when ``trusted``
(untrusted opinions may still be *recorded* in the entry as context, but they
cannot trigger quarantine on their own except through the adjudicator's
explicit resolution)."""
from __future__ import annotations

from typing import Any

from .panel import Judgment
from .quarantine import QuarantineQueue
from .t1_checks import Flag


def route(
    *,
    queue: QuarantineQueue,
    task_id: str,
    run_ref: str,
    verifier_status: str,
    t1_flags: list[Flag],
    judgments: list[Judgment] | None = None,
) -> dict[str, Any]:
    """Apply the closure rules; enqueue at most one entry per run/task."""
    judgments = judgments or []
    suspicions = [f for f in t1_flags if f.severity == "suspicion"]
    fp_evidence = [f for f in suspicions if f.direction in {"fp_suspect", "side_effect"}]
    fn_evidence = [f for f in suspicions if f.direction == "fn_suspect"]

    trusted_disagreements = [
        j
        for j in judgments
        if j.trusted
        and j.opinion != "undecidable"
        and j.opinion != ("success" if verifier_status == "passed" else "failure")
    ]

    reason: str | None = None
    if verifier_status == "passed" and (fp_evidence or trusted_disagreements):
        reason = "possible false positive: verifier passed against contrary evidence"
    elif verifier_status == "failed" and (fn_evidence or trusted_disagreements):
        reason = (
            "possible false negative (FN-suspect queue): remedy is verifier/task "
            "repair + probe-kit re-run, never a score override"
        )

    if reason is None:
        return {"routed": False, "reason": "no qualifying disagreement"}

    entry = queue.enqueue(
        task_id=task_id,
        run_ref=run_ref,
        verifier_status=verifier_status,
        reason=reason,
        flags=[f.to_dict() for f in suspicions]
        + [j.to_dict() for j in judgments if j.opinion != "undecidable"],
    )
    return {"routed": True, "entry_id": entry.entry_id, "reason": reason}
