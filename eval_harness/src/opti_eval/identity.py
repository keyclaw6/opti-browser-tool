"""Closed protocol, schedule, and live run identity contracts.

The conductor resolves mutable inputs into one portable protocol snapshot.
The runner validates an exact scheduled run against that snapshot and returns
an in-memory receipt. Persisted artifacts can be replayed diagnostically on
their own, but only a caller-held receipt can authorize benchmark eligibility.
"""
from __future__ import annotations

import copy
import hashlib
import re
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .models import canonical_json, validate_nonempty_string, validate_standard_json

PROTOCOL_SCHEMA_VERSION = "0.2.0"
RUN_CONTEXT_SCHEMA_VERSION = "0.2.0"
EVIDENCE_MODES = {"simulated", "benchmark"}
ARMS = {"baseline", "treatment", "diagnostic"}

PROTOCOL_FIELDS = {
    "schema_version",
    "campaign_id",
    "iteration",
    "purpose",
    "evidence_mode",
    "suites",
    "matched_blocks",
    "source_runtimes",
    "evaluator",
    "verifier_bundle",
    "adapter",
    "executor",
    "activation_instrumentation",
    "lane",
    "candidate_allowlist",
    "accepted_build",
    "repeated_protocol",
    "execution",
    "calibration_binding_digest",
    "comparison_apparatus_digest",
    "protocol_digest",
}
RUN_CONTEXT_FIELDS = {
    "schema_version",
    "run_id",
    "evidence_mode",
    "arm",
    "suite_role",
    "task_ids",
    "repeat_index",
    "seed",
    "protocol_digest",
    "build",
    "run_digest",
}
BUILD_FIELDS = {
    "role",
    "commit_sha",
    "tree_sha",
    "materialized_digest",
    "immutable",
}
SUITE_FIELDS = {"role", "name", "id", "manifest_digest", "tasks"}
TASK_BINDING_FIELDS = {"id", "source", "record_digest"}
BLOCK_FIELDS = {
    "id",
    "task_id",
    "source",
    "seed",
    "reset_digest",
    "environment_digest",
    "browser_digest",
    "arm_order",
}
COMPONENT_IDENTITY_FIELDS = {"id", "revision", "digest"}
SOURCE_RUNTIME_FIELDS = {
    "source_revision",
    "setup",
    "reset",
    "environment",
    "browser",
}
EVALUATOR_FIELDS = {"components", "apparatus_digest"}
CODE_COMPONENT_FIELDS = {"package", "version", "code_digest"}
VERIFIER_FIELDS = {"id", "checksum", "bundle_digest", "admissions_digest"}
ADAPTER_FIELDS = {"name", "benchmark_reportable", "configuration", "digest"}
EXECUTOR_FIELDS = {
    "provider",
    "route",
    "model",
    "snapshot",
    "revision",
    "settings",
    "settings_digest",
    "tool_schema_digest",
}
INSTRUMENTATION_FIELDS = {"id", "revision", "digest"}
LANE_FIELDS = {"id", "config_path", "config_digest"}
REPEATED_PROTOCOL_FIELDS = {
    "matched_blocks",
    "coverage",
    "repeats",
    "stopping",
    "outcome_handling",
    "effect",
    "non_inferiority",
    "regression",
    "champion",
    "transfer",
    "multiplicity",
    "limits",
    "calibration",
}
REPEATED_SECTION_FIELDS = {
    "matched_blocks": {"seeds", "arm_order", "interleaving", "reset_scope"},
    "coverage": {
        "minimum_fraction",
        "quorum_fraction",
        "required_sources",
        "denominator",
    },
    "repeats": {"count"},
    "stopping": {"rule", "valid_after", "optional_stopping"},
    "outcome_handling": {"invalid", "missing", "quarantined", "one_arm_only"},
    "effect": {"estimator", "uncertainty", "minimum_effect"},
    "non_inferiority": {"rule", "margin"},
    "regression": {"rule", "max_regressions"},
    "champion": {"rule", "margin"},
    "transfer": {"rule", "schedule"},
    "multiplicity": {"rule", "family"},
    "limits": {"max_runs", "deadline_seconds", "exhaustion_outcome"},
    "calibration": {"id", "digest"},
}
EXECUTION_FIELDS = {
    "adapter",
    "suites",
    "thresholds",
    "noise_band",
    "fixed_variables",
    "transfer",
    "exploration",
    "accepted_protection",
}

SUPPORTED_REPEATED_RULES = {
    "interleaving": "paired-dev-regression",
    "reset_scope": "per-task-arm",
    "denominator": "frozen_task_seed_blocks",
    "stopping": "fixed-complete-block-sets",
    "estimator": "paired-mean",
    "uncertainty": "observed-range",
    "non_inferiority": "paired-range-lower-bound",
    "regression": "no-new-failures",
    "champion": "durable-success-rate-floor",
    "transfer_rule": "scheduled-closed-checkpoint",
    "transfer_schedule": "accepted-count-cadence",
    "multiplicity_rule": "all-complete-dev-blocks",
    "multiplicity_family": "frozen-dev-blocks",
}
SUPPORTED_OUTCOME_HANDLING = {
    "invalid": "invalid",
    "missing": "inconclusive",
    "quarantined": "invalid",
    "one_arm_only": "inconclusive",
}

_HEX_DIGEST = re.compile(r"[0-9a-f]{64}")
_GIT_OBJECT = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?")
_CANDIDATE_PARENT = "harness/"
_IMMUTABLE_HARNESS_PREFIXES = (
    "harness/activation/",
    "harness/admission/",
    "harness/contracts/",
    "harness/decision/",
    "harness/evaluator/",
    "harness/evidence/",
    "harness/executor/",
    "harness/gates/",
    "harness/infra/",
    "harness/lanes/",
    "harness/model/",
    "harness/oracle/",
    "harness/protocol/",
    "harness/reset/",
    "harness/safety/",
    "harness/schemas/",
    "harness/secrets/",
    "harness/setup/",
    "harness/store/",
    "harness/tasks/",
    "harness/tracer/",
    "harness/verifier/",
)


