from __future__ import annotations

import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from opti_eval.cli import main
from opti_eval.identity import simulated_run_identity
from opti_eval.models import validate_persisted_result, validate_task_id
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
        task_ids: list[object] = []
        task_manifest: list[dict[str, object]] = []
        tasks: list[dict[str, object]] = []
        protocol = None
        context = None
        try:
            for row in rows:
                validate_persisted_result(row)
                tasks.append({"id": row["task_id"], "source": row["source"]})
            protocol, context = simulated_run_identity(
                suite={"id": "suite-1", "kind": "test"},
                tasks=tasks,
                adapter={"name": adapter_name, "benchmark_reportable": False},
                run_id="run-1",
            )
            rows = copy.deepcopy(rows)
            for row in rows:
                row["metadata"]["run_context_digest"] = context["run_digest"]
        except (TypeError, ValueError):
            protocol = None
            context = None

        tasks_root = run_dir / "tasks"
        tasks_root.mkdir()
        for index, row in enumerate(rows):
            raw_task_id = row.get("task_id") if isinstance(row, dict) else None
            source = row.get("source", "test-source") if isinstance(row, dict) else "test-source"
            task_ids.append(raw_task_id)
            task_manifest.append({"task_id": raw_task_id, "source": source})
            try:
                directory_name = validate_task_id(raw_task_id)
            except ValueError:
                directory_name = f"invalid-row-{index}"
            task_dir = tasks_root / directory_name
            task_dir.mkdir(exist_ok=True)
            atomic_write_json(
                task_dir / "task.json", {"id": raw_task_id, "source": source}
            )
            atomic_write_json(task_dir / "result.json", row)
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
                **(
                    {
                        "protocol_digest": protocol["protocol_digest"],
                        "run_context_digest": context["run_digest"],
                        "adapter_digest": protocol["adapter"]["digest"],
                    }
                    if protocol is not None and context is not None
                    else {}
                ),
            },
        )
        atomic_write_json(
            run_dir / "run.json",
            {
                "schema_version": "0.2.0" if protocol is not None else "0.1.0",
                "run_id": "run-1",
                "status": "completed",
                "suite": {
                    "id": "suite-1",
                    "kind": "test",
                    "task_count_requested": len(rows),
                },
                "task_count": len(rows),
                "task_ids": task_ids,
                "task_manifest": task_manifest,
                "adapter": (
                    protocol["adapter"]
                    if protocol is not None
                    else {"name": adapter_name, "benchmark_reportable": True}
                ),
                **(
                    {
                        "protocol": protocol,
                        "run_context": context,
                        "run_context_digest": context["run_digest"],
                    }
                    if protocol is not None and context is not None
                    else {}
                ),
            },
        )

    @classmethod
    def _write_run(
        cls,
        run_dir: Path,
        markers: list[bool | None],
        *,
        adapter_name: str = "diagnostic-test",
        elapsed_seconds: int | float = 1.0,
    ) -> None:
        results = []
        for index, marker in enumerate(markers):
            metadata = {}
            if marker is not None:
                metadata["benchmark_reportable"] = marker
            results.append(
                {
                    "schema_version": "0.1.0",
                    "run_id": "run-1",
                    "task_id": f"task-{index}",
                    "source": "test-source",
                    "status": "passed",
                    "reward": 1.0,
                    "verifier": {},
                    "error": None,
                    "trace_path": None,
                    "artifacts": [],
                    "metrics": {},
                    "metadata": metadata,
                    "timing": {
                        "started_at": "2026-07-14T00:00:00Z",
                        "finished_at": "2026-07-14T00:00:01Z",
                        "elapsed_seconds": elapsed_seconds,
                    },
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

    def test_cli_replay_rejects_oversized_elapsed_without_overflow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            self._write_run(run_dir, [False], elapsed_seconds=10**4000)
            summary = load_run_summary(run_dir)
            self.assertFalse(summary["run_valid"])
            self.assertTrue(summary["replay_errors"])

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                self.assertEqual(main(["summarize", str(run_dir)]), 0)
            printed = json.loads(stdout.getvalue())
            self.assertFalse(printed["run_valid"])
            self.assertTrue(printed["replay_errors"])

    def test_malformed_result_matrix_fails_closed_for_helper_and_cli(self) -> None:
        valid = {
            "schema_version": "0.1.0",
            "run_id": "run-1",
            "task_id": "task-a",
            "source": "test-source",
            "status": "passed",
            "reward": 1.0,
            "verifier": {},
            "error": None,
            "trace_path": None,
            "artifacts": [],
            "metrics": {},
            "metadata": {"benchmark_reportable": True},
            "timing": {
                "started_at": "2026-07-14T00:00:00Z",
                "finished_at": "2026-07-14T00:00:01Z",
                "elapsed_seconds": 1.0,
            },
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
            "huge_reward": [{**valid, "reward": 10**4000}],
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
