"""Change-manifest contract: one hypothesis, one component, one manifest.

The manifest is the repository's experiment record
(``schemas/experiment.schema.json``) plus the loop extensions proposed in
ADR-0015 §4:

- ``target_component``: exactly one component from the harness tree;
- ``cluster_ref``: the motivating failure-cluster ID (or ``"divergent"`` for
  an exploration iteration per ADR-0015 §9);
- ``attribution``: appended by the conductor after evaluation, never written
  by the optimizer.

Validation is structural and stdlib-only (the optional jsonschema check in
``scripts/validate_json_schemas.py`` remains the authoritative schema tool).
Field names follow agentic-harness-engineering's change manifest where the
two overlap (``predicted_fixes`` / ``risk_tasks`` appear inside the schema's
``predicted_improvements`` / ``regression_risks`` entries).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

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
    # loop extensions (ADR-0015 §4)
    "target_component",
    "cluster_ref",
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


@dataclass(slots=True)
class ManifestReport:
    manifest: dict | None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.manifest is not None and not self.errors


def load_and_validate(
    manifest_path: Path,
    *,
    changed_files: list[str] | None = None,
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
    report.manifest = manifest

    for fieldname in REQUIRED_FIELDS:
        if fieldname not in manifest:
            report.errors.append(f"missing required field: {fieldname}")
    if report.errors:
        return report

    component = manifest["target_component"]
    if component not in COMPONENTS:
        report.errors.append(
            f"target_component {component!r} is not one of {', '.join(COMPONENTS)}"
        )

    treatment = manifest.get("treatment") or {}
    for key in ("description", "change_scope", "activation_evidence"):
        if key not in treatment:
            report.errors.append(f"treatment.{key} is required")
    scope = treatment.get("change_scope") or []
    if not isinstance(scope, list) or not scope:
        report.errors.append("treatment.change_scope must be a non-empty list of paths")
        scope = []

    # One component per change (ADR-0015 §3.D): every changed path must sit
    # inside the declared component's directory.
    expected_prefix = f"{COMPONENT_ROOT}/{component}/"
    for path in scope:
        if not str(path).startswith(expected_prefix):
            report.errors.append(
                f"change_scope path {path!r} is outside {expected_prefix}"
            )
    if changed_files is not None:
        undeclared = [
            path
            for path in changed_files
            if path.startswith(COMPONENT_ROOT + "/") and path not in set(map(str, scope))
        ]
        for path in undeclared:
            report.errors.append(f"changed file not declared in change_scope: {path}")

    if not manifest.get("hypothesis", "").strip():
        report.errors.append("hypothesis must be non-empty")
    if not manifest.get("predicted_improvements"):
        report.errors.append(
            "predicted_improvements must name at least one failure class or task"
        )
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


def predicted_task_ids(manifest: dict) -> set[str]:
    tasks: set[str] = set()
    for entry in manifest.get("predicted_improvements", []):
        for task in entry.get("tasks", []) or []:
            tasks.add(str(task))
    return tasks
