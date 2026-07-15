"""Git-derived immutable candidate builds for the single-host conductor.

The optimizer hands back one static bundle.  The conductor never opens the
optimizer repository: it copies the bundle into an owner-only locked store,
imports it with a sanitized Git process, validates the exact one-commit change,
and publishes a read-only tree derived only from trusted Git blobs.
"""

from __future__ import annotations

import fcntl
import hashlib
import os
import re
import shutil
import stat
import subprocess
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterator

from opti_eval.identity import (
    IdentityError,
    digest_json,
    validate_build_identity,
    validate_candidate_allowlist,
    validate_protocol_snapshot,
)
from opti_eval.models import canonical_json, strict_json_loads

from . import gitutil
from .protocol import (
    ProtocolError,
    canonical_build_digest,
    canonical_build_rows,
    canonical_git_path,
    canonical_git_tree_digest,
)


SCHEMA_VERSION = "1.0.0"
RECEIPT_DIGEST_DOMAIN = "opti.materialization-receipt.v1"
LOCK_NAME = ".campaign.lock"
TREE_NAME = "tree"
RECEIPT_NAME = "receipt.json"
MAX_BUNDLE_BYTES = 256 * 1024 * 1024
MAX_BLOB_BYTES = 16 * 1024 * 1024
MAX_MATERIALIZED_BYTES = 256 * 1024 * 1024
MAX_MATERIALIZED_FILES = 10_000
RECEIPT_FIELDS = frozenset({
    "schema_version", "base_commit_sha", "commit_sha", "tree_sha",
    "candidate_allowlist", "git_tree_digest", "materialized_digest",
    "receipt_digest",
})
_OID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_ALLOWED_GIT_MODES = frozenset({"100644", "100755"})


class MaterializationError(RuntimeError):
    """The handoff, Git provenance, store, or published build is invalid."""


def _owner_directory(path: Path, *, field: str, mode: int = 0o700) -> os.stat_result:
    try:
        info = path.lstat()
    except OSError as exc:
        raise MaterializationError(f"{field} does not exist: {path}") from exc
    if not stat.S_ISDIR(info.st_mode):
        raise MaterializationError(f"{field} must be a real directory: {path}")
    if info.st_uid != os.getuid():
        raise MaterializationError(f"{field} must be owned by the conductor UID")
    actual_mode = stat.S_IMODE(info.st_mode)
    if actual_mode != mode:
        raise MaterializationError(f"{field} mode must be {mode:04o}, got {actual_mode:04o}")
    return info


class CampaignLock:
    """One explicit non-reentrant lock for candidate import and publication."""

    def __init__(self, store_root: Path) -> None:
        self.store_root = Path(store_root).absolute()
        self._descriptor: int | None = None

    @property
    def held(self) -> bool:
        return self._descriptor is not None

    def __enter__(self) -> CampaignLock:
        if self.held:
            raise MaterializationError("campaign lock is already held by this object")
        _owner_directory(self.store_root, field="materialization store")
        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(self.store_root / LOCK_NAME, flags, 0o600)
        except OSError as exc:
            raise MaterializationError("cannot open campaign lock file") from exc
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
                raise MaterializationError("campaign lock file must be regular and conductor-owned")
            if stat.S_IMODE(info.st_mode) != 0o600:
                raise MaterializationError("campaign lock file mode must be 0600")
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise MaterializationError("campaign lock is held by another process") from exc
        except BaseException:
            os.close(descriptor)
            raise
        self._descriptor = descriptor
        return self

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        descriptor = self._descriptor
        self._descriptor = None
        if descriptor is not None:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def require_held(self, store_root: Path) -> None:
        if not self.held or Path(store_root).absolute() != self.store_root:
            raise MaterializationError("candidate import/materialization/publication requires its held campaign lock")
        _owner_directory(self.store_root, field="materialization store")


@dataclass(frozen=True, slots=True)
class _GitContext:
    binary: str
    environment: dict[str, str]
    hooks_dir: Path


