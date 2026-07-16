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

import opti_eval
import opti_judge
import opti_loop
from opti_loop.compare import NoiseBand, NoiseBandError, measure_noise_band
from opti_loop.conductor import (
    _load_accepted_run,
    _revalidate_noise_band_for_decision,
)
from opti_loop.evaluate import EvalRun
from opti_loop.eligibility import assess
from opti_loop.gates import run_gate
from opti_loop.protocol import ProtocolError, freeze_protocol, verify_runtime_bindings
from opti_eval.identity import (
    code_component_identity,
    digest_json,
    expected_live_run_receipt,
    finalize_protocol_snapshot,
    make_run_context,
    simulated_protocol,
)
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


def _admitted_gate_result() -> SimpleNamespace:
    return SimpleNamespace(
        evidence_class="benchmark",
        acceptance_eligible=True,
        integrity_status="valid",
        reasons=[],
        integrity_errors=[],
        quarantined_tasks=[],
        admission_receipt={"receipt_digest": "a" * 64},
        to_dict=lambda: {
            "evidence_class": "benchmark",
            "acceptance_eligible": True,
            "integrity_status": "valid",
            "admission_receipt": {"receipt_digest": "a" * 64},
        },
    )


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


def _benchmark_identity(
    tasks: list[dict],
    *,
    run_id: str,
    admissions_path: Path,
    verifier_id: str = "verifier-v1",
    verifier_checksum: str = "checksum-v1",
    purpose: str = "iteration",
    arm: str = "treatment",
    repeat_index: int = 0,
    repeat_count: int = 1,
) -> tuple[dict, dict, dict]:
    protocol = simulated_protocol(
        suite={"id": "test", "kind": "test"},
        tasks=tasks,
        adapter={"name": "test", "benchmark_reportable": True},
    )

    def pin(value):
        if isinstance(value, str) and value.startswith("simulated:"):
            return "fixture-pinned:" + hashlib.sha256(value.encode()).hexdigest()[:16]
        if isinstance(value, list):
            return [pin(item) for item in value]
        if isinstance(value, dict):
            return {key: pin(item) for key, item in value.items()}
        return value

    protocol = pin(protocol)
    protocol["evidence_mode"] = "benchmark"
    protocol["purpose"] = purpose
    protocol["suites"][0]["role"] = "dev"
    dev_suite = protocol["suites"][0]
    protocol["suites"] = [
        dev_suite,
        {**json.loads(json.dumps(dev_suite)), "role": "smoke", "id": "test-smoke"},
        {
            **json.loads(json.dumps(dev_suite)),
            "role": "regression",
            "id": "test-regression",
        },
    ]
    protocol["execution"]["suites"] = {
        "dev": "test",
        "smoke": "test-smoke",
        "regression": "test-regression",
    }
    components = [
        code_component_identity(
            package=package,
            version=module.__version__,
            package_root=Path(module.__file__).resolve().parent,
        )
        for package, module in (
            ("opti_eval", opti_eval),
            ("opti_loop", opti_loop),
            ("opti_judge", opti_judge),
        )
    ]
    protocol["evaluator"] = {
        "components": components,
        "apparatus_digest": digest_json(
            components,
            domain="opti.trusted-code-apparatus.v1",
        ),
    }
    protocol["verifier_bundle"] = {
        "id": verifier_id,
        "checksum": verifier_checksum,
        "bundle_digest": hashlib.sha256(verifier_checksum.encode()).hexdigest(),
        "admissions_digest": hashlib.sha256(
            b"opti.admissions.v1\0" + admissions_path.read_bytes()
        ).hexdigest(),
    }
    protocol["accepted_build"] = {
        "role": "accepted",
        "commit_sha": "a" * 40,
        "tree_sha": "b" * 40,
        "materialized_digest": hashlib.sha256(b"accepted-build").hexdigest(),
        "immutable": True,
    }
    protocol["execution"]["accepted_protection"].update(
        champion_sha="a" * 40,
    )
    protocol["repeated_protocol"]["repeats"]["count"] = repeat_count
    protocol["repeated_protocol"]["stopping"]["valid_after"] = repeat_count
    protocol["repeated_protocol"]["limits"]["max_runs"] = max(
        repeat_count * 2,
        protocol["repeated_protocol"]["limits"]["max_runs"],
    )
    protocol.pop("calibration_binding_digest", None)
    protocol.pop("comparison_apparatus_digest", None)
    protocol.pop("protocol_digest", None)
    protocol = finalize_protocol_snapshot(protocol)
    candidate = {
        "role": "candidate",
        "commit_sha": "c" * 40,
        "tree_sha": "d" * 40,
        "materialized_digest": hashlib.sha256(b"candidate-build").hexdigest(),
        "immutable": True,
    }
    context = make_run_context(
        protocol,
        protocol["accepted_build"] if arm == "baseline" else candidate,
        arm=arm,
        suite_role="dev",
        task_ids=[task["id"] for task in tasks],
        repeat_index=repeat_index,
        seed=0,
        run_id=run_id,
    )
    return protocol, context, candidate


