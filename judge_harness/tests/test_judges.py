"""Tests for the judge layer: evidence contracts, probe kit, T1, routing,
corpus trust gating, and the panel runner with the fixture provider."""
from __future__ import annotations

import dataclasses
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from opti_judge.corpus import CorpusStore, OperatingPoint, trusted
from opti_judge.evidence import (
    EPOCH_EVENT_TYPES,
    EvidenceContract,
    EvidenceError,
    Trace,
    load_trace,
)
from opti_judge.panel import Judgment, adjudicate, run_role
from opti_judge.probekit import ProbeCase, run_probe_kit
from opti_judge.quarantine import QuarantineQueue
from opti_judge.router import route
from opti_judge.t1_checks import run_all

REPO_ROOT = Path(os.environ["OPTI_BROWSER_REPO_ROOT"])


def _event(seq: int, event_type: str, payload: dict, *, visibility=None, epoch=None) -> dict:
    if event_type == "verifier_result":
        payload = {
            "status": "passed",
            "verifier_id": "verifier-test",
            "verifier_checksum": "checksum-test",
            **payload,
        }
    return {
        "schema_version": "0.1-draft",
        "run_id": "run-t",
        "task_id": "task-t",
        "event_id": f"evt-{seq:04d}",
        "sequence": seq,
        "timestamp": f"2026-07-14T00:00:{seq:02d}+00:00",
        "monotonic_ms": float(seq),
        "actor": "verifier" if event_type == "verifier_result" else "browser",
        "event_type": event_type,
        "visibility": visibility or ["judge", "orchestrator"],
        "payload": payload,
        "artifact_refs": [],
        **(
            {
                "browser_state_epoch": (
                    0 if epoch is None and event_type in EPOCH_EVENT_TYPES else epoch
                )
            }
            if epoch is not None or event_type in EPOCH_EVENT_TYPES
            else {}
        ),
    }


def _write_trace(path: Path, events: list[dict]) -> None:
    path.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")


CONTRACT = EvidenceContract(role="test", visibility=("executor", "judge", "orchestrator"))


class EvidenceTest(unittest.TestCase):
    def test_restricted_material_is_never_loadable(self) -> None:  # F13
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.jsonl"
            _write_trace(
                path,
                [
                    _event(1, "browser_state", {"ok": 1}),
                    _event(2, "verifier_result", {"secret": 1}, visibility=["restricted"]),
                    _event(3, "browser_state", {"x": 2}, visibility=["judge", "restricted"]),
                ],
            )
            trace = load_trace(path, CONTRACT)
            ids = [e["event_id"] for e in trace.events]
            # The mixed-tag event evt-0003 is now DROPPED entirely, not admitted.
            self.assertEqual(ids, ["evt-0001"])
        with self.assertRaises(EvidenceError):
            EvidenceContract(role="bad", visibility=("restricted",))

    def test_restricted_artifact_ref_is_redacted(self) -> None:  # F13
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.jsonl"
            ev = _event(1, "browser_state", {"ok": 1})
            ev["artifact_refs"] = [
                {"kind": "screenshot", "uri": "ok.png", "sha256": "0" * 64,
                 "media_type": "image/png", "visibility": ["judge"]},
                {"kind": "holdout", "uri": "secret.png", "sha256": "1" * 64,
                 "media_type": "image/png", "visibility": ["restricted"]},
            ]
            _write_trace(path, [ev])
            trace = load_trace(path, CONTRACT)
            refs = trace.events[0]["artifact_refs"]
            self.assertEqual([r["kind"] for r in refs], ["screenshot"])

    def test_malformed_trace_raises_evidence_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.jsonl"
            path.write_text("{not json}\n", encoding="utf-8")
            with self.assertRaises(EvidenceError):
                load_trace(path, CONTRACT)
            path.write_text(json.dumps({"event_id": "x"}) + "\n", encoding="utf-8")
            with self.assertRaises(EvidenceError):
                load_trace(path, CONTRACT)


