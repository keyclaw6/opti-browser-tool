from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from opti_eval.adapters.base import AdapterExecutionContext
from opti_eval.adapters.command import CommandAdapter
from opti_eval.adapters.registry import RegistryAdapter
from opti_eval.catalog import select_tasks
from opti_eval.identity import simulated_run_identity
from opti_eval.runner import run_evaluation
from opti_eval.summary import summarize_results


class CommandAdapterTest(unittest.TestCase):
    @staticmethod
    def _execution_context() -> AdapterExecutionContext:
        return AdapterExecutionContext(
            run_id="test-run",
            run_context_digest="0" * 64,
        )

    @staticmethod
    def _payload_adapter(tmp: Path, payload: dict) -> CommandAdapter:
        bridge = tmp / "bridge.py"
        bridge.write_text(
            "import json, os\n"
            f"payload = {payload!r}\n"
            "with open(os.environ['OPTI_RESULT_JSON'], 'w', encoding='utf-8') as fh:\n"
            "    json.dump(payload, fh)\n",
            encoding="utf-8",
        )
        return CommandAdapter(f"{sys.executable} {bridge}", timeout_seconds=30)

    def _run_payload(self, payload: dict):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp) / "task"
            task_dir.mkdir()
            return self._payload_adapter(Path(tmp), payload).run(
                {"id": "task-a", "source": "test-source"},
                task_dir,
                execution_context=self._execution_context(),
            )

    @staticmethod
    def _raw_adapter(tmp: Path, raw: str) -> CommandAdapter:
        bridge = tmp / "raw_bridge.py"
        bridge.write_text(
            "import os\n"
            f"raw = {raw!r}\n"
            "with open(os.environ['OPTI_RESULT_JSON'], 'w', encoding='utf-8', newline='') as fh:\n"
            "    fh.write(raw)\n",
            encoding="utf-8",
        )
        return CommandAdapter(f"{sys.executable} {bridge}", timeout_seconds=30)

    def _run_raw(self, raw: str):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp) / "task"
            task_dir.mkdir()
            return self._raw_adapter(Path(tmp), raw).run(
                {"id": "task-a", "source": "test-source"},
                task_dir,
                execution_context=self._execution_context(),
            )

    def test_missing_task_id_is_invalid(self) -> None:
        result = self._run_payload({"status": "passed"})
        self.assertEqual(result.status, "invalid")
        self.assertEqual(result.error["kind"], "malformed_bridge_result")
        self.assertIn("non-empty string task_id", result.error["message"])

    def test_empty_task_id_is_invalid(self) -> None:
        for task_id in ("", "   "):
            with self.subTest(task_id=task_id):
                result = self._run_payload({"task_id": task_id, "status": "passed"})
                self.assertEqual(result.status, "invalid")
                self.assertEqual(result.error["kind"], "malformed_bridge_result")

    def test_mismatched_task_id_is_invalid(self) -> None:
        result = self._run_payload({"task_id": "task-b", "status": "passed"})
        self.assertEqual(result.status, "invalid")
        self.assertEqual(result.error["kind"], "malformed_bridge_result")
        self.assertIn("expected 'task-a'", result.error["message"])

    def test_legacy_success_fallback_is_invalid(self) -> None:
        result = self._run_payload({"task_id": "task-a", "success": True})
        self.assertEqual(result.status, "invalid")
        self.assertEqual(result.error["kind"], "malformed_bridge_result")
        self.assertIn("unsupported fields", result.error["message"])

    def test_bridge_result_reader_rejects_duplicate_and_nonfinite_json(self) -> None:
        attacks = (
            (
                "duplicate task identity",
                '{"task_id":"forged","task_id":"task-a","status":"passed"}',
                "duplicate object key",
            ),
            (
                "nan",
                '{"task_id":"task-a","status":"passed","metrics":{"probe":NaN}}',
                "non-JSON numeric constant",
            ),
            (
                "positive infinity",
                '{"task_id":"task-a","status":"passed","metrics":{"probe":Infinity}}',
                "non-JSON numeric constant",
            ),
            (
                "negative infinity",
                '{"task_id":"task-a","status":"passed","metrics":{"probe":-Infinity}}',
                "non-JSON numeric constant",
            ),
            (
                "positive overflow",
                '{"task_id":"task-a","status":"passed","metrics":{"probe":1e400}}',
                "non-finite JSON number",
            ),
            (
                "nested negative overflow",
                '{"task_id":"task-a","status":"passed","metrics":{"probe":[-1e400]}}',
                "non-finite JSON number",
            ),
        )
        for label, raw, reason in attacks:
            with self.subTest(attack=label):
                result = self._run_raw(raw)
                self.assertEqual(result.status, "invalid")
                self.assertEqual(result.error["kind"], "malformed_bridge_result")
                self.assertIn(reason, result.error["message"])

    def test_bridge_result_reader_accepts_only_standard_document_delimiters(self) -> None:
        raw = '{"task_id":"task-a","status":"passed"}'
        for suffix in ("", "\n", "\r\n"):
            with self.subTest(valid_suffix=repr(suffix)):
                result = self._run_raw(raw + suffix)
                self.assertEqual(result.status, "passed")

        for malformed in (
            "",
            "\n",
            raw + "\v",
            raw + "\f",
            raw + "\x1e",
            raw + "\u0085",
            raw + "\u2028",
            raw + "\u2029",
        ):
            with self.subTest(invalid_document=repr(malformed[-8:])):
                result = self._run_raw(malformed)
                self.assertEqual(result.status, "invalid")
                self.assertEqual(result.error["kind"], "malformed_bridge_result")

    def test_minimal_passed_payload_is_useful_but_not_reportable(self) -> None:
        result = self._run_payload({"task_id": "task-a", "status": "passed"})
        self.assertEqual(result.status, "passed")
        self.assertEqual(result.reward, 1.0)
        self.assertIs(result.metadata["benchmark_reportable"], False)
        summary = summarize_results([result.to_dict(run_id="test-run")])
        self.assertTrue(summary["run_valid"])
        self.assertFalse(summary["benchmark_reportable"])
        self.assertFalse(summary["acceptance_decision_eligible"])

    def test_bridge_cannot_self_promote_reportability(self) -> None:
        result = self._run_payload(
            {
                "task_id": "task-a",
                "status": "passed",
                "metadata": {"benchmark_reportable": True},
            }
        )
        self.assertIs(result.metadata["benchmark_reportable"], False)

    def test_bridge_cannot_set_runner_owned_run_id(self) -> None:
        result = self._run_payload(
            {"run_id": "bridge-forgery", "task_id": "task-a", "status": "passed"}
        )
        self.assertEqual(result.status, "invalid")
        self.assertIn("runner-owned run_id", result.error["message"])

    def test_summary_requires_explicit_trusted_result_marker(self) -> None:
        summary = summarize_results(
            [{"task_id": "task-a", "source": "test-source", "status": "passed"}],
        )
        self.assertFalse(summary["benchmark_reportable"])
        self.assertFalse(summary["acceptance_decision_eligible"])
        self.assertEqual(summary["non_reportable_result_count"], 1)

    def test_external_adapters_are_non_authoritative_by_default(self) -> None:
        self.assertFalse(CommandAdapter.benchmark_reportable)
        self.assertFalse(RegistryAdapter.benchmark_reportable)

    def test_external_bridge_contract(self) -> None:
        root = Path(os.environ["OPTI_BROWSER_REPO_ROOT"])
        suite, tasks = select_tasks(root, "smoke", limit=1)
        bridge = root / "eval_harness" / "examples" / "fixture_bridge.py"
        command = f"python {bridge} --task-json {{task_json}} --result-json {{result_json}} --pass-rate 1.0"
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "command-run"
            adapter = CommandAdapter(command, timeout_seconds=30)
            protocol, context = simulated_run_identity(
                suite=suite,
                tasks=tasks,
                adapter=adapter.describe(),
            )
            record = run_evaluation(
                repo_root=root,
                suite=suite,
                tasks=tasks,
                adapter=adapter,
                output_dir=out,
                protocol_snapshot=protocol,
                run_context=context,
            ).record
            self.assertTrue(record["summary"]["run_valid"])
            self.assertFalse(record["summary"]["benchmark_reportable"])
            self.assertEqual(record["summary"]["non_reportable_result_count"], 1)
            self.assertEqual(record["summary"]["status_counts"], {"passed": 1})
            self.assertTrue((out / "tasks" / tasks[0]["id"] / "bridge-result.json").is_file())
            persisted = json.loads(
                (out / "tasks" / tasks[0]["id"] / "result.json").read_text()
            )
            self.assertEqual(persisted["run_id"], record["run_id"])
            self.assertIsNone(persisted["trace_path"])
            self.assertTrue(all(isinstance(ref, dict) for ref in persisted["artifacts"]))


if __name__ == "__main__":
    unittest.main()
