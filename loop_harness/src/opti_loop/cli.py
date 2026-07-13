"""opti-loop CLI — the conductor's operator surface.

Commands mirror the loop phases (ADR-0015 §3):

    opti-loop init --campaign <id> [--adapter fixture] [--seed N] [--pass-rate X]
    opti-loop snapshot-guard --campaign <id>
    opti-loop measure-noise --campaign <id> [--runs N]
    opti-loop start --campaign <id>          # A + C + packet
    opti-loop gate --campaign <id>           # E0–E5 + attribution
    opti-loop record --campaign <id>         # F
    opti-loop rollback --campaign <id>       # file-granular revert
    opti-loop status --campaign <id>

Environment: OPTI_BROWSER_REPO_ROOT (or --repo-root) must point at the
repository root, exactly like opti-eval.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .campaign import init_campaign, load_campaign
from .conductor import (
    compare_campaigns,
    gate_iteration,
    measure_noise,
    record_iteration,
    rollback_iteration,
    snapshot_guard_baseline,
    start_iteration,
)
from .ledger import read_rows


def _repo_root(args: argparse.Namespace) -> Path:
    raw = args.repo_root or os.environ.get("OPTI_BROWSER_REPO_ROOT")
    if not raw:
        print("error: set --repo-root or OPTI_BROWSER_REPO_ROOT", file=sys.stderr)
        raise SystemExit(2)
    return Path(raw).resolve()


def _emit(payload) -> None:
    print(json.dumps(payload, indent=2, default=str))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="opti-loop", description=__doc__)
    parser.add_argument("--repo-root", default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="create a campaign")
    p_init.add_argument("--campaign", required=True)
    p_init.add_argument("--adapter", default="fixture", choices=["fixture", "command"])
    p_init.add_argument("--pass-rate", type=float, default=0.55)
    p_init.add_argument("--seed", type=int, default=0)
    p_init.add_argument("--bridge-command", default=None, help="bridge command for the command adapter")
    p_init.add_argument("--dev-suite", default="smoke",
                        help="suite for the development evaluation (default: smoke until "
                        "the primary suite is calibrated)")

    for name in ("snapshot-guard", "start", "gate", "record", "rollback", "status"):
        p = sub.add_parser(name)
        p.add_argument("--campaign", required=True)

    p_noise = sub.add_parser("measure-noise")
    p_noise.add_argument("--campaign", required=True)
    p_noise.add_argument("--runs", type=int, default=3)

    p_cmp = sub.add_parser("compare-campaigns", help="scheduled cross-campaign report")
    p_cmp.add_argument("--campaigns", required=True, help="comma-separated campaign ids")

    args = parser.parse_args(argv)
    repo_root = _repo_root(args)

    if args.command == "compare-campaigns":
        _emit(compare_campaigns(repo_root, [c.strip() for c in args.campaigns.split(",") if c.strip()]))
        return 0

    if args.command == "init":
        adapter: dict = {"kind": args.adapter}
        if args.adapter == "fixture":
            adapter.update({"pass_rate": args.pass_rate, "seed": args.seed})
        elif args.adapter == "command":
            if not args.bridge_command:
                print("error: --bridge-command is required for the command adapter", file=sys.stderr)
                return 2
            adapter["command"] = args.bridge_command
        campaign = init_campaign(
            repo_root,
            args.campaign,
            overrides={
                "adapter": adapter,
                "suites": {"dev": args.dev_suite, "smoke": "smoke", "regression": "regression"},
            },
        )
        snapshot_guard_baseline(campaign)
        _emit({"created": str(campaign.root), "config": campaign.config})
        return 0

    campaign = load_campaign(repo_root, args.campaign)

    if args.command == "snapshot-guard":
        snapshot_guard_baseline(campaign)
        _emit({"guard_baseline_paths": campaign.state["guard_baseline_paths"]})
        return 0
    if args.command == "measure-noise":
        band = measure_noise(campaign, runs=args.runs)
        _emit({"noise_band": band.to_dict()})
        return 0
    if args.command == "start":
        _emit(start_iteration(campaign))
        return 0
    if args.command == "gate":
        report = gate_iteration(campaign)
        _emit(report.to_dict())
        return 0 if report.verdict.endswith("accepted") else 1
    if args.command == "record":
        _emit(record_iteration(campaign))
        return 0
    if args.command == "rollback":
        _emit(rollback_iteration(campaign))
        return 0
    if args.command == "status":
        rows = read_rows(campaign.ledger_path)
        _emit(
            {
                "campaign": campaign.campaign_id,
                "current_iteration": campaign.current_iteration,
                "pending_iteration": campaign.state.get("pending_iteration", 0),
                "accepted_iterations": campaign.state.get("accepted_iterations", []),
                "iterations_since_accept": campaign.state.get("iterations_since_accept"),
                "noise_band": campaign.config.get("noise_band"),
                "ledger_rows": len(rows),
                "last_verdicts": [
                    {"iteration": r.get("iteration"), "verdict": r.get("verdict")}
                    for r in rows[-5:]
                ],
            }
        )
        return 0
    parser.error(f"unknown command {args.command}")
    return 2
