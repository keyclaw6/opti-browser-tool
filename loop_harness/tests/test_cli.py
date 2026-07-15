"""CLI repository-root discovery tests."""
from __future__ import annotations

import argparse
import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from opti_loop.cli import _repo_root


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
    return repo


class RepoRootDiscoveryTest(unittest.TestCase):
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

    def test_current_directory_and_parent_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _seed_repo(Path(tmp))
            child = repo / "nested"
            child.mkdir()
            with patch.dict(os.environ, {}, clear=True), _cwd(child):
                self.assertEqual(_repo_root(argparse.Namespace(repo_root=None)), repo.resolve())


if __name__ == "__main__":
    unittest.main()