def _git_context(control_root: Path) -> _GitContext:
    home = control_root / "home"
    xdg = control_root / "xdg"
    hooks = control_root / "hooks"
    for directory in (control_root, home, xdg, hooks):
        directory.mkdir(mode=0o700, exist_ok=True)
        directory.chmod(0o700)
        _owner_directory(directory, field="Git control directory")
    path = os.environ.get("PATH", "/usr/bin:/bin")
    binary = shutil.which("git", path=path)
    if binary is None:
        raise MaterializationError("trusted Git executable is unavailable")
    environment = {
        "PATH": path,
        "HOME": os.fspath(home),
        "XDG_CONFIG_HOME": os.fspath(xdg),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_ASKPASS": "/bin/false",
        "SSH_ASKPASS": "/bin/false",
        "LANG": "C",
        "LC_ALL": "C",
    }
    return _GitContext(os.path.realpath(binary), environment, hooks)


def _git_command(context: _GitContext, *arguments: str, cwd: Path | None = None) -> list[str]:
    command = [
        context.binary,
        "--no-pager",
        "--no-replace-objects",
        "-c",
        f"core.hooksPath={context.hooks_dir}",
        "-c",
        "protocol.file.allow=always",
    ]
    if cwd is not None:
        command.extend(("-C", os.fspath(cwd)))
    command.extend(arguments)
    return command


def _git(
    context: _GitContext,
    *arguments: str,
    cwd: Path | None = None,
    input_bytes: bytes | None = None,
) -> bytes:
    command = _git_command(context, *arguments, cwd=cwd)
    proc = subprocess.run(
        command, input=input_bytes, capture_output=True, env=context.environment
    )
    if proc.returncode != 0:
        error = proc.stderr.decode("utf-8", errors="replace").strip()
        raise MaterializationError(f"sanitized Git {' '.join(arguments)} failed: {error or 'no diagnostic'}")
    return proc.stdout


def _git_text(context: _GitContext, *arguments: str, cwd: Path | None = None) -> str:
    try:
        return _git(context, *arguments, cwd=cwd).decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise MaterializationError("sanitized Git returned non-UTF-8 metadata") from exc


def _safe_path(value: object, *, field: str = "Git tree path") -> str:
    try:
        return canonical_git_path(value)
    except ProtocolError as exc:
        raise MaterializationError(f"{field} must be a safe relative POSIX path") from exc


def _oid(value: object, *, field: str, length: int | None = None) -> str:
    if type(value) is not str or _OID.fullmatch(value) is None:
        raise MaterializationError(f"{field} must be a full lowercase Git object ID")
    if length is not None and len(value) != length:
        raise MaterializationError(f"{field} uses the wrong Git object format")
    return value


def _allowlist(value: object) -> list[str]:
    try:
        return validate_candidate_allowlist(value)
    except IdentityError as exc:
        raise MaterializationError(str(exc)) from exc


def _copy_bundle(source: Path, destination: Path, *, lock: CampaignLock) -> None:
    lock.require_held(lock.store_root)
    _owner_directory(destination.parent, field="materialization stage")
    try:
        info = source.lstat()
    except OSError as exc:
        raise MaterializationError(f"candidate bundle does not exist: {source}") from exc
    if not stat.S_ISREG(info.st_mode):
        raise MaterializationError("candidate bundle must be a regular non-symlink file")
    if info.st_size <= 0 or info.st_size > MAX_BUNDLE_BYTES:
        raise MaterializationError(f"candidate bundle must be between 1 and {MAX_BUNDLE_BYTES} bytes")
    read_flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    read_flags |= getattr(os, "O_NOFOLLOW", 0)
    write_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
    write_flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        source_fd = os.open(source, read_flags)
    except OSError as exc:
        raise MaterializationError("cannot copy candidate bundle into trusted staging") from exc
    try:
        destination_fd = os.open(destination, write_flags, 0o600)
    except OSError as exc:
        os.close(source_fd)
        raise MaterializationError("cannot copy candidate bundle into trusted staging") from exc
    copied = 0
    try:
        if not stat.S_ISREG(os.fstat(source_fd).st_mode):
            raise MaterializationError("candidate bundle must remain a regular file")
        while True:
            chunk = os.read(source_fd, 1024 * 1024)
            if not chunk:
                break
            copied += len(chunk)
            if copied > MAX_BUNDLE_BYTES:
                raise MaterializationError("candidate bundle exceeds the size limit")
            view = memoryview(chunk)
            while view:
                written = os.write(destination_fd, view)
                view = view[written:]
        if copied == 0:
            raise MaterializationError("candidate bundle is empty")
        os.fchmod(destination_fd, 0o400)
        os.fsync(destination_fd)
    finally:
        os.close(source_fd)
        os.close(destination_fd)


