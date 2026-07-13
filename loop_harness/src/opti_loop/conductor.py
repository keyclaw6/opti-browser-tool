"""The Conductor: deterministic phase driver for one iteration (A–F).

Sequence per ADR-0015 §3, adapted to a synchronous gate:

- ``start``  → A EVALUATE (dev baseline) + drift check + C DISTILL (Analyst)
               + exploration decision + iteration packet for the optimizer.
- (external) → D EVOLVE: the coding agent edits one component and writes
               ``manifest.json`` (this package never edits the harness).
- ``gate``   → E GATE (E0–E5) + B ATTRIBUTE (synchronous: the treatment
               evaluation happens inside the gate, so predictions are
               falsified in the same iteration).
- ``record`` → F RECORD: ledger row, learnings template, cluster-register
               update, regression promotion *candidates* (auto-promotion
               stays off pending ADR-0009), state advance.
- ``rollback`` → file-granular git revert of the manifest's change scope;
               rollback is itself recorded.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from . import fileguard
from .analyst import StubAnalyst
from .campaign import Campaign
from .clusters import load_register, ranked_unresolved, save_register, update_after_iteration
from .compare import NoiseBand, measure_noise_band
from .evaluate import EvalRun, load_run, run_suite
from .gates import GateReport, run_gate
from .ledger import append_learnings, append_row, learnings_template
from .packet import build_packet

DEV_BASELINE_DIR = "eval/dev_baseline"


def _task_sources(repo_root: Path) -> dict[str, str]:
    catalog = repo_root / "evals/catalog/tasks.jsonl"
    sources: dict[str, str] = {}
    for line in catalog.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        sources[str(row["id"])] = str(row.get("source", "unknown"))
    return sources


def _guard_baseline(campaign: Campaign) -> set[str]:
    return set(campaign.state.get("guard_baseline_paths", []))


def snapshot_guard_baseline(campaign: Campaign) -> None:
    """Record pre-existing dirty paths so the guard judges only new edits."""
    changed = fileguard.changed_paths(campaign.repo_root)
    campaign.state["guard_baseline_paths"] = changed
    campaign.save_state()


def start_iteration(campaign: Campaign) -> dict[str, Any]:
    # Learnings discipline: warn when the previous entry was never completed.
    learnings_incomplete = False
    if campaign.learnings_path.is_file():
        text = campaign.learnings_path.read_text(encoding="utf-8")
        last_entry = text.split("## Iteration")[-1] if "## Iteration" in text else ""
        learnings_incomplete = "<fill in" in last_entry

    number = campaign.open_iteration()
    iteration_dir = campaign.iteration_dir(number)
    sources = _task_sources(campaign.repo_root)

    # A — EVALUATE (dev baseline for this iteration).
    baseline = run_suite(
        repo_root=campaign.repo_root,
        suite_name=campaign.config["suites"]["dev"],
        adapter_config=campaign.config["adapter"],
        output_dir=iteration_dir / DEV_BASELINE_DIR,
    )

    # Persistence/drift check against the previous accepted treatment.
    drift: dict[str, Any] | None = None
    prev_treatment = campaign.state.get("last_accepted_treatment_dir")
    if prev_treatment and Path(prev_treatment).is_dir():
        previous = load_run(Path(prev_treatment), campaign.config["suites"]["dev"])
        changed = sorted(
            tid
            for tid in baseline.statuses
            if baseline.statuses.get(tid) != previous.statuses.get(tid)
        )
        drift = {"tasks_changed_since_accepted_treatment": changed}
        (iteration_dir / "drift.json").write_text(
            json.dumps(drift, indent=2) + "\n", encoding="utf-8"
        )

    # C — DISTILL (Analyst; stub until traces exist).
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
    save_register(campaign.clusters_path, register)

    # Exploration decision (ADR-0015 §9).
    quota = int(campaign.config["exploration"].get("divergence_quota", 5))
    force_after = int(campaign.config["exploration"].get("plateau_force_after", 4))
    since_divergent = int(campaign.state.get("iterations_since_divergent", 0))
    since_accept = int(campaign.state.get("iterations_since_accept", 0))
    divergent = (quota > 0 and since_divergent + 1 >= quota) or (
        force_after > 0 and since_accept >= force_after
    )

    build_packet(
        iteration_dir=iteration_dir,
        iteration=number,
        campaign_id=campaign.campaign_id,
        divergent=divergent,
        ranked_clusters=ranked_unresolved(register),
        ledger_path=campaign.ledger_path,
        baseline_summary=baseline.summary,
    )

    campaign.state["pending_iteration"] = number
    campaign.state["pending_divergent"] = divergent
    campaign.save_state()
    result: dict[str, Any] = {
        "iteration": number,
        "divergent": divergent,
        "baseline_success": baseline.summary.get("strict_success_rate"),
        "packet": str(iteration_dir / "PACKET.md"),
        "drift": drift,
    }
    if learnings_incomplete:
        result["warning"] = (
            "previous learnings entry still contains '<fill in' placeholders — "
            "complete it before proposing a new hypothesis (PROGRAM.md §6)"
        )
    return result


def gate_iteration(campaign: Campaign) -> GateReport:
    number = int(campaign.state.get("pending_iteration") or 0)
    if not number:
        raise RuntimeError("no pending iteration — run `opti-loop start` first")
    iteration_dir = campaign.iteration_dir(number)
    baseline = load_run(iteration_dir / DEV_BASELINE_DIR, campaign.config["suites"]["dev"])

    band_payload = campaign.config.get("noise_band")
    band = NoiseBand.from_dict(band_payload) if band_payload else None

    # Pending evaluation-plane quarantine (ADR-0016 T3): fail closed under
    # the strict validity policy when a compared task is quarantined.
    quarantined: set[str] = set()
    queue_rel = campaign.config.get("quarantine_file", "runs/quarantine/queue.jsonl")
    queue_path = campaign.repo_root / queue_rel
    if queue_path.is_file():
        for line in queue_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            if entry.get("status") == "pending":
                quarantined.add(str(entry.get("task_id")))

    report = run_gate(
        repo_root=campaign.repo_root,
        iteration=number,
        iteration_dir=iteration_dir,
        baseline_dev=baseline,
        manifest_path=iteration_dir / "manifest.json",
        adapter_config=campaign.config["adapter"],
        suites=campaign.config["suites"],
        thresholds=campaign.config["thresholds"],
        noise_band=band,
        task_sources=_task_sources(campaign.repo_root),
        regression_last_results=campaign.state.get("regression_last_results", {}),
        guard_baseline_paths=_guard_baseline(campaign),
        quarantined_task_ids=quarantined,
    )
    report.save(iteration_dir / "gate-report.json")

    # Append attribution into the manifest record (conductor-owned field).
    manifest_path = iteration_dir / "manifest.json"
    if report.attribution and manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["attribution"] = report.attribution
        manifest["status"] = (
            "accepted" if report.verdict.endswith("accepted") else "rejected"
        )
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return report


def record_iteration(campaign: Campaign) -> dict[str, Any]:
    number = int(campaign.state.get("pending_iteration") or 0)
    if not number:
        raise RuntimeError("no pending iteration to record")
    iteration_dir = campaign.iteration_dir(number)
    gate_path = iteration_dir / "gate-report.json"
    if not gate_path.is_file():
        raise RuntimeError("no gate report — run `opti-loop gate` first")
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    manifest_path = iteration_dir / "manifest.json"
    manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest_path.is_file()
        else {}
    )
    verdict: str = gate["verdict"]
    divergent = bool(campaign.state.get("pending_divergent", False))
    accepted = verdict.endswith("accepted")

    # Cluster register: fold in verified fixes on acceptance.
    fixed: set[str] = set()
    if accepted and gate.get("comparison"):
        fixed = set(gate["comparison"].get("fixed", []))
        register = load_register(campaign.clusters_path)
        register = update_after_iteration(
            register,
            iteration=number,
            failed_by_cluster={},
            fixed_task_ids=fixed,
            analyst_version="conductor-record",
        )
        save_register(campaign.clusters_path, register)

    # Regression promotion candidates (ADR-0009: proposal, not auto-promotion).
    promotion_candidates = sorted(fixed) if accepted else []

    # Update regression last_results memory from this iteration's E4 run.
    regression_dir = iteration_dir / "eval" / "regression_treatment"
    if regression_dir.is_dir():
        regression = load_run(regression_dir, campaign.config["suites"]["regression"])
        campaign.state["regression_last_results"] = dict(regression.statuses)

    row = {
        "iteration": number,
        "campaign": campaign.campaign_id,
        "verdict": verdict,
        "divergent": divergent,
        "hypothesis": manifest.get("hypothesis", ""),
        "target_component": manifest.get("target_component", ""),
        "cluster_ref": manifest.get("cluster_ref", ""),
        "gate_rungs": {r["rung"]: r["status"] for r in gate.get("rungs", [])},
        "comparison": gate.get("comparison"),
        "attribution": gate.get("attribution"),
        "fixed_variables": campaign.config.get("fixed_variables"),
        "promotion_candidates": promotion_candidates,
    }
    append_row(campaign.ledger_path, row)
    append_learnings(
        campaign.learnings_path,
        learnings_template(
            iteration=number,
            verdict=verdict,
            hypothesis=manifest.get("hypothesis", "<no manifest>"),
            target_component=manifest.get("target_component", "?"),
            cluster_ref=manifest.get("cluster_ref", "?"),
            divergent=divergent,
        ),
    )

    # State advance.
    if accepted:
        campaign.state["iterations_since_accept"] = 0
        campaign.state.setdefault("accepted_iterations", []).append(number)
        campaign.state["last_accepted_treatment_dir"] = str(
            iteration_dir / "eval" / "dev_treatment"
        )
    else:
        campaign.state["iterations_since_accept"] = (
            int(campaign.state.get("iterations_since_accept", 0)) + 1
        )
    campaign.state["iterations_since_divergent"] = (
        0 if divergent else int(campaign.state.get("iterations_since_divergent", 0)) + 1
    )
    campaign.state["pending_iteration"] = 0
    campaign.state["pending_divergent"] = False
    campaign.save_state()
    return {"iteration": number, "verdict": verdict, "promotion_candidates": promotion_candidates}


def rollback_iteration(campaign: Campaign) -> dict[str, Any]:
    """File-granular revert of the pending manifest's change scope."""
    number = int(campaign.state.get("pending_iteration") or 0)
    if not number:
        raise RuntimeError("no pending iteration to roll back")
    iteration_dir = campaign.iteration_dir(number)
    manifest_path = iteration_dir / "manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError("no manifest.json — nothing to roll back")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    scope = [str(p) for p in manifest.get("treatment", {}).get("change_scope", [])]
    reverted: list[str] = []
    for path in scope:
        if not fileguard.is_allowed(path):
            continue
        subprocess.run(
            ["git", "-C", str(campaign.repo_root), "checkout", "--", path],
            check=False,
            capture_output=True,
        )
        full = campaign.repo_root / path
        tracked = (
            subprocess.run(
                ["git", "-C", str(campaign.repo_root), "ls-files", "--error-unmatch", path],
                capture_output=True,
            ).returncode
            == 0
        )
        if not tracked and full.exists():
            full.unlink()  # new untracked file introduced by this change
        reverted.append(path)
    rollback_record = {
        "iteration": number,
        "action": "rollback",
        "reverted_paths": reverted,
        "note": "rollback is itself a manifested change (ADR-0015 §4)",
    }
    (iteration_dir / "rollback.json").write_text(
        json.dumps(rollback_record, indent=2) + "\n", encoding="utf-8"
    )
    return rollback_record