def validate_candidate_allowlist(value: object) -> list[str]:
    """Validate the canonical candidate boundary shared by freeze and replay."""
    if type(value) is not list or not value:
        raise IdentityError("candidate_allowlist must be a non-empty ordered array")
    if any(type(entry) is not str for entry in value):
        raise IdentityError("candidate_allowlist entries must be strings")
    allowlist = list(value)
    if allowlist != sorted(allowlist) or len(set(allowlist)) != len(allowlist):
        raise IdentityError("candidate_allowlist must be sorted with unique entries")
    for entry in allowlist:
        if not entry.endswith("/"):
            raise IdentityError(
                "candidate_allowlist entries must be normalized directory prefixes"
            )
        pure = PurePosixPath(entry[:-1])
        if (
            pure.is_absolute()
            or not pure.parts
            or pure.as_posix() != entry[:-1]
            or any(part in {"", ".", ".."} for part in pure.parts)
        ):
            raise IdentityError(f"unsafe candidate_allowlist prefix: {entry!r}")
        if not entry.startswith(_CANDIDATE_PARENT):
            raise IdentityError(
                f"candidate_allowlist prefix is outside candidate harness: {entry!r}"
            )
        for forbidden in _IMMUTABLE_HARNESS_PREFIXES:
            if entry.startswith(forbidden) or forbidden.startswith(entry):
                raise IdentityError(
                    f"candidate_allowlist prefix overlaps immutable surface {forbidden!r}: {entry!r}"
                )
    for index, entry in enumerate(allowlist):
        for other in allowlist[index + 1 :]:
            if entry.startswith(other) or other.startswith(entry):
                raise IdentityError(
                    f"overlapping candidate_allowlist prefixes: {entry!r}, {other!r}"
                )
    return allowlist
_SENTINEL_NAMESPACES = (
    "simulated:",
    "placeholder:",
    "unconfigured:",
    "unpinned:",
    "uncalibrated:",
    "todo:",
    "tbd:",
)
_SENTINEL_VALUES = {
    "simulated",
    "placeholder",
    "unknown",
    "none",
    "not-calibrated",
    "not_calibrated",
    "not-admitted",
    "not_admitted",
    "unconfigured",
    "unpinned",
    "uncalibrated",
    "todo",
    "tbd",
    "latest",
}


class IdentityError(ValueError):
    """A protocol or run identity is open, incomplete, or inconsistent."""


def digest_json(value: object, *, domain: str) -> str:
    """Return a domain-separated SHA-256 over canonical standard JSON."""
    label = validate_nonempty_string(domain, field_name="digest domain")
    material = label.encode("utf-8") + b"\0" + canonical_json(value).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def _require_fields(
    value: object, expected: set[str], *, field_name: str
) -> dict[str, Any]:
    if type(value) is not dict:
        raise IdentityError(f"{field_name} must be an object")
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        details: list[str] = []
        if missing:
            details.append(f"missing {', '.join(missing)}")
        if extra:
            details.append(f"unexpected {', '.join(extra)}")
        raise IdentityError(
            f"{field_name} fields are not closed: {'; '.join(details)}"
        )
    return value


def _string(value: object, *, field_name: str) -> str:
    try:
        return validate_nonempty_string(value, field_name=field_name)
    except ValueError as exc:
        raise IdentityError(str(exc)) from exc


def _production_string(value: object, *, field_name: str, mode: str) -> str:
    text = _string(value, field_name=field_name)
    if mode == "benchmark":
        lowered = text.casefold()
        if lowered in _SENTINEL_VALUES or lowered.startswith(_SENTINEL_NAMESPACES):
            raise IdentityError(f"{field_name} must be an exact production identity")
    return text


def _digest(value: object, *, field_name: str) -> str:
    text = _string(value, field_name=field_name)
    if _HEX_DIGEST.fullmatch(text) is None:
        raise IdentityError(f"{field_name} must be a lowercase SHA-256 digest")
    return text


