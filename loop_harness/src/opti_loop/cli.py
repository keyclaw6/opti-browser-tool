"""opti-loop CLI — the conductor's operator surface (transactional v2).

    opti-loop [--store-root PATH] init --campaign X [--adapter fixture] [--dev-suite smoke]
    opti-loop measure-noise --campaign X [--runs N]
    opti-loop start --campaign X            # phase A+C: base worktree, baseline, packet
    opti-loop run-iteration --campaign X    # phases E+B+F as ONE transaction
    opti-loop status --campaign X
    opti-loop compare-campaigns --campaigns a,b
    opti-loop transfer-plan --campaign X
    opti-loop transfer-eval --deltas model=0.03,model2=-0.01

The trusted store lives OUTSIDE repo_root (env OPTI_STORE_ROOT or --store-root;
default <repo>/../opti-store). repo_root is discovered from --repo-root,
OPTI_BROWSER_REPO_ROOT, or the current directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
from pathlib import Path

from opti_eval.errors import ConfigurationError
from opti_eval.paths import find_repo_root
from opti_eval.adapters.warc_online4 import (
    WarcOnline4Error,
    load_and_preflight_config,
)

from . import fileguard, gitutil
from .campaign import DEFAULT_CONFIG, init_campaign, load_campaign
from .conductor import (
    compare_campaigns,
    continue_campaign,
    measure_noise,
    run_iteration,
    start_iteration,
)
from .learning import read_records
from .ledger import read_rows
from .operation import (
    operation_config,
    request,
    status as operation_status,
)
from .protocol import ProtocolError, normalize_candidate_allowlist
from .transfer import evaluate_checkpoint, plan_checkpoint


def _repo_root(args) -> Path:
    return find_repo_root(args.repo_root)


def _emit(payload) -> None:
    print(json.dumps(payload, indent=2, default=str))


def _harness_fixture_file(repo_root: Path, value: str) -> str:
    """Validate the one shipped harness-fixture behavior-file seam."""
    if not fileguard.path_is_safe(value):
        raise ValueError("--harness-file must be a safe relative POSIX path")
    try:
        allowlist = tuple(
            normalize_candidate_allowlist(DEFAULT_CONFIG["candidate_allowlist"])
        )
    except ProtocolError as exc:  # static defaults are trusted, but fail closed
        raise ValueError(f"default candidate allowlist is invalid: {exc}") from exc
    if not fileguard.is_allowed(value, allowlist):
        raise ValueError("--harness-file is outside the campaign candidate surface")
    if not fileguard.is_regular_file(repo_root, value):
        raise ValueError("--harness-file must be a regular non-symlink file")
    path = repo_root.joinpath(*value.split("/"))
    try:
        current = path.read_bytes()
    except OSError as exc:
        raise ValueError("--harness-file must be readable") from exc
    try:
        accepted = gitutil.read_blob(repo_root, gitutil.head_sha(repo_root), value)
    except gitutil.GitError as exc:
        raise ValueError(
            "--harness-file must exist in the current accepted harness surface"
        ) from exc
    if current != accepted:
        raise ValueError(
            "--harness-file must match the current accepted harness surface"
        )
    try:
        rate = float(accepted.decode("utf-8").strip())
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError(
            "--harness-file accepted baseline must contain one numeric fixture rate"
        ) from exc
    if not math.isfinite(rate) or not 0.0 <= rate <= 1.0:
        raise ValueError(
            "--harness-file accepted baseline fixture rate must be finite and lie in [0, 1]"
        )
    return value


def _warc_status(campaign) -> dict[str, object]:
    adapter = campaign.config.get("adapter", {})
    if adapter.get("kind") != "warc-online4":
        return {"required": False}
    report: dict[str, object] = {"required": True, "ready": False}
    try:
        checked = load_and_preflight_config(Path(adapter["config_path"]))
    except (KeyError, OSError, ValueError, WarcOnline4Error) as exc:
        report["blocker"] = str(exc)
    else:
        report.update(
            ready=True,
            mode=checked["mode"],
            config_digest=checked["config_digest"],
            lifecycle_executed=False,
        )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="opti-loop", description=__doc__)
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--store-root", default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init")
    p_init.add_argument("--campaign", required=True)
    p_init.add_argument(
        "--adapter", default="fixture",
        choices=["fixture", "harness-fixture", "command", "warc-online4"],
    )
    p_init.add_argument("--pass-rate", type=float, default=0.55)
    p_init.add_argument("--seed", type=int, default=0)
    p_init.add_argument("--harness-file", default=None)
    p_init.add_argument("--bridge-command", default=None)
    p_init.add_argument("--warc-config", default=None)
    p_init.add_argument("--dev-suite", default="smoke")
    p_init.add_argument("--max-iterations", type=int)
    p_init.add_argument("--max-attempts", type=int)
    p_init.add_argument("--deadline-seconds", type=int)
    p_init.add_argument("--external-metering-id")
    p_init.add_argument("--authorize-production-campaign", action="store_true")

    for name in ("start", "status", "preflight", "pause", "stop", "transfer-plan"):
        p = sub.add_parser(name)
        p.add_argument("--campaign", required=True)
    p_run = sub.add_parser("run-iteration")
    p_run.add_argument("--campaign", required=True)
    p_run.add_argument("--candidate-bundle", default=None)
    p_run.add_argument("--candidate-manifest", default=None)
    for name in ("run", "resume"):
        p = sub.add_parser(name)
        p.add_argument("--campaign", required=True)
        p.add_argument("--candidate-bundle", default=None)
        p.add_argument("--candidate-manifest", default=None)

    p_noise = sub.add_parser("measure-noise")
    p_noise.add_argument("--campaign", required=True)
    p_noise.add_argument("--runs", type=int, default=3)

    p_cmp = sub.add_parser("compare-campaigns")
    p_cmp.add_argument("--campaigns", required=True)

    p_teval = sub.add_parser("transfer-eval")
    p_teval.add_argument("--deltas", required=True, help="comma list model=delta")

    p_warc = sub.add_parser(
        "warc-online4-preflight",
        help="Validate WARC online.4 inputs without executing the lifecycle",
    )
    p_warc.add_argument("--config", required=True)

    args = parser.parse_args(argv)
    try:
        repo_root = _repo_root(args)
    except (ConfigurationError, ValueError, OSError) as exc:
        print(f"opti-loop: {exc}", file=sys.stderr)
        return 2
    store_root = args.store_root

    if args.command == "warc-online4-preflight":
        try:
            checked = load_and_preflight_config(Path(args.config))
        except (OSError, ValueError, WarcOnline4Error) as exc:
            print(f"opti-loop: WARC online.4 preflight failed: {exc}", file=sys.stderr)
            return 2
        _emit(
            {
                "ok": True,
                "task_id": "warc-bench-online-4",
                "mode": checked["mode"],
                "benchmark_reportable": False,
                "potential_benchmark_eligibility": checked["mode"] == "production",
                "config_digest": checked["config_digest"],
                "lifecycle_executed": False,
                "credentials": checked["credentials"]["required_env"],
            }
        )
        return 0

    if args.command == "compare-campaigns":
        ids = [c.strip() for c in args.campaigns.split(",") if c.strip()]
        _emit(compare_campaigns(repo_root, ids, store_root=store_root))
        return 0
    if args.command == "transfer-eval":
        deltas = {}
        for pair in args.deltas.split(","):
            if "=" in pair:
                k, v = pair.split("=", 1)
                deltas[k.strip()] = float(v)
        _emit(evaluate_checkpoint(deltas))
        return 0

    if args.command == "init":
        adapter: dict = {"kind": args.adapter}
        if args.adapter == "fixture":
            adapter.update({"pass_rate": args.pass_rate, "seed": args.seed})
        elif args.adapter == "harness-fixture":
            if not args.harness_file:
                print(
                    "error: --harness-file required for the harness-fixture adapter",
                    file=sys.stderr,
                )
                return 2
            try:
                harness_file = _harness_fixture_file(repo_root, args.harness_file)
            except ValueError as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 2
            if not math.isfinite(args.pass_rate) or not 0.0 <= args.pass_rate <= 1.0:
                print(
                    "error: --pass-rate must be finite and lie in [0, 1]",
                    file=sys.stderr,
                )
                return 2
            adapter.update(
                {
                    "file": harness_file,
                    "default_pass_rate": args.pass_rate,
                    "seed": args.seed,
                }
            )
        elif args.adapter == "command":
            if not args.bridge_command:
                print("error: --bridge-command required for the command adapter", file=sys.stderr)
                return 2
            adapter["command"] = args.bridge_command
        elif args.adapter == "warc-online4":
            if not args.warc_config:
                print("error: --warc-config required for warc-online4", file=sys.stderr)
                return 2
            try:
                checked = load_and_preflight_config(Path(args.warc_config))
            except (OSError, ValueError, WarcOnline4Error) as exc:
                print(f"error: WARC online.4 preflight failed: {exc}", file=sys.stderr)
                return 2
            adapter.update(
                {
                    "config_path": str(Path(args.warc_config).resolve()),
                    "treatment_path": checked["treatment_path"],
                    "verifier_id": checked["verifier"]["id"],
                    "verifier_checksum": checked["verifier"]["sha256"],
                }
            )
            protocol_identity = checked["protocol_identity"]
            executor_identity = {
                **checked["executor"],
                "snapshot": checked["executor"]["model"],
                "revision": checked["executor"]["model"],
            }
            identity = {
                "evidence_mode": (
                    "benchmark" if checked["mode"] == "production" else "simulated"
                ),
                "source_runtimes": {"warc_bench": protocol_identity["source_runtime"]},
                "executor": executor_identity,
                "verifier_bundle": {
                    "id": checked["verifier"]["id"],
                    "checksum": checked["verifier"]["sha256"],
                    "bundle_digest": checked["verifier"]["sha256"],
                    "admissions_digest": hashlib.sha256(
                        b"opti.admissions.v1\0"
                        + Path(checked["verifier"]["admissions_path"]).read_bytes()
                    ).hexdigest(),
                },
                "activation_instrumentation": protocol_identity[
                    "activation_instrumentation"
                ],
                "lane": protocol_identity["lane"],
            }
        if any(
            value is None
            for value in (
                args.max_iterations, args.max_attempts, args.deadline_seconds
            )
        ):
            print(
                "error: --max-iterations, --max-attempts, and --deadline-seconds "
                "are required closed campaign limits",
                file=sys.stderr,
            )
            return 2
        try:
            operation = operation_config(
                max_iterations=args.max_iterations,
                max_attempts=args.max_attempts,
                deadline_seconds=args.deadline_seconds,
            )
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        if args.adapter == "warc-online4" and checked["mode"] == "production":
            operation["external_metering"] = (
                f"available:{args.external_metering_id}"
                if args.external_metering_id
                else "unavailable"
            )
            operation["authorization"] = (
                "owner_authorized"
                if args.authorize_production_campaign
                else "required"
            )
        overrides = {
            "adapter": adapter,
            "operation": operation,
            "suites": {
                "dev": args.dev_suite,
                "smoke": (
                    args.dev_suite if args.adapter == "warc-online4" else "smoke"
                ),
                "regression": (
                    args.dev_suite if args.adapter == "warc-online4" else "regression"
                ),
            },
        }
        if args.adapter == "warc-online4":
            overrides.update(
                {
                    "identity": identity,
                    "repeated_protocol": protocol_identity["repeated_protocol"],
                    "fixed_variables": {
                        "executor_model": checked["executor"]["model"],
                        "browser_backend": "warc-browsergym-playwright-qualification",
                        "lane": protocol_identity["lane"]["id"],
                    },
                }
            )
        campaign = init_campaign(
            repo_root, args.campaign, store_root=store_root,
            overrides=overrides,
        )
        if args.adapter == "warc-online4":
            shutil.copyfile(
                checked["verifier"]["admissions_path"], campaign.store.admissions_path
            )
        _emit({"created": str(campaign.store.campaign_dir), "store_outside_repo": True,
               "config": campaign.config})
        return 0

    campaign = load_campaign(repo_root, args.campaign, store_root=store_root)

    if args.command in {"pause", "stop"}:
        try:
            lifecycle = request(campaign, args.command)
        except (RuntimeError, ValueError) as exc:
            print(f"opti-loop: {exc}", file=sys.stderr)
            return 2
        _emit({"campaign": campaign.campaign_id, "lifecycle": lifecycle})
        return 0

    if args.command in {"run", "resume"}:
        try:
            request(campaign, "run", resume=args.command == "resume")
            result = continue_campaign(
                campaign,
                candidate_bundle=(
                    Path(args.candidate_bundle) if args.candidate_bundle else None
                ),
                candidate_manifest=(
                    Path(args.candidate_manifest) if args.candidate_manifest else None
                ),
            )
        except (RuntimeError, ValueError, OSError) as exc:
            print(f"opti-loop: {exc}", file=sys.stderr)
            return 2
        _emit(result)
        return 0

    if args.command == "preflight":
        report = operation_status(campaign)
        warc = _warc_status(campaign)
        report["warc_online4"] = warc
        report["ok"] = not report["blockers"] and not (
            warc.get("required") and not warc.get("ready")
        )
        _emit(report)
        return 0 if report["ok"] else 1

    if args.command == "measure-noise":
        _emit({"noise_band": measure_noise(campaign, runs=args.runs).to_dict()})
        return 0
    if args.command == "start":
        try:
            _emit(start_iteration(campaign))
        except (RuntimeError, ValueError, OSError) as exc:
            print(f"opti-loop: {exc}", file=sys.stderr)
            return 2
        return 0
    if args.command == "run-iteration":
        try:
            result = run_iteration(
                campaign,
                candidate_bundle=(Path(args.candidate_bundle) if args.candidate_bundle else None),
                candidate_manifest=(
                    Path(args.candidate_manifest) if args.candidate_manifest else None
                ),
            )
        except (RuntimeError, ValueError, OSError) as exc:
            print(f"opti-loop: {exc}", file=sys.stderr)
            return 2
        _emit(result)
        return 0 if result.get("advanced_accepted_state") else 1
    if args.command == "transfer-plan":
        _emit(plan_checkpoint(campaign).to_dict())
        return 0
    if args.command == "status":
        operation = operation_status(campaign)
        try:
            rows = read_rows(campaign.ledger_path)
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            ledger_summary = {}
            operation["blockers"].append(
                f"ledger: {exc}; repair the retained campaign ledger"
            )
        else:
            ledger_summary = {
                "ledger_rows": len(rows),
                "last": [
                    {"iteration": row["iteration"], "verdict": row["verdict"]}
                    for row in rows[-5:]
                ],
            }
        try:
            records = read_records(
                campaign.learnings_path,
                campaign_root=campaign.store.campaign_dir,
            )
            latest_learning = records[-1] if records else None
        except ValueError as exc:
            latest_learning = {"invalid": str(exc)}
            operation["blockers"].append(f"learning: {exc}")
        _emit({
            "campaign": campaign.campaign_id,
            "store": str(campaign.store.campaign_dir),
            "accepted_base_sha": campaign.state.get("accepted_base_sha"),
            "current_iteration": campaign.current_iteration,
            "pending_iteration": campaign.state.get("pending_iteration", 0),
            "accepted_iterations": campaign.state.get("accepted_iterations", []),
            "noise_band": campaign.config.get("noise_band"),
            "operation": operation,
            "warc_online4": _warc_status(campaign),
            "latest_learning_record": latest_learning,
            **ledger_summary,
        })
        return 0
    parser.error(f"unknown command {args.command}")
    return 2