def _owned_git_entry(path: Path, *, field: str) -> os.stat_result:
    try:
        info = path.lstat()
    except OSError as exc:
        raise MaterializationError(f"{field} does not exist: {path}") from exc
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o022:
        raise MaterializationError(
            f"{field} must be conductor-owned and not group/world-writable: {path}"
        )
    if stat.S_ISLNK(info.st_mode):
        raise MaterializationError(f"{field} must not contain symlinks: {path}")
    return info


def _trusted_path_ancestry(path: Path) -> None:
    current = path
    root_uid = Path("/").stat().st_uid
    while True:
        info = current.lstat()
        if stat.S_ISLNK(info.st_mode) or info.st_uid not in {root_uid, os.getuid()}:
            raise MaterializationError(
                f"trusted Git path crosses an uncontrolled ancestor: {current}"
            )
        writable = stat.S_IMODE(info.st_mode) & 0o022
        sticky_root_directory = (
            info.st_uid == root_uid
            and stat.S_ISDIR(info.st_mode)
            and bool(info.st_mode & stat.S_ISVTX)
        )
        if writable and not sticky_root_directory:
            raise MaterializationError(
                f"trusted Git path crosses a group/world-writable ancestor: {current}"
            )
        if current.parent == current:
            return
        current = current.parent


def _gitdir_pointer(path: Path, *, prefix: str | None = None) -> Path:
    info = _owned_git_entry(path, field="trusted Git administration pointer")
    if not stat.S_ISREG(info.st_mode) or info.st_size > 4096:
        raise MaterializationError("trusted Git administration pointer must be a small regular file")
    try:
        value = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError) as exc:
        raise MaterializationError("trusted Git administration pointer is unreadable") from exc
    if prefix is not None:
        if not value.startswith(prefix):
            raise MaterializationError("trusted Git administration pointer is malformed")
        value = value[len(prefix) :]
    if not value or "\x00" in value or "\n" in value:
        raise MaterializationError("trusted Git administration pointer is malformed")
    target = Path(value)
    if not target.is_absolute():
        target = path.parent / target
    return Path(os.path.abspath(target))


def _trusted_git_directory(trusted_repo: Path) -> Path:
    """Resolve trusted Git administration without first invoking Git on it."""
    repo = Path(trusted_repo).absolute()
    _trusted_path_ancestry(repo)
    repo_info = _owned_git_entry(repo, field="trusted repository")
    if not stat.S_ISDIR(repo_info.st_mode):
        raise MaterializationError("trusted repository must be a real directory")
    dot_git = repo / ".git"
    dot_git_info = _owned_git_entry(dot_git, field="trusted Git administration")
    if stat.S_ISDIR(dot_git_info.st_mode):
        git_dir = dot_git
    elif stat.S_ISREG(dot_git_info.st_mode):
        git_dir = _gitdir_pointer(dot_git, prefix="gitdir: ")
    else:
        raise MaterializationError("trusted Git administration must be a directory or gitdir file")
    git_dir_info = _owned_git_entry(git_dir, field="trusted Git directory")
    if not stat.S_ISDIR(git_dir_info.st_mode):
        raise MaterializationError("trusted Git directory must be a real directory")

    common_pointer = git_dir / "commondir"
    common_dir = _gitdir_pointer(common_pointer) if common_pointer.exists() else git_dir
    common_info = _owned_git_entry(common_dir, field="trusted Git common directory")
    if not stat.S_ISDIR(common_info.st_mode):
        raise MaterializationError("trusted Git common directory must be a real directory")
    if common_dir != git_dir and common_dir not in git_dir.parents:
        raise MaterializationError("trusted Git directory is outside its common directory")
    _trusted_path_ancestry(git_dir)
    _trusted_path_ancestry(common_dir)
    if (common_dir / "objects/info/alternates").exists():
        raise MaterializationError("trusted Git object alternates are outside the accepted boundary")

    roots = (common_dir,) if common_dir == git_dir else (common_dir, git_dir)
    seen: set[Path] = set()
    for root in roots:
        for current, directories, files in os.walk(root, followlinks=False):
            current_path = Path(current)
            for name in directories + files:
                entry = current_path / name
                if entry in seen:
                    continue
                seen.add(entry)
                _owned_git_entry(entry, field="trusted Git administration entry")
    return common_dir


