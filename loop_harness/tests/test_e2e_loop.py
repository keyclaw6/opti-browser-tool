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
from types import SimpleNamespace
from unittest import mock

from opti_eval.adapters.fixture import FixtureAdapter
from opti_eval.identity import (
    digest_json,
    finalize_protocol_snapshot,
    normalize_adapter_identity,
    simulated_protocol,
)
from opti_loop.campaign import init_campaign, load_campaign
from opti_loop.conductor import (
    _load_accepted_run,
    compare_campaigns,
    measure_noise,
    run_iteration,
    start_iteration,
)
from opti_loop import gitutil
from opti_loop.protocol import (
    ProtocolError,
    build_protocol_snapshot,
    freeze_protocol,
    load_frozen_protocol,
)

REPO_ROOT = Path(os.environ["OPTI_BROWSER_REPO_ROOT"])
ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
       "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
QUALITY_REL = "harness/components/policy/quality.txt"
_UNSET = object()

try:
    from jsonschema import Draft202012Validator
except ImportError:
    EXPERIMENT_VALIDATOR = None
else:
    EXPERIMENT_VALIDATOR = Draft202012Validator(
        json.loads((REPO_ROOT / "schemas/experiment.schema.json").read_text(encoding="utf-8"))
    )

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
        verifier = campaign.config["identity"]["verifier_bundle"]
        verifier.update(
            id="test-verifier",
            checksum=self.checksum,
            bundle_digest=hashlib.sha256(self.bridge.read_bytes()).hexdigest(),
            admissions_digest=hashlib.sha256(
                b"opti.admissions.v1\0"
                + campaign.store.admissions_path.read_bytes()
            ).hexdigest(),
        )
        campaign.save_config()

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
        verifier_id = adapter.get("verifier_id")
        verifier_checksum = adapter.get("verifier_checksum")
        if verifier_id is not None or verifier_checksum is not None:
            overrides["identity"] = {
                "verifier_bundle": {
                    "id": verifier_id,
                    "checksum": verifier_checksum,
                    "bundle_digest": hashlib.sha256(self.bridge.read_bytes()).hexdigest(),
                    "admissions_digest": hashlib.sha256(
                        f"{verifier_id}:{verifier_checksum}".encode()
                    ).hexdigest(),
                }
            }
        return init_campaign(self.repo, cid, store_root=self.store, overrides=overrides)

    def _assert_rejected_transaction(
        self,
        campaign,
        result: dict,
        *,
        expected_submission: object = _UNSET,
        expected_error: str | None = None,
    ) -> dict:
        self.assertEqual(result["decision"], "rejected")
        self.assertFalse(result["advanced_accepted_state"])
        reloaded = load_campaign(self.repo, campaign.campaign_id, store_root=self.store)
        self.assertEqual(reloaded.state["pending_iteration"], 0)
        self.assertIsNone(reloaded.state["pending_base_sha"])
        self.assertFalse(campaign.worktree_path.exists())

        ledger = [
            json.loads(line)
            for line in campaign.ledger_path.read_text().splitlines()
            if line.strip()
        ]
        self.assertEqual(ledger[-1]["decision"], "rejected")
        self.assertTrue(campaign.learnings_path.is_file())

        iteration_dir = campaign.iteration_dir(result["iteration"])
        snapshot = json.loads((iteration_dir / "manifest.snapshot.json").read_text())
        self.assertEqual(snapshot["status"], result["verdict"])
        self.assertNotIn("attribution", snapshot)
        if expected_submission is _UNSET:
            self.assertNotIn("record_type", snapshot)
        else:
            self.assertEqual(snapshot["record_type"], "rejected_submission")
            self.assertEqual(snapshot["original_submission"], expected_submission)
            self.assertEqual(snapshot["verdict"]["label"], result["verdict"])
            self.assertEqual(snapshot["verdict"]["decision"], "rejected")
            self.assertFalse(snapshot["verdict"]["advances_accepted_state"])
            self.assertTrue(snapshot["validation_errors"])
            if expected_error is not None:
                self.assertIn(expected_error, snapshot["validation_errors"])
        if EXPERIMENT_VALIDATOR is not None:
            schema_errors = list(EXPERIMENT_VALIDATOR.iter_errors(snapshot))
            self.assertEqual(
                schema_errors,
                [],
                [error.message for error in schema_errors],
            )
        return json.loads((iteration_dir / "gate-report.json").read_text())

    # ── an untrusted no-trace command bridge cannot advance state ────────
    def test_no_trace_command_bridge_does_not_advance_state(self) -> None:
        campaign = self._new_campaign("cmp", self._command_adapter())
        self._register_admissions(campaign)
        base_before = campaign.state["accepted_base_sha"]
        measure_noise(campaign, runs=2)

        started = start_iteration(campaign)
        self.assertIn(
            "edit only the frozen candidate surface(s) harness/components/",
            started["instructions"],
        )
        packet_path = Path(started["packet"])
        packet = packet_path.read_text()
        self.assertIn("frozen candidate allowlist: `harness/components/`", packet)
        self.assertIn("`target_component` is attribution only", packet)
        self.assertEqual(
            json.loads((packet_path.parent / "packet.json").read_text())[
                "candidate_allowlist"
            ],
            ["harness/components/"],
        )
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

    # ── AR-002: malformed manifests reject without splitting transaction ─
    def test_non_object_manifests_finish_truthful_rejected_transactions(self) -> None:
        campaign = self._new_campaign("cmp", self._command_adapter())
        for submitted in ([], None, "manifest", 7, True):
            with self.subTest(submitted=submitted):
                wt = Path(start_iteration(campaign)["worktree"])
                self._commit_quality(wt, "0.70\n")
                (wt / "manifest.json").write_text(json.dumps(submitted))

                gate = self._assert_rejected_transaction(
                    campaign,
                    run_iteration(campaign),
                    expected_submission=submitted,
                    expected_error="manifest must be a JSON object",
                )
                errors = gate["rungs"][0]["detail"]["manifest_errors"]
                self.assertIn("manifest must be a JSON object", errors)

    def test_non_object_prediction_finishes_rejected_transaction(self) -> None:
        campaign = self._new_campaign("cmp", self._command_adapter())
        wt = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(wt, "0.70\n")
        self._write_manifest(wt, predicted=self.flipping[:1])
        submitted = json.loads((wt / "manifest.json").read_text())
        submitted["predicted_improvements"] = ["not-an-object"]
        (wt / "manifest.json").write_text(json.dumps(submitted))

        gate = self._assert_rejected_transaction(
            campaign,
            run_iteration(campaign),
            expected_submission=submitted,
            expected_error="predicted_improvements[0] must be an object",
        )
        errors = gate["rungs"][0]["detail"]["manifest_errors"]
        self.assertIn("predicted_improvements[0] must be an object", errors)

    def test_context_invalid_path_preserves_original_submission_and_errors(self) -> None:
        campaign = self._new_campaign("cmp", self._command_adapter())
        wt = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(wt, "0.70\n")
        self._write_manifest(wt, predicted=self.flipping[:1])
        submitted = json.loads((wt / "manifest.json").read_text())
        submitted["treatment"]["change_scope"] = [
            "harness/components/policy/../observation/observation_contract.md"
        ]
        (wt / "manifest.json").write_text(json.dumps(submitted))

        gate = self._assert_rejected_transaction(
            campaign,
            run_iteration(campaign),
            expected_submission=submitted,
            expected_error=(
                "unsafe change_scope path: "
                "'harness/components/policy/../observation/observation_contract.md'"
            ),
        )
        self.assertEqual(gate["rungs"][0]["status"], "fail")

    def test_optimizer_status_spoof_is_rejected_and_overwritten(self) -> None:
        campaign = self._new_campaign("cmp", self._command_adapter())
        wt = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(wt, "0.70\n")
        self._write_manifest(wt, predicted=self.flipping[:1], status="accepted")

        submitted = json.loads((wt / "manifest.json").read_text())
        gate = self._assert_rejected_transaction(
            campaign,
            run_iteration(campaign),
            expected_submission=submitted,
        )
        errors = gate["rungs"][0]["detail"]["manifest_errors"]
        self.assertTrue(any("conductor owns terminal status" in error for error in errors))

    def test_e2_rejection_writes_trusted_terminal_snapshot_status(self) -> None:
        campaign = self._new_campaign("cmp", self._command_adapter())
        wt = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(wt, "0.00\n")
        self._write_manifest(wt, predicted=self.flipping[:1])

        gate = self._assert_rejected_transaction(campaign, run_iteration(campaign))
        self.assertEqual(
            [(rung["rung"], rung["status"]) for rung in gate["rungs"]],
            [("E0", "pass"), ("E1", "pass"), ("E2", "fail")],
        )

    def test_pivot_rejection_writes_trusted_terminal_snapshot_status(self) -> None:
        campaign = self._new_campaign("cmp", self._command_adapter())
        campaign.state["failed_attempts"]["stub/real_v1/failed::policy"] = 2
        campaign.save_state()
        wt = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(wt, "0.70\n")
        self._write_manifest(wt, predicted=self.flipping[:1])
        before = (
            campaign.learnings_path.read_text(encoding="utf-8")
            if campaign.learnings_path.is_file()
            else ""
        )

        gate = self._assert_rejected_transaction(campaign, run_iteration(campaign))
        self.assertIn("pivot_rule", gate["rungs"][0]["detail"])
        after = campaign.learnings_path.read_text(encoding="utf-8")
        appended = after[len(before):]
        self.assertEqual(appended.count("## Iteration 0001"), 1)
        self.assertIn("simulated:rejected", appended)
        self.assertIn("raise policy quality", appended)
        self.assertIn("stub/real_v1/failed", appended)
        self.assertIn("`policy`", appended)

    # ── ADR-0018 D1: one frozen protocol and closed per-run identities ──
    def test_protocol_digest_tracks_content_and_exact_runtime_identities(self) -> None:
        campaign = self._new_campaign("identity", {"kind": "fixture", "seed": 0})
        gitutil.worktree_add(
            campaign.repo_root,
            campaign.worktree_path,
            campaign.state["accepted_base_sha"],
        )
        worktree = campaign.worktree_path
        try:
            original = build_protocol_snapshot(campaign, worktree, iteration=1)
            digests = {original["protocol_digest"]}

            catalog = worktree / "evals/catalog/tasks.jsonl"
            rows = catalog.read_text(encoding="utf-8").splitlines()
            first = json.loads(rows[0])
            first["goal"] = first["goal"] + " content mutation"
            rows[0] = json.dumps(first, sort_keys=True)
            catalog.write_text("\n".join(rows) + "\n", encoding="utf-8")
            digests.add(
                build_protocol_snapshot(campaign, worktree, iteration=1)["protocol_digest"]
            )
            _git(worktree, "checkout", "--", "evals/catalog/tasks.jsonl")

            campaign.config["identity"]["executor"]["revision"] = "simulated:v2"
            digests.add(
                build_protocol_snapshot(campaign, worktree, iteration=1)["protocol_digest"]
            )
            campaign.config["identity"]["executor"]["revision"] = "simulated:v1"

            campaign.config["identity"]["verifier_bundle"]["bundle_digest"] = "1" * 64
            digests.add(
                build_protocol_snapshot(campaign, worktree, iteration=1)["protocol_digest"]
            )
            campaign.config["identity"]["verifier_bundle"]["bundle_digest"] = original[
                "verifier_bundle"
            ]["bundle_digest"]

            source = original["matched_blocks"][0]["source"]
            campaign.config["identity"]["source_runtimes"][source]["reset"]["digest"] = "2" * 64
            digests.add(
                build_protocol_snapshot(campaign, worktree, iteration=1)["protocol_digest"]
            )
            campaign.config["identity"]["source_runtimes"][source]["reset"]["digest"] = original[
                "source_runtimes"
            ][source]["reset"]["digest"]
            campaign.config["identity"]["source_runtimes"][source]["browser"]["digest"] = "3" * 64
            digests.add(
                build_protocol_snapshot(campaign, worktree, iteration=1)["protocol_digest"]
            )

            lane = worktree / "harness/lanes/structured.lane.json"
            lane.write_text(lane.read_text() + "\n", encoding="utf-8")
            digests.add(
                build_protocol_snapshot(campaign, worktree, iteration=1)["protocol_digest"]
            )
            self.assertEqual(len(digests), 7)
        finally:
            gitutil.worktree_remove(campaign.repo_root, worktree)

    def test_frozen_protocol_is_no_overwrite_reloadable_and_tamper_evident(self) -> None:
        campaign = self._new_campaign("freeze", {"kind": "fixture", "seed": 0})
        gitutil.worktree_add(
            campaign.repo_root,
            campaign.worktree_path,
            campaign.state["accepted_base_sha"],
        )
        try:
            snapshot = build_protocol_snapshot(
                campaign, campaign.worktree_path, iteration=1
            )
            iteration_dir = campaign.iteration_dir(1)
            path = freeze_protocol(iteration_dir, snapshot)
            self.assertEqual(load_frozen_protocol(iteration_dir), snapshot)
            with self.assertRaisesRegex(ProtocolError, "will not be overwritten"):
                freeze_protocol(iteration_dir, snapshot)
            tampered = json.loads(path.read_text())
            tampered["executor"]["revision"] = "simulated:tampered"
            path.write_text(json.dumps(tampered) + "\n")
            with self.assertRaisesRegex(ProtocolError, "binding_digest|protocol_digest"):
                load_frozen_protocol(iteration_dir)
        finally:
            gitutil.worktree_remove(campaign.repo_root, campaign.worktree_path)

    def test_start_freezes_before_baseline_and_later_config_mutation_is_inert(self) -> None:
        campaign = self._new_campaign("frozen", {"kind": "fixture", "seed": 0})
        started = start_iteration(campaign)
        iteration_dir = campaign.iteration_dir(started["iteration"])
        protocol_path = iteration_dir / "protocol.snapshot.json"
        frozen_bytes = protocol_path.read_bytes()
        protocol = load_frozen_protocol(iteration_dir)
        baseline_record = json.loads(
            (iteration_dir / "eval/dev_baseline/run.json").read_text()
        )
        self.assertEqual(
            baseline_record["run_context"]["protocol_digest"],
            protocol["protocol_digest"],
        )

        campaign.config["adapter"] = {"kind": "unsupported-after-start"}
        campaign.config["suites"] = {
            "dev": "missing-after-start",
            "smoke": "missing-after-start",
            "regression": "missing-after-start",
        }
        campaign.config["identity"]["executor"]["revision"] = "simulated:mutated"
        campaign.save_config()
        result = run_iteration(campaign)
        self.assertEqual(result["decision"], "rejected")
        self.assertEqual(protocol_path.read_bytes(), frozen_bytes)
        ledger = json.loads(campaign.ledger_path.read_text().splitlines()[-1])
        self.assertEqual(ledger["protocol_digest"], protocol["protocol_digest"])

    def test_start_preflight_preserves_existing_iteration_and_state(self) -> None:
        campaign = self._new_campaign("preflight", {"kind": "fixture", "seed": 0})
        iteration_dir = campaign.iteration_dir(1)
        iteration_dir.mkdir(parents=True)
        sentinel = iteration_dir / "owner-artifact.txt"
        sentinel.write_text("preserve\n", encoding="utf-8")
        state_before = json.loads(json.dumps(campaign.state))

        with self.assertRaisesRegex(RuntimeError, "next iteration path already exists"):
            start_iteration(campaign)

        self.assertEqual(campaign.state, state_before)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve\n")
        self.assertFalse(campaign.worktree_path.exists())

    def test_start_adapter_identity_failure_cleans_only_new_state(self) -> None:
        campaign = self._new_campaign("adapter-drift", {"kind": "fixture", "seed": 0})
        gitutil.worktree_add(
            campaign.repo_root,
            campaign.worktree_path,
            campaign.state["accepted_base_sha"],
        )
        snapshot = build_protocol_snapshot(
            campaign,
            campaign.worktree_path,
            iteration=1,
        )
        gitutil.worktree_remove(campaign.repo_root, campaign.worktree_path)
        mismatched = FixtureAdapter(pass_rate=0.55, seed=99).describe()
        snapshot["adapter"] = normalize_adapter_identity(mismatched)
        for name in (
            "calibration_binding_digest",
            "comparison_apparatus_digest",
            "protocol_digest",
        ):
            snapshot.pop(name)
        snapshot = finalize_protocol_snapshot(snapshot)
        state_before = json.loads(json.dumps(campaign.state))

        with (
            mock.patch(
                "opti_loop.conductor.build_protocol_snapshot",
                return_value=snapshot,
            ),
            self.assertRaisesRegex(ValueError, "adapter identity does not match"),
        ):
            start_iteration(campaign)

        self.assertEqual(campaign.state, state_before)
        self.assertFalse(campaign.worktree_path.exists())
        self.assertFalse(campaign.iteration_dir(1).exists())

    def test_comparison_uses_apparatus_not_campaign_run_or_build_identity(self) -> None:
        left = self._new_campaign("compare-left", {"kind": "fixture", "seed": 0})
        right = self._new_campaign("compare-right", {"kind": "fixture", "seed": 0})

        def protocol(label: str, campaign_id: str, iteration: int) -> dict:
            adapter = FixtureAdapter(pass_rate=1.0, seed=0)
            snapshot = simulated_protocol(
                suite={"id": "comparison-suite", "kind": "test"},
                tasks=[
                    {
                        "id": "comparison-task",
                        "source": "test-source",
                        "goal": "test",
                    }
                ],
                adapter=adapter.describe(),
            )
            snapshot["campaign_id"] = campaign_id
            snapshot["iteration"] = iteration
            snapshot["accepted_build"].update(
                commit_sha=f"simulated:{label}:commit",
                tree_sha=f"simulated:{label}:tree",
                materialized_digest=digest_json(
                    label,
                    domain="test.accepted-build.v1",
                ),
            )
            for name in (
                "calibration_binding_digest",
                "comparison_apparatus_digest",
                "protocol_digest",
            ):
                snapshot.pop(name)
            return finalize_protocol_snapshot(snapshot)

        left_protocol = protocol("left", left.campaign_id, 2)
        right_protocol = protocol("right", right.campaign_id, 7)
        self.assertNotEqual(left_protocol["protocol_digest"], right_protocol["protocol_digest"])
        self.assertEqual(
            left_protocol["comparison_apparatus_digest"],
            right_protocol["comparison_apparatus_digest"],
        )
        accepted = SimpleNamespace(
            protocol_snapshot=left_protocol,
            summary={"strict_success_rate": 1.0},
        )
        with mock.patch(
            "opti_loop.conductor._load_accepted_run",
            side_effect=[accepted, accepted],
        ):
            report = compare_campaigns(
                self.repo,
                [left.campaign_id, right.campaign_id],
                store_root=self.store,
            )
        self.assertTrue(report["comparable"], report)

    def test_comparison_fails_closed_for_missing_or_different_identity(self) -> None:
        left = self._new_campaign("compare-base", {"kind": "fixture", "seed": 0})
        different = self._new_campaign(
            "compare-different",
            {"kind": "fixture", "seed": 0},
        )
        missing = self._new_campaign("compare-missing", {"kind": "fixture", "seed": 0})
        base_run = SimpleNamespace(
            protocol_snapshot={
                "comparison_apparatus_digest": "a" * 64,
                "executor": {"model": "model-a"},
                "execution": {"suites": {"dev": "suite-a"}},
            },
            summary={"strict_success_rate": 0.75},
        )
        different_run = SimpleNamespace(
            protocol_snapshot={
                "comparison_apparatus_digest": "b" * 64,
                "executor": {"model": "model-a"},
                "execution": {"suites": {"dev": "suite-a"}},
            },
            summary={"strict_success_rate": 0.80},
        )
        with mock.patch(
            "opti_loop.conductor._load_accepted_run",
            side_effect=[base_run, different_run],
        ):
            report = compare_campaigns(
                self.repo,
                [left.campaign_id, different.campaign_id],
                store_root=self.store,
            )
        self.assertFalse(report["comparable"])
        self.assertIn("differ", report["non_comparable_reason"])

        with mock.patch(
            "opti_loop.conductor._load_accepted_run",
            side_effect=[base_run, None],
        ):
            missing_report = compare_campaigns(
                self.repo,
                [left.campaign_id, missing.campaign_id],
                store_root=self.store,
            )
        self.assertFalse(missing_report["comparable"])
        self.assertIn("missing accepted", missing_report["non_comparable_reason"])


    def test_accepted_loader_rejects_simulated_anchor(self) -> None:
        campaign = self._new_campaign("simulated-anchor", {"kind": "fixture", "seed": 0})
        campaign.state.update(
            last_accepted_treatment_dir=str(campaign.store.campaign_dir),
            last_accepted_admission_receipt=None,
        )
        with self.assertRaisesRegex(RuntimeError, "missing.*AR-003 admission"):
            _load_accepted_run(campaign)

    def test_stale_noise_binding_changes_with_executor_identity(self) -> None:
        campaign = self._new_campaign("stale-noise", {"kind": "fixture", "seed": 0})
        band = measure_noise(campaign, runs=2)
        noise_protocol = load_frozen_protocol(campaign.store.campaign_dir / "noise")
        self.assertEqual(band.run_identity, noise_protocol["calibration_binding_digest"])

        campaign.config["identity"]["executor"]["revision"] = "simulated:v2"
        started = start_iteration(campaign)
        iteration_protocol = load_frozen_protocol(
            campaign.iteration_dir(started["iteration"])
        )
        self.assertNotEqual(
            band.run_identity, iteration_protocol["calibration_binding_digest"]
        )
        run_iteration(campaign)

    def test_digest_only_real_noise_band_cannot_reach_a_decision(self) -> None:
        campaign = self._new_campaign("digest-only-noise", {"kind": "fixture", "seed": 0})
        base_before = campaign.state["accepted_base_sha"]
        band = measure_noise(campaign, runs=2).to_dict()
        band.pop("sample_anchors")
        band["synthetic"] = False
        band["admission_receipt_digests"] = ["a" * 64, "b" * 64]
        campaign.config["noise_band"] = band
        campaign.save_config()

        started = start_iteration(campaign)
        worktree = Path(started["worktree"])
        self._commit_quality(worktree, "0.70\n")
        self._write_manifest(worktree, predicted=self.flipping[:2])
        result = run_iteration(campaign)

        self.assertEqual(result["decision"], "invalid")
        self.assertFalse(result["advanced_accepted_state"])
        self.assertEqual(campaign.state["accepted_base_sha"], base_before)
        report = json.loads(
            (campaign.iteration_dir(result["iteration"]) / "gate-report.json").read_text()
        )
        self.assertIn(
            "noise-band fields are not closed",
            report["rungs"][0]["detail"]["reason"],
        )

    def test_benchmark_preflight_rejects_simulated_identity_before_baseline(self) -> None:
        campaign = self._new_campaign("production", {"kind": "fixture", "seed": 0})
        campaign.config["identity"]["evidence_mode"] = "benchmark"
        with self.assertRaisesRegex(
            ProtocolError, "benchmark verifier admissions file is missing"
        ):
            start_iteration(campaign)
        self.assertEqual(campaign.current_iteration, 0)
        self.assertFalse(campaign.worktree_path.exists())
        self.assertFalse((campaign.iteration_dir(1) / "eval/dev_baseline").exists())


if __name__ == "__main__":
    unittest.main()
