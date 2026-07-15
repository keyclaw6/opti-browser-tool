from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from opti_eval.validation import validate_repository

ROOT = Path(os.environ["OPTI_BROWSER_REPO_ROOT"])
sys.path.insert(0, str(ROOT / "scripts"))

from verify_repository_completeness import audit_git_repository  # noqa: E402


class RepositoryValidationTest(unittest.TestCase):
    def test_complete_repository(self) -> None:
        root = Path(os.environ["OPTI_BROWSER_REPO_ROOT"])
        report = validate_repository(root)
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["candidate_count"], 140)
        self.assertEqual(report["catalog_count"], 140)
        self.assertEqual(report["individual_task_file_count"], 140)
        self.assertEqual(report["primary_count"], 140)
        self.assertEqual(report["smoke_count"], 20)


@unittest.skipUnless(shutil.which("git"), "Git is required")
class GitRepositoryCompletenessTest(unittest.TestCase):
    def test_normal_checkout_and_linked_worktree_are_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_s:
            tmp = Path(tmp_s)
            checkout = tmp / "checkout"
            linked = tmp / "linked"
            subprocess.run(
                ["git", "init", "-q", str(checkout)],
                check=True,
                capture_output=True,
                text=True,
            )
            (checkout / "tracked.txt").write_text("tracked\n", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(checkout), "add", "tracked.txt"],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(checkout),
                    "-c",
                    "user.name=Completeness Test",
                    "-c",
                    "user.email=completeness@example.invalid",
                    "commit",
                    "-qm",
                    "fixture",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(checkout),
                    "worktree",
                    "add",
                    "-q",
                    "-b",
                    "linked-test",
                    str(linked),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertTrue((checkout / ".git").is_dir())
            self.assertEqual(audit_git_repository(checkout), [])
            self.assertTrue((linked / ".git").is_file())
            self.assertEqual(audit_git_repository(linked), [])

            child = checkout / "child"
            child.mkdir()
            errors = audit_git_repository(child)
            self.assertEqual(len(errors), 1)
            self.assertIn("not the Git work-tree toplevel", errors[0])


if __name__ == "__main__":
    unittest.main()