GOOD_VERIFIER = r'''
import json, sys
args = dict(zip(sys.argv[1::2], sys.argv[2::2]))
out = {"status": "error"}
try:
    lines = open(args["--trace"]).read().splitlines()
    first = json.loads(lines[0])
    out = dict(first["payload"]["truth"])
except Exception:
    out = {"status": "invalid"}
json.dump(out, open(args["--result"], "w"))
'''

BROKEN_VERIFIER = r'''
import json, sys
args = dict(zip(sys.argv[1::2], sys.argv[2::2]))
json.dump({"status": "passed", "reward": 1.0}, open(args["--result"], "w"))
'''


class ProbeKitTest(unittest.TestCase):
    def _build_kit(self, tmp: Path) -> list[ProbeCase]:
        cases = []
        truths = {
            "oracle": {"status": "passed", "reward": 1.0},
            "near_miss": {"status": "failed", "reward": 0.0},
            "premature_stop": {"status": "failed", "reward": 0.0},
            # deliberately unreported by the verifier → the kit must detect it
            # via the T1 side-effect monitor over the probe trace
            "harmful_extra_action": {"status": "passed", "reward": 1.0},
            "stale_or_fabricated": {"status": "invalid"},
        }
        for kind, truth in truths.items():
            events = [_event(1, "checkpoint", {"truth": truth})]
            if kind == "harmful_extra_action":
                events.append(
                    _event(2, "network_event", {"method": "DELETE", "url": "/x"})
                )
            trace = tmp / f"{kind}.trace.jsonl"
            _write_trace(trace, events)
            task = tmp / f"{kind}.task.json"
            task.write_text("{}")
            cases.append(ProbeCase(kind=kind, trace_path=trace, task_path=task))
        malformed = tmp / "malformed.trace.jsonl"
        malformed.write_text("this is not a trace at all {{{", encoding="utf-8")
        task = tmp / "malformed.task.json"
        task.write_text("{}")
        cases.append(ProbeCase(kind="malformed", trace_path=malformed, task_path=task))
        return cases

    def test_good_verifier_is_admitted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_s:
            tmp = Path(tmp_s)
            script = tmp / "verifier.py"
            script.write_text(GOOD_VERIFIER)
            record = run_probe_kit(
                verifier_id="good-v1",
                verifier_command=f"{sys.executable} {script} --trace {{trace_json}} --result {{result_json}}",
                task_id="task-x",
                cases=self._build_kit(tmp),
                checksum_files=[script],
                archive_dir=tmp / "archive",
            )
            self.assertTrue(
                record.admitted,
                [dataclasses.asdict(o) for o in record.outcomes if not o.ok],
            )
            self.assertIsNotNone(record.verifier_checksum)
            self.assertTrue(list((tmp / "archive").glob("admission-*.json")))

    def test_probe_trace_rejects_oversized_monotonic_without_overflow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_s:
            tmp = Path(tmp_s)
            script = tmp / "verifier.py"
            script.write_text(GOOD_VERIFIER)
            cases = self._build_kit(tmp)
            harmful = next(case for case in cases if case.kind == "harmful_extra_action")
            events = [
                json.loads(line)
                for line in harmful.trace_path.read_text(encoding="utf-8").splitlines()
            ]
            events[0]["monotonic_ms"] = 10**4000
            events[1]["monotonic_ms"] = 10**4000 + 1
            _write_trace(harmful.trace_path, events)

            record = run_probe_kit(
                verifier_id="good-huge-clock-v1",
                verifier_command=(
                    f"{sys.executable} {script} --trace {{trace_json}} "
                    "--result {result_json}"
                ),
                task_id="task-x",
                cases=cases,
                checksum_files=[script],
            )
            self.assertFalse(record.admitted)
            outcome = next(
                outcome
                for outcome in record.outcomes
                if outcome.kind == "harmful_extra_action"
            )
            self.assertFalse(outcome.ok)
            self.assertIn("monotonic_ms", outcome.observed["t1_error"])

    def test_always_pass_verifier_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_s:
            tmp = Path(tmp_s)
            script = tmp / "verifier.py"
            script.write_text(BROKEN_VERIFIER)
            record = run_probe_kit(
                verifier_id="broken-v1",
                verifier_command=f"{sys.executable} {script} --trace {{trace_json}} --result {{result_json}}",
                task_id="task-x",
                cases=self._build_kit(tmp),
            )
            self.assertFalse(record.admitted)
            failed_kinds = {o.kind for o in record.outcomes if not o.ok}
            # passes oracle (and harmful via T1 fallback), but must flunk
            # near-miss, premature-stop, stale, and malformed-never-failed
            self.assertIn("near_miss", failed_kinds)
            self.assertIn("malformed", failed_kinds)

    def test_incomplete_kit_never_admits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_s:
            tmp = Path(tmp_s)
            script = tmp / "verifier.py"
            script.write_text(GOOD_VERIFIER)
            cases = self._build_kit(tmp)[:3]
            record = run_probe_kit(
                verifier_id="good-v1",
                verifier_command=f"{sys.executable} {script} --trace {{trace_json}} --result {{result_json}}",
                task_id="task-x",
                cases=cases,
            )
            self.assertFalse(record.admitted)