def _protocol_authority(protocol_snapshot: object) -> tuple[str, list[str]]:
    try:
        protocol = validate_protocol_snapshot(protocol_snapshot)
    except IdentityError as exc:
        raise MaterializationError(f"frozen protocol is invalid: {exc}") from exc
    return protocol["accepted_build"]["commit_sha"], protocol["candidate_allowlist"]


def _changed_paths(raw: bytes) -> list[str]:
    fields = raw.split(b"\0")
    if fields[-1] != b"" or len(fields) % 2 != 1:
        raise MaterializationError("candidate Git diff is malformed")
    paths: list[str] = []
    for index in range(0, len(fields) - 1, 2):
        try:
            status = fields[index].decode("ascii")
            path = fields[index + 1].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise MaterializationError("candidate Git diff contains unsafe metadata") from exc
        if status not in {"A", "M", "D", "T"}:
            raise MaterializationError(f"unsupported candidate Git diff status: {status}")
        paths.append(_safe_path(path, field="candidate diff path"))
    return paths


@dataclass(frozen=True, slots=True)
class _ImportedBuild:
    repository: Path
    base_commit_sha: str
    commit_sha: str
    tree_sha: str
    candidate_allowlist: list[str]
    entries: list[tuple[str, str, str, str]]
    blob_sizes: dict[str, int]
    context: _GitContext


def _import_bundle(
    stage: Path, *, bundle_source: Path, trusted_repo: Path, expected_base: str,
    candidate_allowlist: object, lock: CampaignLock,
) -> _ImportedBuild:
    lock.require_held(stage.parent)
    _owner_directory(stage, field="materialization stage")
    allowlist = _allowlist(candidate_allowlist)
    expected_base = _oid(expected_base, field="expected_base")
    trusted_git_dir = _trusted_git_directory(trusted_repo)

    bundle = stage / "candidate.bundle"
    _copy_bundle(Path(bundle_source), bundle, lock=lock)
    context = _git_context(stage / "git-control")
    object_format = _git_text(context, "rev-parse", "--show-object-format", cwd=trusted_git_dir)
    if object_format not in {"sha1", "sha256"}:
        raise MaterializationError(f"unsupported trusted Git object format: {object_format}")
    expected_length = 40 if object_format == "sha1" else 64
    _oid(expected_base, field="expected_base", length=expected_length)
    resolved_base = _git_text(
        context, "rev-parse", "--verify", f"{expected_base}^{{commit}}", cwd=trusted_git_dir
    )
    if resolved_base != expected_base:
        raise MaterializationError("expected_base is not the exact trusted commit")

    repository = stage / "quarantine.git"
    _git(context, "init", "--bare", f"--object-format={object_format}", os.fspath(repository))
    _git(
        context,
        "fetch",
        "--no-tags",
        "--no-write-fetch-head",
        os.fspath(trusted_git_dir),
        expected_base,
        cwd=repository,
    )
    _git(context, "update-ref", "refs/trusted/base", expected_base, cwd=repository)

    _git(context, "bundle", "verify", os.fspath(bundle), cwd=repository)
    _git(context, "fetch", "--no-tags", "--no-write-fetch-head", os.fspath(bundle),
         "+refs/heads/candidate:refs/candidate", cwd=repository)
    candidate = _git_text(context, "rev-parse", "--verify", "refs/candidate^{commit}", cwd=repository)
    parents = _git_text(context, "rev-list", "--parents", "-n", "1", candidate, cwd=repository)
    if parents.split() != [candidate, expected_base]:
        raise MaterializationError("candidate must be exactly one direct, non-merge commit over expected_base")
    tree_sha = _git_text(context, "rev-parse", f"{candidate}^{{tree}}", cwd=repository)
    base_tree = _git_text(context, "rev-parse", f"{expected_base}^{{tree}}", cwd=repository)
    if tree_sha == base_tree:
        raise MaterializationError("candidate tree must differ from the trusted base tree")
    raw_diff = _git(context, "diff-tree", "--no-commit-id", "--name-status", "-r", "-z",
                    "--no-renames", expected_base, candidate, cwd=repository)
    changed = _changed_paths(raw_diff)
    if not changed:
        raise MaterializationError("candidate commit must contain a non-empty diff")
    outside = sorted(path for path in changed if not any(path.startswith(p) for p in allowlist))
    if outside:
        raise MaterializationError(f"candidate diff escapes the frozen allowlist: {outside}")

    raw_tree = _git(context, "ls-tree", "-rz", "--full-tree", f"{candidate}^{{tree}}", cwd=repository)
    try:
        entries = gitutil.parse_raw_tree(raw_tree)
    except gitutil.GitError as exc:
        raise MaterializationError(str(exc)) from exc
    paths: list[str] = []
    for mode, object_type, oid, path in entries:
        safe = _safe_path(path)
        _oid(oid, field=f"Git blob ID for {safe}", length=expected_length)
        if object_type != "blob" or mode not in _ALLOWED_GIT_MODES:
            raise MaterializationError(f"Git tree entry must be a 100644/100755 blob: {safe} ({mode} {object_type})")
        paths.append(safe)
    if not entries or len(paths) != len(set(paths)):
        raise MaterializationError("candidate Git tree must contain unique blob paths")
    if len(entries) > MAX_MATERIALIZED_FILES:
        raise MaterializationError(
            f"candidate Git tree exceeds the {MAX_MATERIALIZED_FILES}-file limit"
        )
    blob_sizes = _blob_sizes(context, repository, entries)
    _git(context, "fsck", "--strict", "--full", "--no-reflogs", cwd=repository)
    return _ImportedBuild(
        repository,
        expected_base,
        candidate,
        tree_sha,
        allowlist,
        entries,
        blob_sizes,
        context,
    )


