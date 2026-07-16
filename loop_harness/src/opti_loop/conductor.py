"""The Conductor: transactional phase driver over a trusted boundary.

Rewritten after the review. The iteration boundary is now owner-controlled:

- ``start`` captures the trusted ``accepted_base_sha``, creates an isolated
  candidate **worktree** at that base (the optimizer's only writable surface),
  runs the baseline + regression baseline there, distills, and writes the
  packet — all into the owner-only trusted store.
- simulated rehearsal edits use the isolated worktree; benchmark handback is
  an independently owned static bundle plus manifest sidecar.
- ``run_iteration`` is a SINGLE atomic transaction (F02, F06): it ingests and
  validates one manifest snapshot, derives the E0 diff from the sealed D2
  candidate against the trusted base, runs E0–E5, and writes the trusted
  attribution, gate report, and ledger row to the
  trusted store, advances accepted state ONLY on ``(accepted, benchmark)``, and
  resets the worktree either way. There is no separate, forgeable record step.

Regression memory is seeded from the accepted-base run at ``start`` and is
never refreshed from a rejected treatment (F06).
"""
from __future__ import annotations

import copy
import json
import os
import shutil
import stat
import sys
import time
from contextlib import ExitStack
from pathlib import Path
from typing import Any

from opti_eval.catalog import load_catalog
from opti_eval.identity import LiveRunReceipt, digest_json, expected_live_run_receipt
from opti_eval.models import strict_json_loads

from . import fileguard, gitutil
from .analyst import StubAnalyst
from .campaign import Campaign, load_campaign
from .clusters import load_register, ranked_unresolved, save_register, update_after_iteration
from .compare import NoiseBand, NoiseBandError, measure_noise_band
from .eligibility import Eligibility, assess
from .evaluate import EvalRun, load_run, run_suite
from .gates import GateReport, RungResult, run_gate
from .learning import build_record, ensure_record, read_records, validate_record
from .ledger import LEDGER_ROW_FIELDS, read_rows
from .manifest import ManifestReport, rejected_submission_record, validate_manifest
from .materialization import (
    MAX_BUNDLE_BYTES,
    CampaignLock,
    MaterializationError,
    consume_materialization,
    materialize_candidate_bundle,
    project_build_identity,
)
from .operation import LIFECYCLE_VERSION, note_attempt, require_transition
from .packet import build_packet
from .protocol import (
    ProtocolError,
    build_protocol_snapshot,
    freeze_protocol,
    load_frozen_protocol,
    run_context,
    verify_runtime_bindings,
)
from .store import atomic_write_json, atomic_write_text
from .transfer import evaluate_checkpoint
from .verdict import Verdict

DEV_BASELINE_DIR = "eval/dev_baseline"
ACCEPTED_REF = "refs/opti/{campaign}/accepted"
MAX_MANIFEST_BYTES = 256 * 1024
PUBLICATION_RECORD = "accepted-publication.json"
PUBLICATION_SCHEMA_VERSION = "0.4.0"
PUBLICATION_RECORD_TYPE = "accepted-publication"
PUBLICATION_DIGEST_DOMAIN = "opti.accepted-publication.v3"
MANIFEST_SNAPSHOT_DIGEST_DOMAIN = "opti.publication-manifest-snapshot.v1"
PUBLICATION_RESULT_FIELDS = {
    "iteration",
    "verdict",
    "decision",
    "evidence_class",
    "advanced_accepted_state",
    "promotion_candidates",
    "accepted_base_sha",
}
PUBLICATION_IDENTITY_FIELDS = {
    "schema_version",
    "record_type",
    "status",
    "campaign_id",
    "iteration",
    "protocol_digest",
    "base_sha",
    "candidate_sha",
    "candidate_tree",
    "staging_ref",
    "expected_ref",
    "manifest_snapshot_digest",
}
PENDING_PUBLICATION_FIELDS = PUBLICATION_IDENTITY_FIELDS | {
    "gate_report",
    "manifest_snapshot",
    "cluster_register",
    "ledger_row",
    "learning_record",
    "pre_state",
    "final_state",
    "result",
    "record_digest",
}
TERMINAL_PUBLICATION_FIELDS = PUBLICATION_IDENTITY_FIELDS | {
    "intent_digest",
    "result_summary",
    "record_digest",
}
FAILED_PUBLICATION_FIELDS = TERMINAL_PUBLICATION_FIELDS | {"error"}
GATE_REPORT_FIELDS = {
    "iteration",
    "verdict",
    "rungs",
    "attribution",
    "comparison",
    "eligibility",
    "admissions",
    "run_digests",
}
class _AcceptedRefContention(gitutil.GitError):
    """The accepted ref changed before this publication could own it."""


def _frozen_transfer_status(
    campaign: Campaign, protocol: dict[str, Any]
) -> str:
    """Map one protocol-bound checkpoint result onto the existing E5 seam."""
    config = protocol["execution"]["transfer"]
    checkpoint_every = int(config.get("checkpoint_every", 0))
    prospective_accept = len(campaign.state.get("accepted_iterations", [])) + 1
    if checkpoint_every <= 0 or prospective_accept % checkpoint_every:
        return "not_due"
    result = config.get("checkpoint_result")
    fields = {
        "campaign_id",
        "accepted_sha",
        "accepted_iterations",
        "deltas_by_model",
        "evidence_digest",
    }
    if type(result) is not dict or set(result) != fields:
        return "missing"
    if (
        result["campaign_id"] != campaign.campaign_id
        or result["accepted_sha"] != protocol["accepted_build"]["commit_sha"]
        or result["accepted_iterations"]
        != campaign.state.get("accepted_iterations", [])
    ):
        return "missing"
    deltas = result["deltas_by_model"]
    if (
        type(deltas) is not dict
        or not deltas
        or any(
            type(model) is not str
            or not model
            or type(delta) not in {int, float}
            for model, delta in deltas.items()
        )
    ):
        return "missing"
    unsigned = {key: value for key, value in result.items() if key != "evidence_digest"}
    try:
        expected_digest = digest_json(
            unsigned, domain="opti.transfer-checkpoint-evidence.v1"
        )
    except (TypeError, ValueError):
        return "missing"
    if result["evidence_digest"] != expected_digest:
        return "missing"
    decision = evaluate_checkpoint(deltas).get("decision")
    return {
        "transfer_supported": "supported",
        "REJECT_TRANSFER_BET": "regressed",
    }.get(decision, "missing")


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
    snapshot = _trusted_manifest_snapshot(
        manifest,
        verdict,
        attribution,
        original_submission=original_submission,
        validation_errors=validation_errors,
    )
    atomic_write_json(iteration_dir / "manifest.snapshot.json", snapshot)


def _trusted_manifest_snapshot(
    manifest: dict[str, Any],
    verdict: Verdict,
    attribution: dict[str, Any] | None = None,
    *,
    original_submission: object = None,
    validation_errors: list[str] | None = None,
) -> dict[str, Any]:
    """Build the exact canonical snapshot used by direct and recovered writes."""
    if validation_errors:
        return rejected_submission_record(
            original_submission=original_submission,
            validation_errors=validation_errors,
            verdict=verdict.to_dict(),
        )
    snapshot = {key: value for key, value in manifest.items() if key != "attribution"}
    if attribution is not None:
        snapshot["attribution"] = attribution
    snapshot["status"] = verdict.label
    return snapshot


# ── phase A + C: start ──────────────────────────────────────────────────
def start_iteration(campaign: Campaign) -> dict[str, Any]:
    materialization_store = campaign.store.campaign_dir / "materializations"
    materialization_store.mkdir(mode=0o700, exist_ok=True)
    materialization_store.chmod(0o700)
    with CampaignLock(materialization_store) as lock:
        fresh = load_campaign(
            campaign.repo_root,
            campaign.campaign_id,
            store_root=campaign.store.root,
        )
        campaign.state = fresh.state
        publication = _project_publication(campaign)[1]
        if publication is not None:
            publication_iteration = publication["iteration"]
            if publication["status"] == "pending":
                raise RuntimeError(
                    "accepted publication recovery is pending; run `opti-loop "
                    "run-iteration` before starting another iteration"
                )
            if publication_iteration > campaign.current_iteration:
                raise RuntimeError(
                    "accepted publication receipt is ahead of campaign state"
                )
            if publication_iteration == campaign.current_iteration:
                _cleanup_terminal_publication(campaign, publication, lock=lock)
        return _start_iteration_locked(campaign, lock=lock)


def _start_iteration_locked(
    campaign: Campaign, *, lock: CampaignLock
) -> dict[str, Any]:
    materialization_store = campaign.store.campaign_dir / "materializations"
    lock.require_held(materialization_store)
    _project_publication(campaign)
    require_transition(campaign, action="start")
    if campaign.state.get("pending_iteration"):
        raise RuntimeError(
            f"iteration {campaign.state['pending_iteration']} is already pending; "
            "run `opti-loop run-iteration` first"
        )
    learning_records = read_records(
        campaign.learnings_path, campaign_root=campaign.store.campaign_dir
    )
    if campaign.current_iteration:
        matches = [
            row for row in learning_records
            if row["iteration"] == campaign.current_iteration
        ]
        if len(matches) != 1:
            raise RuntimeError(
                "latest completed iteration lacks one valid trace-cited LearningRecord"
            )
        latest_learning = matches[0]
    else:
        latest_learning = None
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
    clusters_existed_before = campaign.clusters_path.is_file()
    clusters_before = (
        campaign.clusters_path.read_text(encoding="utf-8")
        if clusters_existed_before
        else None
    )
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

        # Drift vs the previous accepted treatment.
        drift = None
        if previous_accepted is not None:
            changed = sorted(
                task_id
                for task_id in baseline.statuses
                if baseline.statuses.get(task_id)
                != previous_accepted.statuses.get(task_id)
            )
            drift = {"tasks_changed_since_accepted_treatment": changed}
            atomic_write_json(iteration_dir / "drift.json", drift)

        # C — DISTILL (stub analyst until traces exist).
        analyst = StubAnalyst()
        analysis = analyst.distill(
            iteration=number,
            run=baseline,
            task_sources=sources,
            out_dir=iteration_dir / "analysis",
        )
        register = load_register(campaign.clusters_path)
        register = update_after_iteration(
            register,
            iteration=number,
            failed_by_cluster=analysis["failed_by_cluster"],
            fixed_task_ids=set(),
            analyst_version=analyst.version,
        )

        # Exploration decision (ADR-0015 §9).
        quota = int(execution["exploration"].get("divergence_quota", 5))
        force_after = int(execution["exploration"].get("plateau_force_after", 4))
        since_div = int(campaign.state.get("iterations_since_divergent", 0))
        since_acc = int(campaign.state.get("iterations_since_accept", 0))
        divergent = (quota > 0 and since_div + 1 >= quota) or (
            force_after > 0 and since_acc >= force_after
        )

        build_packet(
            iteration_dir=iteration_dir,
            iteration=number,
            campaign_id=campaign.campaign_id,
            divergent=divergent,
            ranked_clusters=ranked_unresolved(register),
            ledger_path=campaign.ledger_path,
            baseline_summary=baseline.summary,
            candidate_allowlist=protocol["candidate_allowlist"],
            latest_learning_record=latest_learning,
        )
        save_register(campaign.clusters_path, register)

        campaign.state["current_iteration"] = number
        campaign.state["pending_iteration"] = number
        campaign.state["pending_divergent"] = divergent
        campaign.state["pending_base_sha"] = base_sha
        campaign.state["pending_protocol_digest"] = protocol["protocol_digest"]
        campaign.state["pending_baseline_run_digest"] = baseline_context["run_digest"]
        campaign.state["pending_regression_baseline_run_digest"] = regression_context[
            "run_digest"
        ]
        campaign.state["pending_baseline_admission_receipt"] = baseline_admission
        campaign.state["pending_baseline_activation_observation"] = (
            baseline.activation_observation
        )
        campaign.state[
            "pending_regression_baseline_admission_receipt"
        ] = regression_admission
        campaign.state["lifecycle"] = {
            "schema_version": LIFECYCLE_VERSION,
            "state": "running",
            "request": "run",
        }
        campaign.save_state()
    except BaseException:
        campaign.state = state_before
        campaign.save_state()
        try:
            if clusters_before is not None:
                atomic_write_text(campaign.clusters_path, clusters_before)
            elif not clusters_existed_before:
                campaign.clusters_path.unlink(missing_ok=True)
            if iteration_dir.exists() and not iteration_dir.is_symlink():
                shutil.rmtree(iteration_dir)
            if worktree_created:
                gitutil.worktree_remove(campaign.repo_root, worktree)
                if worktree.exists() or worktree.is_symlink():
                    raise RuntimeError(
                        "start preparation worktree cleanup did not complete"
                    )
        except BaseException as cleanup_exc:
            campaign.state["cleanup_health"] = {
                "status": "failed",
                "detail": f"start preparation cleanup failed: {cleanup_exc}",
            }
            campaign.save_state()
            raise
        raise

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
    return result


