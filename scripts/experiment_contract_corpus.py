"""Shared structural corpus for the experiment JSON Schema and runtime validator."""
from __future__ import annotations

import copy
from typing import Any

ContractCase = dict[str, Any]
PathPart = str | int


def _mutate(value: object, path: tuple[PathPart, ...], replacement: object) -> None:
    target = value
    for part in path[:-1]:
        target = target[part]  # type: ignore[index]
    target[path[-1]] = replacement  # type: ignore[index]


def _delete(value: object, path: tuple[PathPart, ...]) -> None:
    target = value
    for part in path[:-1]:
        target = target[part]  # type: ignore[index]
    del target[path[-1]]  # type: ignore[index]


def build_contract_corpus(
    example: dict[str, Any],
    schema: dict[str, Any],
    attribution: dict[str, Any],
) -> list[ContractCase]:
    """Return cases with independent JSON-Schema and optimizer-runtime outcomes."""
    cases: list[ContractCase] = []
    experiment_schema = schema["$defs"]["experiment"]

    def add(
        label: str,
        value: object,
        *,
        schema_valid: bool,
        runtime_valid: bool,
        branch: str = "experiment",
    ) -> None:
        cases.append({
            "label": label,
            "value": value,
            "schema_valid": schema_valid,
            "runtime_valid": runtime_valid,
            "branch": branch,
        })

    def changed(
        label: str,
        path: tuple[PathPart, ...],
        replacement: object,
        *,
        base: dict[str, Any] | None = None,
        schema_valid: bool = False,
        runtime_valid: bool = False,
        branch: str = "experiment",
    ) -> None:
        value = copy.deepcopy(base if base is not None else example)
        _mutate(value, path, replacement)
        add(
            label,
            value,
            schema_valid=schema_valid,
            runtime_valid=runtime_valid,
            branch=branch,
        )

    def deleted(
        label: str,
        path: tuple[PathPart, ...],
        *,
        base: dict[str, Any] | None = None,
        schema_valid: bool = False,
        runtime_valid: bool = False,
        branch: str = "experiment",
    ) -> None:
        value = copy.deepcopy(base if base is not None else example)
        _delete(value, path)
        add(
            label,
            value,
            schema_valid=schema_valid,
            runtime_valid=runtime_valid,
            branch=branch,
        )

    add("valid optimizer input", copy.deepcopy(example), schema_valid=True, runtime_valid=True)
    add("root array", [], schema_valid=False, runtime_valid=False)
    add("root null", None, schema_valid=False, runtime_valid=False)
    add("root string", "manifest", schema_valid=False, runtime_valid=False)
    add("root number", 7, schema_valid=False, runtime_valid=False)
    add("root boolean", True, schema_valid=False, runtime_valid=False)

    for fieldname in experiment_schema["required"]:
        deleted(f"missing required {fieldname}", (fieldname,))

    changed("unknown top-level field", ("optimizer_verdict",), "keep")
    changed("wrong schema version", ("schema_version",), "0.0")
    changed("empty experiment id", ("experiment_id",), "")
    changed("non-string experiment id", ("experiment_id",), 7)
    changed("unknown status", ("status",), "complete")
    changed("empty hypothesis", ("hypothesis",), "")
    changed("non-string hypothesis", ("hypothesis",), {})
    changed("trace evidence non-array", ("trace_evidence",), {})
    changed("trace evidence empty", ("trace_evidence",), [])
    changed("trace evidence non-object item", ("trace_evidence",), ["event"])
    changed("empty suspected root cause", ("suspected_root_cause",), "")
    changed("non-string suspected root cause", ("suspected_root_cause",), [])
    changed("unknown target component", ("target_component",), "routing")
    changed("non-string target component", ("target_component",), 4)
    changed("empty cluster reference", ("cluster_ref",), "")
    changed("non-string cluster reference", ("cluster_ref",), {})
    changed("empty baseline reference", ("baseline_ref",), "")
    changed("non-string baseline reference", ("baseline_ref",), 1)
    changed("fixed variables non-object", ("fixed_variables",), [])

    for status in experiment_schema["properties"]["status"]["enum"]:
        if status != "proposed":
            changed(
                f"stored status is not optimizer input: {status}",
                ("status",),
                status,
                schema_valid=True,
                runtime_valid=False,
            )

    changed("treatment non-object", ("treatment",), [])
    for fieldname in experiment_schema["properties"]["treatment"]["required"]:
        deleted(f"treatment missing {fieldname}", ("treatment", fieldname))
    changed("treatment unknown field", ("treatment", "optimizer_note"), "x")
    changed("treatment empty description", ("treatment", "description"), "")
    changed("treatment non-string description", ("treatment", "description"), 1)
    changed("change scope non-array", ("treatment", "change_scope"), {})
    changed("change scope empty", ("treatment", "change_scope"), [])
    changed("change scope non-string item", ("treatment", "change_scope"), [7])
    changed("change scope empty item", ("treatment", "change_scope"), [""])
    changed("activation evidence non-array", ("treatment", "activation_evidence"), {})
    changed("activation evidence non-string item", ("treatment", "activation_evidence"), [7])
    changed(
        "activation evidence empty string allowed",
        ("treatment", "activation_evidence"),
        [""],
        schema_valid=True,
        runtime_valid=True,
    )

    for fieldname in ("predicted_improvements", "regression_risks"):
        changed(f"{fieldname} non-array", (fieldname,), {})
        if fieldname == "predicted_improvements":
            changed(f"{fieldname} empty", (fieldname,), [])
        else:
            changed(
                "regression risks empty allowed",
                (fieldname,),
                [],
                schema_valid=True,
                runtime_valid=True,
            )
        changed(f"{fieldname} non-object item", (fieldname,), ["not-an-object"])
        for nested in schema["$defs"]["prediction"]["required"]:
            deleted(f"{fieldname} entry missing {nested}", (fieldname, 0, nested))
        changed(f"{fieldname} entry unknown field", (fieldname, 0, "confidence"), 1)
        changed(f"{fieldname} empty failure class", (fieldname, 0, "failure_class"), "")
        changed(f"{fieldname} non-string failure class", (fieldname, 0, "failure_class"), [])
        changed(f"{fieldname} tasks non-array", (fieldname, 0, "tasks"), {})
        changed(f"{fieldname} tasks non-string item", (fieldname, 0, "tasks"), [4])
        changed(f"{fieldname} tasks empty string", (fieldname, 0, "tasks"), [""])
        changed(f"{fieldname} tasks duplicate", (fieldname, 0, "tasks"), ["t", "t"])

    changed("evaluation plan non-object", ("evaluation_plan",), [])
    for fieldname in experiment_schema["properties"]["evaluation_plan"]["required"]:
        deleted(f"evaluation plan missing {fieldname}", ("evaluation_plan", fieldname))
    changed("task sets non-array", ("evaluation_plan", "task_sets"), {})
    changed("task sets empty", ("evaluation_plan", "task_sets"), [])
    changed("task sets non-string item", ("evaluation_plan", "task_sets"), [2])
    changed("task sets empty item", ("evaluation_plan", "task_sets"), [""])
    changed("repetitions non-object", ("evaluation_plan", "repetitions"), [])
    changed("repetitions non-integer", ("evaluation_plan", "repetitions"), {"dynamic": 1.5})
    changed("repetitions boolean", ("evaluation_plan", "repetitions"), {"dynamic": True})
    changed("repetitions below minimum", ("evaluation_plan", "repetitions"), {"dynamic": 0})
    changed(
        "integer-valued repetition number allowed",
        ("evaluation_plan", "repetitions"),
        {"dynamic": 1.0},
        schema_valid=True,
        runtime_valid=True,
    )
    changed("pairing non-string", ("evaluation_plan", "pairing"), {})
    changed("pairing empty", ("evaluation_plan", "pairing"), "")
    changed("budget non-object", ("evaluation_plan", "budget"), [])
    changed(
        "evaluation plan extension allowed",
        ("evaluation_plan", "operator_note"),
        "retained",
        schema_valid=True,
        runtime_valid=True,
    )

    changed("acceptance criteria non-object", ("acceptance_criteria",), [])
    changed("acceptance criteria empty", ("acceptance_criteria",), {})
    changed("result ref non-string", ("result_ref",), 1)
    changed("decision notes non-string", ("decision_notes",), [])
    changed("empty optional strings allowed", ("result_ref",), "", schema_valid=True, runtime_valid=True)

    enriched = copy.deepcopy(example)
    enriched["status"] = "accepted"
    enriched["attribution"] = copy.deepcopy(attribution)
    terminal_statuses = experiment_schema["allOf"][0]["then"]["properties"]["status"]["enum"]
    for status in terminal_statuses:
        value = copy.deepcopy(enriched)
        value["status"] = status
        add(
            f"valid conductor snapshot: {status}",
            value,
            schema_valid=True,
            runtime_valid=False,
        )
    nonterminal_statuses = set(experiment_schema["properties"]["status"]["enum"]) - set(terminal_statuses)
    for status in sorted(nonterminal_statuses):
        changed(
            f"attribution with non-terminal status: {status}",
            ("status",),
            status,
            base=enriched,
        )

    changed("attribution non-object", ("attribution",), [], base=enriched)
    attribution_schema = schema["$defs"]["attribution"]
    for fieldname in attribution_schema["required"]:
        deleted(f"attribution missing {fieldname}", ("attribution", fieldname), base=enriched)
    changed("attribution unknown field", ("attribution", "optimizer_note"), "x", base=enriched)
    changed("attribution unknown verdict", ("attribution", "verdict"), "accept", base=enriched)
    changed("attribution predicted count non-integer", ("attribution", "predicted_count"), 1.5, base=enriched)
    changed("attribution predicted count below minimum", ("attribution", "predicted_count"), -1, base=enriched)

    for fieldname in (
        "verified_fixes",
        "missed_predictions",
        "unpredicted_fixes",
        "predicted_risks",
        "materialized_regressions",
    ):
        changed(f"attribution {fieldname} non-array", ("attribution", fieldname), {}, base=enriched)
        changed(f"attribution {fieldname} non-string item", ("attribution", fieldname), [2], base=enriched)
        changed(f"attribution {fieldname} empty string", ("attribution", fieldname), [""], base=enriched)
        changed(f"attribution {fieldname} duplicate", ("attribution", fieldname), ["t", "t"], base=enriched)

    for fieldname in ("prediction_precision", "flip_recall"):
        changed(f"attribution {fieldname} non-number", ("attribution", fieldname), "0.5", base=enriched)
        changed(f"attribution {fieldname} below minimum", ("attribution", fieldname), -0.1, base=enriched)
        changed(f"attribution {fieldname} above maximum", ("attribution", fieldname), 1.1, base=enriched)
    changed("attribution note non-string", ("attribution", "note"), [], base=enriched)
    changed("attribution note empty", ("attribution", "note"), "", base=enriched)

    malformed_prediction = copy.deepcopy(example)
    malformed_prediction["predicted_improvements"] = ["not-an-object"]
    context_invalid_path = copy.deepcopy(example)
    context_invalid_path["treatment"]["change_scope"] = [
        "harness/components/policy/../observation/observation_contract.md"
    ]
    rejected_base = {
        "record_type": "rejected_submission",
        "schema_version": experiment_schema["properties"]["schema_version"]["const"],
        "status": "simulated:rejected",
        "verdict": {
            "decision": "rejected",
            "evidence_class": "simulated",
            "label": "simulated:rejected",
            "advances_accepted_state": False,
        },
        "validation_errors": ["manifest must be a JSON object"],
        "original_submission": None,
    }
    rejected_submissions = (
        ("array", []),
        ("null", None),
        ("string", "manifest"),
        ("number", 7),
        ("boolean", True),
        ("malformed prediction", malformed_prediction),
        ("context-invalid path", context_invalid_path),
    )
    for label, original_submission in rejected_submissions:
        rejected = copy.deepcopy(rejected_base)
        rejected["original_submission"] = original_submission
        add(
            f"valid rejected submission: {label}",
            rejected,
            schema_valid=True,
            runtime_valid=False,
            branch="rejected_submission",
        )

    rejected_schema = schema["$defs"]["rejected_submission"]
    for fieldname in rejected_schema["required"]:
        deleted(
            f"rejected submission missing {fieldname}",
            (fieldname,),
            base=rejected_base,
            branch="rejected_submission",
        )
    changed(
        "rejected submission unknown field",
        ("optimizer_note",),
        "x",
        base=rejected_base,
        branch="rejected_submission",
    )
    changed(
        "rejected submission wrong record type",
        ("record_type",),
        "experiment",
        base=rejected_base,
        branch="rejected_submission",
    )
    changed(
        "rejected submission empty validation errors",
        ("validation_errors",),
        [],
        base=rejected_base,
        branch="rejected_submission",
    )
    changed(
        "rejected submission empty validation error",
        ("validation_errors",),
        [""],
        base=rejected_base,
        branch="rejected_submission",
    )
    changed(
        "rejected submission inconsistent status",
        ("status",),
        "rejected",
        base=rejected_base,
        branch="rejected_submission",
    )
    changed(
        "rejected submission verdict extra field",
        ("verdict", "reason"),
        "invalid manifest",
        base=rejected_base,
        branch="rejected_submission",
    )

    labels = [case["label"] for case in cases]
    if len(labels) != len(set(labels)):
        raise AssertionError("experiment contract corpus labels must be unique")
    return cases
