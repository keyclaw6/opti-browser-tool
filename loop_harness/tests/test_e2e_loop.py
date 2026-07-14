"""End-to-end tests of the transactional v2 loop over a trusted boundary.

Production runbook order (F18): start -> optimizer commits in the isolated
worktree + writes manifest.json -> run-iteration (gate + accept/reset + record
as ONE transaction). The current command bridge is diagnostic plumbing only:
without a trusted evidence path, even a performance-improving pass payload
must remain simulated and cannot advance the accepted base.

Adversarial cases assert the review's blocking holes are closed: committed
forbidden edit (F01), forged gate report (F02), simulated never advances real
state (F04), shotgun precision floor (F09), and rejection resets the worktree
without advancing (F06).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from opti_loop.campaign import init_campaign, load_campaign
from opti_loop.conductor import run_iteration, start_iteration, measure_noise

REPO_ROOT = Path(os.environ["OPTI_BROWSER_REPO_ROOT"])
ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
       "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
QUALITY_REL = "harness/components/policy/quality.txt"

BRIDGE = """import argparse, hashlib, json
p = argparse.ArgumentParser()
p.add_argument("--task-json"); p.add_argument("--result-json"); p.add_argument("--quality")
a = p.parse_args()
task = json.load(open(a.task_json))
try:
    q = float(open(a.quality).read().strip())
except Exception:
    q = 0.0
tid = task["id"]
v = int.from_bytes(hashlib.sha256(f"0:{tid}".encode()).digest(), "big") / float(2 ** 256)
passed = v < q
json.dump({"task_id": tid, "status": "passed" if passed else "failed",
           "reward": 1.0 if passed else 0.0, "verifier": {"kind": "test_state", "valid": True}},
          open(a.result_json, "w"))
