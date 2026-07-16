"""Run the evaluation plane (opti-eval) and read back per-task outcomes.

The loop consumes opti-eval strictly as a read-only instrument: it selects
tasks, runs an adapter, and parses the artifacts opti-eval wrote. It never
modifies catalogs, suites, or verifier assets (ADR-0015 plane boundaries).

Result semantics are opti-eval's fail-closed vocabulary:
``passed | failed | invalid | error | skipped`` — invalid/error/skipped are
infrastructure signals, never agent failures.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any

from opti_eval.adapters.command import CommandAdapter
from opti_eval.adapters.fixture import FixtureAdapter
from opti_eval.catalog import select_tasks
from opti_eval.identity import LiveRunReceipt, digest_json
from opti_eval.models import validate_nonempty_string
from opti_eval.runner import run_evaluation
from opti_eval.summary import load_run_artifacts, validate_run_directory

from . import gitutil

@dataclass(frozen=True, slots=True)
class AdmissionReceipt:
    """Conductor-issued proof that one exact benchmark run passed AR-003."""

    schema_version: str
    protocol_digest: str
    run_digest: str
    adapter_digest: str
    run_id: str
    task_bundle_digest: str
    t1_flag_count: int
    receipt_digest: str

    @classmethod
    def from_dict(cls, payload: object) -> "AdmissionReceipt":
        fields = {
            "schema_version",
            "protocol_digest",
            "run_digest",
            "adapter_digest",
            "run_id",
            "task_bundle_digest",
            "t1_flag_count",
            "receipt_digest",
        }
        if type(payload) is not dict or set(payload) != fields:
            raise ValueError("AR-003 admission receipt fields are not closed")
        if payload["schema_version"] != "0.1.0":
            raise ValueError("AR-003 admission receipt schema_version is invalid")
        for name in (
            "protocol_digest",
            "run_digest",
            "adapter_digest",
            "task_bundle_digest",
            "receipt_digest",
        ):
            value = payload[name]
            if (
                type(value) is not str
                or len(value) != 64
                or any(char not in "0123456789abcdef" for char in value)
            ):
                raise ValueError(f"AR-003 admission receipt {name} is invalid")
        run_id = validate_nonempty_string(
            payload["run_id"], field_name="AR-003 admission receipt run_id"
        )
        flag_count = payload["t1_flag_count"]
        if type(flag_count) is not int or flag_count < 0:
            raise ValueError(
                "AR-003 admission receipt t1_flag_count must be an integer >= 0"
            )
        unsigned = {key: payload[key] for key in fields if key != "receipt_digest"}
        expected_digest = digest_json(
            unsigned, domain="opti.ar003-admission-receipt.v1"
        )
        if payload["receipt_digest"] != expected_digest:
            raise ValueError("AR-003 admission receipt digest is invalid")
        return cls(
            schema_version="0.1.0",
            protocol_digest=payload["protocol_digest"],
            run_digest=payload["run_digest"],
            adapter_digest=payload["adapter_digest"],
            run_id=run_id,
            task_bundle_digest=payload["task_bundle_digest"],
            t1_flag_count=flag_count,
            receipt_digest=payload["receipt_digest"],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "protocol_digest": self.protocol_digest,
            "run_digest": self.run_digest,
            "adapter_digest": self.adapter_digest,
            "run_id": self.run_id,
            "task_bundle_digest": self.task_bundle_digest,
            "t1_flag_count": self.t1_flag_count,
            "receipt_digest": self.receipt_digest,
        }


@dataclass(slots=True)
class EvalRun:
    """Parsed view of one opti-eval run directory."""

    output_dir: Path
    suite_name: str
    summary: dict[str, Any]
    statuses: dict[str, str]  # task_id -> status
    rewards: dict[str, float | None]
    run_id: str = ""
    results: dict[str, dict[str, Any]] = field(default_factory=dict)
    live_receipt: LiveRunReceipt | None = None
    task_ids: list[str] = field(default_factory=list)
    task_sources: dict[str, str] = field(default_factory=dict)
    protocol_digest: str = ""
    run_context_digest: str = ""
    run_context: dict[str, Any] = field(default_factory=dict)
    protocol_snapshot: dict[str, Any] = field(default_factory=dict)
    task_records: dict[str, dict[str, Any]] = field(default_factory=dict)
    admission_receipt: dict[str, Any] | None = None
    activation_observation: dict[str, Any] | None = None

    @property
    def run_valid(self) -> bool:
        return bool(self.summary.get("run_valid"))

    @property
    def acceptance_decision_eligible(self) -> bool:
        return self.benchmark_admitted

    @property
    def benchmark_admitted(self) -> bool:
        receipt = self.admission_receipt
        live = self.live_receipt
        expected_fields = {
            "schema_version",
            "protocol_digest",
            "run_digest",
            "adapter_digest",
            "run_id",
            "task_bundle_digest",
            "t1_flag_count",
            "receipt_digest",
        }
        if (
            live is None
            or live.evidence_mode != "benchmark"
            or not isinstance(receipt, dict)
            or set(receipt) != expected_fields
            or receipt.get("schema_version") != "0.1.0"
            or receipt.get("protocol_digest") != live.protocol_digest
            or receipt.get("run_digest") != live.run_digest
            or receipt.get("adapter_digest") != live.adapter_digest
            or receipt.get("run_id") != self.run_id
            or type(receipt.get("t1_flag_count")) is not int
        ):
            return False
        payload = {
            key: value for key, value in receipt.items() if key != "receipt_digest"
        }
        try:
            return receipt["receipt_digest"] == digest_json(
                payload, domain="opti.ar003-admission-receipt.v1"
            )
        except (TypeError, ValueError):
            return False

    @property
    def benchmark_live(self) -> bool:
        return self.benchmark_admitted

    @property
    def passed_ids(self) -> set[str]:
        return {tid for tid, status in self.statuses.items() if status == "passed"}

    @property
    def valid_ids(self) -> set[str]:
        return {
            tid
            for tid, status in self.statuses.items()
            if status in {"passed", "failed"}
        }


class HarnessFixtureAdapter(FixtureAdapter):
    """Synthetic candidate behavior with a stable adapter execution identity."""

    name = "harness-fixture"

    def __init__(
        self,
        *,
        pass_rate: float,
        default_pass_rate: float,
        seed: int,
        file: str | None,
        activation_observation: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(pass_rate=pass_rate, seed=seed)
        self.default_pass_rate = default_pass_rate
        self.file = file
        self.activation_observation = activation_observation

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "benchmark_reportable": False,
            "default_pass_rate": self.default_pass_rate,
            "seed": self.seed,
            "file": self.file,
        }


def build_adapter(adapter_config: dict[str, Any], *, repo_root: Path | None = None):
    kind = adapter_config.get("kind", "fixture")
    if kind == "fixture":
        return FixtureAdapter(
            pass_rate=float(adapter_config.get("pass_rate", 0.55)),
            seed=int(adapter_config.get("seed", 0)),
        )
    if kind == "harness-fixture":
        # Dry-run simulator: the fixture pass rate is read from a file inside
        # the optimizer's writable surface, so a component edit deterministically
        # changes outcomes. Results remain synthetic and non-reportable
        # (inherits FixtureAdapter semantics); verdicts computed over them are
        # watermarked `simulated:` by the gate. Plumbing rehearsal only.
        default_rate = float(adapter_config.get("default_pass_rate", 0.55))
        rate = default_rate
        rel = adapter_config.get("file")
        observation = None
        if type(rel) is str and rel and repo_root is not None:
            posix = PurePosixPath(rel)
            if (
                not posix.is_absolute()
                and posix.as_posix() == rel
                and all(part not in {"", ".", ".."} for part in posix.parts)
            ):
                path = repo_root.joinpath(*posix.parts)
                try:
                    raw = path.read_bytes()
                    parsed = float(raw.decode("utf-8").strip())
                except (OSError, UnicodeDecodeError, ValueError):
                    pass
                else:
                    rate = parsed
                    observation = {
                        "path": rel,
                        "sha256": hashlib.sha256(raw).hexdigest(),
                        "parsed_value": parsed,
                    }
        return HarnessFixtureAdapter(
            pass_rate=rate,
            default_pass_rate=default_rate,
            seed=int(adapter_config.get("seed", 0)),
            file=(str(rel) if rel else None),
            activation_observation=observation,
        )
    if kind == "command":
        return CommandAdapter(
            adapter_config["command"],
            timeout_seconds=int(adapter_config.get("timeout_seconds", 1800)),
        )
    raise ValueError(
        f"unsupported adapter kind {kind!r} (registry adapters arrive with the source bridges)"
    )


def run_suite(
    *,
    repo_root: Path,
    suite_name: str,
    adapter_config: dict[str, Any],
    output_dir: Path,
    task_ids: list[str] | None = None,
    max_workers: int = 4,
    protocol_snapshot: dict[str, Any] | None = None,
    run_context: dict[str, Any] | None = None,
) -> EvalRun:
    suite, tasks = select_tasks(repo_root, suite_name, task_ids=task_ids)
    adapter = build_adapter(adapter_config, repo_root=repo_root)
    verifier_binding: dict[str, str] | None = None
    verifier_id = adapter_config.get("verifier_id")
    verifier_checksum = adapter_config.get("verifier_checksum")
    if verifier_id is not None or verifier_checksum is not None:
        verifier_binding = {
            "id": validate_nonempty_string(
                verifier_id, field_name="adapter verifier_id"
            ),
            "checksum": validate_nonempty_string(
                verifier_checksum, field_name="adapter verifier_checksum"
            ),
        }
    execution = run_evaluation(
        repo_root=repo_root,
        suite=suite,
        tasks=tasks,
        adapter=adapter,
        output_dir=output_dir,
        max_workers=max_workers,
        overwrite=False,
        verifier_binding=verifier_binding,
        protocol_snapshot=protocol_snapshot,
        run_context=run_context,
    )
    run = _parse_run(output_dir, suite_name, expected_receipt=execution.receipt)
    observation = getattr(adapter, "activation_observation", None)
    if isinstance(observation, dict):
        run.activation_observation = {
            **observation,
            "run_artifact": {
                "path": "run.json",
                "sha256": hashlib.sha256((output_dir / "run.json").read_bytes()).hexdigest(),
            },
        }
    return run


def validate_harness_fixture_activation(
    run: EvalRun,
    *,
    baseline_run: EvalRun,
    trusted_repo: Path,
    base_sha: str,
    candidate_root: Path,
    candidate_build: dict[str, Any],
    candidate_allowlist: list[str],
    changed_files: list[str],
    configured_path: object,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Validate the one conductor-observed activation path implemented for D3."""
    errors: list[str] = []
    if not candidate_build.get("immutable") or run.run_context.get("build") != candidate_build:
        errors.append("treatment run context has the wrong immutable candidate build")
    if run.protocol_snapshot.get("candidate_allowlist") != candidate_allowlist:
        errors.append("treatment run has the wrong frozen candidate allowlist")
    if type(configured_path) is not str or configured_path not in changed_files:
        errors.append("configured candidate behavior file was not changed by the treatment")
    if type(configured_path) is str and not any(
        configured_path.startswith(prefix) for prefix in candidate_allowlist
    ):
        errors.append("configured candidate behavior file is outside the frozen allowlist")
    observation = run.activation_observation
    if type(observation) is not dict:
        errors.append("configured candidate behavior file was not consumed")
    else:
        if observation.get("path") != configured_path:
            errors.append("activation consumed the wrong candidate behavior path")
        checksum = observation.get("sha256")
        if type(checksum) is not str or len(checksum) != 64:
            errors.append("activation lacks the consumed candidate behavior digest")
        elif type(configured_path) is str:
            try:
                actual_checksum = hashlib.sha256(
                    candidate_root.joinpath(*PurePosixPath(configured_path).parts).read_bytes()
                ).hexdigest()
            except OSError:
                actual_checksum = None
            if checksum != actual_checksum:
                errors.append("activation consumed the wrong candidate behavior digest")
        consumed_value = observation.get("parsed_value")
        if any(
            result.get("metrics", {}).get("fixture_pass_rate") != consumed_value
            for result in run.results.values()
        ):
            errors.append("observed candidate behavior did not affect fixture execution")
    baseline = baseline_run.activation_observation
    if type(baseline) is not dict:
        errors.append("trusted accepted-build baseline observation is missing")
    else:
        if baseline.get("path") != configured_path:
            errors.append("baseline observed the wrong candidate behavior path")
        try:
            baseline_digest = hashlib.sha256(
                gitutil.read_blob(trusted_repo, base_sha, configured_path)
            ).hexdigest()
        except (OSError, gitutil.GitError, TypeError):
            baseline_digest = None
        if baseline.get("sha256") != baseline_digest:
            errors.append("baseline observation does not match the trusted accepted build")
        if any(
            result.get("metrics", {}).get("fixture_pass_rate")
            != baseline.get("parsed_value")
            for result in baseline_run.results.values()
        ):
            errors.append("baseline observation did not affect trusted baseline execution")
        baseline_artifact = baseline.get("run_artifact")
        if not isinstance(baseline_artifact, dict) or baseline_artifact.get("path") != "run.json":
            errors.append("baseline observation does not cite its trusted run artifact")
        else:
            try:
                baseline_actual = hashlib.sha256(
                    (baseline_run.output_dir / "run.json").read_bytes()
                ).hexdigest()
            except OSError:
                baseline_actual = None
            if baseline_artifact.get("sha256") != baseline_actual:
                errors.append("baseline observation cites the wrong trusted run artifact")
    artifact = observation.get("run_artifact") if isinstance(observation, dict) else None
    actual_run = run.output_dir / "run.json"
    if type(artifact) is not dict or set(artifact) != {"path", "sha256"} or artifact.get("path") != "run.json":
        errors.append("activation observation does not cite the treatment run artifact")
    else:
        try:
            actual_digest = hashlib.sha256(actual_run.read_bytes()).hexdigest()
        except OSError:
            actual_digest = None
        if artifact.get("sha256") != actual_digest:
            errors.append("activation observation cites the wrong treatment run artifact")
    compact = None
    if isinstance(observation, dict) and isinstance(baseline, dict):
        compact = {
            **observation,
            "baseline_sha256": baseline.get("sha256"),
            "baseline_parsed_value": baseline.get("parsed_value"),
        }
    return compact, errors


