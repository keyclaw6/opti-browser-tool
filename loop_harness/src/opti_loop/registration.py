"""Static half of the E1 activation audit: component registration checks.

Pattern borrowed from agentic-harness-engineering's ``validate_agent.py``:
creating a file is not enough — it must be registered, and the registration
must be internally consistent. The bounded dynamic half for the local
harness-fixture path is conductor-owned in ``evaluate.py``/``gates.py``;
candidate registration remains supporting metadata, never activation authority.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from opti_eval.models import strict_json_loads

from .fileguard import is_regular_file, path_is_safe
from .manifest import COMPONENT_ROOT, COMPONENTS


REGISTRATION_FIELDS = {
    "component",
    "version",
    "purpose",
    "files",
    "interfaces",
    "activation_events",
    "emits",
}


@dataclass(slots=True)
class RegistrationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checked_components: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors


def _check_components(
    repo_root: Path,
    components: list[str],
    *,
    changed_files: list[str] | None = None,
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
            payload = strict_json_loads(
                manifest.read_text(encoding="utf-8"),
                field_name=f"{component}/component.json",
            )
        except (UnicodeDecodeError, ValueError) as exc:
            report.errors.append(f"{component}/component.json is not strict JSON: {exc}")
            continue
        if type(payload) is not dict:
            report.errors.append(f"{component}/component.json must be an object")
            continue
        for field_name in sorted(REGISTRATION_FIELDS - set(payload)):
            report.errors.append(
                f"{component}/component.json missing field: {field_name}"
            )
        for field_name in sorted(set(payload) - REGISTRATION_FIELDS):
            report.errors.append(
                f"{component}/component.json has unknown field: {field_name}"
            )
        if payload.get("component") != component:
            report.errors.append(
                f"{component}/component.json declares component "
                f"{payload.get('component')!r}"
            )
        for field_name in ("version", "purpose"):
            if type(payload.get(field_name)) is not str or not payload.get(field_name):
                report.errors.append(
                    f"{component}/component.json {field_name} must be a non-empty string"
                )
        for field_name in ("interfaces", "activation_events", "emits"):
            values = payload.get(field_name)
            if type(values) is not list or any(type(item) is not str for item in values):
                report.errors.append(
                    f"{component}/component.json {field_name} must be an array of strings"
                )
        files = payload.get("files")
        listed: set[str] = set()
        if type(files) is not list:
            report.errors.append(f"{component}/component.json files must be an array")
            files = []
        seen_files: set[str] = set()
        for relfile in files:
            duplicate = type(relfile) is str and relfile in seen_files
            if type(relfile) is str:
                seen_files.add(relfile)
            if type(relfile) is not str or not path_is_safe(relfile):
                report.errors.append(
                    f"{component}/component.json lists unsafe file: {relfile!r}"
                )
            if duplicate:
                report.errors.append(
                    f"{component}/component.json files must not contain duplicate values: "
                    f"{relfile!r}"
                )
            if (
                type(relfile) is str
                and path_is_safe(relfile)
                and relfile not in listed
                and not is_regular_file(directory, relfile)
            ):
                report.errors.append(
                    f"{component}/component.json lists missing file: {relfile}"
                )
                listed.add(relfile)
            elif type(relfile) is str and path_is_safe(relfile):
                listed.add(relfile)
        if type(payload.get("activation_events")) is list and not payload[
            "activation_events"
        ]:
            report.warnings.append(
                f"{component}: no activation_events declared — the dynamic E1 "
                "audit will have nothing to verify once traces exist"
            )
        if changed_files is not None:
            component_prefix = f"{COMPONENT_ROOT}/{component}/"
            for path in changed_files:
                if not path.startswith(component_prefix):
                    continue
                relative = path[len(component_prefix):]
                if relative != "component.json" and relative not in listed:
                    report.errors.append(
                        f"changed file not registered in {component}/component.json: "
                        f"{relative}"
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
        repo_root,
        [component for component in changed_components if component in COMPONENTS],
        changed_files=changed_files,
    )
    for component in unknown:
        report.errors.append(f"unknown legacy component directory: {component}")
    return report
