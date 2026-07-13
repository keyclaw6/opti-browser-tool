"""End-to-end dry run of the loop shell in a hermetic temporary repository.

A scripted "optimizer" (plain test code — no LLM) plays phase D against the
real conductor, gate ladder, and opti-eval fixture plumbing:

1. accepted path: raise the simulated harness quality → deterministic
   fail→pass flips, zero regressions → `simulated:accepted`;
2. rejected path: an out-of-allowlist edit is stopped at E0;
3. rejected path: lower the quality → regressions beyond the noise band →
   `simulated:rejected`, then file-granular rollback restores the tree.

Everything runs against a temp git repo carrying the real 20-task smoke
catalog subset, so the test exercises the true opti-eval artifact layout.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from opti_eval.adapters.fixture import FixtureAdapter

from opti_loop.campaign import init_campaign
from opti_loop.conductor import (
    gate_iteration,
    measure_noise,
    record_iteration,
    rollback_iteration,
    snapshot_guard_baseline,
    start_iteration,
)

REPO_ROOT = Path(os.environ["OPTI_BROWSER_REPO_ROOT"])

BASE_RATE = 0.55
RAISED_RATE = 0.70
LOWERED_RATE = 0.35
SEED = 0

QUALITY_FILE = "harness/components/policy/quality.txt"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@t",
        },
    )


def _fixture_value(task_id: str) -> float:
    adapter = FixtureAdapter(pass_rate=1.0, seed=SEED)
    result = adapter.run({"id": task_id, "source": "x"}, Path("."))
    return float(result.metrics["fixture_value"])


class EndToEndLoopTest(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        self.repo = tmp / "repo"
        # Evaluation-plane data: real catalog + suites, copied read-only.
        (self.repo / "evals").mkdir(parents=True)
        shutil.copytree(REPO_ROOT / "evals" / "catalog", self.repo / "evals" / "catalog")
        shutil.copytree(REPO_ROOT / "evals" / "suites", self.repo / "evals" / "suites")
        shutil.copytree(REPO_ROOT / "harness", self.repo / "harness")
        # Register the quality file in the policy component.
        quality = self.repo / QUALITY_FILE
        quality.write_text(f"{BASE_RATE}\n", encoding="utf-8")
        reg_path = self.repo / "harness/components/policy/component.json"
        registration = json.loads(reg_path.read_text(encoding="utf-8"))
        registration["files"] = sorted(set(registration["files"]) | {"quality.txt"})
        reg_path.write_text(json.dumps(registration, indent=2) + "\n", encoding="utf-8")
        (self.repo / ".gitignore").write_text("campaigns/\n", encoding="utf-8")
        _git(self.repo, "init", "-q")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-qm", "seed")

        self.campaign = init_campaign(
            self.repo,
            "e2e",
            overrides={
                "adapter": {
                    "kind": "harness-fixture",
                    "file": QUALITY_FILE,
                    "default_pass_rate": BASE_RATE,
                    "seed": SEED,
                },
                "suites": {"dev": "smoke", "smoke": "smoke", "regression": "regression"},
            },
        )
        snapshot_guard_baseline(self.campaign)
        measure_noise(self.campaign, runs=2)

        smoke_ids = json.loads(
            (self.repo / "evals/suites/smoke.json").read_text(encoding="utf-8")
        )["task_ids"]
        self.flipping = sorted(
            tid for tid in smoke_ids if BASE_RATE <= _fixture_value(tid) < RAISED_RATE
        )
        self.assertTrue(self.flipping, "chosen rates must flip at least one smoke task")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _manifest(self, *, new_rate: float, predicted: list[str]) -> dict:
        return {
            "schema_version": "0.1-draft",
            "experiment_id": f"exp-e2e-{new_rate}",
            "status": "proposed",
            "hypothesis": f"raising simulated policy quality to {new_rate} flips the predicted tasks",
            "trace_evidence": [
                {"run_id": "iter-0001", "event_id": "n/a", "finding": "stub analysis: hash-band failures"}
            ],
            "suspected_root_cause": "simulated quality below task hash values",
            "treatment": {
                "description": f"set quality to {new_rate}",
                "change_scope": [QUALITY_FILE],
                "activation_evidence": ["adapter reads quality.txt at run construction"],
            },
            "baseline_ref": "iter-0001",
            "fixed_variables": {"executor_model": "fixture-simulated"},
            "predicted_improvements": [
                {"failure_class": "simulated/hash-band", "tasks": predicted}
            ],
            "regression_risks": [{"failure_class": "simulated/none", "tasks": []}],
            "evaluation_plan": {
                "task_sets": ["smoke"],
                "repetitions": {"deterministic": 1},
                "pairing": "paired",
                "budget": {"max_runs": 10},
            },
            "acceptance_criteria": {"primary": "E5 three conditions"},
            "target_component": "policy",
            "cluster_ref": "stub/simulated/failed",
        }

    def test_accept_reject_and_rollback_paths(self) -> None:
        # ── Iteration 1: improvement is accepted (simulated) ──────────────
        started = start_iteration(self.campaign)
        self.assertFalse(started["divergent"])
        iter_dir = self.campaign.iteration_dir(1)
        self.assertTrue((iter_dir / "PACKET.md").is_file())
        self.assertTrue((iter_dir / "analysis" / "overview.md").is_file())

        (self.repo / QUALITY_FILE).write_text(f"{RAISED_RATE}\n", encoding="utf-8")
        (iter_dir / "manifest.json").write_text(
            json.dumps(self._manifest(new_rate=RAISED_RATE, predicted=self.flipping[:2]))
        )
        report = gate_iteration(self.campaign)
        self.assertEqual(report.verdict, "simulated:accepted", report.to_dict())
        rungs = {r.rung: r.status for r in report.rungs}
        self.assertEqual(rungs["E0"], "pass")
        self.assertEqual(rungs["E1"], "pass")
        self.assertEqual(rungs["E3"], "pass")
        self.assertEqual(rungs["E5"], "pass")
        self.assertEqual(report.attribution["verdict"], "keep")
        self.assertEqual(report.comparison["regressed"], [])
        self.assertGreaterEqual(len(report.comparison["fixed"]), len(self.flipping))

        recorded = record_iteration(self.campaign)
        self.assertEqual(recorded["verdict"], "simulated:accepted")
        self.assertTrue(recorded["promotion_candidates"])
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-qm", "iter-0001 accepted")

        # Manifest now carries conductor-written attribution.
        stored = json.loads((iter_dir / "manifest.json").read_text(encoding="utf-8"))
        self.assertIn("attribution", stored)

        # ── Iteration 2: forbidden edit dies at E0 ────────────────────────
        start_iteration(self.campaign)
        iter2 = self.campaign.iteration_dir(2)
        forbidden = self.repo / "evals" / "suites" / "smoke.json"
        original = forbidden.read_text(encoding="utf-8")
        forbidden.write_text(original.replace("\n", "\n", 1) + "\n")
        (iter2 / "manifest.json").write_text(
            json.dumps(self._manifest(new_rate=RAISED_RATE, predicted=self.flipping[:1]))
        )
        report2 = gate_iteration(self.campaign)
        self.assertEqual(report2.verdict, "rejected")
        self.assertEqual(report2.rungs[0].rung, "E0")
        self.assertEqual(report2.rungs[0].status, "fail")
        forbidden.write_text(original, encoding="utf-8")
        record_iteration(self.campaign)

        # ── Iteration 3: regression is rejected, then rolled back ─────────
        start_iteration(self.campaign)
        iter3 = self.campaign.iteration_dir(3)
        (self.repo / QUALITY_FILE).write_text(f"{LOWERED_RATE}\n", encoding="utf-8")
        (iter3 / "manifest.json").write_text(
            json.dumps(self._manifest(new_rate=LOWERED_RATE, predicted=self.flipping[:1]))
        )
        report3 = gate_iteration(self.campaign)
        self.assertNotEqual(report3.verdict, "simulated:accepted")
        rollback = rollback_iteration(self.campaign)
        self.assertEqual(rollback["reverted_paths"], [QUALITY_FILE])
        self.assertEqual(
            (self.repo / QUALITY_FILE).read_text(encoding="utf-8").strip(),
            str(RAISED_RATE),
        )
        recorded3 = record_iteration(self.campaign)
        self.assertIn("rejected", recorded3["verdict"])

        # Ledger carries all three iterations; learnings appended each time.
        ledger_lines = [
            json.loads(line)
            for line in self.campaign.ledger_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual([row["iteration"] for row in ledger_lines], [1, 2, 3])
        learnings = self.campaign.learnings_path.read_text(encoding="utf-8")
        self.assertEqual(learnings.count("## Iteration"), 3)


if __name__ == "__main__":
    unittest.main()