class _Bundle:
    def __init__(
        self,
        root: Path,
        *,
        run_id: str = "run-1",
        run_dir_name: str = "run",
        purpose: str = "iteration",
        arm: str = "treatment",
        repeat_index: int = 0,
        repeat_count: int = 1,
    ) -> None:
        self.run_id = run_id
        self.purpose = purpose
        self.arm = arm
        self.repeat_index = repeat_index
        self.repeat_count = repeat_count
        self.verifier_id = "verifier-v1"
        self.verifier_checksum = "checksum-v1"
        self.run_dir = root / run_dir_name
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
            _event(1, "browser_state", {"done": False}, run_id=self.run_id, refs=[screenshot_ref]),
            _event(2, "action_requested", {"action": "click", "target": "#save"}, run_id=self.run_id),
            _event(3, "action_result", {"outcome": "ok"}, run_id=self.run_id),
            _event(4, "browser_state", {"done": False}, run_id=self.run_id),
            _event(5, "verifier_result", {"status": "passed"}, actor="verifier", run_id=self.run_id),
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
        self.protocol, self.context, self.candidate_build = _benchmark_identity(
            [self.task_record],
            run_id=self.run_id,
            admissions_path=self.admissions,
            verifier_id=self.verifier_id,
            verifier_checksum=self.verifier_checksum,
            purpose=self.purpose,
            arm=self.arm,
            repeat_index=self.repeat_index,
            repeat_count=self.repeat_count,
        )
        self.result["metadata"]["run_context_digest"] = self.context["run_digest"]
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
            live_receipt=expected_live_run_receipt(
                self.protocol,
                run_digest=self.context["run_digest"],
            ),
            task_ids=["task-a"],
            task_sources={"task-a": "test-source"},
            protocol_digest=self.protocol["protocol_digest"],
            run_context_digest=self.context["run_digest"],
            run_context=self.context,
            protocol_snapshot=self.protocol,
            task_records={"task-a": self.task_record},
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

    def refreeze_admissions(self) -> None:
        """Bind the current raw admissions bytes so parser tests reach parsing."""
        self._write_result()

    def _write_result(self) -> None:
        self.run.results["task-a"] = self.result
        self.protocol, self.context, self.candidate_build = _benchmark_identity(
            [self.run.task_records[task_id] for task_id in self.run.task_ids],
            run_id=self.run_id,
            admissions_path=self.admissions,
            verifier_id=self.verifier_id,
            verifier_checksum=self.verifier_checksum,
            purpose=self.purpose,
            arm=self.arm,
            repeat_index=self.repeat_index,
            repeat_count=self.repeat_count,
        )
        self.run.protocol_snapshot = self.protocol
        self.run.protocol_digest = self.protocol["protocol_digest"]
        self.run.run_context = self.context
        self.run.run_context_digest = self.context["run_digest"]
        self.run.live_receipt = expected_live_run_receipt(
            self.protocol,
            run_digest=self.context["run_digest"],
        )
        for task_id in self.run.task_ids:
            row = self.run.results[task_id]
            row["metadata"]["run_context_digest"] = self.context["run_digest"]
            (self.run_dir / "tasks" / task_id / "task.json").write_text(
                json.dumps(self.run.task_records[task_id], sort_keys=True) + "\n",
                encoding="utf-8",
            )
            (self.run_dir / "tasks" / task_id / "result.json").write_text(
                json.dumps(row, sort_keys=True) + "\n", encoding="utf-8"
            )
        (self.run_dir / "results.jsonl").write_text(
            "".join(
                json.dumps(self.run.results[task_id], sort_keys=True) + "\n"
                for task_id in self.run.task_ids
            ),
            encoding="utf-8",
        )
        (self.run_dir / "summary.json").write_text(
            json.dumps(
                {
                    "schema_version": "0.1.0",
                    "run_id": self.run_id,
                    "suite_id": "test",
                    "task_count": len(self.run.task_ids),
                    "run_valid": True,
                    "benchmark_reportable": True,
                    "acceptance_decision_eligible": True,
                    "protocol_digest": self.protocol["protocol_digest"],
                    "run_context_digest": self.context["run_digest"],
                    "adapter_digest": self.protocol["adapter"]["digest"],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (self.run_dir / "run.json").write_text(
            json.dumps(
                {
                    "schema_version": "0.2.0",
                    "run_id": self.run_id,
                    "status": "completed",
                    "suite": {
                        "id": "test",
                        "kind": "test",
                        "task_count_requested": len(self.run.task_ids),
                    },
                    "task_count": len(self.run.task_ids),
                    "task_ids": self.run.task_ids,
                    "task_manifest": [
                        {"task_id": task_id, "source": self.run.task_sources[task_id]}
                        for task_id in self.run.task_ids
                    ],
                    "verifier": {
                        "id": self.verifier_id,
                        "checksum": self.verifier_checksum,
                    },
                    "adapter": self.protocol["adapter"],
                    "protocol": self.protocol,
                    "run_context": self.context,
                    "run_context_digest": self.context["run_digest"],
                }
            )
            + "\n",
            encoding="utf-8",
        )

    def evaluate(self):
        return assess(
            run=self.run,
            run_dir=self.run_dir,
            expected_receipt=self.run.live_receipt,
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
        self.protocol, self.context, self.candidate_build = _benchmark_identity(
            [self.task_record],
            run_id=self.run_id,
            admissions_path=self.admissions,
            verifier_id=self.verifier_id,
            verifier_checksum=self.verifier_checksum,
            purpose=self.purpose,
            arm=self.arm,
            repeat_index=self.repeat_index,
            repeat_count=self.repeat_count,
        )
        self.result["metadata"]["run_context_digest"] = self.context["run_digest"]
        self.run.run_context = self.context
        self.run.run_context_digest = self.context["run_digest"]
        self.run.protocol_snapshot = self.protocol
        self.run.protocol_digest = self.protocol["protocol_digest"]
        self.run.live_receipt = expected_live_run_receipt(
            self.protocol,
            run_digest=self.context["run_digest"],
        )
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
        self.run.task_records[task_id] = task_record
        self.protocol, self.context, self.candidate_build = _benchmark_identity(
            [self.task_record, task_record],
            run_id=self.run_id,
            admissions_path=self.admissions,
            verifier_id=self.verifier_id,
            verifier_checksum=self.verifier_checksum,
            purpose=self.purpose,
            arm=self.arm,
            repeat_index=self.repeat_index,
            repeat_count=self.repeat_count,
        )
        self.run.protocol_snapshot = self.protocol
        self.run.protocol_digest = self.protocol["protocol_digest"]
        self.run.run_context = self.context
        self.run.run_context_digest = self.context["run_digest"]
        self.result["metadata"]["run_context_digest"] = self.context["run_digest"]
        result["metadata"]["run_context_digest"] = self.context["run_digest"]
        self._write_result()
        return task_record


def _real_noise_revalidation_fixture(root: Path):
    samples = [
        _Bundle(
            root,
            run_id=f"noise-run-{index}",
            run_dir_name=f"noise/run-{index:02d}",
            purpose="noise-calibration",
            arm="baseline",
            repeat_index=index,
            repeat_count=2,
        )
        for index in range(2)
    ]
    if samples[0].protocol != samples[1].protocol:
        raise AssertionError("noise samples must share one frozen protocol")
    freeze_protocol(root / "noise", samples[0].protocol)
    for sample in samples:
        eligibility = sample.evaluate()
        if not eligibility.acceptance_eligible:
            raise AssertionError(eligibility.to_dict())
    band = measure_noise_band(
        [sample.run for sample in samples],
        synthetic=False,
        run_identity=samples[0].protocol["calibration_binding_digest"],
        evidence_root=root,
    )
    current_protocol = json.loads(json.dumps(samples[0].protocol))
    current_protocol["purpose"] = "iteration"
    current_protocol["iteration"] = 1
    current_protocol["repeated_protocol"]["repeats"]["count"] = 1
    current_protocol["repeated_protocol"]["stopping"]["valid_after"] = 1
    current_protocol["execution"]["noise_band"] = band.to_dict()
    for field in (
        "calibration_binding_digest",
        "comparison_apparatus_digest",
        "protocol_digest",
    ):
        current_protocol.pop(field)
    current_protocol = finalize_protocol_snapshot(current_protocol)
    if band.run_identity != current_protocol["calibration_binding_digest"]:
        raise AssertionError("iteration and calibration bindings must match")
    campaign = SimpleNamespace(
        store=SimpleNamespace(
            campaign_dir=root,
            admissions_path=samples[0].admissions,
            quarantine_path=samples[0].quarantine,
        )
    )
    return campaign, current_protocol, band, samples


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
            bundle.run.summary["benchmark_reportable"] = False
            bundle.run.summary["acceptance_decision_eligible"] = False
            eligibility = bundle.evaluate()
            self.assertEqual(eligibility.integrity_status, "valid")
            self.assertEqual(eligibility.evidence_class, "benchmark")
            self.assertTrue(eligibility.acceptance_eligible)
            self.assertEqual(eligibility.t1_flag_count, 0)
            self.assertIsNotNone(eligibility.admission_receipt)
            self.assertTrue(bundle.run.benchmark_admitted)

    def test_benchmark_result_marker_is_preliminary_but_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle = _Bundle(Path(tmp))
            bundle.result["metadata"].pop("benchmark_reportable")
            bundle._write_result()
            eligibility = bundle.evaluate()
            self.assertEqual(eligibility.integrity_status, "invalid")
            self.assertFalse(eligibility.acceptance_eligible)
            self.assertIn(
                "benchmark result marker is missing",
                " ".join(eligibility.integrity_errors),
            )

    def test_accepted_run_replays_ar003_and_requires_exact_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle = _Bundle(Path(tmp))
            admitted = bundle.evaluate()
            anchor = admitted.admission_receipt
            self.assertIsNotNone(anchor)
            campaign = SimpleNamespace(
                state={
                    "last_accepted_treatment_dir": str(bundle.run_dir),
                    "last_accepted_admission_receipt": anchor,
                },
                store=SimpleNamespace(
                    admissions_path=bundle.admissions,
                    quarantine_path=bundle.quarantine,
                ),
            )
            loaded = _load_accepted_run(campaign)
            self.assertIsNotNone(loaded)
            self.assertTrue(loaded.benchmark_admitted)

            campaign.state["last_accepted_admission_receipt"] = {
                **anchor,
                "receipt_digest": "0" * 64,
            }
            with self.assertRaisesRegex(RuntimeError, "anchor is missing or tampered"):
                _load_accepted_run(campaign)

            campaign.state["last_accepted_admission_receipt"] = anchor
            shutil.rmtree(bundle.run_dir)
            with self.assertRaisesRegex(RuntimeError, "evidence directory is missing"):
                _load_accepted_run(campaign)

    def test_real_noise_band_restart_reloads_every_exact_ar003_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            campaign, current_protocol, band, _ = _real_noise_revalidation_fixture(
                root
            )
            persisted_path = root / "noise-band.json"
            persisted_path.write_text(
                json.dumps(band.to_dict()) + "\n", encoding="utf-8"
            )
            for _ in range(2):
                reloaded = NoiseBand.from_dict(
                    json.loads(persisted_path.read_text(encoding="utf-8"))
                )
                self.assertFalse(reloaded.anchors_validated)
                _revalidate_noise_band_for_decision(
                    campaign, reloaded, current_protocol
                )
                self.assertTrue(reloaded.anchors_validated)

    def test_real_noise_band_rederives_every_persisted_authoritative_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            campaign, current_protocol, band, _ = _real_noise_revalidation_fixture(
                root
            )
            self.assertEqual(band.aggregate_margin, 0.0)
            self.assertEqual(band.max_benign_flips, 0)

            widened = band.to_dict()
            widened["aggregate_margin"] = 1.0
            widened["max_benign_flips"] = widened["task_count"]
            with self.assertRaisesRegex(
                NoiseBandError,
                "persisted noise-band authority does not match freshly measured samples",
            ):
                _revalidate_noise_band_for_decision(
                    campaign, NoiseBand.from_dict(widened), current_protocol
                )

            wrong_task_count = band.to_dict()
            wrong_task_count["task_count"] += 1
            with self.assertRaisesRegex(NoiseBandError, "sample count or task count"):
                _revalidate_noise_band_for_decision(
                    campaign,
                    NoiseBand.from_dict(wrong_task_count),
                    current_protocol,
                )

            reordered = band.to_dict()
            reordered["sample_anchors"].reverse()
            with self.assertRaisesRegex(NoiseBandError, "out of order"):
                _revalidate_noise_band_for_decision(
                    campaign, NoiseBand.from_dict(reordered), current_protocol
                )

    def test_real_noise_band_rejects_missing_and_tampered_sample_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            campaign, current_protocol, band, samples = (
                _real_noise_revalidation_fixture(root)
            )
            shutil.rmtree(samples[1].run_dir)
            with self.assertRaisesRegex(NoiseBandError, "directory is missing"):
                _revalidate_noise_band_for_decision(
                    campaign, NoiseBand.from_dict(band.to_dict()), current_protocol
                )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            campaign, current_protocol, band, samples = (
                _real_noise_revalidation_fixture(root)
            )
            samples[0].trace_path.write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(NoiseBandError, "invalid"):
                _revalidate_noise_band_for_decision(
                    campaign, NoiseBand.from_dict(band.to_dict()), current_protocol
                )

    def test_real_noise_band_rejects_stale_admissions_and_fabricated_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            campaign, current_protocol, band, samples = (
                _real_noise_revalidation_fixture(root)
            )
            samples[0].admissions.write_text(
                samples[0].admissions.read_text(encoding="utf-8")
                + samples[0].admissions.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(NoiseBandError, "apparatus drifted"):
                _revalidate_noise_band_for_decision(
                    campaign, NoiseBand.from_dict(band.to_dict()), current_protocol
                )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            campaign, current_protocol, band, _ = _real_noise_revalidation_fixture(
                root
            )
            payload = band.to_dict()
            receipt = payload["sample_anchors"][0]["admission_receipt"]
            receipt["task_bundle_digest"] = "f" * 64
            receipt["receipt_digest"] = digest_json(
                {
                    key: value
                    for key, value in receipt.items()
                    if key != "receipt_digest"
                },
                domain="opti.ar003-admission-receipt.v1",
            )
            fabricated = NoiseBand.from_dict(payload)
            with self.assertRaisesRegex(NoiseBandError, "anchor is missing or tampered"):
                _revalidate_noise_band_for_decision(
                    campaign, fabricated, current_protocol
                )

    def test_real_noise_band_rejects_wrong_path_symlink_and_protocol(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            campaign, current_protocol, band, _ = _real_noise_revalidation_fixture(
                root
            )
            drifted = json.loads(json.dumps(current_protocol))
            drifted["executor"]["revision"] = "fixture-pinned:changed"
            for field in (
                "calibration_binding_digest",
                "comparison_apparatus_digest",
                "protocol_digest",
            ):
                drifted.pop(field)
            drifted = finalize_protocol_snapshot(drifted)
            with self.assertRaisesRegex(NoiseBandError, "current iteration"):
                _revalidate_noise_band_for_decision(
                    campaign, NoiseBand.from_dict(band.to_dict()), drifted
                )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            campaign, current_protocol, band, _ = _real_noise_revalidation_fixture(
                root
            )
            payload = band.to_dict()
            payload["sample_anchors"][1]["evidence_dir"] = "noise/run-09"
            with self.assertRaisesRegex(NoiseBandError, "out of order"):
                _revalidate_noise_band_for_decision(
                    campaign, NoiseBand.from_dict(payload), current_protocol
                )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            campaign, current_protocol, band, samples = (
                _real_noise_revalidation_fixture(root)
            )
            moved = root / "noise/real-run-01"
            samples[1].run_dir.rename(moved)
            samples[1].run_dir.symlink_to(moved, target_is_directory=True)
            with self.assertRaisesRegex(NoiseBandError, "symlink"):
                _revalidate_noise_band_for_decision(
                    campaign, NoiseBand.from_dict(band.to_dict()), current_protocol
                )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            campaign, current_protocol, band, samples = (
                _real_noise_revalidation_fixture(root)
            )
            changed = json.loads(json.dumps(samples[0].protocol))
            changed["purpose"] = "not-noise-calibration"
            for field in (
                "calibration_binding_digest",
                "comparison_apparatus_digest",
                "protocol_digest",
            ):
                changed.pop(field)
            changed = finalize_protocol_snapshot(changed)
            (root / "noise/protocol.snapshot.json").write_text(
                json.dumps(changed) + "\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(NoiseBandError, "wrong purpose"):
                _revalidate_noise_band_for_decision(
                    campaign, NoiseBand.from_dict(band.to_dict()), current_protocol
                )

    def test_legacy_noise_band_cannot_override_e0(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            campaign, current_protocol, band, samples = (
                _real_noise_revalidation_fixture(root)
            )
            reloaded = NoiseBand.from_dict(band.to_dict())
            report = run_gate(
                repo_root=root,
                candidate_root=root,
                candidate_guard=SimpleNamespace(ok=True, changed=[], to_dict=lambda: {}),
                base_sha="a" * 40,
                iteration=1,
                eval_root=root / "gate",
                baseline_dev=samples[0].run,
                manifest={},
                manifest_report=SimpleNamespace(
                    ok=False, errors=["injected E0 failure"], warnings=[]
                ),
                adapter_config={},
                suites={},
                thresholds={},
                noise_band=reloaded,
                run_identity=current_protocol["calibration_binding_digest"],
                protocol_snapshot=current_protocol,
                task_sources={},
                task_records={},
                regression_baseline=samples[0].run,
                admissions_path=campaign.store.admissions_path,
                quarantine_path=campaign.store.quarantine_path,
                treatment_build=current_protocol["accepted_build"],
            )
            self.assertEqual(report.verdict.decision, "rejected")
            self.assertEqual((report.rungs[0].rung, report.rungs[0].status),
                             ("E0", "fail"))

    def test_gate_rejects_unadmitted_benchmark_baseline_before_decision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = _Bundle(root)
            unadmitted = EvalRun(
                output_dir=root,
                suite_name="benchmark-baseline",
                summary={"run_valid": True},
                statuses={"task-a": "passed"},
                rewards={"task-a": 1.0},
                live_receipt=expected_live_run_receipt(
                    bundle.protocol,
                    run_digest=bundle.context["run_digest"],
                ),
            )
            report = run_gate(
                repo_root=root,
                candidate_root=root,
                candidate_guard=SimpleNamespace(ok=True, changed=[], to_dict=lambda: {}),
                base_sha="base",
                iteration=1,
                eval_root=root,
                baseline_dev=unadmitted,
                manifest={},
                manifest_report=SimpleNamespace(ok=False, errors=[], warnings=[]),
                adapter_config={},
                suites={},
                thresholds={},
                noise_band=None,
                run_identity="identity",
                protocol_snapshot=bundle.protocol,
                task_sources={},
                task_records={},
                regression_baseline=unadmitted,
                admissions_path=bundle.admissions,
                quarantine_path=bundle.quarantine,
                treatment_build=bundle.candidate_build,
            )
            self.assertEqual(report.rungs[-1].rung, "E0")
            self.assertEqual(report.rungs[-1].status, "invalid")
            self.assertIn("lacks AR-003 admission", report.rungs[-1].detail["error"])

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
                bundle.refreeze_admissions()
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
                bundle.refreeze_admissions()
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
                bundle.refreeze_admissions()
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
                bundle.refreeze_admissions()
                eligibility = bundle.evaluate()
                self.assertEqual(eligibility.integrity_status, "invalid")

    def test_post_freeze_admissions_drift_is_integrity_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle = _Bundle(Path(tmp))
            bundle.admissions.write_text(
                bundle.admissions.read_text(encoding="utf-8") + "\n",
                encoding="utf-8",
            )
            eligibility = bundle.evaluate()
            self.assertEqual(eligibility.integrity_status, "invalid")
            self.assertIn("admissions drifted", " ".join(eligibility.integrity_errors))

    def test_post_freeze_trusted_code_drift_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle = _Bundle(Path(tmp))
            drifted = json.loads(
                json.dumps(bundle.protocol["evaluator"]["components"])
            )
            drifted[0]["code_digest"] = "0" * 64
            with (
                mock.patch(
                    "opti_loop.protocol._trusted_code_components",
                    return_value=drifted,
                ),
                self.assertRaisesRegex(ProtocolError, "code drifted"),
            ):
                verify_runtime_bindings(
                    bundle.protocol,
                    admissions_path=bundle.admissions,
                )

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
                expected_receipt=bundle.run.live_receipt,
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
            diagnostic.run_context = make_run_context(
                bundle.protocol,
                bundle.protocol["accepted_build"],
                arm="baseline",
                suite_role="dev",
                task_ids=["task-a"],
                repeat_index=0,
                seed=0,
            )
            runs = iter([diagnostic] * 6)
            comparison = SimpleNamespace(
                eligible=True,
                compared_task_count=1,
                baseline_success=0.0,
                treatment_success=1.0,
                fixed=["task-a"],
                regressed=[],
                to_dict=lambda: {},
            )
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
                    "opti_loop.gates.validate_harness_fixture_activation",
                    return_value=({}, []),
                ),
                mock.patch(
                    "opti_loop.gates.make_run_context",
                    return_value=bundle.context,
                ),
                mock.patch(
                    "opti_loop.gates.verify_runtime_bindings",
                ) as verify_runtime,
                mock.patch(
                    "opti_loop.repeated.compare_runs", return_value=comparison
                ) as compare,
                mock.patch("opti_loop.repeated.validate_paired_contexts"),
                mock.patch.object(
                    EvalRun,
                    "benchmark_admitted",
                    new_callable=mock.PropertyMock,
                    return_value=True,
                ),
                mock.patch(
                    "opti_loop.gates.assess",
                    side_effect=[_admitted_gate_result()] * 6,
                ),
            ):
                report = run_gate(
                    repo_root=root,
                    candidate_root=root,
                    candidate_guard=SimpleNamespace(ok=True, changed=[], to_dict=lambda: {}),
                    base_sha="base",
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
                        "kind": "harness-fixture",
                        "file": "harness/components/policy/quality.txt",
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
                    protocol_snapshot=bundle.protocol,
                    task_sources={"task-a": "test-source"},
                    task_records={"task-a": bundle.task_record},
                    regression_baseline=diagnostic,
                    admissions_path=bundle.admissions,
                    quarantine_path=bundle.quarantine,
                    treatment_build=bundle.candidate_build,
                )
            self.assertTrue(compare.called, report.to_dict())
            self.assertTrue(
                all(call.kwargs["quarantined"] == set() for call in compare.call_args_list)
            )
            self.assertIn("predicted flip", report.rungs[-1].detail["reason"])
            self.assertGreaterEqual(verify_runtime.call_count, 5)

    def test_gate_stops_when_runtime_binding_drifts_between_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = _Bundle(root)
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
                run_context=make_run_context(
                    bundle.protocol,
                    bundle.protocol["accepted_build"],
                    arm="baseline",
                    suite_role="dev",
                    task_ids=["task-a"],
                    repeat_index=0,
                    seed=0,
                ),
            )
            with (
                mock.patch(
                    "opti_loop.gates.fileguard.check_candidate",
                    return_value=SimpleNamespace(
                        ok=True,
                        changed=[],
                        to_dict=lambda: {},
                    ),
                ),
                mock.patch(
                    "opti_loop.gates.lint.scan_tree",
                    return_value=SimpleNamespace(
                        ok=True,
                        findings=[],
                        scanned_files=1,
                    ),
                ),
                mock.patch(
                    "opti_loop.gates.registration.check_change_registered",
                    return_value=SimpleNamespace(ok=True, errors=[], warnings=[]),
                ),
                mock.patch(
                    "opti_loop.gates.validate_harness_fixture_activation",
                    return_value=({}, []),
                ),
                mock.patch(
                    "opti_loop.gates.run_suite",
                    return_value=diagnostic,
                ) as run_suite_mock,
                mock.patch(
                    "opti_loop.gates.verify_runtime_bindings",
                    side_effect=[None, None, ProtocolError("trusted code changed")],
                ),
                mock.patch.object(
                    EvalRun,
                    "benchmark_admitted",
                    new_callable=mock.PropertyMock,
                    return_value=True,
                ),
                mock.patch(
                    "opti_loop.gates.assess",
                    return_value=_admitted_gate_result(),
                ),
            ):
                report = run_gate(
                    repo_root=root,
                    candidate_root=root,
                    candidate_guard=SimpleNamespace(ok=True, changed=[], to_dict=lambda: {}),
                    base_sha="base",
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
                        ok=True,
                        errors=[],
                        warnings=[],
                    ),
                    adapter_config={
                        "kind": "harness-fixture",
                        "file": "harness/components/policy/quality.txt",
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
                    protocol_snapshot=bundle.protocol,
                    task_sources={"task-a": "test-source"},
                    task_records={"task-a": bundle.task_record},
                    regression_baseline=diagnostic,
                    admissions_path=bundle.admissions,
                    quarantine_path=bundle.quarantine,
                    treatment_build=bundle.candidate_build,
                )
            self.assertEqual(run_suite_mock.call_count, 1)
            self.assertEqual(report.rungs[-1].rung, "E4")
            self.assertEqual(report.rungs[-1].status, "invalid")
            self.assertIn("trusted code changed", report.rungs[-1].detail["error"])

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
            diagnostic.run_context = make_run_context(
                bundle.protocol,
                bundle.protocol["accepted_build"],
                arm="baseline",
                suite_role="dev",
                task_ids=["task-a"],
                repeat_index=0,
                seed=0,
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
                mock.patch(
                    "opti_loop.gates.validate_harness_fixture_activation",
                    return_value=({}, []),
                ),
                mock.patch(
                    "opti_loop.gates.make_run_context",
                    return_value=bundle.context,
                ),
                mock.patch.object(
                    EvalRun,
                    "benchmark_admitted",
                    new_callable=mock.PropertyMock,
                    return_value=True,
                ),
                mock.patch(
                    "opti_loop.gates.assess",
                    side_effect=[
                        _admitted_gate_result(),
                        _admitted_gate_result(),
                        bundle.evaluate(),
                    ],
                ),
            ):
                report = run_gate(
                    repo_root=root,
                    candidate_root=root,
                    candidate_guard=guard,
                    base_sha="base",
                    iteration=1,
                    eval_root=bundle.run_dir.parent,
                    baseline_dev=diagnostic,
                    manifest=manifest,
                    manifest_report=SimpleNamespace(ok=True, errors=[], warnings=[]),
                    adapter_config={
                        "kind": "harness-fixture",
                        "file": "harness/components/policy/quality.txt",
                        "verifier_id": "verifier-v1",
                        "verifier_checksum": "checksum-v1",
                    },
                    suites={"smoke": "smoke", "dev": "dev", "regression": "regression"},
                    thresholds={"smoke_min_pass_rate": 0.5},
                    noise_band=None,
                    run_identity="identity",
                    protocol_snapshot=bundle.protocol,
                    task_sources={"task-a": "test-source"},
                    task_records={"task-a": {"state_change_expected": False}},
                    regression_baseline=diagnostic,
                    admissions_path=bundle.admissions,
                    quarantine_path=bundle.quarantine,
                    treatment_build=bundle.candidate_build,
                )
            self.assertEqual(report.rungs[-1].rung, "E5")
            self.assertEqual(report.rungs[-1].status, "invalid")
            self.assertIn(
                "trace",
                " ".join(
                    report.eligibility["repeated_protocol"]["integrity_errors"]
                ),
            )
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
