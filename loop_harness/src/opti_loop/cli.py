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
import math
import sys
from pathlib import Path

from opti_eval.errors import ConfigurationError
from opti_eval.paths import find_repo_root

from . import fileguard, gitutil
from .campaign import DEFAULT_CONFIG, init_campaign, load_campaign
from .conductor import compare_campaigns, measure_noise, run_iteration, start_iteration
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
    p_init.add_argument("--harness-file", default=None)
    p_init.add_argument("--bridge-command", default=None)
    p_init.add_argument("--dev-suite", default="smoke")

    for name in ("start", "status", "transfer-plan"):
        p = sub.add_parser(name)
        p.add_argument("--campaign", required=True)
    p_run = sub.add_parser("run-iteration")
    p_run.add_argument("--campaign", required=True)
    p_run.add_argument("--candidate-bundle", default=None)
    p_run.add_argument("--candidate-manifest", default=None)

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
        result = run_iteration(
            campaign,
            candidate_bundle=(Path(args.candidate_bundle) if args.candidate_bundle else None),
            candidate_manifest=(
                Path(args.candidate_manifest) if args.candidate_manifest else None
            ),
        )
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
