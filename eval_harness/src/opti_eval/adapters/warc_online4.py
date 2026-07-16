"""One concrete WARC-Bench ``online.4`` qualification adapter.

The adapter deliberately has no source registry or backend abstraction.  It
validates one closed owner-supplied configuration, runs the repository-owned
lifecycle over pinned primitive runtime boundaries, invokes the pinned native
JavaScript verifier, and emits the existing result/trace/artifact contract.
``local_fixture`` substitutes only those primitives and is non-reportable.
"""
from __future__ import annotations

import copy
import hashlib
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from .base import Adapter, AdapterExecutionContext
from ..admissions import require_verifier_admission
from ..identity import (
    REPEATED_PROTOCOL_FIELDS,
    REPEATED_SECTION_FIELDS,
    SOURCE_RUNTIME_FIELDS,
    IdentityError,
    digest_json,
    validate_repeated_protocol,
)
from ..models import TaskResult, artifact_ref
from ..util import atomic_write_json, read_json, read_jsonl, sha256_file, write_jsonl
from ..warc_online4_runtime import (
    MODEL_NAME,
    MODEL_ROUTE,
    ONLINE4_MATCHER,
    UPSTREAM_START_URL,
    RuntimeFailure,
    _verify_applied_request,
    action_tool_schema_digest,
    run_lifecycle,
)


TASK_ID = "warc-bench-online-4"
SOURCE = "warc_bench"
NATIVE_TASK_ID = "online.4"
UPSTREAM_COMMIT = "98d213ccd2b4380761738e1d144467a8695e37c5"
UPSTREAM_MANIFEST = "src/orby/subtask_benchmark/environments/benchmark.json"
UPSTREAM_MANIFEST_BLOB = "6b2bc7ee04b3231325fe3a84b195d26d0c589287"
UPSTREAM_DATA_PATH = (
    "environments/web_archives/alaska_airlines/"
    "alaska_airlines_flight_booking.wacz"
)
CONFIG_FIELDS = {
    "schema_version", "mode", "task", "source", "wacz", "verifier",
    "provenance", "runtime", "executor", "credentials", "confinement",
    "limits", "treatment_path", "protocol_identity",
}
RUNTIME_FIELDS = {
    "python", "node", "warc_bench", "replay", "browsergym", "gymnasium",
    "playwright", "playwright_driver", "browser", "sandbox", "cdp_port",
}
VERSIONED_FIELDS = {"path", "sha256", "version_command", "expected_version"}
WARC_VERIFIER_FIELDS = {
    "id", "path", "sha256", "admissions_path", "admissions_sha256",
}
WARC_LIMIT_FIELDS = {"timeout_seconds", "deadline_seconds", "action_budget"}
PROTOCOL_IDENTITY_FIELDS = {
    "source_runtime", "activation_instrumentation", "lane", "repeated_protocol",
}
WARC_NESTED_REQUIRED_FIELDS = {
    "runtime": RUNTIME_FIELDS,
    "verifier": WARC_VERIFIER_FIELDS,
    "limits": WARC_LIMIT_FIELDS,
    "protocol_identity": PROTOCOL_IDENTITY_FIELDS,
    "protocol_identity.source_runtime": SOURCE_RUNTIME_FIELDS,
    "protocol_identity.repeated_protocol": REPEATED_PROTOCOL_FIELDS,
    **{
        f"protocol_identity.repeated_protocol.{name}": fields
        for name, fields in REPEATED_SECTION_FIELDS.items()
    },
}
RUNTIME_LAUNCHER = Path(__file__).resolve().parents[1] / "warc_online4_runtime.py"


class WarcOnline4Error(ValueError):
    """Actionable qualification/preflight failure."""


