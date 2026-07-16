from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from opti_eval.adapters.fixture import FixtureAdapter
from opti_eval.identity import (
    IdentityError,
    LiveRunReceipt,
    RUN_CONTEXT_FIELDS,
    calibration_binding_digest,
    digest_json,
    finalize_protocol_snapshot,
    make_run_context,
    normalize_adapter_identity,
    simulated_protocol,
    simulated_run_identity,
    validate_candidate_allowlist,
    validate_paired_contexts,
    validate_protocol_snapshot,
    validate_run_context,
)
from opti_eval.runner import run_evaluation
from opti_eval.summary import load_run_artifacts, load_run_summary, summarize_results


TASK = {"id": "task-a", "source": "test-source", "goal": "test"}
TASK_B = {"id": "task-b", "source": "test-source", "goal": "test b"}
SUITE = {"id": "suite-a", "kind": "test"}


def _protocol(*, tasks: list[dict] | None = None, adapter: dict | None = None) -> dict:
    return simulated_protocol(
        suite=SUITE,
        tasks=tasks or [TASK],
        adapter=adapter or FixtureAdapter(pass_rate=1.0).describe(),
    )


def _pin_production_strings(value):
    if isinstance(value, str):
        lowered = value.casefold()
        if lowered in {
            "simulated",
            "placeholder",
            "unknown",
            "none",
            "not-calibrated",
            "not_calibrated",
            "not-admitted",
            "not_admitted",
            "unconfigured",
            "unpinned",
            "uncalibrated",
            "todo",
            "tbd",
            "latest",
        } or lowered.startswith(
            (
                "simulated:",
                "placeholder:",
                "unconfigured:",
                "unpinned:",
                "uncalibrated:",
                "todo:",
                "tbd:",
            )
        ):
            return "pinned-" + digest_json(value, domain="test.pin.v1")[:16]
    if isinstance(value, list):
        return [_pin_production_strings(item) for item in value]
    if isinstance(value, dict):
        return {key: _pin_production_strings(item) for key, item in value.items()}
    return value


def _benchmark_protocol(*, immutable: bool = True) -> dict:
    protocol = _pin_production_strings(_protocol())
    protocol["evidence_mode"] = "benchmark"
    protocol["accepted_build"].update(
        commit_sha="a" * 40,
        tree_sha="b" * 40,
        immutable=immutable,
    )
    protocol["execution"]["accepted_protection"].update(
        champion_sha="a" * 40,
    )
    reportable = FixtureAdapter(pass_rate=1.0).describe()
    reportable["benchmark_reportable"] = True
    protocol["adapter"] = normalize_adapter_identity(reportable)
    protocol["execution"]["adapter"] = copy.deepcopy(reportable)
    for name in (
        "calibration_binding_digest",
        "comparison_apparatus_digest",
        "protocol_digest",
    ):
        protocol.pop(name, None)
    return finalize_protocol_snapshot(protocol)


def _resign_context(context: dict) -> dict:
    result = copy.deepcopy(context)
    result["run_digest"] = digest_json(
        {key: value for key, value in result.items() if key != "run_digest"},
        domain="opti.run-context.v2",
    )
    return result


class _InspectingAdapter(FixtureAdapter):
    def __init__(self) -> None:
        super().__init__(pass_rate=1.0)
        self.context_fields: set[str] = set()

    def run(self, task, task_dir, *, execution_context):
        self.context_fields = set(execution_context.__dataclass_fields__)
        return super().run(
            task,
            task_dir,
            execution_context=execution_context,
        )


class _DescriptionForgery(FixtureAdapter):
    def describe(self):
        return {**super().describe(), "run_id": "adapter-forgery"}


class _ClaimedReportableFixture(FixtureAdapter):
    benchmark_reportable = True