FILENAME_KEYED_VERIFIER = r'''
import json, sys
args = dict(zip(sys.argv[1::2], sys.argv[2::2]))
# A verifier that tries to cheat by keying on the probe KIND in the filename.
name = args["--trace"]
status = "passed" if "oracle" in name or "near_miss" in name else "failed"
json.dump({"status": status}, open(args["--result"], "w"))
'''


class ProbeBlindingChecksumTest(unittest.TestCase):
    def _kit(self, tmp: Path):
        cases = []
        truths = {"oracle": {"status": "passed", "reward": 1.0},
                  "near_miss": {"status": "failed", "reward": 0.0},
                  "premature_stop": {"status": "failed", "reward": 0.0},
                  "harmful_extra_action": {"status": "passed", "reward": 1.0},
                  "stale_or_fabricated": {"status": "invalid"}}
        for kind, truth in truths.items():
            events = [_event(1, "checkpoint", {"truth": truth})]
            if kind == "harmful_extra_action":
                events.append(_event(2, "network_event", {"method": "DELETE", "url": "/x"}))
            tp = tmp / f"{kind}.trace.jsonl"; _write_trace(tp, events)
            (tmp / f"{kind}.task.json").write_text("{}")
            cases.append(ProbeCase(kind=kind, trace_path=tp, task_path=tmp / f"{kind}.task.json"))
        mal = tmp / "malformed.trace.jsonl"; mal.write_text("not a trace {{{")
        (tmp / "malformed.task.json").write_text("{}")
        cases.append(ProbeCase(kind="malformed", trace_path=mal, task_path=tmp / "malformed.task.json"))
        return cases

    def test_missing_checksum_blocks_admission(self) -> None:  # F11
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            script = tmp / "v.py"; script.write_text(GOOD_VERIFIER)
            rec = run_probe_kit(verifier_id="v", task_id="x",
                                verifier_command=f"{sys.executable} {script} --trace {{trace_json}} --result {{result_json}}",
                                cases=self._kit(tmp))  # no checksum_files
            self.assertFalse(rec.admitted)
            self.assertTrue(any(o.kind == "checksum" for o in rec.outcomes))

    def test_blinding_defeats_filename_keyed_verifier(self) -> None:  # F11
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            script = tmp / "v.py"; script.write_text(FILENAME_KEYED_VERIFIER)
            rec = run_probe_kit(verifier_id="v", task_id="x",
                                verifier_command=f"{sys.executable} {script} --trace {{trace_json}} --result {{result_json}}",
                                cases=self._kit(tmp), checksum_files=[script])
            # Randomized probe filenames mean the verifier can't recognize kinds.
            self.assertFalse(rec.admitted)


