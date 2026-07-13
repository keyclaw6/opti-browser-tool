"""Trusted store: owner-controlled state OUTSIDE the optimizer's mount.

The review's #1 finding: campaign config, state, ledger, gate reports, noise
band, quarantine, and the calibration corpus were gitignored *inside* the repo
the optimizer can write, so a forged ``gate-report.json`` could be recorded as
accepted without ever running the gate (F02). The structural fix is to move
every conductor-owned artifact into a store the optimizer cannot address.

This module locates that store and **refuses to place it under ``repo_root``**.
In production the optimizer is mounted with only ``<worktree>/harness/components``
writable; because the store lives outside the repo entirely, a confined
optimizer cannot reach it. Writes are atomic (temp file + ``os.replace``) so a
crash cannot leave a half-written trusted artifact.

Location resolution (first hit wins):
1. explicit ``store_root`` argument,
2. ``OPTI_STORE_ROOT`` environment variable,
3. ``<repo_root>/../opti-store`` (sibling of the repo).
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


class StoreLocationError(RuntimeError):
    """The requested store path is unsafe (inside the optimizer's repo mount)."""


def resolve_store_root(repo_root: Path, store_root: str | Path | None = None) -> Path:
    repo_root = repo_root.resolve()
    raw = store_root or os.environ.get("OPTI_STORE_ROOT") or (repo_root.parent / "opti-store")
    resolved = Path(raw).resolve()
    # Refuse any store inside the repo the optimizer can write.
    if resolved == repo_root or repo_root in resolved.parents:
        raise StoreLocationError(
            f"trusted store {resolved} is inside repo_root {repo_root}; "
            "the optimizer could forge its contents. Place it outside the repo."
        )
    return resolved


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".swap")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp, path)  # atomic on POSIX
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def atomic_write_json(path: Path, payload: Any) -> None:
    atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


class TrustedStore:
    """Filesystem layout under the owner-only store root, per campaign."""

    def __init__(self, root: Path, campaign_id: str) -> None:
        self.root = root
        self.campaign_id = campaign_id

    @property
    def campaign_dir(self) -> Path:
        return self.root / self.campaign_id

    @property
    def config_path(self) -> Path:
        return self.campaign_dir / "campaign.json"

    @property
    def state_path(self) -> Path:
        return self.campaign_dir / "state.json"

    @property
    def ledger_path(self) -> Path:
        return self.campaign_dir / "ledger.jsonl"

    @property
    def learnings_path(self) -> Path:
        return self.campaign_dir / "LEARNINGS.md"

    @property
    def clusters_path(self) -> Path:
        return self.campaign_dir / "clusters.json"

    @property
    def admissions_path(self) -> Path:
        return self.campaign_dir / "admissions.jsonl"

    @property
    def noise_band_path(self) -> Path:
        return self.campaign_dir / "noise-band.json"

    @property
    def quarantine_path(self) -> Path:
        return self.campaign_dir / "quarantine" / "queue.jsonl"

    @property
    def corpus_path(self) -> Path:
        return self.campaign_dir / "calibration-corpus" / "corpus.jsonl"

    @property
    def iterations_dir(self) -> Path:
        return self.campaign_dir / "iterations"

    def iteration_dir(self, number: int) -> Path:
        return self.iterations_dir / f"iter-{number:04d}"

    @property
    def worktree_path(self) -> Path:
        # The optimizer's mount: a git worktree OUTSIDE repo_root.
        return self.campaign_dir / "candidate-worktree"

    def exists(self) -> bool:
        return self.config_path.is_file()
