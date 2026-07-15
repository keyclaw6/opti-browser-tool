"""File guard: the optimizer's writable surface, enforced over commit objects.

Rewritten after the review (F01, F03, F08-symlink). The authoritative check is
now ``git diff <base>..<candidate>`` (commit objects, immune to working-tree
hiding, ``assume-unchanged``, and ``.git/info/exclude``), plus a working-tree
cleanliness assertion so an optimizer that edits but forgets to commit fails
loudly instead of slipping past.

Path safety is enforced here and re-enforced in ``manifest``: absolute paths,
``..`` traversal, NUL bytes, and non-regular files (symlinks, fifos) are
rejected before anything is read or deleted, closing the traversal-delete
(F03) and symlink-into-eval-plane (F08) holes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import gitutil

# Untracked files the conductor tolerates in the worktree at gate time: the
# optimizer drops its manifest here; the conductor ingests it as untrusted input.
TOLERATED_UNTRACKED: frozenset[str] = frozenset({"manifest.json"})


class GuardError(RuntimeError):
    """Raised when the guard itself cannot run (git missing / not a repo)."""


def is_allowed(path: str, allowed_prefixes: tuple[str, ...]) -> bool:
    return any(path.startswith(prefix) for prefix in allowed_prefixes)


def path_is_safe(path: str) -> bool:
    """Reject absolute paths, traversal, NUL, and backslash separators."""
    if not path or "\x00" in path or "\\" in path:
        return False
    if path.startswith("/"):
        return False
    parts = path.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        return False
    return True


def is_regular_file(root: Path, relpath: str) -> bool:
    """True only for a real regular file (not a symlink/fifo) under root."""
    full = (root / relpath)
    try:
        # Refuse symlinks anywhere along the path or at the leaf.
        resolved = full.resolve()
        resolved.relative_to(root.resolve())
    except (ValueError, OSError):
        return False
    return full.is_file() and not full.is_symlink()


@dataclass(slots=True)
class GuardReport:
    changed: list[str] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)
    dirty_worktree: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations and not self.dirty_worktree

    def to_dict(self) -> dict:
        return {
            "changed": self.changed,
            "violations": self.violations,
            "dirty_worktree": self.dirty_worktree,
            "ok": self.ok,
        }


def check_candidate(
    *,
    repo: Path,
    worktree: Path,
    base_sha: str,
    candidate_sha: str,
    allowed_prefixes: tuple[str, ...],
) -> GuardReport:
    """Authoritative guard over commit objects + worktree cleanliness.

    A change is admitted only if EVERY path in ``base..candidate`` is under an
    allowed prefix, path-safe, and a regular file in the candidate worktree,
    AND the worktree has no uncommitted edits except a tolerated untracked
    ``manifest.json``.
    """
    report = GuardReport()
    try:
        if not gitutil.is_ancestor(repo, base_sha, candidate_sha):
            report.violations.append(
                f"candidate {candidate_sha[:12]} does not descend from trusted base {base_sha[:12]}"
            )
            return report
        pairs = gitutil.diff_name_status(repo, base_sha, candidate_sha)
        dirty = gitutil.porcelain_status(worktree)
    except gitutil.GitError as exc:
        raise GuardError(str(exc)) from exc

    report.changed = sorted(path for _status, path in pairs)

    for _status, path in pairs:
        if not path_is_safe(path):
            report.violations.append(f"unsafe path in candidate diff: {path!r}")
            continue
        if not is_allowed(path, allowed_prefixes):
            report.violations.append(f"path outside optimizer surface: {path}")
            continue
        # Deleted files won't exist in the worktree; only vet present files.
        if _status != "D" and not is_regular_file(worktree, path):
            report.violations.append(f"non-regular file or symlink: {path}")

    for xy, path in dirty:
        if xy == "??" and path in TOLERATED_UNTRACKED:
            continue
        report.dirty_worktree.append(f"{xy} {path}")

    return report
