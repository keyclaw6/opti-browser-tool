"""Prespecified repeated paired/interleaved decision for ADR-0018.

The caller owns concrete execution and AR-003 admission.  This module owns the
frozen schedule and the only efficacy decision: E0-E4 may stop unsafe or broken
work, but no treatment can be accepted from a single lucky E5 observation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from opti_eval.identity import IdentityError, validate_paired_contexts

from .compare import Comparison, compare_runs
from .eligibility import Eligibility
from .evaluate import EvalRun


@dataclass(slots=True)
class ArmEvidence:
    run: EvalRun
    context: dict[str, Any]
    eligibility: Eligibility
    activation_valid: bool = True
    activation_errors: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RepeatedResult:
    decision: str
    evidence_class: str
    detail: dict[str, Any]
    admissions: dict[str, dict[str, Any]] = field(default_factory=dict)
    run_digests: dict[str, str] = field(default_factory=dict)
    final_runs: dict[str, ArmEvidence] = field(default_factory=dict)


RunArm = Callable[[str, str, int, int, bool], ArmEvidence]
ValidateActivation = Callable[[str, ArmEvidence, ArmEvidence], list[str]]


def _finish(
    decision: str,
    evidence_class: str,
    *,
    reason: str,
    admissions: dict[str, dict[str, Any]],
    run_digests: dict[str, str],
    final_runs: dict[str, ArmEvidence],
    **detail: Any,
) -> RepeatedResult:
    return RepeatedResult(
        decision=decision,
        evidence_class=evidence_class,
        detail={"reason": reason, **detail},
        admissions=admissions,
        run_digests=run_digests,
        final_runs=final_runs,
    )


def execute_repeated_protocol(
    *,
    protocol: dict[str, Any],
    task_sources: dict[str, str],
    predicted_task_ids: set[str],
    run_arm: RunArm,
    validate_activation: ValidateActivation,
    deadline_at: float,
    now: Callable[[], float],
    transfer_status: str,
    accepted_protection: dict[str, Any],
    validity_policy: str,
    min_prediction_precision: float,
) -> RepeatedResult:
    """Execute and decide the frozen dev/regression paired-block schedule.

    ``run_arm`` must load an already complete exact run when present; this makes
    interruption recovery a replay of admitted run artifacts rather than a
    second model/browser call.  ``max_runs`` counts completed paired suite
    blocks (both arms), not individual arm invocations.
    """
    repeated = protocol["repeated_protocol"]
    valid_after = int(repeated["stopping"]["valid_after"])
    seeds = list(repeated["matched_blocks"]["seeds"])
    arm_order = list(repeated["matched_blocks"]["arm_order"])
    max_runs = int(repeated["limits"]["max_runs"])
    required_pairs = valid_after * len(seeds)
    expected_pairs = required_pairs * 2  # dev + regression
    admissions: dict[str, dict[str, Any]] = {}
    run_digests: dict[str, str] = {}
    final_runs: dict[str, ArmEvidence] = {}
    comparisons: dict[str, list[Comparison]] = {"dev": [], "regression": []}
    treatment_statuses: list[dict[str, str]] = []
    paired_runs = 0
    evidence_class = protocol["evidence_mode"]

    for repeat_index in range(valid_after):
        for seed in seeds:
            for role in ("dev", "regression"):
                if paired_runs >= max_runs:
                    return _finish(
                        "inconclusive", evidence_class,
                        reason="frozen paired-run budget exhausted before the valid stop",
                        admissions=admissions, run_digests=run_digests,
                        final_runs=final_runs, paired_runs=paired_runs,
                        expected_pairs=expected_pairs, exhaustion="run_budget",
                    )
                arms: dict[str, ArmEvidence] = {}
                for arm in arm_order:
                    if now() >= deadline_at:
                        return _finish(
                            "inconclusive", evidence_class,
                            reason="frozen deadline exhausted before the valid stop",
                            admissions=admissions, run_digests=run_digests,
                            final_runs=final_runs, paired_runs=paired_runs,
                            expected_pairs=expected_pairs, exhaustion="deadline",
                        )
                    is_final = repeat_index == valid_after - 1 and seed == seeds[-1]
                    evidence = run_arm(role, arm, repeat_index, seed, is_final)
                    if now() >= deadline_at:
                        return _finish(
                            repeated["limits"]["exhaustion_outcome"],
                            evidence_class,
                            reason="frozen deadline exhausted before arm evidence could be retained",
                            admissions=admissions,
                            run_digests=run_digests,
                            final_runs=final_runs,
                            paired_runs=paired_runs,
                            expected_pairs=expected_pairs,
                            exhaustion="deadline",
                        )
                    label = f"{role}.repeat-{repeat_index}.seed-{seed}.{arm}"
                    arms[arm] = evidence
                    admissions[label] = evidence.eligibility.to_dict()
                    run_digests[label] = evidence.context["run_digest"]
                    final_runs[f"{role}_{arm}"] = evidence

                    eligibility = evidence.eligibility
                    if eligibility.integrity_status == "invalid":
                        return _finish(
                            "invalid", eligibility.evidence_class,
                            reason=f"{label} evidence integrity is invalid",
                            admissions=admissions, run_digests=run_digests,
                            final_runs=final_runs,
                            integrity_errors=eligibility.integrity_errors,
                        )
                    if protocol["evidence_mode"] == "benchmark" and not eligibility.acceptance_eligible:
                        outcome = repeated["outcome_handling"]["quarantined"]
                        decision = outcome if outcome in {"invalid", "inconclusive"} else "invalid"
                        return _finish(
                            decision, eligibility.evidence_class,
                            reason=f"{label} benchmark arm was not admitted",
                            admissions=admissions, run_digests=run_digests,
                            final_runs=final_runs,
                            quarantined_tasks=eligibility.quarantined_tasks,
                        )
                    if not evidence.run.run_valid:
                        return _finish(
                            "invalid", eligibility.evidence_class,
                            reason=f"{label} contains invalidating task results",
                            admissions=admissions, run_digests=run_digests,
                            final_runs=final_runs,
                        )

                try:
                    validate_paired_contexts(
                        arms["baseline"].context,
                        arms["treatment"].context,
                        protocol_snapshot=protocol,
                    )
                except IdentityError as exc:
                    return _finish(
                        "invalid", evidence_class,
                        reason=f"paired run identity mismatch: {exc}",
                        admissions=admissions, run_digests=run_digests,
                        final_runs=final_runs,
                    )
                activation_errors = validate_activation(
                    role, arms["baseline"], arms["treatment"]
                )
                if activation_errors:
                    return _finish(
                        "invalid", evidence_class,
                        reason="paired activation evidence is invalid",
                        admissions=admissions, run_digests=run_digests,
                        final_runs=final_runs,
                        activation_errors=activation_errors,
                    )
                quarantined = set(arms["baseline"].eligibility.quarantined_tasks)
                quarantined.update(arms["treatment"].eligibility.quarantined_tasks)
                comparison = compare_runs(
                    arms["baseline"].run,
                    arms["treatment"].run,
                    policy=validity_policy,
                    quorum_coverage_floor=float(
                        repeated["coverage"]["quorum_fraction"]
                    ),
                    task_sources=task_sources,
                    quarantined=quarantined,
                )
                if not comparison.eligible:
                    return _finish(
                        "inconclusive", evidence_class,
                        reason="valid paired evidence does not meet frozen coverage/quorum",
                        admissions=admissions, run_digests=run_digests,
                        final_runs=final_runs, comparison_reasons=comparison.reasons,
                    )
                comparisons[role].append(comparison)
                treatment_statuses.append(dict(arms["treatment"].run.statuses))
                paired_runs += 1

    dev = comparisons["dev"]
    regression = comparisons["regression"]
    if len(dev) < required_pairs or len(regression) < required_pairs:
        return _finish(
            "inconclusive", evidence_class,
            reason="valid evidence has not reached the frozen stopping rule",
            admissions=admissions, run_digests=run_digests,
            final_runs=final_runs, paired_runs=paired_runs,
            required_pairs=required_pairs,
        )

    original_tasks = set(task_sources)
    compared = sum(item.compared_task_count for item in dev)
    denominator = len(original_tasks) * len(dev)
    coverage = compared / denominator if denominator else 0.0
    valid_sources = {
        task_sources[task_id]
        for item in dev
        for task_id in original_tasks
        if task_id in item.fixed
        or task_id in item.regressed
        or (
            item.baseline_success is not None
            and item.treatment_success is not None
        )
    }
    required_sources = set(repeated["coverage"]["required_sources"])
    minimum_coverage = float(repeated["coverage"]["minimum_fraction"])
    if coverage < minimum_coverage or not required_sources <= valid_sources:
        return _finish(
            "inconclusive", evidence_class,
            reason="repeated evidence misses frozen coverage or source-family presence",
            admissions=admissions, run_digests=run_digests,
            final_runs=final_runs, coverage=coverage,
            minimum_coverage=minimum_coverage,
            missing_sources=sorted(required_sources - valid_sources),
        )

    dev_deltas = [
        float(item.treatment_success) - float(item.baseline_success)
        for item in dev
        if item.baseline_success is not None and item.treatment_success is not None
    ]
    if not dev_deltas:
        return _finish(
            "inconclusive", evidence_class,
            reason="no valid paired treatment-effect observations",
            admissions=admissions, run_digests=run_digests,
            final_runs=final_runs,
        )
    effect = sum(dev_deltas) / len(dev_deltas)
    # The sole supported frozen uncertainty construction is the observed range
    # over all complete paired development blocks.  Its lower endpoint also
    # implements the all-block multiplicity rule for acceptance.
    lower = min(dev_deltas)
    upper = max(dev_deltas)
    minimum_effect = float(repeated["effect"]["minimum_effect"])

    dev_regressed = {task for item in dev for task in item.regressed}
    regression_regressed = {task for item in regression for task in item.regressed}
    protected_regressions = sorted(dev_regressed | regression_regressed)
    max_regressions = int(repeated["regression"]["max_regressions"])
    if len(protected_regressions) > max_regressions:
        return _finish(
            "rejected", evidence_class,
            reason="repeated evidence establishes a protected regression",
            admissions=admissions, run_digests=run_digests,
            final_runs=final_runs, protected_regressions=protected_regressions,
            max_regressions=max_regressions,
        )

    non_inferiority_margin = float(repeated["non_inferiority"]["margin"])
    champion_margin = float(repeated["champion"]["margin"])
    if lower < -non_inferiority_margin:
        return _finish(
            "rejected", evidence_class,
            reason="repeated evidence violates paired non-inferiority protection",
            admissions=admissions, run_digests=run_digests,
            final_runs=final_runs, effect_lower=lower,
            non_inferiority_margin=non_inferiority_margin,
        )

    candidate_successes: dict[str, int] = {}
    candidate_observations: dict[str, int] = {}
    for statuses in treatment_statuses:
        for task_id, status in statuses.items():
            candidate_observations[task_id] = candidate_observations.get(task_id, 0) + 1
            candidate_successes[task_id] = candidate_successes.get(task_id, 0) + int(
                status == "passed"
            )
    candidate_rates = {
        task_id: candidate_successes[task_id] / observations
        for task_id, observations in sorted(candidate_observations.items())
    }
    protected_tasks = set(accepted_protection["protected_tasks"])
    missing_protected = sorted(protected_tasks - set(candidate_rates))
    if missing_protected:
        return _finish(
            "inconclusive", evidence_class,
            reason="durable champion tasks lack current repeated evidence",
            admissions=admissions, run_digests=run_digests,
            final_runs=final_runs, missing_protected_tasks=missing_protected,
        )
    durable_regressions = sorted(
        task_id
        for task_id in protected_tasks
        if candidate_rates[task_id]
        < float(accepted_protection["success_rates"][task_id]) - champion_margin
    )
    if durable_regressions:
        return _finish(
            "rejected", evidence_class,
            reason="candidate regresses durable champion evidence",
            admissions=admissions, run_digests=run_digests,
            final_runs=final_runs, durable_regressions=durable_regressions,
            champion_sha=accepted_protection["champion_sha"],
            champion_margin=champion_margin,
            candidate_success_rates=candidate_rates,
        )

    if transfer_status == "regressed":
        return _finish(
            "rejected", evidence_class,
            reason="scheduled transfer protection established a regression",
            admissions=admissions, run_digests=run_digests,
            final_runs=final_runs,
        )
    if transfer_status not in {"not_due", "supported"}:
        return _finish(
            "inconclusive", evidence_class,
            reason="scheduled transfer protection lacks sufficient evidence",
            admissions=admissions, run_digests=run_digests,
            final_runs=final_runs, transfer_status=transfer_status,
        )

    predicted = predicted_task_ids & original_tasks
    fix_counts = {
        task: sum(task in item.fixed for item in dev)
        for task in predicted
    }
    fixes = {task for task, count in fix_counts.items() if count == len(dev)}
    partial_fixes = {task for task, count in fix_counts.items() if 0 < count < len(dev)}
    predicted_regressions = {
        task for item in dev for task in item.regressed if task in predicted
    }
    if not fixes:
        if partial_fixes:
            return _finish(
                "inconclusive", evidence_class,
                reason="repeated evidence cannot resolve the prespecified predicted flip",
                admissions=admissions, run_digests=run_digests,
                final_runs=final_runs,
                partial_predicted_fixes=sorted(partial_fixes),
                required_repeat_support=len(dev),
            )
        return _finish(
            "rejected", evidence_class,
            reason="powered repeated evidence misses every prespecified predicted flip",
            admissions=admissions, run_digests=run_digests,
            final_runs=final_runs, predicted_tasks=sorted(predicted),
        )
    if predicted_regressions:
        return _finish(
            "inconclusive", evidence_class,
            reason="repeated evidence cannot resolve the prespecified predicted flip",
            admissions=admissions, run_digests=run_digests,
            final_runs=final_runs,
            predicted_regressions=sorted(predicted_regressions),
        )
    prediction_precision = len(fixes) / len(predicted) if predicted else 0.0
    if prediction_precision < min_prediction_precision:
        return _finish(
            "rejected", evidence_class,
            reason="prespecified predicted-flip precision is below the frozen floor",
            admissions=admissions, run_digests=run_digests,
            final_runs=final_runs,
            prediction_precision=prediction_precision,
            min_prediction_precision=min_prediction_precision,
        )

    fixed_tasks = sorted(
        task_id
        for task_id in original_tasks
        if all(task_id in item.fixed for item in dev)
    )
    candidate_protected_tasks = sorted(
        task_id
        for task_id, successes in candidate_successes.items()
        if successes == candidate_observations[task_id]
    )
    if effect > minimum_effect and lower > minimum_effect:
        decision = "accepted"
        reason = "prespecified repeated benefit and every protection are satisfied"
    elif upper <= minimum_effect:
        decision = "rejected"
        reason = "powered repeated evidence does not exceed the minimum effect"
    else:
        decision = "inconclusive"
        reason = "valid repeated evidence is too uncertain to decide"
    return _finish(
        decision, evidence_class, reason=reason,
        admissions=admissions, run_digests=run_digests,
        final_runs=final_runs, paired_runs=paired_runs,
        effect=effect, effect_lower=lower, effect_upper=upper,
        minimum_effect=minimum_effect, coverage=coverage,
        predicted_fixes=sorted(fixes),
        partial_predicted_fixes=sorted(partial_fixes),
        prediction_precision=prediction_precision,
        fixed=fixed_tasks,
        regressed=protected_regressions,
        protected_regressions=protected_regressions,
        candidate_success_rates=candidate_rates,
        candidate_protected_tasks=candidate_protected_tasks,
        champion_sha=accepted_protection["champion_sha"],
        protections={
            "non_inferiority": True,
            "current_champion": not durable_regressions,
            "regression": True,
            "transfer": transfer_status,
            "multiplicity_rule": repeated["multiplicity"],
        },
        comparisons={
            role: [item.to_dict() for item in rows]
            for role, rows in comparisons.items()
        },
    )