# ── phase E + B + F: one atomic transaction ───────────────────────────────
def _validate_benchmark_handback_ownership(
    *, bundle_info: os.stat_result, manifest_info: os.stat_result,
    parent_info: os.stat_result,
) -> int:
    """Validate the already-opened bundle, sidecar, and inbox descriptors."""
    if (
        not stat.S_ISREG(bundle_info.st_mode)
        or not stat.S_ISREG(manifest_info.st_mode)
        or not stat.S_ISDIR(parent_info.st_mode)
        or bundle_info.st_uid == os.getuid()
        or manifest_info.st_uid != bundle_info.st_uid
        or parent_info.st_uid != bundle_info.st_uid
    ):
        raise MaterializationError(
            "benchmark optimizer bundle, manifest, and inbox must be real paths "
            "owned by one separate optimizer UID"
        )
    return bundle_info.st_uid


def _copy_benchmark_bundle(
    source_fd: int, destination: Path, *, optimizer_uid: int
) -> Path:
    """Copy the pinned optimizer bundle descriptor into the trusted record."""
    destination_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    destination_flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    info = os.fstat(source_fd)
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != optimizer_uid
        or info.st_size <= 0
        or info.st_size > MAX_BUNDLE_BYTES
    ):
        raise MaterializationError(
            "benchmark optimizer bundle changed after ownership validation"
        )
    try:
        destination_fd = os.open(destination, destination_flags, 0o600)
    except OSError as exc:
        raise MaterializationError(
            "trusted benchmark handback copy cannot be created"
        ) from exc
    try:
        os.lseek(source_fd, 0, os.SEEK_SET)
        remaining = info.st_size
        while remaining:
            chunk = os.read(source_fd, min(64 * 1024, remaining))
            if not chunk:
                raise MaterializationError(
                    "benchmark optimizer bundle became shorter during snapshot"
                )
            view = memoryview(chunk)
            while view:
                written = os.write(destination_fd, view)
                if written <= 0:
                    raise OSError("trusted bundle write made no progress")
                view = view[written:]
            remaining -= len(chunk)
        after = os.fstat(source_fd)
        if (
            after.st_size != info.st_size
            or after.st_uid != info.st_uid
            or after.st_mtime_ns != info.st_mtime_ns
            or after.st_ctime_ns != info.st_ctime_ns
        ):
            raise MaterializationError(
                "benchmark optimizer bundle changed during bounded snapshot"
            )
        os.fsync(destination_fd)
    except MaterializationError:
        destination.unlink(missing_ok=True)
        raise
    except OSError as exc:
        destination.unlink(missing_ok=True)
        raise MaterializationError(
            "trusted benchmark handback copy failed"
        ) from exc
    finally:
        os.close(destination_fd)
    return destination


def _open_directory_nofollow(path: Path) -> int:
    """Open one absolute directory chain without following any component."""
    absolute = Path(os.path.abspath(path))
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open("/", flags)
    try:
        for part in absolute.parts[1:]:
            next_descriptor = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
    except OSError as exc:
        os.close(descriptor)
        raise MaterializationError(
            "benchmark optimizer inbox cannot be opened without symlinks"
        ) from exc
    return descriptor


def _open_manifest_nofollow(
    path: Path, resources: ExitStack
) -> tuple[int, int, os.stat_result]:
    parent_fd = _open_directory_nofollow(path.parent)
    resources.callback(os.close, parent_fd)
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path.name, flags, dir_fd=parent_fd)
    except OSError as exc:
        raise MaterializationError(
            "benchmark candidate manifest sidecar cannot be opened without symlinks"
        ) from exc
    resources.callback(os.close, descriptor)
    info = os.fstat(descriptor)
    if not stat.S_ISREG(info.st_mode):
        raise MaterializationError(
            "benchmark candidate manifest sidecar must be a regular file"
        )
    return descriptor, parent_fd, os.fstat(parent_fd)


def _open_benchmark_bundle(
    bundle: Path, manifest: Path, parent_fd: int, resources: ExitStack
) -> tuple[int, os.stat_result]:
    """Pin the bundle and its inbox immediately before E1 ownership checks."""
    if bundle.parent != manifest.parent:
        raise MaterializationError("benchmark bundle and manifest must share one inbox")
    bundle_flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    bundle_flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        bundle_fd = os.open(bundle.name, bundle_flags, dir_fd=parent_fd)
    except OSError as exc:
        raise MaterializationError(
            "benchmark optimizer bundle cannot be opened without symlinks"
        ) from exc
    resources.callback(os.close, bundle_fd)
    bundle_info = os.fstat(bundle_fd)
    if not stat.S_ISREG(bundle_info.st_mode):
        raise MaterializationError("benchmark optimizer bundle must be a regular file")
    return bundle_fd, bundle_info


def _optimizer_bundle(
    campaign: Campaign,
    *,
    supplied_bundle: Path | None,
    supplied_manifest: Path | None,
    evidence_mode: str,
) -> tuple[Path | None, Path | None]:
    """Resolve one bundle/manifest handback without reading either file."""
    if evidence_mode != "benchmark":
        if supplied_bundle is None and supplied_manifest is None:
            return None, campaign.worktree_path / "manifest.json"
    return (
        Path(supplied_bundle) if supplied_bundle is not None else None,
        Path(supplied_manifest) if supplied_manifest is not None else None,
    )


def _benchmark_handback_required(protocol: dict[str, Any]) -> bool:
    return protocol["evidence_mode"] == "benchmark"


def _read_manifest_snapshot(
    path: Path | None,
    *,
    pinned_descriptor: int | None = None,
) -> tuple[object, ManifestReport]:
    """Read and parse the exact manifest bytes once."""
    if path is None:
        return None, ManifestReport(
            manifest=None,
            errors=["candidate manifest sidecar was not supplied"],
        )
    owned_descriptor = False
    descriptor = pinned_descriptor
    if descriptor is None:
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(path, flags)
            owned_descriptor = True
        except OSError:
            return None, ManifestReport(manifest=None, errors=[f"manifest not found: {path}"])
    assert descriptor is not None
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            return None, ManifestReport(
                manifest=None, errors=["candidate manifest must be a regular file"]
            )
        if before.st_size > MAX_MANIFEST_BYTES:
            return None, ManifestReport(
                manifest=None,
                errors=[
                    f"candidate manifest exceeds {MAX_MANIFEST_BYTES} byte limit"
                ],
            )
        try:
            os.lseek(descriptor, 0, os.SEEK_SET)
            remaining = before.st_size
            chunks: list[bytes] = []
            while remaining:
                chunk = os.read(descriptor, min(64 * 1024, remaining))
                if not chunk:
                    return None, ManifestReport(
                        manifest=None,
                        errors=["candidate manifest became shorter during snapshot"],
                    )
                chunks.append(chunk)
                remaining -= len(chunk)
            raw = b"".join(chunks)
            after = os.fstat(descriptor)
            if (
                after.st_size != before.st_size
                or after.st_uid != before.st_uid
                or after.st_mtime_ns != before.st_mtime_ns
                or after.st_ctime_ns != before.st_ctime_ns
            ):
                return None, ManifestReport(
                    manifest=None,
                    errors=["candidate manifest changed during bounded snapshot"],
                )
        except OSError:
            return None, ManifestReport(
                manifest=None, errors=[f"manifest cannot be read: {path}"]
            )
    finally:
        if owned_descriptor:
            os.close(descriptor)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return raw.hex(), ManifestReport(
            manifest=None, errors=[f"manifest is not UTF-8: {exc}"]
        )
    try:
        submitted = strict_json_loads(text, field_name="candidate manifest")
    except ValueError as exc:
        return text, ManifestReport(
            manifest=None, errors=[f"manifest is not strict JSON: {exc}"]
        )
    return submitted, ManifestReport(
        manifest=submitted if isinstance(submitted, dict) else None
    )


def _stage_accepted_candidate(
    campaign: Campaign,
    report: GateReport,
    *,
    trusted_bundle: Path | None,
    receipt: dict[str, Any] | None,
    treatment_build: dict[str, Any] | None,
    expected_ref: str | None,
) -> tuple[str, str | None] | None:
    """Import the exact D2 candidate before any advancing terminal artifacts."""
    if not report.verdict.advances_accepted_state:
        return None
    if (
        report.verdict.evidence_class != "benchmark"
        or trusted_bundle is None
        or receipt is None
        or treatment_build is None
        or receipt.get("commit_sha") != treatment_build.get("commit_sha")
        or receipt.get("tree_sha") != treatment_build.get("tree_sha")
    ):
        raise MaterializationError(
            "advancing benchmark verdict lacks its exact D2 handback identity"
        )
    candidate_sha = treatment_build["commit_sha"]
    staging_ref = f"refs/opti/import/{candidate_sha}"
    gitutil.stage_bundle_candidate(
        campaign.repo_root,
        trusted_bundle,
        candidate_sha=candidate_sha,
        tree_sha=treatment_build["tree_sha"],
        staging_ref=staging_ref,
    )
    accepted_ref = ACCEPTED_REF.format(campaign=campaign.campaign_id)
    if gitutil.try_rev_parse(campaign.repo_root, accepted_ref) != expected_ref:
        gitutil.delete_ref(
            campaign.repo_root, staging_ref, expected=candidate_sha
        )
        raise gitutil.GitError("accepted ref changed before candidate publication")
    return staging_ref, expected_ref


def _delete_staged_candidate(
    campaign: Campaign, staging_ref: str, candidate_sha: str
) -> None:
    current = gitutil.try_rev_parse(campaign.repo_root, staging_ref)
    if current == candidate_sha:
        gitutil.delete_ref(campaign.repo_root, staging_ref, expected=candidate_sha)
    elif current is not None:
        raise RuntimeError("candidate staging ref changed before cleanup")


def _publication_checkpoint(_boundary: str) -> None:
    """Named failure-injection seam for the bounded accepted transaction."""


def _publication_path(campaign: Campaign) -> Path:
    return campaign.store.campaign_dir / PUBLICATION_RECORD