def _blob_sizes(
    context: _GitContext,
    repository: Path,
    entries: list[tuple[str, str, str, str]],
) -> dict[str, int]:
    object_ids = list(dict.fromkeys(entry[2] for entry in entries))
    raw = _git(
        context,
        "cat-file",
        "--batch-check=%(objectname) %(objecttype) %(objectsize)",
        cwd=repository,
        input_bytes=("\n".join(object_ids) + "\n").encode("ascii"),
    )
    sizes: dict[str, int] = {}
    try:
        lines = raw.decode("ascii").splitlines()
        for line in lines:
            oid, object_type, raw_size = line.split()
            if oid not in object_ids or object_type != "blob" or oid in sizes:
                raise ValueError
            size = int(raw_size)
            if size < 0:
                raise ValueError
            sizes[oid] = size
    except (UnicodeDecodeError, ValueError) as exc:
        raise MaterializationError("Git blob size query returned malformed metadata") from exc
    if set(sizes) != set(object_ids):
        raise MaterializationError("Git blob size query did not cover the complete tree")
    oversized = [path for _mode, _type, oid, path in entries if sizes[oid] > MAX_BLOB_BYTES]
    if oversized:
        raise MaterializationError(
            f"candidate Git blob exceeds the {MAX_BLOB_BYTES}-byte limit: {oversized[0]}"
        )
    total = sum(sizes[oid] for _mode, _type, oid, _path in entries)
    if total > MAX_MATERIALIZED_BYTES:
        raise MaterializationError(
            f"candidate Git tree exceeds the {MAX_MATERIALIZED_BYTES}-byte materialized limit"
        )
    return sizes


def _canonical_receipt_bytes(receipt: object) -> bytes:
    try:
        return canonical_json(receipt).encode("utf-8") + b"\n"
    except ValueError as exc:
        raise MaterializationError("materialization receipt is not standard JSON") from exc


def _build_projection(rows: list[dict[str, str]], allowlist: list[str]) -> tuple[list[dict[str, str]], str]:
    selected = [row for row in rows if any(row["path"].startswith(p) for p in allowlist)]
    try:
        canonical = canonical_build_rows(selected, candidate_allowlist=allowlist)
        digest = canonical_build_digest(canonical, candidate_allowlist=allowlist)
    except ProtocolError as exc:
        raise MaterializationError(str(exc)) from exc
    return canonical, digest


