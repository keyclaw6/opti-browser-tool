"""The Conductor: transactional phase driver over a trusted boundary.

Rewritten after the review. The iteration boundary is now owner-controlled:

- ``start`` captures the trusted ``accepted_base_sha``, creates an isolated
  candidate **worktree** at that base (the optimizer's only writable surface),
  runs the baseline + regression baseline there, distills, and writes the
  packet — all into the owner-only trusted store.
- the optimizer edits ``harness/components/**`` in the worktree, commits once,
  and drops a ``manifest.json`` in the worktree root.
- ``run_iteration`` is a SINGLE atomic transaction (F02, F06): it ingests and
  validates the manifest, runs the E0–E5 ladder over the ``base..candidate``
  commit diff, appends attribution, writes the gate report + ledger row to the
  trusted store, advances accepted state ONLY on ``(accepted, benchmark)``, and
  resets the worktree either way. There is no separate, forgeable record step.

Regression memory is seeded from the accepted-base run at ``start`` and is
never refreshed from a rejected treatment (F06).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from . import fileguard, gitutil
from .analyst import StubAnalyst
from .campaign import Campaign
from .clusters import load_register, ranked_unresolved, save_register, update_after_iteration
from .compare import NoiseBand, NoiseBandError, measure_noise_band
from .eligibility import assess
from .evaluate import EvalRun, load_run, run_suite
from .gates import GateReport, run_gate
from .ledger import learnings_template
from .manifest import load_and_validate, rejected_submission_record
from .packet import build_packet
from .store import append_jsonl, atomic_write_json, atomic_write_text
from .verdict import Verdict

DEV_BASELINE_DIR = "eval/dev_baseline"
ACCEPTED_REF = "refs/opti/{campaign}/accepted"


# ── helpers ───────────────────────────────────────────────────────────────
def _catalog(repo_root: Path) -> dict[str, dict[str, Any]]:
    path = repo_root / "evals/catalog/tasks.jsonl"
    records: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            records[str(row["id"])] = row
    return records


def _task_sources(records: dict[str, dict[str, Any]]) -> dict[str, str]:
    return {tid: str(rec.get("source", "unknown")) for tid, rec in records.items()}


def _run_identity(campaign: Campaign, worktree: Path) -> str:
    """Bind a run to catalog + suite + adapter + fixed variables (F07)."""
    catalog_bytes = (worktree / "evals/catalog/tasks.jsonl").read_bytes()
    payload = {
        "dev_suite": campaign.config["suites"]["dev"],
        "smoke": campaign.config["suites"]["smoke"],
        "regression": campaign.config["suites"]["regression"],
        "adapter": campaign.config["adapter"],
        "fixed_variables": campaign.config["fixed_variables"],
        "catalog_sha256": hashlib.sha256(catalog_bytes).hexdigest(),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _pending_quarantine(campaign: Campaign) -> set[str]:
    path = campaign.store.quarantine_path
    ids: set[str] = set()
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                entry = json.loads(line)
                if entry.get("status") == "pending":
                    ids.add(str(entry.get("task_id")))
    return ids


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

    base_sha = str(campaign.state["accepted_base_sha"])
    worktree = campaign.worktree_path
    gitutil.worktree_add(campaign.repo_root, worktree, base_sha)

    records = _catalog(worktree)
    sources = _task_sources(records)
    number = campaign.open_iteration()
    iteration_dir = campaign.iteration_dir(number)

    # A — EVALUATE baseline on the accepted-base harness.
    baseline = run_suite(repo_root=worktree, suite_name=campaign.config["suites"]["dev"],
                         adapter_config=campaign.config["adapter"], output_dir=iteration_dir / DEV_BASELINE_DIR)

    # Seed regression memory from the accepted base (frozen; never a rejected
    # treatment) so E4 has a real previously-passing denominator (F06).
    regression_base = run_suite(repo_root=worktree, suite_name=campaign.config["suites"]["regression"],
                                adapter_config=campaign.config["adapter"],
                                output_dir=iteration_dir / "eval" / "regression_baseline")
    campaign.state["regression_last_results"] = dict(regression_base.statuses)

    # Drift vs the previous accepted treatment.
    drift = None
    prev = campaign.state.get("last_accepted_treatment_dir")
    if prev and Path(prev).is_dir():
        previous = load_run(Path(prev), campaign.config["suites"]["dev"])
        changed = sorted(t for t in baseline.statuses
                         if baseline.statuses.get(t) != previous.statuses.get(t))
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
    quota = int(campaign.config["exploration"].get("divergence_quota", 5))
    force_after = int(campaign.config["exploration"].get("plateau_force_after", 4))
    since_div = int(campaign.state.get("iterations_since_divergent", 0))
    since_acc = int(campaign.state.get("iterations_since_accept", 0))
    divergent = (quota > 0 and since_div + 1 >= quota) or (force_after > 0 and since_acc >= force_after)

    build_packet(iteration_dir=iteration_dir, iteration=number, campaign_id=campaign.campaign_id,
                 divergent=divergent, ranked_clusters=ranked_unresolved(register),
                 ledger_path=campaign.ledger_path, baseline_summary=baseline.summary)

    campaign.state["pending_iteration"] = number
    campaign.state["pending_divergent"] = divergent
    campaign.state["pending_base_sha"] = base_sha
    campaign.save_state()

    result: dict[str, Any] = {
        "iteration": number,
        "divergent": divergent,
        "baseline_success": baseline.summary.get("strict_success_rate"),
        "worktree": str(worktree),
        "instructions": (
            f"edit harness/components/** in {worktree}, commit exactly one candidate "
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
    worktree = campaign.worktree_path
    base_sha = str(campaign.state["pending_base_sha"])
    divergent = bool(campaign.state.get("pending_divergent", False))

    records = _catalog(worktree)
    sources = _task_sources(records)
    baseline = load_run(iteration_dir / DEV_BASELINE_DIR, campaign.config["suites"]["dev"])

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
                                      base_sha=base_sha, candidate_sha=candidate_sha)
    manifest_report = load_and_validate(wt_manifest,
                                        changed_files=guard.changed, divergent=divergent)

    # Pivot enforcement (F16): forbid a 3rd attempt at the same cluster+component.
    pivot_after = int(campaign.config["exploration"].get("pivot_after_failures", 2))
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
    try:
        if campaign.config.get("noise_band"):
            band = NoiseBand.from_dict(campaign.config["noise_band"])
    except NoiseBandError:
        band = None
    run_identity = _run_identity(campaign, worktree)

    report: GateReport = run_gate(
        repo_root=campaign.repo_root, worktree=worktree, base_sha=base_sha, candidate_sha=candidate_sha,
        iteration=number, eval_root=iteration_dir / "eval", baseline_dev=baseline,
        manifest=manifest, manifest_report=manifest_report,
        adapter_config=campaign.config["adapter"], suites=campaign.config["suites"],
        thresholds=campaign.config["thresholds"], noise_band=band, run_identity=run_identity,
        task_sources=sources, task_records=records,
        regression_last_results=campaign.state.get("regression_last_results", {}),
        quarantined_task_ids=_pending_quarantine(campaign),
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
        "base_sha": base_sha, "candidate_sha": candidate_sha, "run_identity": run_identity,
        "hypothesis": manifest.get("hypothesis", ""), "target_component": manifest.get("target_component", ""),
        "cluster_ref": manifest.get("cluster_ref", ""),
        "gate_rungs": {r.rung: r.status for r in report.rungs},
        "comparison": report.comparison, "attribution": report.attribution,
        "eligibility": report.eligibility, "fixed_variables": campaign.config.get("fixed_variables"),
        "promotion_candidates": promotion_candidates,
    })
    _append_learnings(campaign, number, verdict, manifest, divergent)

    # State transition + regression memory discipline (F06).
    if verdict.advances_accepted_state:
        gitutil.update_ref(campaign.repo_root, ACCEPTED_REF.format(campaign=campaign.campaign_id), candidate_sha)
        campaign.state["accepted_base_sha"] = candidate_sha
        campaign.state.setdefault("accepted_iterations", []).append(number)
        campaign.state["iterations_since_accept"] = 0
        campaign.state["last_accepted_treatment_dir"] = str(iteration_dir / "eval" / "dev_treatment")
        # Refresh regression memory ONLY from the accepted treatment.
        acc_reg = iteration_dir / "eval" / "regression_treatment"
        if acc_reg.is_dir():
            campaign.state["regression_last_results"] = dict(
                load_run(acc_reg, campaign.config["suites"]["regression"]).statuses
            )
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
        run_identity = _run_identity(campaign, worktree)
        eval_runs: list[EvalRun] = []
        for index in range(runs):
            eval_runs.append(run_suite(repo_root=worktree, suite_name=campaign.config["suites"]["dev"],
                                       adapter_config=campaign.config["adapter"],
                                       output_dir=campaign.store.campaign_dir / "noise" / f"run-{index:02d}"))
        synthetic = any(not r.acceptance_decision_eligible for r in eval_runs)
        band = measure_noise_band(eval_runs, synthetic=synthetic, run_identity=run_identity)
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
    for campaign_id in campaign_ids:
        campaign = load_campaign(repo_root, campaign_id, store_root=store_root)
        suite = campaign.config["suites"]["dev"]
        executor = str(campaign.config.get("fixed_variables", {}).get("executor_model"))
        adapter = json.dumps(campaign.config.get("adapter"), sort_keys=True)
        # Full run-identity tuple, not just suite+executor strings (F15).
        identity = hashlib.sha256(
            json.dumps({"suite": suite, "executor": executor, "adapter": adapter,
                        "fixed": campaign.config.get("fixed_variables")}, sort_keys=True).encode()
        ).hexdigest()
        identities.add(identity)
        run_dir = campaign.state.get("last_accepted_treatment_dir")
        rows.append({
            "campaign": campaign_id, "suite": suite, "executor": executor,
            "identity": identity, "iterations": campaign.current_iteration,
            "accepted_iterations": campaign.state.get("accepted_iterations", []),
            "strict_success_rate": (
                load_run(Path(run_dir), suite).summary.get("strict_success_rate")
                if run_dir and Path(run_dir).is_dir() else None
            ),
        })
    comparable = len(identities) == 1
    report = {
        "schema_version": "0.2-draft", "comparable": comparable,
        "non_comparable_reason": None if comparable else
            "campaigns differ in the full run-identity tuple (suite/executor/adapter/fixed vars); "
            "cross-campaign scores must not be ranked (ADR-0001, F15)",
        "campaigns": rows,
        "note": "transplanting a winning mechanism is a manifested change through the receiving campaign's gate",
    }
    return report
