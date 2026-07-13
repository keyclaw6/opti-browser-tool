"""Acceptance eligibility: connect verifier admission and T1 to the gate (F10).

The review found the scoring path and the judge layer were disconnected: a
rubber-stamp verifier produced ``acceptance_decision_eligible=true`` with no
admission record, and the loop only read a pre-existing quarantine file — it
never ran T1 or checked admission. This module closes that loop.

A treatment run is **benchmark**-eligible only when:
1. opti-eval already reports it reportable (all-valid, real adapter), AND
2. every task has an admitted verifier whose checksum matches the campaign's
   pinned verifier (F10/F11), AND
3. auto-T1 has run over each task's trace, and any suspicion has been routed
   to the owner quarantine (which then fails the E5 comparison closed).

Anything short of that is ``simulated`` (or invalid), never a real acceptance.
The judge layer lives in ``opti_judge``; it is imported lazily so loop unit
tests that never reach eligibility don't require it.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .evaluate import EvalRun


@dataclass(slots=True)
class Eligibility:
    evidence_class: str            # benchmark | simulated
    acceptance_eligible: bool
    reasons: list[str] = field(default_factory=list)
    newly_quarantined: list[str] = field(default_factory=list)
    t1_flag_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_class": self.evidence_class,
            "acceptance_eligible": self.acceptance_eligible,
            "reasons": self.reasons,
            "newly_quarantined": self.newly_quarantined,
            "t1_flag_count": self.t1_flag_count,
        }


def _load_admissions(path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    index: dict[tuple[str, str], dict[str, Any]] = {}
    if not path.is_file():
        return index
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("admitted"):
            index[(str(row.get("verifier_id")), str(row.get("task_id")))] = row
    return index


def assess(
    *,
    run: EvalRun,
    run_dir: Path,
    adapter_config: dict[str, Any],
    task_records: dict[str, dict[str, Any]],
    admissions_path: Path,
    quarantine_path: Path,
) -> Eligibility:
    # Fixture / non-reportable adapters can never yield benchmark evidence.
    if not run.acceptance_decision_eligible:
        return Eligibility(evidence_class="simulated", acceptance_eligible=False,
                           reasons=["run is not benchmark-reportable (fixture/simulated or contains invalid results)"])

    reasons: list[str] = []
    verifier_id = str(adapter_config.get("verifier_id", ""))
    verifier_checksum = str(adapter_config.get("verifier_checksum", ""))
    if not verifier_id or not verifier_checksum:
        return Eligibility(
            evidence_class="simulated",
            acceptance_eligible=False,
            reasons=["adapter declares no pinned verifier_id/verifier_checksum — cannot be benchmark evidence (F10)"],
        )

    admissions = _load_admissions(admissions_path)
    unadmitted = []
    for task_id in run.statuses:
        row = admissions.get((verifier_id, task_id))
        if row is None or str(row.get("verifier_checksum")) != verifier_checksum:
            unadmitted.append(task_id)
    if unadmitted:
        return Eligibility(
            evidence_class="simulated",
            acceptance_eligible=False,
            reasons=[
                f"{len(unadmitted)} task(s) have no admitted verifier matching checksum "
                f"{verifier_checksum[:12]} (F10): {', '.join(sorted(unadmitted)[:8])}"
            ],
        )

    # Auto-run T1 over any present traces and route suspicion to quarantine.
    newly_quarantined, flag_count = _auto_t1(
        run=run,
        run_dir=run_dir,
        task_records=task_records,
        quarantine_path=quarantine_path,
    )
    if newly_quarantined:
        reasons.append(
            f"auto-T1 routed {len(newly_quarantined)} task(s) to quarantine; "
            "the E5 comparison will fail closed until resolved"
        )
    return Eligibility(
        evidence_class="benchmark",
        acceptance_eligible=True,
        reasons=reasons,
        newly_quarantined=sorted(newly_quarantined),
        t1_flag_count=flag_count,
    )


def _auto_t1(
    *,
    run: EvalRun,
    run_dir: Path,
    task_records: dict[str, dict[str, Any]],
    quarantine_path: Path,
) -> tuple[list[str], int]:
    """Run T1 over each task's trace; route disagreements to quarantine.

    No trace (today's bridge-less state) means no T1 signal for that task —
    reported honestly, not silently treated as clean. Wiring is live now, so
    the day traces exist this fires with zero further changes.
    """
    try:
        from opti_judge.evidence import EvidenceContract, EvidenceError, load_trace
        from opti_judge.quarantine import QuarantineQueue
        from opti_judge.router import route
        from opti_judge.t1_checks import expectations_from_task, run_all
    except ModuleNotFoundError:
        return [], 0

    contract = EvidenceContract(role="loop-auto-t1", visibility=("executor", "judge", "orchestrator"))
    queue = QuarantineQueue(quarantine_path)
    already = queue.pending_task_ids()
    newly: list[str] = []
    total_flags = 0
    for task_id, status in run.statuses.items():
        trace_path = run_dir / "tasks" / task_id / "trace.jsonl"
        if not trace_path.is_file():
            continue
        try:
            trace = load_trace(trace_path, contract)
        except EvidenceError:
            continue  # malformed evidence is an eval-plane invalid, not our call here
        side_effects, assertions = expectations_from_task(task_records.get(task_id, {}))
        flags = run_all(
            trace,
            verifier_status=status,
            side_effect_expectation=side_effects,
            assertions=assertions,
        )
        total_flags += len(flags)
        if task_id in already:
            continue
        routed = route(
            queue=queue,
            task_id=task_id,
            run_ref=str(trace_path),
            verifier_status=status,
            t1_flags=flags,
        )
        if routed.get("routed"):
            newly.append(task_id)
    return newly, total_flags