def load_run(
    output_dir: Path,
    suite_name: str,
    *,
    expected_receipt: LiveRunReceipt | None = None,
) -> EvalRun:
    return _parse_run(output_dir, suite_name, expected_receipt=expected_receipt)


def _parse_run(
    output_dir: Path,
    suite_name: str,
    *,
    expected_receipt: LiveRunReceipt | None = None,
) -> EvalRun:
    summary, results = load_run_artifacts(
        output_dir, expected_receipt=expected_receipt
    )
    checked = validate_run_directory(output_dir, expected_receipt=expected_receipt)
    statuses: dict[str, str] = {}
    rewards: dict[str, float | None] = {}
    for row in results:
        task_id = row["task_id"]
        statuses[task_id] = row["status"]
        rewards[task_id] = row.get("reward")
    return EvalRun(
        output_dir=output_dir,
        suite_name=suite_name,
        summary=summary,
        statuses=statuses,
        rewards=rewards,
        run_id=str(summary.get("run_id", "")),
        results={str(row["task_id"]): row for row in results},
        live_receipt=expected_receipt,
        task_ids=list(checked.task_ids) if checked.ok else [],
        task_sources=dict(checked.task_sources) if checked.ok else {},
        protocol_digest=str(summary.get("protocol_digest", "")),
        run_context_digest=str(summary.get("run_context_digest", "")),
        run_context=dict(checked.run_context) if checked.ok else {},
        protocol_snapshot=dict(checked.protocol_snapshot) if checked.ok else {},
        task_records=dict(checked.tasks_by_id) if checked.ok else {},
    )
