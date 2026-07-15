"""Shared AR-003 evidence corpus through producer, runtime, and replay paths."""
from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
import unittest
from functools import partial
from pathlib import Path

ROOT = Path(os.environ["OPTI_BROWSER_REPO_ROOT"])
sys.path.insert(0, str(ROOT / "scripts"))

from evidence_contract_corpus import (  # noqa: E402
    build_evidence_contract_corpus,
    persisted_result,
)
from opti_eval.adapters.fixture import FixtureAdapter  # noqa: E402
from opti_eval.catalog import load_catalog, load_suite  # noqa: E402
from opti_eval.errors import ValidationError  # noqa: E402
from opti_eval.models import (  # noqa: E402
    TaskResult,
    canonical_json,
    validate_persisted_result,
)
from opti_eval.runner import run_evaluation  # noqa: E402
from opti_eval.summary import load_run_summary  # noqa: E402


def _write_replay(run_dir: Path, result: dict) -> None:
    task_id = result.get("task_id")
    source = result.get("source", "test-source")
    run_dir.mkdir()
    task_dir = run_dir / "tasks" / "task-a"
    task_dir.mkdir(parents=True)
    (task_dir / "task.json").write_text(
        json.dumps({"id": task_id, "source": source}) + "\n", encoding="utf-8"
    )
    (task_dir / "result.json").write_text(
        json.dumps(result) + "\n", encoding="utf-8"
    )
    (run_dir / "results.jsonl").write_text(
        json.dumps(result) + "\n", encoding="utf-8"
    )
    (run_dir / "summary.json").write_text(
        json.dumps({"run_id": "run-1", "task_count": 1}) + "\n",
        encoding="utf-8",
    )
    (run_dir / "run.json").write_text(
        json.dumps(
            {
                "schema_version": "0.1.0",
                "run_id": "run-1",
                "status": "completed",
                "suite": {"id": "test", "kind": "test", "task_count_requested": 1},
                "task_count": 1,
                "task_ids": [task_id],
                "task_manifest": [{"task_id": task_id, "source": source}],
                "adapter": {"name": "test", "benchmark_reportable": False},
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _prepend_json_member(text: str, key: str, raw_value: str) -> str:
    start = text.find("{")
    if start < 0:
        raise AssertionError("test fixture is not a JSON object")
    return text[:start] + f'{{"{key}":{raw_value},' + text[start + 1 :]


class EvidenceContractCorpusTest(unittest.TestCase):
    def test_valid_producer_shape_matches_runtime_contract(self) -> None:
        expected = persisted_result()
        produced = TaskResult(
            task_id=expected["task_id"],
            source=expected["source"],
            status=expected["status"],
            reward=expected["reward"],
            verifier=copy.deepcopy(expected["verifier"]),
            error=expected["error"],
            trace_path=expected["trace_path"],
            artifacts=copy.deepcopy(expected["artifacts"]),
            metrics=copy.deepcopy(expected["metrics"]),
            metadata=copy.deepcopy(expected["metadata"]),
        ).to_dict(run_id=expected["run_id"])
        produced["timing"] = copy.deepcopy(expected["timing"])
        self.assertEqual(canonical_json(produced), canonical_json(expected))
        self.assertEqual(validate_persisted_result(produced), produced)

    def test_shared_result_and_bridge_cases_match_runtime(self) -> None:
        for case in build_evidence_contract_corpus():
            if case["target"] == "result":
                with self.subTest(case=case["label"]):
                    if case["runtime_valid"]:
                        validate_persisted_result(case["value"])
                    else:
                        with self.assertRaises(ValueError):
                            validate_persisted_result(case["value"])
            elif case["target"] == "bridge":
                with self.subTest(case=case["label"]):
                    if case["runtime_valid"]:
                        TaskResult.from_external(
                            case["value"],
                            expected_task_id="task-a",
                            source="test-source",
                        )
                    else:
                        with self.assertRaises(ValueError):
                            TaskResult.from_external(
                                case["value"],
                                expected_task_id="task-a",
                                source="test-source",
                            )

    def test_shared_task_and_suite_cases_match_runtime(self) -> None:
        for case in build_evidence_contract_corpus():
            if case["target"] not in {"task", "suite"}:
                continue
            with self.subTest(case=case["label"]), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                if case["target"] == "task":
                    catalog = root / "evals" / "catalog"
                    catalog.mkdir(parents=True)
                    (catalog / "tasks.jsonl").write_text(
                        json.dumps(case["value"]) + "\n",
                        encoding="utf-8",
                    )
                    operation = partial(load_catalog, root)
                else:
                    suites = root / "evals" / "suites"
                    suites.mkdir(parents=True)
                    (suites / "primary.json").write_text(
                        json.dumps(case["value"]) + "\n",
                        encoding="utf-8",
                    )
                    operation = partial(load_suite, root, "primary")
                if case["runtime_valid"]:
                    operation()
                else:
                    with self.assertRaises(ValidationError):
                        operation()

    def test_catalog_and_suite_readers_reject_nonstandard_raw_json(self) -> None:
        task = {
            "id": "task-a",
            "source": "test-source",
            "goal": "Complete the task",
            "site": "example.test",
        }
        suite = {"id": "primary", "task_ids": ["task-a"], "task_count": 1}
        targets = (
            (
                "catalog",
                Path("evals/catalog/tasks.jsonl"),
                json.dumps(task, separators=(",", ":")),
                "id",
                '"task-a"',
                load_catalog,
            ),
            (
                "suite",
                Path("evals/suites/primary.json"),
                json.dumps(suite, separators=(",", ":")),
                "id",
                '"primary"',
                lambda root: load_suite(root, "primary"),
            ),
        )
        attacks = (
            ("nan", "NaN"),
            ("positive infinity", "Infinity"),
            ("negative infinity", "-Infinity"),
            ("positive overflow", "1e400"),
            ("negative overflow", "-1e400"),
            ("nested overflow", '{"nested":[1e400]}'),
        )
        for label, relative, raw, identity_key, identity_value, operation in targets:
            with self.subTest(target=label, attack="duplicate-key"), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                path = root / relative
                path.parent.mkdir(parents=True)
                path.write_text(
                    _prepend_json_member(raw, identity_key, identity_value),
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(ValidationError, "duplicate object key"):
                    operation(root)

            for attack, raw_value in attacks:
                with self.subTest(target=label, attack=attack), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    path = root / relative
                    path.parent.mkdir(parents=True)
                    path.write_text(
                        _prepend_json_member(raw, "strict_probe", raw_value),
                        encoding="utf-8",
                    )
                    with self.assertRaisesRegex(
                        ValidationError,
                        r"non-JSON numeric constant|non-finite JSON number",
                    ):
                        operation(root)

    def test_catalog_and_suite_delimiters_are_explicit(self) -> None:
        task = json.dumps(
            {
                "id": "task-a",
                "source": "test-source",
                "goal": "Complete the task",
                "site": "example.test",
            },
            separators=(",", ":"),
        )
        suite = json.dumps(
            {"id": "primary", "task_ids": ["task-a"], "task_count": 1},
            separators=(",", ":"),
        )
        for delimiter in ("", "\n", "\r\n"):
            with self.subTest(catalog_delimiter=repr(delimiter)), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                path = root / "evals/catalog/tasks.jsonl"
                path.parent.mkdir(parents=True)
                path.write_text(task + delimiter, encoding="utf-8")
                rows, _ = load_catalog(root)
                self.assertEqual(len(rows), 1)
            with self.subTest(suite_delimiter=repr(delimiter)), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                path = root / "evals/suites/primary.json"
                path.parent.mkdir(parents=True)
                path.write_text(suite + delimiter, encoding="utf-8")
                self.assertEqual(load_suite(root, "primary")["id"], "primary")

        invalid_catalog = (
            ("empty", lambda row: ""),
            ("blank", lambda row: "\n"),
            ("blank-first", lambda row: "\n" + row + "\n"),
            ("blank-last", lambda row: row + "\n\n"),
            ("lone-cr", lambda row: row + "\r"),
            ("vertical-tab", lambda row: row + "\v" + row),
            ("form-feed", lambda row: row + "\f" + row),
            ("record-separator", lambda row: row + "\x1e" + row),
            ("next-line", lambda row: row + "\u0085" + row),
            ("line-separator", lambda row: row + "\u2028" + row),
            ("paragraph-separator", lambda row: row + "\u2029" + row),
        )
        for label, mutate in invalid_catalog:
            with self.subTest(catalog_framing=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                path = root / "evals/catalog/tasks.jsonl"
                path.parent.mkdir(parents=True)
                path.write_text(mutate(task), encoding="utf-8")
                with self.assertRaises(ValidationError):
                    load_catalog(root)

        invalid_suite = (
            ("empty", ""),
            ("blank", "\n"),
            ("vertical-tab", suite + "\v"),
            ("form-feed", suite + "\f"),
            ("record-separator", suite + "\x1e"),
            ("next-line", suite + "\u0085"),
            ("line-separator", suite + "\u2028"),
            ("paragraph-separator", suite + "\u2029"),
        )
        for label, malformed in invalid_suite:
            with self.subTest(suite_framing=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                path = root / "evals/suites/primary.json"
                path.parent.mkdir(parents=True)
                path.write_text(malformed, encoding="utf-8")
                with self.assertRaises(ValidationError):
                    load_suite(root, "primary")

    def test_shared_result_cases_match_replay(self) -> None:
        cases = [
            case
            for case in build_evidence_contract_corpus()
            if case["target"] == "result"
        ]
        for case in cases:
            with self.subTest(case=case["label"]), tempfile.TemporaryDirectory() as tmp:
                run_dir = Path(tmp) / "run"
                _write_replay(run_dir, case["value"])
                summary = load_run_summary(run_dir)
                self.assertEqual(summary["run_valid"], case["runtime_valid"])
                if not case["runtime_valid"]:
                    self.assertTrue(summary["replay_errors"])

    def test_unsafe_task_id_is_rejected_before_runner_path_construction(self) -> None:
        for task_id in ("../../escaped", "/absolute", " task-a", "task/a"):
            with self.subTest(task_id=task_id), tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp) / "run"
                with self.assertRaises(ValueError):
                    run_evaluation(
                        repo_root=ROOT,
                        suite={"id": "test", "kind": "test"},
                        tasks=[{"id": task_id, "source": "test-source"}],
                        adapter=FixtureAdapter(),
                        output_dir=output,
                    )
                self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
