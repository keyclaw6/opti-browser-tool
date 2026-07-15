"""Mechanical checks that the experiment schema and stdlib runtime stay aligned."""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from opti_loop import manifest
from opti_loop.attribution import Attribution
from opti_loop.verdict import Verdict

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "schemas/experiment.schema.json"
EXAMPLE_PATH = REPO_ROOT / "examples/experiment.example.json"
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from experiment_contract_corpus import build_contract_corpus  # noqa: E402
from validate_json_schemas import (  # noqa: E402
    load_json as schema_load_json,
    strict_json_loads as schema_strict_json_loads,
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _runtime_report(payload: object) -> manifest.ManifestReport:
    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "manifest.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return manifest.load_and_validate(
            path,
            changed_files=["harness/components/observation/observation_contract.md"],
        )


def _attribution() -> dict:
    return Attribution(
        verdict="keep",
        predicted_count=2,
        verified_fixes=["dynamic-menu"],
        missed_predictions=["infinite-feed-action"],
        unpredicted_fixes=[],
        predicted_risks=["static-form"],
        materialized_regressions=[],
        prediction_precision=0.5,
        flip_recall=1.0,
    ).to_dict()


def _schema_validators(schema: dict) -> dict | None:
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        return None

    def branch_schema(name: str) -> dict:
        return {
            "$schema": schema["$schema"],
            "$defs": schema["$defs"],
            "$ref": f"#/$defs/{name}",
        }

    return {
        "canonical": Draft202012Validator(schema),
        "experiment": Draft202012Validator(branch_schema("experiment")),
        "rejected_submission": Draft202012Validator(
            branch_schema("rejected_submission")
        ),
    }


def _matching_branches(validators: dict, value: object) -> list[str]:
    return [
        branch
        for branch in ("experiment", "rejected_submission")
        if not list(validators[branch].iter_errors(value))
    ]


class ManifestContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = _load(SCHEMA_PATH)
        self.experiment_schema = self.schema["$defs"]["experiment"]
        self.example = _load(EXAMPLE_PATH)

    def test_schema_and_runtime_constants_cannot_drift(self) -> None:
        self.assertEqual(
            self.schema["oneOf"],
            [
                {"$ref": "#/$defs/experiment"},
                {"$ref": "#/$defs/rejected_submission"},
            ],
        )
        self.assertEqual(
            set(self.experiment_schema["required"]),
            set(manifest.REQUIRED_FIELDS),
        )
        self.assertEqual(
            set(self.experiment_schema["properties"]),
            set(manifest.REQUIRED_FIELDS) | set(manifest.OPTIONAL_FIELDS),
        )
        self.assertEqual(
            self.experiment_schema["properties"]["target_component"]["enum"],
            list(manifest.COMPONENTS),
        )
        self.assertEqual(
            self.experiment_schema["properties"]["status"]["enum"],
            list(manifest.MANIFEST_STATUSES),
        )
        self.assertEqual(
            self.experiment_schema["properties"]["schema_version"]["const"],
            manifest.SCHEMA_VERSION,
        )
        self.assertEqual(manifest.OPTIMIZER_STATUS, "proposed")
        self.assertEqual(
            self.experiment_schema["properties"]["predicted_improvements"]["minItems"],
            1,
        )
        self.assertEqual(
            set(self.experiment_schema["properties"]["treatment"]["required"]),
            set(manifest.TREATMENT_FIELDS),
        )
        self.assertEqual(
            set(self.schema["$defs"]["prediction"]["required"]),
            set(manifest.PREDICTION_FIELDS),
        )
        self.assertEqual(
            set(self.experiment_schema["properties"]["evaluation_plan"]["required"]),
            set(manifest.EVALUATION_FIELDS),
        )
        rejected_schema = self.schema["$defs"]["rejected_submission"]
        self.assertEqual(
            rejected_schema["properties"]["record_type"]["const"],
            manifest.REJECTED_SUBMISSION_RECORD_TYPE,
        )
        self.assertFalse(rejected_schema["additionalProperties"])

        attribution_schema = self.schema["$defs"]["attribution"]
        self.assertEqual(set(attribution_schema["required"]), set(_attribution()))
        terminal_statuses = self.experiment_schema["allOf"][0]["then"]["properties"]["status"]["enum"]
        actual_terminal_statuses = {
            Verdict(decision, evidence_class).label
            for decision in ("accepted", "rejected")
            for evidence_class in ("benchmark", "simulated")
        }
        self.assertEqual(
            set(terminal_statuses),
            actual_terminal_statuses,
        )

    def test_shared_structural_corpus_matches_runtime_and_schema(self) -> None:
        corpus = build_contract_corpus(self.example, self.schema, _attribution())
        self.assertGreaterEqual(len(corpus), 125)
        schema_validators = _schema_validators(self.schema)

        for case in corpus:
            with self.subTest(contract="runtime", case=case["label"]):
                self.assertEqual(_runtime_report(case["value"]).ok, case["runtime_valid"])
            if schema_validators is not None:
                with self.subTest(contract="json-schema-branch", case=case["label"]):
                    branch = case["branch"]
                    branch_valid = not list(
                        schema_validators[branch].iter_errors(case["value"])
                    )
                    matching = _matching_branches(schema_validators, case["value"])
                    canonical_valid = not list(
                        schema_validators["canonical"].iter_errors(case["value"])
                    )
                    expected_matches = [branch] if case["schema_valid"] else []
                    self.assertEqual(branch_valid, case["schema_valid"])
                    self.assertEqual(matching, expected_matches)
                    self.assertEqual(
                        canonical_valid,
                        case["schema_valid"],
                    )
                    self.assertEqual(canonical_valid, len(matching) == 1)

    def test_conductor_snapshot_is_schema_shaped_but_optimizer_cannot_supply_it(self) -> None:
        schema_validators = _schema_validators(self.schema)

        terminal_statuses = {
            Verdict(decision, evidence_class).label
            for decision in ("accepted", "rejected")
            for evidence_class in ("benchmark", "simulated")
        }
        for status in sorted(terminal_statuses):
            enriched = copy.deepcopy(self.example)
            enriched["status"] = status
            enriched["attribution"] = _attribution()

            with self.subTest(contract="optimizer-runtime", status=status):
                report = _runtime_report(enriched)
                self.assertFalse(report.ok)
                self.assertIn("conductor appends it", " ".join(report.errors))
            if schema_validators is not None:
                with self.subTest(contract="conductor-schema", status=status):
                    self.assertEqual(
                        list(schema_validators["experiment"].iter_errors(enriched)),
                        [],
                    )
                    self.assertEqual(
                        _matching_branches(schema_validators, enriched),
                        ["experiment"],
                    )
                    self.assertEqual(
                        list(schema_validators["canonical"].iter_errors(enriched)),
                        [],
                    )

    def test_rejected_submission_variant_preserves_any_json_and_is_not_optimizer_input(self) -> None:
        schema_validators = _schema_validators(self.schema)

        malformed_prediction = copy.deepcopy(self.example)
        malformed_prediction["predicted_improvements"] = ["not-an-object"]
        context_invalid = copy.deepcopy(self.example)
        context_invalid["treatment"]["change_scope"] = [
            "harness/components/observation/../policy/quality.txt"
        ]
        originals = ([], None, "manifest", 7, True, malformed_prediction, context_invalid)
        verdict = Verdict("rejected", "simulated").to_dict()
        for original in originals:
            rejected = manifest.rejected_submission_record(
                original_submission=original,
                validation_errors=["optimizer submission failed validation"],
                verdict=verdict,
            )
            with self.subTest(original=original):
                self.assertEqual(rejected["original_submission"], original)
                self.assertEqual(rejected["validation_errors"], ["optimizer submission failed validation"])
                self.assertEqual(rejected["status"], verdict["label"])
                self.assertEqual(rejected["verdict"], verdict)
                self.assertFalse(_runtime_report(rejected).ok)
                if schema_validators is not None:
                    self.assertEqual(
                        list(
                            schema_validators["rejected_submission"].iter_errors(
                                rejected
                            )
                        ),
                        [],
                    )
                    self.assertEqual(
                        _matching_branches(schema_validators, rejected),
                        ["rejected_submission"],
                    )
                    self.assertEqual(
                        list(schema_validators["canonical"].iter_errors(rejected)),
                        [],
                    )

    def test_schema_loader_rejects_top_level_and_nested_numeric_overflow(self) -> None:
        positive = (
            ("finite top-level", "1e308", 1e308),
            ("finite negative top-level", "-1e308", -1e308),
            ("finite nested", '{"values":[1e308,-1e308]}', {"values": [1e308, -1e308]}),
        )
        for label, raw, expected in positive:
            with self.subTest(valid=label):
                self.assertEqual(schema_strict_json_loads(raw), expected)

        negative = (
            ("positive top-level", "1e400"),
            ("negative top-level", "-1e400"),
            ("positive nested", '{"values":[1e400]}'),
            ("negative nested", '{"outer":{"value":-1e400}}'),
        )
        for label, raw in negative:
            with self.subTest(invalid=label):
                with self.assertRaisesRegex(ValueError, "non-finite JSON number"):
                    schema_strict_json_loads(raw)
                with tempfile.TemporaryDirectory() as temp_dir:
                    path = Path(temp_dir) / "schema.json"
                    path.write_text(raw, encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "non-finite JSON number"):
                        schema_load_json(path)

    def test_schema_tool_skips_derived_corpus_for_invalid_optimizer_example(self) -> None:
        try:
            import jsonschema  # noqa: F401
        except ImportError:
            self.skipTest("optional jsonschema dependency is not installed")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            root.mkdir()
            for directory in (
                "evals",
                "validation",
                "schemas",
                "loop_harness",
                "eval_harness",
                "scripts",
            ):
                (root / directory).symlink_to(REPO_ROOT / directory, target_is_directory=True)
            (root / "examples").mkdir()
            invalid_example = copy.deepcopy(self.example)
            del invalid_example["experiment_id"]
            (root / "examples/experiment.example.json").write_text(
                json.dumps(invalid_example),
                encoding="utf-8",
            )
            output = Path(temp_dir) / "schema-report.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts/validate_json_schemas.py"),
                    "--repo-root",
                    str(root),
                    "--output",
                    str(output),
                ],
                cwd=REPO_ROOT,
                env=os.environ.copy(),
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertNotIn("Traceback", completed.stderr)
            self.assertTrue(output.is_file())
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(json.loads(completed.stdout), report)
            self.assertFalse(report["ok"])
            self.assertEqual(report["experiment_corpus"]["status"], "skipped")
            enriched = next(
                check
                for check in report["checks"]
                if check["label"] == "experiment:conductor-enriched"
            )
            self.assertEqual(enriched["status"], "skipped")
            self.assertTrue(enriched["reason"])
            skipped = next(
                check
                for check in report["checks"]
                if check["label"] == "experiment-corpus:generation"
            )
            self.assertEqual(skipped["status"], "skipped")
            self.assertTrue(skipped["reason"])
            optimizer_check = next(
                check
                for check in report["checks"]
                if check["label"] == "experiment:optimizer-input"
            )
            self.assertFalse(optimizer_check["actual_valid"])
            self.assertTrue(optimizer_check["validation_errors"])
            self.assertEqual(optimizer_check["canonical_branch"], "experiment")
            self.assertEqual(optimizer_check["canonical_branch_matches"], [])
            self.assertFalse(optimizer_check["canonical_root_valid"])

    def test_predicted_task_ids_is_defensive_for_untrusted_shapes(self) -> None:
        cases = (
            ([], set()),
            ({"predicted_improvements": "not-an-array"}, set()),
            ({"predicted_improvements": ["not-an-object"]}, set()),
            ({"predicted_improvements": [{"tasks": "not-an-array"}]}, set()),
            ({"predicted_improvements": [{"tasks": [7, "", "task-1"]}]}, {"task-1"}),
        )
        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(manifest.predicted_task_ids(value), expected)


if __name__ == "__main__":
    unittest.main()
