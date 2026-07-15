from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from opti_eval.adapters.fixture import FixtureAdapter
from opti_eval.catalog import select_tasks
from opti_eval.identity import simulated_run_identity
from opti_eval.runner import run_evaluation
from opti_eval.summary import load_run_summary


class FixtureRunnerTest(unittest.TestCase):
    def test_runs_all_140_tasks(self) -> None:
        root = Path(os.environ["OPTI_BROWSER_REPO_ROOT"])
        suite, tasks = select_tasks(root, "primary")
        self.assertEqual(len(tasks), 140)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "run"
            adapter = FixtureAdapter(pass_rate=0.5, seed=7)
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
                max_workers=4,
                protocol_snapshot=protocol,
                run_context=context,
            ).record
            self.assertEqual(record["summary"]["task_count"], 140)
            self.assertTrue(record["summary"]["run_valid"])
            self.assertFalse(record["summary"]["benchmark_reportable"])
            self.assertEqual(len((out / "results.jsonl").read_text().splitlines()), 140)
            self.assertEqual(len(list((out / "tasks").iterdir())), 140)
            self.assertEqual(record["task_count"], 140)
            self.assertEqual(
                [row["task_id"] for row in record["task_manifest"]],
                record["task_ids"],
            )
            replayed = load_run_summary(out)
            self.assertTrue(replayed["run_valid"], replayed.get("replay_errors"))


if __name__ == "__main__":
    unittest.main()
