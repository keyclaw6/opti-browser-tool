"""D2 tests for the accepted Git-backed materialization boundary."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest import mock

from opti_eval.adapters.fixture import FixtureAdapter
from opti_eval.identity import finalize_protocol_snapshot, simulated_protocol
from opti_loop import gitutil
from opti_loop.materialization import (
    MAX_BUNDLE_BYTES,
    CampaignLock,
    MaterializationError,
    consume_materialization,
    materialize_candidate_bundle,
    project_build_identity,
    verify_materialization,
)
from opti_loop.protocol import build_identity


ALLOWLIST = ["harness/components/"]
GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "D2 test",
    "GIT_AUTHOR_EMAIL": "d2@example.invalid",
    "GIT_COMMITTER_NAME": "D2 test",
    "GIT_COMMITTER_EMAIL": "d2@example.invalid",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": "/dev/null",
}


def _git(repo: Path, *arguments: str, input_bytes: bytes | None = None) -> bytes:
    proc = subprocess.run(
        ["git", "-C", os.fspath(repo), *arguments],
        input=input_bytes,
        capture_output=True,
        env=GIT_ENV,
    )
    if proc.returncode != 0:
        raise AssertionError(proc.stderr.decode("utf-8", errors="replace"))
    return proc.stdout


def _seed_trusted(root: Path) -> tuple[Path, str]:
    repo = root / "trusted"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "harness/components/policy").mkdir(parents=True)
    (repo / "harness/components/tools").mkdir(parents=True)
    (repo / "harness/components/policy/data.txt").write_text("base\n")
    run = repo / "harness/components/tools/run.sh"
    run.write_text("#!/bin/sh\nexit 0\n")
    run.chmod(0o755)
    (repo / "harness/runtime").mkdir(parents=True)
    (repo / "harness/runtime/engine.py").write_text("VALUE = 1\n")
    (repo / "evals").mkdir()
    (repo / "evals/plane.txt").write_text("trusted evaluator bytes\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "initial")
    (repo / "README.md").write_text("trusted base\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-qm", "base")
    return repo, _git(repo, "rev-parse", "HEAD").decode().strip()


class GitMaterializationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.trusted, self.base = _seed_trusted(self.root)
        self.store = self.root / "store"
        self.store.mkdir(mode=0o700)
        self.protocol = simulated_protocol(
            suite={"id": "d2", "kind": "test"},
            tasks=[{"id": "d2-task", "source": "test", "goal": "test"}],
            adapter=FixtureAdapter(pass_rate=1.0, seed=0).describe(),
        )
        self.protocol["candidate_allowlist"] = list(ALLOWLIST)
        self.protocol["accepted_build"] = build_identity(
            self.trusted,
            commit_sha=self.base,
            role="accepted",
            candidate_allowlist=ALLOWLIST,
        )
        for field in (
            "calibration_binding_digest",
            "comparison_apparatus_digest",
            "protocol_digest",
        ):
            self.protocol.pop(field, None)
        self.protocol = finalize_protocol_snapshot(self.protocol)
        self.counter = 0

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def optimizer(self, name: str | None = None) -> Path:
        self.counter += 1
        optimizer = self.root / (name or f"optimizer-{self.counter}")
        subprocess.run(
            ["git", "clone", "-q", os.fspath(self.trusted), os.fspath(optimizer)],
            check=True,
            capture_output=True,
            env=GIT_ENV,
        )
        return optimizer

    def bundle_for(
        self,
        optimizer: Path,
        candidate: str,
        *,
        name: str | None = None,
        prerequisite: bool = True,
    ) -> Path:
        self.counter += 1
        bundle = self.root / (name or f"candidate-{self.counter}.bundle")
        _git(optimizer, "update-ref", "refs/heads/candidate", candidate)
        arguments = ["bundle", "create", os.fspath(bundle), "refs/heads/candidate"]
        if prerequisite:
            arguments.append(f"^{self.base}")
        _git(optimizer, *arguments)
        return bundle

    def simple_candidate(
        self,
        *,
        content: str = "candidate\n",
        path: str = "harness/components/policy/data.txt",
        message: str = "candidate",
    ) -> tuple[Path, Path, str]:
        optimizer = self.optimizer()
        target = optimizer / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        _git(optimizer, "add", "-A")
        _git(optimizer, "commit", "-qm", message)
        candidate = _git(optimizer, "rev-parse", "HEAD").decode().strip()
        return optimizer, self.bundle_for(optimizer, candidate), candidate

    def materialize(
        self,
        bundle: Path,
        *,
        expected_base: str | None = None,
        allowlist: object = ALLOWLIST,
    ) -> tuple[Path, dict]:
        with CampaignLock(self.store) as lock:
            return materialize_candidate_bundle(
                bundle,
                trusted_repo=self.trusted,
                protocol_snapshot=self._protocol(
                    expected_base=expected_base, allowlist=allowlist
                ),
                lock=lock,
            )

    def _protocol(
        self, *, expected_base: str | None = None, allowlist: object = ALLOWLIST
    ) -> dict:
        snapshot = deepcopy(self.protocol)
        if expected_base is not None:
            snapshot["accepted_build"]["commit_sha"] = expected_base
        snapshot["candidate_allowlist"] = allowlist
        for field in (
            "calibration_binding_digest",
            "comparison_apparatus_digest",
            "protocol_digest",
        ):
            snapshot.pop(field, None)
        return finalize_protocol_snapshot(snapshot)

    def test_trusted_bundle_derives_full_tree_and_shared_build_identity(self) -> None:
        optimizer, bundle, candidate = self.simple_candidate()
        target, receipt = self.materialize(bundle)
        self.assertEqual(receipt["commit_sha"], candidate)
        self.assertEqual(
            receipt["tree_sha"],
            _git(optimizer, "rev-parse", f"{candidate}^{{tree}}").decode().strip(),
        )
        self.assertTrue((target / "tree/evals/plane.txt").is_file())
        self.assertIn("git_tree_digest", receipt)
        self.assertNotIn("git_tree_files", receipt)
        identity = build_identity(
            optimizer,
            commit_sha=candidate,
            role="candidate",
            candidate_allowlist=ALLOWLIST,
        )
        self.assertEqual(identity["materialized_digest"], receipt["materialized_digest"])
        projected = project_build_identity(
            target, role="candidate", protocol_snapshot=self.protocol
        )
        self.assertEqual(projected["materialized_digest"], receipt["materialized_digest"])
        self.assertTrue(projected["immutable"])

    def test_different_commits_with_identical_build_rows_share_digest(self) -> None:
        _optimizer1, bundle1, _candidate1 = self.simple_candidate(message="first")
        _optimizer2, bundle2, _candidate2 = self.simple_candidate(message="second")
        target1, receipt1 = self.materialize(bundle1)
        target2, receipt2 = self.materialize(bundle2)
        self.assertNotEqual(target1, target2)
        self.assertNotEqual(receipt1["commit_sha"], receipt2["commit_sha"])
        self.assertEqual(receipt1["tree_sha"], receipt2["tree_sha"])
        self.assertEqual(receipt1["materialized_digest"], receipt2["materialized_digest"])

    def test_lock_and_store_are_fail_closed(self) -> None:
        _optimizer, bundle, _candidate = self.simple_candidate()
        self.store.chmod(0o755)
        with self.assertRaisesRegex(MaterializationError, "mode must be 0700"):
            with CampaignLock(self.store):
                pass
        self.store.chmod(0o700)
        lock = CampaignLock(self.store)
        with self.assertRaisesRegex(MaterializationError, "held campaign lock"):
            materialize_candidate_bundle(
                bundle,
                trusted_repo=self.trusted,
                protocol_snapshot=self.protocol,
                lock=lock,
            )
        with mock.patch("opti_loop.materialization.os.getuid", return_value=os.getuid() + 2):
            with self.assertRaisesRegex(MaterializationError, "owned"):
                with CampaignLock(self.store):
                    pass

    def test_campaign_lock_excludes_a_second_holder(self) -> None:
        first = CampaignLock(self.store)
        second = CampaignLock(self.store)
        with first, self.assertRaisesRegex(MaterializationError, "another process"):
            second.__enter__()

    def test_bundle_must_be_bounded_regular_and_present(self) -> None:
        _optimizer, valid, _candidate = self.simple_candidate()
        directory = self.root / "directory.bundle"
        directory.mkdir()
        symlink = self.root / "symlink.bundle"
        symlink.symlink_to(valid)
        oversized = self.root / "oversized.bundle"
        with oversized.open("wb") as handle:
            handle.truncate(MAX_BUNDLE_BYTES + 1)
        for source in (self.root / "missing.bundle", directory, symlink, oversized):
            with self.subTest(source=source), self.assertRaises(MaterializationError):
                self.materialize(source)
        self.assertEqual(list(self.store.glob(".stage-*")), [])

    def test_tree_file_blob_and_expanded_byte_limits_fail_before_materializing(self) -> None:
        _optimizer, bundle, _candidate = self.simple_candidate()
        cases = (
            ("MAX_MATERIALIZED_FILES", 1, "file limit"),
            ("MAX_BLOB_BYTES", 1, "blob exceeds"),
            ("MAX_MATERIALIZED_BYTES", 1, "materialized limit"),
        )
        for constant, value, diagnostic in cases:
            with (
                self.subTest(limit=constant),
                mock.patch(f"opti_loop.materialization.{constant}", value),
                self.assertRaisesRegex(MaterializationError, diagnostic),
            ):
                self.materialize(bundle)
        self.assertEqual(list(self.store.glob(".stage-*")), [])

    def test_unsafe_linked_worktree_administration_is_rejected_before_import(self) -> None:
        _optimizer, bundle, _candidate = self.simple_candidate()
        linked = self.root / "linked-trusted"
        _git(self.trusted, "worktree", "add", "-q", "--detach", os.fspath(linked), self.base)
        git_dir = Path(_git(linked, "rev-parse", "--absolute-git-dir").decode().strip())
        git_dir.chmod(0o770)
        with (
            CampaignLock(self.store) as lock,
            self.assertRaisesRegex(MaterializationError, "trusted Git directory"),
        ):
            materialize_candidate_bundle(
                bundle,
                trusted_repo=linked,
                protocol_snapshot=self.protocol,
                lock=lock,
            )
        self.assertEqual(list(self.store.glob(".stage-*")), [])

    def test_optimizer_repository_config_and_hooks_are_never_invoked(self) -> None:
        optimizer, bundle, _candidate = self.simple_candidate()
        marker = self.root / "optimizer-config-executed"
        _git(optimizer, "config", "uploadpack.packObjectsHook", f"touch {marker}")
        hooks = optimizer / ".git/hooks"
        hook = hooks / "post-checkout"
        hook.write_text(f"#!/bin/sh\ntouch {marker}\n")
        hook.chmod(0o755)
        self.materialize(bundle)
        self.assertFalse(marker.exists())

    def test_two_commit_merge_empty_reverted_and_unrelated_candidates_fail(self) -> None:
        cases: list[Path] = []

        zero = self.optimizer("zero")
        cases.append(self.bundle_for(zero, self.base, prerequisite=False))

        two = self.optimizer("two")
        for value in ("one\n", "two\n"):
            (two / "harness/components/policy/data.txt").write_text(value)
            _git(two, "add", "-A")
            _git(two, "commit", "-qm", value.strip())
        cases.append(self.bundle_for(two, _git(two, "rev-parse", "HEAD").decode().strip()))

        merged = self.optimizer("merge")
        _git(merged, "checkout", "-qb", "left", self.base)
        (merged / "harness/components/policy/data.txt").write_text("left\n")
        _git(merged, "add", "-A")
        _git(merged, "commit", "-qm", "left")
        _git(merged, "checkout", "-qb", "right", self.base)
        (merged / "harness/components/policy/right.txt").write_text("right\n")
        _git(merged, "add", "-A")
        _git(merged, "commit", "-qm", "right")
        _git(merged, "checkout", "left")
        _git(merged, "merge", "--no-ff", "-qm", "merge", "right")
        cases.append(self.bundle_for(merged, _git(merged, "rev-parse", "HEAD").decode().strip()))

        empty = self.optimizer("empty")
        _git(empty, "commit", "--allow-empty", "-qm", "empty")
        cases.append(self.bundle_for(empty, _git(empty, "rev-parse", "HEAD").decode().strip()))

        reverted = self.optimizer("reverted")
        (reverted / "harness/components/policy/data.txt").write_text("temporary\n")
        _git(reverted, "add", "-A")
        _git(reverted, "commit", "-qm", "change")
        (reverted / "harness/components/policy/data.txt").write_text("base\n")
        _git(reverted, "add", "-A")
        _git(reverted, "commit", "-qm", "revert")
        cases.append(self.bundle_for(reverted, _git(reverted, "rev-parse", "HEAD").decode().strip()))

        unrelated = self.optimizer("unrelated")
        _git(unrelated, "checkout", "--orphan", "orphan")
        _git(unrelated, "rm", "-rf", ".")
        (unrelated / "harness/components/policy").mkdir(parents=True)
        (unrelated / "harness/components/policy/data.txt").write_text("orphan\n")
        _git(unrelated, "add", "-A")
        _git(unrelated, "commit", "-qm", "orphan")
        unrelated_bundle = self.bundle_for(
            unrelated,
            _git(unrelated, "rev-parse", "HEAD").decode().strip(),
            prerequisite=False,
        )
        raw = unrelated_bundle.read_bytes()
        boundary = raw.index(b"\n") + 1
        unrelated_bundle.write_bytes(
            raw[:boundary] + f"-{self.base} expected\n".encode() + raw[boundary:]
        )
        cases.append(unrelated_bundle)

        for bundle in cases:
            with self.subTest(bundle=bundle), self.assertRaises(MaterializationError):
                self.materialize(bundle)

    def test_forbidden_and_unsafe_candidate_paths_fail(self) -> None:
        _optimizer, forbidden, _candidate = self.simple_candidate(
            path="evals/plane.txt", content="tampered\n"
        )
        _optimizer2, unsafe, _candidate2 = self.simple_candidate(
            path="harness/components/bad\\name", content="bad\n"
        )
        for bundle in (forbidden, unsafe):
            with self.subTest(bundle=bundle), self.assertRaises(MaterializationError):
                self.materialize(bundle)

    def test_corrupt_bundle_objects_fail(self) -> None:
        _optimizer, bundle, _candidate = self.simple_candidate()
        raw = bytearray(bundle.read_bytes())
        raw[-1] ^= 0xFF
        bundle.write_bytes(raw)
        with self.assertRaises(MaterializationError):
            self.materialize(bundle)

    def test_symlink_gitlink_and_unexpected_raw_mode_fail(self) -> None:
        symlink_repo = self.optimizer("symlink")
        link = symlink_repo / "harness/components/policy/link"
        link.symlink_to("data.txt")
        _git(symlink_repo, "add", "-A")
        _git(symlink_repo, "commit", "-qm", "link")
        symlink_bundle = self.bundle_for(
            symlink_repo, _git(symlink_repo, "rev-parse", "HEAD").decode().strip()
        )

        gitlink_repo = self.optimizer("gitlink")
        _git(
            gitlink_repo,
            "update-index",
            "--add",
            "--cacheinfo",
            f"160000,{self.base},harness/components/submodule",
        )
        _git(gitlink_repo, "commit", "-qm", "gitlink")
        gitlink_bundle = self.bundle_for(
            gitlink_repo, _git(gitlink_repo, "rev-parse", "HEAD").decode().strip()
        )
        for bundle in (symlink_bundle, gitlink_bundle):
            with self.subTest(bundle=bundle), self.assertRaisesRegex(
                MaterializationError, "100644/100755"
            ):
                self.materialize(bundle)

        _optimizer, valid, _candidate = self.simple_candidate()
        real_parser = gitutil.parse_raw_tree

        def wrong_mode(raw: bytes):
            entries = real_parser(raw)
            mode, object_type, oid, path = entries[0]
            entries[0] = ("100600", object_type, oid, path)
            return entries

        with mock.patch(
            "opti_loop.materialization.gitutil.parse_raw_tree", side_effect=wrong_mode
        ), self.assertRaisesRegex(MaterializationError, "100644/100755"):
            self.materialize(valid)

    def test_read_only_seal_full_tree_tamper_and_consumption_rehash(self) -> None:
        _optimizer, bundle, _candidate = self.simple_candidate()
        target, _receipt = self.materialize(bundle)
        for current, directories, files in os.walk(target):
            for name in directories + files:
                self.assertEqual(stat.S_IMODE((Path(current) / name).lstat().st_mode) & 0o222, 0)
        evaluator = target / "tree/evals/plane.txt"
        with self.assertRaises(MaterializationError):
            with consume_materialization(target):
                evaluator.chmod(0o644)
                evaluator.write_text("drifted trusted bytes\n")
                evaluator.chmod(0o444)
        with self.assertRaisesRegex(MaterializationError, "does not match receipt"):
            verify_materialization(target)

    def test_exact_reuse_conflict_and_stage_cleanup_under_lock(self) -> None:
        _optimizer, bundle, _candidate = self.simple_candidate()
        with CampaignLock(self.store) as lock:
            first, receipt = materialize_candidate_bundle(
                bundle,
                trusted_repo=self.trusted,
                protocol_snapshot=self.protocol,
                lock=lock,
            )
            second, reused = materialize_candidate_bundle(
                bundle,
                trusted_repo=self.trusted,
                protocol_snapshot=self.protocol,
                lock=lock,
            )
            self.assertEqual((first, receipt), (second, reused))
            first.chmod(0o755)
            (first / "unexpected").write_text("conflict")
            first.chmod(0o555)
            with self.assertRaisesRegex(MaterializationError, "conflicts"):
                materialize_candidate_bundle(
                    bundle,
                    trusted_repo=self.trusted,
                    protocol_snapshot=self.protocol,
                    lock=lock,
                )
        self.assertEqual(list(self.store.glob(".stage-*")), [])

    def test_receipt_is_closed_canonical_and_role_is_validated(self) -> None:
        _optimizer, bundle, _candidate = self.simple_candidate()
        target, receipt = self.materialize(bundle)
        with self.assertRaises(MaterializationError):
            project_build_identity(
                target, role="baseline", protocol_snapshot=self.protocol
            )
        path = target / "receipt.json"
        receipt["extra"] = True
        path.chmod(0o644)
        path.write_text(json.dumps(receipt, sort_keys=True))
        path.chmod(0o444)
        with self.assertRaisesRegex(MaterializationError, "wrong fields"):
            verify_materialization(target)

    def test_frozen_protocol_is_the_base_allowlist_and_projection_authority(self) -> None:
        _optimizer, bundle, _candidate = self.simple_candidate()
        parent = _git(self.trusted, "rev-parse", f"{self.base}^").decode().strip()
        with self.assertRaises(MaterializationError):
            self.materialize(bundle, expected_base=parent)

        target, _receipt = self.materialize(bundle)
        wrong_allowlist = self._protocol(allowlist=["harness/runtime/"])
        with self.assertRaisesRegex(MaterializationError, "protocol authority"):
            project_build_identity(
                target,
                role="candidate",
                protocol_snapshot=wrong_allowlist,
            )


if __name__ == "__main__":
    unittest.main()