def _validate_receipt(value: object) -> dict[str, Any]:
    if type(value) is not dict or set(value) != RECEIPT_FIELDS:
        raise MaterializationError("materialization receipt has wrong fields")
    if value["schema_version"] != SCHEMA_VERSION:
        raise MaterializationError("unsupported materialization receipt schema")
    base = _oid(value["base_commit_sha"], field="base_commit_sha")
    commit = _oid(value["commit_sha"], field="commit_sha", length=len(base))
    tree = _oid(value["tree_sha"], field="tree_sha", length=len(base))
    if base == commit:
        raise MaterializationError("materialization commit must differ from its base")
    allowlist = _allowlist(value["candidate_allowlist"])
    tree_digest = value["git_tree_digest"]
    digest = value["materialized_digest"]
    receipt_digest = value["receipt_digest"]
    if type(tree_digest) is not str or _SHA256.fullmatch(tree_digest) is None:
        raise MaterializationError("git_tree_digest must be lowercase SHA-256")
    if type(digest) is not str or _SHA256.fullmatch(digest) is None:
        raise MaterializationError("materialized_digest must be lowercase SHA-256")
    if type(receipt_digest) is not str or _SHA256.fullmatch(receipt_digest) is None:
        raise MaterializationError("receipt_digest must be lowercase SHA-256")
    authoritative = {
        "schema_version": SCHEMA_VERSION, "base_commit_sha": base,
        "commit_sha": commit, "tree_sha": tree, "candidate_allowlist": allowlist,
        "git_tree_digest": tree_digest, "materialized_digest": digest,
    }
    if digest_json(authoritative, domain=RECEIPT_DIGEST_DOMAIN) != receipt_digest:
        raise MaterializationError("materialization receipt digest does not match its fields")
    return {**authoritative, "receipt_digest": receipt_digest}


def _materialize_git_tree(imported: _ImportedBuild, tree: Path, *, lock: CampaignLock) -> list[dict[str, str]]:
    lock.require_held(lock.store_root)
    tree.mkdir(mode=0o700)
    rows: list[dict[str, str]] = []
    directories = {tree}
    for mode, _object_type, oid, relative in sorted(imported.entries, key=lambda row: row[3]):
        destination = tree.joinpath(*PurePosixPath(relative).parts)
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        directories.update((destination.parent, *destination.parents))
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(destination, flags, 0o600)
        try:
            checksum = _stream_blob(imported, oid, descriptor)
            os.fchmod(descriptor, 0o555 if mode == "100755" else 0o444)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        rows.append({"path": relative, "mode": mode, "sha256": checksum})
    materialized_dirs = (path for path in directories if tree == path or tree in path.parents)
    for directory in sorted(materialized_dirs, key=lambda path: len(path.parts), reverse=True):
        directory.chmod(0o555)
    return rows


def _stream_blob(imported: _ImportedBuild, oid: str, descriptor: int) -> str:
    process = subprocess.Popen(
        _git_command(imported.context, "cat-file", "blob", oid, cwd=imported.repository),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=imported.context.environment,
    )
    assert process.stdout is not None
    digest = hashlib.sha256()
    written = 0
    try:
        while True:
            chunk = process.stdout.read(1024 * 1024)
            if not chunk:
                break
            written += len(chunk)
            digest.update(chunk)
            view = memoryview(chunk)
            while view:
                view = view[os.write(descriptor, view) :]
        stderr = process.stderr.read() if process.stderr is not None else b""
        returncode = process.wait()
    except BaseException:
        process.kill()
        process.wait()
        raise
    finally:
        process.stdout.close()
        if process.stderr is not None:
            process.stderr.close()
    if returncode != 0:
        error = stderr.decode("utf-8", errors="replace").strip()
        raise MaterializationError(
            f"sanitized Git cat-file blob failed: {error or 'no diagnostic'}"
        )
    if written != imported.blob_sizes[oid]:
        raise MaterializationError("Git blob size changed after bounded preflight")
    return digest.hexdigest()


