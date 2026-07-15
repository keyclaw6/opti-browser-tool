"""Fail-closed benchmark eligibility over admission, evidence bundles, and T1.

Fixture and command rehearsals remain simulated diagnostics.  An otherwise
reportable run is benchmark-eligible only when every terminal task has a
matching admission, a strict task-local result/trace/artifact bundle, and a
successful deterministic T1 pass whose flags all receive a closed disposition.
Missing validators, malformed evidence, or T1 execution failures are evidence
integrity failures, never behavior failures and never silent clean results.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from opti_eval.models import (
    canonical_json,
    split_lf_jsonl_records,
    strict_json_loads,
    validate_nonempty_string,
    validate_task_id,
)
from opti_eval.summary import validate_run_directory

from .evaluate import EvalRun


@dataclass(slots=True)
class Eligibility:
    evidence_class: str
    acceptance_eligible: bool
    integrity_status: str = "not_applicable"  # not_applicable | valid | invalid
    reasons: list[str] = field(default_factory=list)
    integrity_errors: list[str] = field(default_factory=list)
    newly_quarantined: list[str] = field(default_factory=list)
    quarantined_tasks: list[str] = field(default_factory=list)
    t1_flag_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_class": self.evidence_class,
            "acceptance_eligible": self.acceptance_eligible,
            "integrity_status": self.integrity_status,
            "reasons": self.reasons,
            "integrity_errors": self.integrity_errors,
            "newly_quarantined": self.newly_quarantined,
            "quarantined_tasks": self.quarantined_tasks,
            "t1_flag_count": self.t1_flag_count,
        }


def _invalid(*errors: str, flag_count: int = 0) -> Eligibility:
    rows = [error for error in errors if error]
    return Eligibility(
        evidence_class="simulated",
        acceptance_eligible=False,
        integrity_status="invalid",
        reasons=["benchmark evidence integrity is invalid"],
        integrity_errors=rows,
        t1_flag_count=flag_count,
    )


def _load_admissions(path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    index: dict[tuple[str, str], dict[str, Any]] = {}
    if not path.exists():
        return index
    if path.is_symlink() or not path.is_file():
        raise ValueError("admissions path must be a regular file, not a symlink")
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            records = split_lf_jsonl_records(
                handle.read(), field_name="admissions JSONL"
            )
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"admissions file is unreadable: {exc}") from exc
    except ValueError as exc:
        raise ValueError(f"admissions JSONL framing is invalid: {exc}") from exc
    for line_number, record in enumerate(records, start=1):
        try:
            row = strict_json_loads(
                record, field_name=f"admissions line {line_number}"
            )
        except ValueError as exc:
            raise ValueError(f"admissions line {line_number} is invalid: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"admissions line {line_number} must be an object")
        if not isinstance(row.get("admitted"), bool):
            raise ValueError(f"admissions line {line_number} admitted must be boolean")
        try:
            verifier_id = validate_nonempty_string(
                row.get("verifier_id"),
                field_name=f"admissions line {line_number} verifier_id",
            )
            task_id = validate_task_id(
                row.get("task_id"),
                field_name=f"admissions line {line_number} task_id",
            )
            validate_nonempty_string(
                row.get("verifier_checksum"),
                field_name=f"admissions line {line_number} verifier_checksum",
            )
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        if row["admitted"]:
            key = (verifier_id, task_id)
            previous = index.get(key)
            if previous is not None and previous.get("verifier_checksum") != row.get(
                "verifier_checksum"
            ):
                raise ValueError(
                    f"admissions contains conflicting checksums for {verifier_id}/{task_id}"
                )
            index[key] = row
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
    # Fixture, command, registry, and replay-only runs stay useful as simulated
    # diagnostics and are not required to fabricate browser evidence.  A
    # trusted reportable adapter, however, must fail closed on persisted-run
    # corruption even if replay already removed its optimistic summary flags.
    if not run.adapter_reportable:
        return Eligibility(
            evidence_class="simulated",
            acceptance_eligible=False,
            integrity_status="not_applicable",
            reasons=[
                "run is not benchmark-reportable (fixture/diagnostic or contains invalid results)"
            ],
        )

    checked = validate_run_directory(run_dir)
    if not checked.ok:
        return _invalid(*checked.errors)

    persisted_run_id = checked.run_record.get("run_id")
    if run.run_id != persisted_run_id:
        return _invalid("EvalRun run_id does not match the persisted runner-owned run_id")
    if run.task_ids != checked.task_ids:
        return _invalid("EvalRun ordered task manifest does not match run.json")
    if run.task_sources != checked.task_sources:
        return _invalid("EvalRun scheduled sources do not match run.json")
    if list(run.statuses) != checked.task_ids:
        return _invalid("EvalRun status order does not match the scheduled task manifest")
    if list(run.results) != checked.task_ids:
        return _invalid("EvalRun result order does not match the scheduled task manifest")
    for task_id in checked.task_ids:
        persisted = checked.results_by_task[task_id]
        if run.statuses.get(task_id) != persisted.get("status"):
            return _invalid(f"task {task_id}: EvalRun status does not match results.jsonl")
        try:
            same = canonical_json(run.results.get(task_id)) == canonical_json(persisted)
        except ValueError as exc:
            return _invalid(f"task {task_id}: EvalRun result is not canonical JSON: {exc}")
        if not same:
            return _invalid(f"task {task_id}: EvalRun result does not match results.jsonl")

    if not run.acceptance_decision_eligible:
        return Eligibility(
            evidence_class="simulated",
            acceptance_eligible=False,
            integrity_status="not_applicable",
            reasons=["reportable adapter run contains non-terminal or invalid outcomes"],
        )

    if not run.run_id:
        return _invalid("run has no trusted runner-owned run_id")
    if not run.statuses:
        return _invalid("reportable run has no terminal task results")
    if set(run.results) != set(run.statuses):
        return _invalid("aggregate result rows do not match the reportable task set")

    try:
        verifier_id = validate_nonempty_string(
            adapter_config.get("verifier_id"), field_name="adapter verifier_id"
        )
        verifier_checksum = validate_nonempty_string(
            adapter_config.get("verifier_checksum"),
            field_name="adapter verifier_checksum",
        )
    except ValueError:
        return _invalid(
            "adapter declares no pinned verifier_id/verifier_checksum; benchmark admission is unavailable"
        )
    if checked.run_record.get("verifier") != {
        "id": verifier_id,
        "checksum": verifier_checksum,
    }:
        return _invalid("run.json verifier binding does not match adapter config")

    expected_sources: dict[str, str] = {}
    for task_id in checked.task_ids:
        record = task_records.get(task_id)
        if not isinstance(record, dict):
            return _invalid(f"task {task_id}: trusted scheduled task record is missing")
        if record.get("id") != task_id:
            return _invalid(f"task {task_id}: trusted task record id does not match schedule")
        try:
            source = validate_nonempty_string(
                record.get("source"), field_name=f"task {task_id} scheduled source"
            )
        except ValueError as exc:
            return _invalid(str(exc))
        if checked.task_sources.get(task_id) != source:
            return _invalid(f"task {task_id}: persisted source does not match trusted schedule")
        expected_sources[task_id] = source
    try:
        admissions = _load_admissions(admissions_path)
    except ValueError as exc:
        return _invalid(str(exc))
    unadmitted: list[str] = []
    for task_id in run.statuses:
        row = admissions.get((verifier_id, task_id))
        if row is None or str(row.get("verifier_checksum")) != verifier_checksum:
            unadmitted.append(task_id)
    if unadmitted:
        return _invalid(
            f"{len(unadmitted)} task(s) have no admitted verifier matching checksum "
            f"{verifier_checksum[:12]}: {', '.join(sorted(unadmitted)[:8])}"
        )

    try:
        from opti_judge.evidence import (
            EvidenceContract,
            EvidenceError,
            load_task_bundle,
        )
        from opti_judge.quarantine import QuarantineQueue, flag_fingerprint
        from opti_judge.router import route
        from opti_judge.t1_checks import expectations_from_task, run_all
    except (ImportError, AttributeError) as exc:
        return _invalid(f"evidence validator/T1 is unavailable: {type(exc).__name__}: {exc}")
    if not all(
        callable(value)
        for value in (
            load_task_bundle,
            route,
            flag_fingerprint,
            expectations_from_task,
            run_all,
        )
    ):
        return _invalid("evidence validator/T1 API is unavailable")

    contract = EvidenceContract(
        role="loop-auto-t1",
        visibility=("executor", "judge", "orchestrator"),
    )
    try:
        queue = QuarantineQueue(quarantine_path)
        queue.validate_state()
    except Exception as exc:
        return _invalid(f"quarantine state is unavailable: {type(exc).__name__}: {exc}")

    errors: list[str] = []
    newly: list[str] = []
    quarantined: set[str] = set()
    total_flags = 0
    for task_id in checked.task_ids:
        status = run.statuses[task_id]
        try:
            bundle = load_task_bundle(
                task_root=run_dir / "tasks" / task_id,
                expected_run_id=run.run_id,
                expected_task_id=task_id,
                expected_source=expected_sources[task_id],
                expected_status=status,
                expected_result=run.results[task_id],
                expected_verifier_id=verifier_id,
                expected_verifier_checksum=verifier_checksum,
                contract=contract,
            )
        except EvidenceError as exc:
            errors.append(f"task {task_id}: {exc}")
            continue
        except Exception as exc:
            errors.append(
                f"task {task_id}: evidence validator failed: {type(exc).__name__}: {exc}"
            )
            continue

        try:
            side_effects, assertions = expectations_from_task(task_records.get(task_id, {}))
            flags = run_all(
                bundle.trace,
                verifier_status=status,
                side_effect_expectation=side_effects,
                assertions=assertions,
            )
            if not isinstance(flags, list):
                raise TypeError("T1 did not return a flag list")
        except Exception as exc:
            errors.append(f"task {task_id}: T1 execution failed: {type(exc).__name__}: {exc}")
            continue

        total_flags += len(flags)
        run_ref = f"{run.run_id}/{task_id}/{run.results[task_id]['trace_path']}"
        if not flags:
            try:
                if queue.run_is_blocked(task_id=task_id, run_ref=run_ref):
                    quarantined.add(task_id)
            except Exception as exc:
                errors.append(
                    f"task {task_id}: quarantine disposition check failed: "
                    f"{type(exc).__name__}: {exc}"
                )
            continue
        try:
            routed = route(
                queue=queue,
                task_id=task_id,
                run_ref=run_ref,
                verifier_status=status,
                t1_flags=flags,
            )
        except Exception as exc:
            errors.append(f"task {task_id}: T1 routing failed: {type(exc).__name__}: {exc}")
            continue
        if routed.get("routed"):
            if not routed.get("deduplicated"):
                newly.append(task_id)
            try:
                if queue.run_is_blocked(task_id=task_id, run_ref=run_ref):
                    quarantined.add(task_id)
                recorded = queue.flag_fingerprints(
                    task_id=task_id, run_ref=run_ref
                )
            except Exception as exc:
                errors.append(
                    f"task {task_id}: quarantine disposition check failed: "
                    f"{type(exc).__name__}: {exc}"
                )
                continue
            # The router records every suspicion. Informational flags have no
            # quarantine disposition and therefore close as integrity rejects.
            undisposed = [
                flag
                for flag in flags
                if getattr(flag, "severity", None) != "suspicion"
            ]
            if undisposed:
                errors.append(
                    f"task {task_id}: {len(undisposed)} T1 flag(s) were not recorded by quarantine"
                )
            missing_fingerprints = [
                flag_fingerprint(
                    task_id=task_id, run_ref=run_ref, flag=flag.to_dict()
                )
                for flag in flags
                if getattr(flag, "severity", None) == "suspicion"
                and flag_fingerprint(
                    task_id=task_id, run_ref=run_ref, flag=flag.to_dict()
                )
                not in recorded
            ]
            if missing_fingerprints:
                errors.append(
                    f"task {task_id}: {len(missing_fingerprints)} T1 suspicion flag(s) lack a stable disposition"
                )
        else:
            checks = ", ".join(
                sorted({str(getattr(flag, "check", "unknown")) for flag in flags})
            )
            errors.append(
                f"task {task_id}: T1 flags have no quarantine disposition ({checks})"
            )

    if errors:
        invalid = _invalid(*errors, flag_count=total_flags)
        invalid.newly_quarantined = sorted(newly)
        invalid.quarantined_tasks = sorted(quarantined)
        return invalid
    if quarantined:
        return Eligibility(
            evidence_class="benchmark",
            acceptance_eligible=False,
            integrity_status="valid",
            reasons=[
                f"T1 routed {len(quarantined)} task(s) to quarantine; E5 is blocked "
                "until the exact evidence is favorably cleared or a repaired run is produced"
            ],
            newly_quarantined=sorted(newly),
            quarantined_tasks=sorted(quarantined),
            t1_flag_count=total_flags,
        )
    return Eligibility(
        evidence_class="benchmark",
        acceptance_eligible=True,
        integrity_status="valid",
        t1_flag_count=total_flags,
    )
