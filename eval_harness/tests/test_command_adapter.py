from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

from opti_eval.adapters.command import CommandAdapter
from opti_eval.adapters.registry import RegistryAdapter
from opti_eval.catalog import select_tasks
from opti_eval.runner import run_evaluation
from opti_eval.summary import summarize_results


class CommandAdapterTest(unittest.TestCase):
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
        self.assertIn("Unsupported result status", result.error["message"])

    def test_minimal_passed_payload_is_useful_but_not_reportable(self) -> None:
        result = self._run_payload({"task_id": "task-a", "status": "passed"})
        self.assertEqual(result.status, "passed")
        self.assertEqual(result.reward, 1.0)
        self.assertIs(result.metadata["benchmark_reportable"], False)
        summary = summarize_results([result.to_dict()], adapter_reportable=True)
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

    def test_summary_requires_explicit_trusted_result_marker(self) -> None:
        summary = summarize_results(
            [{"task_id": "task-a", "source": "test-source", "status": "passed"}],
            adapter_reportable=True,
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
            record = run_evaluation(
                repo_root=root,
                suite=suite,
                tasks=tasks,
                adapter=CommandAdapter(command, timeout_seconds=30),
                output_dir=out,
            )
            self.assertTrue(record["summary"]["run_valid"])
            self.assertFalse(record["summary"]["benchmark_reportable"])
            self.assertEqual(record["summary"]["non_reportable_result_count"], 1)
            self.assertEqual(record["summary"]["status_counts"], {"passed": 1})
            self.assertTrue((out / "tasks" / tasks[0]["id"] / "bridge-result.json").is_file())


if __name__ == "__main__":
    unittest.main()