def _scan_materialized_tree(tree: Path) -> list[dict[str, str]]:
    _owner_directory(tree, field="materialized Git tree", mode=0o555)
    rows: list[dict[str, str]] = []
    observed_directories: set[str] = set()
    for current, directories, files in os.walk(tree, topdown=True, followlinks=False):
        current_path = Path(current)
        _owner_directory(current_path, field="materialized Git directory", mode=0o555)
        for name in sorted(directories):
            child = current_path / name
            relative = child.relative_to(tree).as_posix()
            _safe_path(relative)
            _owner_directory(child, field=f"materialized Git directory {relative}", mode=0o555)
            observed_directories.add(relative)
        for name in sorted(files):
            path = current_path / name
            relative = _safe_path(path.relative_to(tree).as_posix())
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
                raise MaterializationError(f"materialized Git file is unsafe: {relative}")
            file_mode = stat.S_IMODE(info.st_mode)
            if file_mode == 0o444:
                git_mode = "100644"
            elif file_mode == 0o555:
                git_mode = "100755"
            else:
                raise MaterializationError(f"materialized Git file has wrong mode: {relative}")
            if info.st_size > MAX_BLOB_BYTES:
                raise MaterializationError(f"materialized Git file exceeds size limit: {relative}")
            rows.append({"path": relative, "mode": git_mode,
                         "sha256": _file_sha256(path)})
    rows.sort(key=lambda row: row["path"])
    if len(rows) > MAX_MATERIALIZED_FILES:
        raise MaterializationError("materialized Git tree exceeds file-count limit")
    if sum((tree / row["path"]).stat().st_size for row in rows) > MAX_MATERIALIZED_BYTES:
        raise MaterializationError("materialized Git tree exceeds total size limit")
    implied: set[str] = set()
    for row in rows:
        parent = PurePosixPath(row["path"]).parent
        while parent != PurePosixPath("."):
            implied.add(parent.as_posix())
            parent = parent.parent
    if observed_directories != implied:
        raise MaterializationError("materialized Git tree contains an empty directory")
    return rows


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_receipt(path: Path) -> dict[str, Any]:
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o444:
        raise MaterializationError("receipt.json must be regular, conductor-owned, and 0444")
    raw = path.read_bytes()
    try:
        value = strict_json_loads(raw.decode("utf-8"), field_name=RECEIPT_NAME)
    except (UnicodeDecodeError, ValueError) as exc:
        raise MaterializationError("receipt.json is not strict UTF-8 JSON") from exc
    receipt = _validate_receipt(value)
    if raw != _canonical_receipt_bytes(receipt):
        raise MaterializationError("receipt.json is not canonical JSON")
    return receipt


def _verify_materialization(
    materialization: object, *, expected_commit_sha: str
) -> dict[str, Any]:
    try:
        root = Path(materialization)
    except TypeError as exc:
        raise MaterializationError("materialization must be a filesystem path") from exc
    _owner_directory(root, field="materialization", mode=0o555)
    try:
        names = sorted(path.name for path in root.iterdir())
    except OSError as exc:
        raise MaterializationError("cannot inspect materialization") from exc
    if names != [RECEIPT_NAME, TREE_NAME]:
        raise MaterializationError(f"unexpected materialization entries: {names}")
    receipt = _read_receipt(root / RECEIPT_NAME)
    if receipt["commit_sha"] != expected_commit_sha:
        raise MaterializationError("materialization receipt does not match expected commit")
    rows = _scan_materialized_tree(root / TREE_NAME)
    try:
        tree_digest = canonical_git_tree_digest(rows)
    except ProtocolError as exc:
        raise MaterializationError(str(exc)) from exc
    if tree_digest != receipt["git_tree_digest"]:
        raise MaterializationError("materialized Git tree does not match receipt digest")
    _selected, digest = _build_projection(rows, receipt["candidate_allowlist"])
    if digest != receipt["materialized_digest"]:
        raise MaterializationError("materialized Git build projection changed")
    return receipt


def verify_materialization(materialization: object) -> dict[str, Any]:
    """Rehash a canonical published Git build and its allowlisted projection."""
    try:
        root = Path(materialization)
    except TypeError as exc:
        raise MaterializationError("materialization must be a filesystem path") from exc
    prefix = "build-"
    expected_commit_sha = root.name.removeprefix(prefix)
    if not root.name.startswith(prefix) or _OID.fullmatch(expected_commit_sha) is None:
        raise MaterializationError("published materialization must use build-{commit_sha}")
    return _verify_materialization(root, expected_commit_sha=expected_commit_sha)


