"""Deterministic offline simulations for the ADR-0018 repeated decision."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from opti_eval.identity import (
    IdentityError,
    digest_json,
    expected_live_run_receipt,
    finalize_protocol_snapshot,
    make_run_context,
    simulated_protocol,
)

from opti_loop.eligibility import Eligibility
from opti_loop.evaluate import EvalRun, reconstruct_warc_online4_activation
from opti_loop.compare import compare_runs
from opti_loop.repeated import ArmEvidence, execute_repeated_protocol
from opti_loop.verdict import Verdict


TASKS = [
    {"id": "task-a", "source": "source-a"},
    {"id": "task-b", "source": "source-a"},
]


def _protocol(
    *, repeats: int = 2, valid_after: int | None = None, max_runs: int = 4
) -> tuple[dict, dict]:
    protocol = simulated_protocol(
        suite={"id": "sim-suite"},
        tasks=TASKS,
        adapter={"name": "fixture", "benchmark_reportable": False},
    )
    dev = copy.deepcopy(protocol["suites"][0])
    dev["role"] = "dev"
    regression = copy.deepcopy(dev)
    regression["role"] = "regression"
    protocol["suites"] = [dev, regression]
    protocol["execution"]["suites"] = {
        "dev": "sim-suite",
        "regression": "sim-suite",
    }
    protocol["repeated_protocol"]["repeats"]["count"] = repeats
    protocol["repeated_protocol"]["stopping"]["valid_after"] = (
        repeats if valid_after is None else valid_after
    )
    protocol["repeated_protocol"]["limits"]["max_runs"] = max_runs
    protocol["repeated_protocol"]["effect"]["minimum_effect"] = 0.0
    for name in (
        "calibration_binding_digest",
        "comparison_apparatus_digest",
        "protocol_digest",
    ):
        protocol.pop(name, None)
    protocol = finalize_protocol_snapshot(protocol)
    candidate = {
        **protocol["accepted_build"],
        "role": "candidate",
        "commit_sha": "simulated:candidate",
        "tree_sha": "simulated:candidate",
        "materialized_digest": digest_json("candidate", domain="test.build"),
    }
    return protocol, candidate


def _run(
    protocol: dict,
    candidate: dict,
    *,
    role: str,
    arm: str,
    repeat_index: int,
    seed: int,
    statuses: dict[str, str],
    invalid: bool = False,
) -> ArmEvidence:
    context = make_run_context(
        protocol,
        protocol["accepted_build"] if arm == "baseline" else candidate,
        arm=arm,
        suite_role=role,
        task_ids=[task["id"] for task in TASKS],
        repeat_index=repeat_index,
        seed=seed,
    )
    run = EvalRun(
        output_dir=Path("."),
        suite_name=role,
        summary={
            "run_valid": not invalid,
            "strict_success_rate": sum(value == "passed" for value in statuses.values())
            / len(statuses),
        },
        statuses=statuses,
        rewards={},
        run_id=context["run_id"],
        live_receipt=expected_live_run_receipt(
            protocol, run_digest=context["run_digest"]
        ),
        run_context=context,
        protocol_snapshot=protocol,
    )
    eligibility = Eligibility(
        evidence_class="simulated",
        acceptance_eligible=False,
        integrity_status="invalid" if invalid else "not_applicable",
        integrity_errors=["injected infrastructure failure"] if invalid else [],
    )
    return ArmEvidence(run=run, context=context, eligibility=eligibility)


class RepeatedProtocolSimulationTest(unittest.TestCase):
    def _execute(
        self,
        scenario,
        *,
        max_runs: int = 4,
        transfer_status: str = "not_due",
        accepted_protection: dict | None = None,
    ):
        protocol, candidate = _protocol(max_runs=max_runs)

        def run_arm(role, arm, repeat_index, seed, _is_final):
            statuses, invalid = scenario(role, arm, repeat_index)
            return _run(
                protocol,
                candidate,
                role=role,
                arm=arm,
                repeat_index=repeat_index,
                seed=seed,
                statuses=statuses,
                invalid=invalid,
            )

        return execute_repeated_protocol(
            protocol=protocol,
            task_sources={task["id"]: task["source"] for task in TASKS},
            predicted_task_ids={"task-a"},
            run_arm=run_arm,
            validate_activation=lambda _role, _baseline, _treatment: [],
            deadline_at=100.0,
            now=lambda: 0.0,
            transfer_status=transfer_status,
            accepted_protection=(
                protocol["execution"]["accepted_protection"]
                if accepted_protection is None
                else accepted_protection
            ),
            validity_policy="strict",
            min_prediction_precision=0.1,
        )

    def test_powered_positive_is_accepted_but_simulated_state_is_inert(self) -> None:
        def scenario(role, arm, _repeat):
            if role == "dev":
                return ({"task-a": "failed", "task-b": "failed"} if arm == "baseline"
                        else {"task-a": "passed", "task-b": "passed"}), False
            return {"task-a": "passed", "task-b": "passed"}, False

        result = self._execute(scenario)
        self.assertEqual(result.decision, "accepted")
        self.assertFalse(Verdict(result.decision, result.evidence_class).advances_accepted_state)

    def test_behavior_neutral_noop_is_rejected(self) -> None:
        result = self._execute(
            lambda _role, _arm, _repeat: (
                {"task-a": "failed", "task-b": "passed"}, False
            )
        )
        self.assertEqual(result.decision, "rejected")
        self.assertIn("predicted flip", result.detail["reason"])

    def test_repeated_regression_is_rejected(self) -> None:
        def scenario(role, arm, _repeat):
            if role == "dev":
                return ({"task-a": "failed", "task-b": "failed"} if arm == "baseline"
                        else {"task-a": "passed", "task-b": "passed"}), False
            return ({"task-a": "passed", "task-b": "passed"} if arm == "baseline"
                    else {"task-a": "passed", "task-b": "failed"}), False

        self.assertEqual(self._execute(scenario).decision, "rejected")

    def test_mixed_valid_effect_is_inconclusive(self) -> None:
        def scenario(role, arm, repeat):
            if role == "regression" or repeat == 1:
                return {"task-a": "failed", "task-b": "failed"}, False
            return ({"task-a": "failed", "task-b": "failed"} if arm == "baseline"
                    else {"task-a": "passed", "task-b": "passed"}), False

        self.assertEqual(self._execute(scenario).decision, "inconclusive")

    def test_infrastructure_failure_is_invalid(self) -> None:
        def scenario(role, arm, repeat):
            invalid = role == "dev" and arm == "treatment" and repeat == 0
            return {"task-a": "failed", "task-b": "failed"}, invalid

        self.assertEqual(self._execute(scenario).decision, "invalid")

    def test_scheduled_transfer_protection_blocks_or_rejects(self) -> None:
        def positive(role, arm, _repeat):
            if role == "dev":
                return ({"task-a": "failed", "task-b": "failed"} if arm == "baseline"
                        else {"task-a": "passed", "task-b": "passed"}), False
            return {"task-a": "passed", "task-b": "passed"}, False

        self.assertEqual(
            self._execute(positive, transfer_status="missing").decision,
            "inconclusive",
        )
        self.assertEqual(
            self._execute(positive, transfer_status="regressed").decision,
            "rejected",
        )

    def test_comparison_quorum_comes_only_from_frozen_protocol(self) -> None:
        def positive(role, arm, _repeat):
            if role == "dev":
                return (
                    {"task-a": "failed", "task-b": "failed"}
                    if arm == "baseline"
                    else {"task-a": "passed", "task-b": "passed"}
                ), False
            return {"task-a": "passed", "task-b": "passed"}, False

        with mock.patch(
            "opti_loop.repeated.compare_runs", wraps=compare_runs
        ) as compared:
            result = self._execute(positive)
        self.assertEqual(result.decision, "accepted")
        self.assertTrue(compared.call_args_list)
        self.assertEqual(
            {
                call.kwargs["quorum_coverage_floor"]
                for call in compared.call_args_list
            },
            {1.0},
        )

    def test_budget_and_deadline_exhaustion_are_inconclusive(self) -> None:
        def neutral(_role, _arm, _repeat):
            return {"task-a": "failed", "task-b": "failed"}, False
        with self.assertRaisesRegex(IdentityError, "cannot reach stopping.valid_after"):
            _protocol(max_runs=2)

        protocol, candidate = _protocol()
        deadline = execute_repeated_protocol(
            protocol=protocol,
            task_sources={task["id"]: task["source"] for task in TASKS},
            predicted_task_ids={"task-a"},
            run_arm=lambda role, arm, repeat, seed, _final: _run(
                protocol, candidate, role=role, arm=arm, repeat_index=repeat,
                seed=seed, statuses={"task-a": "failed", "task-b": "failed"}
            ),
            validate_activation=lambda _role, _baseline, _treatment: [],
            deadline_at=0.0,
            now=lambda: 0.0,
            transfer_status="not_due",
            accepted_protection=protocol["execution"]["accepted_protection"],
            validity_policy="strict",
            min_prediction_precision=0.1,
        )
        self.assertEqual((deadline.decision, deadline.detail["exhaustion"]),
                         ("inconclusive", "deadline"))

    def test_arm_finishing_after_deadline_is_not_retained_or_decided(self) -> None:
        protocol, candidate = _protocol(repeats=1, max_runs=2)
        clock = {"value": 0.0, "arms": 0}

        def run_arm(role, arm, repeat, seed, _final):
            clock["arms"] += 1
            if clock["arms"] == 4:
                clock["value"] = 101.0
            statuses = (
                {"task-a": "failed", "task-b": "failed"}
                if role == "dev" and arm == "baseline"
                else {"task-a": "passed", "task-b": "passed"}
            )
            return _run(
                protocol,
                candidate,
                role=role,
                arm=arm,
                repeat_index=repeat,
                seed=seed,
                statuses=statuses,
            )

        result = execute_repeated_protocol(
            protocol=protocol,
            task_sources={task["id"]: task["source"] for task in TASKS},
            predicted_task_ids={"task-a"},
            run_arm=run_arm,
            validate_activation=lambda _role, _baseline, _treatment: [],
            deadline_at=100.0,
            now=lambda: clock["value"],
            transfer_status="not_due",
            accepted_protection=protocol["execution"]["accepted_protection"],
            validity_policy="strict",
            min_prediction_precision=0.1,
        )
        self.assertEqual(
            (result.decision, result.detail["exhaustion"]),
            ("inconclusive", "deadline"),
        )
        self.assertNotIn("regression.repeat-0.seed-0.treatment", result.admissions)

    def test_interrupted_schedule_resumes_without_reexecuting_completed_arms(self) -> None:
        protocol, candidate = _protocol()
        cache = {}
        executions = []
        interrupt_once = {"armed": True}

        def run_arm(role, arm, repeat, seed, _final):
            key = (role, arm, repeat, seed)
            if key in cache:
                return cache[key]
            if interrupt_once["armed"] and len(executions) == 3:
                interrupt_once["armed"] = False
                raise KeyboardInterrupt("injected interruption")
            statuses = (
                {"task-a": "failed", "task-b": "failed"}
                if role == "dev" and arm == "baseline"
                else {"task-a": "passed", "task-b": "passed"}
            )
            evidence = _run(
                protocol, candidate, role=role, arm=arm, repeat_index=repeat,
                seed=seed, statuses=statuses
            )
            cache[key] = evidence
            executions.append(key)
            return evidence

        kwargs = dict(
            protocol=protocol,
            task_sources={task["id"]: task["source"] for task in TASKS},
            predicted_task_ids={"task-a"},
            run_arm=run_arm,
            validate_activation=lambda _role, _baseline, _treatment: [],
            deadline_at=100.0,
            now=lambda: 0.0,
            transfer_status="not_due",
            accepted_protection=protocol["execution"]["accepted_protection"],
            validity_policy="strict",
            min_prediction_precision=0.1,
        )
        with self.assertRaises(KeyboardInterrupt):
            execute_repeated_protocol(**kwargs)
        result = execute_repeated_protocol(**kwargs)
        self.assertEqual(result.decision, "accepted")
        self.assertEqual(len(executions), 8)
        self.assertEqual(len(set(executions)), 8)

    def test_predicted_flip_requires_support_in_every_frozen_dev_block(self) -> None:
        def scenario(role, arm, repeat):
            if role == "dev" and arm == "treatment" and repeat == 0:
                return {"task-a": "passed", "task-b": "passed"}, False
            if role == "dev" and arm == "treatment":
                return {"task-a": "failed", "task-b": "passed"}, False
            return {"task-a": "failed", "task-b": "failed"}, False

        result = self._execute(scenario)
        self.assertEqual(result.decision, "inconclusive")
        self.assertEqual(result.detail["partial_predicted_fixes"], ["task-a"])

    def test_fixed_stop_runs_interleaved_dev_regression_block_set(self) -> None:
        protocol, candidate = _protocol(repeats=3, valid_after=1, max_runs=2)
        order = []

        def run_arm(role, arm, repeat, seed, _final):
            order.append((role, arm, repeat, seed))
            statuses = (
                {"task-a": "failed", "task-b": "failed"}
                if role == "dev" and arm == "baseline"
                else {"task-a": "passed", "task-b": "passed"}
            )
            return _run(
                protocol,
                candidate,
                role=role,
                arm=arm,
                repeat_index=repeat,
                seed=seed,
                statuses=statuses,
            )

        result = execute_repeated_protocol(
            protocol=protocol,
            task_sources={task["id"]: task["source"] for task in TASKS},
            predicted_task_ids={"task-a"},
            run_arm=run_arm,
            validate_activation=lambda _role, _baseline, _treatment: [],
            deadline_at=100.0,
            now=lambda: 0.0,
            transfer_status="not_due",
            accepted_protection=protocol["execution"]["accepted_protection"],
            validity_policy="strict",
            min_prediction_precision=0.1,
        )
        self.assertEqual(result.decision, "accepted")
        self.assertEqual(
            order,
            [
                ("dev", "baseline", 0, 0),
                ("dev", "treatment", 0, 0),
                ("regression", "baseline", 0, 0),
                ("regression", "treatment", 0, 0),
            ],
        )

    def test_durable_protection_catches_transient_baseline_miss(self) -> None:
        protection = {
            "champion_sha": "a" * 40,
            "protected_tasks": ["task-b"],
            "success_rates": {"task-b": 1.0},
        }

        def scenario(role, arm, _repeat):
            if role == "dev":
                return (
                    {"task-a": "failed", "task-b": "failed"}
                    if arm == "baseline"
                    else {"task-a": "passed", "task-b": "failed"}
                ), False
            return {"task-a": "passed", "task-b": "failed"}, False

        result = self._execute(scenario, accepted_protection=protection)
        self.assertEqual(result.decision, "rejected")
        self.assertEqual(result.detail["durable_regressions"], ["task-b"])

    def test_durable_reference_prevents_cumulative_degradation(self) -> None:
        protection = {
            "champion_sha": "a" * 40,
            "protected_tasks": ["task-b"],
            "success_rates": {"task-b": 1.0},
        }

        def scenario(role, arm, repeat):
            task_b = "passed" if repeat == 0 else "failed"
            if role == "dev":
                return (
                    {"task-a": "failed", "task-b": task_b}
                    if arm == "baseline"
                    else {"task-a": "passed", "task-b": task_b}
                ), False
            return {"task-a": "passed", "task-b": task_b}, False

        result = self._execute(scenario, accepted_protection=protection)
        self.assertEqual(result.decision, "rejected")
        self.assertEqual(result.detail["durable_regressions"], ["task-b"])

    def test_completed_warc_arm_reconstructs_closed_activation_on_resume(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            task_root = output / "tasks" / "warc-bench-online-4"
            work = task_root / "warc-online4"
            work.mkdir(parents=True)
            request = {"runtime_launcher_sha256": "1" * 64}
            (work / "request.json").write_text(json.dumps(request) + "\n")
            runtime_events = [
                {
                    "event_id": "load-1",
                    "event": "treatment_loaded",
                    "path": "harness/components/policy/x.txt",
                    "sha256": "2" * 64,
                },
                {
                    "event_id": "request-1",
                    "event": "model_request_applied",
                    "applied_request_sha256": "3" * 64,
                },
            ]
            (work / "runtime-trace.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in runtime_events)
            )
            (task_root / "trace.jsonl").write_text("{}\n")
            (output / "run.json").write_text("{}\n")
            run = EvalRun(
                output_dir=output,
                suite_name="dev",
                summary={"run_valid": True},
                statuses={},
                rewards={},
            )
            observation = reconstruct_warc_online4_activation(run)
            self.assertIsNotNone(observation)
            assert observation is not None
            self.assertEqual(observation["treatment_event_id"], "load-1")
            self.assertEqual(observation["model_request_event_ids"], ["request-1"])
            self.assertEqual(observation["run_artifact"]["path"], "run.json")


if __name__ == "__main__":
    unittest.main()