def _is_sha256(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _is_git_oid(value: object) -> bool:
    return (
        type(value) is str
        and len(value) in {40, 64}
        and all(character in "0123456789abcdef" for character in value)
    )


def _require_closed_object(
    value: object, fields: set[str], *, field_name: str
) -> dict[str, Any]:
    if type(value) is not dict or set(value) != fields:
        raise RuntimeError(f"{field_name} has an invalid closed shape")
    return value


def _publication_record_digest(record: dict[str, Any]) -> str:
    return digest_json(
        {key: value for key, value in record.items() if key != "record_digest"},
        domain=PUBLICATION_DIGEST_DOMAIN,
    )


def _seal_publication_record(record: dict[str, Any]) -> dict[str, Any]:
    sealed = copy.deepcopy(record)
    sealed["record_digest"] = _publication_record_digest(sealed)
    return sealed


def _manifest_snapshot_digest(snapshot: object) -> str:
    return digest_json(snapshot, domain=MANIFEST_SNAPSHOT_DIGEST_DOMAIN)


def _has_accepted_history(state: dict[str, Any]) -> bool:
    accepted = state.get("accepted_iterations")
    if type(accepted) is not list or any(type(item) is not int for item in accepted):
        raise RuntimeError("campaign accepted-iteration history is malformed")
    return bool(
        accepted
        or state.get("last_accepted_treatment_dir")
        or state.get("last_accepted_admission_receipt")
    )


def _expected_accepted_ref(campaign: Campaign, state: dict[str, Any]) -> str | None:
    base_sha = state.get("accepted_base_sha")
    if not _is_git_oid(base_sha):
        raise RuntimeError("campaign accepted base identity is malformed")
    accepted_ref = ACCEPTED_REF.format(campaign=campaign.campaign_id)
    current_ref = gitutil.try_rev_parse(campaign.repo_root, accepted_ref)
    if _has_accepted_history(state):
        if current_ref is None:
            raise RuntimeError("established accepted Git ref is missing")
        if current_ref != base_sha:
            raise RuntimeError(
                "established accepted Git ref does not match accepted campaign state"
            )
        return str(base_sha)
    if current_ref is not None and current_ref != base_sha:
        raise RuntimeError(
            "accepted Git ref does not match the never-published campaign base"
        )
    return current_ref


def _validate_publication_identity(
    campaign: Campaign, record: dict[str, Any]
) -> None:
    if (
        record.get("schema_version") != PUBLICATION_SCHEMA_VERSION
        or record.get("record_type") != PUBLICATION_RECORD_TYPE
        or record.get("campaign_id") != campaign.campaign_id
    ):
        raise RuntimeError("accepted publication record identity is invalid")
    if type(record.get("iteration")) is not int or record["iteration"] < 1:
        raise RuntimeError("accepted publication iteration is invalid")
    if not _is_sha256(record.get("protocol_digest")):
        raise RuntimeError("accepted publication protocol digest is invalid")
    if not _is_git_oid(record.get("base_sha")):
        raise RuntimeError("accepted publication base_sha is invalid")
    candidate_sha = record.get("candidate_sha")
    candidate_tree = record.get("candidate_tree")
    staging_ref = record.get("staging_ref")
    if candidate_sha is not None and not _is_git_oid(candidate_sha):
        raise RuntimeError("accepted publication candidate_sha is invalid")
    if candidate_tree is not None and not _is_git_oid(candidate_tree):
        raise RuntimeError("accepted publication candidate_tree is invalid")
    if (candidate_sha is None) is not (candidate_tree is None):
        raise RuntimeError("accepted publication candidate identity is incomplete")
    if staging_ref is not None and (
        candidate_sha is None
        or staging_ref != f"refs/opti/import/{candidate_sha}"
    ):
        raise RuntimeError("accepted publication staging identity is invalid")
    expected_ref = record.get("expected_ref")
    if expected_ref is not None and not _is_git_oid(expected_ref):
        raise RuntimeError("accepted publication expected ref is invalid")
    if not _is_sha256(record.get("manifest_snapshot_digest")):
        raise RuntimeError("accepted publication manifest snapshot digest is invalid")
    if not _is_sha256(record.get("record_digest")) or record[
        "record_digest"
    ] != _publication_record_digest(record):
        raise RuntimeError("accepted publication record digest is invalid")


def _validate_result_summary(
    result: object,
    *,
    record: dict[str, Any],
) -> dict[str, Any]:
    summary = _require_closed_object(
        result, PUBLICATION_RESULT_FIELDS, field_name="publication result summary"
    )
    try:
        verdict = Verdict(
            str(summary.get("decision")), str(summary.get("evidence_class"))
        )
    except ValueError as exc:
        raise RuntimeError("publication result summary verdict is invalid") from exc
    expected = {
        "iteration": record["iteration"],
        "verdict": verdict.label,
        "advanced_accepted_state": verdict.advances_accepted_state,
        "accepted_base_sha": (
            record["candidate_sha"]
            if verdict.advances_accepted_state
            else record["base_sha"]
        ),
    }
    for field, value in expected.items():
        if summary.get(field) != value:
            raise RuntimeError(
                f"publication result summary has inconsistent {field}"
            )
    promotions = summary.get("promotion_candidates")
    if (
        type(promotions) is not list
        or any(type(item) is not str for item in promotions)
        or promotions != sorted(set(promotions))
        or not verdict.advances_accepted_state and promotions
    ):
        raise RuntimeError("publication result summary has invalid promotions")
    if verdict.advances_accepted_state and not _is_git_oid(record.get("candidate_sha")):
        raise RuntimeError("accepted publication result lacks candidate identity")
    return summary


def _accepted_final_state(
    campaign: Campaign,
    pre_state: dict[str, Any],
    *,
    iteration: int,
    candidate_sha: str,
    admission: dict[str, Any],
    divergent: bool,
    fingerprint: str,
    comparison: dict[str, Any],
) -> dict[str, Any]:
    """Derive the only state transition an accepted intent may publish."""
    accepted_iterations = pre_state.get("accepted_iterations")
    failed_attempts = pre_state.get("failed_attempts")
    iterations_since_divergent = pre_state.get("iterations_since_divergent")
    if (
        type(accepted_iterations) is not list
        or any(type(item) is not int for item in accepted_iterations)
        or type(failed_attempts) is not dict
        or type(iterations_since_divergent) is not int
        or type(divergent) is not bool
    ):
        raise RuntimeError("publication pre-state counters are malformed")

    final_state = copy.deepcopy(pre_state)
    final_state["accepted_base_sha"] = candidate_sha
    final_state["accepted_iterations"].append(iteration)
    final_state["iterations_since_accept"] = 0
    final_state["last_accepted_treatment_dir"] = str(
        campaign.iteration_dir(iteration) / "eval" / "dev_treatment"
    )
    final_state["last_accepted_admission_receipt"] = copy.deepcopy(admission)
    prior_protection = pre_state.get(
        "accepted_protection",
        {
            "champion_sha": pre_state["accepted_base_sha"],
            "protected_tasks": [],
            "success_rates": {},
        },
    )
    candidate_rates = comparison.get("candidate_success_rates")
    candidate_protected = comparison.get("candidate_protected_tasks")
    if (
        type(prior_protection) is not dict
        or type(candidate_rates) is not dict
        or type(candidate_protected) is not list
        or any(type(task_id) is not str for task_id in candidate_protected)
    ):
        raise RuntimeError("accepted publication protection evidence is malformed")
    durable_rates = copy.deepcopy(prior_protection.get("success_rates"))
    protected_tasks = set(prior_protection.get("protected_tasks", []))
    if type(durable_rates) is not dict:
        raise RuntimeError("accepted publication durable success rates are malformed")
    for task_id in candidate_protected:
        rate = candidate_rates.get(task_id)
        if type(rate) not in {int, float} or not 0 <= rate <= 1:
            raise RuntimeError("accepted publication candidate success rate is malformed")
        protected_tasks.add(task_id)
        durable_rates[task_id] = max(float(durable_rates.get(task_id, 0.0)), float(rate))
    final_state["accepted_protection"] = {
        "champion_sha": candidate_sha,
        "protected_tasks": sorted(protected_tasks),
        "success_rates": {
            task_id: durable_rates[task_id] for task_id in sorted(protected_tasks)
        },
    }
    final_state["failed_attempts"].pop(fingerprint, None)
    final_state["iterations_since_divergent"] = (
        0 if divergent else iterations_since_divergent + 1
    )
    for key, value in (
        ("pending_iteration", 0),
        ("pending_divergent", False),
        ("pending_base_sha", None),
        ("pending_protocol_digest", None),
        ("pending_baseline_run_digest", None),
        ("pending_regression_baseline_run_digest", None),
        ("pending_baseline_admission_receipt", None),
        ("pending_baseline_activation_observation", None),
        ("pending_regression_baseline_admission_receipt", None),
        ("pending_repeated_started_at", None),
        ("active_attempt_iteration", None),
    ):
        final_state[key] = value
    return final_state


def _nonadvancing_final_state(
    pre_state: dict[str, Any],
    *,
    verdict: Verdict,
    divergent: bool,
    fingerprint: str | None,
    cleanup_failure: str | None,
) -> dict[str, Any]:
    """Derive the state-inert terminal transition for every non-accept."""
    final_state = copy.deepcopy(pre_state)
    benchmark_rejection = (
        verdict.decision == "rejected" and verdict.evidence_class == "benchmark"
    )
    if benchmark_rejection:
        final_state["iterations_since_accept"] = int(
            final_state.get("iterations_since_accept", 0)
        ) + 1
        if fingerprint:
            failed = final_state.setdefault("failed_attempts", {})
            failed[fingerprint] = int(failed.get(fingerprint, 0)) + 1
        final_state["iterations_since_divergent"] = (
            0
            if divergent
            else int(final_state.get("iterations_since_divergent", 0)) + 1
        )
    for key, value in (
        ("pending_iteration", 0),
        ("pending_divergent", False),
        ("pending_base_sha", None),
        ("pending_protocol_digest", None),
        ("pending_baseline_run_digest", None),
        ("pending_regression_baseline_run_digest", None),
        ("pending_baseline_admission_receipt", None),
        ("pending_baseline_activation_observation", None),
        ("pending_regression_baseline_admission_receipt", None),
        ("pending_repeated_started_at", None),
        ("active_attempt_iteration", None),
    ):
        final_state[key] = value
    if cleanup_failure is not None:
        final_state["cleanup_health"] = {
            "status": "failed",
            "detail": cleanup_failure,
        }
    return final_state


def _publication_gate_rungs(gate: dict[str, Any]) -> dict[str, str]:
    if type(gate.get("rungs")) is not list:
        raise RuntimeError("publication gate report rungs are malformed")
    statuses: dict[str, str] = {}
    for rung in gate["rungs"]:
        row = _require_closed_object(
            rung, {"rung", "status", "detail"}, field_name="publication gate rung"
        )
        if (
            type(row["rung"]) is not str
            or type(row["status"]) is not str
            or type(row["detail"]) is not dict
            or row["rung"] in statuses
        ):
            raise RuntimeError("publication gate rung identity is malformed")
        statuses[row["rung"]] = row["status"]
    return statuses


def _publication_rejection_errors(gate: dict[str, Any]) -> list[str]:
    """Return exact optimizer-admissibility errors retained by a failed gate."""
    rungs = gate.get("rungs")
    if type(rungs) is not list or len(rungs) != 1:
        return []
    rung = rungs[0]
    if (
        type(rung) is not dict
        or rung.get("rung") != "E0"
        or rung.get("status") != "fail"
    ):
        return []
    detail = rung.get("detail")
    if type(detail) is not dict:
        return []
    if set(detail) == {"manifest_errors"}:
        errors = detail["manifest_errors"]
        if (
            type(errors) is not list
            or not errors
            or any(type(error) is not str or not error for error in errors)
        ):
            raise RuntimeError("publication E0 manifest errors are malformed")
        return list(errors)
    guard_fields = {"changed", "violations", "dirty_worktree", "ok"}
    if set(detail) == guard_fields:
        changed = detail["changed"]
        violations = detail["violations"]
        dirty = detail["dirty_worktree"]
        if (
            detail["ok"] is not False
            or any(type(rows) is not list for rows in (changed, violations, dirty))
            or any(
                type(item) is not str or not item
                for rows in (changed, violations, dirty)
                for item in rows
            )
            or not violations and not dirty
        ):
            raise RuntimeError("publication E0 guard report is malformed")
        return [*violations, *dirty]
    if set(detail) & (guard_fields | {"manifest_errors"}):
        raise RuntimeError("publication E0 rejection detail has an invalid closed shape")
    return []


def _validate_publication_cross_artifacts(
    campaign: Campaign,
    record: dict[str, Any],
    *,
    result: dict[str, Any],
    gate: object,
    snapshot: object,
    ledger: object,
    learning: object,
) -> None:
    """Validate the one canonical publication evidence graph in any phase."""
    iteration = record["iteration"]
    gate = _require_closed_object(
        gate, GATE_REPORT_FIELDS, field_name="publication gate report"
    )
    verdict = Verdict(result["decision"], result["evidence_class"])
    if gate.get("iteration") != iteration or gate.get("verdict") != verdict.to_dict():
        raise RuntimeError("publication gate report has inconsistent identity or verdict")
    gate_rungs = _publication_gate_rungs(gate)
    run_digests = gate.get("run_digests")
    if (
        type(gate.get("admissions")) is not dict
        or type(run_digests) is not dict
        or any(
            type(name) is not str or not _is_sha256(value)
            for name, value in run_digests.items()
        )
    ):
        raise RuntimeError("publication gate evidence identity is malformed")

    ledger = _require_closed_object(
        ledger, LEDGER_ROW_FIELDS, field_name="publication ledger row"
    )
    expected_ledger = {
        "iteration": iteration,
        "campaign": campaign.campaign_id,
        "verdict": verdict.label,
        "decision": verdict.decision,
        "evidence_class": verdict.evidence_class,
        "advances_accepted_state": verdict.advances_accepted_state,
        "base_sha": record["base_sha"],
        "candidate_sha": record["candidate_sha"],
        "protocol_digest": record["protocol_digest"],
        "gate_rungs": gate_rungs,
        "comparison": gate.get("comparison"),
        "attribution": gate.get("attribution"),
        "eligibility": gate.get("eligibility"),
        "promotion_candidates": result["promotion_candidates"],
    }
    for field, value in expected_ledger.items():
        if ledger.get(field) != value:
            raise RuntimeError(f"publication ledger row has inconsistent {field}")
    if (
        type(ledger.get("divergent")) is not bool
        or any(
            type(ledger.get(field)) is not str
            for field in ("hypothesis", "target_component", "cluster_ref")
        )
        or type(ledger.get("fixed_variables")) is not dict
    ):
        raise RuntimeError("publication ledger manifest identity is malformed")

    if verdict.advances_accepted_state:
        if not {"dev_treatment", "regression_treatment"}.issubset(run_digests):
            raise RuntimeError("publication gate evidence identity is malformed")
        comparison = gate.get("comparison")
        fixed = comparison.get("fixed") if type(comparison) is dict else None
        if type(fixed) is not list or any(type(item) is not str for item in fixed):
            raise RuntimeError("publication gate fixed-task evidence is malformed")
        if result["promotion_candidates"] != sorted(set(fixed)):
            raise RuntimeError("publication result and gate comparison promotions differ")
    elif result["promotion_candidates"]:
        raise RuntimeError("non-advancing publication has promotion candidates")

    try:
        learning = validate_record(
            learning,
            campaign_root=campaign.store.campaign_dir,
            pending_gate=gate,
        )
    except ValueError as exc:
        raise RuntimeError(f"publication LearningRecord is invalid: {exc}") from exc
    for field, value in {
        "campaign_id": campaign.campaign_id,
        "iteration": iteration,
        "base_sha": record["base_sha"],
        "candidate_sha": record["candidate_sha"],
        "protocol_digest": record["protocol_digest"],
        "hypothesis": ledger["hypothesis"],
        "target_component": ledger["target_component"],
        "cluster_ref": ledger["cluster_ref"],
        "decision": verdict.to_dict(),
    }.items():
        if learning.get(field) != value:
            raise RuntimeError(f"publication LearningRecord has inconsistent {field}")

    try:
        protocol = load_frozen_protocol(campaign.iteration_dir(iteration))
    except (OSError, ProtocolError) as exc:
        raise RuntimeError(f"publication frozen protocol is invalid: {exc}") from exc
    if (
        protocol.get("campaign_id") != campaign.campaign_id
        or protocol.get("iteration") != iteration
        or protocol.get("protocol_digest") != record["protocol_digest"]
        or protocol.get("accepted_build", {}).get("commit_sha") != record["base_sha"]
        or protocol.get("execution", {}).get("fixed_variables")
        != ledger["fixed_variables"]
    ):
        raise RuntimeError("publication frozen protocol identity is inconsistent")

    if type(snapshot) is not dict:
        raise RuntimeError("publication manifest snapshot must be an object")
    if record["manifest_snapshot_digest"] != _manifest_snapshot_digest(snapshot):
        raise RuntimeError("publication manifest snapshot digest is inconsistent")
    if snapshot.get("record_type") == "rejected_submission":
        validation_errors = _publication_rejection_errors(gate)
        if not validation_errors:
            raise RuntimeError(
                "publication rejected manifest snapshot lacks gate validation errors"
            )
        try:
            expected_snapshot = rejected_submission_record(
                original_submission=snapshot.get("original_submission"),
                validation_errors=validation_errors,
                verdict=verdict.to_dict(),
            )
        except (TypeError, ValueError) as exc:
            raise RuntimeError("publication rejected manifest snapshot is invalid") from exc
        if snapshot != expected_snapshot:
            raise RuntimeError("publication rejected manifest snapshot is inconsistent")
    else:
        if snapshot.get("status") != verdict.label:
            raise RuntimeError("publication manifest snapshot has inconsistent verdict")
        if snapshot.get("attribution") != gate.get("attribution"):
            raise RuntimeError("publication manifest snapshot attribution is inconsistent")
        submitted_snapshot = copy.deepcopy(snapshot)
        submitted_snapshot.pop("attribution", None)
        submitted_snapshot["status"] = "proposed"
        changed_files = None
        if record["candidate_sha"] is not None:
            try:
                changed_files = [
                    path
                    for _status, path in gitutil.diff_name_status(
                        campaign.repo_root,
                        record["base_sha"],
                        record["candidate_sha"],
                    )
                ]
            except gitutil.GitError as exc:
                raise RuntimeError("publication candidate build identity is invalid") from exc
        snapshot_report = validate_manifest(
            submitted_snapshot,
            allowed_prefixes=tuple(protocol["candidate_allowlist"]),
            changed_files=changed_files,
            divergent=ledger["divergent"],
        )
        if not snapshot_report.ok:
            raise RuntimeError("publication manifest snapshot is structurally invalid")
        for field in ("hypothesis", "target_component", "cluster_ref"):
            if snapshot.get(field) != ledger[field]:
                raise RuntimeError(
                    f"publication manifest snapshot has inconsistent {field}"
                )


def _validate_pending_publication(
    campaign: Campaign, record: dict[str, Any]
) -> None:
    _require_closed_object(
        record, PENDING_PUBLICATION_FIELDS, field_name="pending publication record"
    )
    _validate_publication_identity(campaign, record)
    if record["status"] != "pending":
        raise RuntimeError("accepted publication intent has an invalid status")
    result = _validate_result_summary(record["result"], record=record)
    _validate_publication_cross_artifacts(
        campaign,
        record,
        result=result,
        gate=record["gate_report"],
        snapshot=record["manifest_snapshot"],
        ledger=record["ledger_row"],
        learning=record["learning_record"],
    )
    if not result["advanced_accepted_state"]:
        _validate_pending_nonadvancing_publication(campaign, record)
        return

    iteration = record["iteration"]
    base_sha = record["base_sha"]
    candidate_sha = record["candidate_sha"]
    protocol_digest = record["protocol_digest"]
    gate = _require_closed_object(
        record["gate_report"], GATE_REPORT_FIELDS, field_name="publication gate report"
    )
    accepted_verdict = Verdict("accepted", "benchmark").to_dict()
    if gate.get("iteration") != iteration or gate.get("verdict") != accepted_verdict:
        raise RuntimeError("publication gate report has inconsistent identity or verdict")
    if type(gate.get("rungs")) is not list:
        raise RuntimeError("publication gate report rungs are malformed")
    gate_rungs: dict[str, str] = {}
    for rung in gate["rungs"]:
        row = _require_closed_object(
            rung, {"rung", "status", "detail"}, field_name="publication gate rung"
        )
        if (
            type(row["rung"]) is not str
            or type(row["status"]) is not str
            or type(row["detail"]) is not dict
        ):
            raise RuntimeError("publication gate rung identity is malformed")
        if row["rung"] in gate_rungs:
            raise RuntimeError("publication gate report has duplicate rungs")
        gate_rungs[row["rung"]] = row["status"]
    run_digests = gate.get("run_digests")
    if (
        type(gate.get("admissions")) is not dict
        or type(run_digests) is not dict
        or any(type(name) is not str or not _is_sha256(value) for name, value in run_digests.items())
        or not {"dev_treatment", "regression_treatment"}.issubset(run_digests)
    ):
        raise RuntimeError("publication gate evidence identity is malformed")

    snapshot = record["manifest_snapshot"]
    if type(snapshot) is not dict or snapshot.get("status") != "accepted":
        raise RuntimeError("publication manifest snapshot has inconsistent verdict")
    if snapshot.get("attribution") != gate.get("attribution"):
        raise RuntimeError("publication manifest snapshot attribution is inconsistent")
    register = _require_closed_object(
        record["cluster_register"],
        {"schema_version", "clusters"},
        field_name="publication cluster register",
    )
    if register.get("schema_version") != "0.1-draft" or type(
        register.get("clusters")
    ) is not dict:
        raise RuntimeError("publication cluster register is malformed")

    ledger = _require_closed_object(
        record["ledger_row"], LEDGER_ROW_FIELDS, field_name="publication ledger row"
    )
    expected_ledger = {
        "iteration": iteration,
        "campaign": campaign.campaign_id,
        "verdict": "accepted",
        "decision": "accepted",
        "evidence_class": "benchmark",
        "advances_accepted_state": True,
        "base_sha": base_sha,
        "candidate_sha": candidate_sha,
        "protocol_digest": protocol_digest,
        "gate_rungs": gate_rungs,
        "comparison": gate.get("comparison"),
        "attribution": gate.get("attribution"),
        "eligibility": gate.get("eligibility"),
    }
    for field, value in expected_ledger.items():
        if ledger.get(field) != value:
            raise RuntimeError(f"publication ledger row has inconsistent {field}")

    if result["promotion_candidates"] != ledger.get("promotion_candidates"):
        raise RuntimeError("publication result and ledger promotions differ")
    comparison = gate.get("comparison")
    if type(comparison) is not dict:
        raise RuntimeError("publication gate comparison is malformed")
    fixed = comparison.get("fixed")
    if type(fixed) is not list or any(type(item) is not str for item in fixed):
        raise RuntimeError("publication gate fixed-task evidence is malformed")
    if result["promotion_candidates"] != sorted(set(fixed)):
        raise RuntimeError("publication result and gate comparison promotions differ")

    try:
        current_register = strict_json_loads(
            campaign.clusters_path.read_text(encoding="utf-8"),
            field_name="trusted cluster register",
        )
        _require_closed_object(
            current_register,
            {"schema_version", "clusters"},
            field_name="trusted cluster register",
        )
        if current_register != register:
            expected_register = update_after_iteration(
                copy.deepcopy(current_register),
                iteration=iteration,
                failed_by_cluster={},
                fixed_task_ids=set(fixed),
                analyst_version="conductor-record",
            )
            if expected_register != register:
                raise RuntimeError(
                    "publication cluster register is not the canonical transition"
                )
    except (OSError, UnicodeDecodeError, ValueError, KeyError, TypeError) as exc:
        raise RuntimeError(f"publication cluster register is invalid: {exc}") from exc

    pre_state = record["pre_state"]
    final_state = record["final_state"]
    if type(pre_state) is not dict or type(final_state) is not dict:
        raise RuntimeError("publication campaign states are malformed")
    if (
        pre_state.get("current_iteration") != iteration
        or pre_state.get("pending_iteration") != iteration
        or pre_state.get("pending_base_sha") != base_sha
        or pre_state.get("pending_protocol_digest") != protocol_digest
        or pre_state.get("accepted_base_sha") != base_sha
        or type(pre_state.get("pending_divergent")) is not bool
    ):
        raise RuntimeError("publication pre-state identity is inconsistent")
    treatment_admission = gate["admissions"].get("dev_treatment")
    admission = (
        treatment_admission.get("admission_receipt")
        if type(treatment_admission) is dict
        else None
    )
    if type(admission) is not dict:
        raise RuntimeError("publication final-state admission is inconsistent")

    divergent = pre_state["pending_divergent"]
    expected_manifest_fields = {
        "hypothesis": snapshot.get("hypothesis"),
        "target_component": snapshot.get("target_component"),
        "cluster_ref": snapshot.get("cluster_ref"),
        "divergent": divergent,
    }
    for field, value in expected_manifest_fields.items():
        if ledger.get(field) != value:
            raise RuntimeError(f"publication ledger row has inconsistent {field}")
    if any(
        type(ledger.get(field)) is not str
        for field in ("hypothesis", "target_component", "cluster_ref")
    ) or type(ledger.get("fixed_variables")) is not dict:
        raise RuntimeError("publication ledger manifest identity is malformed")

    fingerprint = f"{ledger['cluster_ref']}::{ledger['target_component']}"
    expected_final_state = _accepted_final_state(
        campaign,
        pre_state,
        iteration=iteration,
        candidate_sha=candidate_sha,
        admission=admission,
        divergent=divergent,
        fingerprint=fingerprint,
        comparison=gate["comparison"],
    )
    if final_state != expected_final_state:
        raise RuntimeError("publication final-state transition is inconsistent")

    expected_ref = record["expected_ref"]
    if _has_accepted_history(pre_state):
        if expected_ref != base_sha:
            raise RuntimeError("established accepted ref expectation is inconsistent")
    elif expected_ref not in {None, base_sha}:
        raise RuntimeError("first-publication accepted ref expectation is inconsistent")
    try:
        learning_record = validate_record(
            record.get("learning_record"),
            campaign_root=campaign.store.campaign_dir,
            pending_gate=record["gate_report"],
        )
    except ValueError as exc:
        raise RuntimeError(f"publication LearningRecord is invalid: {exc}") from exc
    if any(
        learning_record.get(field) != value
        for field, value in {
            "campaign_id": campaign.campaign_id,
            "iteration": iteration,
            "base_sha": base_sha,
            "candidate_sha": candidate_sha,
            "protocol_digest": protocol_digest,
            "hypothesis": ledger["hypothesis"],
            "target_component": ledger["target_component"],
            "cluster_ref": ledger["cluster_ref"],
        }.items()
    ):
        raise RuntimeError("publication LearningRecord identity is inconsistent")
    if learning_record["decision"] != accepted_verdict:
        raise RuntimeError("publication LearningRecord decision is inconsistent")

    try:
        protocol = load_frozen_protocol(campaign.iteration_dir(iteration))
    except (OSError, ProtocolError) as exc:
        raise RuntimeError(f"publication frozen protocol is invalid: {exc}") from exc
    if (
        protocol.get("campaign_id") != campaign.campaign_id
        or protocol.get("iteration") != iteration
        or protocol.get("protocol_digest") != protocol_digest
        or protocol.get("accepted_build", {}).get("commit_sha") != base_sha
    ):
        raise RuntimeError("publication frozen protocol identity is inconsistent")
    if ledger["fixed_variables"] != protocol.get("execution", {}).get(
        "fixed_variables"
    ):
        raise RuntimeError("publication fixed variables conflict with frozen protocol")
    expected_protection = pre_state.get(
        "accepted_protection",
        {
            "champion_sha": pre_state["accepted_base_sha"],
            "protected_tasks": [],
            "success_rates": {},
        },
    )
    if protocol.get("execution", {}).get("accepted_protection") != expected_protection:
        raise RuntimeError("publication durable protection conflicts with frozen protocol")
    submitted_snapshot = copy.deepcopy(snapshot)
    submitted_snapshot.pop("attribution", None)
    submitted_snapshot["status"] = "proposed"
    try:
        changed_files = [
            path
            for _status, path in gitutil.diff_name_status(
                campaign.repo_root, base_sha, candidate_sha
            )
        ]
        snapshot_report = validate_manifest(
            submitted_snapshot,
            allowed_prefixes=tuple(protocol["candidate_allowlist"]),
            changed_files=changed_files,
            divergent=divergent,
        )
    except (gitutil.GitError, KeyError, TypeError, ValueError) as exc:
        raise RuntimeError(f"publication manifest snapshot is invalid: {exc}") from exc
    if not snapshot_report.ok:
        raise RuntimeError("publication manifest snapshot is structurally invalid")
    if campaign.state != pre_state and campaign.state != final_state:
        raise RuntimeError("campaign state conflicts with accepted publication intent")


def _cleanup_failure_from_gate(gate: dict[str, Any]) -> str | None:
    rungs = gate.get("rungs")
    if type(rungs) is not list:
        return None
    for rung in rungs:
        if type(rung) is not dict:
            continue
        encoded = json.dumps(rung.get("detail"), sort_keys=True)
        if "cleanup" in encoded.lower() and rung.get("status") == "invalid":
            return encoded
    return None


def _validate_pending_nonadvancing_publication(
    campaign: Campaign, record: dict[str, Any]
) -> None:
    """Validate the state-inert branch of the sole publication intent."""
    iteration = record["iteration"]
    result = record["result"]
    verdict = Verdict(result["decision"], result["evidence_class"])
    if verdict.advances_accepted_state:
        raise RuntimeError("non-advancing publication intent has an accepted verdict")
    gate = _require_closed_object(
        record["gate_report"], GATE_REPORT_FIELDS, field_name="publication gate report"
    )
    if gate.get("iteration") != iteration or gate.get("verdict") != verdict.to_dict():
        raise RuntimeError("publication gate report has inconsistent identity or verdict")
    if type(gate.get("rungs")) is not list:
        raise RuntimeError("publication gate report rungs are malformed")
    gate_rungs: dict[str, str] = {}
    for rung in gate["rungs"]:
        row = _require_closed_object(
            rung, {"rung", "status", "detail"}, field_name="publication gate rung"
        )
        if (
            type(row["rung"]) is not str
            or type(row["status"]) is not str
            or type(row["detail"]) is not dict
            or row["rung"] in gate_rungs
        ):
            raise RuntimeError("publication gate rung identity is malformed")
        gate_rungs[row["rung"]] = row["status"]
    if type(gate.get("admissions")) is not dict or type(gate.get("run_digests")) is not dict:
        raise RuntimeError("publication gate evidence identity is malformed")

    snapshot = record["manifest_snapshot"]
    if type(snapshot) is not dict or snapshot.get("status") != verdict.label:
        raise RuntimeError("publication manifest snapshot has inconsistent verdict")
    ledger = _require_closed_object(
        record["ledger_row"], LEDGER_ROW_FIELDS, field_name="publication ledger row"
    )
    expected_ledger = {
        "iteration": iteration,
        "campaign": campaign.campaign_id,
        "verdict": verdict.label,
        "decision": verdict.decision,
        "evidence_class": verdict.evidence_class,
        "advances_accepted_state": False,
        "base_sha": record["base_sha"],
        "candidate_sha": record["candidate_sha"],
        "protocol_digest": record["protocol_digest"],
        "gate_rungs": gate_rungs,
        "comparison": gate.get("comparison"),
        "attribution": gate.get("attribution"),
        "eligibility": gate.get("eligibility"),
        "promotion_candidates": [],
    }
    for field, value in expected_ledger.items():
        if ledger.get(field) != value:
            raise RuntimeError(f"publication ledger row has inconsistent {field}")
    if (
        type(ledger.get("divergent")) is not bool
        or any(
            type(ledger.get(field)) is not str
            for field in ("hypothesis", "target_component", "cluster_ref")
        )
        or type(ledger.get("fixed_variables")) is not dict
    ):
        raise RuntimeError("publication ledger manifest identity is malformed")

    try:
        register = strict_json_loads(
            campaign.clusters_path.read_text(encoding="utf-8"),
            field_name="trusted cluster register",
        )
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise RuntimeError(f"publication cluster register is invalid: {exc}") from exc
    if record["cluster_register"] != register:
        raise RuntimeError("non-advancing publication changed the cluster register")

    pre_state = record["pre_state"]
    final_state = record["final_state"]
    if type(pre_state) is not dict or type(final_state) is not dict:
        raise RuntimeError("publication campaign states are malformed")
    if (
        pre_state.get("current_iteration") != iteration
        or pre_state.get("pending_iteration") != iteration
        or pre_state.get("pending_base_sha") != record["base_sha"]
        or pre_state.get("pending_protocol_digest") != record["protocol_digest"]
        or pre_state.get("accepted_base_sha") != record["base_sha"]
    ):
        raise RuntimeError("publication pre-state identity is inconsistent")
    fingerprint = (
        f"{ledger['cluster_ref']}::{ledger['target_component']}"
        if ledger["cluster_ref"] and ledger["target_component"]
        else None
    )
    expected_final = _nonadvancing_final_state(
        pre_state,
        verdict=verdict,
        divergent=ledger["divergent"],
        fingerprint=fingerprint,
        cleanup_failure=_cleanup_failure_from_gate(gate),
    )
    if final_state != expected_final:
        raise RuntimeError("publication final-state transition is inconsistent")
    if campaign.state != pre_state and campaign.state != final_state:
        raise RuntimeError("campaign state conflicts with pending publication intent")

    try:
        learning = validate_record(
            record["learning_record"],
            campaign_root=campaign.store.campaign_dir,
            pending_gate=gate,
        )
    except ValueError as exc:
        raise RuntimeError(f"publication LearningRecord is invalid: {exc}") from exc
    for field, value in {
        "campaign_id": campaign.campaign_id,
        "iteration": iteration,
        "base_sha": record["base_sha"],
        "candidate_sha": record["candidate_sha"],
        "protocol_digest": record["protocol_digest"],
        "hypothesis": ledger["hypothesis"],
        "target_component": ledger["target_component"],
        "cluster_ref": ledger["cluster_ref"],
        "decision": verdict.to_dict(),
    }.items():
        if learning.get(field) != value:
            raise RuntimeError(f"publication LearningRecord has inconsistent {field}")

    try:
        protocol = load_frozen_protocol(campaign.iteration_dir(iteration))
    except (OSError, ProtocolError) as exc:
        raise RuntimeError(f"publication frozen protocol is invalid: {exc}") from exc
    if (
        protocol.get("campaign_id") != campaign.campaign_id
        or protocol.get("iteration") != iteration
        or protocol.get("protocol_digest") != record["protocol_digest"]
        or protocol.get("accepted_build", {}).get("commit_sha") != record["base_sha"]
        or protocol.get("execution", {}).get("fixed_variables")
        != ledger["fixed_variables"]
    ):
        raise RuntimeError("publication frozen protocol identity is inconsistent")


def _validate_terminal_publication(
    campaign: Campaign, record: dict[str, Any]
) -> None:
    status = record.get("status")
    fields = FAILED_PUBLICATION_FIELDS if status == "failed" else TERMINAL_PUBLICATION_FIELDS
    _require_closed_object(record, fields, field_name="terminal publication receipt")
    _validate_publication_identity(campaign, record)
    if status not in {"complete", "failed"}:
        raise RuntimeError("terminal publication receipt has an invalid status")
    if not _is_sha256(record.get("intent_digest")):
        raise RuntimeError("terminal publication intent digest is invalid")
    _validate_result_summary(record["result_summary"], record=record)
    if status == "failed" and (
        type(record.get("error")) is not str or not record["error"]
    ):
        raise RuntimeError("failed publication receipt lacks an error")


def _load_publication_record(campaign: Campaign) -> dict[str, Any] | None:
    path = _publication_path(campaign)
    if not path.is_file():
        return None
    try:
        parsed = strict_json_loads(
            path.read_text(encoding="utf-8"), field_name=PUBLICATION_RECORD
        )
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise RuntimeError(f"accepted publication record is invalid: {exc}") from exc
    if type(parsed) is not dict:
        raise RuntimeError("accepted publication record must be an object")
    if parsed.get("status") == "pending":
        _validate_pending_publication(campaign, parsed)
    else:
        _validate_terminal_publication(campaign, parsed)
    return parsed


def _project_publication(
    campaign: Campaign,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Project the sole publication record against the current campaign state."""
    current = campaign.state.get("current_iteration")
    pending = campaign.state.get("pending_iteration")
    if (
        type(current) is not int
        or current < 0
        or type(pending) is not int
        or pending < 0
        or (pending and pending != current)
    ):
        raise RuntimeError("campaign iteration state is malformed")

    record = _load_publication_record(campaign)
    if record is None:
        if (current, pending) in {(0, 0), (1, 1)}:
            return {"status": "none", "recovery_required": False}, None
        raise RuntimeError(
            "accepted publication receipt is missing for established campaign state"
        )

    iteration = record["iteration"]
    if record["status"] == "pending":
        if iteration != current:
            raise RuntimeError(
                "pending publication iteration conflicts with campaign state"
            )
    else:
        expected_iteration = current if pending == 0 else current - 1
        if iteration != expected_iteration:
            raise RuntimeError(
                "terminal publication iteration conflicts with campaign state"
            )
        _validate_terminal_publication_artifacts(campaign, record)

    return {
        "status": record["status"],
        "iteration": iteration,
        "recovery_required": record["status"] == "pending",
        "receipt_digest": record["record_digest"],
    }, record


def publication_status(campaign: Campaign) -> dict[str, Any]:
    """Read-only projection of the conductor's sole publication authority."""
    try:
        projection, _record = _project_publication(campaign)
    except (RuntimeError, ValueError) as exc:
        return {
            "status": "malformed",
            "recovery_required": True,
            "error": str(exc),
        }
    return projection


def _ensure_ledger_row(path: Path, row: dict[str, Any], iteration: int) -> None:
    try:
        rows = read_rows(path)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise RuntimeError(f"trusted ledger is invalid: {exc}") from exc
    matches = [existing for existing in rows if existing.get("iteration") == iteration]
    if matches:
        if matches != [row]:
            raise RuntimeError("trusted ledger already has a different iteration row")
        return
    rows.append(row)
    atomic_write_text(
        path,
        "".join(json.dumps(item, sort_keys=True) + "\n" for item in rows),
    )


def _terminal_publication_record(
    pending: dict[str, Any],
    *,
    status: str,
    result_summary: dict[str, Any],
    error: str | None = None,
) -> dict[str, Any]:
    terminal = {
        field: copy.deepcopy(pending[field])
        for field in PUBLICATION_IDENTITY_FIELDS - {"status"}
    }
    terminal.update(
        status=status,
        intent_digest=pending["record_digest"],
        result_summary=copy.deepcopy(result_summary),
    )
    if status == "failed":
        terminal["error"] = error
    return _seal_publication_record(terminal)


def _load_strict_object(path: Path, *, field_name: str) -> dict[str, Any]:
    try:
        parsed = strict_json_loads(
            path.read_text(encoding="utf-8"), field_name=field_name
        )
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise RuntimeError(f"{field_name} is invalid: {exc}") from exc
    if type(parsed) is not dict:
        raise RuntimeError(f"{field_name} must be an object")
    return parsed


def _terminal_ledger_row(campaign: Campaign, iteration: int) -> dict[str, Any]:
    try:
        ledger = read_rows(campaign.ledger_path)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise RuntimeError(f"trusted ledger is invalid: {exc}") from exc
    rows = [row for row in ledger if row["iteration"] == iteration]
    if len(rows) != 1:
        raise RuntimeError("terminal publication has no unique canonical ledger row")
    return rows[0]


def _validate_terminal_publication_artifacts(
    campaign: Campaign, record: dict[str, Any]
) -> None:
    iteration = record["iteration"]
    result = record["result_summary"]
    iteration_dir = campaign.iteration_dir(iteration)
    gate = _load_strict_object(
        iteration_dir / "gate-report.json", field_name="terminal gate report"
    )
    snapshot = _load_strict_object(
        iteration_dir / "manifest.snapshot.json",
        field_name="terminal manifest snapshot",
    )
    ledger = _terminal_ledger_row(campaign, iteration)
    learning_matches = [
        row
        for row in read_records(
            campaign.learnings_path, campaign_root=campaign.store.campaign_dir
        )
        if row["iteration"] == iteration
    ]
    if len(learning_matches) != 1:
        raise RuntimeError("terminal publication lacks one valid LearningRecord")
    _validate_publication_cross_artifacts(
        campaign,
        record,
        result=result,
        gate=gate,
        snapshot=snapshot,
        ledger=ledger,
        learning=learning_matches[0],
    )


def _validate_terminal_publication_state(
    campaign: Campaign, record: dict[str, Any]
) -> None:
    iteration = record["iteration"]
    result = record["result_summary"]
    if (
        campaign.current_iteration != iteration
        or campaign.state.get("pending_iteration") != 0
        or campaign.state.get("accepted_base_sha") != result["accepted_base_sha"]
    ):
        raise RuntimeError("terminal publication conflicts with current campaign state")

    accepted_ref = ACCEPTED_REF.format(campaign=campaign.campaign_id)
    current_ref = gitutil.try_rev_parse(campaign.repo_root, accepted_ref)
    if result["advanced_accepted_state"]:
        accepted_iterations = campaign.state.get("accepted_iterations")
        if (
            type(accepted_iterations) is not list
            or not accepted_iterations
            or accepted_iterations[-1] != iteration
            or current_ref != record["candidate_sha"]
            or gitutil.rev_parse(
                campaign.repo_root, f"{record['candidate_sha']}^{{tree}}"
            )
            != record["candidate_tree"]
        ):
            raise RuntimeError("completed publication accepted identity is inconsistent")
    elif _has_accepted_history(campaign.state):
        if current_ref != record["base_sha"]:
            raise RuntimeError("failed publication established accepted ref is inconsistent")
    elif current_ref not in {None, record["base_sha"]}:
        raise RuntimeError("failed publication accepted ref is inconsistent")


def _cleanup_terminal_publication(
    campaign: Campaign,
    record: dict[str, Any],
    *,
    lock: CampaignLock,
) -> dict[str, Any]:
    materialization_store = campaign.store.campaign_dir / "materializations"
    lock.require_held(materialization_store)
    _validate_terminal_publication(campaign, record)
    _validate_terminal_publication_artifacts(campaign, record)
    _validate_terminal_publication_state(campaign, record)

    try:
        staging_ref = record["staging_ref"]
        candidate_sha = record["candidate_sha"]
        if staging_ref is not None:
            staged = gitutil.try_rev_parse(campaign.repo_root, staging_ref)
            if staged == candidate_sha:
                gitutil.delete_ref(campaign.repo_root, staging_ref, expected=candidate_sha)
            elif staged is not None:
                raise RuntimeError("terminal publication staging ref points elsewhere")
        trusted_handback = (
            campaign.iteration_dir(record["iteration"]) / "candidate.handback.bundle"
        )
        trusted_handback.unlink(missing_ok=True)
        gitutil.worktree_remove(campaign.repo_root, campaign.worktree_path)
        if campaign.worktree_path.exists() or campaign.worktree_path.is_symlink():
            raise RuntimeError("terminal publication worktree cleanup did not complete")
    except Exception as exc:
        campaign.state["cleanup_health"] = {
            "status": "failed",
            "detail": f"terminal publication cleanup failed: {exc}",
        }
        campaign.save_state()
        raise
    cleanup = campaign.state.get("cleanup_health")
    if (
        type(cleanup) is dict
        and cleanup.get("status") == "failed"
        and str(cleanup.get("detail", "")).startswith(
            "terminal publication cleanup failed:"
        )
    ):
        campaign.state["cleanup_health"] = {
            "status": "clean",
            "detail": "terminal publication cleanup recovered",
        }
        campaign.save_state()
    return copy.deepcopy(record["result_summary"])


def _recover_publication(
    campaign: Campaign,
    record: dict[str, Any],
    *,
    lock: CampaignLock,
) -> dict[str, Any]:
    """Idempotently finish the sole terminal publication intent."""
    materialization_store = campaign.store.campaign_dir / "materializations"
    lock.require_held(materialization_store)
    _validate_pending_publication(campaign, record)
    iteration = record["iteration"]
    candidate_sha = record["candidate_sha"]
    candidate_tree = record["candidate_tree"]
    staging_ref = record["staging_ref"]
    expected_ref = record["expected_ref"]
    if candidate_sha is not None and (
        gitutil.rev_parse(campaign.repo_root, f"{candidate_sha}^{{commit}}")
        != candidate_sha
        or gitutil.rev_parse(campaign.repo_root, f"{candidate_sha}^{{tree}}")
        != candidate_tree
    ):
        raise RuntimeError("publication candidate commit/tree is unavailable")
    if record["result"]["advanced_accepted_state"]:
        if staging_ref is None or candidate_sha is None:
            raise RuntimeError("accepted publication staging identity is unavailable")
        accepted_ref = ACCEPTED_REF.format(campaign=campaign.campaign_id)
        current_ref = gitutil.try_rev_parse(campaign.repo_root, accepted_ref)
        if current_ref == expected_ref:
            if gitutil.try_rev_parse(campaign.repo_root, staging_ref) != candidate_sha:
                raise RuntimeError("accepted publication staging ref is unavailable")
            try:
                gitutil.compare_and_swap_ref(
                    campaign.repo_root,
                    accepted_ref,
                    candidate_sha,
                    expected=expected_ref,
                )
            except gitutil.GitError as exc:
                observed_ref = gitutil.try_rev_parse(campaign.repo_root, accepted_ref)
                if observed_ref == candidate_sha:
                    pass
                elif observed_ref is not None and observed_ref != expected_ref:
                    raise _AcceptedRefContention(
                        "accepted ref changed during candidate publication"
                    ) from exc
                else:
                    raise
        elif current_ref is not None and current_ref != candidate_sha:
            raise _AcceptedRefContention(
                "accepted ref conflicts with pending publication"
            )
        elif current_ref != candidate_sha:
            raise gitutil.GitError(
                "accepted ref is unavailable during pending publication"
            )
        _publication_checkpoint("accepted-ref")

    iteration_dir = campaign.iteration_dir(iteration)
    atomic_write_json(iteration_dir / "gate-report.json", record["gate_report"])
    _publication_checkpoint("gate-report")
    atomic_write_json(
        iteration_dir / "manifest.snapshot.json", record["manifest_snapshot"]
    )
    _publication_checkpoint("manifest-snapshot")
    if record["result"]["advanced_accepted_state"]:
        atomic_write_json(campaign.clusters_path, record["cluster_register"])
        _publication_checkpoint("cluster-register")
    _ensure_ledger_row(campaign.ledger_path, record["ledger_row"], iteration)
    _publication_checkpoint("ledger")
    ensure_record(
        campaign.learnings_path,
        record["learning_record"],
        campaign_root=campaign.store.campaign_dir,
    )
    _publication_checkpoint("learnings")

    current_state = campaign.state
    if (
        current_state != record["pre_state"]
        and current_state != record["final_state"]
    ):
        raise RuntimeError("campaign state conflicts with pending publication")
    campaign.state = copy.deepcopy(record["final_state"])
    campaign.save_state()
    _publication_checkpoint("campaign-state")

    publication_error: str | None = None
    terminal_status = "complete"
    if not record["result"]["advanced_accepted_state"] and staging_ref is not None:
        terminal_status = "failed"
        for rung in record["gate_report"]["rungs"]:
            detail = rung.get("detail") if type(rung) is dict else None
            error = detail.get("error") if type(detail) is dict else None
            if type(error) is str and error:
                publication_error = error
                break
        if publication_error is None:
            raise RuntimeError("failed publication outcome lacks a retained error")
    completed = _terminal_publication_record(
        record,
        status=terminal_status,
        result_summary=record["result"],
        error=publication_error,
    )
    atomic_write_json(_publication_path(campaign), completed)
    _publication_checkpoint(
        "failed-receipt" if terminal_status == "failed" else "complete-receipt"
    )
    return _cleanup_terminal_publication(campaign, completed, lock=lock)


def _recover_pending_publication(
    campaign: Campaign, *, lock: CampaignLock
) -> dict[str, Any] | None:
    record = _project_publication(campaign)[1]
    if record is None:
        return None
    if record["status"] == "pending":
        return _recover_publication(campaign, record, lock=lock)
    if record["iteration"] > campaign.current_iteration:
        raise RuntimeError("terminal publication receipt is ahead of campaign state")
    if record["iteration"] == campaign.current_iteration:
        return _cleanup_terminal_publication(campaign, record, lock=lock)
    return None


def _persist_nonadvancing_publication(
    campaign: Campaign,
    *,
    lock: CampaignLock,
    iteration: int,
    base_sha: str,
    protocol_digest: str,
    report: dict[str, Any],
    manifest_snapshot: dict[str, Any],
    ledger_row: dict[str, Any],
    learning_record: dict[str, Any],
    final_state: dict[str, Any],
    candidate_sha: str | None,
    candidate_tree: str | None,
    staging_ref: str | None,
    expected_ref: str | None,
) -> dict[str, Any]:
    """Seal then reconcile the state-inert branch of the sole intent."""
    result = {
        "iteration": iteration,
        "verdict": report["verdict"]["label"],
        "decision": report["verdict"]["decision"],
        "evidence_class": report["verdict"]["evidence_class"],
        "advanced_accepted_state": False,
        "promotion_candidates": [],
        "accepted_base_sha": base_sha,
    }
    publication = _seal_publication_record(
        {
            "schema_version": PUBLICATION_SCHEMA_VERSION,
            "record_type": PUBLICATION_RECORD_TYPE,
            "status": "pending",
            "campaign_id": campaign.campaign_id,
            "iteration": iteration,
            "protocol_digest": protocol_digest,
            "base_sha": base_sha,
            "candidate_sha": candidate_sha,
            "candidate_tree": candidate_tree,
            "staging_ref": staging_ref,
            "expected_ref": expected_ref,
            "manifest_snapshot_digest": _manifest_snapshot_digest(
                manifest_snapshot
            ),
            "gate_report": report,
            "manifest_snapshot": manifest_snapshot,
            "cluster_register": load_register(campaign.clusters_path),
            "ledger_row": ledger_row,
            "learning_record": learning_record,
            "pre_state": copy.deepcopy(campaign.state),
            "final_state": final_state,
            "result": result,
        }
    )
    _validate_pending_publication(campaign, publication)
    atomic_write_json(_publication_path(campaign), publication)
    persisted = _load_publication_record(campaign)
    if persisted != publication:
        raise RuntimeError("durable publication intent changed")
    _publication_checkpoint("intent")
    return _recover_publication(campaign, publication, lock=lock)


def _clear_pre_intent_attempt(
    iteration_dir: Path, *, preserve_bundle: Path | None
) -> None:
    """Remove derived attempt artifacts when no publication intent exists."""
    for bundle in (
        iteration_dir / "candidate.bundle",
        iteration_dir / "candidate.handback.bundle",
    ):
        if preserve_bundle is None or bundle != preserve_bundle:
            bundle.unlink(missing_ok=True)
    for name in (
        "smoke_treatment",
        "targeted_screen",
        "regression_screen",
    ):
        output = iteration_dir / "eval" / name
        if output.is_symlink() or output.is_file():
            output.unlink()
        elif output.exists():
            shutil.rmtree(output)


def _cleanup_failure(report: GateReport) -> str | None:
    """Return the exact retained cleanup failure without process machinery."""
    for rung in report.rungs:
        encoded = json.dumps(rung.detail, sort_keys=True)
        if "cleanup" in encoded.lower() and rung.status == "invalid":
            return encoded
    return None


def run_iteration(
    campaign: Campaign,
    *,
    candidate_bundle: Path | None = None,
    candidate_manifest: Path | None = None,
) -> dict[str, Any]:
    materialization_store = campaign.store.campaign_dir / "materializations"
    materialization_store.mkdir(mode=0o700, exist_ok=True)
    materialization_store.chmod(0o700)
    with CampaignLock(materialization_store) as lock:
        fresh = load_campaign(
            campaign.repo_root,
            campaign.campaign_id,
            store_root=campaign.store.root,
        )
        campaign.config = fresh.config
        campaign.state = fresh.state
        require_transition(campaign, action="reconcile")
        _project_publication(campaign)
        recovered = _recover_pending_publication(campaign, lock=lock)
        if recovered is not None:
            return recovered
        with ExitStack() as resources:
            return _run_iteration_locked(
                campaign,
                candidate_bundle=candidate_bundle,
                candidate_manifest=candidate_manifest,
                lock=lock,
                resources=resources,
            )


def continue_campaign(
    campaign: Campaign,
    *,
    candidate_bundle: Path | None = None,
    candidate_manifest: Path | None = None,
) -> dict[str, Any]:
    """Reload under the campaign lock, then resume pending work or start once."""
    materialization_store = campaign.store.campaign_dir / "materializations"
    materialization_store.mkdir(mode=0o700, exist_ok=True)
    materialization_store.chmod(0o700)
    with CampaignLock(materialization_store) as lock:
        fresh = load_campaign(
            campaign.repo_root,
            campaign.campaign_id,
            store_root=campaign.store.root,
        )
        campaign.config = fresh.config
        campaign.state = fresh.state
        require_transition(campaign, action="reconcile")
        try:
            _projection, publication = _project_publication(campaign)
        except (RuntimeError, ValueError) as exc:
            raise RuntimeError(
                "publication record is malformed; inspect retained receipt: " + str(exc)
            ) from exc
        if publication is not None and publication["status"] == "pending":
            return _recover_publication(campaign, publication, lock=lock)
        if campaign.state.get("pending_iteration"):
            with ExitStack() as resources:
                return _run_iteration_locked(
                    campaign,
                    candidate_bundle=candidate_bundle,
                    candidate_manifest=candidate_manifest,
                    lock=lock,
                    resources=resources,
                )
        if publication is not None:
            if publication["iteration"] > campaign.current_iteration:
                raise RuntimeError(
                    "terminal publication receipt is ahead of campaign state"
                )
            if publication["iteration"] == campaign.current_iteration:
                _cleanup_terminal_publication(campaign, publication, lock=lock)
        return _start_iteration_locked(campaign, lock=lock)


def _run_iteration_locked(
    campaign: Campaign,
    *,
    candidate_bundle: Path | None,
    candidate_manifest: Path | None,
    lock: CampaignLock,
    resources: ExitStack,
) -> dict[str, Any]:
    materialization_store = campaign.store.campaign_dir / "materializations"
    lock.require_held(materialization_store)
    _project_publication(campaign)
    number = int(campaign.state.get("pending_iteration") or 0)
    if not number:
        raise RuntimeError("no pending iteration — run `opti-loop start` first")
    iteration_dir = campaign.iteration_dir(number)
    _clear_pre_intent_attempt(
        iteration_dir,
        preserve_bundle=(Path(candidate_bundle) if candidate_bundle is not None else None),
    )
    protocol = load_frozen_protocol(iteration_dir)
    pending_digest = campaign.state.get("pending_protocol_digest")
    if pending_digest != protocol["protocol_digest"]:
        raise RuntimeError(
            "pending iteration protocol digest does not match the frozen protocol snapshot"
        )
    execution = protocol["execution"]
    worktree = campaign.worktree_path
    base_sha = str(campaign.state["pending_base_sha"])
    accepted_base_sha = str(campaign.state.get("accepted_base_sha") or "")
    if not accepted_base_sha or base_sha != accepted_base_sha:
        raise RuntimeError(
            "pending iteration base no longer matches freshly loaded accepted state"
        )
    expected_accepted_ref = _expected_accepted_ref(campaign, campaign.state)
    note_attempt(campaign)
    divergent = bool(campaign.state.get("pending_divergent", False))
    benchmark_handback = _benchmark_handback_required(protocol)

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
    baseline.activation_observation = campaign.state.get(
        "pending_baseline_activation_observation"
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

    candidate_sha = ""
    submitted_manifest: object = None
    manifest: dict[str, Any] = {}
    manifest_report = ManifestReport(manifest=None)
    report: GateReport | None = None
    handback: Path | None = None
    manifest_path: Path | None = None
    trusted_handback: Path | None = None
    receipt: dict[str, Any] | None = None
    treatment_build: dict[str, Any] | None = None
    staged_publication: tuple[str, str | None] | None = None
    manifest_fd: int | None = None
    manifest_parent_fd: int | None = None
    manifest_parent_info: os.stat_result | None = None

    handback, manifest_path = _optimizer_bundle(
        campaign,
        supplied_bundle=candidate_bundle,
        supplied_manifest=candidate_manifest,
        evidence_mode=protocol["evidence_mode"],
    )
    if not benchmark_handback and handback is None:
        candidate_sha = gitutil.head_sha(worktree)
    if benchmark_handback and manifest_path is not None:
        try:
            manifest_fd, manifest_parent_fd, manifest_parent_info = (
                _open_manifest_nofollow(manifest_path, resources)
            )
        except MaterializationError as exc:
            submitted_manifest = None
            parsed_report = ManifestReport(manifest=None, errors=[str(exc)])
        else:
            submitted_manifest, parsed_report = _read_manifest_snapshot(
                manifest_path, pinned_descriptor=manifest_fd
            )
    else:
        submitted_manifest, parsed_report = _read_manifest_snapshot(manifest_path)
    manifest_report = parsed_report if parsed_report.errors else validate_manifest(
        submitted_manifest,
        allowed_prefixes=tuple(protocol["candidate_allowlist"]),
        divergent=divergent,
    )
    manifest = (
        submitted_manifest if isinstance(submitted_manifest, dict) else {}
    )

    if report is None and not manifest_report.ok:
        report = GateReport(iteration=number)
        report.verdict = Verdict("rejected", "simulated")
        report.rungs.append(
            RungResult("E0", "fail", {"manifest_errors": manifest_report.errors})
        )

    if report is None and handback is None:
        try:
            simulated_guard = fileguard.check_candidate(
                repo=campaign.repo_root,
                worktree=worktree,
                base_sha=base_sha,
                candidate_sha=candidate_sha,
                allowed_prefixes=tuple(protocol["candidate_allowlist"]),
            )
        except fileguard.GuardError as exc:
            report = GateReport(iteration=number)
            report.rungs.append(RungResult("E0", "invalid", {"error": str(exc)}))
        else:
            if not simulated_guard.ok:
                report = GateReport(iteration=number)
                report.verdict = Verdict("rejected", "simulated")
                report.rungs.append(RungResult("E0", "fail", simulated_guard.to_dict()))

    # Pivot enforcement (F16): forbid a 3rd attempt at the same cluster+component.
    pivot_after = int(execution["exploration"].get("pivot_after_failures", 2))
    fingerprint = None
    prior_failures = 0
    if report is None and manifest_report.ok:
        fingerprint = f"{manifest.get('cluster_ref')}::{manifest.get('target_component')}"
        prior_failures = int(
            campaign.state.get("failed_attempts", {}).get(fingerprint, 0)
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
    if report is None:
        try:
            if handback is None:
                if benchmark_handback:
                    raise MaterializationError(
                        "benchmark candidate bundle was not supplied"
                    )
                handback = iteration_dir / "candidate.bundle"
                gitutil.create_candidate_bundle(
                    campaign.repo_root,
                    handback,
                    base_sha=base_sha,
                    candidate_sha=candidate_sha,
                )
            elif benchmark_handback:
                if (
                    manifest_path is None
                    or manifest_fd is None
                    or manifest_parent_fd is None
                    or manifest_parent_info is None
                ):
                    raise MaterializationError(
                        "benchmark candidate manifest sidecar was not supplied"
                    )
                bundle_fd, bundle_info = _open_benchmark_bundle(
                    handback, manifest_path, manifest_parent_fd, resources
                )
                optimizer_uid = _validate_benchmark_handback_ownership(
                    bundle_info=bundle_info,
                    manifest_info=os.fstat(manifest_fd),
                    parent_info=manifest_parent_info,
                )
                trusted_handback = _copy_benchmark_bundle(
                    bundle_fd,
                    iteration_dir / "candidate.handback.bundle",
                    optimizer_uid=optimizer_uid,
                )
                handback = trusted_handback
            materialization, receipt = materialize_candidate_bundle(
                handback,
                trusted_repo=campaign.repo_root,
                protocol_snapshot=protocol,
                lock=lock,
            )
            treatment_build = project_build_identity(
                materialization, protocol_snapshot=protocol
            )
            candidate_sha = treatment_build["commit_sha"]
        except (
            MaterializationError,
            fileguard.GuardError,
            gitutil.GitError,
            OSError,
        ) as exc:
            report = GateReport(iteration=number)
            report.rungs.append(
                RungResult(
                    "E1",
                    "invalid",
                    {"error": f"candidate materialization invalid: {exc}"},
                )
            )
        else:
            consumption = consume_materialization(materialization)
            try:
                candidate_root, consumed = consumption.__enter__()
            except MaterializationError as exc:
                report = GateReport(iteration=number)
                report.rungs.append(
                    RungResult(
                        "E1",
                        "invalid",
                        {"error": f"candidate materialization invalid: {exc}"},
                    )
                )
            else:
                preparation_error: Exception | None = None
                try:
                    if consumed != receipt:
                        raise MaterializationError(
                            "consumed materialization receipt does not match imported receipt"
                        )
                    guard = fileguard.check_materialized_candidate(
                        repo=campaign.repo_root,
                        candidate_root=candidate_root,
                        base_sha=base_sha,
                        allowed_prefixes=tuple(protocol["candidate_allowlist"]),
                    )
                    manifest_report = validate_manifest(
                        manifest,
                        allowed_prefixes=tuple(protocol["candidate_allowlist"]),
                        changed_files=guard.changed,
                        divergent=divergent,
                    )
                except (
                    MaterializationError,
                    fileguard.GuardError,
                    gitutil.GitError,
                    OSError,
                ) as exc:
                    preparation_error = exc
                if preparation_error is not None:
                    try:
                        consumption.__exit__(None, None, None)
                    except MaterializationError as exc:
                        preparation_error = exc
                    report = GateReport(iteration=number)
                    report.rungs.append(
                        RungResult(
                            "E1",
                            "invalid",
                            {
                                "error": "candidate materialization invalid: "
                                f"{preparation_error}"
                            },
                        )
                    )
                elif manifest_report.ok and prior_failures >= pivot_after:
                    try:
                        consumption.__exit__(None, None, None)
                    except MaterializationError as exc:
                        report = GateReport(iteration=number)
                        report.rungs.append(
                            RungResult(
                                "E1",
                                "invalid",
                                {"error": f"candidate materialization invalid: {exc}"},
                            )
                        )
                    else:
                        return _reject_pivot(
                            campaign,
                            number,
                            fingerprint,
                            prior_failures,
                            base_sha,
                            manifest,
                            protocol=protocol,
                            divergent=divergent,
                            expected_ref=expected_accepted_ref,
                            lock=lock,
                        )
                else:
                    # Gate code owns expected operational failures at their
                    # active rung. Its unexpected exceptions are never relabeled.
                    started_at = campaign.state.get("pending_repeated_started_at")
                    if started_at is None:
                        started_at = time.time()
                        campaign.state["pending_repeated_started_at"] = started_at
                        campaign.save_state()
                    if type(started_at) not in {int, float}:
                        raise RuntimeError("pending repeated-protocol deadline is malformed")
                    deadline_at = float(started_at) + int(
                        protocol["repeated_protocol"]["limits"]["deadline_seconds"]
                    )
                    baseline_root = iteration_dir / "accepted-repeated-worktree"
                    gitutil.worktree_add(campaign.repo_root, baseline_root, base_sha)
                    resources.callback(
                        gitutil.worktree_remove, campaign.repo_root, baseline_root
                    )
                    transfer_status = _frozen_transfer_status(campaign, protocol)
                    gate_completed = False
                    try:
                        report = run_gate(
                            repo_root=campaign.repo_root,
                            candidate_root=candidate_root,
                            candidate_guard=guard,
                            base_sha=base_sha,
                            iteration=number,
                            eval_root=iteration_dir / "eval",
                            baseline_dev=baseline,
                            manifest=manifest,
                            manifest_report=manifest_report,
                            adapter_config=execution["adapter"],
                            suites=execution["suites"],
                            thresholds=execution["thresholds"],
                            noise_band=band,
                            run_identity=protocol_identity,
                            noise_band_error=noise_band_error,
                            protocol_snapshot=protocol,
                            task_sources=sources,
                            task_records=records,
                            regression_baseline=regression_baseline,
                            admissions_path=campaign.store.admissions_path,
                            quarantine_path=campaign.store.quarantine_path,
                            treatment_build=treatment_build,
                            baseline_root=baseline_root,
                            deadline_at=deadline_at,
                            now=time.time,
                            transfer_status=transfer_status,
                        )
                        gate_completed = True
                    finally:
                        if not gate_completed:
                            try:
                                consumption.__exit__(*sys.exc_info())
                            except MaterializationError:
                                pass
                    try:
                        consumption.__exit__(None, None, None)
                    except MaterializationError as exc:
                        report = GateReport(iteration=number)
                        report.rungs.append(
                            RungResult(
                                "E1",
                                "invalid",
                                {"error": f"candidate materialization invalid: {exc}"},
                            )
                        )
    assert report is not None
    accepted_admission: dict[str, Any] | None = None
    publication_failure: str | None = None
    if report.verdict.advances_accepted_state:
        try:
            if not report.run_digests.get("dev_treatment") or not report.run_digests.get(
                "regression_treatment"
            ):
                raise MaterializationError(
                    "accepted gate report is missing trusted treatment run digests"
                )
            admission = report.admissions.get("dev_treatment", {}).get(
                "admission_receipt"
            )
            if not isinstance(admission, dict):
                raise MaterializationError(
                    "accepted gate report is missing AR-003 treatment admission"
                )
            accepted_admission = admission
            staged_publication = _stage_accepted_candidate(
                campaign,
                report,
                trusted_bundle=trusted_handback,
                receipt=receipt,
                treatment_build=treatment_build,
                expected_ref=expected_accepted_ref,
            )
        except (MaterializationError, gitutil.GitError) as exc:
            report = GateReport(iteration=number)
            report.verdict = Verdict("invalid", "benchmark")
            report.rungs.append(
                RungResult(
                    "E1",
                    "invalid",
                    {"error": f"candidate publication preflight invalid: {exc}"},
                )
            )

    if report.verdict.advances_accepted_state:
        assert accepted_admission is not None
        assert staged_publication is not None
        assert treatment_build is not None
        staging_ref, staging_expected_ref = staged_publication
        publication: dict[str, Any] | None = None
        try:
            fixed = set((report.comparison or {}).get("fixed", []))
            promotion_candidates = sorted(fixed)
            register = update_after_iteration(
                load_register(campaign.clusters_path),
                iteration=number,
                failed_by_cluster={},
                fixed_task_ids=fixed,
                analyst_version="conductor-record",
            )
            ledger_row = {
                "iteration": number,
                "campaign": campaign.campaign_id,
                "verdict": report.verdict.label,
                "decision": report.verdict.decision,
                "evidence_class": report.verdict.evidence_class,
                "advances_accepted_state": True,
                "divergent": divergent,
                "base_sha": base_sha,
                "candidate_sha": candidate_sha,
                "protocol_digest": protocol["protocol_digest"],
                "hypothesis": manifest.get("hypothesis", ""),
                "target_component": manifest.get("target_component", ""),
                "cluster_ref": manifest.get("cluster_ref", ""),
                "gate_rungs": {r.rung: r.status for r in report.rungs},
                "comparison": report.comparison,
                "attribution": report.attribution,
                "eligibility": report.eligibility,
                "fixed_variables": execution["fixed_variables"],
                "promotion_candidates": promotion_candidates,
            }
            assert fingerprint is not None
            final_state = _accepted_final_state(
                campaign,
                campaign.state,
                iteration=number,
                candidate_sha=candidate_sha,
                admission=accepted_admission,
                divergent=divergent,
                fingerprint=fingerprint,
                comparison=report.comparison,
            )
            manifest_snapshot = _trusted_manifest_snapshot(
                manifest,
                report.verdict,
                report.attribution,
                original_submission=submitted_manifest,
                validation_errors=(
                    manifest_report.errors if not manifest_report.ok else None
                ),
            )
            publication = _seal_publication_record(
                {
                    "schema_version": PUBLICATION_SCHEMA_VERSION,
                    "record_type": PUBLICATION_RECORD_TYPE,
                    "status": "pending",
                    "campaign_id": campaign.campaign_id,
                    "iteration": number,
                    "protocol_digest": protocol["protocol_digest"],
                    "base_sha": base_sha,
                    "candidate_sha": candidate_sha,
                    "candidate_tree": treatment_build["tree_sha"],
                    "staging_ref": staging_ref,
                    "expected_ref": staging_expected_ref,
                    "manifest_snapshot_digest": _manifest_snapshot_digest(
                        manifest_snapshot
                    ),
                    "gate_report": report.to_dict(),
                    "manifest_snapshot": manifest_snapshot,
                    "cluster_register": register,
                    "ledger_row": ledger_row,
                    "learning_record": build_record(
                        campaign_root=campaign.store.campaign_dir,
                        campaign_id=campaign.campaign_id,
                        iteration=number,
                        base_sha=base_sha,
                        candidate_sha=candidate_sha,
                        protocol_digest=protocol["protocol_digest"],
                        verdict=report.verdict.to_dict(),
                        manifest=manifest,
                        gate_report=report.to_dict(),
                    ),
                    "pre_state": copy.deepcopy(campaign.state),
                    "final_state": final_state,
                    "result": {
                        "iteration": number,
                        "verdict": report.verdict.label,
                        "decision": report.verdict.decision,
                        "evidence_class": report.verdict.evidence_class,
                        "advanced_accepted_state": True,
                        "promotion_candidates": promotion_candidates,
                        "accepted_base_sha": candidate_sha,
                    },
                }
            )
            _validate_pending_publication(campaign, publication)
            atomic_write_json(_publication_path(campaign), publication)
            persisted = _load_publication_record(campaign)
            if persisted != publication:
                raise RuntimeError("durable accepted publication intent changed")
        except BaseException:
            delete_staging = publication is None
            if publication is not None:
                try:
                    persisted = _load_publication_record(campaign)
                except RuntimeError:
                    pass
                else:
                    delete_staging = persisted != publication
            if delete_staging:
                _delete_staged_candidate(campaign, staging_ref, candidate_sha)
            raise
        assert publication is not None
        _publication_checkpoint("intent")
        try:
            return _recover_publication(campaign, publication, lock=lock)
        except _AcceptedRefContention as exc:
            publication_failure = str(exc)
            report = GateReport(iteration=number)
            report.verdict = Verdict("invalid", "benchmark")
            report.rungs.append(
                RungResult(
                    "E1",
                    "invalid",
                    {"error": f"candidate publication preflight invalid: {exc}"},
                )
            )
    verdict: Verdict = report.verdict
    if verdict.advances_accepted_state:
        raise RuntimeError("accepted publication bypassed its sole recovery state machine")
    candidate_identity = candidate_sha or None
    candidate_tree = (
        gitutil.rev_parse(campaign.repo_root, f"{candidate_identity}^{{tree}}")
        if candidate_identity is not None
        else None
    )
    staging_ref = staged_publication[0] if staged_publication is not None else None
    staging_expected_ref = (
        staged_publication[1]
        if staged_publication is not None
        else expected_accepted_ref
    )
    report_dict = report.to_dict()
    rejection_errors = _publication_rejection_errors(report_dict)
    snapshot = _trusted_manifest_snapshot(
        manifest,
        verdict,
        report.attribution,
        original_submission=submitted_manifest,
        validation_errors=(rejection_errors or None),
    )
    ledger_row = {
        "iteration": number, "campaign": campaign.campaign_id,
        "verdict": verdict.label, "decision": verdict.decision, "evidence_class": verdict.evidence_class,
        "advances_accepted_state": False, "divergent": divergent,
        "base_sha": base_sha, "candidate_sha": candidate_identity,
        "protocol_digest": protocol["protocol_digest"],
        "hypothesis": manifest.get("hypothesis", ""), "target_component": manifest.get("target_component", ""),
        "cluster_ref": manifest.get("cluster_ref", ""),
        "gate_rungs": {r.rung: r.status for r in report.rungs},
        "comparison": report.comparison, "attribution": report.attribution,
        "eligibility": report.eligibility, "fixed_variables": execution["fixed_variables"],
        "promotion_candidates": [],
    }
    learning_record = build_record(
        campaign_root=campaign.store.campaign_dir,
        campaign_id=campaign.campaign_id,
        iteration=number,
        base_sha=base_sha,
        candidate_sha=candidate_identity,
        protocol_digest=protocol["protocol_digest"],
        verdict=verdict.to_dict(),
        manifest=manifest,
        gate_report=report_dict,
    )
    final_state = _nonadvancing_final_state(
        campaign.state,
        verdict=verdict,
        divergent=divergent,
        fingerprint=fingerprint,
        cleanup_failure=_cleanup_failure(report),
    )
    try:
        return _persist_nonadvancing_publication(
            campaign,
            lock=lock,
            iteration=number,
            base_sha=base_sha,
            protocol_digest=protocol["protocol_digest"],
            report=report_dict,
            manifest_snapshot=snapshot,
            ledger_row=ledger_row,
            learning_record=learning_record,
            final_state=final_state,
            candidate_sha=candidate_identity,
            candidate_tree=candidate_tree,
            staging_ref=staging_ref,
            expected_ref=staging_expected_ref,
        )
    except BaseException:
        # Once the replacement intent is durable, replay owns all cleanup.
        # Before that point, preserve any staged accepted candidate for the
        # still-durable accepted intent rather than creating a second authority.
        if publication_failure is None and staging_ref is not None:
            persisted = _load_publication_record(campaign)
            if persisted is None:
                _delete_staged_candidate(campaign, staging_ref, candidate_identity)
        raise


def _reject_pivot(
    campaign: Campaign,
    number: int,
    fingerprint: str,
    prior: int,
    base_sha: str,
    manifest: dict[str, Any],
    *,
    protocol: dict[str, Any],
    divergent: bool,
    expected_ref: str | None,
    lock: CampaignLock,
) -> dict[str, Any]:
    verdict = Verdict("rejected", "simulated")
    report = {
        "iteration": number, "verdict": verdict.to_dict(),
        "rungs": [{"rung": "E0", "status": "fail", "detail": {
            "pivot_rule": f"{prior} prior failed attempts at {fingerprint}; a component-level pivot is required (F16)"}}],
        "attribution": None, "comparison": None, "eligibility": None,
        "admissions": {},
        "run_digests": {},
    }
    ledger_row = {
        "iteration": number, "campaign": campaign.campaign_id, "verdict": verdict.label,
        "decision": "rejected", "evidence_class": "simulated", "advances_accepted_state": False,
        "divergent": divergent, "base_sha": base_sha, "candidate_sha": None,
        "protocol_digest": protocol["protocol_digest"],
        "hypothesis": manifest.get("hypothesis", ""),
        "target_component": manifest.get("target_component", ""),
        "cluster_ref": manifest.get("cluster_ref", ""),
        "gate_rungs": {"E0": "fail"}, "comparison": None,
        "attribution": None, "eligibility": None,
        "fixed_variables": protocol["execution"]["fixed_variables"],
        "promotion_candidates": [],
    }
    learning_record = build_record(
        campaign_root=campaign.store.campaign_dir,
        campaign_id=campaign.campaign_id,
        iteration=number,
        base_sha=base_sha,
        candidate_sha=None,
        protocol_digest=protocol["protocol_digest"],
        verdict=verdict.to_dict(),
        manifest=manifest,
        gate_report=report,
    )
    final_state = _nonadvancing_final_state(
        campaign.state,
        verdict=verdict,
        divergent=divergent,
        fingerprint=fingerprint,
        cleanup_failure=None,
    )
    return _persist_nonadvancing_publication(
        campaign,
        lock=lock,
        iteration=number,
        base_sha=base_sha,
        protocol_digest=protocol["protocol_digest"],
        report=report,
        manifest_snapshot=_trusted_manifest_snapshot(manifest, verdict),
        ledger_row=ledger_row,
        learning_record=learning_record,
        final_state=final_state,
        candidate_sha=None,
        candidate_tree=None,
        staging_ref=None,
        expected_ref=expected_ref,
    )


# ── noise calibration (owner artifact, identity-bound) ─────────────────────
def measure_noise(campaign: Campaign, *, runs: int = 3) -> NoiseBand:
    require_transition(campaign, action="evaluate")
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
