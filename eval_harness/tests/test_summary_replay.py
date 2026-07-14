from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from opti_eval.cli import main
from opti_eval.summary import load_run_summary
from opti_eval.util import atomic_write_json


class SummaryReplayTest(unittest.TestCase):
    @staticmethod
    def _write_rows(
        run_dir: Path,
        rows: list[object],
        *,
        adapter_name: str = "diagnostic-test",
    ) -> None:
        run_dir.joinpath("results.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in rows),
            encoding="utf-8",
        )
        atomic_write_json(
            run_dir / "summary.json",
            {
                "schema_version": "0.1.0",
                "run_id": "run-1",
                "suite_id": "suite-1",
                "task_count": len(rows),
                "status_counts": {"passed": len(rows)},
                "run_valid": True,
                "benchmark_reportable": True,
                "acceptance_decision_eligible": True,
                "non_reportable_result_count": 0,
            },
        )
        atomic_write_json(
            run_dir / "run.json",
            {"adapter": {"name": adapter_name, "benchmark_reportable": True}},
        )

    @classmethod
    def _write_run(
        cls,
        run_dir: Path,
        markers: list[bool | None],
        *,
        adapter_name: str = "diagnostic-test",
    ) -> None:
        results = []
        for index, marker in enumerate(markers):
            metadata = {}
            if marker is not None:
                metadata["benchmark_reportable"] = marker
            results.append(
                {
                    "task_id": f"task-{index}",
                    "source": "test-source",
                    "status": "passed",
                    "reward": 1.0,
                    "metadata": metadata,
                }
            )
        cls._write_rows(run_dir, results, adapter_name=adapter_name)

    def test_false_marker_overrides_optimistic_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            self._write_run(run_dir, [False])
            summary = load_run_summary(run_dir)
            self.assertFalse(summary["benchmark_reportable"])
            self.assertFalse(summary["acceptance_decision_eligible"])

    def test_missing_marker_overrides_optimistic_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            self._write_run(run_dir, [None])
            summary = load_run_summary(run_dir)
            self.assertFalse(summary["benchmark_reportable"])
            self.assertEqual(summary["non_reportable_result_count"], 1)

    def test_mixed_markers_override_optimistic_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            self._write_run(run_dir, [True, False])
            summary = load_run_summary(run_dir)
            self.assertFalse(summary["benchmark_reportable"])
            self.assertFalse(summary["acceptance_decision_eligible"])
            self.assertEqual(summary["non_reportable_result_count"], 1)

    def test_known_external_adapter_legacy_claims_are_nonreportable(self) -> None:
        for adapter_name in ("base", "command", "fixture", "registry"):
            with self.subTest(adapter_name=adapter_name), tempfile.TemporaryDirectory() as tmp:
                run_dir = Path(tmp)
                self._write_run(run_dir, [True], adapter_name=adapter_name)
                summary = load_run_summary(run_dir)
                self.assertFalse(summary["benchmark_reportable"])
                self.assertFalse(summary["acceptance_decision_eligible"])

    def test_arbitrary_persisted_adapter_name_is_not_authority(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            self._write_run(run_dir, [True], adapter_name="made-up-authority")
            summary = load_run_summary(run_dir)
            self.assertFalse(summary["benchmark_reportable"])

    def test_cli_replay_rejects_legacy_command_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            self._write_run(run_dir, [True], adapter_name="command")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                self.assertEqual(main(["summarize", str(run_dir)]), 0)
            printed = json.loads(stdout.getvalue())
            self.assertFalse(printed["benchmark_reportable"])
            self.assertFalse(printed["acceptance_decision_eligible"])

    def test_malformed_result_matrix_fails_closed_for_helper_and_cli(self) -> None:
        valid = {
            "task_id": "task-a",
            "source": "test-source",
            "status": "passed",
            "reward": 1.0,
            "metadata": {"benchmark_reportable": True},
        }
        cases: dict[str, list[object]] = {
            "bogus_status": [{**valid, "status": "bogus"}],
            "uppercase_status": [{**valid, "status": "PASSED"}],
            "null_status": [{**valid, "status": None}],
            "numeric_status": [{**valid, "status": 1}],
            "missing_status": [{k: v for k, v in valid.items() if k != "status"}],
            "missing_task_id": [{k: v for k, v in valid.items() if k != "task_id"}],
            "numeric_task_id": [{**valid, "task_id": 1}],
            "empty_task_id": [{**valid, "task_id": ""}],
            "duplicate_task_id": [valid, dict(valid)],
            "malformed_metadata": [{**valid, "metadata": []}],
            "non_object_row": [["not", "an", "object"]],
            "empty_results": [],
        }
        for name, rows in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                run_dir = Path(tmp)
                self._write_rows(run_dir, rows)
                summary = load_run_summary(run_dir)
                self.assertFalse(summary["run_valid"])
                self.assertFalse(summary["benchmark_reportable"])
                self.assertFalse(summary["acceptance_decision_eligible"])
                self.assertTrue(summary["replay_errors"])

                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    self.assertEqual(main(["summarize", str(run_dir)]), 0)
                printed = json.loads(stdout.getvalue())
                self.assertFalse(printed["run_valid"])
                self.assertFalse(printed["acceptance_decision_eligible"])


if __name__ == "__main__":
    unittest.main()
