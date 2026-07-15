"""The E0–E5 gate ladder (ADR-0005, Proposed): deterministic, fail-fast.

Every rung's decision is computed from recorded artifacts by this code — no
LLM participates (ADR-0015 §5.3). Rewritten after the adversarial review:

- E0 is authoritative over the ``base..candidate`` commit diff, not the
  mutable working tree (F01); paths are safety-checked (F03) and the whole
  candidate component tree is linted, not just the diff (F08).
- E3 is screening only; the acceptance flip must be verified in the FULL E5
  evidence, and a ``revert`` attribution can never be accepted (F05).
- A shotgun prediction (predict-everything) fails a precision floor (F09).
- The verdict is typed; only ``(accepted, benchmark)`` can advance real state,
  and benchmark evidence requires verifier admission + a noise band bound to
  this run's identity (F04, F07, F10).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from opti_eval.identity import (
    IdentityError,
    expected_live_run_receipt,
    validate_paired_contexts,
)

from . import fileguard, lint, registration
from .attribution import attribute
from .compare import NoiseBand, compare_runs
from .eligibility import Eligibility, assess
from .evaluate import EvalRun, run_suite
from .manifest import ManifestReport, predicted_task_ids
from .protocol import (
    ProtocolError,
    build_identity,
    run_context as make_run_context,
    verify_runtime_bindings,
)
from .verdict import Verdict


@dataclass(slots=True)
class RungResult:
    rung: str
    status: str  # pass | fail | invalid | pending | skipped
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class GateReport:
    iteration: int
    rungs: list[RungResult] = field(default_factory=list)
    verdict: Verdict = field(default_factory=lambda: Verdict("invalid", "simulated"))
    attribution: dict[str, Any] | None = None
    comparison: dict[str, Any] | None = None
    eligibility: dict[str, Any] | None = None
    admissions: dict[str, dict[str, Any]] = field(default_factory=dict)
    run_digests: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "iteration": self.iteration,
            "verdict": self.verdict.to_dict(),
            "rungs": [
                {"rung": r.rung, "status": r.status, "detail": r.detail} for r in self.rungs
            ],
            "attribution": self.attribution,
            "comparison": self.comparison,
            "eligibility": self.eligibility,
            "admissions": self.admissions,
            "run_digests": self.run_digests,
        }


def _finish(report: GateReport, decision: str, evidence_class: str = "simulated") -> GateReport:
    report.verdict = Verdict(decision, evidence_class)
    return report


def run_gate(
    *,
    repo_root: Path,
    worktree: Path,
    base_sha: str,
    candidate_sha: str,
    iteration: int,
    eval_root: Path,
    baseline_dev: EvalRun,
    manifest: dict,
    manifest_report: ManifestReport,
    adapter_config: dict[str, Any],
    suites: dict[str, str],
    thresholds: dict[str, Any],
    noise_band: NoiseBand | None,
    run_identity: str,
    protocol_snapshot: dict[str, Any],
    task_sources: dict[str, str],
    task_records: dict[str, dict[str, Any]],
    regression_baseline: EvalRun,
    admissions_path: Path,
    quarantine_path: Path,
    noise_band_error: str | None = None,
) -> GateReport:
    """Run the ladder. ``manifest``/``manifest_report`` are pre-validated by the
    conductor (which owns manifest ingestion from the untrusted worktree)."""
    report = GateReport(iteration=iteration)
    if noise_band_error:
        report.rungs.append(
            RungResult(
                "E5",
                "invalid",
                {"reason": f"noise-band evidence preflight failed: {noise_band_error}"},
            )
        )
        return _finish(report, "invalid")
    if noise_band is not None and not noise_band.synthetic and not noise_band.anchors_validated:
        report.rungs.append(
            RungResult(
                "E5",
                "invalid",
                {"reason": "real noise band lacks fresh AR-003 sample revalidation"},
            )
        )
        return _finish(report, "invalid")
    seed = int(protocol_snapshot["repeated_protocol"]["matched_blocks"]["seeds"][0])

    frozen_tasks = {
        suite["role"]: [task["id"] for task in suite["tasks"]]
        for suite in protocol_snapshot["suites"]
    }

    def runtime_drift() -> str | None:
        try:
            verify_runtime_bindings(
                protocol_snapshot,
                admissions_path=admissions_path,
            )
        except ProtocolError as exc:
            return str(exc)
        return None

    def admit_decision_run(
        label: str, run: EvalRun, context: dict[str, Any]
    ) -> Eligibility:
        eligibility = assess(
            run=run,
            run_dir=run.output_dir,
            expected_receipt=expected_live_run_receipt(
                protocol_snapshot,
                run_digest=context["run_digest"],
            ),
            task_records=run.task_records,
            admissions_path=admissions_path,
            quarantine_path=quarantine_path,
        )
        report.admissions[label] = eligibility.to_dict()
        return eligibility

    def admission_error(eligibility: Eligibility) -> dict[str, Any] | None:
        if protocol_snapshot["evidence_mode"] != "benchmark":
            return None
        if eligibility.integrity_status == "invalid":
            return {
                "reason": "benchmark evidence admission failed",
                "task_errors": eligibility.integrity_errors,
            }
        if not eligibility.acceptance_eligible or eligibility.admission_receipt is None:
            return {
                "reason": "benchmark evidence was not admitted for decision",
                "quarantined_tasks": eligibility.quarantined_tasks,
            }
        return None

    if drift := runtime_drift():
        report.rungs.append(
            RungResult("E0", "invalid", {"error": f"trusted apparatus drift: {drift}"})
        )
        return _finish(report, "invalid")
    if protocol_snapshot["evidence_mode"] == "benchmark":
        report.admissions["dev_baseline"] = {
            "admission_receipt": baseline_dev.admission_receipt
        }
        if not baseline_dev.benchmark_admitted:
            report.rungs.append(
                RungResult(
                    "E0",
                    "invalid",
                    {"error": "benchmark development baseline lacks AR-003 admission"},
                )
            )
            return _finish(report, "invalid")
        report.admissions["regression_baseline"] = {
            "admission_receipt": regression_baseline.admission_receipt
        }
        if not regression_baseline.benchmark_admitted:
            report.rungs.append(
                RungResult(
                    "E0",
                    "invalid",
                    {"error": "benchmark regression baseline lacks AR-003 admission"},
                )
            )
            return _finish(report, "invalid")

    # ── E0: containment — commit-diff guard, manifest, whole-tree lint ────
    try:
        guard = fileguard.check_candidate(
            repo=repo_root,
            worktree=worktree,
            base_sha=base_sha,
            candidate_sha=candidate_sha,
            allowed_prefixes=tuple(protocol_snapshot["candidate_allowlist"]),
        )
    except fileguard.GuardError as exc:
        report.rungs.append(RungResult("E0", "invalid", {"error": str(exc)}))
        return _finish(report, "invalid")
    if not guard.ok:
        report.rungs.append(RungResult("E0", "fail", guard.to_dict()))
        return _finish(report, "rejected")
    if not manifest_report.ok:
        report.rungs.append(RungResult("E0", "fail", {"manifest_errors": manifest_report.errors}))
        return _finish(report, "rejected")

    lint_report = lint.scan_tree(
        worktree,
        allowed_prefixes=tuple(protocol_snapshot["candidate_allowlist"]),
    )
    if not lint_report.ok:
        report.rungs.append(
            RungResult("E0", "fail", {"generality_lint": [f.to_dict() for f in lint_report.findings]})
        )
        return _finish(report, "rejected")
    report.rungs.append(
        RungResult("E0", "pass", {
            "changed_files": guard.changed,
            "manifest_warnings": manifest_report.warnings,
            "lint_scanned_files": lint_report.scanned_files,
        })
    )

    # ── E1: activation audit — static half now, dynamic half pending ─────
    reg_report = registration.check_change_registered(
        worktree, manifest["target_component"], guard.changed
    )
    if not reg_report.ok:
        report.rungs.append(RungResult("E1", "invalid", {"errors": reg_report.errors}))
        return _finish(report, "invalid")  # inert/broken wiring falsifies nothing
    report.rungs.append(RungResult("E1", "pass", {
        "static": "pass",
        "dynamic_trace_audit": "pending (no tracer/browser runtime yet)",
        "warnings": reg_report.warnings,
    }))
    try:
        treatment_build = build_identity(
            worktree,
            commit_sha=candidate_sha,
            role="candidate",
            candidate_allowlist=protocol_snapshot["candidate_allowlist"],
            immutable=False,
        )
    except ProtocolError as exc:
        report.rungs.append(RungResult("E1", "invalid", {"error": str(exc)}))
        return _finish(report, "invalid")

    def treatment_context(
        suite_role: str, task_ids: list[str] | None = None
    ) -> dict[str, Any]:
        return make_run_context(
            protocol_snapshot,
            treatment_build,
            arm="treatment",
            suite_role=suite_role,
            task_ids=list(task_ids or frozen_tasks[suite_role]),
            seed=seed,
        )

    # ── E2: smoke ─────────────────────────────────────────────────────────
    if drift := runtime_drift():
        report.rungs.append(RungResult("E2", "invalid", {"error": drift}))
        return _finish(report, "invalid")
    smoke_context = treatment_context("smoke")
    smoke = run_suite(repo_root=worktree, suite_name=suites["smoke"],
                      adapter_config=adapter_config, output_dir=eval_root / "smoke_treatment",
                      protocol_snapshot=protocol_snapshot,
                      run_context=smoke_context)
    report.run_digests["smoke_treatment"] = smoke_context["run_digest"]
    smoke_eligibility = admit_decision_run("smoke_treatment", smoke, smoke_context)
    if error := admission_error(smoke_eligibility):
        report.rungs.append(RungResult("E2", "invalid", error))
        return _finish(report, "invalid", smoke_eligibility.evidence_class)
    if not smoke.run_valid:
        report.rungs.append(RungResult("E2", "invalid", {"reason": "smoke contains invalidating results"}))
        return _finish(report, "invalid")
    smoke_rate = smoke.summary.get("strict_success_rate") or 0.0
    smoke_min = float(thresholds.get("smoke_min_pass_rate", 0.5))
    if smoke_rate < smoke_min:
        report.rungs.append(RungResult("E2", "fail", {"smoke_rate": smoke_rate, "threshold": smoke_min}))
        return _finish(report, "rejected", smoke_eligibility.evidence_class)
    report.rungs.append(RungResult("E2", "pass", {"smoke_rate": smoke_rate, "threshold": smoke_min}))

    # ── E3: SCREENING ONLY — never sufficient for acceptance (F05) ───────
    predicted_set = predicted_task_ids(manifest) & set(task_sources)
    predicted = [task_id for task_id in frozen_tasks["dev"] if task_id in predicted_set]
    e3_detail: dict[str, Any] = {"predicted_task_ids_in_catalog": predicted, "role": "screening only"}
    if predicted:
        if drift := runtime_drift():
            report.rungs.append(RungResult("E3", "invalid", {"error": drift}))
            return _finish(report, "invalid")
        screen_context = treatment_context("dev", predicted)
        screen = run_suite(repo_root=worktree, suite_name=suites["dev"], adapter_config=adapter_config,
                           output_dir=eval_root / "targeted_screen", task_ids=predicted,
                           protocol_snapshot=protocol_snapshot,
                           run_context=screen_context)
        report.run_digests["targeted_screen"] = screen_context["run_digest"]
        screen_eligibility = admit_decision_run(
            "targeted_screen", screen, screen_context
        )
        if error := admission_error(screen_eligibility):
            report.rungs.append(RungResult("E3", "invalid", error))
            return _finish(report, "invalid", screen_eligibility.evidence_class)
        screened_flips = sorted(
            t for t in predicted
            if screen.statuses.get(t) == "passed" and baseline_dev.statuses.get(t) == "failed"
        )
        e3_detail["screened_flips"] = screened_flips
        if not screened_flips:
            report.rungs.append(RungResult("E3", "fail", e3_detail))
            return _finish(report, "rejected", screen_eligibility.evidence_class)
        report.rungs.append(RungResult("E3", "pass", e3_detail))
    else:
        e3_detail["note"] = "no catalog task IDs predicted; flip must appear in E5"
        report.rungs.append(RungResult("E3", "skipped", e3_detail))

    # ── E4: regression, near-zero tolerance, frozen accepted baseline ────
    if drift := runtime_drift():
        report.rungs.append(RungResult("E4", "invalid", {"error": drift}))
        return _finish(report, "invalid")
    regression_context = treatment_context("regression")
    regression = run_suite(repo_root=worktree, suite_name=suites["regression"], adapter_config=adapter_config,
                           output_dir=eval_root / "regression_treatment",
                           protocol_snapshot=protocol_snapshot,
                           run_context=regression_context)
    report.run_digests["regression_treatment"] = regression_context["run_digest"]
    regression_eligibility = admit_decision_run(
        "regression_treatment", regression, regression_context
    )
    if error := admission_error(regression_eligibility):
        report.rungs.append(RungResult("E4", "invalid", error))
        return _finish(report, "invalid", regression_eligibility.evidence_class)
    if not regression.run_valid:
        report.rungs.append(RungResult("E4", "invalid", {"reason": "regression contains invalidating results"}))
        return _finish(report, "invalid")
    previously_passing = {
        task_id
        for task_id, status in regression_baseline.statuses.items()
        if status == "passed"
    }
    new_failures = sorted(t for t in previously_passing if regression.statuses.get(t) == "failed")
    max_new = int(thresholds.get("regression_max_new_failures", 0))
    e4_detail = {"new_failures": new_failures, "tolerance": max_new,
                 "baseline_source": "accepted/baseline (never a rejected treatment)"}
    if len(new_failures) > max_new:
        report.rungs.append(RungResult("E4", "fail", e4_detail))
        return _finish(report, "rejected", regression_eligibility.evidence_class)
    report.rungs.append(RungResult("E4", "pass", e4_detail))

    # ── E5: paired development evaluation ─────────────────────────────────
    if drift := runtime_drift():
        report.rungs.append(RungResult("E5", "invalid", {"error": drift}))
        return _finish(report, "invalid")
    treatment_context_record = treatment_context("dev")
    treatment = run_suite(repo_root=worktree, suite_name=suites["dev"], adapter_config=adapter_config,
                          output_dir=eval_root / "dev_treatment",
                          protocol_snapshot=protocol_snapshot,
                          run_context=treatment_context_record)
    report.run_digests["dev_treatment"] = treatment_context_record["run_digest"]
    try:
        validate_paired_contexts(
            baseline_dev.run_context,
            treatment.run_context,
            protocol_snapshot=protocol_snapshot,
        )
    except IdentityError as exc:
        report.rungs.append(
            RungResult("E5", "invalid", {"reason": f"paired run identity mismatch: {exc}"})
        )
        return _finish(report, "invalid")
    if drift := runtime_drift():
        report.rungs.append(RungResult("E5", "invalid", {"error": drift}))
        return _finish(report, "invalid")
    eligibility = admit_decision_run(
        "dev_treatment", treatment, treatment_context_record
    )
    report.eligibility = eligibility.to_dict()
    evidence_class = eligibility.evidence_class

    if eligibility.integrity_status == "invalid":
        report.rungs.append(RungResult("E5", "invalid", {
            "reason": "evidence integrity invalid",
            "task_errors": eligibility.integrity_errors,
        }))
        return _finish(report, "invalid", evidence_class)
    if eligibility.integrity_status == "valid" and not eligibility.acceptance_eligible:
        report.rungs.append(RungResult("E5", "invalid", {
            "reason": "validated evidence has unresolved exact-run T1 quarantine",
            "quarantined_tasks": eligibility.quarantined_tasks,
        }))
        return _finish(report, "invalid", evidence_class)

    # Any exact-run quarantine already returned above.  Keep the comparison's
    # exclusion input exact-run scoped rather than importing task-only state.
    quarantined = set(eligibility.quarantined_tasks)
    comparison = compare_runs(
        baseline_dev, treatment,
        policy=str(thresholds.get("validity_policy", "strict")),
        quorum_coverage_floor=float(thresholds.get("quorum_coverage_floor", 0.9)),
        task_sources=task_sources, quarantined=quarantined,
    )
    report.comparison = comparison.to_dict()
    if not comparison.eligible:
        report.rungs.append(RungResult("E5", "invalid", {"reasons": comparison.reasons}))
        return _finish(report, "invalid", evidence_class)

    if noise_band is None:
        report.rungs.append(RungResult("E5", "invalid", {"reason": "noise band unmeasured"}))
        return _finish(report, "invalid", evidence_class)
    if not noise_band.synthetic and not noise_band.matches_identity(run_identity):
        report.rungs.append(RungResult("E5", "invalid", {
            "reason": "noise band was not measured for this run identity",
            "expected": run_identity, "band": noise_band.run_identity,
        }))
        return _finish(report, "invalid", evidence_class)
    if evidence_class == "benchmark":
        if noise_band.synthetic:
            report.rungs.append(RungResult("E5", "invalid", {"reason": "benchmark run cannot use a synthetic noise band"}))
            return _finish(report, "invalid", evidence_class)

    attribution = attribute(manifest, comparison)
    report.attribution = attribution.to_dict()

    # Acceptance conditions — the flip must be verified in FULL E5 evidence.
    verified_in_e5 = bool(attribution.verified_fixes)  # predicted ∩ E5.fixed
    not_revert = attribution.verdict != "revert"
    min_precision = float(thresholds.get("min_prediction_precision", 0.1))
    precision_ok = (
        attribution.predicted_count == 0
        or (attribution.prediction_precision or 0.0) >= min_precision
    )
    regress_ok = len(comparison.regressed) <= noise_band.max_benign_flips
    base = comparison.baseline_success or 0.0
    treat = comparison.treatment_success or 0.0
    non_inferior = treat >= base - noise_band.aggregate_margin

    conditions = {
        "predicted_flip_verified_in_E5": verified_in_e5,
        "attribution_not_revert": not_revert,
        "prediction_precision_ok": precision_ok,
        "regressions_within_noise_band": regress_ok,
        "aggregate_non_inferior": non_inferior,
    }
    accepted = all(conditions.values())
    report.rungs.append(RungResult("E5", "pass" if accepted else "fail", {
        "conditions": conditions,
        "min_prediction_precision": min_precision,
        "noise_band": noise_band.to_dict(),
    }))
    return _finish(report, "accepted" if accepted else "rejected", evidence_class)