class IdentityContractTest(unittest.TestCase):
    def test_raw_summary_never_claims_ar003_reportability(self) -> None:
        receipt = LiveRunReceipt(
            protocol_digest="1" * 64,
            run_digest="2" * 64,
            adapter_digest="3" * 64,
            evidence_mode="benchmark",
        )
        summary = summarize_results(
            [
                {
                    "task_id": "task-a",
                    "source": "test-source",
                    "status": "passed",
                    "metadata": {"benchmark_reportable": True},
                }
            ],
            live_receipt=receipt,
            run_context={
                "arm": "baseline",
                "protocol_digest": receipt.protocol_digest,
                "run_digest": receipt.run_digest,
            },
        )
        self.assertTrue(summary["live_execution_identity_verified"])
        self.assertTrue(summary["result_reportability_markers_complete"])
        self.assertFalse(summary["benchmark_reportable"])
        self.assertFalse(summary["acceptance_decision_eligible"])
        self.assertIn("AR-003", summary["interpretation"])

    def test_candidate_allowlist_rejects_trusted_surfaces_on_replay(self) -> None:
        self.assertEqual(
            validate_candidate_allowlist(
                ["harness/components/", "harness/runtime/"]
            ),
            ["harness/components/", "harness/runtime/"],
        )
        for forbidden in (
            ["evals/"],
            ["eval_harness/"],
            ["loop_harness/"],
            ["judge_harness/"],
            ["schemas/"],
            ["harness/infra/"],
            ["harness/lanes/"],
            ["harness/"],
        ):
            with self.subTest(forbidden=forbidden):
                with self.assertRaises(IdentityError):
                    validate_candidate_allowlist(forbidden)

    def test_calibration_binding_ignores_only_count_derived_scheduling(self) -> None:
        noise = _protocol()
        decision = copy.deepcopy(noise)
        decision["repeated_protocol"]["repeats"]["count"] = 3
        decision["repeated_protocol"]["stopping"]["valid_after"] = 3
        decision["repeated_protocol"]["limits"]["max_runs"] = 6
        for name in (
            "calibration_binding_digest",
            "comparison_apparatus_digest",
            "protocol_digest",
        ):
            decision.pop(name)
        decision = finalize_protocol_snapshot(decision)
        self.assertEqual(
            calibration_binding_digest(noise),
            calibration_binding_digest(decision),
        )

        drifted = copy.deepcopy(decision)
        drifted["executor"]["revision"] = "simulated:v2"
        for name in (
            "calibration_binding_digest",
            "comparison_apparatus_digest",
            "protocol_digest",
        ):
            drifted.pop(name)
        drifted = finalize_protocol_snapshot(drifted)
        self.assertNotEqual(
            calibration_binding_digest(noise),
            calibration_binding_digest(drifted),
        )

    def test_treatment_requires_changed_materialized_bytes(self) -> None:
        protocol = _protocol()
        no_op = {
            **protocol["accepted_build"],
            "role": "candidate",
            "commit_sha": "different-commit",
            "tree_sha": "different-tree",
        }
        with self.assertRaisesRegex(IdentityError, "materialization is identical"):
            make_run_context(
                protocol,
                no_op,
                arm="treatment",
                suite_role="direct",
                task_ids=["task-a"],
                repeat_index=0,
                seed=0,
            )

        changed = {
            **no_op,
            "materialized_digest": digest_json(
                "changed-candidate", domain="opti.build.v1"
            ),
        }
        context = make_run_context(
            protocol,
            changed,
            arm="treatment",
            suite_role="direct",
            task_ids=["task-a"],
            repeat_index=0,
            seed=0,
        )
        self.assertEqual(context["build"]["materialized_digest"], changed["materialized_digest"])

    def test_canonical_digest_is_stable_and_domain_separated(self) -> None:
        left = {"b": [2, 3], "a": 1}
        right = {"a": 1, "b": [2, 3]}
        self.assertEqual(
            digest_json(left, domain="one"), digest_json(right, domain="one")
        )
        self.assertNotEqual(
            digest_json(left, domain="one"), digest_json(left, domain="two")
        )

    def test_protocol_and_unique_run_identities_are_separate(self) -> None:
        protocol = _protocol()
        baseline = make_run_context(
            protocol,
            protocol["accepted_build"],
            arm="baseline",
            suite_role="direct",
            task_ids=["task-a"],
            repeat_index=0,
            seed=0,
        )
        treatment_build = {
            **protocol["accepted_build"],
            "role": "candidate",
            "materialized_digest": digest_json("candidate", domain="opti.build.v1"),
        }
        treatment = make_run_context(
            protocol,
            treatment_build,
            arm="treatment",
            suite_role="direct",
            task_ids=["task-a"],
            repeat_index=0,
            seed=0,
        )
        self.assertEqual(baseline["protocol_digest"], treatment["protocol_digest"])
        self.assertNotEqual(baseline["run_id"], treatment["run_id"])
        self.assertNotEqual(baseline["run_digest"], treatment["run_digest"])
        validate_paired_contexts(
            baseline,
            treatment,
            protocol_snapshot=protocol,
        )

        changed = copy.deepcopy(protocol)
        changed["executor"]["revision"] = "simulated:v2"
        for name in (
            "calibration_binding_digest",
            "comparison_apparatus_digest",
            "protocol_digest",
        ):
            changed.pop(name)
        changed = finalize_protocol_snapshot(changed)
        mismatched = make_run_context(
            changed,
            treatment_build,
            arm="treatment",
            suite_role="direct",
            task_ids=["task-a"],
            repeat_index=0,
            seed=0,
        )
        with self.assertRaisesRegex(IdentityError, "protocol_digest"):
            validate_paired_contexts(
                baseline,
                mismatched,
                protocol_snapshot=protocol,
            )

    def test_closed_protocol_rejects_extra_nonfinite_and_benchmark_adapter(self) -> None:
        protocol = _protocol()
        extra = copy.deepcopy(protocol)
        extra["surprise"] = True
        with self.assertRaisesRegex(IdentityError, "unexpected surprise"):
            validate_protocol_snapshot(extra)

        nonfinite = copy.deepcopy(protocol)
        nonfinite["repeated_protocol"]["effect"]["minimum_effect"] = float("nan")
        with self.assertRaisesRegex(IdentityError, "non-finite"):
            validate_protocol_snapshot(nonfinite)

        benchmark = _pin_production_strings(protocol)
        benchmark["evidence_mode"] = "benchmark"
        for name in (
            "calibration_binding_digest",
            "comparison_apparatus_digest",
            "protocol_digest",
        ):
            benchmark.pop(name)
        with self.assertRaisesRegex(IdentityError, "reportable live adapter"):
            finalize_protocol_snapshot(benchmark)

    def test_repeated_protocol_rejects_every_unsupported_fixed_policy(self) -> None:
        cases = (
            (("matched_blocks", "interleaving"), "unsupported-interleaving"),
            (("matched_blocks", "reset_scope"), "unsupported-reset"),
            (("coverage", "denominator"), "unsupported-denominator"),
            (("stopping", "rule"), "unsupported-stop"),
            (("effect", "estimator"), "unsupported-estimator"),
            (("effect", "uncertainty"), "unsupported-uncertainty"),
            (("non_inferiority", "rule"), "unsupported-non-inferiority"),
            (("regression", "rule"), "unsupported-regression"),
            (("champion", "rule"), "unsupported-champion"),
            (("transfer", "rule"), "unsupported-transfer"),
            (("transfer", "schedule"), "unsupported-schedule"),
            (("multiplicity", "rule"), "unsupported-multiplicity"),
            (("outcome_handling", "missing"), "invalid"),
        )
        for path, value in cases:
            with self.subTest(path=path):
                protocol = _protocol()
                protocol["repeated_protocol"][path[0]][path[1]] = value
                for name in (
                    "calibration_binding_digest",
                    "comparison_apparatus_digest",
                    "protocol_digest",
                ):
                    protocol.pop(name)
                with self.assertRaisesRegex(IdentityError, "unsupported"):
                    finalize_protocol_snapshot(protocol)

    def test_benchmark_protocol_requires_immutable_materialized_build(self) -> None:
        with self.assertRaisesRegex(IdentityError, "immutable materialized build receipt"):
            _benchmark_protocol(immutable=False)

    def test_production_identity_rejects_casefolded_exact_sentinels_only(self) -> None:
        for sentinel in ("NONE", "Not-Calibrated", "LATEST", "Placeholder:route"):
            with self.subTest(sentinel=sentinel):
                benchmark = _benchmark_protocol()
                benchmark["executor"]["model"] = sentinel
                for name in (
                    "calibration_binding_digest",
                    "comparison_apparatus_digest",
                    "protocol_digest",
                ):
                    benchmark.pop(name)
                with self.assertRaisesRegex(IdentityError, "exact production identity"):
                    finalize_protocol_snapshot(benchmark)

        benchmark = _benchmark_protocol()
        benchmark["executor"]["model"] = "model-latest-stable"
        for name in (
            "calibration_binding_digest",
            "comparison_apparatus_digest",
            "protocol_digest",
        ):
            benchmark.pop(name)
        validate_protocol_snapshot(finalize_protocol_snapshot(benchmark))

    def test_run_context_closes_exact_subset_seed_repeat_and_order(self) -> None:
        protocol = _protocol(tasks=[TASK, TASK_B])
        context = make_run_context(
            protocol,
            {**protocol["accepted_build"], "role": "diagnostic"},
            arm="diagnostic",
            suite_role="direct",
            task_ids=["task-b"],
            repeat_index=0,
            seed=0,
        )
        self.assertEqual(context["task_ids"], ["task-b"])
        self.assertEqual(set(context), RUN_CONTEXT_FIELDS)
        for name, value, message in (
            ("task_ids", ["task-b", "task-a"], "outside or out of order"),
            ("task_ids", ["task-a", "outside"], "outside or out of order"),
            ("seed", 1, "not declared"),
            ("repeat_index", 1, "exceeds frozen repeat count"),
        ):
            with self.subTest(field=name, value=value):
                attacked = copy.deepcopy(context)
                attacked[name] = value
                attacked = _resign_context(attacked)
                with self.assertRaisesRegex(IdentityError, message):
                    validate_run_context(attacked, protocol_snapshot=protocol)

    def test_protocol_requires_exact_task_seed_blocks_and_arm_order(self) -> None:
        for mutate in (
            lambda protocol: protocol["matched_blocks"].pop(),
            lambda protocol: protocol["matched_blocks"][0].update(
                arm_order=["treatment", "baseline"]
            ),
        ):
            protocol = _protocol()
            mutate(protocol)
            for name in (
                "calibration_binding_digest",
                "comparison_apparatus_digest",
                "protocol_digest",
            ):
                protocol.pop(name)
            with self.assertRaisesRegex(IdentityError, "matched_blocks"):
                finalize_protocol_snapshot(protocol)

    def test_arm_roles_bind_accepted_candidate_and_diagnostic_evidence(self) -> None:
        protocol = _protocol()
        candidate = {
            **protocol["accepted_build"],
            "role": "candidate",
            "materialized_digest": digest_json("candidate", domain="opti.build.v1"),
        }
        with self.assertRaisesRegex(IdentityError, "baseline.*accepted"):
            make_run_context(
                protocol,
                candidate,
                arm="baseline",
                suite_role="direct",
                task_ids=["task-a"],
                repeat_index=0,
                seed=0,
            )
        with self.assertRaisesRegex(IdentityError, "candidate.*identical"):
            make_run_context(
                protocol,
                {**protocol["accepted_build"], "role": "candidate"},
                arm="treatment",
                suite_role="direct",
                task_ids=["task-a"],
                repeat_index=0,
                seed=0,
            )

        benchmark = _benchmark_protocol()
        with self.assertRaisesRegex(IdentityError, "diagnostic runs cannot"):
            make_run_context(
                benchmark,
                {**benchmark["accepted_build"], "role": "diagnostic"},
                arm="diagnostic",
                suite_role="direct",
                task_ids=["task-a"],
                repeat_index=0,
                seed=0,
            )

    def test_runner_exposes_only_minimal_identity_and_persists_caller_digests(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            adapter = _InspectingAdapter()
            protocol, context = simulated_run_identity(
                suite=SUITE,
                tasks=[TASK],
                adapter=adapter.describe(),
            )
            execution = run_evaluation(
                repo_root=Path(tmp),
                suite=SUITE,
                tasks=[TASK],
                adapter=adapter,
                output_dir=Path(tmp) / "run",
                protocol_snapshot=protocol,
                run_context=context,
            )
            record = execution.record
            self.assertEqual(
                adapter.context_fields,
                {"run_id", "run_context_digest"},
            )
            self.assertEqual(record["run_context_digest"], context["run_digest"])
            self.assertEqual(
                record["protocol"]["protocol_digest"], protocol["protocol_digest"]
            )
            self.assertEqual(
                record["summary"]["adapter_digest"], protocol["adapter"]["digest"]
            )

    def test_runner_rejects_description_forgery_adapter_drift_and_self_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            adapter = _DescriptionForgery()
            protocol, context = simulated_run_identity(
                suite=SUITE,
                tasks=[TASK],
                adapter=FixtureAdapter().describe(),
            )
            with self.assertRaisesRegex(ValueError, "runner-owned identity"):
                run_evaluation(
                    repo_root=Path(tmp),
                    suite=SUITE,
                    tasks=[TASK],
                    adapter=adapter,
                    output_dir=Path(tmp) / "forgery",
                    protocol_snapshot=protocol,
                    run_context=context,
                )

        with tempfile.TemporaryDirectory() as tmp:
            frozen = FixtureAdapter(pass_rate=1.0)
            actual = FixtureAdapter(pass_rate=0.5)
            protocol, context = simulated_run_identity(
                suite=SUITE,
                tasks=[TASK],
                adapter=frozen.describe(),
            )
            with self.assertRaisesRegex(ValueError, "adapter identity does not match"):
                run_evaluation(
                    repo_root=Path(tmp),
                    suite=SUITE,
                    tasks=[TASK],
                    adapter=actual,
                    output_dir=Path(tmp) / "drift",
                    protocol_snapshot=protocol,
                    run_context=context,
                )

        with tempfile.TemporaryDirectory() as tmp:
            adapter = _ClaimedReportableFixture()
            protocol, context = simulated_run_identity(
                suite=SUITE,
                tasks=[TASK],
                adapter=adapter.describe(),
            )
            with self.assertRaisesRegex(ValueError, "exact benchmark protocol"):
                run_evaluation(
                    repo_root=Path(tmp),
                    suite=SUITE,
                    tasks=[TASK],
                    adapter=adapter,
                    output_dir=Path(tmp) / "claim",
                    protocol_snapshot=protocol,
                    run_context=context,
                )

    def test_ordinary_replay_is_diagnostic_and_receipt_blocks_bundle_substitution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            adapter = FixtureAdapter(pass_rate=1.0)
            executions = []
            for name in ("one", "two"):
                protocol, context = simulated_run_identity(
                    suite=SUITE,
                    tasks=[TASK],
                    adapter=adapter.describe(),
                )
                executions.append(
                    run_evaluation(
                        repo_root=root,
                        suite=SUITE,
                        tasks=[TASK],
                        adapter=adapter,
                        output_dir=root / name,
                        protocol_snapshot=protocol,
                        run_context=context,
                    )
                )
            replayed = load_run_summary(root / "one")
            self.assertTrue(replayed["run_valid"], replayed.get("replay_errors"))
            self.assertFalse(replayed["benchmark_reportable"])
            substituted, _ = load_run_artifacts(
                root / "one",
                expected_receipt=executions[1].receipt,
            )
            self.assertFalse(substituted["run_valid"])
            self.assertTrue(substituted["replay_errors"])

    def test_replay_rejects_omitted_tampered_and_cross_surface_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "base"
            adapter = FixtureAdapter(pass_rate=1.0)
            protocol, context = simulated_run_identity(
                suite=SUITE,
                tasks=[TASK],
                adapter=adapter.describe(),
            )
            run_evaluation(
                repo_root=root,
                suite=SUITE,
                tasks=[TASK],
                adapter=adapter,
                output_dir=base,
                protocol_snapshot=protocol,
                run_context=context,
            )
            self.assertTrue(load_run_summary(base)["run_valid"])
            attacks = {
                "omitted": lambda run, summary, result, task: run.pop("run_context"),
                "tampered": lambda run, summary, result, task: run["run_context"].update(
                    arm="treatment"
                ),
                "summary_mismatch": lambda run, summary, result, task: summary.update(
                    run_context_digest="0" * 64
                ),
                "result_mismatch": lambda run, summary, result, task: result[
                    "metadata"
                ].update(run_context_digest="0" * 64),
                "task_mismatch": lambda run, summary, result, task: task.update(
                    goal="tampered"
                ),
            }
            for name, mutate in attacks.items():
                with self.subTest(name=name):
                    target = root / name
                    shutil.copytree(base, target)
                    run = json.loads((target / "run.json").read_text())
                    summary = json.loads((target / "summary.json").read_text())
                    result = json.loads(
                        (target / "tasks" / "task-a" / "result.json").read_text()
                    )
                    task = json.loads(
                        (target / "tasks" / "task-a" / "task.json").read_text()
                    )
                    mutate(run, summary, result, task)
                    (target / "run.json").write_text(json.dumps(run) + "\n")
                    (target / "summary.json").write_text(json.dumps(summary) + "\n")
                    (target / "tasks" / "task-a" / "task.json").write_text(
                        json.dumps(task) + "\n"
                    )
                    (target / "tasks" / "task-a" / "result.json").write_text(
                        json.dumps(result) + "\n"
                    )
                    (target / "results.jsonl").write_text(json.dumps(result) + "\n")
                    replayed = load_run_summary(target)
                    self.assertFalse(replayed["run_valid"])
                    self.assertTrue(replayed["replay_errors"])


if __name__ == "__main__":
    unittest.main()
