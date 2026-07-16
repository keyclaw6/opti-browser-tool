"""Git primitives for the trusted experiment boundary.

The review (F01) showed the fatal flaw: the old guard compared the working
tree against mutable ``HEAD``, so once the optimizer committed — which the
runbook *requires* — its edits vanished from the guard, and ``assume-unchanged``
/ ``.git/info/exclude`` hid them too. The fix is to stop trusting the working
tree: capture an owner-trusted **base SHA** at iteration start, have the
optimizer produce exactly one **candidate commit** in an isolated worktree,
and derive the change set from ``git diff <base>..<candidate>`` over commit
objects — which local metadata tricks cannot alter.

All functions here operate on a git dir via ``-C`` and raise ``GitError`` on
failure; nothing degrades silently.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


class GitError(RuntimeError):
    pass


def _run(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
    )
    if check and proc.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed in {cwd}: {proc.stderr.strip()}")
    return proc


def parse_raw_tree(raw: bytes) -> list[tuple[str, str, str, str]]:
    """Parse ``git ls-tree -rz`` without path quoting or locale ambiguity."""
    entries: list[tuple[str, str, str, str]] = []
    records = raw.split(b"\0")
    if records[-1] != b"":
        raise GitError("raw Git tree output is not NUL terminated")
    for record in records[:-1]:
        try:
            metadata, raw_path = record.split(b"\t", 1)
            raw_mode, raw_type, raw_oid = metadata.split(b" ", 2)
            mode = raw_mode.decode("ascii")
            object_type = raw_type.decode("ascii")
            oid = raw_oid.decode("ascii")
            path = raw_path.decode("utf-8")
        except (UnicodeDecodeError, ValueError) as exc:
            raise GitError("raw Git tree contains a malformed record") from exc
        entries.append((mode, object_type, oid, path))
    return entries


def head_sha(repo: Path) -> str:
    return _run(repo, "rev-parse", "HEAD").stdout.strip()


def rev_parse(repo: Path, ref: str) -> str:
    return _run(repo, "rev-parse", ref).stdout.strip()


def try_rev_parse(repo: Path, ref: str) -> str | None:
    proc = _run(repo, "rev-parse", "--verify", ref, check=False)
    return proc.stdout.strip() if proc.returncode == 0 else None


def tree_entries(repo: Path, commit: str) -> list[tuple[str, str, str, str]]:
    proc = subprocess.run(
        ["git", "-C", str(repo), "ls-tree", "-rz", "--full-tree", f"{commit}^{{tree}}"],
        capture_output=True,
    )
    if proc.returncode != 0:
        raise GitError(
            f"git ls-tree failed in {repo}: "
            + proc.stderr.decode("utf-8", errors="replace").strip()
        )
    return parse_raw_tree(proc.stdout)


def hash_blob(repo: Path, content: bytes) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), "hash-object", "--stdin"],
        input=content,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise GitError(
            f"git hash-object failed in {repo}: "
            + proc.stderr.decode("utf-8", errors="replace").strip()
        )
    return proc.stdout.decode("ascii").strip()


def read_blob(repo: Path, commit: str, path: str) -> bytes:
    proc = subprocess.run(
        ["git", "-C", str(repo), "show", f"{commit}:{path}"],
        capture_output=True,
    )
    if proc.returncode != 0:
        raise GitError(f"Git blob is missing at {commit[:12]}:{path}")
    return proc.stdout


def is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    proc = _run(repo, "merge-base", "--is-ancestor", ancestor, descendant, check=False)
    if proc.returncode == 0:
        return True
    if proc.returncode == 1:
        return False
    raise GitError(f"merge-base --is-ancestor failed: {proc.stderr.strip()}")


def commits_between(repo: Path, base: str, candidate: str) -> list[str]:
    out = _run(repo, "rev-list", f"{base}..{candidate}").stdout.strip()
    return [line for line in out.splitlines() if line]


def diff_name_status(repo: Path, base: str, candidate: str) -> list[tuple[str, str]]:
    """Return (status, path) pairs for ``base..candidate`` over commit objects.

    Renames/copies are decomposed (``--no-renames``) so every touched path is
    audited independently; a rename cannot smuggle a file across the guard.
    """
    out = _run(
        repo, "diff", "--no-renames", "--name-status", f"{base}..{candidate}"
    ).stdout
    pairs: list[tuple[str, str]] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status, path = parts[0].strip(), parts[-1].strip()
        pairs.append((status, path))
    return pairs


def porcelain_status(repo: Path) -> list[tuple[str, str]]:
    """Return (xy, path) for ``git status --porcelain`` in a worktree."""
    out = _run(repo, "status", "--porcelain").stdout
    rows: list[tuple[str, str]] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        rows.append((line[:2], line[3:].strip()))
    return rows


def worktree_add(repo: Path, worktree: Path, base_sha: str) -> None:
    """Create a detached worktree at ``base_sha``. Removes a stale one first."""
    if worktree.exists():
        worktree_remove(repo, worktree)
    worktree.parent.mkdir(parents=True, exist_ok=True)
    _run(repo, "worktree", "add", "--detach", str(worktree), base_sha)


def worktree_remove(repo: Path, worktree: Path) -> None:
    _run(repo, "worktree", "remove", "--force", str(worktree), check=False)
    _run(repo, "worktree", "prune", check=False)


def reset_worktree(worktree: Path, base_sha: str) -> None:
    """Hard-reset a worktree to base and purge every untracked file/dir."""
    _run(worktree, "checkout", "--detach", base_sha)
    _run(worktree, "reset", "--hard", base_sha)
    _run(worktree, "clean", "-fdx")


def update_ref(repo: Path, ref: str, sha: str, *, expected: str | None = None) -> None:
    """Point a ref at a SHA, optionally with compare-and-swap semantics."""
    if expected is None:
        _run(repo, "update-ref", ref, sha)
        return
    _run(repo, "update-ref", ref, sha, expected)


def delete_ref(repo: Path, ref: str, *, expected: str) -> None:
    """Delete exactly the expected temporary ref."""
    _run(repo, "update-ref", "-d", ref, expected)


def compare_and_swap_ref(
    repo: Path, ref: str, sha: str, *, expected: str | None
) -> None:
    """Create a missing ref or replace exactly its expected object ID."""
    if expected is None:
        object_format = _run(repo, "rev-parse", "--show-object-format").stdout.strip()
        expected = "0" * (64 if object_format == "sha256" else 40)
    _run(repo, "update-ref", ref, sha, expected)


def stage_bundle_candidate(
    repo: Path,
    bundle: Path,
    *,
    candidate_sha: str,
    tree_sha: str,
    staging_ref: str,
) -> None:
    """Import and root one exact bundle candidate before accepted publication."""
    existing = try_rev_parse(repo, staging_ref)
    if existing is None:
        _run(
            repo,
            "fetch",
            "--no-tags",
            "--no-write-fetch-head",
            str(bundle),
            f"refs/heads/candidate:{staging_ref}",
        )
    elif existing != candidate_sha:
        raise GitError(f"candidate staging ref already points elsewhere: {staging_ref}")
    try:
        staged = rev_parse(repo, f"{staging_ref}^{{commit}}")
        staged_tree = rev_parse(repo, f"{staging_ref}^{{tree}}")
        if staged != candidate_sha or staged_tree != tree_sha:
            raise GitError("staged candidate commit/tree does not match D2 receipt")
    except BaseException:
        if try_rev_parse(repo, staging_ref) == candidate_sha:
            delete_ref(repo, staging_ref, expected=candidate_sha)
        raise


def create_candidate_bundle(
    repo: Path, destination: Path, *, base_sha: str, candidate_sha: str
) -> None:
    """Create the static D2 handback used by same-user simulated rehearsals."""
    ref = "refs/heads/candidate"
    previous = try_rev_parse(repo, ref)
    if previous == candidate_sha:
        _run(repo, "bundle", "create", str(destination), ref, f"^{base_sha}")
        if try_rev_parse(repo, ref) != candidate_sha:
            destination.unlink(missing_ok=True)
            raise GitError("candidate ref changed concurrently during bundle creation")
        return
    object_format = _run(repo, "rev-parse", "--show-object-format").stdout.strip()
    missing = "0" * (64 if object_format == "sha256" else 40)
    _run(repo, "update-ref", ref, candidate_sha, previous or missing)
    try:
        _run(repo, "bundle", "create", str(destination), ref, f"^{base_sha}")
    finally:
        try:
            if previous is None:
                _run(repo, "update-ref", "-d", ref, candidate_sha)
            else:
                _run(repo, "update-ref", ref, previous, candidate_sha)
        except GitError:
            destination.unlink(missing_ok=True)
            raise