def _int(value: object, *, field_name: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise IdentityError(f"{field_name} must be an integer >= {minimum}")
    return value


def _number(value: object, *, field_name: str) -> float | int:
    if type(value) not in {int, float}:
        raise IdentityError(f"{field_name} must be a finite number")
    try:
        validate_standard_json(value, field_name=field_name)
    except ValueError as exc:
        raise IdentityError(str(exc)) from exc
    return value


def code_tree_digest(package_root: Path) -> str:
    """Hash the ordered Python source tree for one trusted package."""
    rows: list[dict[str, str]] = []
    for path in sorted(package_root.rglob("*.py")):
        if path.is_symlink() or not path.is_file():
            raise IdentityError(
                f"trusted code package contains a non-regular Python file: {path}"
            )
        rows.append(
            {
                "path": path.relative_to(package_root).as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    if not rows:
        raise IdentityError(f"trusted code package contains no Python source: {package_root}")
    return digest_json(rows, domain="opti.trusted-code-tree.v1")


def code_component_identity(
    *, package: str, version: str, package_root: Path
) -> dict[str, str]:
    return {
        "package": _string(package, field_name="trusted code package"),
        "version": _string(version, field_name="trusted code version"),
        "code_digest": code_tree_digest(package_root),
    }


def normalize_adapter_identity(description: object) -> dict[str, Any]:
    """Close a live adapter description into one stable execution identity."""
    if type(description) is not dict:
        raise IdentityError("adapter description must be an object")
    reserved = {
        "run_id",
        "run_context",
        "run_digest",
        "protocol_digest",
        "build",
        "digest",
    }
    forged = sorted(reserved & set(description))
    if forged:
        raise IdentityError(
            "adapter description must not set runner-owned identity field(s): "
            + ", ".join(forged)
        )
    name = _string(description.get("name"), field_name="adapter name")
    reportable = description.get("benchmark_reportable")
    if type(reportable) is not bool:
        raise IdentityError("adapter benchmark_reportable must be a boolean")
    configuration = {
        key: copy.deepcopy(value)
        for key, value in description.items()
        if key not in {"name", "benchmark_reportable"}
    }
    try:
        validate_standard_json(configuration, field_name="adapter configuration")
    except ValueError as exc:
        raise IdentityError(str(exc)) from exc
    payload: dict[str, Any] = {
        "name": name,
        "benchmark_reportable": reportable,
        "configuration": configuration,
    }
    payload["digest"] = digest_json(payload, domain="opti.adapter.v1")
    return payload


def validate_build_identity(value: object, *, evidence_mode: str) -> dict[str, Any]:
    row = _require_fields(value, BUILD_FIELDS, field_name="build identity")
    role = _string(row["role"], field_name="build identity role")
    if role not in {"accepted", "candidate", "diagnostic"}:
        raise IdentityError(
            "build identity role must be accepted, candidate, or diagnostic"
        )
    commit = _string(row["commit_sha"], field_name="build commit_sha")
    tree = _string(row["tree_sha"], field_name="build tree_sha")
    _digest(row["materialized_digest"], field_name="build materialized_digest")
    if type(row["immutable"]) is not bool:
        raise IdentityError("build immutable must be a boolean")
    if evidence_mode == "benchmark":
        if _GIT_OBJECT.fullmatch(commit) is None or _GIT_OBJECT.fullmatch(tree) is None:
            raise IdentityError(
                "benchmark build commit/tree identities must be exact Git object IDs"
            )
        if row["immutable"] is not True:
            raise IdentityError(
                "benchmark protocol requires an immutable materialized build receipt; "
                "milestone D2 is not yet satisfied"
            )
    return row


def _without_derived_digests(snapshot: dict[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(snapshot)
    value.pop("protocol_digest", None)
    value.pop("calibration_binding_digest", None)
    value.pop("comparison_apparatus_digest", None)
    return value


def calibration_binding_digest(snapshot: dict[str, Any]) -> str:
    """Bind unchanged-baseline apparatus, not calibration scheduling count."""
    value = _without_derived_digests(snapshot)
    value.pop("purpose", None)
    value.pop("iteration", None)
    execution = value.get("execution")
    if type(execution) is dict:
        execution["noise_band"] = None
    repeated = value.get("repeated_protocol")
    if type(repeated) is dict:
        if type(repeated.get("repeats")) is dict:
            repeated["repeats"]["count"] = 0
        if type(repeated.get("stopping")) is dict:
            repeated["stopping"]["valid_after"] = 0
        if type(repeated.get("limits")) is dict:
            repeated["limits"]["max_runs"] = 0
    return digest_json(value, domain="opti.calibration-binding.v2")


def comparison_apparatus_digest(snapshot: dict[str, Any]) -> str:
    """Hash comparison apparatus while excluding campaign/build/run identity."""
    value = _without_derived_digests(snapshot)
    value.pop("campaign_id", None)
    value.pop("iteration", None)
    value.pop("accepted_build", None)
    execution = value.get("execution")
    if type(execution) is dict and type(execution.get("accepted_protection")) is dict:
        execution["accepted_protection"].pop("champion_sha", None)
    return digest_json(value, domain="opti.comparison-apparatus.v1")


def protocol_digest(snapshot: dict[str, Any]) -> str:
    value = copy.deepcopy(snapshot)
    value.pop("protocol_digest", None)
    return digest_json(value, domain="opti.protocol.v2")


def _validate_component_identity(
    value: object, *, field_name: str, mode: str
) -> None:
    row = _require_fields(value, COMPONENT_IDENTITY_FIELDS, field_name=field_name)
    _production_string(row["id"], field_name=f"{field_name}.id", mode=mode)
    _production_string(
        row["revision"], field_name=f"{field_name}.revision", mode=mode
    )
    _digest(row["digest"], field_name=f"{field_name}.digest")


def validate_repeated_protocol(
    value: object, *, runtimes: dict[str, Any], mode: str
) -> tuple[dict[str, Any], list[int], list[str], int]:
    repeated = _require_fields(
        value, REPEATED_PROTOCOL_FIELDS, field_name="repeated_protocol"
    )
    for section_name, section_fields in REPEATED_SECTION_FIELDS.items():
        _require_fields(
            repeated[section_name],
            section_fields,
            field_name=f"repeated_protocol.{section_name}",
        )
    matched = repeated["matched_blocks"]
    seeds = matched["seeds"]
    if (
        type(seeds) is not list
        or not seeds
        or any(type(seed) is not int or seed < 0 for seed in seeds)
    ):
        raise IdentityError(
            "repeated_protocol.matched_blocks.seeds must be non-empty "
            "non-negative integers"
        )
    if len(set(seeds)) != len(seeds):
        raise IdentityError("repeated_protocol.matched_blocks.seeds must be unique")
    arm_order = matched["arm_order"]
    if arm_order not in (["baseline", "treatment"], ["treatment", "baseline"]):
        raise IdentityError(
            "repeated_protocol matched arm_order must contain both arms exactly once"
        )
    _production_string(
        matched["interleaving"],
        field_name="repeated_protocol.matched_blocks.interleaving",
        mode=mode,
    )
    if matched["interleaving"] != SUPPORTED_REPEATED_RULES["interleaving"]:
        raise IdentityError("unsupported repeated_protocol.matched_blocks.interleaving")
    _production_string(
        matched["reset_scope"],
        field_name="repeated_protocol.matched_blocks.reset_scope",
        mode=mode,
    )
    if matched["reset_scope"] != SUPPORTED_REPEATED_RULES["reset_scope"]:
        raise IdentityError("unsupported repeated_protocol.matched_blocks.reset_scope")
    coverage = repeated["coverage"]
    for name in ("minimum_fraction", "quorum_fraction"):
        number = _number(
            coverage[name], field_name=f"repeated_protocol.coverage.{name}"
        )
        if not 0 <= number <= 1:
            raise IdentityError(
                f"repeated_protocol.coverage.{name} must be in [0, 1]"
            )
    if coverage["required_sources"] != sorted(runtimes):
        raise IdentityError(
            "repeated_protocol.coverage.required_sources must equal frozen sources"
        )
    _string(
        coverage["denominator"],
        field_name="repeated_protocol.coverage.denominator",
    )
    if coverage["denominator"] != SUPPORTED_REPEATED_RULES["denominator"]:
        raise IdentityError("unsupported repeated_protocol.coverage.denominator")
    repeat_count = _int(
        repeated["repeats"]["count"],
        field_name="repeated_protocol.repeats.count",
        minimum=1,
    )
    _production_string(
        repeated["stopping"]["rule"],
        field_name="repeated_protocol.stopping.rule",
        mode=mode,
    )
    if repeated["stopping"]["rule"] != SUPPORTED_REPEATED_RULES["stopping"]:
        raise IdentityError("unsupported repeated_protocol.stopping.rule")
    valid_after = _int(
        repeated["stopping"]["valid_after"],
        field_name="repeated_protocol.stopping.valid_after",
        minimum=1,
    )
    if valid_after > repeat_count:
        raise IdentityError(
            "repeated_protocol.stopping.valid_after exceeds frozen repeat count"
        )
    if repeated["stopping"]["optional_stopping"] is not False:
        raise IdentityError("repeated_protocol.stopping.optional_stopping must be false")
    for name, item in repeated["outcome_handling"].items():
        _string(item, field_name=f"repeated_protocol.outcome_handling.{name}")
    if repeated["outcome_handling"] != SUPPORTED_OUTCOME_HANDLING:
        raise IdentityError("unsupported repeated_protocol.outcome_handling")
    for section_name in (
        "effect",
        "non_inferiority",
        "regression",
        "champion",
        "transfer",
        "multiplicity",
    ):
        for name, item in repeated[section_name].items():
            if name in {"minimum_effect", "margin", "max_regressions"}:
                _number(item, field_name=f"repeated_protocol.{section_name}.{name}")
            else:
                _production_string(
                    item,
                    field_name=f"repeated_protocol.{section_name}.{name}",
                    mode=mode,
                )
    if repeated["effect"]["estimator"] != SUPPORTED_REPEATED_RULES["estimator"]:
        raise IdentityError("unsupported repeated_protocol.effect.estimator")
    if repeated["effect"]["uncertainty"] != SUPPORTED_REPEATED_RULES["uncertainty"]:
        raise IdentityError("unsupported repeated_protocol.effect.uncertainty")
    fixed_rules = {
        "non_inferiority": SUPPORTED_REPEATED_RULES["non_inferiority"],
        "regression": SUPPORTED_REPEATED_RULES["regression"],
        "champion": SUPPORTED_REPEATED_RULES["champion"],
    }
    for section, rule in fixed_rules.items():
        if repeated[section]["rule"] != rule:
            raise IdentityError(f"unsupported repeated_protocol.{section}.rule")
    if repeated["transfer"] != {
        "rule": SUPPORTED_REPEATED_RULES["transfer_rule"],
        "schedule": SUPPORTED_REPEATED_RULES["transfer_schedule"],
    }:
        raise IdentityError("unsupported repeated_protocol.transfer policy")
    if repeated["multiplicity"] != {
        "rule": SUPPORTED_REPEATED_RULES["multiplicity_rule"],
        "family": SUPPORTED_REPEATED_RULES["multiplicity_family"],
    }:
        raise IdentityError("unsupported repeated_protocol.multiplicity rule")
    limits = repeated["limits"]
    max_runs = _int(
        limits["max_runs"],
        field_name="repeated_protocol.limits.max_runs",
        minimum=1,
    )
    required_runs = valid_after * len(seeds) * 2
    if max_runs < required_runs:
        raise IdentityError(
            "repeated_protocol.limits.max_runs cannot reach stopping.valid_after"
        )
    _int(
        limits["deadline_seconds"],
        field_name="repeated_protocol.limits.deadline_seconds",
        minimum=1,
    )
    if limits["exhaustion_outcome"] != "inconclusive":
        raise IdentityError(
            "repeated_protocol.limits.exhaustion_outcome must be inconclusive"
        )
    calibration = repeated["calibration"]
    _production_string(
        calibration["id"],
        field_name="repeated_protocol.calibration.id",
        mode=mode,
    )
    _digest(calibration["digest"], field_name="repeated_protocol.calibration.digest")
    return repeated, list(seeds), list(arm_order), repeat_count


def _expected_matched_blocks(
    tasks: list[dict[str, Any]],
    runtimes: dict[str, dict[str, Any]],
    seeds: list[int],
    arm_order: list[str],
) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for task in tasks:
        runtime = runtimes[task["source"]]
        for seed in seeds:
            blocks.append(
                {
                    "id": f"{task['id']}:seed-{seed}",
                    "task_id": task["id"],
                    "source": task["source"],
                    "seed": seed,
                    "reset_digest": runtime["reset"]["digest"],
                    "environment_digest": runtime["environment"]["digest"],
                    "browser_digest": runtime["browser"]["digest"],
                    "arm_order": list(arm_order),
                }
            )
    return blocks


def validate_protocol_snapshot(value: object) -> dict[str, Any]:
    snapshot = _require_fields(value, PROTOCOL_FIELDS, field_name="protocol snapshot")
    try:
        validate_standard_json(snapshot, field_name="protocol snapshot")
    except ValueError as exc:
        raise IdentityError(str(exc)) from exc
    if snapshot["schema_version"] != PROTOCOL_SCHEMA_VERSION:
        raise IdentityError(
            f"unsupported protocol schema_version {snapshot['schema_version']!r}"
        )
    mode = _string(snapshot["evidence_mode"], field_name="protocol evidence_mode")
    if mode not in EVIDENCE_MODES:
        raise IdentityError("protocol evidence_mode must be simulated or benchmark")
    _string(snapshot["campaign_id"], field_name="protocol campaign_id")
    _int(snapshot["iteration"], field_name="protocol iteration")
    _string(snapshot["purpose"], field_name="protocol purpose")

    suites = snapshot["suites"]
    if type(suites) is not list or not suites:
        raise IdentityError("protocol suites must be a non-empty ordered array")
    suite_roles: set[str] = set()
    task_sources: dict[str, str] = {}
    suites_by_role: dict[str, dict[str, Any]] = {}
    for index, raw_suite in enumerate(suites):
        suite = _require_fields(
            raw_suite, SUITE_FIELDS, field_name=f"protocol suites[{index}]"
        )
        role = _string(suite["role"], field_name=f"protocol suites[{index}].role")
        if role in suite_roles:
            raise IdentityError(f"protocol suites duplicates role {role!r}")
        suite_roles.add(role)
        suites_by_role[role] = suite
        _string(suite["name"], field_name=f"protocol suites[{index}].name")
        _string(suite["id"], field_name=f"protocol suites[{index}].id")
        _digest(
            suite["manifest_digest"],
            field_name=f"protocol suites[{index}].manifest_digest",
        )
        tasks = suite["tasks"]
        if type(tasks) is not list or not tasks:
            raise IdentityError(f"protocol suites[{index}].tasks must be non-empty")
        seen: set[str] = set()
        for task_index, raw_task in enumerate(tasks):
            task = _require_fields(
                raw_task,
                TASK_BINDING_FIELDS,
                field_name=f"protocol suites[{index}].tasks[{task_index}]",
            )
            task_id = _string(task["id"], field_name="protocol task id")
            source = _string(task["source"], field_name="protocol task source")
            _digest(task["record_digest"], field_name="protocol task record_digest")
            if task_id in seen:
                raise IdentityError(
                    f"protocol suite {role!r} duplicates task {task_id!r}"
                )
            seen.add(task_id)
            prior = task_sources.setdefault(task_id, source)
            if prior != source:
                raise IdentityError(
                    f"protocol task {task_id!r} changes source across suites"
                )

    runtimes = snapshot["source_runtimes"]
    if type(runtimes) is not dict or not runtimes:
        raise IdentityError("protocol source_runtimes must be a non-empty object")
    for source, raw_runtime in runtimes.items():
        _string(source, field_name="source_runtimes key")
        runtime = _require_fields(
            raw_runtime,
            SOURCE_RUNTIME_FIELDS,
            field_name=f"source_runtimes.{source}",
        )
        _production_string(
            runtime["source_revision"],
            field_name=f"source_runtimes.{source}.source_revision",
            mode=mode,
        )
        for name in ("setup", "reset", "environment", "browser"):
            _validate_component_identity(
                runtime[name],
                field_name=f"source_runtimes.{source}.{name}",
                mode=mode,
            )
    missing_sources = sorted(set(task_sources.values()) - set(runtimes))
    if missing_sources:
        raise IdentityError(
            "protocol source_runtimes missing scheduled source(s): "
            + ", ".join(missing_sources)
        )

    repeated, seeds, arm_order, _repeat_count = validate_repeated_protocol(
        snapshot["repeated_protocol"], runtimes=runtimes, mode=mode
    )
    schedule_role = "dev" if "dev" in suites_by_role else suites[0]["role"]
    expected_blocks = _expected_matched_blocks(
        suites_by_role[schedule_role]["tasks"], runtimes, seeds, arm_order
    )
    blocks = snapshot["matched_blocks"]
    if type(blocks) is not list:
        raise IdentityError("protocol matched_blocks must be an ordered array")
    for index, raw_block in enumerate(blocks):
        block = _require_fields(
            raw_block, BLOCK_FIELDS, field_name=f"matched_blocks[{index}]"
        )
        _string(block["id"], field_name=f"matched_blocks[{index}].id")
        _string(block["task_id"], field_name=f"matched_blocks[{index}].task_id")
        _string(block["source"], field_name=f"matched_blocks[{index}].source")
        _int(block["seed"], field_name=f"matched_blocks[{index}].seed")
        for name in ("reset_digest", "environment_digest", "browser_digest"):
            _digest(block[name], field_name=f"matched_blocks[{index}].{name}")
        if block["arm_order"] != arm_order:
            raise IdentityError(
                f"matched_blocks[{index}].arm_order differs from repeated protocol"
            )
    if canonical_json(blocks) != canonical_json(expected_blocks):
        raise IdentityError(
            "protocol matched_blocks must exactly cover ordered dev task/seed blocks"
        )

    evaluator = _require_fields(
        snapshot["evaluator"], EVALUATOR_FIELDS, field_name="evaluator"
    )
    components = evaluator["components"]
    if type(components) is not list or not components:
        raise IdentityError("evaluator.components must be a non-empty ordered array")
    packages: set[str] = set()
    for index, raw_component in enumerate(components):
        component = _require_fields(
            raw_component,
            CODE_COMPONENT_FIELDS,
            field_name=f"evaluator.components[{index}]",
        )
        package = _production_string(
            component["package"],
            field_name=f"evaluator.components[{index}].package",
            mode=mode,
        )
        if package in packages:
            raise IdentityError(f"evaluator.components duplicates {package!r}")
        packages.add(package)
        _production_string(
            component["version"],
            field_name=f"evaluator.components[{index}].version",
            mode=mode,
        )
        _digest(
            component["code_digest"],
            field_name=f"evaluator.components[{index}].code_digest",
        )
    if snapshot["purpose"] in {"iteration", "noise-calibration"} and packages != {
        "opti_eval",
        "opti_loop",
        "opti_judge",
    }:
        raise IdentityError(
            "loop protocols must bind opti_eval, opti_loop, and opti_judge code"
        )
    _digest(evaluator["apparatus_digest"], field_name="evaluator.apparatus_digest")
    if evaluator["apparatus_digest"] != digest_json(
        components, domain="opti.trusted-code-apparatus.v1"
    ):
        raise IdentityError("evaluator.apparatus_digest does not match components")

    verifier = _require_fields(
        snapshot["verifier_bundle"], VERIFIER_FIELDS, field_name="verifier_bundle"
    )
    _production_string(verifier["id"], field_name="verifier_bundle.id", mode=mode)
    _production_string(
        verifier["checksum"], field_name="verifier_bundle.checksum", mode=mode
    )
    _digest(verifier["bundle_digest"], field_name="verifier_bundle.bundle_digest")
    _digest(
        verifier["admissions_digest"], field_name="verifier_bundle.admissions_digest"
    )

    adapter = _require_fields(snapshot["adapter"], ADAPTER_FIELDS, field_name="adapter")
    _production_string(adapter["name"], field_name="adapter.name", mode=mode)
    if type(adapter["benchmark_reportable"]) is not bool:
        raise IdentityError("adapter.benchmark_reportable must be a boolean")
    if type(adapter["configuration"]) is not dict:
        raise IdentityError("adapter.configuration must be an object")
    _digest(adapter["digest"], field_name="adapter.digest")
    if adapter["digest"] != digest_json(
        {key: adapter[key] for key in ("name", "benchmark_reportable", "configuration")},
        domain="opti.adapter.v1",
    ):
        raise IdentityError("adapter.digest does not match frozen adapter identity")
    if mode == "benchmark" and adapter["benchmark_reportable"] is not True:
        raise IdentityError("benchmark protocol requires a reportable live adapter")

    executor = _require_fields(
        snapshot["executor"], EXECUTOR_FIELDS, field_name="executor"
    )
    for name in ("provider", "route", "model", "snapshot", "revision"):
        _production_string(
            executor[name], field_name=f"executor.{name}", mode=mode
        )
    if type(executor["settings"]) is not dict:
        raise IdentityError("executor.settings must be an object")
    if digest_json(
        executor["settings"], domain="opti.executor-settings.v1"
    ) != executor["settings_digest"]:
        raise IdentityError("executor.settings_digest does not match settings")
    _digest(executor["tool_schema_digest"], field_name="executor.tool_schema_digest")

    instrumentation = _require_fields(
        snapshot["activation_instrumentation"],
        INSTRUMENTATION_FIELDS,
        field_name="activation_instrumentation",
    )
    _production_string(
        instrumentation["id"], field_name="activation_instrumentation.id", mode=mode
    )
    _production_string(
        instrumentation["revision"],
        field_name="activation_instrumentation.revision",
        mode=mode,
    )
    _digest(
        instrumentation["digest"], field_name="activation_instrumentation.digest"
    )
    lane = _require_fields(snapshot["lane"], LANE_FIELDS, field_name="lane")
    _production_string(lane["id"], field_name="lane.id", mode=mode)
    _string(lane["config_path"], field_name="lane.config_path")
    _digest(lane["config_digest"], field_name="lane.config_digest")

    validate_candidate_allowlist(snapshot["candidate_allowlist"])

    accepted_build = validate_build_identity(
        snapshot["accepted_build"], evidence_mode=mode
    )
    if accepted_build["role"] != "accepted":
        raise IdentityError("protocol accepted_build role must be accepted")

    execution = _require_fields(
        snapshot["execution"], EXECUTION_FIELDS, field_name="execution"
    )
    for name in (
        "adapter",
        "suites",
        "thresholds",
        "fixed_variables",
        "transfer",
        "exploration",
        "accepted_protection",
    ):
        if type(execution[name]) is not dict:
            raise IdentityError(f"execution.{name} must be an object")
    protection = _require_fields(
        execution["accepted_protection"],
        {"champion_sha", "protected_tasks", "success_rates"},
        field_name="execution.accepted_protection",
    )
    reference = _production_string(
        protection["champion_sha"],
        field_name="execution.accepted_protection.champion_sha",
        mode=mode,
    )
    if mode == "benchmark" and not _GIT_OBJECT.fullmatch(reference):
        raise IdentityError("execution.accepted_protection.champion_sha is not a git object")
    protected_tasks = protection["protected_tasks"]
    success_rates = protection["success_rates"]
    if (
        type(protected_tasks) is not list
        or protected_tasks != sorted(set(protected_tasks))
        or any(type(task_id) is not str or not task_id for task_id in protected_tasks)
        or type(success_rates) is not dict
        or set(success_rates) != set(protected_tasks)
    ):
        raise IdentityError("execution.accepted_protection task evidence is malformed")
    for task_id, rate in success_rates.items():
        value = _number(rate, field_name=f"execution.accepted_protection.success_rates.{task_id}")
        if not 0 <= value <= 1:
            raise IdentityError("execution.accepted_protection success rate must be in [0, 1]")
    if protection["champion_sha"] != accepted_build["commit_sha"]:
        raise IdentityError(
            "execution.accepted_protection.champion_sha differs from accepted build"
        )
    if execution["noise_band"] is not None and type(execution["noise_band"]) is not dict:
        raise IdentityError("execution.noise_band must be an object or null")

    _digest(snapshot["calibration_binding_digest"], field_name="calibration_binding_digest")
    _digest(
        snapshot["comparison_apparatus_digest"],
        field_name="comparison_apparatus_digest",
    )
    _digest(snapshot["protocol_digest"], field_name="protocol_digest")
    if snapshot["calibration_binding_digest"] != calibration_binding_digest(snapshot):
        raise IdentityError(
            "calibration_binding_digest does not match frozen calibration inputs"
        )
    if snapshot["comparison_apparatus_digest"] != comparison_apparatus_digest(
        snapshot
    ):
        raise IdentityError(
            "comparison_apparatus_digest does not match frozen comparison apparatus"
        )
    if snapshot["protocol_digest"] != protocol_digest(snapshot):
        raise IdentityError(
            "protocol_digest does not match the frozen protocol snapshot"
        )
    return snapshot


def finalize_protocol_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    snapshot = copy.deepcopy(payload)
    snapshot["calibration_binding_digest"] = calibration_binding_digest(snapshot)
    snapshot["comparison_apparatus_digest"] = comparison_apparatus_digest(snapshot)
    snapshot["protocol_digest"] = protocol_digest(snapshot)
    validate_protocol_snapshot(snapshot)
    return snapshot


def _suite_for_role(protocol: dict[str, Any], role: str) -> dict[str, Any]:
    matches = [suite for suite in protocol["suites"] if suite["role"] == role]
    if len(matches) != 1:
        raise IdentityError(f"run context suite_role {role!r} is not frozen")
    return matches[0]


def make_run_context(
    protocol_snapshot: dict[str, Any],
    build: dict[str, Any],
    *,
    arm: str,
    suite_role: str,
    task_ids: list[str],
    repeat_index: int,
    seed: int,
    run_id: str | None = None,
) -> dict[str, Any]:
    protocol = validate_protocol_snapshot(protocol_snapshot)
    context: dict[str, Any] = {
        "schema_version": RUN_CONTEXT_SCHEMA_VERSION,
        "run_id": run_id or f"run-{uuid.uuid4().hex}",
        "evidence_mode": protocol["evidence_mode"],
        "arm": arm,
        "suite_role": suite_role,
        "task_ids": copy.deepcopy(task_ids),
        "repeat_index": repeat_index,
        "seed": seed,
        "protocol_digest": protocol["protocol_digest"],
        "build": copy.deepcopy(build),
    }
    context["run_digest"] = digest_json(context, domain="opti.run-context.v2")
    validate_run_context(context, protocol_snapshot=protocol)
    return context


def validate_run_context(
    value: object, *, protocol_snapshot: dict[str, Any]
) -> dict[str, Any]:
    protocol = validate_protocol_snapshot(protocol_snapshot)
    context = _require_fields(value, RUN_CONTEXT_FIELDS, field_name="run context")
    try:
        validate_standard_json(context, field_name="run context")
    except ValueError as exc:
        raise IdentityError(str(exc)) from exc
    if context["schema_version"] != RUN_CONTEXT_SCHEMA_VERSION:
        raise IdentityError(
            f"unsupported run context schema_version {context['schema_version']!r}"
        )
    _string(context["run_id"], field_name="run context run_id")
    mode = _string(context["evidence_mode"], field_name="run context evidence_mode")
    if mode != protocol["evidence_mode"]:
        raise IdentityError("run context evidence_mode does not match protocol")
    arm = _string(context["arm"], field_name="run context arm")
    if arm not in ARMS:
        raise IdentityError(f"run context arm must be one of {sorted(ARMS)}")
    role = _string(context["suite_role"], field_name="run context suite_role")
    suite = _suite_for_role(protocol, role)
    task_ids = context["task_ids"]
    if (
        type(task_ids) is not list
        or not task_ids
        or any(type(task_id) is not str or not task_id for task_id in task_ids)
        or len(set(task_ids)) != len(task_ids)
    ):
        raise IdentityError(
            "run context task_ids must be unique non-empty strings in frozen order"
        )
    frozen_ids = [task["id"] for task in suite["tasks"]]
    expected_order = [task_id for task_id in frozen_ids if task_id in set(task_ids)]
    if task_ids != expected_order:
        raise IdentityError(
            "run context task_ids are outside or out of order for frozen suite_role"
        )
    repeat_index = _int(
        context["repeat_index"], field_name="run context repeat_index"
    )
    repeat_count = protocol["repeated_protocol"]["repeats"]["count"]
    if repeat_index >= repeat_count:
        raise IdentityError("run context repeat_index exceeds frozen repeat count")
    seed = _int(context["seed"], field_name="run context seed")
    if seed not in protocol["repeated_protocol"]["matched_blocks"]["seeds"]:
        raise IdentityError("run context seed is not declared by the frozen protocol")
    _digest(context["protocol_digest"], field_name="run context protocol_digest")
    if context["protocol_digest"] != protocol["protocol_digest"]:
        raise IdentityError("run context protocol_digest does not match protocol")

    build = validate_build_identity(context["build"], evidence_mode=mode)
    accepted = protocol["accepted_build"]
    if arm == "baseline":
        if build["role"] != "accepted" or canonical_json(build) != canonical_json(
            accepted
        ):
            raise IdentityError(
                "baseline run context build does not match accepted protocol build"
            )
    elif arm == "treatment":
        if build["role"] != "candidate":
            raise IdentityError("treatment run context requires a candidate build")
        if build["materialized_digest"] == accepted["materialized_digest"]:
            raise IdentityError(
                "treatment run context candidate materialization is identical to accepted build"
            )
    else:
        if mode != "simulated":
            raise IdentityError("diagnostic runs cannot become benchmark evidence")
        if build["role"] != "diagnostic":
            raise IdentityError("diagnostic run context requires a diagnostic build")

    schedule_role = "dev" if any(
        suite_row["role"] == "dev" for suite_row in protocol["suites"]
    ) else protocol["suites"][0]["role"]
    if role == schedule_role:
        blocks = {
            (block["task_id"], block["seed"]): block
            for block in protocol["matched_blocks"]
        }
        expected_arm_order = protocol["repeated_protocol"]["matched_blocks"][
            "arm_order"
        ]
        for task_id in task_ids:
            block = blocks.get((task_id, seed))
            if block is None or block["arm_order"] != expected_arm_order:
                raise IdentityError(
                    f"run context task/seed block {task_id}/{seed} is not frozen"
                )

    _digest(context["run_digest"], field_name="run context run_digest")
    expected_run_digest = digest_json(
        {key: item for key, item in context.items() if key != "run_digest"},
        domain="opti.run-context.v2",
    )
    if context["run_digest"] != expected_run_digest:
        raise IdentityError("run context run_digest does not match its closed fields")
    return context


def validate_paired_contexts(
    baseline: object,
    treatment: object,
    *,
    protocol_snapshot: dict[str, Any],
) -> None:
    left = validate_run_context(baseline, protocol_snapshot=protocol_snapshot)
    right = validate_run_context(treatment, protocol_snapshot=protocol_snapshot)
    if left["arm"] != "baseline" or right["arm"] != "treatment":
        raise IdentityError("paired contexts must be baseline and treatment")
    for name in (
        "evidence_mode",
        "suite_role",
        "task_ids",
        "repeat_index",
        "seed",
        "protocol_digest",
    ):
        if left[name] != right[name]:
            raise IdentityError(f"paired run contexts differ in {name}")
    if left["run_id"] == right["run_id"] or left["run_digest"] == right["run_digest"]:
        raise IdentityError("paired run contexts must have unique run identities")


@dataclass(frozen=True, slots=True)
class LiveRunReceipt:
    """Trusted in-memory expectation required for reportable artifact loading."""

    protocol_digest: str
    run_digest: str
    adapter_digest: str
    evidence_mode: str

    def __post_init__(self) -> None:
        _digest(self.protocol_digest, field_name="receipt protocol_digest")
        _digest(self.run_digest, field_name="receipt run_digest")
        _digest(self.adapter_digest, field_name="receipt adapter_digest")
        if self.evidence_mode not in EVIDENCE_MODES:
            raise IdentityError("receipt evidence_mode must be simulated or benchmark")


def expected_live_run_receipt(
    protocol_snapshot: dict[str, Any], *, run_digest: str
) -> LiveRunReceipt:
    protocol = validate_protocol_snapshot(protocol_snapshot)
    return LiveRunReceipt(
        protocol_digest=protocol["protocol_digest"],
        run_digest=run_digest,
        adapter_digest=protocol["adapter"]["digest"],
        evidence_mode=protocol["evidence_mode"],
    )


def make_live_run_receipt(
    protocol_snapshot: dict[str, Any],
    run_context: dict[str, Any],
    *,
    actual_adapter_identity: dict[str, Any],
) -> LiveRunReceipt:
    protocol = validate_protocol_snapshot(protocol_snapshot)
    context = validate_run_context(run_context, protocol_snapshot=protocol)
    actual = _require_fields(
        actual_adapter_identity, ADAPTER_FIELDS, field_name="actual adapter identity"
    )
    if canonical_json(actual) != canonical_json(protocol["adapter"]):
        raise IdentityError("live adapter identity does not match the frozen protocol")
    return expected_live_run_receipt(protocol, run_digest=context["run_digest"])


def _simulated_digest(label: str) -> str:
    return digest_json(label, domain="opti.simulated-identity.v2")


def _simulated_component(source: str, name: str) -> dict[str, str]:
    return {
        "id": f"simulated:{source}:{name}",
        "revision": "simulated:v1",
        "digest": _simulated_digest(f"{source}:{name}"),
    }


def simulated_identity_defaults(
    sources: list[str], *, repeat_count: int = 1
) -> dict[str, Any]:
    """Single authority for direct and conductor simulation identities."""
    ordered_sources = sorted(set(sources))
    if not ordered_sources:
        raise IdentityError("simulated identity requires at least one source")
    repeated = {
        "matched_blocks": {
            "seeds": [0],
            "arm_order": ["baseline", "treatment"],
            "interleaving": SUPPORTED_REPEATED_RULES["interleaving"],
            "reset_scope": SUPPORTED_REPEATED_RULES["reset_scope"],
        },
        "coverage": {
            "minimum_fraction": 1.0,
            "quorum_fraction": 1.0,
            "required_sources": ordered_sources,
            "denominator": "frozen_task_seed_blocks",
        },
        "repeats": {"count": repeat_count},
        "stopping": {
            "rule": SUPPORTED_REPEATED_RULES["stopping"],
            "valid_after": repeat_count,
            "optional_stopping": False,
        },
        "outcome_handling": copy.deepcopy(SUPPORTED_OUTCOME_HANDLING),
        "effect": {
            "estimator": SUPPORTED_REPEATED_RULES["estimator"],
            "uncertainty": SUPPORTED_REPEATED_RULES["uncertainty"],
            "minimum_effect": 0.0,
        },
        "non_inferiority": {
            "rule": SUPPORTED_REPEATED_RULES["non_inferiority"],
            "margin": 0.0,
        },
        "regression": {
            "rule": SUPPORTED_REPEATED_RULES["regression"],
            "max_regressions": 0,
        },
        "champion": {
            "rule": SUPPORTED_REPEATED_RULES["champion"],
            "margin": 0.0,
        },
        "transfer": {
            "rule": SUPPORTED_REPEATED_RULES["transfer_rule"],
            "schedule": SUPPORTED_REPEATED_RULES["transfer_schedule"],
        },
        "multiplicity": {
            "rule": SUPPORTED_REPEATED_RULES["multiplicity_rule"],
            "family": SUPPORTED_REPEATED_RULES["multiplicity_family"],
        },
        "limits": {
            "max_runs": repeat_count * 2,
            "deadline_seconds": 3600,
            "exhaustion_outcome": "inconclusive",
        },
        "calibration": {
            "id": "simulated:not-calibrated",
            "digest": _simulated_digest("calibration"),
        },
    }
    return {
        "source_runtimes": {
            source: {
                "source_revision": f"simulated:{source}:v1",
                "setup": _simulated_component(source, "setup"),
                "reset": _simulated_component(source, "reset"),
                "environment": _simulated_component(source, "environment"),
                "browser": _simulated_component(source, "browser"),
            }
            for source in ordered_sources
        },
        "executor": {
            "provider": "simulated:local",
            "route": "simulated:fixture",
            "model": "simulated:fixture",
            "snapshot": "simulated:v1",
            "revision": "simulated:v1",
            "settings": {},
            "tool_schema_digest": _simulated_digest("tool-schema"),
        },
        "verifier_bundle": {
            "id": "simulated:not-admitted",
            "checksum": "simulated:not-admitted",
            "bundle_digest": _simulated_digest("verifier-bundle"),
            "admissions_digest": _simulated_digest("admissions"),
        },
        "activation_instrumentation": {
            "id": "simulated:not-active",
            "revision": "simulated:v1",
            "digest": _simulated_digest("activation-instrumentation"),
        },
        "repeated_protocol": repeated,
    }


def simulated_protocol(
    *, suite: dict[str, Any], tasks: list[dict[str, Any]], adapter: dict[str, Any]
) -> dict[str, Any]:
    """Build a self-contained explicit non-reportable direct-run protocol."""
    task_rows = [
        {
            "id": _string(task.get("id"), field_name="simulated task id"),
            "source": _string(task.get("source"), field_name="simulated task source"),
            "record_digest": digest_json(task, domain="opti.task-record.v1"),
        }
        for task in tasks
    ]
    sources = sorted({row["source"] for row in task_rows})
    defaults = simulated_identity_defaults(sources)
    executor = copy.deepcopy(defaults["executor"])
    executor["settings_digest"] = digest_json(
        executor["settings"], domain="opti.executor-settings.v1"
    )
    accepted_build = {
        "role": "accepted",
        "commit_sha": "simulated:direct-eval",
        "tree_sha": "simulated:direct-eval",
        "materialized_digest": digest_json("direct-eval", domain="opti.build.v1"),
        "immutable": False,
    }
    component = code_component_identity(
        package="opti_eval",
        version="0.1.0",
        package_root=Path(__file__).resolve().parent,
    )
    evaluator = {
        "components": [component],
        "apparatus_digest": digest_json(
            [component], domain="opti.trusted-code-apparatus.v1"
        ),
    }
    suite_row = {
        "role": "direct",
        "name": str(suite.get("id") or "direct"),
        "id": str(suite.get("id") or "direct"),
        "manifest_digest": digest_json(suite, domain="opti.suite-manifest.v1"),
        "tasks": task_rows,
    }
    payload = {
        "schema_version": PROTOCOL_SCHEMA_VERSION,
        "campaign_id": "simulated:direct-eval",
        "iteration": 0,
        "purpose": "direct-evaluation",
        "evidence_mode": "simulated",
        "suites": [suite_row],
        "matched_blocks": _expected_matched_blocks(
            task_rows,
            defaults["source_runtimes"],
            defaults["repeated_protocol"]["matched_blocks"]["seeds"],
            defaults["repeated_protocol"]["matched_blocks"]["arm_order"],
        ),
        "source_runtimes": defaults["source_runtimes"],
        "evaluator": evaluator,
        "verifier_bundle": defaults["verifier_bundle"],
        "adapter": normalize_adapter_identity(adapter),
        "executor": executor,
        "activation_instrumentation": defaults["activation_instrumentation"],
        "lane": {
            "id": "simulated:direct",
            "config_path": "simulated:direct",
            "config_digest": _simulated_digest("lane-direct"),
        },
        "candidate_allowlist": ["harness/direct/"],
        "accepted_build": accepted_build,
        "repeated_protocol": defaults["repeated_protocol"],
        "execution": {
            "adapter": copy.deepcopy(adapter),
            "suites": {"direct": str(suite.get("id") or "direct")},
            "thresholds": {},
            "noise_band": None,
            "fixed_variables": {"evidence_mode": "simulated"},
            "transfer": {},
            "exploration": {},
            "accepted_protection": {
                "champion_sha": accepted_build["commit_sha"],
                "protected_tasks": [],
                "success_rates": {},
            },
        },
    }
    return finalize_protocol_snapshot(payload)


def simulated_run_identity(
    *,
    suite: dict[str, Any],
    tasks: list[dict[str, Any]],
    adapter: dict[str, Any],
    run_id: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    protocol = simulated_protocol(suite=suite, tasks=tasks, adapter=adapter)
    diagnostic_build = {
        **protocol["accepted_build"],
        "role": "diagnostic",
    }
    context = make_run_context(
        protocol,
        diagnostic_build,
        arm="diagnostic",
        suite_role="direct",
        task_ids=[task["id"] for task in tasks],
        repeat_index=0,
        seed=0,
        run_id=run_id,
    )
    return protocol, context
