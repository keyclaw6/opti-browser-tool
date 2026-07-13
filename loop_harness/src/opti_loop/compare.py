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

    # F14: coverage and the source-universe are measured against the ORIGINAL
    # task universe, never a universe already shrunk by quarantine. Otherwise
    # quarantining an entire source family reports 100% coverage and stays
    # eligible while a whole family has silently vanished.
    original_ids = set(baseline.statuses) | set(treatment.statuses)
    quarantined_here = sorted((quarantined or set()) & original_ids)
    valid_both = (baseline.valid_ids & treatment.valid_ids) - set(quarantined_here)
    comparison.compared_task_count = len(valid_both)
    comparison.coverage = len(valid_both) / len(original_ids) if original_ids else 0.0

    if quarantined_here and policy == "strict":
        comparison.eligible = False
        comparison.reasons.append(
            "quarantine pending on compared task(s): "
            + ", ".join(quarantined_here[:10])
            + " — resolve via `opti-judge quarantine` before this comparison can decide anything"
        )
    elif quarantined_here:
        comparison.reasons.append(
            f"{len(quarantined_here)} quarantined task(s) excluded from the valid intersection"
        )

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
                f"valid-in-both coverage {comparison.coverage:.2%} of the original suite "
                f"is below the floor {quorum_coverage_floor:.0%}"
            )
        if task_sources:
            # Universe of families is taken from the ORIGINAL ids; any family
            # with no valid task in the intersection makes the run ineligible.
            sources_all = {task_sources.get(tid, "unknown") for tid in original_ids}
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


class NoiseBandError(ValueError):
    """A noise band is out of range or bound to a different run identity (F07)."""


@dataclass(slots=True)
class NoiseBand:
    """Measured run-to-run variability of the *unchanged* baseline.

    Bound to a ``run_identity`` hash (F07): a band measured under one
    catalog/suite/adapter/task-set configuration cannot be silently reused to
    judge a treatment run under a different configuration. Values are range-
    validated on construction so a hand-written ``aggregate_margin: 99`` or
    ``max_benign_flips: 999999`` is rejected instead of widening tolerance.
    """

    aggregate_margin: float
    max_benign_flips: int
    sample_runs: int
    synthetic: bool
    task_count: int = 0
    run_identity: str = ""

    def __post_init__(self) -> None:
        if not (0.0 <= self.aggregate_margin <= 1.0):
            raise NoiseBandError(f"aggregate_margin {self.aggregate_margin} outside [0, 1]")
        if self.max_benign_flips < 0:
            raise NoiseBandError("max_benign_flips must be >= 0")
        if self.task_count and self.max_benign_flips > self.task_count:
            raise NoiseBandError(
                f"max_benign_flips {self.max_benign_flips} exceeds task_count {self.task_count}"
            )
        if self.sample_runs < 2:
            raise NoiseBandError("a noise band requires at least two sample runs")

    def to_dict(self) -> dict[str, Any]:
        return {
            "aggregate_margin": self.aggregate_margin,
            "max_benign_flips": self.max_benign_flips,
            "sample_runs": self.sample_runs,
            "synthetic": self.synthetic,
            "task_count": self.task_count,
            "run_identity": self.run_identity,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "NoiseBand":
        return cls(
            aggregate_margin=float(payload["aggregate_margin"]),
            max_benign_flips=int(payload["max_benign_flips"]),
            sample_runs=int(payload.get("sample_runs", 0)),
            synthetic=bool(payload.get("synthetic", True)),
            task_count=int(payload.get("task_count", 0)),
            run_identity=str(payload.get("run_identity", "")),
        )

    def matches_identity(self, run_identity: str) -> bool:
        return bool(self.run_identity) and self.run_identity == run_identity


def measure_noise_band(
    runs: list[EvalRun], *, synthetic: bool, run_identity: str = ""
) -> NoiseBand:
    """Estimate the band from repeated identical-configuration baseline runs.

    Requires at least two runs over the same task set; a run whose validity or
    task set differs is rejected (F07) rather than folded in.
    """
    if len(runs) < 2:
        raise NoiseBandError("noise-band measurement needs at least two runs")
    task_sets = {frozenset(run.statuses) for run in runs}
    if len(task_sets) != 1:
        raise NoiseBandError("noise-band runs must cover an identical task set")
    task_count = len(next(iter(task_sets)))
    rates = [run.summary.get("strict_success_rate") or 0.0 for run in runs]
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
        task_count=task_count,
        run_identity=run_identity,
    )
