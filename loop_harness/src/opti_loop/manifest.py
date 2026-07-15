"""Change-manifest contract: one hypothesis, one component, one manifest.

The manifest is the repository's canonical experiment contract
(``schemas/experiment.schema.json``), including the loop fields required by
ADR-0015 §4:

- ``target_component``: exactly one component from the harness tree;
- ``cluster_ref``: the motivating failure-cluster ID (or ``"divergent"`` for
  an exploration iteration per ADR-0015 §9);
- ``attribution``: appended by the conductor after evaluation, never written
  by the optimizer.

The same canonical schema also defines a conductor-only
``rejected_submission`` record. It preserves malformed optimizer JSON and the
validation errors verbatim instead of fabricating a complete experiment.

Validation is structural and stdlib-only (the optional jsonschema check in
``scripts/validate_json_schemas.py`` remains the authoritative schema tool).
Prediction and risk entries use one shared ``failure_class`` + ``tasks``
shape so downstream attribution never receives an untyped entry.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .fileguard import is_allowed, path_is_safe

REQUIRED_FIELDS = (
    "schema_version",
    "experiment_id",
    "status",
    "hypothesis",
    "trace_evidence",
    "suspected_root_cause",
    "treatment",
    "baseline_ref",
    "fixed_variables",
    "predicted_improvements",
    "regression_risks",
    "evaluation_plan",
    "acceptance_criteria",
    # Loop identity (ADR-0015 §4).
    "target_component",
    "cluster_ref",
)

OPTIONAL_FIELDS = (
    "result_ref",
    "decision_notes",
    # Present only in conductor-owned snapshots; rejected from optimizer input.
    "attribution",
)

SCHEMA_VERSION = "0.1-draft"
OPTIMIZER_STATUS = "proposed"
REJECTED_SUBMISSION_RECORD_TYPE = "rejected_submission"

MANIFEST_STATUSES = (
    "proposed",
    "running",
    "accepted",
    "rejected",
    "inconclusive",
    "invalid",
    "simulated:accepted",
    "simulated:rejected",
    "simulated:invalid",
)

COMPONENTS = (
    "policy",
    "observation",
    "actions",
    "tool_descriptions",
    "middleware",
    "skills",
    "sub_agents",
    "memory",
)

COMPONENT_ROOT = "harness/components"
TREATMENT_FIELDS = ("description", "change_scope", "activation_evidence")
PREDICTION_FIELDS = ("failure_class", "tasks")
EVALUATION_FIELDS = ("task_sets", "repetitions", "pairing", "budget")


@dataclass(slots=True)
class ManifestReport:
    manifest: dict | None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.manifest is not None and not self.errors


def rejected_submission_record(
    *,
    original_submission: object,
    validation_errors: list[str],
    verdict: dict[str, object],
) -> dict[str, object]:
    """Build the schema-defined conductor record for invalid optimizer input."""
    errors = list(validation_errors)
    if not errors or any(not isinstance(error, str) or not error for error in errors):
        raise ValueError("rejected submission requires non-empty validation errors")
    verdict_fields = {"decision", "evidence_class", "label", "advances_accepted_state"}
    if set(verdict) != verdict_fields:
        raise ValueError("rejected submission verdict has an invalid shape")
    evidence_class = verdict.get("evidence_class")
    expected_status = (
        "rejected" if evidence_class == "benchmark"
        else "simulated:rejected" if evidence_class == "simulated"
        else None
    )
    if (
        verdict.get("decision") != "rejected"
        or verdict.get("label") != expected_status
        or verdict.get("advances_accepted_state") is not False
    ):
        raise ValueError("rejected submission requires a consistent rejected verdict")
    return {
        "record_type": REJECTED_SUBMISSION_RECORD_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": expected_status,
        "verdict": dict(verdict),
        "validation_errors": errors,
        "original_submission": original_submission,
    }


def _is_nonempty_string(value: object) -> bool:
    return isinstance(value, str) and len(value) > 0


def _validate_string_list(
    report: ManifestReport,
    value: object,
    fieldname: str,
    *,
    min_items: int = 0,
    unique: bool = False,
    nonempty: bool = True,
) -> list[str]:
    if not isinstance(value, list):
        report.errors.append(f"{fieldname} must be an array")
        return []
    if len(value) < min_items:
        report.errors.append(f"{fieldname} must contain at least {min_items} item(s)")

    valid: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or (nonempty and not item):
            qualifier = "non-empty " if nonempty else ""
            report.errors.append(f"{fieldname}[{index}] must be a {qualifier}string")
            continue
        valid.append(item)
    if unique and len(valid) != len(set(valid)):
        report.errors.append(f"{fieldname} must not contain duplicate values")
    return valid


def _validate_predictions(
    report: ManifestReport,
    value: object,
    fieldname: str,
    *,
    min_items: int,
) -> None:
    if not isinstance(value, list):
        report.errors.append(f"{fieldname} must be an array")
        return
    if len(value) < min_items:
        report.errors.append(f"{fieldname} must contain at least {min_items} item(s)")

    allowed = set(PREDICTION_FIELDS)
    for index, entry in enumerate(value):
        prefix = f"{fieldname}[{index}]"
        if not isinstance(entry, dict):
            report.errors.append(f"{prefix} must be an object")
            continue
        for key in sorted(set(entry) - allowed):
            report.errors.append(f"unknown field: {prefix}.{key}")
        for key in PREDICTION_FIELDS:
            if key not in entry:
                report.errors.append(f"{prefix}.{key} is required")
        if "failure_class" in entry and not _is_nonempty_string(entry["failure_class"]):
            report.errors.append(f"{prefix}.failure_class must be a non-empty string")
        if "tasks" in entry:
            _validate_string_list(report, entry["tasks"], f"{prefix}.tasks", unique=True)


def _validate_evaluation_plan(report: ManifestReport, value: object) -> None:
    if not isinstance(value, dict):
        report.errors.append("evaluation_plan must be an object")
        return
    for key in EVALUATION_FIELDS:
        if key not in value:
            report.errors.append(f"evaluation_plan.{key} is required")

    if "task_sets" in value:
        _validate_string_list(
            report,
            value["task_sets"],
            "evaluation_plan.task_sets",
            min_items=1,
        )
    repetitions = value.get("repetitions")
    if "repetitions" in value and not isinstance(repetitions, dict):
        report.errors.append("evaluation_plan.repetitions must be an object")
    elif isinstance(repetitions, dict):
        for key, count in repetitions.items():
            # JSON Schema's ``integer`` type is mathematical: ``1.0`` is an
            # integer value even though Python decodes it as ``float``. Keep
            # the stdlib validator aligned while still rejecting booleans.
            is_integer = (
                not isinstance(count, bool)
                and isinstance(count, (int, float))
                and float(count).is_integer()
            )
            if not is_integer or count < 1:
                report.errors.append(
                    f"evaluation_plan.repetitions.{key} must be an integer of at least 1"
                )
    if "pairing" in value and not _is_nonempty_string(value["pairing"]):
        report.errors.append("evaluation_plan.pairing must be a non-empty string")
    if "budget" in value and not isinstance(value["budget"], dict):
        report.errors.append("evaluation_plan.budget must be an object")


def load_and_validate(
    manifest_path: Path,
    *,
    allowed_prefixes: tuple[str, ...],
    changed_files: list[str] | None = None,
    divergent: bool = False,
) -> ManifestReport:
    report = ManifestReport(manifest=None)
    if not manifest_path.is_file():
        report.errors.append(f"manifest not found: {manifest_path}")
        return report
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        report.errors.append(f"manifest is not valid JSON: {exc}")
        return report
    if not isinstance(manifest, dict):
        report.errors.append("manifest must be a JSON object")
        return report
    report.manifest = manifest

    for fieldname in REQUIRED_FIELDS:
        if fieldname not in manifest:
            report.errors.append(f"missing required field: {fieldname}")
    if report.errors:
        return report

    allowed_fields = set(REQUIRED_FIELDS) | set(OPTIONAL_FIELDS)
    for fieldname in sorted(set(manifest) - allowed_fields):
        report.errors.append(f"unknown top-level field: {fieldname}")

    if manifest["schema_version"] != SCHEMA_VERSION:
        report.errors.append(
            f"schema_version must be {SCHEMA_VERSION!r}, got {manifest['schema_version']!r}"
        )
    if manifest["status"] != OPTIMIZER_STATUS:
        report.errors.append(
            f"optimizer manifest status must be {OPTIMIZER_STATUS!r}; "
            f"the conductor owns terminal status (got {manifest['status']!r})"
        )

    for fieldname in (
        "experiment_id",
        "hypothesis",
        "suspected_root_cause",
        "baseline_ref",
        "cluster_ref",
    ):
        if not _is_nonempty_string(manifest[fieldname]):
            report.errors.append(f"{fieldname} must be a non-empty string")

    trace_evidence = manifest["trace_evidence"]
    if not isinstance(trace_evidence, list):
        report.errors.append("trace_evidence must be an array")
    elif not trace_evidence:
        report.errors.append("trace_evidence must contain at least 1 item")
    else:
        for index, entry in enumerate(trace_evidence):
            if not isinstance(entry, dict):
                report.errors.append(f"trace_evidence[{index}] must be an object")

    component = manifest["target_component"]
    if component not in COMPONENTS:
        report.errors.append(
            f"target_component {component!r} is not one of {', '.join(COMPONENTS)}"
        )

    treatment = manifest["treatment"]
    if not isinstance(treatment, dict):
        report.errors.append("treatment must be an object")
        treatment = {}
    for key in sorted(set(treatment) - set(TREATMENT_FIELDS)):
        report.errors.append(f"unknown field: treatment.{key}")
    for key in TREATMENT_FIELDS:
        if key not in treatment:
            report.errors.append(f"treatment.{key} is required")
    if "description" in treatment and not _is_nonempty_string(treatment["description"]):
        report.errors.append("treatment.description must be a non-empty string")
    scope = _validate_string_list(
        report,
        treatment.get("change_scope"),
        "treatment.change_scope",
        min_items=1,
        unique=True,
    ) if "change_scope" in treatment else []
    if "activation_evidence" in treatment:
        _validate_string_list(
            report,
            treatment["activation_evidence"],
            "treatment.activation_evidence",
            nonempty=False,
        )

    # The frozen candidate allowlist is the sole path authority (ADR-0018).
    # target_component remains attribution metadata; it cannot narrow or
    # broaden the treatment.  change_scope must be path-safe and exactly match
    # the complete base..candidate commit diff.
    for path in scope:
        if not isinstance(path, str) or not path:
            report.errors.append(f"change_scope path must be a non-empty string: {path!r}")
            continue
        path_str = path
        if not path_is_safe(path_str):
            report.errors.append(f"unsafe change_scope path: {path_str!r}")
            continue
        if not is_allowed(path_str, allowed_prefixes):
            report.errors.append(f"change_scope path {path_str!r} is outside the optimizer surface")
    if changed_files is not None:
        scope_set = set(scope)
        changed_set = set(changed_files)
        undeclared = sorted(changed_set - scope_set)
        for path in undeclared:
            report.errors.append(f"changed file not declared in change_scope: {path}")
        unchanged = sorted(scope_set - changed_set)
        for path in unchanged:
            report.errors.append(f"change_scope declares unchanged file: {path}")

    # Exploration enforcement (F16): a divergent iteration must NOT be a local
    # retry on the top cluster. It must carry a reserved divergent cluster_ref
    # and (advisory) an architecture-class hypothesis.
    cluster_ref = manifest["cluster_ref"] if isinstance(manifest["cluster_ref"], str) else ""
    if divergent and not cluster_ref.startswith("divergent"):
        report.errors.append(
            "divergent iteration requires cluster_ref starting with 'divergent' "
            "(no local retry of the top cluster is permitted this iteration)"
        )
    if not divergent and cluster_ref.startswith("divergent"):
        report.errors.append(
            "cluster_ref 'divergent*' used in a non-divergent iteration"
        )

    if not isinstance(manifest["fixed_variables"], dict):
        report.errors.append("fixed_variables must be an object")

    _validate_predictions(
        report,
        manifest["predicted_improvements"],
        "predicted_improvements",
        min_items=1,
    )
    _validate_predictions(
        report,
        manifest["regression_risks"],
        "regression_risks",
        min_items=0,
    )
    _validate_evaluation_plan(report, manifest["evaluation_plan"])

    acceptance_criteria = manifest["acceptance_criteria"]
    if not isinstance(acceptance_criteria, dict) or not acceptance_criteria:
        report.errors.append("acceptance_criteria must be a non-empty object")

    if "result_ref" in manifest and not isinstance(manifest["result_ref"], str):
        report.errors.append("result_ref must be a string")
    if "decision_notes" in manifest and not isinstance(manifest["decision_notes"], str):
        report.errors.append("decision_notes must be a string")
    if manifest.get("regression_risks") == []:
        # AHE finding: "empty at_risk_regressions is almost never true".
        # A warning, not an error — and per ADR-0015 §8 the risk list is
        # never used for gate protection either way.
        report.warnings.append(
            "regression_risks is empty — the reference evidence says this is almost never true"
        )
    if "attribution" in manifest:
        report.errors.append(
            "manifest must not contain 'attribution' — the conductor appends it after evaluation"
        )
    return report


def predicted_task_ids(manifest: object) -> set[str]:
    tasks: set[str] = set()
    if not isinstance(manifest, dict):
        return tasks
    entries = manifest.get("predicted_improvements")
    if not isinstance(entries, list):
        return tasks
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        predicted = entry.get("tasks")
        if not isinstance(predicted, list):
            continue
        for task in predicted:
            if isinstance(task, str) and task:
                tasks.add(task)
    return tasks