def _remove_stage(stage: Path, store_root: Path) -> None:
    if not stage.exists():
        return
    if stage.parent != store_root or not stage.name.startswith(".stage-") or stage.is_symlink():
        raise MaterializationError("refusing to remove anything except a known direct-child stage")
    for current, _directories, _files in os.walk(stage):
        Path(current).chmod(0o700)
    shutil.rmtree(stage)


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def materialize_candidate_bundle(
    bundle_path: Path, *, trusted_repo: Path, protocol_snapshot: object,
    lock: CampaignLock,
) -> tuple[Path, dict[str, Any]]:
    """Import, validate, seal, and atomically publish one optimizer bundle."""
    lock.require_held(lock.store_root)
    expected_base, candidate_allowlist = _protocol_authority(protocol_snapshot)
    stage = Path(tempfile.mkdtemp(prefix=".stage-", dir=lock.store_root))
    stage.chmod(0o700)
    _owner_directory(stage, field="materialization stage")
    try:
        imported = _import_bundle(
            stage, bundle_source=Path(bundle_path), trusted_repo=Path(trusted_repo),
            expected_base=expected_base, candidate_allowlist=candidate_allowlist, lock=lock,
        )
        rows = _materialize_git_tree(imported, stage / TREE_NAME, lock=lock)
        _selected, materialized_digest = _build_projection(rows, imported.candidate_allowlist)
        try:
            git_tree_digest = canonical_git_tree_digest(rows)
        except ProtocolError as exc:
            raise MaterializationError(str(exc)) from exc
        authoritative_receipt = {
            "schema_version": SCHEMA_VERSION,
            "base_commit_sha": imported.base_commit_sha,
            "commit_sha": imported.commit_sha,
            "tree_sha": imported.tree_sha,
            "candidate_allowlist": imported.candidate_allowlist,
            "git_tree_digest": git_tree_digest,
            "materialized_digest": materialized_digest,
        }
        receipt = _validate_receipt(
            {
                **authoritative_receipt,
                "receipt_digest": digest_json(
                    authoritative_receipt, domain=RECEIPT_DIGEST_DOMAIN
                ),
            }
        )
        shutil.rmtree(imported.repository)
        (stage / "candidate.bundle").unlink()
        shutil.rmtree(stage / "git-control")
        receipt_path = stage / RECEIPT_NAME
        receipt_path.write_bytes(_canonical_receipt_bytes(receipt))
        receipt_path.chmod(0o444)
        stage.chmod(0o555)
        if _verify_materialization(
            stage, expected_commit_sha=imported.commit_sha
        ) != receipt:
            raise MaterializationError("sealed stage verification changed its receipt")

        final = lock.store_root / f"build-{imported.commit_sha}"
        if final.exists() or final.is_symlink():
            try:
                existing = verify_materialization(final)
            except MaterializationError as exc:
                raise MaterializationError(f"existing materialization conflicts and is invalid: {final.name}") from exc
            if existing != receipt:
                raise MaterializationError(f"existing materialization conflicts with candidate: {final.name}")
            _remove_stage(stage, lock.store_root)
            return final, existing
        lock.require_held(lock.store_root)
        os.rename(stage, final)
        _fsync_directory(lock.store_root)
        return final, verify_materialization(final)
    except BaseException:
        _remove_stage(stage, lock.store_root)
        raise


@contextmanager
def consume_materialization(materialization: Path) -> Iterator[tuple[Path, dict[str, Any]]]:
    """Verify immediately before and after one immutable-build consumer."""
    before = verify_materialization(materialization)
    try:
        yield Path(materialization) / TREE_NAME, before
    finally:
        after = verify_materialization(materialization)
        if after != before:
            raise MaterializationError("materialization receipt changed during consumption")


def project_build_identity(
    materialization: object, *, protocol_snapshot: object
) -> dict[str, Any]:
    """Project a verified D2 receipt into a candidate D1 build identity."""
    receipt = verify_materialization(materialization)
    expected_base, candidate_allowlist = _protocol_authority(protocol_snapshot)
    if (
        receipt["base_commit_sha"] != expected_base
        or receipt["candidate_allowlist"] != candidate_allowlist
    ):
        raise MaterializationError("materialization does not match frozen protocol authority")
    try:
        return validate_build_identity(
            {
                "role": "candidate",
                "commit_sha": receipt["commit_sha"],
                "tree_sha": receipt["tree_sha"],
                "materialized_digest": receipt["materialized_digest"],
                "immutable": True,
            },
            evidence_mode="benchmark",
        )
    except IdentityError as exc:
        raise MaterializationError(str(exc)) from exc
