"""AR-003 adversarial tests at the real eligibility and E5 boundary."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from opti_loop.evaluate import EvalRun
from opti_loop.eligibility import assess
from opti_loop.gates import run_gate
from opti_eval.models import (
    EDGE_WHITESPACE_CHARS,
    EDGE_WHITESPACE_SCHEMA_CLASS,
    MAX_FINITE_REAL_MAGNITUDE,
    has_edge_whitespace,
)
from opti_judge import evidence
from opti_judge.quarantine import QuarantineQueue, QuarantineStateError
from opti_judge.t1_checks import expectations_from_task

ROOT = Path(os.environ["OPTI_BROWSER_REPO_ROOT"])
sys.path.insert(0, str(ROOT / "scripts"))
from evidence_contract_corpus import build_evidence_contract_corpus  # noqa: E402


def _ref(path: Path, root: Path, kind: str, media_type: str) -> dict:
    return {
        "kind": kind,
        "uri": path.relative_to(root).as_posix(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "media_type": media_type,
        "visibility": ["judge", "orchestrator"],
    }


def _event(
    sequence: int,
    event_type: str,
    payload: dict,
    *,
    actor: str = "browser",
    run_id: str = "run-1",
    task_id: str = "task-a",
    refs: list[dict] | None = None,
) -> dict:
    if event_type == "verifier_result":
        payload = {
            "verifier_id": "verifier-v1",
            "verifier_checksum": "checksum-v1",
            **payload,
        }
    event = {
        "schema_version": "0.1-draft",
        "run_id": run_id,
        "task_id": task_id,
        "event_id": f"event-{sequence}",
        "sequence": sequence,
        "timestamp": f"2026-07-14T00:00:{sequence:02d}+00:00",
        "monotonic_ms": float(sequence),
        "actor": actor,
        "event_type": event_type,
        "visibility": ["judge", "orchestrator"],
        "payload": payload,
        "artifact_refs": list(refs or []),
    }
    if event_type in evidence.EPOCH_EVENT_TYPES:
        event["browser_state_epoch"] = 0
    return event


def _resequence(events: list[dict]) -> None:
    for sequence, event in enumerate(events, start=1):
        event.update(
            sequence=sequence,
            event_id=f"event-{sequence}",
            timestamp=f"2026-07-14T00:00:{sequence:02d}+00:00",
            monotonic_ms=float(sequence),
        )


def _prepend_json_member(text: str, key: str, raw_value: str) -> str:
    start = text.find("{")
    if start < 0:
        raise AssertionError("test fixture is not a JSON object")
    return text[:start] + f'{{"{key}":{raw_value},' + text[start + 1 :]


class _Bundle:
    def __init__(self, root: Path) -> None:
        self.run_id = "run-1"
        self.verifier_id = "verifier-v1"
        self.verifier_checksum = "checksum-v1"
        self.run_dir = root / "run"
        self.task_dir = self.run_dir / "tasks" / "task-a"
        self.task_dir.mkdir(parents=True)
        self.trace_path = self.task_dir / "trace.jsonl"
        self.screenshot = self.task_dir / "final.png"
        self.task_record = {
            "id": "task-a",
            "source": "test-source",
            "state_change_expected": False,
            "verification": {
                "verifier_id": self.verifier_id,
                "verifier_checksum": self.verifier_checksum,
            },
        }
        (self.task_dir / "task.json").write_text(
            json.dumps(self.task_record) + "\n", encoding="utf-8"
        )
        self.screenshot.write_bytes(b"trusted screenshot")
        screenshot_ref = _ref(self.screenshot, self.task_dir, "screenshot", "image/png")
        self.events = [
            _event(1, "browser_state", {"done": False}, refs=[screenshot_ref]),
            _event(2, "action_requested", {"action": "click", "target": "#save"}),
            _event(3, "action_result", {"outcome": "ok"}),
            _event(4, "browser_state", {"done": False}),
            _event(5, "verifier_result", {"status": "passed"}, actor="verifier"),
        ]
        self._write_trace(self.events)
        self.result = {
            "schema_version": "0.1.0",
            "run_id": self.run_id,
            "task_id": "task-a",
            "source": "test-source",
            "status": "passed",
            "reward": 1.0,
            "verifier": {
                "id": self.verifier_id,
                "checksum": self.verifier_checksum,
                "outcome": "passed",
            },
            "error": None,
            "trace_path": "trace.jsonl",
            "artifacts": [
                _ref(self.trace_path, self.task_dir, "trace", "application/x-ndjson"),
                screenshot_ref,
            ],
            "metrics": {},
            "metadata": {"benchmark_reportable": True},
            "timing": {
                "started_at": "2026-07-14T00:00:00+00:00",
                "finished_at": "2026-07-14T00:00:05+00:00",
                "elapsed_seconds": 5.0,
            },
        }
        self.run = EvalRun(
            output_dir=self.run_dir,
            suite_name="test",
            summary={
                "run_valid": True,
                "acceptance_decision_eligible": True,
                "strict_success_rate": 1.0,
            },
            statuses={"task-a": "passed"},
            rewards={"task-a": 1.0},
            run_id=self.run_id,
            results={"task-a": self.result},
            adapter_reportable=True,
            task_ids=["task-a"],
            task_sources={"task-a": "test-source"},
        )
        self.admissions = root / "admissions.jsonl"
        self.admissions.write_text(
            json.dumps(
                {
                    "verifier_id": self.verifier_id,
                    "task_id": "task-a",
                    "verifier_checksum": self.verifier_checksum,
                    "admitted": True,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        self.quarantine = root / "quarantine.jsonl"
        self._write_result()

    def _write_trace(self, events: list[dict]) -> None:
        self.events = events
        self.trace_path.write_text(
            "".join(json.dumps(event) + "\n" for event in events),
            encoding="utf-8",
        )

    def rewrite_trace(self, events: list[dict]) -> None:
        self._write_trace(events)
        trace_ref = next(ref for ref in self.result["artifacts"] if ref["kind"] == "trace")
        trace_ref["sha256"] = hashlib.sha256(self.trace_path.read_bytes()).hexdigest()
        self._write_result()

    def rewrite_raw_trace(self, text: str) -> None:
        self.trace_path.write_text(text, encoding="utf-8")
        trace_ref = next(ref for ref in self.result["artifacts"] if ref["kind"] == "trace")
        trace_ref["sha256"] = hashlib.sha256(self.trace_path.read_bytes()).hexdigest()
        self._write_result()

    def _write_result(self) -> None:
        self.run.results["task-a"] = self.result
        (self.task_dir / "result.json").write_text(
            json.dumps(self.result, sort_keys=True) + "\n", encoding="utf-8"
        )
        (self.run_dir / "results.jsonl").write_text(
            json.dumps(self.result, sort_keys=True) + "\n", encoding="utf-8"
        )
        (self.run_dir / "summary.json").write_text(
            json.dumps(
                {
                    "schema_version": "0.1.0",
                    "run_id": self.run_id,
                    "suite_id": "test",
                    "task_count": 1,
                    "run_valid": True,
                    "benchmark_reportable": True,
                    "acceptance_decision_eligible": True,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (self.run_dir / "run.json").write_text(
            json.dumps(
                {
                    "schema_version": "0.1.0",
                    "run_id": self.run_id,
                    "status": "completed",
                    "suite": {
                        "id": "test",
                        "kind": "test",
                        "task_count_requested": 1,
                    },
                    "task_count": 1,
                    "task_ids": ["task-a"],
                    "task_manifest": [
                        {"task_id": "task-a", "source": "test-source"}
                    ],
                    "verifier": {
                        "id": self.verifier_id,
                        "checksum": self.verifier_checksum,
                    },
                    "adapter": {"name": "test", "benchmark_reportable": True},
                }
            )
            + "\n",
            encoding="utf-8",
        )

    def evaluate(self):
        return assess(
            run=self.run,
            run_dir=self.run_dir,
            adapter_config={
                "verifier_id": self.verifier_id,
                "verifier_checksum": self.verifier_checksum,
            },
            task_records={"task-a": self.task_record},
            admissions_path=self.admissions,
            quarantine_path=self.quarantine,
        )

    def rebind_repaired_run(
        self,
        run_id: str,
        *,
        verifier_id: str | None = None,
        verifier_checksum: str | None = None,
    ) -> None:
        self.run_id = run_id
        if verifier_id is not None:
            self.verifier_id = verifier_id
        if verifier_checksum is not None:
            self.verifier_checksum = verifier_checksum
        for event in self.events:
            event["run_id"] = self.run_id
            if event["event_type"] == "verifier_result":
                event["payload"]["verifier_id"] = self.verifier_id
                event["payload"]["verifier_checksum"] = self.verifier_checksum
        self.result["run_id"] = self.run_id
        self.result["verifier"]["id"] = self.verifier_id
        self.result["verifier"]["checksum"] = self.verifier_checksum
        self.run.run_id = self.run_id
        self.task_record["verification"]["verifier_id"] = self.verifier_id
        self.task_record["verification"]["verifier_checksum"] = self.verifier_checksum
        (self.task_dir / "task.json").write_text(
            json.dumps(self.task_record) + "\n", encoding="utf-8"
        )
        self.admissions.write_text(
            self.admissions.read_text(encoding="utf-8")
            + json.dumps(
                {
                    "verifier_id": self.verifier_id,
                    "task_id": "task-a",
                    "verifier_checksum": self.verifier_checksum,
                    "admitted": True,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        self.rewrite_trace(self.events)

    def set_verifier_status(self, status: str) -> None:
        reward = 1.0 if status == "passed" else 0.0
        self.result["status"] = status
        self.result["reward"] = reward
        self.result["verifier"]["outcome"] = status
        self.run.statuses["task-a"] = status
        self.run.rewards["task-a"] = reward
        for event in self.events:
            if event["event_type"] == "verifier_result":
                event["payload"]["status"] = status
        self.rewrite_trace(self.events)

    def add_task_b(self) -> dict:
        task_id = "task-b"
        source = "other-source"
        task_dir = self.run_dir / "tasks" / task_id
        task_dir.mkdir()
        task_record = {
            "id": task_id,
            "source": source,
            "state_change_expected": False,
            "verification": {
                "verifier_id": "verifier-v1",
                "verifier_checksum": "checksum-v1",
            },
        }
        (task_dir / "task.json").write_text(
            json.dumps(task_record) + "\n", encoding="utf-8"
        )
        (task_dir / "final.png").write_bytes(self.screenshot.read_bytes())
        events = json.loads(json.dumps(self.events))
        for event in events:
            event["task_id"] = task_id
        trace_path = task_dir / "trace.jsonl"
        trace_path.write_text(
            "".join(json.dumps(event) + "\n" for event in events), encoding="utf-8"
        )
        result = json.loads(json.dumps(self.result))
        result["task_id"] = task_id
        result["source"] = source
        for ref in result["artifacts"]:
            path = task_dir / ref["uri"]
            ref["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        (task_dir / "result.json").write_text(
            json.dumps(result, sort_keys=True) + "\n", encoding="utf-8"
        )

        run_record = json.loads((self.run_dir / "run.json").read_text())
        run_record["task_count"] = 2
        run_record["task_ids"] = ["task-a", task_id]
        run_record["task_manifest"] = [
            {"task_id": "task-a", "source": "test-source"},
            {"task_id": task_id, "source": source},
        ]
        run_record["suite"]["task_count_requested"] = 2
        (self.run_dir / "run.json").write_text(
            json.dumps(run_record) + "\n", encoding="utf-8"
        )
        summary = json.loads((self.run_dir / "summary.json").read_text())
        summary["task_count"] = 2
        (self.run_dir / "summary.json").write_text(
            json.dumps(summary) + "\n", encoding="utf-8"
        )
        (self.run_dir / "results.jsonl").write_text(
            json.dumps(self.result, sort_keys=True)
            + "\n"
            + json.dumps(result, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        self.run.statuses[task_id] = "passed"
        self.run.rewards[task_id] = 1.0
        self.run.results[task_id] = result
        self.run.task_ids.append(task_id)
        self.run.task_sources[task_id] = source
        return task_record


class EvidenceEligibilityTest(unittest.TestCase):
    def test_quarantine_state_is_empty_only_when_genuinely_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle = _Bundle(Path(tmp))
            self.assertFalse(bundle.quarantine.exists())
            self.assertEqual(QuarantineQueue(bundle.quarantine).pending(), [])
            eligibility = bundle.evaluate()
            self.assertEqual(eligibility.integrity_status, "valid")
            self.assertTrue(eligibility.acceptance_eligible)

        for kind in ("directory", "symlink", "broken-symlink"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                bundle = _Bundle(root)
                if kind == "directory":
                    bundle.quarantine.mkdir()
                elif kind == "symlink":
                    target = root / "real-quarantine.jsonl"
                    target.write_text("", encoding="utf-8")
                    bundle.quarantine.symlink_to(target)
                else:
                    bundle.quarantine.symlink_to(root / "missing-quarantine.jsonl")
                eligibility = bundle.evaluate()
                self.assertEqual(eligibility.integrity_status, "invalid")
                self.assertFalse(eligibility.acceptance_eligible)
                self.assertIn(
                    "quarantine state is unavailable",
                    " ".join(eligibility.integrity_errors),
                )

    def test_quarantine_stat_and_read_failures_are_integrity_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle = _Bundle(Path(tmp))
            real_lstat = Path.lstat

            def fail_queue_lstat(path: Path, *args, **kwargs):
                if path == bundle.quarantine:
                    raise OSError("synthetic stat failure")
                return real_lstat(path, *args, **kwargs)

            with mock.patch.object(Path, "lstat", autospec=True, side_effect=fail_queue_lstat):
                eligibility = bundle.evaluate()
            self.assertEqual(eligibility.integrity_status, "invalid")
            self.assertIn("cannot be inspected", " ".join(eligibility.integrity_errors))

        with tempfile.TemporaryDirectory() as tmp:
            bundle = _Bundle(Path(tmp))
            bundle.quarantine.write_text("", encoding="utf-8")
            real_open = Path.open

            def fail_queue_open(path: Path, *args, **kwargs):
                if path == bundle.quarantine:
                    raise PermissionError("synthetic read failure")
                return real_open(path, *args, **kwargs)

            with mock.patch.object(
                Path, "open", autospec=True, side_effect=fail_queue_open
            ):
                eligibility = bundle.evaluate()
            self.assertEqual(eligibility.integrity_status, "invalid")
            self.assertIn("unreadable", " ".join(eligibility.integrity_errors))

    def test_quarantine_failure_during_routing_is_integrity_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle = _Bundle(Path(tmp))
            events = json.loads(json.dumps(bundle.events))
            events.insert(
                -2,
                _event(4, "network_event", {"method": "DELETE", "url": "/x"}),
            )
            _resequence(events)
            bundle.rewrite_trace(events)
            with mock.patch.object(
                QuarantineQueue,
                "_load_all",
                side_effect=[[], QuarantineStateError("synthetic routing read failure")],
            ):
                eligibility = bundle.evaluate()
            self.assertEqual(eligibility.integrity_status, "invalid")
            self.assertIn("T1 routing failed", " ".join(eligibility.integrity_errors))

    def test_conforming_positive_control_reaches_benchmark_eligibility(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle = _Bundle(Path(tmp))
            eligibility = bundle.evaluate()
            self.assertEqual(eligibility.integrity_status, "valid")
            self.assertEqual(eligibility.evidence_class, "benchmark")
            self.assertTrue(eligibility.acceptance_eligible)
            self.assertEqual(eligibility.t1_flag_count, 0)

    def test_all_persisted_run_documents_use_strict_standard_json(self) -> None:
        documents = (
            ("run.json", lambda b: b.run_dir / "run.json", "run_id", '"run-1"'),
            (
                "summary.json",
                lambda b: b.run_dir / "summary.json",
                "run_id",
                '"run-1"',
            ),
            (
                "results.jsonl",
                lambda b: b.run_dir / "results.jsonl",
                "task_id",
                '"task-a"',
            ),
            (
                "task.json",
                lambda b: b.task_dir / "task.json",
                "id",
                '"task-a"',
            ),
            (
                "result.json",
                lambda b: b.task_dir / "result.json",
                "task_id",
                '"task-a"',
            ),
        )
        numeric_attacks = (
            ("nan", "NaN"),
            ("positive infinity", "Infinity"),
            ("negative infinity", "-Infinity"),
            ("positive overflow", "1e400"),
            ("negative overflow", "-1e400"),
            ("nested overflow", '{"nested":[1e400]}'),
        )
        for label, locate, identity_key, identity_value in documents:
            with self.subTest(document=label, attack="duplicate-key"), tempfile.TemporaryDirectory() as tmp:
                bundle = _Bundle(Path(tmp))
                path = locate(bundle)
                path.write_text(
                    _prepend_json_member(
                        path.read_text(encoding="utf-8"),
                        identity_key,
                        identity_value,
                    ),
                    encoding="utf-8",
                )
                eligibility = bundle.evaluate()
                self.assertEqual(eligibility.integrity_status, "invalid")
                self.assertIn("duplicate object key", " ".join(eligibility.integrity_errors))

            for attack, raw_value in numeric_attacks:
                with self.subTest(document=label, attack=attack), tempfile.TemporaryDirectory() as tmp:
                    bundle = _Bundle(Path(tmp))
                    path = locate(bundle)
                    path.write_text(
                        _prepend_json_member(
                            path.read_text(encoding="utf-8"),
                            "strict_probe",
                            raw_value,
                        ),
                        encoding="utf-8",
                    )
                    eligibility = bundle.evaluate()
                    self.assertEqual(eligibility.integrity_status, "invalid")
                    self.assertRegex(
                        " ".join(eligibility.integrity_errors),
                        r"non-JSON numeric constant|non-finite JSON number",
                    )

    def test_aggregate_results_jsonl_has_exact_record_framing(self) -> None:
        for delimiter in ("", "\n", "\r\n"):
            with self.subTest(valid_delimiter=repr(delimiter)), tempfile.TemporaryDirectory() as tmp:
                bundle = _Bundle(Path(tmp))
                path = bundle.run_dir / "results.jsonl"
                record = path.read_text(encoding="utf-8").rstrip("\n")
                path.write_text(record + delimiter, encoding="utf-8")
                eligibility = bundle.evaluate()
                self.assertEqual(eligibility.integrity_status, "valid")
                self.assertTrue(eligibility.acceptance_eligible)

        invalid = (
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
        for label, mutate in invalid:
            with self.subTest(invalid_framing=label), tempfile.TemporaryDirectory() as tmp:
                bundle = _Bundle(Path(tmp))
                path = bundle.run_dir / "results.jsonl"
                record = path.read_text(encoding="utf-8").rstrip("\n")
                path.write_text(mutate(record), encoding="utf-8")
                eligibility = bundle.evaluate()
                self.assertEqual(eligibility.integrity_status, "invalid")

    def test_persisted_json_documents_have_standard_document_framing(self) -> None:
        documents = (
            ("run.json", lambda b: b.run_dir / "run.json"),
            ("summary.json", lambda b: b.run_dir / "summary.json"),
            ("task.json", lambda b: b.task_dir / "task.json"),
            ("result.json", lambda b: b.task_dir / "result.json"),
        )
        for label, locate in documents:
            for suffix in ("", "\n", "\r\n"):
                with self.subTest(document=label, valid_suffix=repr(suffix)), tempfile.TemporaryDirectory() as tmp:
                    bundle = _Bundle(Path(tmp))
                    path = locate(bundle)
                    raw = path.read_text(encoding="utf-8").rstrip("\n")
                    path.write_text(raw + suffix, encoding="utf-8")
                    eligibility = bundle.evaluate()
                    self.assertEqual(eligibility.integrity_status, "valid")
                    self.assertTrue(eligibility.acceptance_eligible)

            invalid = (
                ("empty", lambda raw: ""),
                ("blank", lambda raw: "\n"),
                ("vertical-tab", lambda raw: raw + "\v"),
                ("form-feed", lambda raw: raw + "\f"),
                ("record-separator", lambda raw: raw + "\x1e"),
                ("next-line", lambda raw: raw + "\u0085"),
                ("line-separator", lambda raw: raw + "\u2028"),
                ("paragraph-separator", lambda raw: raw + "\u2029"),
            )
            for framing, mutate in invalid:
                with self.subTest(document=label, invalid_framing=framing), tempfile.TemporaryDirectory() as tmp:
                    bundle = _Bundle(Path(tmp))
                    path = locate(bundle)
                    raw = path.read_text(encoding="utf-8").rstrip("\n")
                    path.write_text(mutate(raw), encoding="utf-8")
                    eligibility = bundle.evaluate()
                    self.assertEqual(eligibility.integrity_status, "invalid")

    def test_admissions_use_strict_json_and_exact_record_framing(self) -> None:
        duplicate_fields = (
            ("verifier_id", '"verifier-v1"'),
            ("task_id", '"task-a"'),
            ("verifier_checksum", '"checksum-v1"'),
            ("admitted", "true"),
        )
        for key, raw_value in duplicate_fields:
            with self.subTest(duplicate=key), tempfile.TemporaryDirectory() as tmp:
                bundle = _Bundle(Path(tmp))
                bundle.admissions.write_text(
                    _prepend_json_member(
                        bundle.admissions.read_text(encoding="utf-8"),
                        key,
                        raw_value,
                    ),
                    encoding="utf-8",
                )
                eligibility = bundle.evaluate()
                self.assertEqual(eligibility.integrity_status, "invalid")
                self.assertIn("duplicate object key", " ".join(eligibility.integrity_errors))

        for label, raw_value in (
            ("nan", "NaN"),
            ("positive infinity", "Infinity"),
            ("negative infinity", "-Infinity"),
            ("positive overflow", "1e400"),
            ("negative overflow", "-1e400"),
            ("nested overflow", '{"nested":[1e400]}'),
        ):
            with self.subTest(numeric=label), tempfile.TemporaryDirectory() as tmp:
                bundle = _Bundle(Path(tmp))
                bundle.admissions.write_text(
                    _prepend_json_member(
                        bundle.admissions.read_text(encoding="utf-8"),
                        "strict_probe",
                        raw_value,
                    ),
                    encoding="utf-8",
                )
                eligibility = bundle.evaluate()
                self.assertEqual(eligibility.integrity_status, "invalid")
                self.assertRegex(
                    " ".join(eligibility.integrity_errors),
                    r"non-JSON numeric constant|non-finite JSON number",
                )

        for delimiter in ("", "\n", "\r\n"):
            with self.subTest(valid_delimiter=repr(delimiter)), tempfile.TemporaryDirectory() as tmp:
                bundle = _Bundle(Path(tmp))
                record = bundle.admissions.read_text(encoding="utf-8").rstrip("\n")
                bundle.admissions.write_text(record + delimiter, encoding="utf-8")
                eligibility = bundle.evaluate()
                self.assertEqual(eligibility.integrity_status, "valid")
                self.assertTrue(eligibility.acceptance_eligible)

        invalid = (
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
        for label, mutate in invalid:
            with self.subTest(invalid_framing=label), tempfile.TemporaryDirectory() as tmp:
                bundle = _Bundle(Path(tmp))
                record = bundle.admissions.read_text(encoding="utf-8").rstrip("\n")
                bundle.admissions.write_text(mutate(record), encoding="utf-8")
                eligibility = bundle.evaluate()
                self.assertEqual(eligibility.integrity_status, "invalid")

    def test_exact_scheduled_task_manifest_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle = _Bundle(Path(tmp))
            run_record = json.loads((bundle.run_dir / "run.json").read_text())
            run_record["task_count"] = 2
            run_record["task_ids"].append("task-b")
            run_record["task_manifest"].append(
                {"task_id": "task-b", "source": "other-source"}
            )
            run_record["suite"]["task_count_requested"] = 2
            (bundle.run_dir / "run.json").write_text(json.dumps(run_record) + "\n")
            eligibility = bundle.evaluate()
            self.assertEqual(eligibility.integrity_status, "invalid")
            self.assertIn("count", " ".join(eligibility.integrity_errors))

        with tempfile.TemporaryDirectory() as tmp:
            bundle = _Bundle(Path(tmp))
            (bundle.run_dir / "tasks" / "unexpected").mkdir()
            eligibility = bundle.evaluate()
            self.assertEqual(eligibility.integrity_status, "invalid")
            self.assertIn("unexpected", " ".join(eligibility.integrity_errors))

        with tempfile.TemporaryDirectory() as tmp:
            bundle = _Bundle(Path(tmp))
            task_b = bundle.add_task_b()
            rows = [bundle.run.results["task-b"], bundle.run.results["task-a"]]
            (bundle.run_dir / "results.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
            )
            eligibility = assess(
                run=bundle.run,
                run_dir=bundle.run_dir,
                adapter_config={
                    "verifier_id": "verifier-v1",
                    "verifier_checksum": "checksum-v1",
                },
                task_records={"task-a": bundle.task_record, "task-b": task_b},
                admissions_path=bundle.admissions,
                quarantine_path=bundle.quarantine,
            )
            self.assertEqual(eligibility.integrity_status, "invalid")
            self.assertIn("order", " ".join(eligibility.integrity_errors))

        for location in ("run", "suite", "summary"):
            with self.subTest(boolean_count=location), tempfile.TemporaryDirectory() as tmp:
                bundle = _Bundle(Path(tmp))
                if location == "summary":
                    record_path = bundle.run_dir / "summary.json"
                    record = json.loads(record_path.read_text())
                    record["task_count"] = True
                else:
                    record_path = bundle.run_dir / "run.json"
                    record = json.loads(record_path.read_text())
                    if location == "run":
                        record["task_count"] = True
                    else:
                        record["suite"]["task_count_requested"] = True
                record_path.write_text(json.dumps(record) + "\n")
                eligibility = bundle.evaluate()
                self.assertEqual(eligibility.integrity_status, "invalid")
                self.assertIn("integer", " ".join(eligibility.integrity_errors))

    def test_task_metadata_source_and_verifier_are_bound(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle = _Bundle(Path(tmp))
            bundle.result["source"] = "forged-source"
            bundle._write_result()
            eligibility = bundle.evaluate()
            self.assertEqual(eligibility.integrity_status, "invalid")
            self.assertIn("source", " ".join(eligibility.integrity_errors))

        for field, forged in (("id", "forged-verifier"), ("checksum", "forged-checksum")):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                bundle = _Bundle(Path(tmp))
                bundle.result["verifier"][field] = forged
                bundle._write_result()
                eligibility = bundle.evaluate()
                self.assertEqual(eligibility.integrity_status, "invalid")
                self.assertIn("verifier", " ".join(eligibility.integrity_errors))

        with tempfile.TemporaryDirectory() as tmp:
            bundle = _Bundle(Path(tmp))
            task = json.loads((bundle.task_dir / "task.json").read_text())
            task["verification"]["verifier_checksum"] = "forged-checksum"
            (bundle.task_dir / "task.json").write_text(json.dumps(task) + "\n")
            eligibility = bundle.evaluate()
            self.assertEqual(eligibility.integrity_status, "invalid")
            self.assertIn("verifier metadata", " ".join(eligibility.integrity_errors))

        for field in ("verifier_id", "verifier_checksum"):
            with self.subTest(terminal_field=field), tempfile.TemporaryDirectory() as tmp:
                bundle = _Bundle(Path(tmp))
                events = json.loads(json.dumps(bundle.events))
                events[-1]["payload"][field] = "forged"
                bundle.rewrite_trace(events)
                eligibility = bundle.evaluate()
                self.assertEqual(eligibility.integrity_status, "invalid")
                self.assertIn("terminal verifier", " ".join(eligibility.integrity_errors))

    def test_terminal_verifier_result_is_unique_and_final(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle = _Bundle(Path(tmp))
            events = json.loads(json.dumps(bundle.events))
            events.append(_event(6, "verifier_result", {"status": "passed"}, actor="verifier"))
            bundle.rewrite_trace(events)
            eligibility = bundle.evaluate()
            self.assertEqual(eligibility.integrity_status, "invalid")
            self.assertIn("exactly one", " ".join(eligibility.integrity_errors))

        with tempfile.TemporaryDirectory() as tmp:
            bundle = _Bundle(Path(tmp))
            events = json.loads(json.dumps(bundle.events))
            events.append(_event(6, "browser_state", {"done": True}))
            bundle.rewrite_trace(events)
            eligibility = bundle.evaluate()
            self.assertEqual(eligibility.integrity_status, "invalid")
            self.assertIn("final", " ".join(eligibility.integrity_errors))

        with tempfile.TemporaryDirectory() as tmp:
            bundle = _Bundle(Path(tmp))
            events = json.loads(json.dumps(bundle.events))
            events.insert(-1, _event(5, "action_result", {"outcome": "ok"}))
            _resequence(events)
            bundle.rewrite_trace(events)
            eligibility = bundle.evaluate()
            self.assertEqual(eligibility.integrity_status, "invalid")
            self.assertIn("immediately precede", " ".join(eligibility.integrity_errors))

    def test_aggregate_and_local_results_use_type_strict_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle = _Bundle(Path(tmp))
            local = json.loads((bundle.task_dir / "result.json").read_text())
            local["reward"] = True
            (bundle.task_dir / "result.json").write_text(json.dumps(local) + "\n")
            eligibility = bundle.evaluate()
            self.assertEqual(eligibility.integrity_status, "invalid")
            self.assertIn("reward", " ".join(eligibility.integrity_errors))

        with tempfile.TemporaryDirectory() as tmp:
            bundle = _Bundle(Path(tmp))
            aggregate = json.loads(json.dumps(bundle.result))
            aggregate["reward"] = True
            (bundle.run_dir / "results.jsonl").write_text(json.dumps(aggregate) + "\n")
            eligibility = bundle.evaluate()
            self.assertEqual(eligibility.integrity_status, "invalid")
            self.assertIn("reward", " ".join(eligibility.integrity_errors))

    def test_artifact_refs_are_filtered_by_the_caller_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle = _Bundle(Path(tmp))
            executor_file = bundle.task_dir / "executor.txt"
            executor_file.write_text("executor-only", encoding="utf-8")
            executor_ref = _ref(executor_file, bundle.task_dir, "executor", "text/plain")
            executor_ref["visibility"] = ["executor"]
            bundle.result["artifacts"].append(executor_ref)
            events = json.loads(json.dumps(bundle.events))
            events[0]["artifact_refs"].append(executor_ref)
            bundle.rewrite_trace(events)
            loaded = evidence.load_task_bundle(
                task_root=bundle.task_dir,
                expected_run_id="run-1",
                expected_task_id="task-a",
                expected_source="test-source",
                expected_status="passed",
                expected_result=bundle.result,
                expected_verifier_id="verifier-v1",
                expected_verifier_checksum="checksum-v1",
                contract=evidence.EvidenceContract(role="judge-only", visibility=("judge",)),
            )
            self.assertNotIn("executor.txt", {ref["uri"] for ref in loaded.result["artifacts"]})
            self.assertNotIn(
                "executor.txt",
                {
                    ref["uri"]
                    for event in loaded.trace.events
                    for ref in event["artifact_refs"]
                },
            )

    def test_unrelated_pending_quarantine_does_not_mask_new_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle = _Bundle(Path(tmp))
            queue = QuarantineQueue(bundle.quarantine)
            queue.enqueue(
                task_id="task-a",
                run_ref="old-run/task-a/trace.jsonl",
                verifier_status="passed",
                reason="old unrelated flag",
                flags=[
                    {
                        "check": "old-check",
                        "direction": "fp_suspect",
                        "severity": "suspicion",
                        "detail": "old",
                        "evidence": [],
                    }
                ],
            )
            events = json.loads(json.dumps(bundle.events))
            events.insert(-2, _event(4, "network_event", {"method": "DELETE", "url": "/x"}))
            _resequence(events)
            bundle.rewrite_trace(events)
            eligibility = bundle.evaluate()
            self.assertEqual(eligibility.integrity_status, "valid")
            self.assertEqual(eligibility.newly_quarantined, ["task-a"])
            self.assertEqual(len(queue.pending()), 2)

    def test_old_run_pending_quarantine_does_not_block_clean_repaired_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle = _Bundle(Path(tmp))
            queue = QuarantineQueue(bundle.quarantine)
            queue.enqueue(
                task_id="task-a",
                run_ref="old-run/task-a/trace.jsonl",
                verifier_status="passed",
                reason="old run remains under review",
                flags=[
                    {
                        "check": "old-check",
                        "direction": "fp_suspect",
                        "severity": "suspicion",
                        "detail": "old evidence only",
                        "evidence": [],
                    }
                ],
            )
            eligibility = bundle.evaluate()
            self.assertEqual(eligibility.integrity_status, "valid")
            self.assertTrue(eligibility.acceptance_eligible)
            self.assertEqual(eligibility.quarantined_tasks, [])

    def test_gate_does_not_reintroduce_task_only_quarantine(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = _Bundle(root)
            treatment_dir = root / "dev_treatment"
            bundle.run_dir.rename(treatment_dir)
            bundle.run_dir = treatment_dir
            bundle.task_dir = treatment_dir / "tasks" / "task-a"
            bundle.trace_path = bundle.task_dir / "trace.jsonl"
            bundle.screenshot = bundle.task_dir / "final.png"
            bundle.run.output_dir = treatment_dir
            QuarantineQueue(bundle.quarantine).enqueue(
                task_id="task-a",
                run_ref="old-run/task-a/trace.jsonl",
                verifier_status="passed",
                reason="old run remains under review",
                flags=[
                    {
                        "check": "old-check",
                        "direction": "fp_suspect",
                        "severity": "suspicion",
                        "detail": "old evidence only",
                        "evidence": [],
                    }
                ],
            )
            diagnostic = EvalRun(
                output_dir=root,
                suite_name="diagnostic",
                summary={
                    "run_valid": True,
                    "acceptance_decision_eligible": False,
                    "strict_success_rate": 1.0,
                },
                statuses={"task-a": "passed"},
                rewards={"task-a": 1.0},
            )
            runs = iter([diagnostic, diagnostic, bundle.run])
            comparison = SimpleNamespace(eligible=True, to_dict=lambda: {})
            with (
                mock.patch(
                    "opti_loop.gates.fileguard.check_candidate",
                    return_value=SimpleNamespace(
                        ok=True, changed=[], to_dict=lambda: {}
                    ),
                ),
                mock.patch(
                    "opti_loop.gates.lint.scan_tree",
                    return_value=SimpleNamespace(
                        ok=True, findings=[], scanned_files=1
                    ),
                ),
                mock.patch(
                    "opti_loop.gates.registration.check_change_registered",
                    return_value=SimpleNamespace(ok=True, errors=[], warnings=[]),
                ),
                mock.patch(
                    "opti_loop.gates.run_suite", side_effect=lambda **_: next(runs)
                ),
                mock.patch(
                    "opti_loop.gates.compare_runs", return_value=comparison
                ) as compare,
            ):
                report = run_gate(
                    repo_root=root,
                    worktree=root,
                    base_sha="base",
                    candidate_sha="candidate",
                    iteration=1,
                    eval_root=root,
                    baseline_dev=diagnostic,
                    manifest={
                        "target_component": "policy",
                        "predicted_improvements": [
                            {"failure_class": "x", "tasks": ["not-in-catalog"]}
                        ],
                        "regression_risks": [],
                    },
                    manifest_report=SimpleNamespace(
                        ok=True, errors=[], warnings=[]
                    ),
                    adapter_config={
                        "verifier_id": "verifier-v1",
                        "verifier_checksum": "checksum-v1",
                    },
                    suites={
                        "smoke": "smoke",
                        "dev": "dev",
                        "regression": "regression",
                    },
                    thresholds={"smoke_min_pass_rate": 0.5},
                    noise_band=None,
                    run_identity="identity",
                    task_sources={"task-a": "test-source"},
                    task_records={"task-a": bundle.task_record},
                    regression_last_results={},
                    admissions_path=bundle.admissions,
                    quarantine_path=bundle.quarantine,
                )
            self.assertTrue(report.eligibility["acceptance_eligible"])
            self.assertEqual(compare.call_args.kwargs["quarantined"], set())
            self.assertEqual(
                report.rungs[-1].detail["reason"], "noise band unmeasured"
            )

    def test_same_run_pending_quarantine_blocks_clean_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle = _Bundle(Path(tmp))
            queue = QuarantineQueue(bundle.quarantine)
            queue.enqueue(
                task_id="task-a",
                run_ref="run-1/task-a/trace.jsonl",
                verifier_status="passed",
                reason="exact run remains under review",
                flags=[
                    {
                        "check": "exact-check",
                        "direction": "fp_suspect",
                        "severity": "suspicion",
                        "detail": "same evidence",
                        "evidence": [],
                    }
                ],
            )
            eligibility = bundle.evaluate()
            self.assertEqual(eligibility.integrity_status, "valid")
            self.assertFalse(eligibility.acceptance_eligible)
            self.assertEqual(eligibility.quarantined_tasks, ["task-a"])

    def test_unrelated_malformed_quarantine_state_fails_globally(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle = _Bundle(Path(tmp))
            bundle.quarantine.write_text(
                '{"task_id":"unrelated","status":"pending"}\n',
                encoding="utf-8",
            )
            eligibility = bundle.evaluate()
            self.assertEqual(eligibility.integrity_status, "invalid")
            self.assertFalse(eligibility.acceptance_eligible)
            self.assertIn(
                "quarantine state is unavailable",
                " ".join(eligibility.integrity_errors),
            )

    def test_resolution_semantics_block_only_the_exact_adverse_run(self) -> None:
        cases = (
            ("true_success", "passed", True),
            ("true_failure", "failed", True),
            ("verifier_defect", "passed", False),
            ("task_defect", "passed", False),
            ("undecidable", "passed", False),
        )
        for resolution, status, clears_same_run in cases:
            with self.subTest(resolution=resolution), tempfile.TemporaryDirectory() as tmp:
                bundle = _Bundle(Path(tmp))
                if status == "failed":
                    bundle.set_verifier_status("failed")
                    bundle.task_record["judge_expectations"] = {
                        "state_assertions": [
                            {"path": "done", "op": "equals", "value": False}
                        ]
                    }
                    clean_events = json.loads(json.dumps(bundle.events))
                else:
                    clean_events = json.loads(json.dumps(bundle.events))
                    events = json.loads(json.dumps(bundle.events))
                    events.insert(
                        -2,
                        _event(4, "network_event", {"method": "DELETE", "url": "/x"}),
                    )
                    _resequence(events)
                    bundle.rewrite_trace(events)

                initial = bundle.evaluate()
                self.assertEqual(initial.integrity_status, "valid")
                self.assertFalse(initial.acceptance_eligible)
                queue = QuarantineQueue(bundle.quarantine)
                entry = queue.pending()[0]
                queue.resolve(entry.entry_id, resolution=resolution, note="reviewed")

                same_run = bundle.evaluate()
                self.assertEqual(same_run.integrity_status, "valid")
                self.assertEqual(same_run.acceptance_eligible, clears_same_run)
                self.assertEqual(
                    queue.run_is_blocked(
                        task_id="task-a", run_ref="run-1/task-a/trace.jsonl"
                    ),
                    not clears_same_run,
                )

                bundle.task_record.pop("judge_expectations", None)
                bundle.rewrite_trace(clean_events)
                if resolution == "verifier_defect":
                    bundle.rebind_repaired_run(
                        "run-2",
                        verifier_id="verifier-v2",
                        verifier_checksum="checksum-v2",
                    )
                else:
                    bundle.rebind_repaired_run("run-2")
                repaired = bundle.evaluate()
                self.assertEqual(repaired.integrity_status, "valid")
                self.assertTrue(repaired.acceptance_eligible)

    def test_malformed_t1_expectations_are_integrity_invalid(self) -> None:
        mutations = (
            lambda task: task.update(state_change_expected="false"),
            lambda task: task.update(
                judge_expectations={"side_effect_expectation": False}
            ),
            lambda task: task.update(
                judge_expectations={
                    "state_assertions": [{"path": "done", "op": "equals"}]
                }
            ),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate), tempfile.TemporaryDirectory() as tmp:
                bundle = _Bundle(Path(tmp))
                mutate(bundle.task_record)
                eligibility = bundle.evaluate()
                self.assertEqual(eligibility.integrity_status, "invalid")
                self.assertIn("T1 execution failed", " ".join(eligibility.integrity_errors))

    def test_t1_assertions_use_json_type_strict_equality_and_contains(self) -> None:
        cases = (
            ("equals", True, 1, False),
            ("equals", 1, 1, True),
            ("contains", [True], 1, False),
            ("contains", [1], 1, True),
        )
        for op, actual, expected, acceptance_eligible in cases:
            with self.subTest(op=op, actual=actual), tempfile.TemporaryDirectory() as tmp:
                bundle = _Bundle(Path(tmp))
                events = json.loads(json.dumps(bundle.events))
                events[-2]["payload"]["actual"] = actual
                bundle.rewrite_trace(events)
                bundle.task_record["judge_expectations"] = {
                    "state_assertions": [
                        {"path": "actual", "op": op, "value": expected}
                    ]
                }
                eligibility = bundle.evaluate()
                self.assertEqual(eligibility.integrity_status, "valid")
                self.assertEqual(
                    eligibility.acceptance_eligible, acceptance_eligible
                )

    def test_shared_event_and_trace_corpus_matches_runtime(self) -> None:
        contract = evidence.EvidenceContract(role="corpus", visibility=("judge",))
        for case in build_evidence_contract_corpus():
            if case["target"] == "event":
                with self.subTest(case=case["label"]):
                    if case["runtime_valid"]:
                        evidence._validate_event(json.loads(json.dumps(case["value"])), 1)
                    else:
                        with self.assertRaises(evidence.EvidenceError):
                            evidence._validate_event(json.loads(json.dumps(case["value"])), 1)
            elif case["target"] == "raw_event":
                with self.subTest(case=case["label"]):
                    with self.assertRaises(evidence.EvidenceError):
                        evidence._parse_trace_text(
                            case["value"], source=case["label"], contract=contract
                        )
            elif case["target"] == "raw_trace":
                with self.subTest(case=case["label"]), tempfile.TemporaryDirectory() as tmp:
                    bundle = _Bundle(Path(tmp))
                    bundle.rewrite_raw_trace(case["value"])
                    eligibility = bundle.evaluate()
                    self.assertEqual(
                        eligibility.integrity_status == "valid",
                        case["runtime_valid"],
                    )
            elif case["target"] == "trace":
                with self.subTest(case=case["label"]), tempfile.TemporaryDirectory() as tmp:
                    bundle = _Bundle(Path(tmp))
                    bundle.rewrite_trace(json.loads(json.dumps(case["value"])))
                    eligibility = bundle.evaluate()
                    self.assertEqual(
                        eligibility.integrity_status == "valid",
                        case["runtime_valid"],
                    )
            elif case["target"] == "assertion":
                with self.subTest(case=case["label"]):
                    task = {
                        "state_change_expected": False,
                        "judge_expectations": {"state_assertions": [case["value"]]},
                    }
                    if case["runtime_valid"]:
                        expectations_from_task(task)
                    else:
                        with self.assertRaises(ValueError):
                            expectations_from_task(task)

    def test_missing_and_malformed_trace_fail_integrity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle = _Bundle(Path(tmp))
            bundle.trace_path.unlink()
            eligibility = bundle.evaluate()
            self.assertEqual(eligibility.integrity_status, "invalid")
            self.assertIn("does not exist", " ".join(eligibility.integrity_errors))
        with tempfile.TemporaryDirectory() as tmp:
            bundle = _Bundle(Path(tmp))
            bundle.rewrite_raw_trace("{not json}\n")
            eligibility = bundle.evaluate()
            self.assertEqual(eligibility.integrity_status, "invalid")
            self.assertIn("not valid JSON", " ".join(eligibility.integrity_errors))

    def test_strict_event_schema_and_file_order_fail_closed(self) -> None:
        mutations = {
            "missing required field": lambda events: events[0].pop("timestamp"),
            "duplicate event id": lambda events: events[1].update(event_id=events[0]["event_id"]),
            "decreasing sequence": lambda events: events[1].update(sequence=0),
            "decreasing monotonic": lambda events: events[1].update(monotonic_ms=0.0),
            "mixed run": lambda events: events[1].update(run_id="spliced-run"),
            "mixed task": lambda events: events[1].update(task_id="spliced-task"),
            "future parent": lambda events: events[0].update(parent_event_id=events[2]["event_id"]),
            "invalid actor": lambda events: events[0].update(actor="candidate"),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                bundle = _Bundle(Path(tmp))
                events = json.loads(json.dumps(bundle.events))
                mutate(events)
                bundle.rewrite_trace(events)
                eligibility = bundle.evaluate()
                self.assertEqual(eligibility.integrity_status, "invalid")
                self.assertFalse(eligibility.acceptance_eligible)

    def test_result_and_terminal_identity_mismatches_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle = _Bundle(Path(tmp))
            bundle.result["run_id"] = "other-run"
            bundle._write_result()
            eligibility = bundle.evaluate()
            self.assertEqual(eligibility.integrity_status, "invalid")
            self.assertIn("run_id", " ".join(eligibility.integrity_errors))
        with tempfile.TemporaryDirectory() as tmp:
            bundle = _Bundle(Path(tmp))
            events = json.loads(json.dumps(bundle.events))
            events[-1]["payload"]["status"] = "failed"
            bundle.rewrite_trace(events)
            eligibility = bundle.evaluate()
            self.assertEqual(eligibility.integrity_status, "invalid")
            self.assertIn("terminal verifier", " ".join(eligibility.integrity_errors))
        with tempfile.TemporaryDirectory() as tmp:
            bundle = _Bundle(Path(tmp))
            events = json.loads(json.dumps(bundle.events))
            events[-1]["actor"] = "orchestrator"
            bundle.rewrite_trace(events)
            eligibility = bundle.evaluate()
            self.assertEqual(eligibility.integrity_status, "invalid")

    def test_unsafe_symlink_and_tampered_artifacts_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle = _Bundle(Path(tmp))
            bundle.result["artifacts"][0]["visibility"] = ["restricted"]
            bundle._write_result()
            eligibility = bundle.evaluate()
            self.assertEqual(eligibility.integrity_status, "invalid")
            self.assertIn("not visible", " ".join(eligibility.integrity_errors))
        with tempfile.TemporaryDirectory() as tmp:
            bundle = _Bundle(Path(tmp))
            bundle.result["artifacts"].append(
                {
                    "kind": "escape",
                    "uri": "../outside.txt",
                    "sha256": "0" * 64,
                    "media_type": "text/plain",
                    "visibility": ["judge"],
                }
            )
            bundle._write_result()
            eligibility = bundle.evaluate()
            self.assertEqual(eligibility.integrity_status, "invalid")
            self.assertIn("relative POSIX", " ".join(eligibility.integrity_errors))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = _Bundle(root)
            outside = root / "outside.txt"
            outside.write_text("outside", encoding="utf-8")
            link = bundle.task_dir / "linked.txt"
            os.symlink(outside, link)
            bundle.result["artifacts"].append(_ref(link, bundle.task_dir, "linked", "text/plain"))
            bundle._write_result()
            eligibility = bundle.evaluate()
            self.assertEqual(eligibility.integrity_status, "invalid")
            self.assertIn("symlink", " ".join(eligibility.integrity_errors))
        with tempfile.TemporaryDirectory() as tmp:
            bundle = _Bundle(Path(tmp))
            bundle.screenshot.write_bytes(b"tampered")
            eligibility = bundle.evaluate()
            self.assertEqual(eligibility.integrity_status, "invalid")
            self.assertIn("sha256 mismatch", " ".join(eligibility.integrity_errors))
        with tempfile.TemporaryDirectory() as tmp:
            bundle = _Bundle(Path(tmp))
            bundle.trace_path.write_text(bundle.trace_path.read_text() + "\n", encoding="utf-8")
            eligibility = bundle.evaluate()
            self.assertEqual(eligibility.integrity_status, "invalid")
            self.assertIn("sha256 mismatch", " ".join(eligibility.integrity_errors))

    def test_event_artifact_must_match_result_declaration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle = _Bundle(Path(tmp))
            events = json.loads(json.dumps(bundle.events))
            events[0]["artifact_refs"][0]["sha256"] = "f" * 64
            bundle.rewrite_trace(events)
            eligibility = bundle.evaluate()
            self.assertEqual(eligibility.integrity_status, "invalid")
            self.assertIn("does not match", " ".join(eligibility.integrity_errors))

    def test_missing_validator_and_t1_failure_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle = _Bundle(Path(tmp))
            real_import = __import__

            def blocked_import(name, *args, **kwargs):
                if name == "opti_judge.evidence":
                    raise ModuleNotFoundError("judge module unavailable")
                return real_import(name, *args, **kwargs)

            with mock.patch("builtins.__import__", side_effect=blocked_import):
                eligibility = bundle.evaluate()
            self.assertEqual(eligibility.integrity_status, "invalid")
            self.assertIn("unavailable", " ".join(eligibility.integrity_errors))
        with tempfile.TemporaryDirectory() as tmp:
            bundle = _Bundle(Path(tmp))
            with mock.patch("opti_judge.evidence.load_task_bundle", None):
                eligibility = bundle.evaluate()
            self.assertEqual(eligibility.integrity_status, "invalid")
            self.assertIn("unavailable", " ".join(eligibility.integrity_errors))
        with tempfile.TemporaryDirectory() as tmp:
            bundle = _Bundle(Path(tmp))
            with mock.patch(
                "opti_judge.t1_checks.run_all", side_effect=RuntimeError("T1 crashed")
            ):
                eligibility = bundle.evaluate()
            self.assertEqual(eligibility.integrity_status, "invalid")
            self.assertIn("T1 execution failed", " ".join(eligibility.integrity_errors))

    def test_every_t1_flag_is_quarantined_or_integrity_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle = _Bundle(Path(tmp))
            events = [_event(1, "browser_state", {"done": False})]
            for sequence in range(2, 6):
                events.append(
                    _event(sequence, "action_requested", {"action": "click", "target": "#same"})
                )
            events.extend(
                [
                    _event(6, "action_result", {"outcome": "ok"}),
                    _event(7, "browser_state", {"done": False}),
                    _event(8, "verifier_result", {"status": "passed"}, actor="verifier"),
                ]
            )
            bundle.rewrite_trace(events)
            eligibility = bundle.evaluate()
            self.assertEqual(eligibility.integrity_status, "invalid")
            self.assertIn("no quarantine disposition", " ".join(eligibility.integrity_errors))
        with tempfile.TemporaryDirectory() as tmp:
            bundle = _Bundle(Path(tmp))
            events = json.loads(json.dumps(bundle.events))
            events.insert(-2, _event(4, "network_event", {"method": "DELETE", "url": "/x"}))
            _resequence(events)
            bundle.rewrite_trace(events)
            eligibility = bundle.evaluate()
            self.assertEqual(eligibility.integrity_status, "valid")
            self.assertEqual(eligibility.evidence_class, "benchmark")
            self.assertFalse(eligibility.acceptance_eligible)
            self.assertEqual(eligibility.newly_quarantined, ["task-a"])

    def test_invalid_bundle_is_explicit_invalid_at_e5_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = _Bundle(root)
            bundle.trace_path.unlink()
            diagnostic = EvalRun(
                output_dir=root,
                suite_name="diagnostic",
                summary={"run_valid": True, "acceptance_decision_eligible": False,
                         "strict_success_rate": 1.0},
                statuses={"task-a": "passed"},
                rewards={"task-a": 1.0},
            )
            runs = iter([diagnostic, diagnostic, bundle.run])
            guard = SimpleNamespace(ok=True, changed=[], to_dict=lambda: {})
            lint_report = SimpleNamespace(ok=True, findings=[], scanned_files=1)
            registration = SimpleNamespace(ok=True, errors=[], warnings=[])
            manifest = {
                "target_component": "policy",
                "predicted_improvements": [
                    {"failure_class": "x", "tasks": ["not-in-catalog"]}
                ],
                "regression_risks": [],
            }
            with (
                mock.patch("opti_loop.gates.fileguard.check_candidate", return_value=guard),
                mock.patch("opti_loop.gates.lint.scan_tree", return_value=lint_report),
                mock.patch(
                    "opti_loop.gates.registration.check_change_registered",
                    return_value=registration,
                ),
                mock.patch("opti_loop.gates.run_suite", side_effect=lambda **_: next(runs)),
            ):
                report = run_gate(
                    repo_root=root,
                    worktree=root,
                    base_sha="base",
                    candidate_sha="candidate",
                    iteration=1,
                    eval_root=bundle.run_dir.parent,
                    baseline_dev=diagnostic,
                    manifest=manifest,
                    manifest_report=SimpleNamespace(ok=True, errors=[], warnings=[]),
                    adapter_config={
                        "verifier_id": "verifier-v1",
                        "verifier_checksum": "checksum-v1",
                    },
                    suites={"smoke": "smoke", "dev": "dev", "regression": "regression"},
                    thresholds={"smoke_min_pass_rate": 0.5},
                    noise_band=None,
                    run_identity="identity",
                    task_sources={"task-a": "test-source"},
                    task_records={"task-a": {"state_change_expected": False}},
                    regression_last_results={},
                    admissions_path=bundle.admissions,
                    quarantine_path=bundle.quarantine,
                )
            self.assertEqual(report.rungs[-1].rung, "E5")
            self.assertEqual(report.rungs[-1].status, "invalid")
            self.assertEqual(report.eligibility["integrity_status"], "invalid")
            self.assertEqual(report.verdict.decision, "invalid")
            self.assertFalse(report.verdict.advances_accepted_state)


class EvidenceSchemaAlignmentTest(unittest.TestCase):
    def test_contract_patterns_use_true_end_anchors(self) -> None:
        root = Path(os.environ["OPTI_BROWSER_REPO_ROOT"])
        paths = (
            root / "schemas/result.schema.json",
            root / "schemas/trace-event.schema.json",
            root / "evals/schemas/bridge-result.schema.json",
            root / "evals/schemas/normalized-task.schema.json",
            root / "evals/schemas/suite.schema.json",
        )

        def patterns(value: object):
            if isinstance(value, dict):
                for key, child in value.items():
                    if key == "pattern":
                        yield child
                    else:
                        yield from patterns(child)
            elif isinstance(value, list):
                for child in value:
                    yield from patterns(child)

        for path in paths:
            schema = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(
                schema["x-edge-whitespace-class"],
                EDGE_WHITESPACE_SCHEMA_CLASS,
            )
            for pattern in patterns(schema):
                with self.subTest(schema=path.name, pattern=pattern):
                    self.assertNotIn("$", pattern)
                    semantic = pattern.replace(r"[\s\S]", "")
                    self.assertNotIn(r"\s", semantic)
                    self.assertNotIn(r"\S", semantic)

    @unittest.skipUnless(shutil.which("node"), "Node is required for ECMA regex parity")
    def test_edge_whitespace_class_matches_node_ecma_regex(self) -> None:
        root = Path(os.environ["OPTI_BROWSER_REPO_ROOT"])
        result_schema = json.loads(
            (root / "schemas/result.schema.json").read_text(encoding="utf-8")
        )
        trace_schema = json.loads(
            (root / "schemas/trace-event.schema.json").read_text(encoding="utf-8")
        )
        bridge_schema = json.loads(
            (root / "evals/schemas/bridge-result.schema.json").read_text(
                encoding="utf-8"
            )
        )
        task_schema = json.loads(
            (root / "evals/schemas/normalized-task.schema.json").read_text(
                encoding="utf-8"
            )
        )
        suite_schema = json.loads(
            (root / "evals/schemas/suite.schema.json").read_text(encoding="utf-8")
        )
        patterns = (
            result_schema["$defs"]["nonempty_trimmed"]["pattern"],
            trace_schema["properties"]["run_id"]["pattern"],
            bridge_schema["$defs"]["nonempty_trimmed"]["pattern"],
            task_schema["$defs"]["nonempty_trimmed"]["pattern"],
            suite_schema["properties"]["id"]["pattern"],
        )
        edge_chars = sorted(EDGE_WHITESPACE_CHARS)
        candidates = (
            ["valid", "valid interior", "valid\ninterior"]
            + [char + "value" for char in edge_chars]
            + ["value" + char for char in edge_chars]
            + ["left" + char + "right" for char in edge_chars]
        )
        expected = [
            bool(value) and not has_edge_whitespace(value) for value in candidates
        ]
        script = (
            "const input=JSON.parse(process.argv[1]);"
            "const results=input.patterns.map(p=>{const r=new RegExp(p);"
            "return input.values.map(v=>r.test(v));});"
            "process.stdout.write(JSON.stringify(results));"
        )
        completed = subprocess.run(
            [
                "node",
                "-e",
                script,
                json.dumps({"patterns": patterns, "values": candidates}),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(json.loads(completed.stdout), [expected] * len(patterns))

    def test_runtime_and_json_schema_structures_match(self) -> None:
        root = Path(os.environ["OPTI_BROWSER_REPO_ROOT"])
        trace_schema = json.loads((root / "schemas/trace-event.schema.json").read_text())
        result_schema = json.loads((root / "schemas/result.schema.json").read_text())
        bridge_schema = json.loads(
            (root / "evals/schemas/bridge-result.schema.json").read_text()
        )
        self.assertEqual(set(trace_schema["required"]), evidence.REQUIRED_EVENT_FIELDS)
        self.assertEqual(
            set(trace_schema["properties"]) - evidence.REQUIRED_EVENT_FIELDS,
            evidence.OPTIONAL_EVENT_FIELDS,
        )
        self.assertEqual(
            set(trace_schema["properties"]["actor"]["enum"]), evidence.ALLOWED_ACTORS
        )
        self.assertEqual(
            set(trace_schema["properties"]["event_type"]["enum"]),
            evidence.ALLOWED_EVENT_TYPES,
        )
        epoch_rule = trace_schema["allOf"][1]
        self.assertEqual(
            set(epoch_rule["if"]["properties"]["event_type"]["enum"]),
            evidence.EPOCH_EVENT_TYPES,
        )
        trace_ref = trace_schema["properties"]["artifact_refs"]["items"]
        self.assertEqual(set(trace_ref["required"]), evidence.ARTIFACT_FIELDS)
        self.assertEqual(set(result_schema["required"]), evidence.RESULT_FIELDS)
        self.assertEqual(
            set(result_schema["$defs"]["artifact_ref"]["required"]),
            evidence.ARTIFACT_FIELDS,
        )
        self.assertEqual(
            set(bridge_schema["$defs"]["artifact_ref"]["required"]),
            evidence.ARTIFACT_FIELDS,
        )
        self.assertEqual(
            trace_schema["properties"]["monotonic_ms"]["maximum"],
            MAX_FINITE_REAL_MAGNITUDE,
        )
        self.assertEqual(
            result_schema["$defs"]["timing"]["properties"]["elapsed_seconds"][
                "maximum"
            ],
            MAX_FINITE_REAL_MAGNITUDE,
        )


if __name__ == "__main__":
    unittest.main()
