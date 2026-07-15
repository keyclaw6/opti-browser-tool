"""The Conductor: transactional phase driver over a trusted boundary.

Rewritten after the review. The iteration boundary is now owner-controlled:

- ``start`` captures the trusted ``accepted_base_sha``, creates an isolated
  candidate **worktree** at that base (the optimizer's only writable surface),
  runs the baseline + regression baseline there, distills, and writes the
  packet — all into the owner-only trusted store.
- the optimizer edits only the frozen campaign candidate allowlist in the
  worktree, commits once, and drops a ``manifest.json`` in the worktree root.
- ``run_iteration`` is a SINGLE atomic transaction (F02, F06): it ingests and
  validates the manifest, runs the E0–E5 ladder over the ``base..candidate``
  commit diff, appends attribution, writes the gate report + ledger row to the
  trusted store, advances accepted state ONLY on ``(accepted, benchmark)``, and
  resets the worktree either way. There is no separate, forgeable record step.

Regression memory is seeded from the accepted-base run at ``start`` and is
never refreshed from a rejected treatment (F06).
"""
from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path
from typing import Any

from opti_eval.catalog import load_catalog
from opti_eval.identity import LiveRunReceipt, expected_live_run_receipt

from . import fileguard, gitutil
from .analyst import StubAnalyst
from .campaign import Campaign
from .clusters import load_register, ranked_unresolved, save_register, update_after_iteration
from .compare import NoiseBand, NoiseBandError, measure_noise_band
from .eligibility import Eligibility, assess
from .evaluate import EvalRun, load_run, run_suite
from .gates import GateReport, run_gate
from .ledger import learnings_template
from .manifest import load_and_validate, rejected_submission_record
from .packet import build_packet
from .protocol import (
    ProtocolError,
    build_protocol_snapshot,
    freeze_protocol,
    load_frozen_protocol,
    run_context,
    verify_runtime_bindings,
)
from .store import append_jsonl, atomic_write_json
from .verdict import Verdict

DEV_BASELINE_DIR = "eval/dev_baseline"
ACCEPTED_REF = "refs/opti/{campaign}/accepted"


# ── helpers ───────────────────────────────────────────────────────────────
def _catalog(repo_root: Path) -> dict[str, dict[str, Any]]:
    _, records = load_catalog(repo_root)
    return records


def _task_sources(records: dict[str, dict[str, Any]]) -> dict[str, str]:
    return {tid: str(rec.get("source", "unknown")) for tid, rec in records.items()}


def _protocol_task_ids(protocol: dict[str, Any], role: str) -> list[str]:
    matches = [suite for suite in protocol["suites"] if suite["role"] == role]
    if len(matches) != 1:
        raise RuntimeError(f"frozen protocol has no unique suite role {role!r}")
    return [task["id"] for task in matches[0]["tasks"]]


def _assess_exact_run(
    campaign: Campaign,
    run: EvalRun,
    expected_receipt: LiveRunReceipt,
    *,
    label: str,
) -> dict[str, Any] | None:
    eligibility: Eligibility = assess(
        run=run,
        run_dir=run.output_dir,
        expected_receipt=expected_receipt,
        task_records=run.task_records,
        admissions_path=campaign.store.admissions_path,
        quarantine_path=campaign.store.quarantine_path,
    )
    if expected_receipt.evidence_mode != "benchmark":
        return None
    if (
        eligibility.integrity_status != "valid"
        or not eligibility.acceptance_eligible
        or eligibility.admission_receipt is None
    ):
        detail = eligibility.integrity_errors or eligibility.reasons
        raise RuntimeError(
            f"{label} failed AR-003 evidence admission: "
            + ("; ".join(detail) if detail else "no admission receipt")
        )
    return eligibility.admission_receipt


def _revalidate_admission_anchor(
    campaign: Campaign,
    run: EvalRun,
    expected_receipt: LiveRunReceipt,
    anchor: object,
    *,
    label: str,
) -> None:
    fresh = _assess_exact_run(campaign, run, expected_receipt, label=label)
    if expected_receipt.evidence_mode == "benchmark" and fresh != anchor:
        raise RuntimeError(f"{label} AR-003 admission anchor is missing or tampered")
    if expected_receipt.evidence_mode != "benchmark" and anchor is not None:
        raise RuntimeError(f"{label} synthetic run carries a benchmark admission anchor")


