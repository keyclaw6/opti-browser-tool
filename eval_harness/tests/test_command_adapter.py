from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from opti_eval.adapters.command import CommandAdapter
from opti_eval.catalog import select_tasks
from opti_eval.runner import run_evaluation


class CommandAdapterTest(unittest.TestCase):
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
