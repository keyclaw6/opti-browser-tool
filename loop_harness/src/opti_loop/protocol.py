"""Conductor-owned construction and persistence of frozen iteration protocols."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

import opti_eval
import opti_judge
import opti_loop
from opti_eval.catalog import select_tasks
from opti_eval.identity import (
    IdentityError,
    PROTOCOL_SCHEMA_VERSION,
    code_component_identity,
    digest_json,
    finalize_protocol_snapshot,
    make_run_context,
    normalize_adapter_identity,
    validate_candidate_allowlist,
    validate_protocol_snapshot,
)
from opti_eval.models import canonical_json, strict_json_loads

from . import gitutil
from .campaign import Campaign

PROTOCOL_FILENAME = "protocol.snapshot.json"
_SUITE_ROLES = ("dev", "smoke", "regression")
BUILD_DIGEST_DOMAIN = "opti.build.v1"
GIT_TREE_DIGEST_DOMAIN = "opti.git-tree.v1"
BUILD_ROW_FIELDS = frozenset({"path", "mode", "sha256"})
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class ProtocolError(RuntimeError):
    """Trusted protocol inputs are missing, unsafe, or inconsistent."""


def _file_digest(path: Path, *, domain: str) -> str:
    if path.is_symlink() or not path.is_file():
        raise ProtocolError(f"identity input must be a real file: {path}")
    return hashlib.sha256(domain.encode("utf-8") + b"\0" + path.read_bytes()).hexdigest()


def _trusted_code_components() -> list[dict[str, str]]:
    packages = (
        ("opti_eval", opti_eval.__version__, Path(opti_eval.__file__).resolve().parent),
        ("opti_loop", opti_loop.__version__, Path(opti_loop.__file__).resolve().parent),
        ("opti_judge", opti_judge.__version__, Path(opti_judge.__file__).resolve().parent),
    )
    try:
        return [
            code_component_identity(
                package=package,
                version=version,
                package_root=package_root,
            )
            for package, version, package_root in packages
        ]
    except IdentityError as exc:
        raise ProtocolError(f"trusted code identity failed: {exc}") from exc


def normalize_candidate_allowlist(value: object) -> list[str]:
    """Normalize configured ``directory/**`` entries into exact prefixes."""
    if type(value) is not list or not value:
        raise ProtocolError("campaign candidate_allowlist must be a non-empty array")
    prefixes: list[str] = []
    for entry in value:
        if type(entry) is not str or not entry:
            raise ProtocolError("candidate_allowlist entries must be non-empty strings")
        if entry.endswith("/**"):
            raw = entry[:-3]
        elif entry.endswith("/"):
            raw = entry[:-1]
        else:
            raise ProtocolError(
                "candidate_allowlist entries must name a directory with /**"
            )
        posix = PurePosixPath(raw)
        if (
            posix.is_absolute()
            or not posix.parts
            or posix.as_posix() != raw
            or any(part in {"", ".", ".."} for part in posix.parts)
        ):
            raise ProtocolError(f"unsafe candidate_allowlist entry: {entry!r}")
        prefix = posix.as_posix() + "/"
        if prefix in prefixes:
            raise ProtocolError(f"duplicate candidate_allowlist prefix: {prefix!r}")
        prefixes.append(prefix)
    prefixes.sort()
    try:
        return validate_candidate_allowlist(prefixes)
    except IdentityError as exc:
        raise ProtocolError(str(exc)) from exc


def canonical_git_path(value: object) -> str:
    if type(value) is not str or not value or "\x00" in value or "\\" in value:
        raise ProtocolError("build row path must be a safe relative POSIX path")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or path.as_posix() != value
        or any(part in {"", ".", "..", ".git"} for part in path.parts)
    ):
        raise ProtocolError("build row path must be a safe relative POSIX path")
    return value


def canonical_git_rows(value: object) -> list[dict[str, str]]:
    """Validate the full-tree row shape shared by D1 and D2."""
    if type(value) is not list or not value:
        raise ProtocolError("Git tree resolves to no files")
    rows: list[dict[str, str]] = []
    paths: list[str] = []
    for index, entry in enumerate(value):
        if type(entry) is not dict or set(entry) != BUILD_ROW_FIELDS:
            raise ProtocolError(f"build row {index} has wrong fields")
        path = canonical_git_path(entry["path"])
        mode = entry["mode"]
        checksum = entry["sha256"]
        if mode not in {"100644", "100755"}:
            raise ProtocolError(f"build row {index} has unsupported Git mode")
        if type(checksum) is not str or _SHA256.fullmatch(checksum) is None:
            raise ProtocolError(f"build row {index} has invalid SHA-256")
        rows.append({"path": path, "mode": mode, "sha256": checksum})
        paths.append(path)
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise ProtocolError("build rows must be sorted by unique path")
    return rows


def canonical_build_rows(
    value: object, *, candidate_allowlist: list[str]
) -> list[dict[str, str]]:
    """Close the one D1/D2 allowlisted projection used for build identity."""
    try:
        allowlist = validate_candidate_allowlist(candidate_allowlist)
    except IdentityError as exc:
        raise ProtocolError(str(exc)) from exc
    rows = canonical_git_rows(value)
    paths = [row["path"] for row in rows]
    outside = [path for path in paths if not any(path.startswith(p) for p in allowlist)]
    if outside:
        raise ProtocolError(f"build rows are outside candidate_allowlist: {outside}")
    for prefix in allowlist:
        if not any(path.startswith(prefix) for path in paths):
            raise ProtocolError(
                f"candidate_allowlist prefix resolves to no Git blobs: {prefix!r}"
            )
    return rows


def canonical_build_digest(
    value: object, *, candidate_allowlist: list[str]
) -> str:
    rows = canonical_build_rows(value, candidate_allowlist=candidate_allowlist)
    return digest_json(rows, domain=BUILD_DIGEST_DOMAIN)


def canonical_git_tree_digest(value: object) -> str:
    """Digest one complete canonical Git tree without making its rows durable."""
    return digest_json(canonical_git_rows(value), domain=GIT_TREE_DIGEST_DOMAIN)


def _worktree_build_rows(
    repo_root: Path, *, candidate_allowlist: list[str]
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    resolved_repo = repo_root.resolve()
    for prefix in candidate_allowlist:
        root = repo_root.joinpath(*PurePosixPath(prefix[:-1]).parts)
        if root.is_symlink():
            raise ProtocolError(f"candidate_allowlist root is a symlink: {prefix!r}")
        try:
            resolved = root.resolve(strict=True)
        except OSError as exc:
            raise ProtocolError(f"candidate_allowlist entry does not resolve: {prefix!r}") from exc
        if resolved_repo not in resolved.parents:
            raise ProtocolError(f"candidate_allowlist entry escapes repository: {prefix!r}")
        descendants = [resolved] if resolved.is_file() else sorted(resolved.rglob("*"))
        for path in descendants:
            if path.is_symlink():
                raise ProtocolError(f"candidate build contains a symlink: {path}")
            if path.is_file():
                mode = path.stat().st_mode & 0o777
                if mode not in {0o644, 0o755}:
                    raise ProtocolError(f"candidate build file mode is not 0644/0755: {path}")
                relative = path.relative_to(resolved_repo).as_posix()
                canonical_git_path(relative)
                git_mode = "100755" if mode == 0o755 else "100644"
                rows.append(
                    {
                        "path": relative,
                        "mode": git_mode,
                        "sha256": _file_sha256(path),
                    }
                )
    rows.sort(key=lambda row: row["path"])
    return canonical_build_rows(rows, candidate_allowlist=candidate_allowlist)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_identity(
    repo_root: Path,
    *,
    commit_sha: str,
    role: str,
    candidate_allowlist: list[str],
    immutable: bool = False,
) -> dict[str, Any]:
    """Hash the live allowlisted surface with the shared D1/D2 row authority."""
    try:
        validate_candidate_allowlist(candidate_allowlist)
    except IdentityError as exc:
        raise ProtocolError(str(exc)) from exc
    if gitutil.head_sha(repo_root) != commit_sha:
        raise ProtocolError("build commit_sha does not match the materialized worktree HEAD")
    rows = _worktree_build_rows(repo_root, candidate_allowlist=candidate_allowlist)
    return {
        "role": role,
        "commit_sha": commit_sha,
        "tree_sha": gitutil.rev_parse(repo_root, f"{commit_sha}^{{tree}}"),
        "materialized_digest": canonical_build_digest(
            rows, candidate_allowlist=candidate_allowlist
        ),
        "immutable": immutable,
    }


def _suite_bindings(
    repo_root: Path,
    suites: dict[str, Any],
    adapter: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    bindings: list[dict[str, Any]] = []
    selected_by_role: dict[str, list[dict[str, Any]]] = {}
    for role in _SUITE_ROLES:
        name = suites.get(role)
        if type(name) is not str or not name:
            raise ProtocolError(f"campaign suites.{role} must be a non-empty string")
        suite, tasks = select_tasks(repo_root, name)
        selected_by_role[role] = tasks
        suite_path = repo_root / "evals" / "suites" / f"{name}.json"
        if not suite_path.is_file():
            # select_tasks may have resolved a catalog alias.
            from opti_eval.catalog import SUITE_ALIASES

            suite_path = repo_root / "evals" / "suites" / f"{SUITE_ALIASES.get(name, name)}.json"
        bound_tasks: list[dict[str, Any]] = []
        for task in tasks:
            bound = copy.deepcopy(task)
            verifier_id = adapter.get("verifier_id")
            verifier_checksum = adapter.get("verifier_checksum")
            if verifier_id is not None or verifier_checksum is not None:
                verification = bound.get("verification")
                if verification is None:
                    verification = {}
                if type(verification) is not dict:
                    raise ProtocolError(
                        f"scheduled task {task['id']} verification must be an object"
                    )
                bound["verification"] = {
                    **verification,
                    "verifier_id": verifier_id,
                    "verifier_checksum": verifier_checksum,
                }
            bound_tasks.append(bound)
        bindings.append(
            {
                "role": role,
                "name": name,
                "id": suite["id"],
                "manifest_digest": _file_digest(suite_path, domain="opti.suite-manifest.v1"),
                "tasks": [
                    {
                        "id": task["id"],
                        "source": task["source"],
                        "record_digest": digest_json(task, domain="opti.task-record.v1"),
                    }
                    for task in bound_tasks
                ],
            }
        )
    return bindings, selected_by_role


def _identity_config(campaign: Campaign) -> dict[str, Any]:
    identity = campaign.config.get("identity")
    if type(identity) is not dict:
        raise ProtocolError("campaign identity must be a closed object")
    expected = {
        "evidence_mode",
        "source_runtimes",
        "executor",
        "verifier_bundle",
        "activation_instrumentation",
        "lane",
    }
    if set(identity) != expected:
        missing = sorted(expected - set(identity))
        extra = sorted(set(identity) - expected)
        raise ProtocolError(f"campaign identity fields mismatch; missing={missing}, unsupported={extra}")
    return copy.deepcopy(identity)


def _admissions_digest(campaign: Campaign, configured: str, *, mode: str) -> str:
    path = campaign.store.admissions_path
    if path.is_file():
        actual = _file_digest(path, domain="opti.admissions.v1")
        if mode == "benchmark" and configured != actual:
            raise ProtocolError(
                "benchmark verifier admissions_digest does not match the exact admissions file"
            )
        return actual
    if mode == "benchmark":
        raise ProtocolError(f"benchmark verifier admissions file is missing: {path}")
    return configured


def _matched_blocks(
    dev_tasks: list[dict[str, Any]],
    source_runtimes: dict[str, dict[str, Any]],
    repeated: dict[str, Any],
) -> list[dict[str, Any]]:
    config = repeated.get("matched_blocks")
    if type(config) is not dict:
        raise ProtocolError("repeated_protocol.matched_blocks must be an object")
    seeds = config.get("seeds")
    arm_order = config.get("arm_order")
    if type(seeds) is not list or type(arm_order) is not list:
        raise ProtocolError("repeated protocol must declare seeds and arm_order arrays")
    blocks: list[dict[str, Any]] = []
    for task in dev_tasks:
        source = task["source"]
        runtime = source_runtimes.get(source)
        if type(runtime) is not dict:
            raise ProtocolError(f"campaign source_runtimes missing scheduled source {source!r}")
        for seed in seeds:
            blocks.append(
                {
                    "id": f"{task['id']}:seed-{seed}",
                    "task_id": task["id"],
                    "source": source,
                    "seed": seed,
                    "reset_digest": runtime["reset"]["digest"],
                    "environment_digest": runtime["environment"]["digest"],
                    "browser_digest": runtime["browser"]["digest"],
                    "arm_order": copy.deepcopy(arm_order),
                }
            )
    return blocks


def build_protocol_snapshot(
    campaign: Campaign,
    worktree: Path,
    *,
    iteration: int,
    purpose: str = "iteration",
    repeat_count: int | None = None,
) -> dict[str, Any]:
    """Resolve all mutable campaign/repository inputs into one closed record."""
    identity = _identity_config(campaign)
    mode = identity["evidence_mode"]
    suites = copy.deepcopy(campaign.config.get("suites"))
    if type(suites) is not dict:
        raise ProtocolError("campaign suites must be an object")
    adapter = copy.deepcopy(campaign.config.get("adapter", {}))
    if type(adapter) is not dict:
        raise ProtocolError("campaign adapter must be an object")
    from .evaluate import build_adapter

    try:
        live_adapter = build_adapter(adapter, repo_root=worktree)
        adapter_identity = normalize_adapter_identity(live_adapter.describe())
    except (IdentityError, TypeError, ValueError) as exc:
        raise ProtocolError(f"campaign adapter identity is invalid: {exc}") from exc
    suite_bindings, selected = _suite_bindings(worktree, suites, adapter)
    source_runtimes = identity["source_runtimes"]
    if type(source_runtimes) is not dict:
        raise ProtocolError("campaign identity.source_runtimes must be an object")
    repeated = copy.deepcopy(campaign.config.get("repeated_protocol"))
    if type(repeated) is not dict:
        raise ProtocolError("campaign repeated_protocol must be an object")
    if repeat_count is not None:
        if type(repeat_count) is not int or repeat_count < 1:
            raise ProtocolError("repeat_count must be an integer >= 1")
        try:
            repeated["repeats"]["count"] = repeat_count
            repeated["stopping"]["valid_after"] = repeat_count
            repeated["limits"]["max_runs"] = max(
                repeat_count, int(repeated["limits"]["max_runs"])
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ProtocolError(
                "campaign repeated_protocol cannot accept a frozen repeat count"
            ) from exc
    allowlist = normalize_candidate_allowlist(
        copy.deepcopy(campaign.config.get("candidate_allowlist"))
    )
    executor_config = identity["executor"]
    if type(executor_config) is not dict:
        raise ProtocolError("campaign identity.executor must be an object")
    executor = copy.deepcopy(executor_config)
    settings = executor.get("settings")
    if type(settings) is not dict:
        raise ProtocolError("campaign identity.executor.settings must be an object")
    executor["settings_digest"] = digest_json(settings, domain="opti.executor-settings.v1")
    verifier = copy.deepcopy(identity["verifier_bundle"])
    if type(verifier) is not dict or not {"id", "checksum", "bundle_digest", "admissions_digest"} <= set(verifier):
        raise ProtocolError(
            "campaign verifier_bundle must include id/checksum/bundle/admissions identity"
        )
    verifier["admissions_digest"] = _admissions_digest(
        campaign, verifier["admissions_digest"], mode=mode
    )
    verifier_id = adapter.get("verifier_id")
    verifier_checksum = adapter.get("verifier_checksum")
    if verifier_id is not None or verifier_checksum is not None:
        if {
            "id": verifier_id,
            "checksum": verifier_checksum,
        } != {
            "id": verifier["id"],
            "checksum": verifier["checksum"],
        }:
            raise ProtocolError(
                "adapter verifier binding does not match identity.verifier_bundle"
            )
    elif mode == "benchmark":
        raise ProtocolError("benchmark adapter config requires verifier_id/verifier_checksum")
    lane_config = identity["lane"]
    if type(lane_config) is not dict or set(lane_config) != {"id", "config_path"}:
        raise ProtocolError("campaign identity.lane fields must be exactly id and config_path")
    lane_path = worktree / str(lane_config["config_path"])
    lane = {
        **lane_config,
        "config_digest": _file_digest(lane_path, domain="opti.lane-config.v1"),
    }
    base_sha = str(campaign.state["accepted_base_sha"])
    accepted_build = build_identity(
        worktree,
        commit_sha=base_sha,
        role="accepted",
        candidate_allowlist=allowlist,
        immutable=False,
    )
    components = _trusted_code_components()
    payload = {
        "schema_version": PROTOCOL_SCHEMA_VERSION,
        "campaign_id": campaign.campaign_id,
        "iteration": iteration,
        "purpose": purpose,
        "evidence_mode": mode,
        "suites": suite_bindings,
        "matched_blocks": _matched_blocks(
            selected["dev"], source_runtimes, repeated
        ),
        "source_runtimes": copy.deepcopy(source_runtimes),
        "evaluator": {
            "components": components,
            "apparatus_digest": digest_json(
                components, domain="opti.trusted-code-apparatus.v1"
            ),
        },
        "verifier_bundle": verifier,
        "adapter": adapter_identity,
        "executor": executor,
        "activation_instrumentation": copy.deepcopy(identity["activation_instrumentation"]),
        "lane": lane,
        "candidate_allowlist": allowlist,
        "accepted_build": accepted_build,
        "repeated_protocol": repeated,
        "execution": {
            "adapter": adapter,
            "suites": suites,
            "thresholds": copy.deepcopy(campaign.config.get("thresholds", {})),
            "noise_band": copy.deepcopy(campaign.config.get("noise_band")),
            "fixed_variables": copy.deepcopy(campaign.config.get("fixed_variables", {})),
            "transfer": copy.deepcopy(campaign.config.get("transfer", {})),
            "exploration": copy.deepcopy(campaign.config.get("exploration", {})),
        },
    }
    try:
        return finalize_protocol_snapshot(payload)
    except IdentityError as exc:
        raise ProtocolError(f"protocol preflight failed: {exc}") from exc


def verify_runtime_bindings(
    snapshot: dict[str, Any], *, admissions_path: Path
) -> None:
    """Recompute trusted code and admissions immediately before consumption."""
    try:
        protocol = validate_protocol_snapshot(snapshot)
    except IdentityError as exc:
        raise ProtocolError(f"runtime protocol validation failed: {exc}") from exc
    actual_components = _trusted_code_components()
    if canonical_json(actual_components) != canonical_json(
        protocol["evaluator"]["components"]
    ):
        raise ProtocolError("trusted evaluator/gate/judge code drifted after protocol freeze")
    if admissions_path.is_file():
        actual_admissions = _file_digest(admissions_path, domain="opti.admissions.v1")
        if actual_admissions != protocol["verifier_bundle"]["admissions_digest"]:
            raise ProtocolError("verifier admissions drifted after protocol freeze")
    elif protocol["evidence_mode"] == "benchmark":
        raise ProtocolError("benchmark verifier admissions file disappeared after freeze")


def _atomic_create(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ProtocolError(f"frozen protocol already exists and will not be overwritten: {path}")
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".protocol-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError as exc:
            raise ProtocolError(
                f"frozen protocol already exists and will not be overwritten: {path}"
            ) from exc
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def freeze_protocol(iteration_dir: Path, snapshot: dict[str, Any]) -> Path:
    try:
        validated = validate_protocol_snapshot(snapshot)
    except IdentityError as exc:
        raise ProtocolError(f"refusing to freeze invalid protocol: {exc}") from exc
    path = iteration_dir / PROTOCOL_FILENAME
    _atomic_create(path, validated)
    return path


def load_frozen_protocol(iteration_dir: Path) -> dict[str, Any]:
    path = iteration_dir / PROTOCOL_FILENAME
    if path.is_symlink() or not path.is_file():
        raise ProtocolError(f"frozen protocol is missing or not a real file: {path}")
    try:
        parsed = strict_json_loads(path.read_text(encoding="utf-8"), field_name="frozen protocol")
        return validate_protocol_snapshot(parsed)
    except (OSError, ValueError, IdentityError) as exc:
        raise ProtocolError(f"frozen protocol is invalid: {exc}") from exc


def run_context(
    snapshot: dict[str, Any],
    build: dict[str, Any],
    *,
    arm: str,
    suite_role: str,
    task_ids: list[str],
    repeat_index: int = 0,
    seed: int = 0,
    run_id: str | None = None,
) -> dict[str, Any]:
    try:
        arguments: dict[str, Any] = {
            "arm": arm,
            "suite_role": suite_role,
            "task_ids": task_ids,
            "repeat_index": repeat_index,
            "seed": seed,
        }
        if run_id is not None:
            arguments["run_id"] = run_id
        return make_run_context(
            snapshot,
            build,
            **arguments,
        )
    except IdentityError as exc:
        raise ProtocolError(f"cannot create run context: {exc}") from exc
