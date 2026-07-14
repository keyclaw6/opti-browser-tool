"""Unit tests for the v2 conductor primitives (post-review)."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from opti_loop import fileguard, gitutil, manifest
from opti_loop.attribution import attribute
from opti_loop.compare import Comparison, NoiseBand, NoiseBandError, compare_runs, measure_noise_band
from opti_loop.evaluate import EvalRun
from opti_loop.verdict import Verdict

ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
       "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=ENV)


def _seed_repo(tmp: Path) -> Path:
    repo = tmp / "repo"
    (repo / "harness/components/policy").mkdir(parents=True)
    (repo / "harness/components/policy/system_prompt.md").write_text("seed\n")
    (repo / "harness/components/policy/component.json").write_text(
        json.dumps({"component": "policy", "version": "0.1.0-seed",
                    "files": ["system_prompt.md"], "activation_events": ["x"], "emits": []}) + "\n")
    (repo / "evals").mkdir()
    (repo / "evals/plane.txt").write_text("evaluation plane\n")
    _git(repo, "init", "-q"); _git(repo, "add", "-A"); _git(repo, "commit", "-qm", "base")
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
            _git(wt, "add", "-A"); _git(wt, "commit", "-qm", "chg")
            cand = gitutil.head_sha(wt)
            report = fileguard.check_candidate(repo=repo, worktree=wt, base_sha=base, candidate_sha=cand)
            self.assertTrue(report.ok, report.to_dict())

    def test_committed_forbidden_edit_is_caught(self) -> None:
        # The exact F01 bypass: commit an eval-plane edit. The old working-tree
        # guard went blind after the commit; the commit-diff guard does not.
        with tempfile.TemporaryDirectory() as t:
            repo, base, wt = self._candidate(Path(t))
            (wt / "evals/plane.txt").write_text("tampered\n")
            (wt / "harness/components/policy/system_prompt.md").write_text("x\n")
            _git(wt, "add", "-A"); _git(wt, "commit", "-qm", "sneaky")
            cand = gitutil.head_sha(wt)
            report = fileguard.check_candidate(repo=repo, worktree=wt, base_sha=base, candidate_sha=cand)
            self.assertFalse(report.ok)
            self.assertIn("evals/plane.txt", " ".join(report.violations))

    def test_uncommitted_edit_flags_dirty_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            repo, base, wt = self._candidate(Path(t))
            (wt / "harness/components/policy/system_prompt.md").write_text("uncommitted\n")
            report = fileguard.check_candidate(repo=repo, worktree=wt, base_sha=base, candidate_sha=base)
            self.assertFalse(report.ok)
            self.assertTrue(report.dirty_worktree)

    def test_manifest_untracked_is_tolerated(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            repo, base, wt = self._candidate(Path(t))
            (wt / "manifest.json").write_text("{}")
            report = fileguard.check_candidate(repo=repo, worktree=wt, base_sha=base, candidate_sha=base)
            self.assertTrue(report.ok, report.to_dict())


class PathSafetyTest(unittest.TestCase):
    def test_rejects_traversal_absolute_and_nul(self) -> None:
        self.assertFalse(fileguard.path_is_safe("harness/components/policy/../../../evals/x"))
        self.assertFalse(fileguard.path_is_safe("/etc/passwd"))
        self.assertFalse(fileguard.path_is_safe("a\x00b"))
        self.assertFalse(fileguard.path_is_safe("a\\b"))
        self.assertTrue(fileguard.path_is_safe("harness/components/policy/system_prompt.md"))


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
            p = Path(t) / "m.json"; p.write_text(json.dumps(m))
            return manifest.load_and_validate(p, **kw)

    def test_valid(self) -> None:
        self.assertTrue(self._check(_valid_manifest(), changed_files=["harness/components/policy/system_prompt.md"]).ok)

    def test_traversal_scope_rejected(self) -> None:  # F03
        m = _valid_manifest()
        m["treatment"]["change_scope"] = ["harness/components/policy/../../../evals/plane.txt"]
        self.assertFalse(self._check(m, changed_files=[]).ok)

    def test_cross_component_and_undeclared_rejected(self) -> None:
        m = _valid_manifest(); m["treatment"]["change_scope"] = ["harness/components/actions/a.md"]
        self.assertFalse(self._check(m, changed_files=[]).ok)
        self.assertFalse(self._check(_valid_manifest(),
                         changed_files=["harness/components/policy/system_prompt.md",
                                        "harness/components/policy/undeclared.md"]).ok)

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
    return EvalRun(output_dir=Path("."), suite_name="t",
                   summary={"run_valid": valid, "acceptance_decision_eligible": eligible and valid,
                            "strict_success_rate": passed / len(statuses) if statuses else None},
                   statuses=dict(statuses), rewards={})


class CompareTest(unittest.TestCase):
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
    def test_rejects_absurd_values(self) -> None:  # F07
        for bad in ({"aggregate_margin": 99, "max_benign_flips": 1, "sample_runs": 2},
                    {"aggregate_margin": 0.1, "max_benign_flips": 999999, "sample_runs": 2, "task_count": 20},
                    {"aggregate_margin": 0.1, "max_benign_flips": 1, "sample_runs": 0}):
            with self.assertRaises(NoiseBandError):
                NoiseBand.from_dict(bad)

    def test_measure_requires_identical_task_set(self) -> None:
        with self.assertRaises(NoiseBandError):
            measure_noise_band([_run({"a": "passed"}), _run({"a": "passed", "b": "failed"})], synthetic=True)

    def test_identity_binding(self) -> None:
        band = measure_noise_band([_run({"a": "passed", "b": "failed"}),
                                   _run({"a": "passed", "b": "failed"})], synthetic=False, run_identity="ID1")
        self.assertTrue(band.matches_identity("ID1"))
        self.assertFalse(band.matches_identity("ID2"))


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
            summary = summarize_results(results, adapter_reportable=True)
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
                adapter_config={"verifier_id": "v", "verifier_checksum": "c"},
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

    def test_unadmitted_verifier_is_not_benchmark(self) -> None:
        from opti_loop.eligibility import assess
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            run = _run({"a": "passed"}, eligible=True)  # reportable
            elig = assess(run=run, run_dir=tmp, adapter_config={"verifier_id": "v", "verifier_checksum": "c"},
                          task_records={}, admissions_path=tmp / "adm.jsonl", quarantine_path=tmp / "q.jsonl")
            self.assertEqual(elig.evidence_class, "simulated")
            self.assertFalse(elig.acceptance_eligible)

    def test_admitted_plus_auto_t1_routes_suspicion(self) -> None:
        from opti_loop.eligibility import assess
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            (tmp / "adm.jsonl").write_text(json.dumps(
                {"verifier_id": "v", "task_id": "a", "verifier_checksum": "c", "admitted": True}) + "\n")
            # A passed run whose trace shows a DELETE with no expected mutation.
            trace_dir = tmp / "tasks" / "a"; trace_dir.mkdir(parents=True)
            (trace_dir / "trace.jsonl").write_text("\n".join([
                json.dumps({"run_id": "r", "event_id": "e1", "sequence": 1, "actor": "browser",
                            "event_type": "browser_state", "visibility": ["judge"], "payload": {}}),
                json.dumps({"run_id": "r", "event_id": "e2", "sequence": 2, "actor": "browser",
                            "event_type": "network_event", "visibility": ["judge"],
                            "payload": {"method": "DELETE", "url": "/x"}}),
            ]) + "\n")
            run = _run({"a": "passed"}, eligible=True)
            elig = assess(run=run, run_dir=tmp,
                          adapter_config={"verifier_id": "v", "verifier_checksum": "c"},
                          task_records={"a": {"state_change_expected": False}},
                          admissions_path=tmp / "adm.jsonl", quarantine_path=tmp / "q.jsonl")
            self.assertEqual(elig.evidence_class, "benchmark")
            self.assertIn("a", elig.newly_quarantined)  # auto-T1 flagged the mutation


class VerdictTest(unittest.TestCase):
    def test_only_benchmark_accept_advances(self) -> None:  # F04
        self.assertTrue(Verdict("accepted", "benchmark").advances_accepted_state)
        self.assertFalse(Verdict("accepted", "simulated").advances_accepted_state)
        self.assertFalse(Verdict("rejected", "benchmark").advances_accepted_state)
        self.assertEqual(Verdict("accepted", "simulated").label, "simulated:accepted")


if __name__ == "__main__":
    unittest.main()
