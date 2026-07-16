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
import hashlib
from pathlib import Path
import time
from typing import Any

from opti_eval.errors import OptiEvalError
from opti_eval.identity import expected_live_run_receipt
from opti_eval.models import canonical_json

from . import fileguard, lint, registration
from .attribution import Attribution
from .compare import NoiseBand
from .eligibility import Eligibility, assess
from .evaluate import (
    EvalRun,
    build_adapter,
    load_run,
    reconstruct_warc_online4_activation,
    run_suite,
    validate_harness_fixture_activation,
    validate_warc_online4_activation,
)
from .manifest import ManifestReport, predicted_task_ids
from .protocol import (
    ProtocolError,
    build_identity,
    run_context as make_run_context,
    verify_runtime_bindings,
)
from .repeated import ArmEvidence, execute_repeated_protocol
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
    candidate_root: Path,
    candidate_guard: fileguard.GuardReport,
    base_sha: str,
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
    treatment_build: dict[str, Any],
    baseline_root: Path | None = None,
    deadline_at: float = float("inf"),
    now: Any = time.time,
    transfer_status: str = "not_due",
) -> GateReport:
    """Run the ladder. ``manifest``/``manifest_report`` are pre-validated by the
    conductor (which owns manifest ingestion from the untrusted worktree)."""
    report = GateReport(iteration=iteration)
    legacy_noise_diagnostic = {
        "status": "error" if noise_band_error else ("present" if noise_band else "absent"),
        "error": noise_band_error,
        "note": "diagnostic only; never repeated-protocol acceptance authority",
    }
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
    guard = candidate_guard
    if not guard.ok:
        report.rungs.append(RungResult("E0", "fail", guard.to_dict()))
        return _finish(report, "rejected")
    if not manifest_report.ok:
        report.rungs.append(RungResult("E0", "fail", {"manifest_errors": manifest_report.errors}))
        return _finish(report, "rejected")

    lint_report = lint.scan_tree(
        candidate_root,
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

    # ── E1: static registration + one qualified observed activation seam ──
    adapter_kind = adapter_config.get("kind")
    if adapter_kind not in {"harness-fixture", "warc-online4"}:
        report.rungs.append(
            RungResult(
                "E1",
                "invalid",
                {"error": "adapter lacks qualified conductor-owned activation instrumentation"},
            )
        )
        return _finish(report, "invalid")
    try:
        reg_report = registration.check_change_registered(
            candidate_root, manifest["target_component"], guard.changed
        )
    except OSError as exc:
        report.rungs.append(
            RungResult("E1", "invalid", {"error": f"registration preflight failed: {exc}"})
        )
        return _finish(report, "invalid")
    if not reg_report.ok:
        report.rungs.append(RungResult("E1", "invalid", {"errors": reg_report.errors}))
        return _finish(report, "invalid")  # inert/broken wiring falsifies nothing
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

    # The smoke execution is also the bounded D3 activation probe.  It is the
    # only treatment run allowed before E1 is proven.
    if drift := runtime_drift():
        report.rungs.append(RungResult("E1", "invalid", {"error": drift}))
        return _finish(report, "invalid")
    smoke_context = treatment_context("smoke")
    try:
        smoke = run_suite(repo_root=candidate_root, suite_name=suites["smoke"],
                          adapter_config=adapter_config, output_dir=eval_root / "smoke_treatment",
                          protocol_snapshot=protocol_snapshot,
                          run_context=smoke_context)
    except (OptiEvalError, OSError, ValueError) as exc:
        report.rungs.append(
            RungResult("E1", "invalid", {"error": f"smoke evaluation failed: {exc}"})
        )
        return _finish(report, "invalid")
    report.run_digests["smoke_treatment"] = smoke_context["run_digest"]
    activation_validator = (
        validate_warc_online4_activation
        if adapter_kind == "warc-online4"
        else validate_harness_fixture_activation
    )
    activation, activation_errors = activation_validator(
        smoke,
        baseline_run=baseline_dev,
        trusted_repo=repo_root,
        base_sha=base_sha,
        candidate_root=candidate_root,
        candidate_build=treatment_build,
        candidate_allowlist=protocol_snapshot["candidate_allowlist"],
        changed_files=guard.changed,
        configured_path=(
            adapter_config.get("treatment_path")
            if adapter_kind == "warc-online4"
            else adapter_config.get("file")
        ),
    )
    if activation_errors:
        report.rungs.append(RungResult("E1", "invalid", {"errors": activation_errors}))
        return _finish(report, "invalid")
    report.rungs.append(RungResult("E1", "pass", {
        "static": "pass",
        "observed_activation": activation,
        "warnings": reg_report.warnings,
    }))

    # ── E2: smoke ─────────────────────────────────────────────────────────
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
        try:
            screen = run_suite(repo_root=candidate_root, suite_name=suites["dev"], adapter_config=adapter_config,
                               output_dir=eval_root / "targeted_screen", task_ids=predicted,
                               protocol_snapshot=protocol_snapshot,
                               run_context=screen_context)
        except (OptiEvalError, OSError, ValueError) as exc:
            report.rungs.append(
                RungResult("E3", "invalid", {"error": f"targeted evaluation failed: {exc}"})
            )
            return _finish(report, "invalid")
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
    try:
        regression = run_suite(repo_root=candidate_root, suite_name=suites["regression"], adapter_config=adapter_config,
                               output_dir=eval_root / "regression_screen",
                               protocol_snapshot=protocol_snapshot,
                               run_context=regression_context)
    except (OptiEvalError, OSError, ValueError) as exc:
        report.rungs.append(
            RungResult("E4", "invalid", {"error": f"regression evaluation failed: {exc}"})
        )
        return _finish(report, "invalid")
    report.run_digests["regression_screen"] = regression_context["run_digest"]
    regression_eligibility = admit_decision_run(
        "regression_screen", regression, regression_context
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

    # ── E5: prespecified repeated paired/interleaved decision ─────────────
    if drift := runtime_drift():
        report.rungs.append(RungResult("E5", "invalid", {"error": drift}))
        return _finish(report, "invalid")

    accepted_build = protocol_snapshot["accepted_build"]

    def arm_context(role: str, arm: str, repeat_index: int, repeat_seed: int) -> dict[str, Any]:
        return make_run_context(
            protocol_snapshot,
            accepted_build if arm == "baseline" else treatment_build,
            arm=arm,
            suite_role=role,
            task_ids=frozen_tasks[role],
            repeat_index=repeat_index,
            seed=repeat_seed,
            run_id=(
                f"run-{protocol_snapshot['protocol_digest'][:16]}-{role}-"
                f"{repeat_index}-{repeat_seed}-{arm}"
            ),
        )

    def arm_output(
        role: str,
        arm: str,
        repeat_index: int,
        repeat_seed: int,
        is_final: bool,
    ) -> Path:
        if arm == "treatment" and is_final:
            return eval_root / ("dev_treatment" if role == "dev" else "regression_treatment")
        return eval_root / "repeated" / role / f"repeat-{repeat_index:04d}" / f"seed-{repeat_seed}" / arm

    def restore_simulated_activation(run: EvalRun, root: Path) -> None:
        if run.activation_observation is not None:
            return
        if adapter_kind == "warc-online4":
            run.activation_observation = reconstruct_warc_online4_activation(run)
            return
        if adapter_kind == "harness-fixture":
            adapter = build_adapter(adapter_config, repo_root=root)
            observation = getattr(adapter, "activation_observation", None)
        else:
            observation = None
        if type(observation) is dict:
            run.activation_observation = {
                **observation,
                "run_artifact": {
                    "path": "run.json",
                    "sha256": hashlib.sha256((run.output_dir / "run.json").read_bytes()).hexdigest(),
                },
            }

    def run_arm(
        role: str, arm: str, repeat_index: int, repeat_seed: int, is_final: bool
    ) -> ArmEvidence:
        if drift := runtime_drift():
            raise ProtocolError(drift)
        context = arm_context(role, arm, repeat_index, repeat_seed)
        output = arm_output(role, arm, repeat_index, repeat_seed, is_final)
        receipt = expected_live_run_receipt(
            protocol_snapshot, run_digest=context["run_digest"]
        )
        root = (baseline_root or repo_root) if arm == "baseline" else candidate_root
        if arm == "baseline" and baseline_root is not None:
            observed = build_identity(
                root,
                commit_sha=base_sha,
                role="accepted",
                candidate_allowlist=protocol_snapshot["candidate_allowlist"],
                immutable=bool(accepted_build["immutable"]),
            )
            if canonical_json(observed) != canonical_json(accepted_build):
                raise ProtocolError("repeated baseline root differs from the frozen accepted build")
        if output.is_dir():
            run = load_run(output, suites[role], expected_receipt=receipt)
            restore_simulated_activation(run, root)
        else:
            run = run_suite(
                repo_root=root,
                suite_name=suites[role],
                adapter_config=adapter_config,
                output_dir=output,
                protocol_snapshot=protocol_snapshot,
                run_context=context,
            )
        if arm == "baseline" and baseline_root is not None:
            observed_after = build_identity(
                root,
                commit_sha=base_sha,
                role="accepted",
                candidate_allowlist=protocol_snapshot["candidate_allowlist"],
                immutable=bool(accepted_build["immutable"]),
            )
            if canonical_json(observed_after) != canonical_json(accepted_build):
                raise ProtocolError("repeated baseline build changed during execution")
        eligibility = assess(
            run=run,
            run_dir=run.output_dir,
            expected_receipt=receipt,
            task_records=run.task_records,
            admissions_path=admissions_path,
            quarantine_path=quarantine_path,
        )
        return ArmEvidence(run=run, context=context, eligibility=eligibility)

    def validate_activation(
        _role: str, baseline_arm: ArmEvidence, treatment_arm: ArmEvidence
    ) -> list[str]:
        _activation, errors = activation_validator(
            treatment_arm.run,
            baseline_run=baseline_arm.run,
            trusted_repo=repo_root,
            base_sha=base_sha,
            candidate_root=candidate_root,
            candidate_build=treatment_build,
            candidate_allowlist=protocol_snapshot["candidate_allowlist"],
            changed_files=candidate_guard.changed,
            configured_path=(
                adapter_config.get("treatment_path")
                if adapter_kind == "warc-online4"
                else adapter_config.get("file")
            ),
        )
        return errors

    try:
        repeated_result = execute_repeated_protocol(
            protocol=protocol_snapshot,
            task_sources=task_sources,
            predicted_task_ids=predicted_set,
            run_arm=run_arm,
            validate_activation=validate_activation,
            deadline_at=deadline_at,
            now=now,
            transfer_status=transfer_status,
            accepted_protection=protocol_snapshot["execution"]["accepted_protection"],
            validity_policy=str(thresholds.get("validity_policy", "strict")),
            min_prediction_precision=float(
                thresholds.get("min_prediction_precision", 0.1)
            ),
        )
    except (OptiEvalError, OSError, ValueError, ProtocolError) as exc:
        report.rungs.append(
            RungResult("E5", "invalid", {"error": f"repeated evaluation failed: {exc}"})
        )
        return _finish(report, "invalid")

    report.admissions.update(repeated_result.admissions)
    report.run_digests.update(repeated_result.run_digests)
    for role in ("dev", "regression"):
        key = f"{role}_treatment"
        final = repeated_result.final_runs.get(key)
        if final is not None:
            alias = "dev_treatment" if role == "dev" else "regression_treatment"
            report.run_digests[alias] = final.context["run_digest"]
            report.admissions[alias] = final.eligibility.to_dict()
    report.eligibility = {"repeated_protocol": repeated_result.detail}
    report.comparison = {
        "protocol": "prespecified-repeated-paired-interleaved",
        "legacy_noise_envelope": legacy_noise_diagnostic,
        **repeated_result.detail,
    }
    fixed = set(repeated_result.detail.get("fixed", []))
    regressed = set(repeated_result.detail.get("regressed", []))
    predicted_all = predicted_task_ids(manifest)
    verified = sorted(predicted_all & fixed)
    report.attribution = Attribution(
        verdict=("keep" if verified and not regressed else "partial" if verified else "revert"),
        predicted_count=len(predicted_all),
        verified_fixes=verified,
        missed_predictions=sorted(predicted_all - fixed),
        unpredicted_fixes=sorted(fixed - predicted_all),
        materialized_regressions=sorted(regressed),
        prediction_precision=(round(len(verified) / len(predicted_all), 4) if predicted_all else None),
        flip_recall=(round(len(verified) / len(fixed), 4) if fixed else None),
    ).to_dict()
    status = "pass" if repeated_result.decision == "accepted" else (
        "invalid" if repeated_result.decision == "invalid" else "fail"
    )
    report.rungs.append(RungResult("E5", status, repeated_result.detail))
    return _finish(report, repeated_result.decision, repeated_result.evidence_class)
