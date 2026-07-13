"""Campaign state, persisted in the owner-only trusted store (not the repo).

After the review (F02, F15): a campaign's config, state, ledger, learnings,
cluster register, noise band, quarantine, and corpus live under the
``TrustedStore`` root OUTSIDE ``repo_root``, so an optimizer confined to the
repo worktree cannot forge them. The optimizer's only writable surface is the
candidate worktree's ``harness/components/**`` plus an untrusted
``manifest.json`` the conductor ingests and validates.

One campaign = one line of harness evolution, anchored by an ``accepted_base_sha``
that advances only on a genuine benchmark acceptance.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import gitutil
from .store import TrustedStore, atomic_write_json, atomic_write_text, resolve_store_root

DEFAULT_CONFIG: dict[str, Any] = {
    "schema_version": "0.2-draft",
    "campaign_id": None,
    "suites": {"dev": "smoke", "smoke": "smoke", "regression": "regression"},
    "adapter": {"kind": "fixture", "pass_rate": 0.55, "seed": 0},
    "fixed_variables": {
        "executor_model": "MiniMax-M3 via OpenCode Go (ADR-0017; exact API identifier pinned per campaign at bring-up)",
        "browser_backend": "none (ADR-0003 open; no browser code exists)",
        "lane": "structured",
    },
    "thresholds": {
        "smoke_min_pass_rate": 0.5,
        "regression_max_new_failures": 0,
        "validity_policy": "strict",
        "quorum_coverage_floor": 0.9,
        # Shotgun-prediction guard (F09): of the tasks a manifest predicts will
        # flip, at least this fraction must actually flip in E5.
        "min_prediction_precision": 0.1,
    },
    "noise_band": None,
    "exploration": {"divergence_quota": 5, "plateau_force_after": 4, "pivot_after_failures": 2},
    "repeats": {"stable": 1, "unstable": 3},
    # Transfer-bet falsification protocol (F17); see transfer.py.
    "transfer": {
        "checkpoint_every": 5,
        "reject_bet_if": "median per-model transfer delta <= 0 on discovery-excluded tasks across the stronger-model panel",
    },
}


@dataclass(slots=True)
class Campaign:
    repo_root: Path
    campaign_id: str
    store: TrustedStore
    config: dict[str, Any]
    state: dict[str, Any] = field(default_factory=dict)

    # ── trusted-store paths ───────────────────────────────────────────────
    @property
    def ledger_path(self) -> Path:
        return self.store.ledger_path

    @property
    def learnings_path(self) -> Path:
        return self.store.learnings_path

    @property
    def clusters_path(self) -> Path:
        return self.store.clusters_path

    @property
    def worktree_path(self) -> Path:
        return self.store.worktree_path

    def iteration_dir(self, number: int) -> Path:
        return self.store.iteration_dir(number)

    # ── persistence (atomic, owner-only) ──────────────────────────────────
    def save_config(self) -> None:
        atomic_write_json(self.store.config_path, self.config)

    def save_state(self) -> None:
        atomic_write_json(self.store.state_path, self.state)

    @property
    def current_iteration(self) -> int:
        return int(self.state.get("current_iteration", 0))

    def open_iteration(self) -> int:
        number = self.current_iteration + 1
        self.state["current_iteration"] = number
        self.iteration_dir(number).mkdir(parents=True, exist_ok=True)
        self.save_state()
        return number


def _deep_merge(config: dict[str, Any], overrides: dict[str, Any]) -> None:
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(config.get(key), dict):
            config[key].update(value)
        else:
            config[key] = value


def init_campaign(
    repo_root: Path,
    campaign_id: str,
    *,
    store_root: str | Path | None = None,
    overrides: dict[str, Any] | None = None,
) -> Campaign:
    repo_root = repo_root.resolve()
    store = TrustedStore(resolve_store_root(repo_root, store_root), campaign_id)
    if store.exists():
        raise FileExistsError(f"campaign already exists: {store.campaign_dir}")
    config = json.loads(json.dumps(DEFAULT_CONFIG))
    config["campaign_id"] = campaign_id
    _deep_merge(config, overrides or {})
    campaign = Campaign(repo_root=repo_root, campaign_id=campaign_id, store=store, config=config)
    campaign.state = {
        "current_iteration": 0,
        "accepted_base_sha": gitutil.head_sha(repo_root),
        "accepted_iterations": [],
        "iterations_since_divergent": 0,
        "iterations_since_accept": 0,
        "failed_attempts": {},          # "<cluster>::<component>" -> count (pivot rule)
        "regression_last_results": {},  # frozen from the accepted-base regression run
        "pending_iteration": 0,
        "pending_divergent": False,
        "pending_base_sha": None,
    }
    store.campaign_dir.mkdir(parents=True, exist_ok=True)
    campaign.save_config()
    campaign.save_state()
    store.ledger_path.touch()
    atomic_write_text(
        store.learnings_path,
        f"# Learnings — campaign {campaign_id}\n\n"
        "Append one entry per iteration, pass or fail. The optimizer's only\n"
        "persistent memory across iterations.\n",
    )
    atomic_write_json(store.clusters_path, {"schema_version": "0.1-draft", "clusters": {}})
    return campaign


def load_campaign(
    repo_root: Path, campaign_id: str, *, store_root: str | Path | None = None
) -> Campaign:
    repo_root = repo_root.resolve()
    store = TrustedStore(resolve_store_root(repo_root, store_root), campaign_id)
    if not store.config_path.is_file():
        raise FileNotFoundError(f"no campaign config at {store.config_path}")
    config = json.loads(store.config_path.read_text(encoding="utf-8"))
    state = (
        json.loads(store.state_path.read_text(encoding="utf-8"))
        if store.state_path.is_file()
        else {}
    )
    return Campaign(
        repo_root=repo_root, campaign_id=campaign_id, store=store, config=config, state=state
    )
