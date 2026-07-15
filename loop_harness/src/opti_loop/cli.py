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
import json
import sys
from pathlib import Path

from opti_eval.errors import ConfigurationError
from opti_eval.paths import find_repo_root

from .campaign import init_campaign, load_campaign
from .conductor import compare_campaigns, measure_noise, run_iteration, start_iteration
from .transfer import evaluate_checkpoint, plan_checkpoint


def _repo_root(args) -> Path:
    return find_repo_root(args.repo_root)


def _emit(payload) -> None:
    print(json.dumps(payload, indent=2, default=str))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="opti-loop", description=__doc__)
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--store-root", default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init")
    p_init.add_argument("--campaign", required=True)
    p_init.add_argument("--adapter", default="fixture", choices=["fixture", "harness-fixture", "command"])
    p_init.add_argument("--pass-rate", type=float, default=0.55)
    p_init.add_argument("--seed", type=int, default=0)
    p_init.add_argument("--bridge-command", default=None)
    p_init.add_argument("--dev-suite", default="smoke")

    for name in ("start", "run-iteration", "status", "transfer-plan"):
        p = sub.add_parser(name)
        p.add_argument("--campaign", required=True)

    p_noise = sub.add_parser("measure-noise")
    p_noise.add_argument("--campaign", required=True)
    p_noise.add_argument("--runs", type=int, default=3)

    p_cmp = sub.add_parser("compare-campaigns")
    p_cmp.add_argument("--campaigns", required=True)

    p_teval = sub.add_parser("transfer-eval")
    p_teval.add_argument("--deltas", required=True, help="comma list model=delta")

    args = parser.parse_args(argv)
    try:
        repo_root = _repo_root(args)
    except (ConfigurationError, ValueError, OSError) as exc:
        print(f"opti-loop: {exc}", file=sys.stderr)
        return 2
    store_root = args.store_root

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
        elif args.adapter == "command":
            if not args.bridge_command:
                print("error: --bridge-command required for the command adapter", file=sys.stderr)
                return 2
            adapter["command"] = args.bridge_command
        campaign = init_campaign(
            repo_root, args.campaign, store_root=store_root,
            overrides={"adapter": adapter,
                       "suites": {"dev": args.dev_suite, "smoke": "smoke", "regression": "regression"}},
        )
        _emit({"created": str(campaign.store.campaign_dir), "store_outside_repo": True,
               "config": campaign.config})
        return 0

    campaign = load_campaign(repo_root, args.campaign, store_root=store_root)

    if args.command == "measure-noise":
        _emit({"noise_band": measure_noise(campaign, runs=args.runs).to_dict()})
        return 0
    if args.command == "start":
        _emit(start_iteration(campaign))
        return 0
    if args.command == "run-iteration":
        result = run_iteration(campaign)
        _emit(result)
        return 0 if result.get("advanced_accepted_state") else 1
    if args.command == "transfer-plan":
        _emit(plan_checkpoint(campaign).to_dict())
        return 0
    if args.command == "status":
        rows = []
        if campaign.ledger_path.is_file():
            rows = [json.loads(x) for x in campaign.ledger_path.read_text().splitlines() if x.strip()]
        _emit({
            "campaign": campaign.campaign_id,
            "store": str(campaign.store.campaign_dir),
            "accepted_base_sha": campaign.state.get("accepted_base_sha"),
            "current_iteration": campaign.current_iteration,
            "pending_iteration": campaign.state.get("pending_iteration", 0),
            "accepted_iterations": campaign.state.get("accepted_iterations", []),
            "noise_band": campaign.config.get("noise_band"),
            "ledger_rows": len(rows),
            "last": [{"iteration": r.get("iteration"), "verdict": r.get("verdict")} for r in rows[-5:]],
        })
        return 0
    parser.error(f"unknown command {args.command}")
    return 2