class CorpusDedupeTest(unittest.TestCase):
    def test_duplicate_cases_do_not_inflate_trust(self) -> None:  # F12
        from opti_judge.corpus import CorpusStore, OperatingPoint, trusted
        with tempfile.TemporaryDirectory() as t:
            corpus = CorpusStore(Path(t) / "c.jsonl")
            for _ in range(25):  # same task+run, 25 attempts
                case = corpus.add_case(source="manual", task_id="t", run_ref="r", ground_truth="failure")
                corpus.record_judge_output(case["case_id"], "j", "failure")
            m = corpus.measure("j", positive="failure")
            self.assertEqual(m["cases_measured"], 1)  # deduped
            self.assertFalse(trusted(m, OperatingPoint(min_cases=10, min_distinct_tasks=5)))


class T1ChecksTest(unittest.TestCase):
    def test_each_check_fires(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_s:
            tmp = Path(tmp_s)
            events = [
                _event(1, "browser_state", {"form": {"saved": False}}, epoch=0),
                _event(2, "network_event", {"method": "POST", "url": "/mutate"}),
                _event(3, "browser_state", {"form": {"saved": False}}, epoch=2),
                _event(4, "action_result", {"outcome": "ok"}, epoch=2),
            ]
            for i in range(4):  # loop: same action 4x
                events.append(
                    _event(
                        5 + i,
                        "action_requested",
                        {"action": "click", "target": "#btn"},
                        epoch=2,
                    )
                )
            path = tmp / "t.jsonl"
            _write_trace(path, events)
            trace = load_trace(path, CONTRACT)
            flags = run_all(
                trace,
                verifier_status="passed",
                side_effect_expectation="none",
                assertions=[{"path": "form.saved", "op": "equals", "value": True}],
            )
            checks = {f.check for f in flags}
            self.assertIn("side_effect_monitor", checks)
            self.assertIn("loop_detector", checks)
            self.assertIn("expected_state", checks)  # passed but assertion violated
            directions = {f.direction for f in flags}
            self.assertIn("fp_suspect", directions)
            self.assertIn("side_effect", directions)

            stale = Trace(
                events=[
                    _event(1, "browser_state", {"form": {}}, epoch=0),
                    _event(2, "browser_state", {"form": {}}, epoch=2),
                    _event(3, "action_result", {"outcome": "ok"}, epoch=0),
                ]
            )
            self.assertIn(
                "stale_epoch",
                {f.check for f in run_all(stale, verifier_status="passed")},
            )

    def test_zero_action_pass_and_fn_direction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_s:
            tmp = Path(tmp_s)
            path = tmp / "t.jsonl"
            _write_trace(
                path, [_event(1, "browser_state", {"cart": {"count": 3}}, epoch=0)]
            )
            trace = load_trace(path, CONTRACT)
            flags = run_all(trace, verifier_status="passed")
            self.assertIn("zero_action_pass", {f.check for f in flags})
            # FN direction: verifier failed although the asserted state holds
            flags = run_all(
                trace,
                verifier_status="failed",
                assertions=[{"path": "cart.count", "op": "equals", "value": 3}],
            )
            self.assertIn("fn_suspect", {f.direction for f in flags})

    def test_clean_trace_raises_no_suspicion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_s:
            tmp = Path(tmp_s)
            path = tmp / "t.jsonl"
            _write_trace(
                path,
                [
                    _event(1, "browser_state", {"done": True}, epoch=0),
                    _event(2, "action_requested", {"action": "click", "target": "#a"}),
                    _event(3, "action_result", {"outcome": "ok"}, epoch=0),
                ],
            )
            trace = load_trace(path, CONTRACT)
            flags = run_all(trace, verifier_status="passed", side_effect_expectation="none")
            self.assertEqual([f for f in flags if f.severity == "suspicion"], [])


class RoutingAndQuarantineTest(unittest.TestCase):
    def test_fp_and_fn_routing_and_resolution_feeds_corpus(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_s:
            tmp = Path(tmp_s)
            queue = QuarantineQueue(tmp / "queue.jsonl")
            corpus = CorpusStore(tmp / "corpus.jsonl")

            trace_path = tmp / "t.jsonl"
            _write_trace(trace_path, [_event(1, "browser_state", {"x": 1}, epoch=0)])
            trace = load_trace(trace_path, CONTRACT)

            # FP route: passed with zero actions
            flags = run_all(trace, verifier_status="passed")
            routed = route(
                queue=queue,
                task_id="task-fp",
                run_ref="run-1",
                verifier_status="passed",
                t1_flags=flags,
            )
            self.assertTrue(routed["routed"])

            # FN route: failed although asserted state holds
            flags = run_all(
                trace,
                verifier_status="failed",
                assertions=[{"path": "x", "op": "equals", "value": 1}],
            )
            routed = route(
                queue=queue,
                task_id="task-fn",
                run_ref="run-2",
                verifier_status="failed",
                t1_flags=flags,
            )
            self.assertTrue(routed["routed"])
            self.assertIn("false negative", routed["reason"])

            self.assertEqual(queue.pending_task_ids(), {"task-fp", "task-fn"})

            # Resolve the FN as a verifier defect → corpus gains a 'success' label
            fn_entry = next(e for e in queue.pending() if e.task_id == "task-fn")
            queue.resolve(
                fn_entry.entry_id,
                resolution="verifier_defect",
                note="verifier missed dynamic cart total",
                corpus=corpus,
            )
            stats = corpus.stats()
            self.assertEqual(stats["cases"], 1)
            self.assertEqual(stats["by_ground_truth"], {"success": 1})
            with self.assertRaises(ValueError):
                queue.resolve("nonexistent" * 2, resolution="override_score", note="")

    def test_clean_run_is_not_routed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_s:
            tmp = Path(tmp_s)
            queue = QuarantineQueue(tmp / "queue.jsonl")
            routed = route(
                queue=queue,
                task_id="task-ok",
                run_ref="run-3",
                verifier_status="passed",
                t1_flags=[],
            )
            self.assertFalse(routed["routed"])
            self.assertEqual(queue.pending(), [])

    def test_exact_run_task_flag_fingerprint_dedupes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_s:
            tmp = Path(tmp_s)
            queue = QuarantineQueue(tmp / "queue.jsonl")
            trace_path = tmp / "t.jsonl"
            _write_trace(trace_path, [_event(1, "browser_state", {"x": 1}, epoch=0)])
            flags = run_all(load_trace(trace_path, CONTRACT), verifier_status="passed")

            first = route(
                queue=queue,
                task_id="task-fp",
                run_ref="run-1/task-fp/trace.jsonl",
                verifier_status="passed",
                t1_flags=flags + flags,
            )
            duplicate = route(
                queue=queue,
                task_id="task-fp",
                run_ref="run-1/task-fp/trace.jsonl",
                verifier_status="passed",
                t1_flags=flags,
            )
            self.assertTrue(first["routed"])
            self.assertTrue(duplicate["deduplicated"])
            self.assertEqual(len(queue.pending()), 1)
            self.assertEqual(len(queue.pending()[0].flags), len(flags))

            different_run = route(
                queue=queue,
                task_id="task-fp",
                run_ref="run-2/task-fp/trace.jsonl",
                verifier_status="passed",
                t1_flags=flags,
            )
            self.assertFalse(different_run["deduplicated"])
            self.assertEqual(len(queue.pending()), 2)

    def test_repeated_trusted_judgment_uses_same_disposition(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_s:
            queue = QuarantineQueue(Path(tmp_s) / "queue.jsonl")
            judgment = Judgment(
                role_id="completion_cross_examiner",
                role_version="1",
                opinion="failure",
                confidence=0.9,
                rationale="final state contradicts the goal",
                evidence_refs=["run-1/event-1"],
                labels={},
                model={"provider": "fixture"},
                trusted=True,
                calibration={"cases": 25},
            )
            first = route(
                queue=queue,
                task_id="task-fp",
                run_ref="run-1/task-fp/trace.jsonl",
                verifier_status="passed",
                t1_flags=[],
                judgments=[judgment],
            )
            duplicate = route(
                queue=queue,
                task_id="task-fp",
                run_ref="run-1/task-fp/trace.jsonl",
                verifier_status="passed",
                t1_flags=[],
                judgments=[judgment],
            )
            self.assertTrue(first["routed"])
            self.assertTrue(duplicate["deduplicated"])
            self.assertEqual(len(queue.pending()), 1)

    def test_resolution_must_match_the_terminal_verifier_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_s:
            queue = QuarantineQueue(Path(tmp_s) / "queue.jsonl")
            passed = queue.enqueue(
                task_id="task-passed",
                run_ref="run-1/task-passed/trace.jsonl",
                verifier_status="passed",
                reason="possible false positive",
            )
            failed = queue.enqueue(
                task_id="task-failed",
                run_ref="run-1/task-failed/trace.jsonl",
                verifier_status="failed",
                reason="possible false negative",
            )
            with self.assertRaisesRegex(ValueError, "true_failure"):
                queue.resolve(
                    passed.entry_id, resolution="true_failure", note="mismatch"
                )
            with self.assertRaisesRegex(ValueError, "true_success"):
                queue.resolve(
                    failed.entry_id, resolution="true_success", note="mismatch"
                )
            self.assertEqual(len(queue.pending()), 2)


class CorpusTrustTest(unittest.TestCase):
    def test_trust_requires_cases_and_operating_point(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_s:
            corpus = CorpusStore(Path(tmp_s) / "c.jsonl")
            # 10 cases: judge perfectly matches ground truth
            for i in range(10):
                truth = "failure" if i % 2 else "success"
                case = corpus.add_case(
                    source="manual", task_id=f"t-{i}", run_ref=f"r-{i}", ground_truth=truth
                )
                corpus.record_judge_output(case["case_id"], "completion_cross_examiner", truth)
            measurement = corpus.measure("completion_cross_examiner", positive="failure")
            self.assertEqual(measurement["precision"], 1.0)
            self.assertEqual(measurement["recall"], 1.0)
            # perfect but too few cases → still untrusted
            self.assertFalse(trusted(measurement, OperatingPoint(min_cases=25, min_recall=0.8)))
            self.assertTrue(trusted(measurement, OperatingPoint(min_cases=10, min_recall=0.8)))


class PanelTest(unittest.TestCase):
    def test_fixture_role_run_is_untrusted_and_adjudication_quarantines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_s:
            tmp = Path(tmp_s)
            trace_path = tmp / "t.jsonl"
            _write_trace(
                trace_path,
                [
                    _event(1, "browser_state", {"cart": {"count": 0}}, epoch=0),
                    _event(2, "action_requested", {"action": "click", "target": "#buy"}),
                ],
            )
            judgment = run_role(
                repo_root=REPO_ROOT,
                role_id="completion_cross_examiner",
                trace_path=trace_path,
                goal="add 3 items to the cart",
                verifier_status="passed",
                model_override={
                    "provider": "fixture",
                    "responses": {
                        "default": json.dumps(
                            {
                                "opinion": "failure",
                                "confidence": 0.9,
                                "key_points": ["3 items in cart"],
                                "unmet_points": ["cart shows 0"],
                                "rationale": "final state contradicts the goal",
                            }
                        )
                    },
                },
            )
            self.assertEqual(judgment.opinion, "failure")
            self.assertFalse(judgment.trusted)  # no corpus measurement yet
            self.assertEqual(judgment.model["provider"], "fixture")

            verdict = adjudicate(
                verifier_status="passed", judgments=[judgment], t1_flags=[]
            )
            # untrusted disagreement still raises quarantine (weaker evidence
            # never suppresses doubt), and never touches a score
            self.assertEqual(verdict["resolution"], "quarantine")

            agree = adjudicate(verifier_status="failed", judgments=[judgment], t1_flags=[])
            self.assertEqual(agree["resolution"], "agree")

    def test_all_five_role_definitions_load(self) -> None:
        from opti_judge.panel import load_role

        for role_id in (
            "completion_cross_examiner",
            "side_effect_safety_judge",
            "root_cause_analyst",
            "implementation_activation_auditor",
            "adjudicator",
        ):
            role = load_role(REPO_ROOT, role_id)
            self.assertEqual(role["role_id"], role_id)
            self.assertNotIn(
                "restricted", role.get("evidence_contract", {}).get("visibility", [])
            )


class LoopIntegrationTest(unittest.TestCase):
    def test_quarantine_fails_strict_comparison_closed(self) -> None:
        from opti_loop.compare import compare_runs
        from opti_loop.evaluate import EvalRun

        def run(statuses: dict[str, str]) -> EvalRun:
            return EvalRun(
                output_dir=Path("."),
                suite_name="t",
                summary={
                    "run_valid": True,
                    "acceptance_decision_eligible": True,
                    "strict_success_rate": 0.5,
                },
                statuses=statuses,
                rewards={},
            )

        base = run({"a": "passed", "b": "failed"})
        treat = run({"a": "passed", "b": "passed"})

        strict = compare_runs(base, treat, policy="strict", quarantined={"b"})
        self.assertFalse(strict.eligible)
        self.assertIn("quarantine pending", strict.reasons[0])

        quorum = compare_runs(
            base, treat, policy="quorum", quorum_coverage_floor=0.5, quarantined={"b"}
        )
        self.assertTrue(quorum.eligible)
        self.assertNotIn("b", quorum.fixed)


if __name__ == "__main__":
    unittest.main()


class TaskExpectationTest(unittest.TestCase):
    def test_mapping_defaults_and_override(self) -> None:
        from opti_judge.t1_checks import expectations_from_task

        self.assertEqual(expectations_from_task({"state_change_expected": True}), ("some", []))
        self.assertEqual(expectations_from_task({"state_change_expected": False}), ("none", []))
        with self.assertRaisesRegex(ValueError, "state_change_expected"):
            expectations_from_task({})
        exp, asserts = expectations_from_task(
            {
                "state_change_expected": True,
                "judge_expectations": {
                    "side_effect_expectation": "none",
                    "state_assertions": [{"path": "cart.count", "op": "equals", "value": 3}],
                },
            }
        )
        self.assertEqual(exp, "none")  # explicit judge_expectations wins
        self.assertEqual(asserts[0]["path"], "cart.count")

        with self.assertRaisesRegex(ValueError, "side_effect_expectation"):
            expectations_from_task(
                {
                    "state_change_expected": False,
                    "judge_expectations": {"side_effect_expectation": False},
                }
            )

        malformed = (
            {"state_change_expected": 1},
            {"state_change_expected": False, "judge_expectations": []},
            {
                "state_change_expected": False,
                "judge_expectations": {"unsupported": True},
            },
            {
                "state_change_expected": False,
                "judge_expectations": {"state_assertions": {}},
            },
            {
                "state_change_expected": False,
                "judge_expectations": {
                    "state_assertions": [
                        {"path": "cart..count", "op": "equals", "value": 1}
                    ]
                },
            },
            {
                "state_change_expected": False,
                "judge_expectations": {
                    "state_assertions": [
                        {"path": "cart.count", "op": "exists", "value": True}
                    ]
                },
            },
            {
                "state_change_expected": False,
                "judge_expectations": {
                    "state_assertions": [
                        {"path": "cart.count", "op": "equals", "value": float("nan")}
                    ]
                },
            },
        )
        for task in malformed:
            with self.subTest(task=task), self.assertRaises(ValueError):
                expectations_from_task(task)
