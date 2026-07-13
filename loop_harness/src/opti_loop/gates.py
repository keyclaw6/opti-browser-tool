"""The E0–E5 gate ladder (ADR-0005, Proposed): deterministic, fail-fast.

Every rung's decision is computed from recorded artifacts by this code —
no LLM participates (ADR-0015 §5.3). A rung failure stops the ladder.
Verdicts:

- ``accepted`` / ``rejected``: the comparison was eligible and the rules fired;
- ``invalid``: infrastructure or containment failure — falsifies nothing;
- ``simulated:<verdict>``: the rules fired but at least one run was not
  benchmark-reportable (e.g. the fixture adapter) — never a real acceptance,
  mirroring opti-eval's ``acceptance_decision_eligible`` semantics.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import fileguard, lint, registration
from .attribution import attribute
from .compare import NoiseBand, compare_runs
from .evaluate import EvalRun, run_suite
from .manifest import ManifestReport, load_and_validate, predicted_task_ids


@dataclass(slots=True)
class RungResult:
    rung: str
    status: str  # pass | fail | invalid | pending | skipped
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class GateReport:
    iteration: int
    rungs: list[RungResult] = field(default_factory=list)
    verdict: str = "invalid"
    attribution: dict[str, Any] | None = None
    comparison: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "iteration": self.iteration,
            "verdict": self.verdict,
            "rungs": [
                {"rung": rung.rung, "status": rung.status, "detail": rung.detail}
                for rung in self.rungs
            ],
            "attribution": self.attribution,
            "comparison": self.comparison,
        }

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")


def run_gate(
    *,
    repo_root: Path,
    iteration: int,
    iteration_dir: Path,
    baseline_dev: EvalRun,
    manifest_path: Path,
    adapter_config: dict[str, Any],
    suites: dict[str, str],
    thresholds: dict[str, Any],
    noise_band: NoiseBand | None,
    task_sources: dict[str, str],
    regression_last_results: dict[str, str],
    guard_baseline_paths: set[str] | None = None,
    quarantined_task_ids: set[str] | None = None,
) -> GateReport:
    report = GateReport(iteration=iteration)

    # ── E0: containment — file guard, manifest contract, generality lint ──
    try:
        guard = fileguard.check(repo_root, baseline_paths=guard_baseline_paths)
    except fileguard.GuardError as exc:
        report.rungs.append(RungResult("E0", "invalid", {"error": str(exc)}))
        report.verdict = "invalid"
        return report
    if not guard.ok:
        report.rungs.append(
            RungResult("E0", "fail", {"file_guard_violations": guard.violations})
        )
        report.verdict = "rejected"
        return report

    optimizer_changes = [p for p in guard.changed if fileguard.is_allowed(p)]
    manifest_report: ManifestReport = load_and_validate(
        manifest_path, changed_files=optimizer_changes
    )
    if not manifest_report.ok:
        report.rungs.append(
            RungResult("E0", "fail", {"manifest_errors": manifest_report.errors})
        )
        report.verdict = "rejected"
        return report
    manifest = manifest_report.manifest
    assert manifest is not None

    lint_report = lint.scan_files(repo_root, optimizer_changes)
    if not lint_report.ok:
        report.rungs.append(
            RungResult(
                "E0",
                "fail",
                {
                    "generality_lint": [
                        {
                            "path": f.path,
                            "line": f.line,
                            "kind": f.kind,
                            "token": f.token,
                        }
                        for f in lint_report.findings
                    ]
                },
            )
        )
        report.verdict = "rejected"
        return report
    report.rungs.append(
        RungResult(
            "E0",
            "pass",
            {
                "changed_files": optimizer_changes,
                "manifest_warnings": manifest_report.warnings,
                "lint_scanned_files": lint_report.scanned_files,
            },
        )
    )

    # ── E1: activation audit — static half now, dynamic half pending ─────
    reg_report = registration.check_change_registered(
        repo_root, manifest["target_component"], optimizer_changes
    )
    if not reg_report.ok:
        report.rungs.append(RungResult("E1", "invalid", {"errors": reg_report.errors}))
        report.verdict = "invalid"  # inert/broken wiring falsifies nothing
        return report
    report.rungs.append(
        RungResult(
            "E1",
            "pass",
            {
                "static": "pass",
                "dynamic_trace_audit": "pending (no tracer/browser runtime yet)",
                "warnings": reg_report.warnings,
            },
        )
    )

    # ── E2: smoke ─────────────────────────────────────────────────────────
    smoke_run = run_suite(
        repo_root=repo_root,
        suite_name=suites["smoke"],
        adapter_config=adapter_config,
        output_dir=iteration_dir / "eval" / "smoke_treatment",
    )
    smoke_rate = smoke_run.summary.get("strict_success_rate") or 0.0
    smoke_min = float(thresholds.get("smoke_min_pass_rate", 0.5))
    if not smoke_run.run_valid:
        report.rungs.append(
            RungResult("E2", "invalid", {"reason": "smoke run contains invalidating results"})
        )
        report.verdict = "invalid"
        return report
    if smoke_rate < smoke_min:
        report.rungs.append(
            RungResult("E2", "fail", {"smoke_rate": smoke_rate, "threshold": smoke_min})
        )
        report.verdict = "rejected"
        return report
    report.rungs.append(
        RungResult("E2", "pass", {"smoke_rate": smoke_rate, "threshold": smoke_min})
    )

    # ── E3: targeted re-evaluation of the motivating tasks ───────────────
    predicted = sorted(predicted_task_ids(manifest) & set(task_sources))
    e3_detail: dict[str, Any] = {"predicted_task_ids_in_catalog": predicted}
    if predicted:
        targeted = run_suite(
            repo_root=repo_root,
            suite_name=suites["dev"],
            adapter_config=adapter_config,
            output_dir=iteration_dir / "eval" / "targeted_treatment",
            task_ids=predicted,
        )
        newly_passing = sorted(
            tid
            for tid in predicted
            if targeted.statuses.get(tid) == "passed"
            and baseline_dev.statuses.get(tid) == "failed"
        )
        e3_detail["verified_predicted_flips"] = newly_passing
        if not newly_passing:
            report.rungs.append(RungResult("E3", "fail", e3_detail))
            report.verdict = "rejected"
            return report
        report.rungs.append(RungResult("E3", "pass", e3_detail))
    else:
        e3_detail["note"] = (
            "manifest predicts failure classes only (no catalog task IDs); "
            "flip verification deferred to E5"
        )
        report.rungs.append(RungResult("E3", "skipped", e3_detail))

    # ── E4: regression suite, near-zero tolerance ─────────────────────────
    regression_run = run_suite(
        repo_root=repo_root,
        suite_name=suites["regression"],
        adapter_config=adapter_config,
        output_dir=iteration_dir / "eval" / "regression_treatment",
    )
    if not regression_run.run_valid:
        report.rungs.append(
            RungResult("E4", "invalid", {"reason": "regression run contains invalidating results"})
        )
        report.verdict = "invalid"
        return report
    previously_passing = {
        tid for tid, status in regression_last_results.items() if status == "passed"
    }
    new_failures = sorted(
        tid
        for tid in previously_passing
        if regression_run.statuses.get(tid) == "failed"
    )
    max_new = int(thresholds.get("regression_max_new_failures", 0))
    e4_detail = {
        "new_failures": new_failures,
        "tolerance": max_new,
        "regression_statuses": regression_run.summary.get("status_counts"),
    }
    if len(new_failures) > max_new:
        report.rungs.append(RungResult("E4", "fail", e4_detail))
        report.verdict = "rejected"
        return report
    report.rungs.append(RungResult("E4", "pass", e4_detail))

    # ── E5: paired development evaluation ─────────────────────────────────
    treatment_dev = run_suite(
        repo_root=repo_root,
        suite_name=suites["dev"],
        adapter_config=adapter_config,
        output_dir=iteration_dir / "eval" / "dev_treatment",
    )
    comparison = compare_runs(
        baseline_dev,
        treatment_dev,
        policy=str(thresholds.get("validity_policy", "strict")),
        quorum_coverage_floor=float(thresholds.get("quorum_coverage_floor", 0.9)),
        task_sources=task_sources,
        quarantined=quarantined_task_ids,
    )
    report.comparison = comparison.to_dict()
    if not comparison.eligible:
        report.rungs.append(RungResult("E5", "invalid", {"reasons": comparison.reasons}))
        report.verdict = "invalid"
        return report

    if noise_band is None:
        report.rungs.append(
            RungResult(
                "E5",
                "invalid",
                {"reason": "noise band unmeasured — run `opti-loop measure-noise` first"},
            )
        )
        report.verdict = "invalid"
        return report

    attribution = attribute(manifest, comparison)
    report.attribution = attribution.to_dict()

    verified_any = bool(attribution.verified_fixes) or bool(
        next(
            (r for r in report.rungs if r.rung == "E3" and r.status == "pass"),
            None,
        )
    )
    regress_ok = len(comparison.regressed) <= noise_band.max_benign_flips
    base = comparison.baseline_success or 0.0
    treat = comparison.treatment_success or 0.0
    non_inferior = treat >= base - noise_band.aggregate_margin

    conditions = {
        "predicted_flip_verified": verified_any,
        "regressions_within_noise_band": regress_ok,
        "aggregate_non_inferior": non_inferior,
    }
    accepted = all(conditions.values())
    report.rungs.append(
        RungResult(
            "E5",
            "pass" if accepted else "fail",
            {"conditions": conditions, "noise_band": noise_band.to_dict()},
        )
    )
    verdict = "accepted" if accepted else "rejected"
    if comparison.simulated or noise_band.synthetic:
        verdict = f"simulated:{verdict}"
    report.verdict = verdict
    return report
