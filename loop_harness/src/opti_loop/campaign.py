"""Campaign state: one campaign = one line of harness evolution.

A campaign owns its configuration, iteration counter, ledger, learnings file,
cluster register, and noise-band state. Parallel campaigns (ADR-0015 §9) are
separate campaign directories — they share the read-only evaluation plane and
never share mutable state.

Everything under ``campaigns/`` is gitignored, mirroring auto-harness's
``workspace/`` convention: the optimizer may write its manifest and learnings
there without tripping the tracked-file guard.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CAMPAIGN_DIR_NAME = "campaigns"
CONFIG_FILE = "campaign.json"
STATE_FILE = "state.json"
CLUSTERS_FILE = "clusters.json"
LEDGER_FILE = "ledger.jsonl"
LEARNINGS_FILE = "LEARNINGS.md"

DEFAULT_CONFIG: dict[str, Any] = {
    "schema_version": "0.1-draft",
    "campaign_id": None,
    # Evaluation plane (read-only to the loop; opti-eval owns it).
    "suites": {"dev": "smoke", "smoke": "smoke", "regression": "regression"},
    "adapter": {"kind": "fixture", "pass_rate": 0.55, "seed": 0},
    # Fixed variables per docs/evaluation/EVALUATION_PRINCIPLES.md. Recorded in
    # every ledger row. The executor pin is a run configuration under Open
    # Question 17; the fixture adapter ignores it.
    "fixed_variables": {
        "executor_model": "unpinned (OQ-17; project owner direction: MiniMax-M3)",
        "browser_backend": "none (ADR-0003 open; no browser code exists)",
        "lane": "structured",
    },
    # Gate thresholds. Deliberately explicit so nothing hides in code.
    # All values are provisional and TBD-from-measurement per ADR-0005.
    "thresholds": {
        "smoke_min_pass_rate": 0.5,
        "regression_max_new_failures": 0,
        "validity_policy": "strict",  # strict | quorum (quorum pends ADR-0005)
        "quorum_coverage_floor": 0.9,
    },
    # Noise band: null until measured via `opti-loop measure-noise`.
    "noise_band": None,
    # Evaluation-plane quarantine queue (opti-judge); pending entries on
    # compared tasks fail the E5 comparison closed under strict policy.
    "quarantine_file": "runs/quarantine/queue.jsonl",
    # Exploration policy per ADR-0015 §9.
    "exploration": {"divergence_quota": 5, "plateau_force_after": 4},
    "repeats": {"stable": 1, "unstable": 1},
}


@dataclass(slots=True)
class Campaign:
    repo_root: Path
    campaign_id: str
    config: dict[str, Any]
    state: dict[str, Any] = field(default_factory=dict)

    # ── paths ────────────────────────────────────────────────────────────
    @property
    def root(self) -> Path:
        return self.repo_root / CAMPAIGN_DIR_NAME / self.campaign_id

    @property
    def iterations_dir(self) -> Path:
        return self.root / "iterations"

    def iteration_dir(self, number: int) -> Path:
        return self.iterations_dir / f"iter-{number:04d}"

    @property
    def ledger_path(self) -> Path:
        return self.root / LEDGER_FILE

    @property
    def learnings_path(self) -> Path:
        return self.root / LEARNINGS_FILE

    @property
    def clusters_path(self) -> Path:
        return self.root / CLUSTERS_FILE

    # ── state ────────────────────────────────────────────────────────────
    def save_config(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / CONFIG_FILE).write_text(
            json.dumps(self.config, indent=2) + "\n", encoding="utf-8"
        )

    def save_state(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / STATE_FILE).write_text(
            json.dumps(self.state, indent=2) + "\n", encoding="utf-8"
        )

    @property
    def current_iteration(self) -> int:
        return int(self.state.get("current_iteration", 0))

    def open_iteration(self) -> int:
        """Allocate the next iteration number and create its directory."""
        number = self.current_iteration + 1
        self.state["current_iteration"] = number
        directory = self.iteration_dir(number)
        directory.mkdir(parents=True, exist_ok=False)
        self.save_state()
        return number


def init_campaign(
    repo_root: Path, campaign_id: str, overrides: dict[str, Any] | None = None
) -> Campaign:
    config = json.loads(json.dumps(DEFAULT_CONFIG))
    config["campaign_id"] = campaign_id
    for key, value in (overrides or {}).items():
        if isinstance(value, dict) and isinstance(config.get(key), dict):
            config[key].update(value)
        else:
            config[key] = value
    campaign = Campaign(repo_root=repo_root, campaign_id=campaign_id, config=config)
    if campaign.root.exists():
        raise FileExistsError(f"campaign already exists: {campaign.root}")
    campaign.state = {
        "current_iteration": 0,
        "accepted_iterations": [],
        "iterations_since_divergent": 0,
        "iterations_since_accept": 0,
        "regression_last_results": {},
        "noise_band_measured": False,
    }
    campaign.save_config()
    campaign.save_state()
    campaign.ledger_path.touch()
    campaign.learnings_path.write_text(
        f"# Learnings — campaign {campaign_id}\n\n"
        "Append one entry per iteration, pass or fail. This file is the\n"
        "optimizer's only persistent memory across iterations.\n",
        encoding="utf-8",
    )
    campaign.clusters_path.write_text(
        json.dumps({"schema_version": "0.1-draft", "clusters": {}}, indent=2) + "\n",
        encoding="utf-8",
    )
    return campaign


def load_campaign(repo_root: Path, campaign_id: str) -> Campaign:
    root = repo_root / CAMPAIGN_DIR_NAME / campaign_id
    config_path = root / CONFIG_FILE
    if not config_path.is_file():
        raise FileNotFoundError(f"no campaign config at {config_path}")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    state_path = root / STATE_FILE
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {}
    return Campaign(
        repo_root=repo_root, campaign_id=campaign_id, config=config, state=state
    )
