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
from .quarantine import QuarantineQueue, flag_fingerprint
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
    """Apply closure rules and persist each run/task/flag fingerprint once."""
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

    existing = queue.flag_fingerprints(task_id=task_id, run_ref=run_ref)
    suspicion_rows = [f.to_dict() for f in suspicions]
    candidate_rows = suspicion_rows + [
        j.to_dict() for j in judgments if j.opinion != "undecidable"
    ]
    handled = set(existing)
    new_rows: list[dict[str, Any]] = []
    for row in candidate_rows:
        fingerprint = flag_fingerprint(task_id=task_id, run_ref=run_ref, flag=row)
        if fingerprint in handled:
            continue
        handled.add(fingerprint)
        new_rows.append(row)
    if not new_rows:
        return {
            "routed": True,
            "deduplicated": True,
            "reason": reason,
            "handled_fingerprints": sorted(existing),
        }

    entry = queue.enqueue(
        task_id=task_id,
        run_ref=run_ref,
        verifier_status=verifier_status,
        reason=reason,
        flags=new_rows,
    )
    return {
        "routed": True,
        "deduplicated": False,
        "entry_id": entry.entry_id,
        "reason": reason,
        "handled_fingerprints": [
            row["fingerprint"] for row in entry.flags if "fingerprint" in row
        ],
    }
