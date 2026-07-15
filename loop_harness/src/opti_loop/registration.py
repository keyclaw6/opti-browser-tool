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

from .fileguard import is_regular_file, path_is_safe
from .manifest import COMPONENT_ROOT, COMPONENTS


@dataclass(slots=True)
class RegistrationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checked_components: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors


def _check_components(
    repo_root: Path, components: list[str]
) -> RegistrationReport:
    report = RegistrationReport()
    root = repo_root / COMPONENT_ROOT
    for component in components:
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
        files = payload.get("files", [])
        if type(files) is not list:
            report.errors.append(f"{component}/component.json files must be an array")
            files = []
        for relfile in files:
            if type(relfile) is not str or not path_is_safe(relfile):
                report.errors.append(
                    f"{component}/component.json lists unsafe file: {relfile!r}"
                )
            elif not is_regular_file(directory, relfile):
                report.errors.append(
                    f"{component}/component.json lists missing file: {relfile}"
                )
        if not payload.get("activation_events"):
            report.warnings.append(
                f"{component}: no activation_events declared — the dynamic E1 "
                "audit will have nothing to verify once traces exist"
            )
    return report


def check_tree(repo_root: Path) -> RegistrationReport:
    """Validate every component.json in the legacy component tree."""
    if not (repo_root / COMPONENT_ROOT).is_dir():
        return RegistrationReport(errors=[f"missing component root: {COMPONENT_ROOT}/"])
    return _check_components(repo_root, list(COMPONENTS))


def check_change_registered(repo_root: Path, target_component: str, changed_files: list[str]) -> RegistrationReport:
    """Validate only legacy component paths actually changed.

    ``target_component`` is retained for manifest attribution compatibility;
    the frozen allowlist, not that label, owns path authority.
    """
    del target_component
    prefix = COMPONENT_ROOT + "/"
    changed_components = sorted(
        {
            path[len(prefix):].split("/", 1)[0]
            for path in changed_files
            if path.startswith(prefix) and "/" in path[len(prefix):]
        }
    )
    unknown = sorted(set(changed_components) - set(COMPONENTS))
    report = _check_components(
        repo_root, [component for component in changed_components if component in COMPONENTS]
    )
    for component in unknown:
        report.errors.append(f"unknown legacy component directory: {component}")
    for component in changed_components:
        if component not in COMPONENTS:
            continue
        directory = repo_root / COMPONENT_ROOT / component
        manifest_path = directory / "component.json"
        if not manifest_path.is_file():
            continue
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        listed = set(payload.get("files", []))
        component_prefix = f"{COMPONENT_ROOT}/{component}/"
        for path in changed_files:
            if not path.startswith(component_prefix):
                continue
            relative = path[len(component_prefix):]
            if relative != "component.json" and relative not in listed:
                report.errors.append(
                    f"changed file not registered in {component}/component.json: {relative}"
                )
    return report