def _closed(value: object, fields: set[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != fields:
        missing = sorted(fields - set(value) if isinstance(value, dict) else fields)
        extra = sorted(set(value) - fields if isinstance(value, dict) else set())
        raise WarcOnline4Error(f"{label} fields mismatch; missing={missing}, unsupported={extra}")
    return value


def _text(value: object, label: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise WarcOnline4Error(f"{label} must be a non-empty string without edge whitespace")
    return value


def _sha(value: object, label: str) -> str:
    value = _text(value, label)
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise WarcOnline4Error(f"{label} must be 64 lowercase hexadecimal characters")
    return value


def _absolute_file(path_value: object, expected_sha: object, label: str) -> Path:
    path = Path(_text(path_value, f"{label}.path"))
    if not path.is_absolute():
        raise WarcOnline4Error(f"{label}.path must be absolute")
    try:
        path.lstat()
    except OSError as exc:
        raise WarcOnline4Error(f"{label}.path is not readable: {path}") from exc
    if path.is_symlink() or not path.is_file():
        raise WarcOnline4Error(f"{label}.path must be a regular non-symlink file: {path}")
    actual = sha256_file(path)
    expected = _sha(expected_sha, f"{label}.sha256")
    if actual != expected:
        raise WarcOnline4Error(
            f"{label}.sha256 mismatch for {path}: expected {expected}, got {actual}"
        )
    return path


def _versioned(value: object, label: str) -> dict[str, Any]:
    row = _closed(value, VERSIONED_FIELDS, label)
    path = _absolute_file(row["path"], row["sha256"], label)
    command = row["version_command"]
    if (
        type(command) is not list or not command
        or any(type(arg) is not str or not arg for arg in command)
        or not Path(command[0]).is_absolute()
    ):
        raise WarcOnline4Error(
            f"{label}.version_command must be a non-empty argv with an absolute executable"
        )
    expected = _text(row["expected_version"], f"{label}.expected_version")
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=10,
            check=False, env={"LC_ALL": "C", "LANG": "C"},
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise WarcOnline4Error(f"{label} version command could not run: {exc}") from exc
    observed = "\n".join(part.strip() for part in (completed.stdout, completed.stderr) if part.strip())
    if completed.returncode != 0 or observed != expected:
        raise WarcOnline4Error(
            f"{label} version mismatch: expected {expected!r}, got {observed!r} "
            f"(exit {completed.returncode})"
        )
    return {**copy.deepcopy(row), "path": str(path)}


def _safe_relative(value: object, label: str) -> str:
    text = _text(value, label)
    path = PurePosixPath(text)
    if path.is_absolute() or path.as_posix() != text or any(part in {"", ".", ".."} for part in path.parts):
        raise WarcOnline4Error(f"{label} must be a safe relative POSIX path")
    return text


def _contained_file(root: Path, relative: str, label: str) -> Path:
    path = root.joinpath(*PurePosixPath(relative).parts)
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise WarcOnline4Error(f"{label} is missing: {relative}") from exc
    if not resolved.is_relative_to(root.resolve()) or not resolved.is_file():
        raise WarcOnline4Error(f"{label} escapes its trusted root: {relative}")
    current = root
    for part in PurePosixPath(relative).parts:
        current = current / part
        if current.is_symlink():
            raise WarcOnline4Error(f"{label} contains a symlink: {relative}")
    return resolved


def _protocol_identity(value: object, label: str) -> dict[str, Any]:
    row = _closed(value, {"id", "revision", "digest"}, label)
    _text(row["id"], f"{label}.id")
    _text(row["revision"], f"{label}.revision")
    _sha(row["digest"], f"{label}.digest")
    return row


def load_and_preflight_config(config_path: Path) -> dict[str, Any]:
    """Return the closed, identity-verified configuration without running a task."""
    if config_path.is_symlink() or not config_path.is_file():
        raise WarcOnline4Error(
            f"WARC online.4 config must be a regular non-symlink file: {config_path}"
        )
    config_path = config_path.resolve()
    raw = _closed(read_json(config_path), CONFIG_FIELDS, "WARC online.4 config")
    if raw["schema_version"] != "0.1.0":
        raise WarcOnline4Error("WARC online.4 config schema_version must be '0.1.0'")
    if raw["mode"] not in {"production", "local_fixture"}:
        raise WarcOnline4Error("WARC online.4 config mode must be production or local_fixture")

    task = _closed(raw["task"], {"id", "source", "native_task_id"}, "task")
    expected_task = {"id": TASK_ID, "source": SOURCE, "native_task_id": NATIVE_TASK_ID}
    if task != expected_task:
        raise WarcOnline4Error(f"task identity must be exactly {expected_task}")
    source = _closed(
        raw["source"],
        {"upstream_commit", "manifest_path", "manifest_blob_sha1", "data_path"},
        "source",
    )
    expected_source = {
        "upstream_commit": UPSTREAM_COMMIT,
        "manifest_path": UPSTREAM_MANIFEST,
        "manifest_blob_sha1": UPSTREAM_MANIFEST_BLOB,
        "data_path": UPSTREAM_DATA_PATH,
    }
    if source != expected_source:
        raise WarcOnline4Error(f"source identity must be exactly {expected_source}")

    wacz = _closed(raw["wacz"], {"path", "sha256", "start_url"}, "wacz")
    verifier = _closed(
        raw["verifier"],
        WARC_VERIFIER_FIELDS,
        "verifier",
    )
    wacz_path = _absolute_file(wacz["path"], wacz["sha256"], "wacz")
    verifier_path = _absolute_file(verifier["path"], verifier["sha256"], "verifier")
    try:
        verifier_script = verifier_path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError) as exc:
        raise WarcOnline4Error(f"verifier.path is not readable JavaScript: {exc}") from exc
    if verifier_script != ONLINE4_MATCHER:
        raise WarcOnline4Error(
            "verifier.path must contain the exact pinned online.4 JavaScript matcher"
        )
    start_url = _text(wacz["start_url"], "wacz.start_url")
    if start_url != UPSTREAM_START_URL:
        raise WarcOnline4Error(
            "wacz.start_url must equal the pinned WARC online.4 replay page URL"
        )
    admissions_path = _absolute_file(
        verifier["admissions_path"], verifier["admissions_sha256"],
        "verifier.admissions",
    )
    verifier_id = _text(verifier["id"], "verifier.id")
    try:
        require_verifier_admission(
            admissions_path,
            verifier_id=verifier_id,
            task_id=TASK_ID,
            verifier_checksum=verifier["sha256"],
        )
    except ValueError as exc:
        raise WarcOnline4Error(f"verifier admission failed: {exc}") from exc

    provenance = _closed(
        raw["provenance"],
        {
            "wacz_origin", "verifier_origin", "license_id", "license_evidence_path",
            "license_evidence_sha256", "acknowledged",
        },
        "provenance",
    )
    for name in ("wacz_origin", "verifier_origin", "license_id"):
        _text(provenance[name], f"provenance.{name}")
    if provenance["acknowledged"] is not True:
        raise WarcOnline4Error("provenance.acknowledged must be true")
    license_path = _absolute_file(
        provenance["license_evidence_path"],
        provenance["license_evidence_sha256"],
        "provenance.license_evidence",
    )

    runtime = _closed(raw["runtime"], RUNTIME_FIELDS, "runtime")
    checked_runtime = {
        name: _versioned(runtime[name], f"runtime.{name}")
        for name in (
            "python", "node", "warc_bench", "replay", "browsergym", "gymnasium",
            "playwright", "playwright_driver", "browser", "sandbox",
        )
    }
    cdp_port = runtime["cdp_port"]
    if type(cdp_port) is not int or not 1024 <= cdp_port <= 65535:
        raise WarcOnline4Error("runtime.cdp_port must be an integer from 1024 through 65535")
    checked_runtime["cdp_port"] = cdp_port
    pinned_runtime_paths = {
        item["path"] for item in checked_runtime.values() if type(item) is dict
    }
    if any(
        item["version_command"][0] not in pinned_runtime_paths
        for item in checked_runtime.values() if type(item) is dict
    ):
        raise WarcOnline4Error(
            "runtime version commands must use an executable pinned in the same runtime object"
        )
    if raw["mode"] == "production":
        if Path(checked_runtime["sandbox"]["path"]).name != "bwrap":
            raise WarcOnline4Error("runtime.sandbox.path must be the pinned bubblewrap 'bwrap' binary")
        if Path(checked_runtime["replay"]["path"]).as_posix().split("/")[-2:] != ["dist", "index.js"]:
            raise WarcOnline4Error(
                "runtime.replay.path must be the pinned webreplay-standalone dist/index.js file"
            )

    executor = _closed(
        raw["executor"],
        {"provider", "route", "model", "settings", "tool_schema_digest"},
        "executor",
    )
    for name in ("provider", "route", "model"):
        _text(executor[name], f"executor.{name}")
    if type(executor["settings"]) is not dict:
        raise WarcOnline4Error("executor.settings must be an object")
    if set(executor["settings"]) != {"temperature", "max_tokens"}:
        raise WarcOnline4Error(
            "executor.settings must contain exactly temperature and max_tokens"
        )
    if type(executor["settings"]["temperature"]) not in {int, float}:
        raise WarcOnline4Error("executor.settings.temperature must be numeric")
    if type(executor["settings"]["max_tokens"]) is not int or executor["settings"]["max_tokens"] < 1:
        raise WarcOnline4Error("executor.settings.max_tokens must be an integer >= 1")
    tool_digest = _sha(executor["tool_schema_digest"], "executor.tool_schema_digest")
    if tool_digest != action_tool_schema_digest():
        raise WarcOnline4Error(
            "executor.tool_schema_digest does not match the repository-owned BrowserGym action tools"
        )
    if raw["mode"] == "production" and (
        executor["provider"] != "opencode-go"
        or executor["route"] != MODEL_ROUTE
        or executor["model"] != MODEL_NAME
    ):
        raise WarcOnline4Error(
            f"production executor must be opencode-go {MODEL_NAME} at {MODEL_ROUTE}"
        )

    credentials = _closed(raw["credentials"], {"required_env"}, "credentials")
    required_env = credentials["required_env"]
    if type(required_env) is not list or any(
        type(name) is not str or not name or name != name.strip() for name in required_env
    ) or len(set(required_env)) != len(required_env):
        raise WarcOnline4Error("credentials.required_env must be a unique string array")
    if raw["mode"] == "production":
        if required_env != ["OPENCODE_API_KEY"]:
            raise WarcOnline4Error(
                "production credentials.required_env must be exactly ['OPENCODE_API_KEY']"
            )
        missing = [name for name in required_env if not os.environ.get(name)]
        if missing:
            raise WarcOnline4Error(
                "missing required credential environment variables: " + ", ".join(missing)
            )

    confinement = _closed(
        raw["confinement"],
        {"single_host", "network", "filesystem", "optimizer_uid", "static_inbox"},
        "confinement",
    )
    if confinement["single_host"] is not True:
        raise WarcOnline4Error("confinement.single_host must be true")
    if confinement["network"] != "loopback-only":
        raise WarcOnline4Error("confinement.network must be 'loopback-only'")
    if confinement["filesystem"] != "read-only-except-task-output":
        raise WarcOnline4Error(
            "confinement.filesystem must be 'read-only-except-task-output'"
        )
    optimizer_uid = confinement["optimizer_uid"]
    if type(optimizer_uid) is not int or optimizer_uid < 0:
        raise WarcOnline4Error("confinement.optimizer_uid must be a non-negative integer")
    inbox = Path(_text(confinement["static_inbox"], "confinement.static_inbox"))
    if not inbox.is_absolute() or not inbox.is_dir() or inbox.is_symlink():
        raise WarcOnline4Error("confinement.static_inbox must be an absolute non-symlink directory")
    if inbox.stat().st_uid != optimizer_uid:
        raise WarcOnline4Error(
            f"confinement.static_inbox must be owned by optimizer_uid {optimizer_uid}"
        )
    if raw["mode"] == "production" and os.geteuid() == optimizer_uid:
        raise WarcOnline4Error("production conductor UID must differ from optimizer_uid")

    limits = _closed(raw["limits"], WARC_LIMIT_FIELDS, "limits")
    for name in ("timeout_seconds", "deadline_seconds", "action_budget"):
        if type(limits[name]) is not int or limits[name] < 1:
            raise WarcOnline4Error(f"limits.{name} must be an integer >= 1")
    if limits["timeout_seconds"] > limits["deadline_seconds"]:
        raise WarcOnline4Error("limits.timeout_seconds must not exceed deadline_seconds")

    checked = copy.deepcopy(raw)
    checked["wacz"]["path"] = str(wacz_path)
    checked["verifier"]["path"] = str(verifier_path)
    checked["verifier"]["admissions_path"] = str(admissions_path)
    checked["provenance"]["license_evidence_path"] = str(license_path)
    checked["runtime"] = checked_runtime
    checked["confinement"]["static_inbox"] = str(inbox.resolve())
    checked["treatment_path"] = _safe_relative(raw["treatment_path"], "treatment_path")
    protocol_identity = _closed(
        raw["protocol_identity"],
        PROTOCOL_IDENTITY_FIELDS,
        "protocol_identity",
    )
    if any(type(protocol_identity[name]) is not dict for name in protocol_identity):
        raise WarcOnline4Error("protocol_identity values must be objects")
    source_runtime = _closed(
        protocol_identity["source_runtime"],
        SOURCE_RUNTIME_FIELDS,
        "protocol_identity.source_runtime",
    )
    _text(source_runtime["source_revision"], "protocol_identity.source_runtime.source_revision")
    for name in ("setup", "reset", "environment", "browser"):
        _protocol_identity(
            source_runtime[name], f"protocol_identity.source_runtime.{name}"
        )
    _protocol_identity(
        protocol_identity["activation_instrumentation"],
        "protocol_identity.activation_instrumentation",
    )
    lane = _closed(protocol_identity["lane"], {"id", "config_path"}, "protocol_identity.lane")
    _text(lane["id"], "protocol_identity.lane.id")
    _safe_relative(lane["config_path"], "protocol_identity.lane.config_path")
    repeated = protocol_identity["repeated_protocol"]
    try:
        validate_repeated_protocol(
            repeated,
            runtimes={SOURCE: source_runtime},
            mode="benchmark" if raw["mode"] == "production" else "simulated",
        )
    except IdentityError as exc:
        detail = str(exc).replace(
            "repeated_protocol", "protocol_identity.repeated_protocol", 1
        )
        raise WarcOnline4Error(detail) from exc
    checked["config_digest"] = digest_json(checked, domain="opti.warc-online4-config.v1")
    return checked


class WarcOnline4Adapter(Adapter):
    """Qualified adapter for only ``warc-bench-online-4``."""

    name = "warc-online4"

    def __init__(self, config_path: Path, *, candidate_root: Path) -> None:
        self.config = load_and_preflight_config(config_path)
        self.config_path = config_path.resolve()
        self.candidate_root = candidate_root.resolve()
        self.benchmark_reportable = self.config["mode"] == "production"
        self.activation_observation: dict[str, Any] | None = None

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "benchmark_reportable": self.benchmark_reportable,
            "config_digest": self.config["config_digest"],
            "mode": self.config["mode"],
            "task_id": TASK_ID,
            "source_commit": UPSTREAM_COMMIT,
            "treatment_path": self.config["treatment_path"],
        }

    def validate_protocol(self, protocol: dict[str, Any]) -> None:
        if type(protocol) is not dict:
            raise WarcOnline4Error("WARC execution requires a frozen protocol object")
        if protocol["executor"] != {
            **self.config["executor"],
            "snapshot": self.config["executor"]["model"],
            "revision": self.config["executor"]["model"],
            "settings_digest": digest_json(
                self.config["executor"]["settings"], domain="opti.executor-settings.v1"
            ),
        }:
            raise WarcOnline4Error("WARC config executor identity does not match the frozen protocol")
        verifier = protocol["verifier_bundle"]
        admissions_digest = hashlib.sha256(
            b"opti.admissions.v1\0"
            + Path(self.config["verifier"]["admissions_path"]).read_bytes()
        ).hexdigest()
        if verifier != {
            "id": self.config["verifier"]["id"],
            "checksum": self.config["verifier"]["sha256"],
            "bundle_digest": self.config["verifier"]["sha256"],
            "admissions_digest": admissions_digest,
        }:
            raise WarcOnline4Error("WARC config verifier identity does not match the frozen protocol")
        expected_identity = self.config["protocol_identity"]
        if protocol.get("source_runtimes") != {SOURCE: expected_identity["source_runtime"]}:
            raise WarcOnline4Error("WARC source runtime identity does not match the frozen protocol")
        if protocol.get("activation_instrumentation") != expected_identity["activation_instrumentation"]:
            raise WarcOnline4Error("WARC activation instrumentation does not match the frozen protocol")
        lane = protocol.get("lane")
        if (
            type(lane) is not dict
            or {name: lane.get(name) for name in ("id", "config_path")}
            != expected_identity["lane"]
            or type(lane.get("config_digest")) is not str
            or len(lane["config_digest"]) != 64
        ):
            raise WarcOnline4Error("WARC lane identity does not match the frozen protocol")
        if type(protocol.get("repeated_protocol")) is not dict:
            raise WarcOnline4Error("WARC execution lacks the frozen repeated protocol")
        expected_mode = "benchmark" if self.config["mode"] == "production" else "simulated"
        if protocol.get("evidence_mode") != expected_mode:
            raise WarcOnline4Error("WARC evidence mode does not match the frozen protocol")

    def run(
        self,
        task: dict[str, Any],
        task_dir: Path,
        *,
        execution_context: AdapterExecutionContext,
    ) -> TaskResult:
        if task.get("id") != TASK_ID or task.get("source") != SOURCE:
            raise WarcOnline4Error(f"adapter accepts only {TASK_ID!r} from {SOURCE!r}")
        upstream = task.get("upstream")
        if not isinstance(upstream, dict) or any(
            upstream.get(key) != value
            for key, value in {
                "version": f"Git commit {UPSTREAM_COMMIT}",
                "native_task_id": NATIVE_TASK_ID,
                "source_manifest": UPSTREAM_MANIFEST,
                "source_checksum": UPSTREAM_MANIFEST_BLOB,
                "data_path": UPSTREAM_DATA_PATH,
            }.items()
        ):
            raise WarcOnline4Error("scheduled task has the wrong pinned WARC source identity")

        treatment_rel = self.config["treatment_path"]
        treatment = _contained_file(
            self.candidate_root, treatment_rel, "WARC treatment path"
        )
        treatment_sha = sha256_file(treatment)
        work = task_dir / "warc-online4"
        work.mkdir(mode=0o700)
        request_path = work / "request.json"
        runtime_result_path = work / "runtime-result.json"
        final_state_path = work / "final-state.json"
        request = {
            "schema_version": "0.2.0",
            "mode": self.config["mode"],
            "task_id": TASK_ID,
            "native_task_id": NATIVE_TASK_ID,
            "goal": task.get("goal"),
            "wacz_path": self.config["wacz"]["path"],
            "wacz_sha256": self.config["wacz"]["sha256"],
            "wacz_start_url": self.config["wacz"]["start_url"],
            "source_identity": self.config["source"],
            "verifier": {
                "id": self.config["verifier"]["id"],
                "path": self.config["verifier"]["path"],
                "sha256": self.config["verifier"]["sha256"],
            },
            "treatment_path": str(treatment),
            "treatment_relative_path": treatment_rel,
            "treatment_sha256": treatment_sha,
            "runtime": self.config["runtime"],
            "executor": self.config["executor"],
            "credential_env": self.config["credentials"]["required_env"],
            "limits": self.config["limits"],
            "runtime_launcher_sha256": sha256_file(RUNTIME_LAUNCHER),
            "confinement": {
                "single_host": True,
                "network": "loopback-only",
                "filesystem": "read-only-except-task-output",
                "task_output": str(work),
                "optimizer_uid": self.config["confinement"]["optimizer_uid"],
                "static_inbox": self.config["confinement"]["static_inbox"],
            },
        }
        request_digest = digest_json(request, domain="opti.warc-online4-request.v1")
        request["request_digest"] = request_digest
        atomic_write_json(request_path, request)

        try:
            run_lifecycle(request_path, runtime_result_path)
        except (OSError, ValueError, RuntimeFailure) as exc:
            raise WarcOnline4Error(f"WARC online.4 lifecycle failed: {exc}") from exc
        if not runtime_result_path.is_file():
            raise WarcOnline4Error("WARC online.4 lifecycle did not write its result")
        result = read_json(runtime_result_path)
        secret_values = [
            os.environ[name].encode()
            for name in self.config["credentials"]["required_env"]
            if os.environ.get(name)
        ]
        if any(secret in runtime_result_path.read_bytes() for secret in secret_values):
            raise WarcOnline4Error("runtime result contains a credential value")
        result_fields = {
            "schema_version", "task_id", "request_digest", "reset", "steps",
            "final_state", "verifier", "artifacts", "activation", "cleanup",
        }
        result = _closed(result, result_fields, "runtime result")
        if result["schema_version"] != "0.4.0" or result["task_id"] != TASK_ID:
            raise WarcOnline4Error("runtime result has the wrong schema/task identity")
        if result["request_digest"] != request_digest:
            raise WarcOnline4Error("runtime result does not bind the exact request")
        reset = _closed(
            result["reset"], {"start_url", "initial_state", "source_manifest"},
            "reset",
        )
        if reset["start_url"] != UPSTREAM_START_URL:
            raise WarcOnline4Error(
                "reset.start_url must equal the pinned WARC online.4 replay page URL"
            )
        if type(reset["initial_state"]) is not dict:
            raise WarcOnline4Error("reset must capture an objective initial state")
        source_manifest = _closed(
            reset["source_manifest"],
            {
                "git_blob_sha1", "content_sha256", "online4_row_sha256",
                "verified_from_installed_bytes",
            },
            "reset.source_manifest",
        )
        if source_manifest["git_blob_sha1"] != UPSTREAM_MANIFEST_BLOB:
            raise WarcOnline4Error("runtime consumed the wrong WARC task manifest blob")
        _sha(source_manifest["content_sha256"], "reset.source_manifest.content_sha256")
        _sha(
            source_manifest["online4_row_sha256"],
            "reset.source_manifest.online4_row_sha256",
        )
        expected_verified = self.config["mode"] == "production"
        if source_manifest["verified_from_installed_bytes"] is not expected_verified:
            raise WarcOnline4Error(
                "runtime source-manifest evidence class does not match execution mode"
            )
        steps = result["steps"]
        if type(steps) is not list or not steps or len(steps) > self.config["limits"]["action_budget"]:
            raise WarcOnline4Error("runtime steps must be non-empty and within action_budget")
        for index, step in enumerate(steps):
            _closed(step, {"action", "outcome", "browser_state"}, f"steps[{index}]")
            if any(type(step[name]) is not dict for name in ("action", "outcome", "browser_state")):
                raise WarcOnline4Error(f"steps[{index}] fields must be objects")
        if type(result["final_state"]) is not dict:
            raise WarcOnline4Error("runtime final_state must be an object")
        activation = _closed(
            result["activation"],
            {
                "path", "sha256", "runtime_trace_path", "runtime_trace_sha256",
                "treatment_event_id", "model_request_event_ids",
            },
            "activation",
        )
        if activation["path"] != treatment_rel or activation["sha256"] != treatment_sha:
            raise WarcOnline4Error(
                "trusted lifecycle activation does not bind the treatment bytes"
            )
        runtime_trace_rel = _safe_relative(
            activation["runtime_trace_path"], "activation.runtime_trace_path"
        )
        runtime_trace_path = _contained_file(
            work, runtime_trace_rel, "trusted lifecycle trace"
        )
        runtime_trace_sha = sha256_file(runtime_trace_path)
        if activation["runtime_trace_sha256"] != runtime_trace_sha:
            raise WarcOnline4Error("trusted lifecycle trace digest mismatch")
        runtime_events = read_jsonl(runtime_trace_path)
        treatment_events = [
            row for row in runtime_events
            if row.get("event_id") == activation["treatment_event_id"]
            and row.get("event") == "treatment_loaded"
        ]
        if len(treatment_events) != 1 or any(
            treatment_events[0].get(name) != value
            for name, value in {
                "path": treatment_rel,
                "sha256": treatment_sha,
                "byte_count": treatment.stat().st_size,
            }.items()
        ):
            raise WarcOnline4Error(
                "trusted lifecycle trace lacks the exact treatment load event"
            )
        model_request_event_ids = activation["model_request_event_ids"]
        if (
            type(model_request_event_ids) is not list
            or not model_request_event_ids
            or len(set(model_request_event_ids)) != len(model_request_event_ids)
        ):
            raise WarcOnline4Error("trusted lifecycle activation lacks applied model request events")
        request_events = {
            row.get("event_id"): row
            for row in runtime_events
            if row.get("event") == "model_request_applied"
        }
        for event_id in model_request_event_ids:
            event = request_events.get(event_id)
            if type(event) is not dict or event.get("treatment_sha256") != treatment_sha:
                raise WarcOnline4Error(
                    "trusted lifecycle trace does not bind model request to treatment bytes"
                )
            model_request_rel = _safe_relative(event.get("request_path"), "model request path")
            model_request_path = _contained_file(work, model_request_rel, "applied model request")
            applied = model_request_path.read_bytes().rstrip(b"\n")
            if hashlib.sha256(applied).hexdigest() != event.get("applied_request_sha256"):
                raise WarcOnline4Error("applied model request digest mismatch")
            try:
                _verify_applied_request(applied, treatment.read_bytes(), treatment_sha)
            except RuntimeFailure as exc:
                raise WarcOnline4Error(str(exc)) from exc
        cleanup = _closed(result["cleanup"], {"completed"}, "cleanup")
        if cleanup["completed"] is not True:
            raise WarcOnline4Error("runtime cleanup.completed must be true")
        verifier_results = _closed(
            result["verifier"], {"initial", "final"}, "runtime verifier"
        )
        expected_verifier_identity = {
            "verifier_id": self.config["verifier"]["id"],
            "verifier_sha256": self.config["verifier"]["sha256"],
            "upstream_commit": UPSTREAM_COMMIT,
            "manifest_blob_sha1": UPSTREAM_MANIFEST_BLOB,
        }
        checked_verifiers: dict[str, dict[str, Any]] = {}
        verifier_fields = {
            "passed", "verifier_id", "verifier_sha256", "upstream_commit",
            "manifest_blob_sha1", "page_url", "state_sha256",
        }
        for phase in ("initial", "final"):
            row = _closed(
                verifier_results[phase], verifier_fields,
                f"runtime verifier.{phase}",
            )
            if any(row.get(name) != value for name, value in expected_verifier_identity.items()):
                raise WarcOnline4Error(
                    f"runtime verifier.{phase} has the wrong admitted/source identity"
                )
            if type(row["passed"]) is not bool:
                raise WarcOnline4Error(f"runtime verifier.{phase}.passed must be boolean")
            if row["page_url"] != UPSTREAM_START_URL:
                raise WarcOnline4Error(
                    f"runtime verifier.{phase}.page_url must equal the pinned online.4 URL"
                )
            _sha(row["state_sha256"], f"runtime verifier.{phase}.state_sha256")
            checked_verifiers[phase] = row
        if checked_verifiers["initial"]["passed"] is not False:
            raise WarcOnline4Error(
                "reset live page must independently fail the native verifier"
            )
        verifier_result = checked_verifiers["final"]

        atomic_write_json(final_state_path, result["final_state"])

        declared_artifacts = []
        artifacts = result["artifacts"]
        if type(artifacts) is not list or not artifacts:
            raise WarcOnline4Error("runtime artifacts must be a non-empty array")
        for index, raw_artifact in enumerate(artifacts):
            row = _closed(raw_artifact, {"path", "kind", "media_type"}, f"artifacts[{index}]")
            rel = _safe_relative(row["path"], f"artifacts[{index}].path")
            path = _contained_file(work, rel, "runtime artifact")
            if any(secret in path.read_bytes() for secret in secret_values):
                raise WarcOnline4Error(f"runtime artifact contains a credential value: {rel}")
            declared_artifacts.append(
                artifact_ref(
                    path, evidence_root=task_dir, kind=_text(row["kind"], "artifact kind"),
                    media_type=_text(row["media_type"], "artifact media_type"),
                    visibility=("judge", "orchestrator"),
                )
            )
        runtime_trace_ref = artifact_ref(
            runtime_trace_path,
            evidence_root=task_dir,
            kind="activation_trace",
            media_type="application/x-ndjson",
            visibility=("judge", "orchestrator"),
        )
        if any(secret in runtime_trace_path.read_bytes() for secret in secret_values):
            raise WarcOnline4Error("trusted lifecycle trace contains a credential value")
        final_ref = artifact_ref(
            final_state_path, evidence_root=task_dir, kind="final_state",
            media_type="application/json", visibility=("judge", "orchestrator"),
        )
        verifier_evidence_ref = artifact_ref(
            runtime_result_path, evidence_root=task_dir, kind="verifier_evidence",
            media_type="application/json", visibility=("judge", "orchestrator"),
        )

        events: list[dict[str, Any]] = []
        base_time = datetime.now(timezone.utc).replace(microsecond=0)
        epoch = 0

        def event(event_type: str, actor: str, payload: dict[str, Any], refs: list[dict[str, Any]] | None = None) -> None:
            sequence = len(events) + 1
            row: dict[str, Any] = {
                "schema_version": "0.1-draft", "run_id": execution_context.run_id,
                "task_id": TASK_ID, "event_id": f"event-{sequence}", "sequence": sequence,
                "timestamp": (base_time + timedelta(milliseconds=sequence)).isoformat(),
                "monotonic_ms": float(sequence), "actor": actor, "event_type": event_type,
                "visibility": ["judge", "orchestrator"], "payload": payload,
                "artifact_refs": list(refs or []),
            }
            if event_type in {"browser_state", "action_requested", "action_result"}:
                row["browser_state_epoch"] = epoch
            events.append(row)

        event(
            "checkpoint",
            "orchestrator",
            {
                "phase": "trusted_activation",
                "treatment_path": treatment_rel,
                "treatment_sha256": treatment_sha,
                "runtime_launcher_sha256": request["runtime_launcher_sha256"],
                "treatment_event_id": activation["treatment_event_id"],
                "model_request_event_ids": model_request_event_ids,
            },
            [runtime_trace_ref],
        )
        event("browser_state", "browser", {"phase": "reset", **reset})
        for step in steps:
            event("action_requested", "executor", step["action"])
            event("action_result", "browser", step["outcome"])
            epoch += 1
            event("browser_state", "browser", step["browser_state"])
        event("browser_state", "browser", {"phase": "final", **result["final_state"]}, [final_ref])
        status = "passed" if verifier_result["passed"] else "failed"
        event(
            "verifier_result", "verifier",
            {"status": status, "verifier_id": self.config["verifier"]["id"],
             "verifier_checksum": self.config["verifier"]["sha256"],
             "live_page_evidence": verifier_result},
            [verifier_evidence_ref],
        )
        trace_path = task_dir / "trace.jsonl"
        write_jsonl(trace_path, events)
        trace_ref = artifact_ref(
            trace_path, evidence_root=task_dir, kind="trace",
            media_type="application/x-ndjson", visibility=("judge", "orchestrator"),
        )
        self.activation_observation = {
            "path": treatment_rel,
            "sha256": treatment_sha,
            "request_sha256": hashlib.sha256(request_path.read_bytes()).hexdigest(),
            "runtime_launcher_sha256": request["runtime_launcher_sha256"],
            "runtime_trace": {
                "path": runtime_trace_ref["uri"],
                "sha256": runtime_trace_sha,
            },
            "task_trace": {
                "path": "trace.jsonl",
                "sha256": sha256_file(trace_path),
            },
            "treatment_event_id": activation["treatment_event_id"],
            "model_request_event_ids": model_request_event_ids,
            "applied_request_sha256": [
                request_events[event_id]["applied_request_sha256"]
                for event_id in model_request_event_ids
            ],
        }
        return TaskResult(
            task_id=TASK_ID, source=SOURCE, status=status,
            reward=1.0 if status == "passed" else 0.0,
            verifier={
                "id": self.config["verifier"]["id"],
                "checksum": self.config["verifier"]["sha256"],
                "outcome": status,
            },
            trace_path="trace.jsonl",
            artifacts=[
                trace_ref, runtime_trace_ref, final_ref, verifier_evidence_ref,
                *declared_artifacts,
            ],
            metrics={
                "browser_actions": len(steps), "request_digest": request_digest,
                "activation_sha256": treatment_sha,
                "activation_trace_sha256": runtime_trace_sha,
                "runtime_launcher_sha256": request["runtime_launcher_sha256"],
            },
            metadata={
                "benchmark_reportable": self.benchmark_reportable,
                "evidence_class": "benchmark" if self.benchmark_reportable else "local_fixture",
                "config_digest": self.config["config_digest"], "cleanup_completed": True,
            },
        )
