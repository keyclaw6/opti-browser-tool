"""Static half of the E1 activation audit: component registration checks.

Pattern borrowed from agentic-harness-engineering's ``validate_agent.py``:
creating a file is not enough — it must be registered, and the registration
must be internally consistent. The dynamic half of E1 (trace evidence that
the changed component actually executed) requires the tracer and browser
runtime, which do not exist yet; the gate reports it as PENDING rather than
silently passing (fail-closed on honesty, permissive on execution until the
instrument exists — see loop_harness/README.md).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .manifest import COMPONENT_ROOT, COMPONENTS


@dataclass(slots=True)
class RegistrationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checked_components: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors


def check_tree(repo_root: Path) -> RegistrationReport:
    """Validate every component.json in the harness tree."""
    report = RegistrationReport()
    root = repo_root / COMPONENT_ROOT
    if not root.is_dir():
        report.errors.append(f"missing component root: {COMPONENT_ROOT}/")
        return report
    for component in COMPONENTS:
        directory = root / component
        manifest = directory / "component.json"
        if not directory.is_dir():
            report.errors.append(f"missing component directory: {component}")
            continue
        if not manifest.is_file():
            report.errors.append(f"missing registration: {component}/component.json")
            continue
        report.checked_components += 1
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            report.errors.append(f"{component}/component.json is not valid JSON: {exc}")
            continue
        if payload.get("component") != component:
            report.errors.append(
                f"{component}/component.json declares component "
                f"{payload.get('component')!r}"
            )
        for relfile in payload.get("files", []):
            if not (directory / relfile).is_file():
                report.errors.append(
                    f"{component}/component.json lists missing file: {relfile}"
                )
        if not payload.get("activation_events"):
            report.warnings.append(
                f"{component}: no activation_events declared — the dynamic E1 "
                "audit will have nothing to verify once traces exist"
            )
    return report


def check_change_registered(repo_root: Path, target_component: str, changed_files: list[str]) -> RegistrationReport:
    """Every changed file inside the component must be listed in its component.json."""
    report = check_tree(repo_root)
    directory = repo_root / COMPONENT_ROOT / target_component
    manifest_path = directory / "component.json"
    if not manifest_path.is_file():
        return report
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    listed = set(payload.get("files", []))
    prefix = f"{COMPONENT_ROOT}/{target_component}/"
    for path in changed_files:
        if not path.startswith(prefix):
            continue
        relative = path[len(prefix):]
        if relative == "component.json":
            continue
        if relative not in listed:
            report.errors.append(
                f"changed file not registered in {target_component}/component.json: {relative}"
            )
    return report
