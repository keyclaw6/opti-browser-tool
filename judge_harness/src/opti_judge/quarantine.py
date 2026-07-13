"""T3 quarantine queue: unresolved disagreement goes to the project owner.

The adjudication tie rule (ADR-0016) is structural here: nothing in this
module can modify a score. A quarantine entry is created when layers
disagree (T0 pass + fp_suspect flags; T0 fail + fn_suspect flags; verifier
vs assertion conflicts), and only a human resolution closes it.

Resolutions append to the calibration corpus automatically — the corpus is
a by-product of operating the system, not a separate labeling project.

FN recovery discipline: when a resolution says the verifier was wrong, the
recorded remedy is a *verifier or task repair* (which must re-run its probe
kit), never a score override — the ``resolution`` vocabulary has no
"override score" option on purpose.
"""
from __future__ import annotations

import datetime as _dt
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .corpus import CorpusStore

RESOLUTIONS = (
    "true_success",       # T0 was right; flags were false alarms (labels judge errors)
    "true_failure",       # T0 was right; fn-suspicion unfounded
    "verifier_defect",    # T0 wrong → repair verifier, re-run probe kit
    "task_defect",        # task/assertion wrong → repair task record
    "undecidable",        # insufficient evidence → instrumentation gap recorded
)


@dataclass(slots=True)
class QuarantineEntry:
    entry_id: str
    task_id: str
    run_ref: str
    verifier_status: str
    reason: str
    flags: list[dict[str, Any]] = field(default_factory=list)
    status: str = "pending"  # pending | resolved
    resolution: str | None = None
    resolution_note: str | None = None
    created_at: str = ""
    resolved_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "task_id": self.task_id,
            "run_ref": self.run_ref,
            "verifier_status": self.verifier_status,
            "reason": self.reason,
            "flags": self.flags,
            "status": self.status,
            "resolution": self.resolution,
            "resolution_note": self.resolution_note,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
        }


class QuarantineQueue:
    def __init__(self, path: Path) -> None:
        self.path = path

    # ── storage ──────────────────────────────────────────────────────────
    def _load_all(self) -> list[QuarantineEntry]:
        if not self.path.is_file():
            return []
        entries = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            entries.append(QuarantineEntry(**row))
        return entries

    def _write_all(self, entries: list[QuarantineEntry]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            "".join(json.dumps(e.to_dict(), sort_keys=True) + "\n" for e in entries),
            encoding="utf-8",
        )

    # ── operations ───────────────────────────────────────────────────────
    def enqueue(
        self,
        *,
        task_id: str,
        run_ref: str,
        verifier_status: str,
        reason: str,
        flags: list[dict[str, Any]] | None = None,
    ) -> QuarantineEntry:
        entry = QuarantineEntry(
            entry_id=uuid.uuid4().hex[:12],
            task_id=task_id,
            run_ref=run_ref,
            verifier_status=verifier_status,
            reason=reason,
            flags=flags or [],
            created_at=_dt.datetime.now(_dt.timezone.utc).isoformat(),
        )
        entries = self._load_all()
        entries.append(entry)
        self._write_all(entries)
        return entry

    def pending(self) -> list[QuarantineEntry]:
        return [e for e in self._load_all() if e.status == "pending"]

    def pending_task_ids(self) -> set[str]:
        return {e.task_id for e in self.pending()}

    def resolve(
        self,
        entry_id: str,
        *,
        resolution: str,
        note: str,
        corpus: CorpusStore | None = None,
    ) -> QuarantineEntry:
        if resolution not in RESOLUTIONS:
            raise ValueError(
                f"unknown resolution {resolution!r}; allowed: {', '.join(RESOLUTIONS)} "
                "(there is deliberately no 'override score' option)"
            )
        entries = self._load_all()
        target = next((e for e in entries if e.entry_id == entry_id), None)
        if target is None:
            raise KeyError(f"no quarantine entry {entry_id}")
        if target.status == "resolved":
            raise ValueError(f"entry {entry_id} is already resolved")
        target.status = "resolved"
        target.resolution = resolution
        target.resolution_note = note
        target.resolved_at = _dt.datetime.now(_dt.timezone.utc).isoformat()
        self._write_all(entries)

        if corpus is not None:
            ground_truth = {
                "true_success": "success",
                "true_failure": "failure",
                "verifier_defect": (
                    "success" if target.verifier_status == "failed" else "failure"
                ),
                "task_defect": "undecidable",
                "undecidable": "undecidable",
            }[resolution]
            corpus.add_case(
                source="quarantine",
                task_id=target.task_id,
                run_ref=target.run_ref,
                ground_truth=ground_truth,
                detail={
                    "entry_id": target.entry_id,
                    "resolution": resolution,
                    "note": note,
                    "verifier_status": target.verifier_status,
                    "flags": target.flags,
                },
            )
        return target
