"""CLI repository-root discovery tests."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from opti_loop.campaign import load_campaign
from opti_loop.cli import _repo_root, main

REPO_ROOT = Path(os.environ["OPTI_BROWSER_REPO_ROOT"])
GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "CLI test",
    "GIT_AUTHOR_EMAIL": "cli@test",
    "GIT_COMMITTER_NAME": "CLI test",
    "GIT_COMMITTER_EMAIL": "cli@test",
}


@contextmanager
def _cwd(path: Path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def _seed_repo(path: Path) -> Path:
    repo = path / "repo"
    (repo / "evals/catalog").mkdir(parents=True)
    (repo / "evals/catalog/tasks.jsonl").write_text("", encoding="utf-8")
    (repo / "evals/suites").mkdir()
    fixture = repo / "harness/components/policy/quality.txt"
    fixture.parent.mkdir(parents=True)
    fixture.write_text("0.55\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True, env=GIT_ENV)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, env=GIT_ENV)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-qm", "fixture surface"],
        check=True,
        env=GIT_ENV,
    )
    return repo


def _seed_loop_repo(path: Path) -> Path:
    repo = path / "repo"
    shutil.copytree(REPO_ROOT / "evals", repo / "evals")
    shutil.copytree(REPO_ROOT / "harness", repo / "harness")
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True, env=GIT_ENV)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, env=GIT_ENV)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-qm", "shipped fixture"],
        check=True,
        env=GIT_ENV,
    )
    return repo


class RepoRootDiscoveryTest(unittest.TestCase):
    def test_rehearsal_commands_bind_closed_limits_and_package_graph(self) -> None:
        makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
        readmes = [
            (REPO_ROOT / "README.md").read_text(encoding="utf-8"),
            (REPO_ROOT / "loop_harness/README.md").read_text(encoding="utf-8"),
        ]
        limits = "--max-iterations 3 --max-attempts 6 --deadline-seconds 3600"
        self.assertIn(limits, makefile)
        for readme in readmes:
            self.assertIn(limits, readme)
        loop_path = next(
            line for line in makefile.splitlines() if line.startswith("LOOP_PYTHONPATH :=")
        )
        for package in ("eval_harness/src", "judge_harness/src", "loop_harness/src"):
            self.assertIn(package, loop_path)

        package_path = os.pathsep.join(
            str(REPO_ROOT / package)
            for package in ("eval_harness/src", "judge_harness/src", "loop_harness/src")
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = _seed_loop_repo(root)
            for campaign, cwd in (
                ("root-readme", REPO_ROOT),
                ("loop-readme", REPO_ROOT / "loop_harness"),
            ):
                result = subprocess.run(
                    [
                        sys.executable, "-m", "opti_loop",
                        "--repo-root", str(repo),
                        "--store-root", str(root / "store"),
                        "init", "--campaign", campaign,
                        "--adapter", "harness-fixture",
                        "--harness-file", "harness/components/policy/quality.txt",
                        "--max-iterations", "3", "--max-attempts", "6",
                        "--deadline-seconds", "3600",
                    ],
                    cwd=cwd,
                    env={
                        **os.environ,
                        "OPTI_BROWSER_REPO_ROOT": str(repo),
                        "PYTHONPATH": package_path,
                    },
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_explicit_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _seed_repo(Path(tmp))
            with patch.dict(os.environ, {}, clear=True), _cwd(Path(tmp)):
                self.assertEqual(_repo_root(argparse.Namespace(repo_root=str(repo))), repo.resolve())

    def test_environment_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _seed_repo(Path(tmp))
            with patch.dict(os.environ, {"OPTI_BROWSER_REPO_ROOT": str(repo)}, clear=True), _cwd(Path(tmp)):
                self.assertEqual(_repo_root(argparse.Namespace(repo_root=None)), repo.resolve())

    def test_harness_fixture_init_requires_candidate_surface_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _seed_repo(Path(tmp))
            stderr = StringIO()
            with redirect_stderr(stderr):
                code = main([
                    "--repo-root", str(repo), "init", "--campaign", "fixture",
                    "--adapter", "harness-fixture",
                ])
            self.assertEqual(code, 2)
            self.assertIn("--harness-file required", stderr.getvalue())

    def test_init_requires_closed_campaign_limits_with_exact_remediation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _seed_repo(Path(tmp))
            stderr = StringIO()
            with redirect_stderr(stderr):
                code = main([
                    "--repo-root", str(repo), "init", "--campaign", "no-limits",
                ])
            self.assertEqual(code, 2)
            self.assertIn(
                "--max-iterations, --max-attempts, and --deadline-seconds are required",
                stderr.getvalue(),
            )

    def test_warc_admission_preflight_blocks_campaign_initialization(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _seed_repo(Path(tmp))
            stderr = StringIO()
            with (
                patch(
                    "opti_loop.cli.load_and_preflight_config",
                    side_effect=ValueError(
                        "verifier admission failed: no admitted verifier record"
                    ),
                ),
                patch("opti_loop.cli.init_campaign") as init,
                redirect_stderr(stderr),
            ):
                code = main([
                    "--repo-root", str(repo), "init", "--campaign", "warc",
                    "--adapter", "warc-online4", "--warc-config", "/owner/config.json",
                ])
            self.assertEqual(code, 2)
            self.assertIn("verifier admission failed", stderr.getvalue())
            init.assert_not_called()

    def test_production_source_preflight_never_claims_reportability(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _seed_repo(Path(tmp))
            stdout = StringIO()
            checked = {
                "mode": "production",
                "config_digest": "a" * 64,
                "credentials": {"required_env": ["OPENCODE_API_KEY"]},
            }
            with (
                patch("opti_loop.cli.load_and_preflight_config", return_value=checked),
                redirect_stdout(stdout),
            ):
                code = main([
                    "--repo-root", str(repo), "warc-online4-preflight",
                    "--config", "/owner/config.json",
                ])
            self.assertEqual(code, 0)
            report = json.loads(stdout.getvalue())
            self.assertFalse(report["benchmark_reportable"])
            self.assertTrue(report["potential_benchmark_eligibility"])
            self.assertFalse(report["lifecycle_executed"])

    def test_harness_fixture_init_writes_direct_file_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _seed_repo(Path(tmp))
            created = SimpleNamespace(
                store=SimpleNamespace(campaign_dir=Path(tmp) / "store/fixture"),
                config={},
            )
            stdout = StringIO()
            with (
                patch("opti_loop.cli.init_campaign", return_value=created) as init,
                redirect_stdout(stdout),
            ):
                code = main([
                    "--repo-root", str(repo), "init", "--campaign", "fixture",
                    "--adapter", "harness-fixture", "--harness-file",
                    "harness/components/policy/quality.txt",
                    "--max-iterations", "3", "--max-attempts", "6",
                    "--deadline-seconds", "3600",
                ])
            self.assertEqual(code, 0)
            self.assertEqual(
                init.call_args.kwargs["overrides"]["adapter"],
                {
                    "kind": "harness-fixture",
                    "file": "harness/components/policy/quality.txt",
                    "default_pass_rate": 0.55,
                    "seed": 0,
                },
            )

    def test_harness_fixture_init_rejects_unsafe_symlink_and_invalid_rate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _seed_repo(Path(tmp))
            symlink = repo / "harness/components/policy/link.txt"
            symlink.symlink_to("quality.txt")
            invalid = repo / "harness/components/policy/invalid.txt"
            invalid.write_text("not-a-rate\n", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(repo), "add", invalid.relative_to(repo)],
                check=True,
                env=GIT_ENV,
            )
            subprocess.run(
                ["git", "-C", str(repo), "commit", "-qm", "invalid fixture"],
                check=True,
                env=GIT_ENV,
            )
            for value, expected in (
                ("../quality.txt", "safe relative POSIX path"),
                ("evals/catalog/tasks.jsonl", "outside the campaign candidate surface"),
                ("harness/components/policy/link.txt", "regular non-symlink"),
                ("harness/components/policy/invalid.txt", "numeric fixture rate"),
            ):
                with self.subTest(value=value):
                    stderr = StringIO()
                    with redirect_stderr(stderr):
                        code = main([
                            "--repo-root", str(repo), "init", "--campaign", "bad",
                            "--adapter", "harness-fixture", "--harness-file", value,
                        ])
                    self.assertEqual(code, 2)
                    self.assertIn(expected, stderr.getvalue())

    def test_harness_fixture_init_rejects_nonfinite_or_out_of_range_rates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _seed_repo(Path(tmp))
            for rate in ("nan", "inf", "-0.1", "1.1"):
                with self.subTest(rate=rate):
                    stderr = StringIO()
                    with redirect_stderr(stderr):
                        code = main([
                            "--repo-root", str(repo), "init", "--campaign", f"rate-{rate}",
                            "--adapter", "harness-fixture", "--harness-file",
                            "harness/components/policy/quality.txt", "--pass-rate", rate,
                        ])
                    self.assertEqual(code, 2)
                    self.assertIn("finite and lie in [0, 1]", stderr.getvalue())

    def test_harness_fixture_init_rejects_invalid_accepted_baseline_rate(self) -> None:
        for baseline in ("NaN\n", "Infinity\n", "-0.1\n", "1.1\n"):
            with self.subTest(baseline=baseline.strip()), tempfile.TemporaryDirectory() as tmp:
                repo = _seed_repo(Path(tmp))
                fixture = repo / "harness/components/policy/quality.txt"
                fixture.write_text(baseline, encoding="utf-8")
                subprocess.run(
                    ["git", "-C", str(repo), "add", fixture.relative_to(repo)],
                    check=True,
                    env=GIT_ENV,
                )
                subprocess.run(
                    ["git", "-C", str(repo), "commit", "-qm", "bad baseline"],
                    check=True,
                    env=GIT_ENV,
                )
                stderr = StringIO()
                with redirect_stderr(stderr):
                    code = main([
                        "--repo-root", str(repo), "init", "--campaign", "bad-baseline",
                        "--adapter", "harness-fixture", "--harness-file",
                        "harness/components/policy/quality.txt",
                    ])
                self.assertEqual(code, 2)
                self.assertIn("finite and lie in [0, 1]", stderr.getvalue())

    def test_harness_fixture_init_rejects_dirty_file_outside_accepted_surface(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _seed_repo(Path(tmp))
            (repo / "harness/components/policy/quality.txt").write_text("0.70\n")
            stderr = StringIO()
            with redirect_stderr(stderr):
                code = main([
                    "--repo-root", str(repo), "init", "--campaign", "dirty",
                    "--adapter", "harness-fixture", "--harness-file",
                    "harness/components/policy/quality.txt",
                ])
            self.assertEqual(code, 2)
            self.assertIn("match the current accepted harness surface", stderr.getvalue())

    def test_shipped_harness_fixture_cli_init_then_start(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = _seed_loop_repo(root)
            store = root / "store"
            init_output = StringIO()
            with redirect_stdout(init_output):
                init_code = main([
                    "--repo-root", str(repo), "--store-root", str(store),
                    "init", "--campaign", "offline", "--adapter",
                    "harness-fixture", "--harness-file",
                    "harness/components/policy/quality.txt",
                    "--max-iterations", "3", "--max-attempts", "6",
                    "--deadline-seconds", "3600",
                ])
            self.assertEqual(init_code, 0, init_output.getvalue())
            with redirect_stdout(StringIO()):
                self.assertEqual(main([
                    "--repo-root", str(repo), "--store-root", str(store),
                    "preflight", "--campaign", "offline",
                ]), 0)
                self.assertEqual(main([
                    "--repo-root", str(repo), "--store-root", str(store),
                    "pause", "--campaign", "offline",
                ]), 0)
            paused_stderr = StringIO()
            with redirect_stderr(paused_stderr):
                self.assertEqual(main([
                    "--repo-root", str(repo), "--store-root", str(store),
                    "run", "--campaign", "offline",
                ]), 2)
            self.assertIn("campaign is paused", paused_stderr.getvalue())
            start_output = StringIO()
            with redirect_stdout(start_output):
                start_code = main([
                    "--repo-root", str(repo), "--store-root", str(store),
                    "resume", "--campaign", "offline",
                ])
            self.assertEqual(start_code, 0, start_output.getvalue())
            campaign = load_campaign(repo, "offline", store_root=store)
            self.assertEqual(campaign.state["pending_iteration"], 1)
            self.assertEqual(
                campaign.state["pending_baseline_activation_observation"]["parsed_value"],
                0.55,
            )

    def test_current_directory_and_parent_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _seed_repo(Path(tmp))
            child = repo / "nested"
            child.mkdir()
            with patch.dict(os.environ, {}, clear=True), _cwd(child):
                self.assertEqual(_repo_root(argparse.Namespace(repo_root=None)), repo.resolve())


if __name__ == "__main__":
    unittest.main()