def compare_campaigns(repo_root: Path, campaign_ids: list[str]) -> dict[str, Any]:
    """Scheduled cross-campaign report (ADR-0015 §9) — never a per-iteration race.

    Compares each campaign's latest accepted treatment (falling back to its
    latest baseline) on identical suite + executor configuration. Campaigns
    with differing dev suites or executor pins are reported as non-comparable
    (ADR-0001: no cross-model attribution).
    """
    from .campaign import load_campaign  # local import to avoid cycles

    rows: list[dict[str, Any]] = []
    reference: dict[str, str] = {}
    for campaign_id in campaign_ids:
        campaign = load_campaign(repo_root, campaign_id)
        suite = campaign.config["suites"]["dev"]
        executor = str(campaign.config.get("fixed_variables", {}).get("executor_model"))
        run_dir = campaign.state.get("last_accepted_treatment_dir")
        source = "latest_accepted_treatment"
        if not run_dir or not Path(run_dir).is_dir():
            pending = int(campaign.state.get("pending_iteration") or campaign.current_iteration)
            candidate = campaign.iteration_dir(pending) / DEV_BASELINE_DIR
            run_dir = str(candidate) if candidate.is_dir() else None
            source = "latest_baseline"
        row: dict[str, Any] = {
            "campaign": campaign_id,
            "suite": suite,
            "executor": executor,
            "iterations": campaign.current_iteration,
            "accepted_iterations": campaign.state.get("accepted_iterations", []),
            "run_source": source,
        }
        if run_dir:
            run = load_run(Path(run_dir), suite)
            row["strict_success_rate"] = run.summary.get("strict_success_rate")
            row["simulated"] = not run.acceptance_decision_eligible
            row["passed_task_ids"] = sorted(run.passed_ids)
        else:
            row["strict_success_rate"] = None
            row["note"] = "no evaluation runs yet"
        rows.append(row)
        reference.setdefault("suite", suite)
        reference.setdefault("executor", executor)

    comparable = all(
        r["suite"] == reference.get("suite") and r["executor"] == reference.get("executor")
        for r in rows
    )
    report = {
        "schema_version": "0.1-draft",
        "comparable": comparable,
        "non_comparable_reason": (
            None
            if comparable
            else "campaigns differ in dev suite or executor pin — cross-campaign scores must not be ranked (ADR-0001)"
        ),
        "campaigns": rows,
        "note": "scheduled report; transplanting a winning mechanism is a manifested change through the receiving campaign's gate",
    }
    out = repo_root / "campaigns" / "cross-campaign-report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def measure_noise(campaign: Campaign, *, runs: int = 3) -> NoiseBand:
    """Repeated identical-configuration baseline runs → noise band."""
    out_root = campaign.root / "noise"
    eval_runs: list[EvalRun] = []
    for index in range(runs):
        eval_runs.append(
            run_suite(
                repo_root=campaign.repo_root,
                suite_name=campaign.config["suites"]["dev"],
                adapter_config=campaign.config["adapter"],
                output_dir=out_root / f"run-{index:02d}",
            )
        )
    synthetic = any(not run.acceptance_decision_eligible for run in eval_runs)
    band = measure_noise_band(eval_runs, synthetic=synthetic)
    campaign.config["noise_band"] = band.to_dict()
    campaign.state["noise_band_measured"] = True
    campaign.save_config()
    campaign.save_state()
    return band
