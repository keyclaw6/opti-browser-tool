"""Unit tests for the v2 conductor primitives (post-review)."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from opti_eval.identity import LiveRunReceipt, digest_json
from opti_loop import fileguard, gitutil, lint, manifest, registration
from opti_loop.attribution import attribute
from opti_loop.compare import Comparison, NoiseBand, NoiseBandError, compare_runs, measure_noise_band
from opti_loop.conductor import _frozen_transfer_status
from opti_loop.evaluate import EvalRun
from opti_loop.protocol import ProtocolError, build_identity, normalize_candidate_allowlist
from opti_loop.verdict import Verdict

ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
       "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
ALLOWED_PREFIXES = ("harness/components/",)


class FrozenTransferStatusTest(unittest.TestCase):
    def test_due_closed_checkpoint_maps_supported_regressed_or_missing(self) -> None:
        state = {"accepted_iterations": [1, 2, 3, 4]}
        campaign = SimpleNamespace(campaign_id="campaign-a", state=state)
        base = "a" * 40
        result = {
            "campaign_id": "campaign-a",
            "accepted_sha": base,
            "accepted_iterations": [1, 2, 3, 4],
            "deltas_by_model": {"model-a": 0.2, "model-b": 0.1},
        }
        result["evidence_digest"] = digest_json(
            result, domain="opti.transfer-checkpoint-evidence.v1"
        )
        protocol = {
            "accepted_build": {"commit_sha": base},
            "execution": {
                "transfer": {"checkpoint_every": 5, "checkpoint_result": result}
            },
        }
        self.assertEqual(_frozen_transfer_status(campaign, protocol), "supported")
        result["deltas_by_model"] = {"model-a": -0.2, "model-b": 0.1}
        result["evidence_digest"] = digest_json(
            {key: value for key, value in result.items() if key != "evidence_digest"},
            domain="opti.transfer-checkpoint-evidence.v1",
        )
        self.assertEqual(_frozen_transfer_status(campaign, protocol), "regressed")
        result["evidence_digest"] = "f" * 64
        self.assertEqual(_frozen_transfer_status(campaign, protocol), "missing")
        result["evidence_digest"] = digest_json(
            {key: value for key, value in result.items() if key != "evidence_digest"},
            domain="opti.transfer-checkpoint-evidence.v1",
        )
        result["decision"] = "transfer_supported"
        self.assertEqual(_frozen_transfer_status(campaign, protocol), "missing")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=ENV)


def _seed_repo(tmp: Path) -> Path:
    repo = tmp / "repo"
    (repo / "harness/components/policy").mkdir(parents=True)
    (repo / "harness/components/policy/system_prompt.md").write_text("seed\n")
    (repo / "harness/components/policy/component.json").write_text(
        json.dumps(
            {
                "component": "policy",
                "version": "0.1.0-seed",
                "purpose": "Test policy fixture",
                "files": ["system_prompt.md"],
                "interfaces": [],
                "activation_events": ["x"],
                "emits": [],
            }
        )
        + "\n"
    )
    (repo / "harness/runtime").mkdir(parents=True)
    (repo / "harness/runtime/engine.py").write_text("VALUE = 1\n")
    (repo / "evals").mkdir()
    (repo / "evals/plane.txt").write_text("evaluation plane\n")
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    return repo


class FileGuardCommitDiffTest(unittest.TestCase):
    """F01: the guard is authoritative over base..candidate commit objects."""

    def _candidate(self, tmp: Path):
        repo = _seed_repo(tmp)
        base = gitutil.head_sha(repo)
        wt = tmp / "wt"
        gitutil.worktree_add(repo, wt, base)
        return repo, base, wt

    def test_allowed_committed_edit_passes(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            repo, base, wt = self._candidate(Path(t))
            (wt / "harness/components/policy/system_prompt.md").write_text("improved\n")
            _git(wt, "add", "-A")
            _git(wt, "commit", "-qm", "chg")
            cand = gitutil.head_sha(wt)
            report = fileguard.check_candidate(
                repo=repo,
                worktree=wt,
                base_sha=base,
                candidate_sha=cand,
                allowed_prefixes=ALLOWED_PREFIXES,
            )
            self.assertTrue(report.ok, report.to_dict())

    def test_committed_forbidden_edit_is_caught(self) -> None:
        # The exact F01 bypass: commit an eval-plane edit. The old working-tree
        # guard went blind after the commit; the commit-diff guard does not.
        with tempfile.TemporaryDirectory() as t:
            repo, base, wt = self._candidate(Path(t))
            (wt / "evals/plane.txt").write_text("tampered\n")
            (wt / "harness/components/policy/system_prompt.md").write_text("x\n")
            _git(wt, "add", "-A")
            _git(wt, "commit", "-qm", "sneaky")
            cand = gitutil.head_sha(wt)
            report = fileguard.check_candidate(
                repo=repo,
                worktree=wt,
                base_sha=base,
                candidate_sha=cand,
                allowed_prefixes=ALLOWED_PREFIXES,
            )
            self.assertFalse(report.ok)
            self.assertIn("evals/plane.txt", " ".join(report.violations))

    def test_uncommitted_edit_flags_dirty_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            repo, base, wt = self._candidate(Path(t))
            (wt / "harness/components/policy/system_prompt.md").write_text("uncommitted\n")
            report = fileguard.check_candidate(
                repo=repo,
                worktree=wt,
                base_sha=base,
                candidate_sha=base,
                allowed_prefixes=ALLOWED_PREFIXES,
            )
            self.assertFalse(report.ok)
            self.assertTrue(report.dirty_worktree)

    def test_manifest_untracked_is_tolerated(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            repo, base, wt = self._candidate(Path(t))
            (wt / "manifest.json").write_text("{}")
            report = fileguard.check_candidate(
                repo=repo,
                worktree=wt,
                base_sha=base,
                candidate_sha=base,
                allowed_prefixes=ALLOWED_PREFIXES,
            )
            self.assertTrue(report.ok, report.to_dict())

    def test_runtime_allowlist_is_authoritative(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            repo, base, wt = self._candidate(Path(t))
            (wt / "harness/runtime/engine.py").write_text("VALUE = 2\n")
            _git(wt, "add", "-A")
            _git(wt, "commit", "-qm", "runtime")
            report = fileguard.check_candidate(
                repo=repo,
                worktree=wt,
                base_sha=base,
                candidate_sha=gitutil.head_sha(wt),
                allowed_prefixes=("harness/runtime/",),
            )
            self.assertTrue(report.ok, report.to_dict())

    def test_build_identity_hashes_every_allowed_root(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            repo = _seed_repo(Path(t))
            head = gitutil.head_sha(repo)
            identity = build_identity(
                repo,
                commit_sha=head,
                role="accepted",
                candidate_allowlist=["harness/components/", "harness/runtime/"],
            )
            (repo / "harness/runtime/engine.py").write_text("VALUE = 9\n")
            changed = build_identity(
                repo,
                commit_sha=head,
                role="accepted",
                candidate_allowlist=["harness/components/", "harness/runtime/"],
            )
            self.assertNotEqual(
                identity["materialized_digest"], changed["materialized_digest"]
            )


class PathSafetyTest(unittest.TestCase):
    def test_rejects_traversal_absolute_and_nul(self) -> None:
        self.assertFalse(fileguard.path_is_safe(""))
        self.assertFalse(fileguard.path_is_safe("."))
        self.assertFalse(fileguard.path_is_safe("harness/./components/policy"))
        self.assertFalse(fileguard.path_is_safe("harness//components/policy"))
        self.assertFalse(fileguard.path_is_safe("harness/components/policy/../../../evals/x"))
        self.assertFalse(fileguard.path_is_safe("/etc/passwd"))
        self.assertFalse(fileguard.path_is_safe("a\x00b"))
        self.assertFalse(fileguard.path_is_safe("a\\b"))
        self.assertTrue(fileguard.path_is_safe("harness/components/policy/system_prompt.md"))

    def test_candidate_allowlist_has_one_normalized_nonoverlapping_authority(self) -> None:
        self.assertEqual(
            normalize_candidate_allowlist(
                ["harness/components/**", "harness/runtime/"],
            ),
            ["harness/components/", "harness/runtime/"],
        )
        with self.assertRaisesRegex(ProtocolError, "overlap"):
            normalize_candidate_allowlist(
                ["harness/**", "harness/components/**"],
            )
        for forbidden in (
            "evals/**",
            "eval_harness/**",
            "loop_harness/**",
            "judge_harness/**",
            "schemas/**",
            "harness/activation/**",
            "harness/admission/**",
            "harness/contracts/**",
            "harness/decision/**",
            "harness/evaluator/**",
            "harness/evidence/**",
            "harness/executor/**",
            "harness/gates/**",
            "harness/infra/**",
            "harness/lanes/**",
            "harness/model/**",
            "harness/oracle/**",
            "harness/protocol/**",
            "harness/reset/**",
            "harness/safety/**",
            "harness/schemas/**",
            "harness/secrets/**",
            "harness/setup/**",
            "harness/store/**",
            "harness/tasks/**",
            "harness/tracer/**",
            "harness/verifier/**",
        ):
            with self.subTest(forbidden=forbidden):
                with self.assertRaises(ProtocolError):
                    normalize_candidate_allowlist([forbidden])


def _valid_manifest(**over) -> dict:
    m = {
        "schema_version": "0.1-draft", "experiment_id": "e", "status": "proposed",
        "hypothesis": "h", "trace_evidence": [{"run_id": "r", "event_id": "n"}],
        "suspected_root_cause": "c",
        "treatment": {"description": "d", "change_scope": ["harness/components/policy/system_prompt.md"],
                      "activation_evidence": ["a"]},
        "baseline_ref": "b", "fixed_variables": {"executor_model": "x"},
        "predicted_improvements": [{"failure_class": "f", "tasks": ["t-1"]}],
        "regression_risks": [{"failure_class": "n", "tasks": []}],
        "evaluation_plan": {"task_sets": ["smoke"], "repetitions": {}, "pairing": "paired", "budget": {}},
        "acceptance_criteria": {"primary": "E5"}, "target_component": "policy", "cluster_ref": "stub/x/failed",
    }
    m.update(over)
    return m


class ManifestTest(unittest.TestCase):
    def _check(self, m, **kw):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "m.json"
            p.write_text(json.dumps(m))
            allowed_prefixes = kw.pop("allowed_prefixes", ALLOWED_PREFIXES)
            return manifest.load_and_validate(
                p,
                allowed_prefixes=allowed_prefixes,
                **kw,
            )

    def test_valid(self) -> None:
        self.assertTrue(self._check(_valid_manifest(), changed_files=["harness/components/policy/system_prompt.md"]).ok)

    def test_traversal_scope_rejected(self) -> None:  # F03
        m = _valid_manifest()
        m["treatment"]["change_scope"] = ["harness/components/policy/../../../evals/plane.txt"]
        self.assertFalse(self._check(m, changed_files=[]).ok)

    def test_cross_component_and_undeclared_rejected(self) -> None:
        m = _valid_manifest()
        m["treatment"]["change_scope"] = ["harness/components/actions/a.md"]
        self.assertFalse(self._check(m, changed_files=[]).ok)
        self.assertFalse(self._check(_valid_manifest(),
                         changed_files=["harness/components/policy/system_prompt.md",
                                        "harness/components/policy/undeclared.md"]).ok)

    def test_target_component_is_attribution_not_path_authority(self) -> None:
        changed = "harness/components/actions/action_contract.md"
        candidate = _valid_manifest()
        candidate["target_component"] = "policy"
        candidate["treatment"]["change_scope"] = [changed]
        report = self._check(candidate, changed_files=[changed])
        self.assertTrue(report.ok, report.errors)

    def test_runtime_scope_must_exactly_equal_full_diff(self) -> None:
        runtime_path = "harness/runtime/engine.py"
        candidate = _valid_manifest()
        candidate["treatment"]["change_scope"] = [runtime_path]
        allowed = ("harness/components/", "harness/runtime/")
        self.assertTrue(
            self._check(
                candidate,
                allowed_prefixes=allowed,
                changed_files=[runtime_path],
            ).ok
        )
        missing = self._check(
            candidate,
            allowed_prefixes=allowed,
            changed_files=[runtime_path, "harness/components/policy/system_prompt.md"],
        )
        self.assertIn("changed file not declared", " ".join(missing.errors))
        unchanged = self._check(
            candidate,
            allowed_prefixes=allowed,
            changed_files=[],
        )
        self.assertIn("declares unchanged file", " ".join(unchanged.errors))

    def test_optimizer_attribution_rejected(self) -> None:
        self.assertFalse(self._check(_valid_manifest(attribution={"verdict": "keep"}), changed_files=[]).ok)

    def test_divergent_enforcement(self) -> None:  # F16
        self.assertFalse(self._check(_valid_manifest(), changed_files=["harness/components/policy/system_prompt.md"],
                                     divergent=True).ok)  # non-divergent cluster_ref in divergent iter
        ok = self._check(_valid_manifest(cluster_ref="divergent/try-vision"),
                         changed_files=["harness/components/policy/system_prompt.md"], divergent=True)
        self.assertTrue(ok.ok, ok.errors)


def _run(statuses, *, eligible=True) -> EvalRun:
    inval = {"invalid", "error", "skipped"}
    valid = not any(s in inval for s in statuses.values())
    passed = sum(1 for s in statuses.values() if s == "passed")
    results = {
        task_id: {
            "run_id": "r",
            "task_id": task_id,
            "status": status,
        }
        for task_id, status in statuses.items()
    }
    return EvalRun(output_dir=Path("."), suite_name="t",
                   summary={"run_valid": valid, "acceptance_decision_eligible": eligible and valid,
                            "strict_success_rate": passed / len(statuses) if statuses else None},
                   statuses=dict(statuses), rewards={}, run_id="r", results=results)


def _benchmark_run(statuses, *, token: str, admitted: bool) -> EvalRun:
    run = _run(statuses)
    run.run_id = f"run-{token}"
    live = LiveRunReceipt(
        protocol_digest="1" * 64,
        run_digest=token * 64,
        adapter_digest="2" * 64,
        evidence_mode="benchmark",
    )
    run.live_receipt = live
    if admitted:
        payload = {
            "schema_version": "0.1.0",
            "protocol_digest": live.protocol_digest,
            "run_digest": live.run_digest,
            "adapter_digest": live.adapter_digest,
            "run_id": run.run_id,
            "task_bundle_digest": "3" * 64,
            "t1_flag_count": 0,
        }
        run.admission_receipt = {
            **payload,
            "receipt_digest": digest_json(
                payload, domain="opti.ar003-admission-receipt.v1"
            ),
        }
    return run


class CompareTest(unittest.TestCase):
    def test_benchmark_pair_requires_both_matching_admission_receipts(self) -> None:
        baseline = _benchmark_run({"a": "failed"}, token="a", admitted=False)
        treatment = _benchmark_run({"a": "passed"}, token="b", admitted=True)
        rejected = compare_runs(baseline, treatment)
        self.assertFalse(rejected.eligible)
        self.assertFalse(rejected.simulated)
        self.assertIn("both benchmark arms", " ".join(rejected.reasons))

        baseline = _benchmark_run({"a": "failed"}, token="a", admitted=True)
        accepted = compare_runs(baseline, treatment)
        self.assertTrue(accepted.eligible, accepted.reasons)
        self.assertEqual(accepted.fixed, ["a"])

    def test_strict_rejects_invalidating(self) -> None:
        self.assertFalse(compare_runs(_run({"a": "passed", "b": "invalid"}),
                                      _run({"a": "passed", "b": "passed"}), policy="strict").eligible)

    def test_quorum_whole_family_quarantine_is_ineligible(self) -> None:  # F14
        base = _run({"a": "failed", "b": "passed"})
        treat = _run({"a": "passed", "b": "passed"})
        sources = {"a": "src1", "b": "src2"}
        # Quarantine every task of src2 -> that family vanishes -> ineligible,
        # and coverage is measured against the ORIGINAL 2-task universe.
        cmp = compare_runs(base, treat, policy="quorum", quorum_coverage_floor=0.4,
                           task_sources=sources, quarantined={"b"})
        self.assertFalse(cmp.eligible)
        self.assertTrue(any("absent" in r for r in cmp.reasons))

    def test_simulated_flag(self) -> None:
        self.assertTrue(compare_runs(_run({"a": "passed"}, eligible=False),
                                     _run({"a": "passed"}, eligible=False)).simulated)


class NoiseBandTest(unittest.TestCase):
    def _real_band(self, root: Path) -> NoiseBand:
        first = _benchmark_run(
            {"a": "passed", "b": "failed"}, token="a", admitted=True
        )
        second = _benchmark_run(
            {"a": "passed", "b": "failed"}, token="b", admitted=True
        )
        first.output_dir = root / "noise/run-00"
        second.output_dir = root / "noise/run-01"
        return measure_noise_band(
            [first, second],
            synthetic=False,
            run_identity="a" * 64,
            evidence_root=root,
        )

    def test_rejects_absurd_values(self) -> None:  # F07
        base = {
            "aggregate_margin": 0.1,
            "max_benign_flips": 1,
            "sample_runs": 2,
            "synthetic": True,
            "task_count": 20,
            "run_identity": "a" * 64,
            "sample_anchors": [],
        }
        for bad in (
            {**base, "aggregate_margin": 99},
            {**base, "max_benign_flips": 999999},
            {**base, "sample_runs": 0},
        ):
            with self.assertRaises(NoiseBandError):
                NoiseBand.from_dict(bad)

    def test_persisted_evidence_class_and_admissions_are_type_strict(self) -> None:
        base = {
            "aggregate_margin": 0.1,
            "max_benign_flips": 1,
            "sample_runs": 2,
            "synthetic": True,
            "task_count": 2,
            "run_identity": "a" * 64,
            "sample_anchors": [],
        }
        with self.assertRaisesRegex(NoiseBandError, "synthetic marker"):
            NoiseBand.from_dict({**base, "synthetic": 1})
        with self.assertRaisesRegex(NoiseBandError, "must be an array"):
            NoiseBand.from_dict(
                {**base, "synthetic": False, "sample_anchors": "not-an-array"}
            )
        with self.assertRaisesRegex(NoiseBandError, "one AR-003 anchor"):
            NoiseBand.from_dict({**base, "synthetic": False})
        with self.assertRaisesRegex(NoiseBandError, "fields are not closed"):
            NoiseBand.from_dict({**base, "admission_receipt_digests": []})

    def test_real_band_round_trip_has_closed_full_unique_anchors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            band = self._real_band(Path(tmp))
            persisted = band.to_dict()
            reloaded = NoiseBand.from_dict(persisted)
            self.assertEqual(reloaded.to_dict(), persisted)
            self.assertFalse(reloaded.anchors_validated)

            absolute = json.loads(json.dumps(persisted))
            absolute["sample_anchors"][0]["evidence_dir"] = "/tmp/run-00"
            with self.assertRaisesRegex(NoiseBandError, "unsafe"):
                NoiseBand.from_dict(absolute)

            traversal = json.loads(json.dumps(persisted))
            traversal["sample_anchors"][0]["evidence_dir"] = "noise/../run-00"
            with self.assertRaisesRegex(NoiseBandError, "canonical"):
                NoiseBand.from_dict(traversal)

            forged = json.loads(json.dumps(persisted))
            forged["sample_anchors"][0]["admission_receipt"][
                "task_bundle_digest"
            ] = "f" * 64
            with self.assertRaisesRegex(NoiseBandError, "receipt digest"):
                NoiseBand.from_dict(forged)

            duplicate = json.loads(json.dumps(persisted))
            duplicate["sample_anchors"][1] = duplicate["sample_anchors"][0]
            with self.assertRaisesRegex(NoiseBandError, "must be unique"):
                NoiseBand.from_dict(duplicate)

    def test_measure_requires_identical_task_set(self) -> None:
        with self.assertRaises(NoiseBandError):
            measure_noise_band([_run({"a": "passed"}), _run({"a": "passed", "b": "failed"})], synthetic=True)

    def test_identity_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            band = self._real_band(Path(tmp))
        self.assertTrue(band.matches_identity("a" * 64))
        self.assertFalse(band.matches_identity("b" * 64))

    def test_real_noise_rejects_any_unadmitted_sample(self) -> None:
        admitted = _benchmark_run({"a": "passed"}, token="a", admitted=True)
        unadmitted = _benchmark_run({"a": "passed"}, token="b", admitted=False)
        with self.assertRaisesRegex(NoiseBandError, "every benchmark noise sample"):
            measure_noise_band(
                [admitted, unadmitted],
                synthetic=False,
                run_identity="a" * 64,
                evidence_root=Path("."),
            )


class CandidateBoundaryTest(unittest.TestCase):
    def test_lint_requires_the_frozen_allowlist(self) -> None:
        with self.assertRaises(TypeError):
            lint.scan_tree(Path("."))

    def test_lint_scans_every_frozen_allowed_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "harness/components/policy").mkdir(parents=True)
            (root / "harness/runtime").mkdir(parents=True)
            (root / "harness/components/policy/prompt.md").write_text("generic\n")
            (root / "harness/runtime/engine.py").write_text("generic = True\n")
            report = lint.scan_tree(
                root,
                allowed_prefixes=("harness/components/", "harness/runtime/"),
                vocabulary={"task_ids": set(), "sources": set(), "hosts": set()},
            )
            self.assertTrue(report.ok, [finding.to_dict() for finding in report.findings])
            self.assertEqual(report.scanned_files, 2)

    def test_registration_uses_changed_component_not_target_label(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _seed_repo(Path(tmp))
            changed = "harness/components/policy/system_prompt.md"
            report = registration.check_change_registered(
                repo, "actions", [changed]
            )
            self.assertTrue(report.ok, report.errors)
            self.assertEqual(report.checked_components, 1)


class AttributionTest(unittest.TestCase):
    def test_metric_labels_and_shotgun(self) -> None:  # F09
        m = _valid_manifest(predicted_improvements=[{"failure_class": "f", "tasks": [f"t-{i}" for i in range(140)]}])
        cmp = Comparison(policy="strict", eligible=True, fixed=["t-1"], regressed=[])
        attr = attribute(m, cmp)
        # precision = verified/predicted = 1/140 (low — shotgun exposed), not 1.0
        self.assertEqual(attr.prediction_precision, round(1 / 140, 4))
        self.assertEqual(attr.flip_recall, 1.0)
        self.assertEqual(attr.verdict, "keep")

    def test_revert_when_no_verified_fix(self) -> None:
        m = _valid_manifest(predicted_improvements=[{"failure_class": "f", "tasks": ["t-9"]}])
        attr = attribute(m, Comparison(policy="strict", eligible=True, fixed=[], regressed=["t-3"]))
        self.assertEqual(attr.verdict, "revert")


class EligibilityTest(unittest.TestCase):
    """F10: benchmark eligibility requires admission; auto-T1 routes to quarantine."""

    def test_legacy_registry_replay_cannot_reach_benchmark_eligibility(self) -> None:
        from opti_eval.summary import summarize_results
        from opti_eval.util import atomic_write_json, write_jsonl
        from opti_loop.eligibility import assess
        from opti_loop.evaluate import load_run

        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            results = [{
                "task_id": "a",
                "source": "test-source",
                "status": "passed",
                "reward": 1.0,
                "metadata": {"benchmark_reportable": True},
            }]
            write_jsonl(tmp / "results.jsonl", results)
            summary = summarize_results(results)
            summary.update({
                "run_valid": True,
                "benchmark_reportable": True,
                "acceptance_decision_eligible": True,
            })
            atomic_write_json(tmp / "summary.json", summary)
            atomic_write_json(
                tmp / "run.json",
                {"adapter": {"name": "registry", "benchmark_reportable": True}},
            )
            (tmp / "adm.jsonl").write_text(json.dumps({
                "verifier_id": "v",
                "task_id": "a",
                "verifier_checksum": "c",
                "admitted": True,
            }) + "\n")

            run = load_run(tmp, "test")
            self.assertFalse(run.acceptance_decision_eligible)
            eligibility = assess(
                run=run,
                run_dir=tmp,
                expected_receipt=LiveRunReceipt(
                    protocol_digest="0" * 64,
                    run_digest="1" * 64,
                    adapter_digest="2" * 64,
                    evidence_mode="simulated",
                ),
                task_records={},
                admissions_path=tmp / "adm.jsonl",
                quarantine_path=tmp / "q.jsonl",
            )
            self.assertEqual(eligibility.evidence_class, "simulated")
            self.assertFalse(eligibility.acceptance_eligible)

    def test_malformed_persisted_result_makes_loop_run_invalid_without_crashing(self) -> None:
        from opti_eval.util import atomic_write_json, write_jsonl
        from opti_loop.evaluate import load_run

        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            write_jsonl(tmp / "results.jsonl", [{
                "task_id": "a",
                "source": "test-source",
                "status": "PASSED",
                "metadata": {"benchmark_reportable": True},
            }])
            atomic_write_json(tmp / "summary.json", {
                "run_valid": True,
                "benchmark_reportable": True,
                "acceptance_decision_eligible": True,
            })
            atomic_write_json(tmp / "run.json", {
                "adapter": {"name": "diagnostic-test", "benchmark_reportable": True},
            })

            run = load_run(tmp, "test")
            self.assertFalse(run.run_valid)
            self.assertFalse(run.acceptance_decision_eligible)
            self.assertEqual(run.statuses, {})
            self.assertTrue(run.summary["replay_errors"])

    def test_unadmitted_synthetic_run_is_not_benchmark(self) -> None:
        from opti_loop.eligibility import assess
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            receipt = LiveRunReceipt(
                protocol_digest="0" * 64,
                run_digest="1" * 64,
                adapter_digest="2" * 64,
                evidence_mode="simulated",
            )
            run = _run({"a": "passed"}, eligible=True)
            run.live_receipt = receipt
            elig = assess(
                run=run,
                run_dir=tmp,
                expected_receipt=receipt,
                task_records={},
                admissions_path=tmp / "adm.jsonl",
                quarantine_path=tmp / "q.jsonl",
            )
            self.assertEqual(elig.evidence_class, "simulated")
            self.assertFalse(elig.acceptance_eligible)

    def test_admitted_incomplete_trace_is_integrity_invalid(self) -> None:
        from opti_loop.eligibility import assess
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            (tmp / "adm.jsonl").write_text(json.dumps(
                {"verifier_id": "v", "task_id": "a", "verifier_checksum": "c", "admitted": True}) + "\n")
            # A passed run whose trace shows a DELETE with no expected mutation.
            trace_dir = tmp / "tasks" / "a"
            trace_dir.mkdir(parents=True)
            (trace_dir / "trace.jsonl").write_text("\n".join([
                json.dumps({"run_id": "r", "event_id": "e1", "sequence": 1, "actor": "browser",
                            "event_type": "browser_state", "visibility": ["judge"], "payload": {}}),
                json.dumps({"run_id": "r", "event_id": "e2", "sequence": 2, "actor": "browser",
                            "event_type": "network_event", "visibility": ["judge"],
                            "payload": {"method": "DELETE", "url": "/x"}}),
            ]) + "\n")
            run = _run({"a": "passed"}, eligible=True)
            receipt = LiveRunReceipt(
                protocol_digest="0" * 64,
                run_digest="1" * 64,
                adapter_digest="2" * 64,
                evidence_mode="benchmark",
            )
            run.live_receipt = receipt
            elig = assess(
                run=run,
                run_dir=tmp,
                expected_receipt=receipt,
                task_records={"a": {"state_change_expected": False}},
                admissions_path=tmp / "adm.jsonl",
                quarantine_path=tmp / "q.jsonl",
            )
            self.assertEqual(elig.evidence_class, "simulated")
            self.assertEqual(elig.integrity_status, "invalid")
            self.assertFalse(elig.acceptance_eligible)


class VerdictTest(unittest.TestCase):
    def test_only_benchmark_accept_advances(self) -> None:  # F04
        self.assertTrue(Verdict("accepted", "benchmark").advances_accepted_state)
        self.assertFalse(Verdict("accepted", "simulated").advances_accepted_state)
        self.assertFalse(Verdict("rejected", "benchmark").advances_accepted_state)
        self.assertFalse(Verdict("inconclusive", "benchmark").advances_accepted_state)
        self.assertEqual(Verdict("accepted", "simulated").label, "simulated:accepted")


if __name__ == "__main__":
    unittest.main()