"""


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=ENV)


def _fixture_value(tid: str) -> float:
    return int.from_bytes(hashlib.sha256(f"0:{tid}".encode()).digest(), "big") / float(2 ** 256)


class TransactionalLoopTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        self.repo = tmp / "repo"
        (self.repo / "evals").mkdir(parents=True)
        shutil.copytree(REPO_ROOT / "evals/catalog", self.repo / "evals/catalog")
        shutil.copytree(REPO_ROOT / "evals/suites", self.repo / "evals/suites")
        shutil.copytree(REPO_ROOT / "harness", self.repo / "harness")
        # Register a simulated-quality knob in the policy component.
        (self.repo / QUALITY_REL).write_text("0.55\n")
        reg = self.repo / "harness/components/policy/component.json"
        data = json.loads(reg.read_text()); data["files"] = sorted(set(data["files"]) | {"quality.txt"})
        reg.write_text(json.dumps(data, indent=2) + "\n")
        _git(self.repo, "init", "-q"); _git(self.repo, "add", "-A"); _git(self.repo, "commit", "-qm", "base")

        self.store = tmp / "store"
        self.bridge = tmp / "bridge.py"; self.bridge.write_text(BRIDGE)
        self.checksum = hashlib.sha256(self.bridge.read_bytes()).hexdigest()
        self.smoke_ids = json.loads((self.repo / "evals/suites/smoke.json").read_text())["task_ids"]
        self.flipping = sorted(t for t in self.smoke_ids if 0.55 <= _fixture_value(t) < 0.70)
        self.assertTrue(self.flipping)

    def tearDown(self) -> None:
        subprocess.run(["git", "-C", str(self.repo), "worktree", "prune"], capture_output=True, env=ENV)
        self._tmp.cleanup()

    # ── adapters / admissions ─────────────────────────────────────────────
    def _command_adapter(self) -> dict:
        quality_abs = self.store / "cmp" / "candidate-worktree" / QUALITY_REL
        cmd = (f"{sys.executable} {self.bridge} --task-json {{task_json}} "
               f"--result-json {{result_json}} --quality {quality_abs}")
        return {"kind": "command", "command": cmd,
                "verifier_id": "test-verifier", "verifier_checksum": self.checksum}

    def _register_admissions(self, campaign) -> None:
        ids = set(self.smoke_ids) | set(json.loads((self.repo / "evals/suites/regression.json").read_text())["task_ids"])
        campaign.store.admissions_path.parent.mkdir(parents=True, exist_ok=True)
        with campaign.store.admissions_path.open("w") as fh:
            for tid in sorted(ids):
                fh.write(json.dumps({"verifier_id": "test-verifier", "task_id": tid,
                                     "verifier_checksum": self.checksum, "admitted": True}) + "\n")

    def _commit_quality(self, worktree: Path, value: str) -> None:
        (worktree / QUALITY_REL).write_text(value)
        _git(worktree, "add", "-A"); _git(worktree, "commit", "-qm", f"quality {value}")

    def _write_manifest(self, worktree: Path, predicted: list[str], **over) -> None:
        m = {
            "schema_version": "0.1-draft", "experiment_id": "e", "status": "proposed",
            "hypothesis": "raise policy quality", "trace_evidence": [{"run_id": "iter", "event_id": "n"}],
            "suspected_root_cause": "quality low",
            "treatment": {"description": "quality 0.70", "change_scope": [QUALITY_REL],
                          "activation_evidence": ["adapter reads quality.txt"]},
            "baseline_ref": "b", "fixed_variables": {"executor_model": "test"},
            "predicted_improvements": [{"failure_class": "hash-band", "tasks": predicted}],
            "regression_risks": [{"failure_class": "none", "tasks": []}],
            "evaluation_plan": {"task_sets": ["smoke"], "repetitions": {}, "pairing": "paired", "budget": {}},
            "acceptance_criteria": {"primary": "E5"}, "target_component": "policy", "cluster_ref": "stub/real_v1/failed",
        }
        m.update(over)
        (worktree / "manifest.json").write_text(json.dumps(m))

    def _new_campaign(self, cid: str, adapter: dict, **thresholds):
        overrides = {"adapter": adapter,
                     "suites": {"dev": "smoke", "smoke": "smoke", "regression": "regression"},
                     "thresholds": {"smoke_min_pass_rate": 0.1, **thresholds},
                     "exploration": {"divergence_quota": 0, "plateau_force_after": 0, "pivot_after_failures": 2}}
        return init_campaign(self.repo, cid, store_root=self.store, overrides=overrides)

    # ── an untrusted no-trace command bridge cannot advance state ────────
    def test_no_trace_command_bridge_does_not_advance_state(self) -> None:
        campaign = self._new_campaign("cmp", self._command_adapter())
        self._register_admissions(campaign)
        base_before = campaign.state["accepted_base_sha"]
        measure_noise(campaign, runs=2)

        started = start_iteration(campaign)
        wt = Path(started["worktree"])
        self._commit_quality(wt, "0.70\n")
        self._write_manifest(wt, predicted=self.flipping[:2])
        result = run_iteration(campaign)

        self.assertEqual(result["decision"], "accepted")
        self.assertEqual(result["evidence_class"], "simulated")
        self.assertFalse(result["advanced_accepted_state"])
        reloaded = load_campaign(self.repo, "cmp", store_root=self.store)
        self.assertEqual(reloaded.state["accepted_base_sha"], base_before)
        self.assertEqual(reloaded.state["accepted_iterations"], [])
        # worktree destroyed after the transaction (boundary reset).
        self.assertFalse(campaign.worktree_path.exists())
        gate = json.loads((campaign.iteration_dir(1) / "gate-report.json").read_text())
        self.assertEqual({r["rung"] for r in gate["rungs"]}, {"E0", "E1", "E2", "E3", "E4", "E5"})
        self.assertFalse(gate["eligibility"]["acceptance_eligible"])

    # ── F01: committed forbidden edit is rejected ────────────────────────
    def test_committed_forbidden_edit_rejected(self) -> None:
        campaign = self._new_campaign("cmp", self._command_adapter())
        self._register_admissions(campaign); measure_noise(campaign, runs=2)
        wt = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(wt, "0.70\n")
        (wt / "evals/plane.txt").write_text("tampered\n")  # eval-plane edit...
        _git(wt, "add", "-A"); _git(wt, "commit", "-qm", "sneaky")  # ...committed (the F01 bypass)
        self._write_manifest(wt, predicted=self.flipping[:1])
        result = run_iteration(campaign)
        self.assertEqual(result["decision"], "rejected")
        self.assertFalse(result["advanced_accepted_state"])

    # ── F02: a forged gate report cannot cause acceptance ────────────────
    def test_forged_gate_report_is_ignored(self) -> None:
        campaign = self._new_campaign("cmp", self._command_adapter())
        self._register_admissions(campaign); measure_noise(campaign, runs=2)
        started = start_iteration(campaign)
        wt = Path(started["worktree"])
        # Pre-plant a forged "accepted" gate report in the store iteration dir.
        forged = campaign.iteration_dir(1) / "gate-report.json"
        forged.write_text(json.dumps({"verdict": {"decision": "accepted", "evidence_class": "benchmark",
                                                   "advances_accepted_state": True}}))
        # Optimizer makes NO commit and writes NO manifest — yet a forged
        # "accepted" report sits in the store. The transaction must recompute.
        self.assertTrue(wt.exists())
        result = run_iteration(campaign)
        # The transaction recomputes the verdict itself; the forgery is overwritten.
        self.assertFalse(result["advanced_accepted_state"])
        self.assertNotEqual(result["decision"], "accepted")

    # ── F04: a simulated (fixture) acceptance never advances real state ──
    def test_simulated_acceptance_does_not_advance(self) -> None:
        campaign = self._new_campaign("sim", {"kind": "harness-fixture", "file": QUALITY_REL,
                                              "default_pass_rate": 0.55, "seed": 0})
        base_before = campaign.state["accepted_base_sha"]
        measure_noise(campaign, runs=2)
        wt = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(wt, "0.70\n")
        self._write_manifest(wt, predicted=self.flipping[:2])
        result = run_iteration(campaign)
        self.assertEqual(result["decision"], "accepted")
        self.assertEqual(result["evidence_class"], "simulated")
        self.assertFalse(result["advanced_accepted_state"])  # the F04 property
        reloaded = load_campaign(self.repo, "sim", store_root=self.store)
        self.assertEqual(reloaded.state["accepted_base_sha"], base_before)
        self.assertEqual(reloaded.state["accepted_iterations"], [])

    # ── F09: a shotgun prediction fails the precision floor ──────────────
    def test_shotgun_prediction_rejected(self) -> None:
        campaign = self._new_campaign("cmp", self._command_adapter(), min_prediction_precision=0.9)
        self._register_admissions(campaign); measure_noise(campaign, runs=2)
        wt = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(wt, "0.70\n")
        # Predict ALL smoke tasks to catch the few that flip -> precision far below 0.9.
        self._write_manifest(wt, predicted=sorted(self.smoke_ids))
        result = run_iteration(campaign)
        self.assertEqual(result["decision"], "rejected")
        gate = json.loads((campaign.iteration_dir(1) / "gate-report.json").read_text())
        e5 = next(r for r in gate["rungs"] if r["rung"] == "E5")
        self.assertFalse(e5["detail"]["conditions"]["prediction_precision_ok"])


if __name__ == "__main__":
    unittest.main()
