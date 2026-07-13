"""Unit tests for the loop conductor's deterministic pieces."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from opti_loop import attribution as attribution_mod
from opti_loop import fileguard, lint, manifest
from opti_loop.compare import Comparison, NoiseBand
from opti_loop.evaluate import EvalRun


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"},
    )


def _make_repo(tmp: Path) -> Path:
    repo = tmp / "repo"
    (repo / "harness" / "components" / "policy").mkdir(parents=True)
    (repo / "harness" / "components" / "policy" / "system_prompt.md").write_text("seed\n")
    (repo / "evals").mkdir()
    (repo / "other.txt").write_text("infrastructure\n")
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "seed")
    return repo


class FileGuardTest(unittest.TestCase):
    def test_allows_component_edits_and_rejects_infrastructure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_repo(Path(tmp))
            (repo / "harness/components/policy/system_prompt.md").write_text("edited\n")
            report = fileguard.check(repo)
            self.assertTrue(report.ok, report.violations)

            (repo / "other.txt").write_text("tampered\n")
            report = fileguard.check(repo)
            self.assertEqual(report.violations, ["other.txt"])

    def test_untracked_files_are_caught_and_baseline_is_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_repo(Path(tmp))
            (repo / "evals" / "sneaky.json").write_text("{}\n")
            report = fileguard.check(repo)
            self.assertIn("evals/sneaky.json", report.violations)
            report = fileguard.check(repo, baseline_paths={"evals/sneaky.json"})
            self.assertTrue(report.ok)


class LintTest(unittest.TestCase):
    def test_flags_task_ids_sources_and_hosts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "evals/catalog").mkdir(parents=True)
            (repo / "evals/catalog/tasks.jsonl").write_text(
                json.dumps(
                    {
                        "id": "webarena-verified-423",
                        "source": "webarena_verified",
                        "upstream": {"url": "https://wa-host.example.org/task"},
                    }
                )
                + "\n"
            )
            target = repo / "harness/components/skills"
            target.mkdir(parents=True)
            (target / "bad.md").write_text(
                "if task == 'webarena-verified-423': shortcut()\n"
                "generic recovery logic\n"
                "visit https://wa-host.example.org/login first\n"
            )
            report = lint.scan_files(repo, ["harness/components/skills/bad.md"])
            kinds = {finding.kind for finding in report.findings}
            self.assertEqual(kinds, {"task_id", "source_token", "benchmark_host"})

            (target / "good.md").write_text("wait for network idle before clicking\n")
            report = lint.scan_files(repo, ["harness/components/skills/good.md"])
            self.assertTrue(report.ok)


def _valid_manifest() -> dict:
    return {
        "schema_version": "0.1-draft",
        "experiment_id": "exp-t-1",
        "status": "proposed",
        "hypothesis": "raising policy quality fixes hash-band tasks",
        "trace_evidence": [{"run_id": "iter-0001", "event_id": "n/a", "finding": "x"}],
        "suspected_root_cause": "policy quality too low",
        "treatment": {
            "description": "raise quality",
            "change_scope": ["harness/components/policy/quality.txt"],
            "activation_evidence": ["quality file read by adapter"],
        },
        "baseline_ref": "iter-0001",
        "fixed_variables": {"executor_model": "fixture"},
        "predicted_improvements": [{"failure_class": "hash-band", "tasks": ["t-1"]}],
        "regression_risks": [{"failure_class": "none-known", "tasks": []}],
        "evaluation_plan": {"task_sets": ["smoke"], "repetitions": {}, "pairing": "paired", "budget": {}},
        "acceptance_criteria": {"primary": "E5"},
        "target_component": "policy",
        "cluster_ref": "stub/x/failed",
    }


class ManifestTest(unittest.TestCase):
    def test_valid_manifest_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text(json.dumps(_valid_manifest()))
            report = manifest.load_and_validate(
                path, changed_files=["harness/components/policy/quality.txt"]
            )
            self.assertTrue(report.ok, report.errors)

    def test_cross_component_scope_rejected(self) -> None:
        bad = _valid_manifest()
        bad["treatment"]["change_scope"] = ["harness/components/actions/a.md"]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text(json.dumps(bad))
            report = manifest.load_and_validate(path, changed_files=[])
            self.assertFalse(report.ok)

    def test_undeclared_change_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text(json.dumps(_valid_manifest()))
            report = manifest.load_and_validate(
                path,
                changed_files=[
                    "harness/components/policy/quality.txt",
                    "harness/components/policy/undeclared.md",
                ],
            )
            self.assertFalse(report.ok)

    def test_optimizer_written_attribution_rejected(self) -> None:
        bad = _valid_manifest()
        bad["attribution"] = {"verdict": "keep"}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text(json.dumps(bad))
            report = manifest.load_and_validate(path, changed_files=[])
            self.assertFalse(report.ok)


def _run(statuses: dict[str, str], *, eligible: bool = True) -> EvalRun:
    invalidating = {"invalid", "error", "skipped"}
    run_valid = not any(status in invalidating for status in statuses.values())
    passed = sum(1 for s in statuses.values() if s == "passed")
    return EvalRun(
        output_dir=Path("."),
        suite_name="t",
        summary={
            "run_valid": run_valid,
            "acceptance_decision_eligible": eligible and run_valid,
            "strict_success_rate": passed / len(statuses) if statuses else None,
        },
        statuses=dict(statuses),
        rewards={},
    )


class CompareTest(unittest.TestCase):
    def test_strict_policy_rejects_invalidating_results(self) -> None:
        from opti_loop.compare import compare_runs

        base = _run({"a": "passed", "b": "invalid"})
        treat = _run({"a": "passed", "b": "passed"})
        comparison = compare_runs(base, treat, policy="strict")
        self.assertFalse(comparison.eligible)

    def test_quorum_policy_uses_valid_intersection(self) -> None:
        from opti_loop.compare import compare_runs

        base = _run({"a": "failed", "b": "passed", "c": "invalid"})
        treat = _run({"a": "passed", "b": "passed", "c": "failed"})
        comparison = compare_runs(
            base, treat, policy="quorum", quorum_coverage_floor=0.5
        )
        self.assertTrue(comparison.eligible)
        self.assertEqual(comparison.fixed, ["a"])
        self.assertEqual(comparison.regressed, [])

    def test_fixture_runs_are_marked_simulated(self) -> None:
        from opti_loop.compare import compare_runs

        base = _run({"a": "passed"}, eligible=False)
        treat = _run({"a": "passed"}, eligible=False)
        comparison = compare_runs(base, treat)
        self.assertTrue(comparison.simulated)


class AttributionTest(unittest.TestCase):
    def test_verdicts(self) -> None:
        m = _valid_manifest()

        keep = attribution_mod.attribute(
            m, Comparison(policy="strict", eligible=True, fixed=["t-1"], regressed=[])
        )
        self.assertEqual(keep.verdict, "keep")

        partial = attribution_mod.attribute(
            m, Comparison(policy="strict", eligible=True, fixed=["t-9"], regressed=[])
        )
        self.assertEqual(partial.verdict, "partial")

        revert = attribution_mod.attribute(
            m, Comparison(policy="strict", eligible=True, fixed=[], regressed=["t-3"])
        )
        self.assertEqual(revert.verdict, "revert")
        self.assertEqual(revert.materialized_regressions, ["t-3"])


class NoiseBandTest(unittest.TestCase):
    def test_roundtrip(self) -> None:
        band = NoiseBand(aggregate_margin=0.05, max_benign_flips=2, sample_runs=3, synthetic=True)
        self.assertEqual(NoiseBand.from_dict(band.to_dict()).aggregate_margin, 0.05)


if __name__ == "__main__":
    unittest.main()


class CompareCampaignsTest(unittest.TestCase):
    def test_non_comparable_configs_are_flagged(self) -> None:
        from opti_loop.campaign import init_campaign
        from opti_loop.conductor import compare_campaigns

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_campaign(repo, "a", overrides={"suites": {"dev": "smoke", "smoke": "smoke", "regression": "regression"}})
            init_campaign(repo, "b", overrides={"suites": {"dev": "primary", "smoke": "smoke", "regression": "regression"}})
            report = compare_campaigns(repo, ["a", "b"])
            self.assertFalse(report["comparable"])
            self.assertIn("must not be ranked", report["non_comparable_reason"])
            init_campaign(repo, "c", overrides={"suites": {"dev": "smoke", "smoke": "smoke", "regression": "regression"}})
            report = compare_campaigns(repo, ["a", "c"])
            self.assertTrue(report["comparable"])
            self.assertTrue((repo / "campaigns" / "cross-campaign-report.json").is_file())