def _load_accepted_run(campaign: Campaign) -> EvalRun | None:
    raw_path = campaign.state.get("last_accepted_treatment_dir")
    anchor = campaign.state.get("last_accepted_admission_receipt")
    if not raw_path:
        if anchor is not None:
            raise RuntimeError("accepted treatment path is missing for its AR-003 anchor")
        return None
    if not Path(raw_path).is_dir():
        raise RuntimeError("accepted treatment evidence directory is missing")
    if not isinstance(anchor, dict):
        raise RuntimeError("accepted treatment is missing its AR-003 admission anchor")
    try:
        expected_receipt = LiveRunReceipt(
            protocol_digest=anchor["protocol_digest"],
            run_digest=anchor["run_digest"],
            adapter_digest=anchor["adapter_digest"],
            evidence_mode="benchmark",
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("accepted treatment AR-003 admission anchor is malformed") from exc
    accepted = load_run(
        Path(raw_path),
        "accepted-treatment",
        expected_receipt=expected_receipt,
    )
    _revalidate_admission_anchor(
        campaign,
        accepted,
        expected_receipt,
        anchor,
        label="accepted treatment",
    )
    return accepted


def _revalidate_noise_band_for_decision(
    campaign: Campaign,
    band: NoiseBand,
    current_protocol: dict[str, Any],
) -> None:
    """Reload every real calibration sample and reproduce its AR-003 receipt."""
    if band.synthetic:
        return
    try:
        current_binding = current_protocol["calibration_binding_digest"]
        if band.run_identity != current_binding:
            raise NoiseBandError(
                "noise band does not match the current iteration calibration binding"
            )
        campaign_root = campaign.store.campaign_dir
        if campaign_root.is_symlink() or not campaign_root.is_dir():
            raise NoiseBandError("campaign evidence root is missing or a symlink")
        root_resolved = campaign_root.resolve(strict=True)
        calibration_protocol = load_frozen_protocol(campaign_root / "noise")
        if (
            calibration_protocol["purpose"] != "noise-calibration"
            or calibration_protocol["iteration"] != 0
        ):
            raise NoiseBandError("frozen noise protocol has the wrong purpose or iteration")
        if calibration_protocol["calibration_binding_digest"] != current_binding:
            raise NoiseBandError(
                "frozen noise protocol does not match the current calibration binding"
            )
        repeat_count = calibration_protocol["repeated_protocol"]["repeats"][
            "count"
        ]
        task_ids = _protocol_task_ids(calibration_protocol, "dev")
        if repeat_count != band.sample_runs or len(task_ids) != band.task_count:
            raise NoiseBandError(
                "noise sample count or task count does not match its frozen protocol"
            )
        seed = int(
            calibration_protocol["repeated_protocol"]["matched_blocks"]["seeds"][0]
        )
        fresh_samples: list[EvalRun] = []
        for index, anchor in enumerate(band.sample_anchors):
            expected_relative = f"noise/run-{index:02d}"
            if anchor.evidence_dir != expected_relative:
                raise NoiseBandError(
                    "noise sample directories are duplicated, missing, or out of order"
                )
            sample_dir = campaign_root
            for part in anchor.evidence_dir.split("/"):
                sample_dir = sample_dir / part
                if sample_dir.is_symlink():
                    raise NoiseBandError(
                        f"noise sample path redirects through a symlink: {anchor.evidence_dir}"
                    )
            if not sample_dir.is_dir():
                raise NoiseBandError(
                    f"noise sample evidence directory is missing: {anchor.evidence_dir}"
                )
            resolved_sample = sample_dir.resolve(strict=True)
            try:
                resolved_sample.relative_to(root_resolved)
            except ValueError as exc:
                raise NoiseBandError(
                    f"noise sample evidence escapes the campaign store: {anchor.evidence_dir}"
                ) from exc
            receipt = anchor.admission_receipt
            context = run_context(
                calibration_protocol,
                calibration_protocol["accepted_build"],
                arm="baseline",
                suite_role="dev",
                task_ids=task_ids,
                repeat_index=index,
                seed=seed,
                run_id=receipt.run_id,
            )
            expected_receipt = expected_live_run_receipt(
                calibration_protocol,
                run_digest=context["run_digest"],
            )
            if (
                receipt.protocol_digest != expected_receipt.protocol_digest
                or receipt.run_digest != expected_receipt.run_digest
                or receipt.adapter_digest != expected_receipt.adapter_digest
            ):
                raise NoiseBandError(
                    f"noise sample {index} anchor does not match its frozen run identity"
                )
            sample = load_run(
                resolved_sample,
                "noise-calibration",
                expected_receipt=expected_receipt,
            )
            _revalidate_admission_anchor(
                campaign,
                sample,
                expected_receipt,
                receipt.to_dict(),
                label=f"noise sample {index}",
            )
            fresh_samples.append(sample)
        fresh_band = measure_noise_band(
            fresh_samples,
            synthetic=False,
            run_identity=current_binding,
            evidence_root=campaign_root,
        )
        if fresh_band.to_dict() != band.to_dict():
            raise NoiseBandError(
                "persisted noise-band authority does not match freshly measured samples"
            )
        band.mark_anchors_validated()
    except NoiseBandError:
        raise
    except (KeyError, OSError, ProtocolError, RuntimeError, TypeError, ValueError) as exc:
        raise NoiseBandError(f"benchmark noise evidence is invalid: {exc}") from exc


def _write_trusted_manifest_snapshot(
    iteration_dir: Path,
    manifest: dict[str, Any],
    verdict: Verdict,
    attribution: dict[str, Any] | None = None,
    *,
    original_submission: object = None,
    validation_errors: list[str] | None = None,
) -> None:
    """Stamp conductor-owned fields for every terminal iteration outcome."""
    if validation_errors:
        snapshot = rejected_submission_record(
            original_submission=original_submission,
            validation_errors=validation_errors,
            verdict=verdict.to_dict(),
        )
    else:
        snapshot = {key: value for key, value in manifest.items() if key != "attribution"}
        if attribution is not None:
            snapshot["attribution"] = attribution
        snapshot["status"] = verdict.label
    atomic_write_json(iteration_dir / "manifest.snapshot.json", snapshot)


# ── phase A + C: start ──────────────────────────────────────────────────
def start_iteration(campaign: Campaign) -> dict[str, Any]:
    if campaign.state.get("pending_iteration"):
        raise RuntimeError(
            f"iteration {campaign.state['pending_iteration']} is already pending; "
            "run `opti-loop run-iteration` first"
        )
    learnings_incomplete = (
        campaign.learnings_path.is_file()
        and "<fill in" in campaign.learnings_path.read_text(encoding="utf-8").split("## Iteration")[-1]
    )
    previous_accepted = _load_accepted_run(campaign)

    base_sha = str(campaign.state["accepted_base_sha"])
    worktree = campaign.worktree_path
    number = campaign.current_iteration + 1
    iteration_dir = campaign.iteration_dir(number)
    if iteration_dir.exists() or iteration_dir.is_symlink():
        raise RuntimeError(
            f"next iteration path already exists; refusing to consume iteration {number}: "
            f"{iteration_dir}"
        )
    state_before = copy.deepcopy(campaign.state)
    worktree_created = False
    try:
        gitutil.worktree_add(campaign.repo_root, worktree, base_sha)
        worktree_created = True
        records = _catalog(worktree)
        sources = _task_sources(records)
        protocol = build_protocol_snapshot(
            campaign, worktree, iteration=number, purpose="iteration"
        )
        freeze_protocol(iteration_dir, protocol)
        opened_number = campaign.open_iteration()
        if opened_number != number:
            raise RuntimeError("campaign iteration changed during protocol preflight")
        execution = protocol["execution"]
        accepted_build = protocol["accepted_build"]
        seed = int(protocol["repeated_protocol"]["matched_blocks"]["seeds"][0])

        # A — EVALUATE baseline on the accepted-base harness.
        baseline_context = run_context(
            protocol,
            accepted_build,
            arm="baseline",
            suite_role="dev",
            task_ids=_protocol_task_ids(protocol, "dev"),
            seed=seed,
        )
        verify_runtime_bindings(
            protocol, admissions_path=campaign.store.admissions_path
        )
        baseline = run_suite(
            repo_root=worktree,
            suite_name=execution["suites"]["dev"],
            adapter_config=execution["adapter"],
            output_dir=iteration_dir / DEV_BASELINE_DIR,
            protocol_snapshot=protocol,
            run_context=baseline_context,
        )
        baseline_admission = _assess_exact_run(
            campaign,
            baseline,
            expected_live_run_receipt(
                protocol, run_digest=baseline_context["run_digest"]
            ),
            label="development baseline",
        )

        # Seed regression memory from the accepted base (frozen; never a
        # rejected treatment) so E4 has a real denominator (F06).
        regression_context = run_context(
            protocol,
            accepted_build,
            arm="baseline",
            suite_role="regression",
            task_ids=_protocol_task_ids(protocol, "regression"),
            seed=seed,
        )
        verify_runtime_bindings(
            protocol, admissions_path=campaign.store.admissions_path
        )
        regression_base = run_suite(
            repo_root=worktree,
            suite_name=execution["suites"]["regression"],
            adapter_config=execution["adapter"],
            output_dir=iteration_dir / "eval" / "regression_baseline",
            protocol_snapshot=protocol,
            run_context=regression_context,
        )
        regression_admission = _assess_exact_run(
            campaign,
            regression_base,
            expected_live_run_receipt(
                protocol, run_digest=regression_context["run_digest"]
            ),
            label="regression baseline",
        )
    except Exception:
        campaign.state = state_before
        campaign.save_state()
        if iteration_dir.exists() and not iteration_dir.is_symlink():
            shutil.rmtree(iteration_dir)
        if worktree_created:
            gitutil.worktree_remove(campaign.repo_root, worktree)
        raise

    # Drift vs the previous accepted treatment.
    drift = None
    if previous_accepted is not None:
        changed = sorted(t for t in baseline.statuses
                         if baseline.statuses.get(t) != previous_accepted.statuses.get(t))
        drift = {"tasks_changed_since_accepted_treatment": changed}
        atomic_write_json(iteration_dir / "drift.json", drift)

    # C — DISTILL (stub analyst until traces exist).
    analyst = StubAnalyst()
    analysis = analyst.distill(iteration=number, run=baseline, task_sources=sources,
                               out_dir=iteration_dir / "analysis")
    register = load_register(campaign.clusters_path)
    register = update_after_iteration(register, iteration=number,
                                       failed_by_cluster=analysis["failed_by_cluster"],
                                       fixed_task_ids=set(), analyst_version=analyst.version)
    save_register(campaign.clusters_path, register)

    # Exploration decision (ADR-0015 §9).
    quota = int(execution["exploration"].get("divergence_quota", 5))
    force_after = int(execution["exploration"].get("plateau_force_after", 4))
    since_div = int(campaign.state.get("iterations_since_divergent", 0))
    since_acc = int(campaign.state.get("iterations_since_accept", 0))
    divergent = (quota > 0 and since_div + 1 >= quota) or (force_after > 0 and since_acc >= force_after)

    build_packet(iteration_dir=iteration_dir, iteration=number, campaign_id=campaign.campaign_id,
                 divergent=divergent, ranked_clusters=ranked_unresolved(register),
                 ledger_path=campaign.ledger_path, baseline_summary=baseline.summary,
                 candidate_allowlist=protocol["candidate_allowlist"])

    campaign.state["pending_iteration"] = number
    campaign.state["pending_divergent"] = divergent
    campaign.state["pending_base_sha"] = base_sha
    campaign.state["pending_protocol_digest"] = protocol["protocol_digest"]
    campaign.state["pending_baseline_run_digest"] = baseline_context["run_digest"]
    campaign.state["pending_regression_baseline_run_digest"] = regression_context[
        "run_digest"
    ]
    campaign.state["pending_baseline_admission_receipt"] = baseline_admission
    campaign.state[
        "pending_regression_baseline_admission_receipt"
    ] = regression_admission
    campaign.save_state()

    result: dict[str, Any] = {
        "iteration": number,
        "divergent": divergent,
        "baseline_success": baseline.summary.get("strict_success_rate"),
        "worktree": str(worktree),
        "instructions": (
            "edit only the frozen candidate surface(s) "
            f"{', '.join(protocol['candidate_allowlist'])} in {worktree}, commit exactly one candidate "
            "commit, and write manifest.json in the worktree root; then run "
            "`opti-loop run-iteration`."
        ),
        "packet": str(iteration_dir / "PACKET.md"),
        "drift": drift,
    }
    if divergent:
        result["divergence_note"] = "cluster_ref must start with 'divergent' this iteration (ADR-0015 §9)"
    if learnings_incomplete:
        result["warning"] = "previous learnings entry has unfilled '<fill in' placeholders (PROGRAM.md §6)"
    return result


# ── phase E + B + F: one atomic transaction ───────────────────────────────
def run_iteration(campaign: Campaign) -> dict[str, Any]:
    number = int(campaign.state.get("pending_iteration") or 0)
    if not number:
        raise RuntimeError("no pending iteration — run `opti-loop start` first")
    iteration_dir = campaign.iteration_dir(number)
    protocol = load_frozen_protocol(iteration_dir)
    pending_digest = campaign.state.get("pending_protocol_digest")
    if pending_digest != protocol["protocol_digest"]:
        raise RuntimeError(
            "pending iteration protocol digest does not match the frozen protocol snapshot"
        )
    execution = protocol["execution"]
    worktree = campaign.worktree_path
    base_sha = str(campaign.state["pending_base_sha"])
    divergent = bool(campaign.state.get("pending_divergent", False))

    baseline_digest = campaign.state.get("pending_baseline_run_digest")
    if not isinstance(baseline_digest, str) or not baseline_digest:
        raise RuntimeError("pending iteration has no trusted baseline run digest")
    baseline_receipt = expected_live_run_receipt(
        protocol,
        run_digest=baseline_digest,
    )
    baseline = load_run(
        iteration_dir / DEV_BASELINE_DIR,
        execution["suites"]["dev"],
        expected_receipt=baseline_receipt,
    )
    _revalidate_admission_anchor(
        campaign,
        baseline,
        baseline_receipt,
        campaign.state.get("pending_baseline_admission_receipt"),
        label="pending development baseline",
    )
    regression_baseline_digest = campaign.state.get(
        "pending_regression_baseline_run_digest"
    )
    if not isinstance(regression_baseline_digest, str) or not regression_baseline_digest:
        raise RuntimeError("pending iteration has no trusted regression baseline run digest")
    regression_baseline_receipt = expected_live_run_receipt(
        protocol,
        run_digest=regression_baseline_digest,
    )
    regression_baseline = load_run(
        iteration_dir / "eval" / "regression_baseline",
        execution["suites"]["regression"],
        expected_receipt=regression_baseline_receipt,
    )
    _revalidate_admission_anchor(
        campaign,
        regression_baseline,
        regression_baseline_receipt,
        campaign.state.get("pending_regression_baseline_admission_receipt"),
        label="pending regression baseline",
    )
    records = baseline.task_records
    sources = baseline.task_sources

    # Ingest the manifest from the untrusted worktree; snapshot into the store.
    wt_manifest = worktree / "manifest.json"
    submitted_manifest: object = None
    if wt_manifest.is_file():
        raw_manifest = wt_manifest.read_text(encoding="utf-8")
        try:
            submitted_manifest = json.loads(raw_manifest)
        except json.JSONDecodeError:
            # There is no parsed JSON value to preserve; retain the exact text
            # as the rejected record's original submission.
            submitted_manifest = raw_manifest

    # Every downstream consumer receives a mapping even when the submitted
    # JSON is a scalar/array. Validation reads the optimizer-owned file while
    # the original parsed value is retained for the final trusted snapshot.
    manifest: dict[str, Any] = (
        submitted_manifest if isinstance(submitted_manifest, dict) else {}
    )

    candidate_sha = gitutil.head_sha(worktree)
    guard = fileguard.check_candidate(repo=campaign.repo_root, worktree=worktree,
                                      base_sha=base_sha, candidate_sha=candidate_sha,
                                      allowed_prefixes=tuple(protocol["candidate_allowlist"]))
    manifest_report = load_and_validate(wt_manifest,
                                        allowed_prefixes=tuple(protocol["candidate_allowlist"]),
                                        changed_files=guard.changed, divergent=divergent)

    # Pivot enforcement (F16): forbid a 3rd attempt at the same cluster+component.
    pivot_after = int(execution["exploration"].get("pivot_after_failures", 2))
    fingerprint = None
    if manifest_report.ok:
        fingerprint = f"{manifest.get('cluster_ref')}::{manifest.get('target_component')}"
        prior_failures = int(campaign.state.get("failed_attempts", {}).get(fingerprint, 0))
        if prior_failures >= pivot_after:
            return _reject_pivot(
                campaign,
                number,
                fingerprint,
                prior_failures,
                iteration_dir,
                base_sha,
                manifest,
            )

    # Noise band (validated; absurd values raise and become invalid).
    band: NoiseBand | None = None
    noise_band_error: str | None = None
    try:
        if execution.get("noise_band"):
            band = NoiseBand.from_dict(execution["noise_band"])
            _revalidate_noise_band_for_decision(campaign, band, protocol)
    except NoiseBandError as exc:
        noise_band_error = str(exc)
        band = None
    protocol_identity = protocol["calibration_binding_digest"]

    report: GateReport = run_gate(
        repo_root=campaign.repo_root, worktree=worktree, base_sha=base_sha, candidate_sha=candidate_sha,
        iteration=number, eval_root=iteration_dir / "eval", baseline_dev=baseline,
        manifest=manifest, manifest_report=manifest_report,
        adapter_config=execution["adapter"], suites=execution["suites"],
        thresholds=execution["thresholds"], noise_band=band, run_identity=protocol_identity,
        noise_band_error=noise_band_error,
        protocol_snapshot=protocol,
        task_sources=sources, task_records=records,
        regression_baseline=regression_baseline,
        admissions_path=campaign.store.admissions_path, quarantine_path=campaign.store.quarantine_path,
    )
    atomic_write_json(iteration_dir / "gate-report.json", report.to_dict())

    verdict: Verdict = report.verdict
    _write_trusted_manifest_snapshot(
        iteration_dir,
        manifest,
        verdict,
        report.attribution,
        original_submission=submitted_manifest,
        validation_errors=(manifest_report.errors if not manifest_report.ok else None),
    )

    fixed = set((report.comparison or {}).get("fixed", [])) if verdict.advances_accepted_state else set()
    promotion_candidates = sorted(fixed)

    if verdict.advances_accepted_state:
        register = load_register(campaign.clusters_path)
        register = update_after_iteration(register, iteration=number, failed_by_cluster={},
                                           fixed_task_ids=fixed, analyst_version="conductor-record")
        save_register(campaign.clusters_path, register)

    # Ledger + learnings (trusted store).
    append_jsonl(campaign.ledger_path, {
        "iteration": number, "campaign": campaign.campaign_id,
        "verdict": verdict.label, "decision": verdict.decision, "evidence_class": verdict.evidence_class,
        "advances_accepted_state": verdict.advances_accepted_state, "divergent": divergent,
        "base_sha": base_sha, "candidate_sha": candidate_sha,
        "protocol_digest": protocol["protocol_digest"],
        "hypothesis": manifest.get("hypothesis", ""), "target_component": manifest.get("target_component", ""),
        "cluster_ref": manifest.get("cluster_ref", ""),
        "gate_rungs": {r.rung: r.status for r in report.rungs},
        "comparison": report.comparison, "attribution": report.attribution,
        "eligibility": report.eligibility, "fixed_variables": execution["fixed_variables"],
        "promotion_candidates": promotion_candidates,
    })
    _append_learnings(campaign, number, verdict, manifest, divergent)

    # State transition + regression memory discipline (F06).
    if verdict.advances_accepted_state:
        accepted_treatment_digest = report.run_digests.get("dev_treatment")
        accepted_regression_digest = report.run_digests.get("regression_treatment")
        if not accepted_treatment_digest or not accepted_regression_digest:
            raise RuntimeError("accepted gate report is missing trusted treatment run digests")
        accepted_admission = report.admissions.get("dev_treatment", {}).get(
            "admission_receipt"
        )
        if not isinstance(accepted_admission, dict):
            raise RuntimeError("accepted gate report is missing AR-003 treatment admission")
        gitutil.update_ref(campaign.repo_root, ACCEPTED_REF.format(campaign=campaign.campaign_id), candidate_sha)
        campaign.state["accepted_base_sha"] = candidate_sha
        campaign.state.setdefault("accepted_iterations", []).append(number)
        campaign.state["iterations_since_accept"] = 0
        campaign.state["last_accepted_treatment_dir"] = str(iteration_dir / "eval" / "dev_treatment")
        campaign.state["last_accepted_admission_receipt"] = accepted_admission
        if fingerprint:
            campaign.state.get("failed_attempts", {}).pop(fingerprint, None)
    else:
        campaign.state["iterations_since_accept"] = int(campaign.state.get("iterations_since_accept", 0)) + 1
        if fingerprint:
            fa = campaign.state.setdefault("failed_attempts", {})
            fa[fingerprint] = int(fa.get(fingerprint, 0)) + 1

    campaign.state["iterations_since_divergent"] = (
        0 if divergent else int(campaign.state.get("iterations_since_divergent", 0)) + 1
    )
    campaign.state["pending_iteration"] = 0
    campaign.state["pending_divergent"] = False
    campaign.state["pending_base_sha"] = None
    campaign.state["pending_protocol_digest"] = None
    campaign.state["pending_baseline_run_digest"] = None
    campaign.state["pending_regression_baseline_run_digest"] = None
    campaign.state["pending_baseline_admission_receipt"] = None
    campaign.state["pending_regression_baseline_admission_receipt"] = None
    campaign.save_state()

    # Reset the boundary: discard the (accepted-or-rejected) worktree; the next
    # `start` re-creates it at the new accepted base. Rejected candidate commits
    # are unreferenced and GC-eligible; accepted ones are held by ACCEPTED_REF.
    gitutil.worktree_remove(campaign.repo_root, worktree)

    return {
        "iteration": number, "verdict": verdict.label, "decision": verdict.decision,
        "evidence_class": verdict.evidence_class,
        "advanced_accepted_state": verdict.advances_accepted_state,
        "promotion_candidates": promotion_candidates,
        "accepted_base_sha": campaign.state["accepted_base_sha"],
    }


def _reject_pivot(
    campaign,
    number,
    fingerprint,
    prior,
    iteration_dir,
    base_sha,
    manifest,
) -> dict[str, Any]:
    verdict = Verdict("rejected", "simulated")
    report = {
        "iteration": number, "verdict": verdict.to_dict(),
        "rungs": [{"rung": "E0", "status": "fail", "detail": {
            "pivot_rule": f"{prior} prior failed attempts at {fingerprint}; a component-level pivot is required (F16)"}}],
        "attribution": None, "comparison": None, "eligibility": None,
        "run_digests": {},
    }
    atomic_write_json(iteration_dir / "gate-report.json", report)
    _write_trusted_manifest_snapshot(iteration_dir, manifest, verdict)
    append_jsonl(campaign.ledger_path, {
        "iteration": number, "campaign": campaign.campaign_id, "verdict": verdict.label,
        "decision": "rejected", "evidence_class": "simulated", "advances_accepted_state": False,
        "cluster_ref": fingerprint, "reason": "pivot required",
    })
    _append_learnings(
        campaign,
        number,
        verdict,
        manifest,
        bool(campaign.state.get("pending_divergent", False)),
    )
    campaign.state["iterations_since_accept"] = int(campaign.state.get("iterations_since_accept", 0)) + 1
    campaign.state["pending_iteration"] = 0
    campaign.state["pending_divergent"] = False
    campaign.state["pending_base_sha"] = None
    campaign.state["pending_protocol_digest"] = None
    campaign.state["pending_baseline_run_digest"] = None
    campaign.state["pending_regression_baseline_run_digest"] = None
    campaign.state["pending_baseline_admission_receipt"] = None
    campaign.state["pending_regression_baseline_admission_receipt"] = None
    campaign.save_state()
    gitutil.worktree_remove(campaign.repo_root, campaign.worktree_path)
    return {"iteration": number, "verdict": verdict.label, "decision": "rejected",
            "advanced_accepted_state": False, "reason": "pivot required", "fingerprint": fingerprint}


def _append_learnings(campaign, number, verdict: Verdict, manifest, divergent) -> None:
    with campaign.learnings_path.open("a", encoding="utf-8") as handle:
        handle.write(learnings_template(
            iteration=number, verdict=verdict.label,
            hypothesis=manifest.get("hypothesis", "<no manifest>"),
            target_component=manifest.get("target_component", "?"),
            cluster_ref=manifest.get("cluster_ref", "?"), divergent=divergent,
        ))


# ── noise calibration (owner artifact, identity-bound) ─────────────────────
def measure_noise(campaign: Campaign, *, runs: int = 3) -> NoiseBand:
    base_sha = str(campaign.state["accepted_base_sha"])
    worktree = campaign.worktree_path
    gitutil.worktree_add(campaign.repo_root, worktree, base_sha)
    try:
        protocol = build_protocol_snapshot(
            campaign,
            worktree,
            iteration=0,
            purpose="noise-calibration",
            repeat_count=runs,
        )
        noise_root = campaign.store.campaign_dir / "noise"
        freeze_protocol(noise_root, protocol)
        execution = protocol["execution"]
        seed = int(protocol["repeated_protocol"]["matched_blocks"]["seeds"][0])
        eval_runs: list[EvalRun] = []
        for index in range(runs):
            calibration_context = run_context(
                protocol,
                protocol["accepted_build"],
                arm="baseline",
                suite_role="dev",
                task_ids=_protocol_task_ids(protocol, "dev"),
                repeat_index=index,
                seed=seed,
            )
            verify_runtime_bindings(
                protocol, admissions_path=campaign.store.admissions_path
            )
            sample = run_suite(
                repo_root=worktree,
                suite_name=execution["suites"]["dev"],
                adapter_config=execution["adapter"],
                output_dir=noise_root / f"run-{index:02d}",
                protocol_snapshot=protocol,
                run_context=calibration_context,
            )
            _assess_exact_run(
                campaign,
                sample,
                expected_live_run_receipt(
                    protocol, run_digest=calibration_context["run_digest"]
                ),
                label=f"noise sample {index}",
            )
            eval_runs.append(sample)
        synthetic = protocol["evidence_mode"] != "benchmark"
        band = measure_noise_band(
            eval_runs,
            synthetic=synthetic,
            run_identity=protocol["calibration_binding_digest"],
            evidence_root=campaign.store.campaign_dir,
        )
    finally:
        gitutil.worktree_remove(campaign.repo_root, worktree)
    campaign.config["noise_band"] = band.to_dict()
    campaign.save_config()
    atomic_write_json(campaign.store.noise_band_path, band.to_dict())
    return band


# ── cross-campaign report (scheduled, never a per-iteration race) ──────────
def compare_campaigns(repo_root: Path, campaign_ids: list[str], *, store_root=None) -> dict[str, Any]:
    from .campaign import load_campaign

    rows: list[dict[str, Any]] = []
    identities: set[str] = set()
    missing_identities: list[str] = []
    for campaign_id in campaign_ids:
        campaign = load_campaign(repo_root, campaign_id, store_root=store_root)
        accepted_run = _load_accepted_run(campaign)
        protocol = accepted_run.protocol_snapshot if accepted_run is not None else {}
        identity = (
            str(protocol.get("comparison_apparatus_digest", ""))
            if accepted_run is not None
            else ""
        )
        executor = str(protocol.get("executor", {}).get("model", ""))
        suite = str(protocol.get("execution", {}).get("suites", {}).get("dev", ""))
        if identity:
            identities.add(identity)
        else:
            missing_identities.append(campaign_id)
        rows.append({
            "campaign": campaign_id, "suite": suite, "executor": executor,
            "identity": identity, "iterations": campaign.current_iteration,
            "accepted_iterations": campaign.state.get("accepted_iterations", []),
            "strict_success_rate": (
                accepted_run.summary.get("strict_success_rate")
                if accepted_run is not None else None
            ),
        })
    comparable = bool(rows) and not missing_identities and len(identities) == 1
    report = {
        "schema_version": "0.2-draft", "comparable": comparable,
        "non_comparable_reason": (
            None
            if comparable
            else (
                "campaigns are missing accepted trusted apparatus identities: "
                + ", ".join(missing_identities)
                if missing_identities
                else "campaigns differ in frozen comparison-apparatus identity; "
                "cross-campaign scores must not be ranked (ADR-0001, F15)"
            )
        ),
        "campaigns": rows,
        "note": "transplanting a winning mechanism is a manifested change through the receiving campaign's gate",
    }
    return report
