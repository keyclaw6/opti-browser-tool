"""Paired baseline/treatment comparison with fail-closed validity.

Replaces auto-harness's monotonic ``val_score >= best`` ratchet (ADR-0015 §8):
on stochastic browser tasks a lucky run ratchets the bar and locks progress.
Instead a treatment is compared against its own iteration baseline on the
same tasks, within a measured noise band.

Validity policies (ADR-0005; thresholds TBD-from-measurement):

- ``strict`` (default — matches the documented eval-harness rule): any
  ``invalid``/``error``/``skipped`` result in either run makes the comparison
  ineligible for acceptance.
- ``quorum`` (proposed in ADR-0005, NOT the default): compare on the
  valid-in-both intersection, requiring a coverage floor and no source
  family entirely absent.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .evaluate import EvalRun


@dataclass(slots=True)
class Comparison:
    policy: str
    eligible: bool
    reasons: list[str] = field(default_factory=list)
    compared_task_count: int = 0
    coverage: float = 0.0
    fixed: list[str] = field(default_factory=list)  # fail -> pass
    regressed: list[str] = field(default_factory=list)  # pass -> fail
    baseline_success: float | None = None
    treatment_success: float | None = None
    simulated: bool = False  # true when either run is not benchmark-reportable

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy": self.policy,
            "eligible": self.eligible,
            "reasons": self.reasons,
            "compared_task_count": self.compared_task_count,
            "coverage": round(self.coverage, 4),
            "fixed": self.fixed,
            "regressed": self.regressed,
            "baseline_success": self.baseline_success,
            "treatment_success": self.treatment_success,
            "simulated": self.simulated,
        }


def compare_runs(
    baseline: EvalRun,
    treatment: EvalRun,
    *,
    policy: str = "strict",
    quorum_coverage_floor: float = 0.9,
    task_sources: dict[str, str] | None = None,
    quarantined: set[str] | None = None,
) -> Comparison:
    """``quarantined``: tasks with a pending evaluation-plane quarantine entry
    (ADR-0016 T3). Strict policy fails closed — a comparison touching a
    quarantined task is ineligible until the project owner resolves the entry.
    Quorum policy excludes those tasks from the valid intersection instead."""
    comparison = Comparison(policy=policy, eligible=True)
    comparison.simulated = not (
        baseline.acceptance_decision_eligible and treatment.acceptance_decision_eligible
    )

    all_ids = set(baseline.statuses) | set(treatment.statuses)
    quarantined_here = sorted((quarantined or set()) & all_ids)
    if quarantined_here:
        if policy == "strict":
            comparison.eligible = False
            comparison.reasons.append(
                "quarantine pending on compared task(s): "
                + ", ".join(quarantined_here[:10])
                + " — resolve via `opti-judge quarantine` before this comparison can decide anything"
            )
        else:
            all_ids -= set(quarantined_here)
            comparison.reasons.append(
                f"{len(quarantined_here)} quarantined task(s) excluded from the valid intersection"
            )
    valid_both = (baseline.valid_ids & treatment.valid_ids) - set(quarantined_here or [])
    comparison.compared_task_count = len(valid_both)
    comparison.coverage = len(valid_both) / len(all_ids) if all_ids else 0.0

    if policy == "strict":
        if not baseline.run_valid:
            comparison.eligible = False
            comparison.reasons.append(
                "baseline run contains invalid/error/skipped results (strict policy)"
            )
        if not treatment.run_valid:
            comparison.eligible = False
            comparison.reasons.append(
                "treatment run contains invalid/error/skipped results (strict policy)"
            )
    elif policy == "quorum":
        if comparison.coverage < quorum_coverage_floor:
            comparison.eligible = False
            comparison.reasons.append(
                f"valid-in-both coverage {comparison.coverage:.2%} is below the "
                f"floor {quorum_coverage_floor:.0%}"
            )
        if task_sources:
            sources_all = {task_sources.get(tid, "unknown") for tid in all_ids}
            sources_valid = {task_sources.get(tid, "unknown") for tid in valid_both}
            missing = sorted(sources_all - sources_valid)
            if missing:
                comparison.eligible = False
                comparison.reasons.append(
                    f"source families absent from the valid intersection: {', '.join(missing)}"
                )
    else:
        raise ValueError(f"unknown validity policy: {policy}")

    base_pass = baseline.passed_ids & valid_both
    treat_pass = treatment.passed_ids & valid_both
    comparison.fixed = sorted(treat_pass - base_pass)
    comparison.regressed = sorted(base_pass - treat_pass)
    if valid_both:
        comparison.baseline_success = round(len(base_pass) / len(valid_both), 4)
        comparison.treatment_success = round(len(treat_pass) / len(valid_both), 4)
    return comparison


@dataclass(slots=True)
class NoiseBand:
    """Measured run-to-run variability of the *unchanged* baseline."""

    aggregate_margin: float
    max_benign_flips: int
    sample_runs: int
    synthetic: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "aggregate_margin": self.aggregate_margin,
            "max_benign_flips": self.max_benign_flips,
            "sample_runs": self.sample_runs,
            "synthetic": self.synthetic,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "NoiseBand":
        return cls(
            aggregate_margin=float(payload["aggregate_margin"]),
            max_benign_flips=int(payload["max_benign_flips"]),
            sample_runs=int(payload.get("sample_runs", 0)),
            synthetic=bool(payload.get("synthetic", True)),
        )


def measure_noise_band(runs: list[EvalRun], *, synthetic: bool) -> NoiseBand:
    """Estimate the band from repeated identical-configuration baseline runs."""
    if len(runs) < 2:
        raise ValueError("noise-band measurement needs at least two runs")
    rates = [
        run.summary.get("strict_success_rate") or 0.0 for run in runs
    ]
    aggregate_margin = max(rates) - min(rates)
    max_flips = 0
    first = runs[0]
    for other in runs[1:]:
        flips = len(
            (first.passed_ids - other.passed_ids) | (other.passed_ids - first.passed_ids)
        )
        max_flips = max(max_flips, flips)
    return NoiseBand(
        aggregate_margin=round(aggregate_margin, 4),
        max_benign_flips=max_flips,
        sample_runs=len(runs),
        synthetic=synthetic,
    )
