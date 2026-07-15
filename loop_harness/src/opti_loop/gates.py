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

from . import fileguard, lint, registration
from .attribution import attribute
from .compare import NoiseBand, compare_runs
from .eligibility import Eligibility, assess
from .evaluate import EvalRun, run_suite
from .manifest import ManifestReport, predicted_task_ids
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
    task_sources: dict[str, str],
    task_records: dict[str, dict[str, Any]],
    regression_last_results: dict[str, str],
    admissions_path: Path,
    quarantine_path: Path,
) -> GateReport:
    """Run the ladder. ``manifest``/``manifest_report`` are pre-validated by the
    conductor (which owns manifest ingestion from the untrusted worktree)."""
    report = GateReport(iteration=iteration)

    # ── E0: containment — commit-diff guard, manifest, whole-tree lint ────
    try:
        guard = fileguard.check_candidate(
            repo=repo_root, worktree=worktree, base_sha=base_sha, candidate_sha=candidate_sha
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

    lint_report = lint.scan_tree(worktree)
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

    # ── E2: smoke ─────────────────────────────────────────────────────────
    smoke = run_suite(repo_root=worktree, suite_name=suites["smoke"],
                      adapter_config=adapter_config, output_dir=eval_root / "smoke_treatment")
    if not smoke.run_valid:
        report.rungs.append(RungResult("E2", "invalid", {"reason": "smoke contains invalidating results"}))
        return _finish(report, "invalid")
    smoke_rate = smoke.summary.get("strict_success_rate") or 0.0
    smoke_min = float(thresholds.get("smoke_min_pass_rate", 0.5))
    if smoke_rate < smoke_min:
        report.rungs.append(RungResult("E2", "fail", {"smoke_rate": smoke_rate, "threshold": smoke_min}))
        return _finish(report, "rejected")
    report.rungs.append(RungResult("E2", "pass", {"smoke_rate": smoke_rate, "threshold": smoke_min}))

    # ── E3: SCREENING ONLY — never sufficient for acceptance (F05) ───────
    predicted = sorted(predicted_task_ids(manifest) & set(task_sources))
    e3_detail: dict[str, Any] = {"predicted_task_ids_in_catalog": predicted, "role": "screening only"}
    if predicted:
        screen = run_suite(repo_root=worktree, suite_name=suites["dev"], adapter_config=adapter_config,
                           output_dir=eval_root / "targeted_screen", task_ids=predicted)
        screened_flips = sorted(
            t for t in predicted
            if screen.statuses.get(t) == "passed" and baseline_dev.statuses.get(t) == "failed"
        )
        e3_detail["screened_flips"] = screened_flips
        if not screened_flips:
            report.rungs.append(RungResult("E3", "fail", e3_detail))
            return _finish(report, "rejected")
        report.rungs.append(RungResult("E3", "pass", e3_detail))
    else:
        e3_detail["note"] = "no catalog task IDs predicted; flip must appear in E5"
        report.rungs.append(RungResult("E3", "skipped", e3_detail))

    # ── E4: regression, near-zero tolerance, frozen accepted baseline ────
    regression = run_suite(repo_root=worktree, suite_name=suites["regression"], adapter_config=adapter_config,
                           output_dir=eval_root / "regression_treatment")
    if not regression.run_valid:
        report.rungs.append(RungResult("E4", "invalid", {"reason": "regression contains invalidating results"}))
        return _finish(report, "invalid")
    previously_passing = {t for t, s in regression_last_results.items() if s == "passed"}
    new_failures = sorted(t for t in previously_passing if regression.statuses.get(t) == "failed")
    max_new = int(thresholds.get("regression_max_new_failures", 0))
    e4_detail = {"new_failures": new_failures, "tolerance": max_new,
                 "baseline_source": "accepted/baseline (never a rejected treatment)"}
    if len(new_failures) > max_new:
        report.rungs.append(RungResult("E4", "fail", e4_detail))
        return _finish(report, "rejected")
    report.rungs.append(RungResult("E4", "pass", e4_detail))

    # ── E5: paired development evaluation ─────────────────────────────────
    treatment = run_suite(repo_root=worktree, suite_name=suites["dev"], adapter_config=adapter_config,
                          output_dir=eval_root / "dev_treatment")
    eligibility: Eligibility = assess(
        run=treatment,
        run_dir=eval_root / "dev_treatment",
        adapter_config=adapter_config,
        task_records=task_records,
        admissions_path=admissions_path,
        quarantine_path=quarantine_path,
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
    if evidence_class == "benchmark":
        if noise_band.synthetic:
            report.rungs.append(RungResult("E5", "invalid", {"reason": "benchmark run cannot use a synthetic noise band"}))
            return _finish(report, "invalid", evidence_class)
        if not noise_band.matches_identity(run_identity):
            report.rungs.append(RungResult("E5", "invalid", {
                "reason": "noise band was not measured for this run identity",
                "expected": run_identity, "band": noise_band.run_identity,
            }))
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
