"""End-to-end tests of the transactional v2 loop over a trusted boundary.

Production runbook order (F18): start -> optimizer commits in the isolated
worktree + writes manifest.json -> run-iteration (gate + accept/reset + record
as ONE transaction). The current command bridge is diagnostic plumbing only:
without a trusted evidence path, even a performance-improving pass payload
must remain simulated and cannot advance the accepted base.

Adversarial cases assert the review's blocking holes are closed: committed
forbidden edit (F01), forged gate report (F02), simulated never advances real
state (F04), shotgun precision floor (F09), and rejection resets the worktree
without advancing (F06).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from opti_eval.adapters.fixture import FixtureAdapter
from opti_eval.identity import (
    digest_json,
    finalize_protocol_snapshot,
    normalize_adapter_identity,
    simulated_identity_defaults,
    simulated_protocol,
)
from opti_eval.warc_online4_runtime import (
    ONLINE4_MATCHER,
    UPSTREAM_START_URL,
    action_tool_schema_digest,
)
from opti_eval.warc_online4_runtime import run_lifecycle as run_warc_lifecycle
from opti_loop.campaign import init_campaign, load_campaign
from opti_loop.operation import (
    accepted_ref_status,
    blockers as operation_blockers,
    operation_config,
    request as lifecycle_request,
    status as operation_status,
)
from opti_loop.learning import read_records
from opti_loop.ledger import read_rows
from opti_loop.packet import build_packet
from opti_loop.cli import main as cli_main
from opti_loop.conductor import (
    MAX_MANIFEST_BYTES,
    _copy_benchmark_bundle,
    _manifest_snapshot_digest,
    _optimizer_bundle,
    _publication_rejection_errors,
    _seal_publication_record,
    _validate_benchmark_handback_ownership,
    _read_manifest_snapshot,
    _load_accepted_run,
    compare_campaigns,
    continue_campaign,
    measure_noise,
    publication_status,
    run_iteration,
    start_iteration,
)
from opti_loop import gitutil
from opti_loop.gates import GateReport, RungResult
from opti_loop.materialization import (
    CampaignLock,
    MaterializationError,
)
from opti_loop.verdict import Verdict
from opti_loop.protocol import (
    ProtocolError,
    build_protocol_snapshot,
    freeze_protocol,
    load_frozen_protocol,
)

REPO_ROOT = Path(os.environ["OPTI_BROWSER_REPO_ROOT"])
ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
       "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
QUALITY_REL = "harness/components/policy/quality.txt"
_UNSET = object()

try:
    from jsonschema import Draft202012Validator
except ImportError:
    EXPERIMENT_VALIDATOR = None
else:
    EXPERIMENT_VALIDATOR = Draft202012Validator(
        json.loads((REPO_ROOT / "schemas/experiment.schema.json").read_text(encoding="utf-8"))
    )

BRIDGE = """import argparse, hashlib, json
p = argparse.ArgumentParser()
p.add_argument("--task-json"); p.add_argument("--result-json"); p.add_argument("--quality")
a = p.parse_args()
task = json.load(open(a.task_json))
try:
    q = float(open(a.quality).read().strip())
except Exception:
    q = 0.0
tid = task["id"]
v = int.from_bytes(hashlib.sha256(f"0:{tid}".encode()).digest(), "big") / float(2 ** 256)
passed = v < q
json.dump({"task_id": tid, "status": "passed" if passed else "failed",
           "reward": 1.0 if passed else 0.0, "verifier": {"kind": "test_state", "valid": True}},
          open(a.result_json, "w"))
"""

WARC_VERIFIER = ONLINE4_MATCHER + "\n"


def _warc_echo_only_lifecycle(request_path: Path, result_path: Path) -> None:
    """Legacy-shaped echo: identity claims without trusted lifecycle evidence."""
    request = json.loads(request_path.read_text())
    result_path.write_text(json.dumps({
        "schema_version": "0.4.0", "task_id": request["task_id"],
        "request_digest": request["request_digest"],
        "reset": {
            "start_url": UPSTREAM_START_URL,
            "initial_state": {"calendarfocusdate": None},
            "source_manifest": {
                "git_blob_sha1": request["source_identity"]["manifest_blob_sha1"],
                "content_sha256": "0" * 64,
                "online4_row_sha256": "0" * 64,
                "verified_from_installed_bytes": False,
            },
        },
        "steps": [{
            "action": {"kind": "click"}, "outcome": {"status": "ok"},
            "browser_state": {"calendarfocusdate": "03/21/2025"},
        }],
        "final_state": {"calendarfocusdate": "03/21/2025"},
        "verifier": {
            phase: {
                "passed": phase == "final",
                "verifier_id": request["verifier"]["id"],
                "verifier_sha256": request["verifier"]["sha256"],
                "upstream_commit": request["source_identity"]["upstream_commit"],
                "manifest_blob_sha1": request["source_identity"]["manifest_blob_sha1"],
                "page_url": request["wacz_start_url"], "state_sha256": "0" * 64,
            }
            for phase in ("initial", "final")
        },
        "artifacts": [],
        "activation": {
            "path": request["treatment_relative_path"],
            "sha256": request["treatment_sha256"],
            "runtime_trace_path": "missing.jsonl",
            "runtime_trace_sha256": "0" * 64,
            "treatment_event_id": "echo",
            "model_request_event_ids": ["echo"],
        },
        "cleanup": {"completed": True},
    }) + "\n")


def _warc_dropped_treatment_lifecycle(request_path: Path, result_path: Path) -> None:
    """A complete-looking run whose actual model body omits the candidate."""
    run_warc_lifecycle(request_path, result_path)
    work = result_path.parent
    request_file = work / "model-request-0.json"
    body = json.loads(request_file.read_text())
    body["system"] = "candidate bytes deliberately dropped"
    applied = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    request_file.write_bytes(applied + b"\n")
    trace_path = work / "runtime-trace.jsonl"
    events = [json.loads(line) for line in trace_path.read_text().splitlines()]
    for event in events:
        if event.get("event") == "model_request_applied" and event.get("request_path") == request_file.name:
            event["applied_request_sha256"] = hashlib.sha256(applied).hexdigest()
    trace_path.write_text("".join(json.dumps(event, sort_keys=True) + "\n" for event in events))
    result = json.loads(result_path.read_text())
    result["activation"]["runtime_trace_sha256"] = hashlib.sha256(trace_path.read_bytes()).hexdigest()
    result_path.write_text(json.dumps(result, sort_keys=True) + "\n")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=ENV)


def _fixture_value(tid: str) -> float:
    return int.from_bytes(hashlib.sha256(f"0:{tid}".encode()).digest(), "big") / float(2 ** 256)


class TransactionalLoopTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        self.repo = tmp / "repo"
        (self.repo / "evals").mkdir(parents=True)
        shutil.copytree(REPO_ROOT / "evals/catalog", self.repo / "evals/catalog")
        shutil.copytree(REPO_ROOT / "evals/suites", self.repo / "evals/suites")
        shutil.copytree(REPO_ROOT / "harness", self.repo / "harness")
        # Register a simulated-quality knob in the policy component.
        (self.repo / QUALITY_REL).write_text("0.55\n")
        reg = self.repo / "harness/components/policy/component.json"
        data = json.loads(reg.read_text())
        data["files"] = sorted(set(data["files"]) | {"quality.txt"})
        reg.write_text(json.dumps(data, indent=2) + "\n")
        _git(self.repo, "init", "-q")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-qm", "base")

        self.store = tmp / "store"
        self.bridge = tmp / "bridge.py"
        self.bridge.write_text(BRIDGE)
        self.checksum = hashlib.sha256(self.bridge.read_bytes()).hexdigest()
        self.smoke_ids = json.loads((self.repo / "evals/suites/smoke.json").read_text())["task_ids"]
        self.flipping = sorted(t for t in self.smoke_ids if 0.55 <= _fixture_value(t) < 0.70)
        self.assertTrue(self.flipping)

    def tearDown(self) -> None:
        subprocess.run(["git", "-C", str(self.repo), "worktree", "prune"], capture_output=True, env=ENV)
        self._tmp.cleanup()

    # ── adapters / admissions ─────────────────────────────────────────────
    def _command_adapter(self) -> dict:
        quality_abs = self.store / "cmp" / "candidate-worktree" / QUALITY_REL
        cmd = (f"{sys.executable} {self.bridge} --task-json {{task_json}} "
               f"--result-json {{result_json}} --quality {quality_abs}")
        return {"kind": "command", "command": cmd,
                "verifier_id": "test-verifier", "verifier_checksum": self.checksum}

    def _register_admissions(self, campaign) -> None:
        ids = set(self.smoke_ids) | set(json.loads((self.repo / "evals/suites/regression.json").read_text())["task_ids"])
        campaign.store.admissions_path.parent.mkdir(parents=True, exist_ok=True)
        with campaign.store.admissions_path.open("w") as fh:
            for tid in sorted(ids):
                fh.write(json.dumps({"verifier_id": "test-verifier", "task_id": tid,
                                     "verifier_checksum": self.checksum, "admitted": True}) + "\n")
        verifier = campaign.config["identity"]["verifier_bundle"]
        verifier.update(
            id="test-verifier",
            checksum=self.checksum,
            bundle_digest=hashlib.sha256(self.bridge.read_bytes()).hexdigest(),
            admissions_digest=hashlib.sha256(
                b"opti.admissions.v1\0"
                + campaign.store.admissions_path.read_bytes()
            ).hexdigest(),
        )
        campaign.save_config()

    def _commit_quality(self, worktree: Path, value: str) -> None:
        (worktree / QUALITY_REL).write_text(value)
        _git(worktree, "add", "-A")
        _git(worktree, "commit", "-qm", f"quality {value}")

    def _commit_registration_only(self, worktree: Path) -> None:
        path = worktree / "harness/components/policy/component.json"
        payload = json.loads(path.read_text())
        payload["activation_events"] = sorted(
            set(payload.get("activation_events", [])) | {"fixture-registration-only"}
        )
        path.write_text(json.dumps(payload, indent=2) + "\n")
        _git(worktree, "add", "-A")
        _git(worktree, "commit", "-qm", "registration only")

    def _write_manifest(self, worktree: Path, predicted: list[str], **over) -> None:
        m = {
            "schema_version": "0.1-draft", "experiment_id": "e", "status": "proposed",
            "hypothesis": "raise policy quality", "trace_evidence": [{"run_id": "iter", "event_id": "n"}],
            "suspected_root_cause": "quality low",
            "treatment": {"description": "quality 0.70", "change_scope": [QUALITY_REL],
                          "activation_evidence": ["adapter reads quality.txt"]},
            "baseline_ref": "b", "fixed_variables": {"executor_model": "test"},
            "predicted_improvements": [{"failure_class": "hash-band", "tasks": predicted}],
            "regression_risks": [{"failure_class": "none", "tasks": []}],
            "evaluation_plan": {"task_sets": ["smoke"], "repetitions": {}, "pairing": "paired", "budget": {}},
            "acceptance_criteria": {"primary": "E5"}, "target_component": "policy", "cluster_ref": "stub/real_v1/failed",
        }
        m.update(over)
        (worktree / "manifest.json").write_text(json.dumps(m))

    def _static_handback(self, campaign, worktree: Path) -> tuple[Path, Path]:
        inbox = self.store / f"{campaign.campaign_id}-inbox"
        inbox.mkdir()
        sidecar = inbox / "manifest.json"
        shutil.copyfile(worktree / "manifest.json", sidecar)
        bundle = inbox / "candidate.bundle"
        gitutil.create_candidate_bundle(
            self.repo,
            bundle,
            base_sha=campaign.state["pending_base_sha"],
            candidate_sha=gitutil.head_sha(worktree),
        )
        return bundle, sidecar

    @staticmethod
    def _accepted_benchmark_report() -> GateReport:
        report = GateReport(iteration=1)
        report.verdict = Verdict("accepted", "benchmark")
        report.run_digests = {
            "dev_treatment": "d" * 64,
            "regression_treatment": "e" * 64,
        }
        report.admissions = {
            "dev_treatment": {"admission_receipt": {"receipt": "narrow mock"}}
        }
        report.comparison = {
            "fixed": [],
            "candidate_success_rates": {},
            "candidate_protected_tasks": [],
        }
        return report

    def _interrupt_publication(
        self, campaign, boundary: str
    ) -> tuple[str, dict]:
        worktree = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(worktree, "0.70\n")
        self._write_manifest(worktree, predicted=self.flipping[:1])
        candidate_sha = gitutil.head_sha(worktree)
        bundle, sidecar = self._static_handback(campaign, worktree)
        captured: dict[str, dict] = {}
        injected = False

        def interrupt(current: str) -> None:
            nonlocal injected
            if current == "intent":
                captured["intent"] = json.loads(
                    (
                        campaign.store.campaign_dir / "accepted-publication.json"
                    ).read_text()
                )
            if current == boundary and not injected:
                injected = True
                raise OSError(f"interrupt after {boundary}")

        with (
            mock.patch("opti_loop.conductor._benchmark_handback_required", return_value=True),
            mock.patch(
                "opti_loop.conductor._validate_benchmark_handback_ownership",
                return_value=os.getuid(),
            ),
            mock.patch(
                "opti_loop.conductor.run_gate",
                return_value=self._accepted_benchmark_report(),
            ),
            mock.patch(
                "opti_loop.conductor._publication_checkpoint",
                side_effect=interrupt,
            ),
            self.assertRaisesRegex(OSError, f"interrupt after {boundary}"),
        ):
            run_iteration(
                campaign,
                candidate_bundle=bundle,
                candidate_manifest=sidecar,
            )
        return candidate_sha, captured["intent"]

    def _new_campaign(self, cid: str, adapter: dict, **thresholds):
        overrides = {"adapter": adapter,
                     "operation": operation_config(max_iterations=20, max_attempts=40,
                                                   deadline_seconds=3600),
                     "suites": {"dev": "smoke", "smoke": "smoke", "regression": "regression"},
                     "thresholds": {"smoke_min_pass_rate": 0.1, **thresholds},
                     "exploration": {"divergence_quota": 0, "plateau_force_after": 0, "pivot_after_failures": 2}}
        verifier_id = adapter.get("verifier_id")
        verifier_checksum = adapter.get("verifier_checksum")
        if verifier_id is not None or verifier_checksum is not None:
            overrides["identity"] = {
                "verifier_bundle": {
                    "id": verifier_id,
                    "checksum": verifier_checksum,
                    "bundle_digest": hashlib.sha256(self.bridge.read_bytes()).hexdigest(),
                    "admissions_digest": hashlib.sha256(
                        f"{verifier_id}:{verifier_checksum}".encode()
                    ).hexdigest(),
                }
            }
        return init_campaign(self.repo, cid, store_root=self.store, overrides=overrides)

    def _new_warc_campaign(self, cid: str, *, via_cli: bool = False):
        self.store.mkdir(parents=True, exist_ok=True)
        verifier = self.store / f"{cid}-verifier.py"
        wacz = self.store / f"{cid}.wacz"
        license_file = self.store / f"{cid}-LICENSE"
        admissions = self.store / f"{cid}-admissions.jsonl"
        inbox = self.store / f"{cid}-static-inbox"
        verifier.write_text(WARC_VERIFIER)
        wacz.write_bytes(b"local fixture wacz")
        license_file.write_text("local fixture only\n")
        admissions.write_text(
            json.dumps(
                {
                    "verifier_id": f"{cid}-native-js",
                    "task_id": "warc-bench-online-4",
                    "verifier_checksum": hashlib.sha256(verifier.read_bytes()).hexdigest(),
                    "admitted": True,
                }
            )
            + "\n"
        )
        inbox.mkdir()
        python = str(Path(sys.executable).resolve())
        python_sha = hashlib.sha256(Path(python).read_bytes()).hexdigest()
        version = subprocess.run(
            [python, "--version"], capture_output=True, text=True, check=True
        )
        expected_version = "\n".join(
            value.strip() for value in (version.stdout, version.stderr) if value.strip()
        )
        runtime_identity = {
            "path": python,
            "sha256": python_sha,
            "version_command": [python, "--version"],
            "expected_version": expected_version,
        }
        defaults = simulated_identity_defaults(["warc_bench"])
        defaults["executor"]["settings"] = {"temperature": 0, "max_tokens": 256}
        defaults["executor"]["tool_schema_digest"] = action_tool_schema_digest()
        defaults["executor"]["snapshot"] = defaults["executor"]["model"]
        defaults["executor"]["revision"] = defaults["executor"]["model"]
        config_executor = dict(defaults["executor"])
        config_executor.pop("snapshot")
        config_executor.pop("revision")
        config = {
            "schema_version": "0.1.0",
            "mode": "local_fixture",
            "task": {"id": "warc-bench-online-4", "source": "warc_bench",
                     "native_task_id": "online.4"},
            "source": {
                "upstream_commit": "98d213ccd2b4380761738e1d144467a8695e37c5",
                "manifest_path": "src/orby/subtask_benchmark/environments/benchmark.json",
                "manifest_blob_sha1": "6b2bc7ee04b3231325fe3a84b195d26d0c589287",
                "data_path": "environments/web_archives/alaska_airlines/alaska_airlines_flight_booking.wacz",
            },
            "wacz": {
                "path": str(wacz), "sha256": hashlib.sha256(wacz.read_bytes()).hexdigest(),
                "start_url": UPSTREAM_START_URL,
            },
            "verifier": {
                "id": f"{cid}-native-js", "path": str(verifier),
                "sha256": hashlib.sha256(verifier.read_bytes()).hexdigest(),
                "admissions_path": str(admissions),
                "admissions_sha256": hashlib.sha256(admissions.read_bytes()).hexdigest(),
            },
            "provenance": {
                "wacz_origin": "local-fixture:generated", "verifier_origin": "local-fixture:generated",
                "license_id": "local-fixture-only", "license_evidence_path": str(license_file),
                "license_evidence_sha256": hashlib.sha256(license_file.read_bytes()).hexdigest(),
                "acknowledged": True,
            },
            "runtime": {
                **{name: dict(runtime_identity) for name in
                   ("python", "node", "warc_bench", "replay", "browsergym", "gymnasium",
                    "playwright", "playwright_driver", "browser", "sandbox")},
                "cdp_port": 4222,
            },
            "executor": config_executor,
            "credentials": {"required_env": []},
            "confinement": {
                "single_host": True, "network": "loopback-only",
                "filesystem": "read-only-except-task-output",
                "optimizer_uid": os.getuid(), "static_inbox": str(inbox),
            },
            "limits": {"timeout_seconds": 30, "deadline_seconds": 60, "action_budget": 3},
            "treatment_path": QUALITY_REL,
            "protocol_identity": {
                "source_runtime": defaults["source_runtimes"]["warc_bench"],
                "activation_instrumentation": defaults["activation_instrumentation"],
                "lane": {"id": "structured", "config_path": "harness/lanes/structured.lane.json"},
                "repeated_protocol": defaults["repeated_protocol"],
            },
        }
        config_path = self.store / f"{cid}-warc-config.json"
        config_path.write_text(json.dumps(config, indent=2) + "\n")
        verifier_sha = config["verifier"]["sha256"]
        if via_cli:
            self.assertEqual(
                cli_main([
                    "--repo-root", str(self.repo),
                    "--store-root", str(self.store),
                    "init", "--campaign", cid,
                    "--adapter", "warc-online4",
                    "--warc-config", str(config_path),
                    "--dev-suite", "warc-online4-qualification",
                    "--max-iterations", "20", "--max-attempts", "40",
                    "--deadline-seconds", "3600",
                ]),
                0,
            )
            return load_campaign(
                self.repo, cid, store_root=self.store
            ), config_path
        campaign = init_campaign(
            self.repo,
            cid,
            store_root=self.store,
            overrides={
                "adapter": {
                    "kind": "warc-online4", "config_path": str(config_path),
                    "treatment_path": QUALITY_REL,
                    "verifier_id": config["verifier"]["id"],
                    "verifier_checksum": verifier_sha,
                },
                "operation": operation_config(max_iterations=20, max_attempts=40,
                                              deadline_seconds=3600),
                "suites": {role: "warc-online4-qualification" for role in ("dev", "smoke", "regression")},
                "identity": {
                    "evidence_mode": "simulated",
                    "source_runtimes": {"warc_bench": defaults["source_runtimes"]["warc_bench"]},
                    "executor": defaults["executor"],
                    "verifier_bundle": {
                        "id": config["verifier"]["id"], "checksum": verifier_sha,
                        "bundle_digest": verifier_sha,
                        "admissions_digest": hashlib.sha256(
                            b"opti.admissions.v1\0" + admissions.read_bytes()
                        ).hexdigest(),
                    },
                    "activation_instrumentation": defaults["activation_instrumentation"],
                    "lane": config["protocol_identity"]["lane"],
                },
                "repeated_protocol": defaults["repeated_protocol"],
                "thresholds": {"smoke_min_pass_rate": 0.1},
                "exploration": {"divergence_quota": 0, "plateau_force_after": 0,
                                "pivot_after_failures": 2},
            },
        )
        shutil.copyfile(admissions, campaign.store.admissions_path)
        return campaign, config_path

    def _assert_rejected_transaction(
        self,
        campaign,
        result: dict,
        *,
        expected_submission: object = _UNSET,
        expected_error: str | None = None,
    ) -> dict:
        self.assertEqual(result["decision"], "rejected")
        self.assertFalse(result["advanced_accepted_state"])
        reloaded = load_campaign(self.repo, campaign.campaign_id, store_root=self.store)
        self.assertEqual(reloaded.state["pending_iteration"], 0)
        self.assertIsNone(reloaded.state["pending_base_sha"])
        self.assertFalse(campaign.worktree_path.exists())

        ledger = [
            json.loads(line)
            for line in campaign.ledger_path.read_text().splitlines()
            if line.strip()
        ]
        self.assertEqual(ledger[-1]["decision"], "rejected")
        self.assertTrue(campaign.learnings_path.is_file())

        iteration_dir = campaign.iteration_dir(result["iteration"])
        snapshot = json.loads((iteration_dir / "manifest.snapshot.json").read_text())
        self.assertEqual(snapshot["status"], result["verdict"])
        self.assertNotIn("attribution", snapshot)
        if expected_submission is _UNSET:
            self.assertNotIn("record_type", snapshot)
        else:
            self.assertEqual(snapshot["record_type"], "rejected_submission")
            self.assertEqual(snapshot["original_submission"], expected_submission)
            self.assertEqual(snapshot["verdict"]["label"], result["verdict"])
            self.assertEqual(snapshot["verdict"]["decision"], "rejected")
            self.assertFalse(snapshot["verdict"]["advances_accepted_state"])
            self.assertTrue(snapshot["validation_errors"])
            if expected_error is not None:
                self.assertIn(expected_error, snapshot["validation_errors"])
        if EXPERIMENT_VALIDATOR is not None:
            schema_errors = list(EXPERIMENT_VALIDATOR.iter_errors(snapshot))
            self.assertEqual(
                schema_errors,
                [],
                [error.message for error in schema_errors],
            )
        return json.loads((iteration_dir / "gate-report.json").read_text())

    # ── an untrusted no-trace command bridge cannot advance state ────────
    def test_no_trace_command_bridge_does_not_advance_state(self) -> None:
        campaign = self._new_campaign("cmp", self._command_adapter())
        self._register_admissions(campaign)
        base_before = campaign.state["accepted_base_sha"]
        measure_noise(campaign, runs=2)

        started = start_iteration(campaign)
        self.assertIn(
            "edit only the frozen candidate surface(s) harness/components/",
            started["instructions"],
        )
        packet_path = Path(started["packet"])
        packet = packet_path.read_text()
        self.assertIn("frozen candidate allowlist: `harness/components/`", packet)
        self.assertIn("`target_component` is attribution only", packet)
        self.assertEqual(
            json.loads((packet_path.parent / "packet.json").read_text())[
                "candidate_allowlist"
            ],
            ["harness/components/"],
        )
        wt = Path(started["worktree"])
        self._commit_quality(wt, "0.70\n")
        self._write_manifest(wt, predicted=self.flipping[:2])
        result = run_iteration(campaign)

        self.assertEqual(result["decision"], "invalid")
        self.assertEqual(result["evidence_class"], "simulated")
        self.assertFalse(result["advanced_accepted_state"])
        reloaded = load_campaign(self.repo, "cmp", store_root=self.store)
        self.assertEqual(reloaded.state["accepted_base_sha"], base_before)
        self.assertEqual(reloaded.state["accepted_iterations"], [])
        # worktree destroyed after the transaction (boundary reset).
        self.assertFalse(campaign.worktree_path.exists())
        gate = json.loads((campaign.iteration_dir(1) / "gate-report.json").read_text())
        self.assertEqual(
            [(r["rung"], r["status"]) for r in gate["rungs"]],
            [("E0", "pass"), ("E1", "invalid")],
        )
        self.assertIsNone(gate["eligibility"])

    # ── F01: committed forbidden edit is rejected ────────────────────────
    def test_committed_forbidden_edit_rejected(self) -> None:
        campaign = self._new_campaign("cmp", self._command_adapter())
        self._register_admissions(campaign)
        measure_noise(campaign, runs=2)
        wt = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(wt, "0.70\n")
        (wt / "evals/plane.txt").write_text("tampered\n")  # eval-plane edit...
        _git(wt, "add", "-A")
        _git(wt, "commit", "-qm", "sneaky")  # ...committed (the F01 bypass)
        self._write_manifest(wt, predicted=self.flipping[:1])
        submitted = json.loads((wt / "manifest.json").read_text())
        result = run_iteration(campaign)
        self.assertEqual(result["decision"], "rejected")
        self.assertFalse(result["advanced_accepted_state"])
        receipt = json.loads(
            (campaign.store.campaign_dir / "accepted-publication.json").read_text()
        )
        self.assertEqual(receipt["status"], "complete")
        ledger = json.loads(campaign.ledger_path.read_text())
        self.assertEqual(ledger["decision"], "rejected")
        learning = read_records(
            campaign.learnings_path, campaign_root=campaign.store.campaign_dir
        )
        self.assertEqual(len(learning), 1)
        self.assertEqual(learning[0]["decision"]["decision"], "rejected")
        snapshot_path = campaign.iteration_dir(1) / "manifest.snapshot.json"
        snapshot = json.loads(snapshot_path.read_text())
        self.assertEqual(snapshot["record_type"], "rejected_submission")
        self.assertEqual(snapshot["original_submission"], submitted)
        self.assertTrue(snapshot["validation_errors"])
        self.assertTrue(any(
            "outside optimizer surface" in error
            for error in snapshot["validation_errors"]
        ))
        self.assertEqual(publication_status(campaign)["status"], "complete")
        self.assertEqual(run_iteration(campaign), result)

        snapshot["original_submission"]["hypothesis"] = "forged submission"
        snapshot_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
        self.assertEqual(publication_status(campaign)["status"], "malformed")
        with self.assertRaisesRegex(RuntimeError, "manifest snapshot digest"):
            run_iteration(campaign)

    def test_rejected_snapshot_requires_exact_immediate_e0_admissibility_detail(self) -> None:
        def gate(detail, *, rung="E0", status="fail", trailing=None):
            rungs = [{"rung": rung, "status": status, "detail": detail}]
            if trailing is not None:
                rungs.append(trailing)
            return {"rungs": rungs}

        self.assertEqual(
            _publication_rejection_errors(
                gate({"manifest_errors": ["missing required field: hypothesis"]})
            ),
            ["missing required field: hypothesis"],
        )
        guard = {
            "changed": ["evals/plane.txt"],
            "violations": ["path outside optimizer surface: evals/plane.txt"],
            "dirty_worktree": [],
            "ok": False,
        }
        self.assertEqual(
            _publication_rejection_errors(gate(guard)),
            ["path outside optimizer surface: evals/plane.txt"],
        )
        malformed = {
            "extra": {"manifest_errors": ["bad"], "unexpected": True},
            "malformed": {"manifest_errors": ["bad", 7]},
            "mixed": {"manifest_errors": ["bad"], **guard},
            "partial guard": {"changed": [], "violations": ["bad"], "ok": False},
        }
        for label, detail in malformed.items():
            with self.subTest(label=label), self.assertRaisesRegex(
                RuntimeError, "E0"
            ):
                _publication_rejection_errors(gate(detail))
        self.assertEqual(
            _publication_rejection_errors(
                gate({"manifest_errors": ["unrelated"]}, rung="E1")
            ),
            [],
        )
        self.assertEqual(
            _publication_rejection_errors(
                gate(
                    {"manifest_errors": ["not immediate"]},
                    trailing={"rung": "E1", "status": "fail", "detail": {}},
                )
            ),
            [],
        )
        self.assertEqual(
            _publication_rejection_errors(gate({"generality_lint": []})),
            [],
        )

    # ── F02: a forged gate report cannot cause acceptance ────────────────
    def test_forged_gate_report_is_ignored(self) -> None:
        campaign = self._new_campaign("cmp", self._command_adapter())
        self._register_admissions(campaign)
        measure_noise(campaign, runs=2)
        started = start_iteration(campaign)
        wt = Path(started["worktree"])
        # Pre-plant a forged "accepted" gate report in the store iteration dir.
        forged = campaign.iteration_dir(1) / "gate-report.json"
        forged.write_text(json.dumps({"verdict": {"decision": "accepted", "evidence_class": "benchmark",
                                                   "advances_accepted_state": True}}))
        # Optimizer makes NO commit and writes NO manifest — yet a forged
        # "accepted" report sits in the store. The transaction must recompute.
        self.assertTrue(wt.exists())
        result = run_iteration(campaign)
        # The transaction recomputes the verdict itself; the forgery is overwritten.
        self.assertFalse(result["advanced_accepted_state"])
        self.assertNotEqual(result["decision"], "accepted")

    # ── F04: a simulated (fixture) acceptance never advances real state ──
    def test_simulated_acceptance_does_not_advance(self) -> None:
        campaign = self._new_campaign("sim", {"kind": "harness-fixture", "file": QUALITY_REL,
                                              "default_pass_rate": 0.55, "seed": 0})
        base_before = campaign.state["accepted_base_sha"]
        measure_noise(campaign, runs=2)
        wt = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(wt, "0.70\n")
        self._write_manifest(wt, predicted=self.flipping[:2])
        result = run_iteration(campaign)
        self.assertEqual(result["decision"], "accepted")
        self.assertEqual(result["evidence_class"], "simulated")
        self.assertFalse(result["advanced_accepted_state"])  # the F04 property
        reloaded = load_campaign(self.repo, "sim", store_root=self.store)
        self.assertEqual(reloaded.state["accepted_base_sha"], base_before)
        self.assertEqual(reloaded.state["accepted_iterations"], [])
        gate = json.loads((campaign.iteration_dir(1) / "gate-report.json").read_text())
        activation = next(r for r in gate["rungs"] if r["rung"] == "E1")["detail"][
            "observed_activation"
        ]
        self.assertEqual(activation["path"], QUALITY_REL)
        self.assertEqual(activation["parsed_value"], 0.70)
        self.assertEqual(activation["baseline_parsed_value"], 0.55)
        treatment_roots = set()
        for name in (
            "smoke_treatment", "targeted_screen", "regression_treatment", "dev_treatment"
        ):
            run_record = json.loads(
                (campaign.iteration_dir(1) / "eval" / name / "run.json").read_text()
            )
            self.assertEqual(
                run_record["run_context"]["build"]["commit_sha"], json.loads(
                    campaign.ledger_path.read_text().splitlines()[-1]
                )["candidate_sha"]
            )
            self.assertIn("/materializations/build-", run_record["repo_root"])
            treatment_roots.add(run_record["repo_root"])
        self.assertEqual(len(treatment_roots), 1)
        self.assertTrue((campaign.iteration_dir(1) / "candidate.bundle").is_file())

    def test_warc_online4_local_fixture_traverses_real_seam_and_is_state_inert(self) -> None:
        campaign, _config_path = self._new_warc_campaign("warc-local")
        base_before = campaign.state["accepted_base_sha"]
        measure_noise(campaign, runs=2)
        worktree = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(worktree, "0.550\n")
        self._write_manifest(worktree, predicted=["warc-bench-online-4"])

        result = run_iteration(campaign)

        self.assertEqual(result["decision"], "rejected")
        self.assertEqual(result["evidence_class"], "simulated")
        self.assertFalse(result["advanced_accepted_state"])
        reloaded = load_campaign(self.repo, campaign.campaign_id, store_root=self.store)
        self.assertEqual(reloaded.state["accepted_base_sha"], base_before)
        self.assertEqual(reloaded.state["accepted_iterations"], [])
        gate = json.loads((campaign.iteration_dir(1) / "gate-report.json").read_text())
        self.assertEqual(
            [(rung["rung"], rung["status"]) for rung in gate["rungs"]],
            [("E0", "pass"), ("E1", "pass"), ("E2", "pass"), ("E3", "fail")],
        )
        activation = gate["rungs"][1]["detail"]["observed_activation"]
        self.assertEqual(activation["path"], QUALITY_REL)
        self.assertNotEqual(activation["sha256"], activation["baseline_sha256"])
        for name in ("smoke_treatment", "targeted_screen"):
            result_row = json.loads(
                (campaign.iteration_dir(1) / "eval" / name / "results.jsonl")
                .read_text()
                .splitlines()[0]
            )
            self.assertEqual(result_row["metadata"]["evidence_class"], "local_fixture")
            self.assertFalse(result_row["metadata"]["benchmark_reportable"])
            self.assertTrue(result_row["metadata"]["cleanup_completed"])
            self.assertEqual(result_row["task_id"], "warc-bench-online-4")
            self.assertEqual(result_row["trace_path"], "trace.jsonl")
            self.assertTrue(result_row["artifacts"])

    def test_warc_cli_init_start_projects_model_aliases_and_reaches_local_seam(self) -> None:
        campaign, _config_path = self._new_warc_campaign(
            "warc-cli-local", via_cli=True
        )
        executor = campaign.config["identity"]["executor"]
        self.assertEqual(executor["snapshot"], executor["model"])
        self.assertEqual(executor["revision"], executor["model"])
        base_before = campaign.state["accepted_base_sha"]
        measure_noise(campaign, runs=2)

        self.assertEqual(
            cli_main([
                "--repo-root", str(self.repo),
                "--store-root", str(self.store),
                "start", "--campaign", campaign.campaign_id,
            ]),
            0,
        )
        campaign = load_campaign(
            self.repo, campaign.campaign_id, store_root=self.store
        )
        worktree = campaign.worktree_path
        self._commit_quality(worktree, "0.550\n")
        self._write_manifest(worktree, predicted=["warc-bench-online-4"])
        self.assertEqual(
            cli_main([
                "--repo-root", str(self.repo),
                "--store-root", str(self.store),
                "run-iteration", "--campaign", campaign.campaign_id,
            ]),
            1,
        )

        reloaded = load_campaign(
            self.repo, campaign.campaign_id, store_root=self.store
        )
        self.assertEqual(reloaded.state["accepted_base_sha"], base_before)
        self.assertEqual(reloaded.state["accepted_iterations"], [])
        result_row = json.loads(
            (
                campaign.iteration_dir(1)
                / "eval/smoke_treatment/results.jsonl"
            ).read_text().splitlines()[0]
        )
        self.assertEqual(result_row["metadata"]["evidence_class"], "local_fixture")
        self.assertFalse(result_row["metadata"]["benchmark_reportable"])

    def test_warc_echo_only_activation_is_invalid_in_normal_traversal(self) -> None:
        campaign, _config_path = self._new_warc_campaign("warc-echo-only")
        base_before = campaign.state["accepted_base_sha"]
        measure_noise(campaign, runs=2)
        worktree = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(worktree, "0.550\n")
        self._write_manifest(worktree, predicted=["warc-bench-online-4"])

        with mock.patch(
            "opti_eval.adapters.warc_online4.run_lifecycle",
            side_effect=_warc_echo_only_lifecycle,
        ):
            result = run_iteration(campaign)

        self.assertEqual(result["decision"], "invalid")
        self.assertFalse(result["advanced_accepted_state"])
        reloaded = load_campaign(self.repo, campaign.campaign_id, store_root=self.store)
        self.assertEqual(reloaded.state["accepted_base_sha"], base_before)
        gate = json.loads((campaign.iteration_dir(1) / "gate-report.json").read_text())
        self.assertEqual(gate["rungs"][1]["rung"], "E1")
        self.assertEqual(gate["rungs"][1]["status"], "invalid")

    def test_warc_dropped_treatment_is_invalid_in_normal_traversal(self) -> None:
        campaign, _config_path = self._new_warc_campaign("warc-dropped-treatment")
        base_before = campaign.state["accepted_base_sha"]
        measure_noise(campaign, runs=2)
        worktree = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(worktree, "0.550\n")
        self._write_manifest(worktree, predicted=["warc-bench-online-4"])

        with mock.patch(
            "opti_eval.adapters.warc_online4.run_lifecycle",
            side_effect=_warc_dropped_treatment_lifecycle,
        ):
            result = run_iteration(campaign)

        self.assertEqual(result["decision"], "invalid")
        self.assertFalse(result["advanced_accepted_state"])
        reloaded = load_campaign(self.repo, campaign.campaign_id, store_root=self.store)
        self.assertEqual(reloaded.state["accepted_base_sha"], base_before)
        gate = json.loads((campaign.iteration_dir(1) / "gate-report.json").read_text())
        self.assertEqual(gate["rungs"][1]["status"], "invalid")

    def test_all_simulated_terminal_decisions_preserve_continuation_counters(self) -> None:
        for decision in ("accepted", "rejected", "invalid"):
            with self.subTest(decision=decision):
                campaign = self._new_campaign(
                    f"inertia-{decision}",
                    {"kind": "harness-fixture", "file": QUALITY_REL,
                     "default_pass_rate": 0.55, "seed": 0},
                )
                worktree = Path(start_iteration(campaign)["worktree"])
                campaign.state["iterations_since_accept"] = 7
                campaign.state["iterations_since_divergent"] = 9
                campaign.state["failed_attempts"] = {"sentinel::policy": 4}
                campaign.save_state()
                self._commit_quality(worktree, "0.70\n")
                self._write_manifest(worktree, predicted=self.flipping[:1])
                report = GateReport(iteration=1)
                report.verdict = Verdict(decision, "simulated")

                with mock.patch("opti_loop.conductor.run_gate", return_value=report):
                    result = run_iteration(campaign)

                self.assertEqual(result["decision"], decision)
                reloaded = load_campaign(
                    self.repo, campaign.campaign_id, store_root=self.store
                )
                self.assertEqual(reloaded.state["iterations_since_accept"], 7)
                self.assertEqual(reloaded.state["iterations_since_divergent"], 9)
                self.assertEqual(
                    reloaded.state["failed_attempts"], {"sentinel::policy": 4}
                )
                self.assertEqual(reloaded.state["pending_iteration"], 0)

    def test_invalid_fixture_rates_finish_e1_invalid_and_reset(self) -> None:
        for value in ("2.0\n", "NaN\n", "Infinity\n"):
            with self.subTest(value=value.strip()):
                campaign = self._new_campaign(
                    f"bad-rate-{value.strip().lower()}",
                    {"kind": "harness-fixture", "file": QUALITY_REL,
                     "default_pass_rate": 0.55, "seed": 0},
                )
                worktree = Path(start_iteration(campaign)["worktree"])
                self._commit_quality(worktree, value)
                self._write_manifest(worktree, predicted=self.flipping[:1])

                result = run_iteration(campaign)

                self.assertEqual(result["decision"], "invalid")
                gate = json.loads(
                    (campaign.iteration_dir(1) / "gate-report.json").read_text()
                )
                self.assertEqual(gate["rungs"][-1]["rung"], "E1")
                self.assertEqual(gate["rungs"][-1]["status"], "invalid")
                self.assertTrue((campaign.iteration_dir(1) / "manifest.snapshot.json").is_file())
                self.assertTrue(campaign.ledger_path.is_file())
                self.assertEqual(campaign.state["pending_iteration"], 0)

    def test_expected_smoke_evaluation_failure_finishes_e1_invalid(self) -> None:
        campaign = self._new_campaign(
            "evaluation-failure",
            {"kind": "harness-fixture", "file": QUALITY_REL,
             "default_pass_rate": 0.55, "seed": 0},
        )
        worktree = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(worktree, "0.70\n")
        self._write_manifest(worktree, predicted=self.flipping[:1])
        with mock.patch("opti_loop.gates.run_suite", side_effect=OSError("disk full")):
            result = run_iteration(campaign)

        self.assertEqual(result["decision"], "invalid")
        gate = json.loads((campaign.iteration_dir(1) / "gate-report.json").read_text())
        self.assertEqual([(r["rung"], r["status"]) for r in gate["rungs"]],
                         [("E0", "pass"), ("E1", "invalid")])
        self.assertIn("disk full", gate["rungs"][-1]["detail"]["error"])
        self.assertEqual(campaign.state["pending_iteration"], 0)

    def test_expected_regression_evaluation_failure_stays_at_e4(self) -> None:
        from opti_loop.evaluate import run_suite as real_run_suite

        campaign = self._new_campaign(
            "e4-evaluation-failure",
            {"kind": "harness-fixture", "file": QUALITY_REL,
             "default_pass_rate": 0.55, "seed": 0},
        )
        worktree = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(worktree, "0.70\n")
        self._write_manifest(worktree, predicted=[])
        calls = 0

        def fail_regression(**kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise ValueError("regression evaluation unavailable")
            return real_run_suite(**kwargs)

        with mock.patch("opti_loop.gates.run_suite", side_effect=fail_regression):
            result = run_iteration(campaign)

        self.assertEqual(result["decision"], "invalid")
        gate = json.loads((campaign.iteration_dir(1) / "gate-report.json").read_text())
        self.assertEqual(gate["rungs"][-1]["rung"], "E4")
        self.assertEqual(gate["rungs"][-1]["status"], "invalid")
        self.assertIn("regression evaluation unavailable", gate["rungs"][-1]["detail"]["error"])
        self.assertEqual(campaign.state["pending_iteration"], 0)

    def test_unexpected_gate_exceptions_propagate_without_e1_evidence(self) -> None:
        cases = (
            ("materialization", MaterializationError("gate materialization defect")),
            ("value", ValueError("gate value defect")),
            ("filesystem", OSError("gate filesystem defect")),
        )
        for label, error in cases:
            with self.subTest(error=label):
                campaign = self._new_campaign(
                    f"gate-defect-{label}",
                    {"kind": "harness-fixture", "file": QUALITY_REL,
                     "default_pass_rate": 0.55, "seed": 0},
                )
                worktree = Path(start_iteration(campaign)["worktree"])
                self._commit_quality(worktree, "0.70\n")
                self._write_manifest(worktree, predicted=self.flipping[:1])
                state_before = json.loads(json.dumps(campaign.state))
                ledger_before = campaign.ledger_path.read_bytes()
                with (
                    mock.patch("opti_loop.conductor.run_gate", side_effect=error),
                    self.assertRaisesRegex(type(error), str(error)),
                ):
                    run_iteration(campaign)

                reloaded = load_campaign(
                    self.repo, campaign.campaign_id, store_root=self.store
                )
                self.assertIsInstance(
                    reloaded.state["pending_repeated_started_at"], float
                )
                reloaded.state["pending_repeated_started_at"] = state_before[
                    "pending_repeated_started_at"
                ]
                state_before["operation_attempts"] += 1
                state_before["active_attempt_iteration"] = 1
                state_before["lifecycle"] = {
                    "schema_version": "0.1.0",
                    "state": "running",
                    "request": "run",
                }
                self.assertEqual(reloaded.state, state_before)
                self.assertEqual(campaign.ledger_path.read_bytes(), ledger_before)
                self.assertFalse(
                    (campaign.iteration_dir(1) / "gate-report.json").exists()
                )
                self.assertFalse(
                    (campaign.iteration_dir(1) / "manifest.snapshot.json").exists()
                )

    def test_e0_lint_filesystem_defect_propagates_without_e1_relabel(self) -> None:
        campaign = self._new_campaign(
            "lint-filesystem-defect",
            {"kind": "harness-fixture", "file": QUALITY_REL,
             "default_pass_rate": 0.55, "seed": 0},
        )
        worktree = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(worktree, "0.70\n")
        self._write_manifest(worktree, predicted=self.flipping[:1])
        with (
            mock.patch(
                "opti_loop.gates.lint.scan_tree",
                side_effect=OSError("lint tree unreadable"),
            ),
            self.assertRaisesRegex(OSError, "lint tree unreadable"),
        ):
            run_iteration(campaign)

        self.assertEqual(campaign.state["pending_iteration"], 1)
        self.assertFalse((campaign.iteration_dir(1) / "gate-report.json").exists())

    def test_expected_registration_preflight_failure_finishes_e1_invalid(self) -> None:
        campaign = self._new_campaign(
            "registration-failure",
            {"kind": "harness-fixture", "file": QUALITY_REL,
             "default_pass_rate": 0.55, "seed": 0},
        )
        worktree = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(worktree, "0.70\n")
        self._write_manifest(worktree, predicted=self.flipping[:1])
        with (
            mock.patch(
                "opti_loop.gates.registration.check_change_registered",
                side_effect=OSError("registration unreadable"),
            ),
            mock.patch("opti_loop.gates.run_suite") as treatment_run,
        ):
            result = run_iteration(campaign)

        self.assertEqual(result["decision"], "invalid")
        treatment_run.assert_not_called()
        gate = json.loads((campaign.iteration_dir(1) / "gate-report.json").read_text())
        self.assertIn("registration unreadable", gate["rungs"][-1]["detail"]["error"])
        self.assertEqual(campaign.state["pending_iteration"], 0)

    def test_malformed_component_registrations_finish_real_e1_invalid(self) -> None:
        valid = json.loads(
            (self.repo / "harness/components/policy/component.json").read_text()
        )
        null_files = {**valid, "files": None}
        invalid_items = {**valid, "files": [["quality.txt"], 7]}
        unknown_missing = {
            "component": "policy",
            "files": ["quality.txt"],
            "unknown": True,
        }
        duplicate = json.dumps(valid).replace(
            '"files": [', '"files": ["quality.txt"], "files": [', 1
        )
        constant = json.dumps(valid).replace(
            '"files": [', '"files": [NaN, ', 1
        )
        cases = {
            "list": "[]",
            "scalar": "null",
            "null-files": json.dumps(null_files),
            "invalid-items": json.dumps(invalid_items),
            "duplicate-key": duplicate,
            "non-json-number": constant,
            "unknown-missing": json.dumps(unknown_missing),
        }
        registration_rel = "harness/components/policy/component.json"
        for label, raw in cases.items():
            with self.subTest(registration=label):
                campaign = self._new_campaign(
                    f"malformed-registration-{label}",
                    {"kind": "harness-fixture", "file": QUALITY_REL,
                     "default_pass_rate": 0.55, "seed": 0},
                )
                worktree = Path(start_iteration(campaign)["worktree"])
                (worktree / QUALITY_REL).write_text("0.70\n")
                (worktree / registration_rel).write_text(raw)
                _git(worktree, "add", "-A")
                _git(worktree, "commit", "-qm", f"malformed registration {label}")
                self._write_manifest(worktree, predicted=self.flipping[:1])
                submitted = json.loads((worktree / "manifest.json").read_text())
                submitted["treatment"]["change_scope"] = [
                    QUALITY_REL,
                    registration_rel,
                ]
                (worktree / "manifest.json").write_text(json.dumps(submitted))

                result = run_iteration(campaign)

                self.assertEqual(result["decision"], "invalid")
                self.assertFalse(result["advanced_accepted_state"])
                gate = json.loads(
                    (campaign.iteration_dir(1) / "gate-report.json").read_text()
                )
                self.assertEqual(
                    [(rung["rung"], rung["status"]) for rung in gate["rungs"]],
                    [("E0", "pass"), ("E1", "invalid")],
                )
                self.assertTrue(gate["rungs"][-1]["detail"]["errors"])
                snapshot = json.loads(
                    (campaign.iteration_dir(1) / "manifest.snapshot.json").read_text()
                )
                self.assertEqual(snapshot["status"], "simulated:invalid")
                self.assertEqual(campaign.state["pending_iteration"], 0)
                self.assertFalse(campaign.worktree_path.exists())

    def test_unsupported_adapter_is_e1_invalid_before_treatment_execution(self) -> None:
        campaign = self._new_campaign("unsupported", self._command_adapter())
        worktree = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(worktree, "0.70\n")
        self._write_manifest(worktree, predicted=self.flipping[:1])
        with mock.patch("opti_loop.gates.run_suite") as treatment_run:
            result = run_iteration(campaign)

        self.assertEqual(result["decision"], "invalid")
        treatment_run.assert_not_called()
        gate = json.loads((campaign.iteration_dir(1) / "gate-report.json").read_text())
        self.assertEqual([(r["rung"], r["status"]) for r in gate["rungs"]],
                         [("E0", "pass"), ("E1", "invalid")])

    def test_missing_activation_is_invalid_and_stops_later_treatment_runs(self) -> None:
        campaign = self._new_campaign(
            "missing-activation",
            {"kind": "harness-fixture", "file": "harness/components/policy/missing.txt",
             "default_pass_rate": 0.55, "seed": 0},
        )
        measure_noise(campaign, runs=2)
        worktree = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(worktree, "0.70\n")
        self._write_manifest(worktree, predicted=self.flipping[:1])

        result = run_iteration(campaign)

        self.assertEqual(result["decision"], "invalid")
        gate = json.loads((campaign.iteration_dir(1) / "gate-report.json").read_text())
        self.assertEqual([(r["rung"], r["status"]) for r in gate["rungs"]],
                         [("E0", "pass"), ("E1", "invalid")])
        self.assertTrue((campaign.iteration_dir(1) / "eval/smoke_treatment").is_dir())
        for later in ("targeted_screen", "regression_treatment", "dev_treatment"):
            self.assertFalse((campaign.iteration_dir(1) / "eval" / later).exists())

    def test_baseline_only_noop_activation_is_invalid(self) -> None:
        campaign = self._new_campaign(
            "noop-activation",
            {"kind": "harness-fixture", "file": QUALITY_REL,
             "default_pass_rate": 0.55, "seed": 0},
        )
        measure_noise(campaign, runs=2)
        worktree = Path(start_iteration(campaign)["worktree"])
        self._commit_registration_only(worktree)
        self._write_manifest(worktree, predicted=self.flipping[:1])
        manifest = json.loads((worktree / "manifest.json").read_text())
        manifest["treatment"]["change_scope"] = [
            "harness/components/policy/component.json"
        ]
        (worktree / "manifest.json").write_text(json.dumps(manifest))

        result = run_iteration(campaign)

        self.assertEqual(result["decision"], "invalid")
        report = json.loads((campaign.iteration_dir(1) / "gate-report.json").read_text())
        errors = report["rungs"][-1]["detail"]["errors"]
        self.assertIn("configured candidate behavior file was not changed", " ".join(errors))

    def test_behavior_neutral_mode_change_reaches_decision_path(self) -> None:
        campaign = self._new_campaign(
            "mode-only",
            {"kind": "harness-fixture", "file": QUALITY_REL,
             "default_pass_rate": 0.55, "seed": 0},
        )
        measure_noise(campaign, runs=2)
        worktree = Path(start_iteration(campaign)["worktree"])
        (worktree / QUALITY_REL).chmod(0o755)
        _git(worktree, "add", QUALITY_REL)
        _git(worktree, "commit", "-qm", "mode only")
        self._write_manifest(worktree, predicted=self.flipping[:1])

        result = run_iteration(campaign)

        self.assertEqual(result["decision"], "rejected")
        gate = json.loads((campaign.iteration_dir(1) / "gate-report.json").read_text())
        self.assertEqual([(r["rung"], r["status"]) for r in gate["rungs"]],
                         [("E0", "pass"), ("E1", "pass"), ("E2", "pass"),
                          ("E3", "fail")])
        activation = gate["rungs"][1]["detail"]["observed_activation"]
        self.assertEqual(activation["sha256"], activation["baseline_sha256"])
        self.assertEqual(
            activation["parsed_value"], activation["baseline_parsed_value"]
        )

    def test_behavior_neutral_candidate_bytes_reach_decision_path(self) -> None:
        campaign = self._new_campaign(
            "numeric-noop",
            {"kind": "harness-fixture", "file": QUALITY_REL,
             "default_pass_rate": 0.55, "seed": 0},
        )
        measure_noise(campaign, runs=2)
        worktree = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(worktree, "0.550\n")
        self._write_manifest(worktree, predicted=self.flipping[:1])

        result = run_iteration(campaign)

        self.assertEqual(result["decision"], "rejected")
        gate = json.loads((campaign.iteration_dir(1) / "gate-report.json").read_text())
        self.assertEqual([(r["rung"], r["status"]) for r in gate["rungs"]],
                         [("E0", "pass"), ("E1", "pass"), ("E2", "pass"),
                          ("E3", "fail")])
        activation = gate["rungs"][1]["detail"]["observed_activation"]
        self.assertNotEqual(activation["sha256"], activation["baseline_sha256"])
        self.assertEqual(
            activation["parsed_value"], activation["baseline_parsed_value"]
        )

    def test_missing_trusted_baseline_observation_is_invalid(self) -> None:
        campaign = self._new_campaign(
            "missing-baseline-observation",
            {"kind": "harness-fixture", "file": QUALITY_REL,
             "default_pass_rate": 0.55, "seed": 0},
        )
        measure_noise(campaign, runs=2)
        worktree = Path(start_iteration(campaign)["worktree"])
        campaign.state["pending_baseline_activation_observation"] = None
        campaign.save_state()
        self._commit_quality(worktree, "0.70\n")
        self._write_manifest(worktree, predicted=self.flipping[:1])

        result = run_iteration(campaign)

        self.assertEqual(result["decision"], "invalid")
        gate = json.loads((campaign.iteration_dir(1) / "gate-report.json").read_text())
        self.assertIn("baseline observation is missing", " ".join(
            gate["rungs"][-1]["detail"]["errors"]
        ))

    def test_wrong_path_activation_is_invalid(self) -> None:
        campaign = self._new_campaign(
            "wrong-path",
            {"kind": "harness-fixture", "file": QUALITY_REL,
             "default_pass_rate": 0.55, "seed": 0},
        )
        measure_noise(campaign, runs=2)
        worktree = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(worktree, "0.70\n")
        self._write_manifest(worktree, predicted=self.flipping[:1])
        from opti_loop import evaluate as evaluate_module
        real_build_adapter = evaluate_module.build_adapter

        def wrong_path(*args, **kwargs):
            adapter = real_build_adapter(*args, **kwargs)
            if getattr(adapter, "activation_observation", None):
                adapter.activation_observation["path"] = (
                    "harness/components/policy/baseline.txt"
                )
            return adapter

        with mock.patch("opti_loop.evaluate.build_adapter", side_effect=wrong_path):
            result = run_iteration(campaign)
        self.assertEqual(result["decision"], "invalid")
        self.assertFalse(result["advanced_accepted_state"])

    def test_materialization_tamper_before_consumption_is_invalid(self) -> None:
        campaign = self._new_campaign(
            "tamper-before",
            {"kind": "harness-fixture", "file": QUALITY_REL,
             "default_pass_rate": 0.55, "seed": 0},
        )
        measure_noise(campaign, runs=2)
        worktree = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(worktree, "0.70\n")
        self._write_manifest(worktree, predicted=self.flipping[:1])
        from opti_loop import conductor as conductor_module
        real_materialize = conductor_module.materialize_candidate_bundle

        def tamper(*args, **kwargs):
            materialization, receipt = real_materialize(*args, **kwargs)
            target = materialization / "tree" / QUALITY_REL
            target.chmod(0o644)
            target.write_text("0.99\n")
            return materialization, receipt

        with mock.patch("opti_loop.conductor.materialize_candidate_bundle", side_effect=tamper):
            result = run_iteration(campaign)
        self.assertEqual(result["decision"], "invalid")

    def test_materialization_tamper_after_consumption_is_invalid(self) -> None:
        campaign = self._new_campaign(
            "tamper-after",
            {"kind": "harness-fixture", "file": QUALITY_REL,
             "default_pass_rate": 0.55, "seed": 0},
        )
        measure_noise(campaign, runs=2)
        worktree = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(worktree, "0.70\n")
        self._write_manifest(worktree, predicted=self.flipping[:1])
        from opti_loop import gates as gates_module
        real_run_suite = gates_module.run_suite
        changed = False

        def tamper(*args, **kwargs):
            nonlocal changed
            run = real_run_suite(*args, **kwargs)
            root = Path(kwargs["repo_root"])
            if not changed and root.parent.name.startswith("build-"):
                target = root / QUALITY_REL
                target.chmod(0o644)
                target.write_text("0.99\n")
                changed = True
            return run

        with mock.patch("opti_loop.gates.run_suite", side_effect=tamper):
            result = run_iteration(campaign)
        self.assertEqual(result["decision"], "invalid")

    def test_benchmark_requires_separately_owned_optimizer_bundle(self) -> None:
        campaign = self._new_campaign(
            "benchmark-handoff",
            {"kind": "harness-fixture", "file": QUALITY_REL,
             "default_pass_rate": 0.55, "seed": 0},
        )
        iteration_dir = campaign.iteration_dir(1)
        iteration_dir.mkdir(parents=True)
        self.assertEqual(
            _optimizer_bundle(
                campaign,
                supplied_bundle=None,
                supplied_manifest=None,
                evidence_mode="benchmark",
            ),
            (None, None),
        )
        same_uid = iteration_dir / "candidate.bundle"
        same_uid.write_bytes(b"not read because ownership fails first")
        sidecar = iteration_dir / "manifest.json"
        sidecar.write_text("{}")
        with self.assertRaisesRegex(MaterializationError, "separate optimizer UID"):
            _validate_benchmark_handback_ownership(
                bundle_info=same_uid.stat(),
                manifest_info=sidecar.stat(),
                parent_info=iteration_dir.stat(),
            )

    def test_bounded_bundle_snapshot_rejects_append_and_shortening(self) -> None:
        for mutation in ("append", "shorten"):
            with self.subTest(mutation=mutation):
                source = Path(self._tmp.name) / f"{mutation}.bundle"
                destination = Path(self._tmp.name) / f"{mutation}.trusted.bundle"
                source.write_bytes(b"a" * (128 * 1024))
                descriptor = os.open(source, os.O_RDWR | os.O_NOFOLLOW)
                real_read = os.read
                mutated = False

                def mutating_read(fd, count):
                    nonlocal mutated
                    chunk = real_read(fd, count)
                    if not mutated:
                        mutated = True
                        if mutation == "append":
                            with source.open("ab") as handle:
                                handle.write(b"later bytes")
                        else:
                            os.truncate(source, 0)
                    return chunk

                try:
                    with (
                        mock.patch("opti_loop.conductor.os.read", side_effect=mutating_read),
                        self.assertRaisesRegex(
                            MaterializationError, "changed|shorter"
                        ),
                    ):
                        _copy_benchmark_bundle(
                            descriptor,
                            destination,
                            optimizer_uid=os.getuid(),
                        )
                finally:
                    os.close(descriptor)
                self.assertFalse(destination.exists())

    def test_manifest_snapshot_rejects_oversize_before_reading(self) -> None:
        path = Path(self._tmp.name) / "oversize-manifest.json"
        path.write_bytes(b" " * (MAX_MANIFEST_BYTES + 1))
        submitted, report = _read_manifest_snapshot(path)
        self.assertIsNone(submitted)
        self.assertFalse(report.ok)
        self.assertIn("byte limit", " ".join(report.errors))

    def test_campaign_lock_prevents_duplicate_pending_iteration_consumption(self) -> None:
        campaign = self._new_campaign(
            "transaction-lock",
            {"kind": "harness-fixture", "file": QUALITY_REL,
             "default_pass_rate": 0.55, "seed": 0},
        )
        worktree = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(worktree, "0.70\n")
        self._write_manifest(worktree, predicted=self.flipping[:1])
        materialization_store = campaign.store.campaign_dir / "materializations"
        materialization_store.mkdir(mode=0o700, exist_ok=True)
        with CampaignLock(materialization_store):
            with self.assertRaisesRegex(MaterializationError, "held by another process"):
                run_iteration(campaign)

        reloaded = load_campaign(self.repo, campaign.campaign_id, store_root=self.store)
        self.assertEqual(reloaded.state["pending_iteration"], 1)
        self.assertFalse((campaign.iteration_dir(1) / "gate-report.json").exists())
        result = run_iteration(campaign)
        self.assertEqual(result["iteration"], 1)
        self.assertEqual(len(campaign.ledger_path.read_text().splitlines()), 1)

    def test_strict_manifest_rejects_duplicate_keys_and_non_json_numbers_at_e0(self) -> None:
        cases = {
            "duplicate": ', "hypothesis": "duplicate"}',
            "nan": ', "extra": NaN}',
            "infinity": ', "extra": Infinity}',
        }
        for label, suffix in cases.items():
            with self.subTest(label=label):
                campaign = self._new_campaign(
                    f"strict-{label}",
                    {"kind": "harness-fixture", "file": QUALITY_REL,
                     "default_pass_rate": 0.55, "seed": 0},
                )
                worktree = Path(start_iteration(campaign)["worktree"])
                self._commit_quality(worktree, "0.70\n")
                self._write_manifest(worktree, predicted=self.flipping[:1])
                raw = (worktree / "manifest.json").read_text()
                (worktree / "manifest.json").write_text(raw[:-1] + suffix)
                with mock.patch(
                    "opti_loop.conductor.materialize_candidate_bundle"
                ) as materialize:
                    result = run_iteration(campaign)

                self.assertEqual(result["decision"], "rejected")
                materialize.assert_not_called()
                gate = json.loads(
                    (campaign.iteration_dir(1) / "gate-report.json").read_text()
                )
                error = " ".join(gate["rungs"][0]["detail"]["manifest_errors"])
                self.assertIn(
                    "duplicate object key" if label == "duplicate" else "non-JSON numeric constant",
                    error,
                )

    def test_huge_integer_repetition_is_canonical_e0_rejection(self) -> None:
        campaign = self._new_campaign(
            "huge-repetition",
            {"kind": "harness-fixture", "file": QUALITY_REL,
             "default_pass_rate": 0.55, "seed": 0},
        )
        worktree = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(worktree, "0.70\n")
        self._write_manifest(worktree, predicted=self.flipping[:1])
        submitted = json.loads((worktree / "manifest.json").read_text())
        submitted["evaluation_plan"]["repetitions"] = {"dynamic": 10**400}
        (worktree / "manifest.json").write_text(json.dumps(submitted))

        result = run_iteration(campaign)

        self.assertEqual(result["decision"], "rejected")
        self.assertFalse(result["advanced_accepted_state"])
        gate = json.loads((campaign.iteration_dir(1) / "gate-report.json").read_text())
        self.assertEqual([(r["rung"], r["status"]) for r in gate["rungs"]], [("E0", "fail")])
        self.assertIn(
            "must be an integer from 1 through",
            " ".join(gate["rungs"][0]["detail"]["manifest_errors"]),
        )
        self.assertEqual(campaign.state["pending_iteration"], 0)
        self.assertFalse(campaign.worktree_path.exists())

    def test_symlinked_benchmark_manifest_is_e0_rejected_without_import(self) -> None:
        campaign = self._new_campaign(
            "symlinked-sidecar",
            {"kind": "harness-fixture", "file": QUALITY_REL,
             "default_pass_rate": 0.55, "seed": 0},
        )
        worktree = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(worktree, "0.70\n")
        self._write_manifest(worktree, predicted=self.flipping[:1])
        bundle, sidecar = self._static_handback(campaign, worktree)
        target = sidecar.with_suffix(".real.json")
        sidecar.rename(target)
        sidecar.symlink_to(target)
        with (
            mock.patch("opti_loop.conductor._benchmark_handback_required", return_value=True),
            mock.patch("opti_loop.conductor.materialize_candidate_bundle") as materialize,
        ):
            result = run_iteration(
                campaign, candidate_bundle=bundle, candidate_manifest=sidecar
            )

        self.assertEqual(result["decision"], "rejected")
        materialize.assert_not_called()
        gate = json.loads((campaign.iteration_dir(1) / "gate-report.json").read_text())
        self.assertEqual([(r["rung"], r["status"]) for r in gate["rungs"]],
                         [("E0", "fail")])

    def test_expected_handback_preflight_failure_finishes_invalid_transaction(self) -> None:
        campaign = self._new_campaign(
            "handback-preflight",
            {"kind": "harness-fixture", "file": QUALITY_REL,
             "default_pass_rate": 0.55, "seed": 0},
        )
        worktree = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(worktree, "0.70\n")
        self._write_manifest(worktree, predicted=self.flipping[:1])
        bundle, sidecar = self._static_handback(campaign, worktree)
        with (
            mock.patch(
                "opti_loop.conductor._benchmark_handback_required",
                return_value=True,
            ),
            mock.patch(
                "opti_loop.conductor._validate_benchmark_handback_ownership",
                side_effect=MaterializationError(
                    "benchmark optimizer bundle, manifest, and inbox must be real "
                    "paths owned by one separate optimizer UID"
                ),
            ),
        ):
            result = run_iteration(
                campaign, candidate_bundle=bundle, candidate_manifest=sidecar
            )

        self.assertEqual(result["decision"], "invalid")
        iteration = campaign.iteration_dir(1)
        gate = json.loads((iteration / "gate-report.json").read_text())
        self.assertEqual([(r["rung"], r["status"]) for r in gate["rungs"]],
                         [("E1", "invalid")])
        snapshot = json.loads((iteration / "manifest.snapshot.json").read_text())
        submitted = json.loads(sidecar.read_text())
        self.assertEqual(set(snapshot), set(submitted))
        self.assertEqual(snapshot["status"], "simulated:invalid")
        self.assertEqual(snapshot["experiment_id"], submitted["experiment_id"])
        if EXPERIMENT_VALIDATOR is not None:
            self.assertEqual(list(EXPERIMENT_VALIDATOR.iter_errors(snapshot)), [])
        self.assertTrue(campaign.ledger_path.is_file())
        self.assertFalse(campaign.worktree_path.exists())
        self.assertEqual(load_campaign(
            self.repo, campaign.campaign_id, store_root=self.store
        ).state["pending_iteration"], 0)

    def test_malformed_manifest_stops_at_e0_before_malformed_bundle_import(self) -> None:
        campaign = self._new_campaign(
            "malformed-combined",
            {"kind": "harness-fixture", "file": QUALITY_REL,
             "default_pass_rate": 0.55, "seed": 0},
        )
        worktree = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(worktree, "0.70\n")
        inbox = self.store / "malformed-combined-inbox"
        inbox.mkdir()
        bundle = inbox / "candidate.bundle"
        bundle.write_bytes(b"malformed bundle")
        sidecar = inbox / "manifest.json"
        sidecar.write_text("[]")
        with (
            mock.patch("opti_loop.conductor.materialize_candidate_bundle") as materialize,
            mock.patch(
                "opti_loop.conductor._benchmark_handback_required",
                return_value=True,
            ),
            mock.patch(
                "opti_loop.conductor._validate_benchmark_handback_ownership"
            ) as ownership,
        ):
            result = run_iteration(
                campaign, candidate_bundle=bundle, candidate_manifest=sidecar
            )

        self.assertEqual(result["decision"], "rejected")
        materialize.assert_not_called()
        ownership.assert_not_called()
        gate = json.loads((campaign.iteration_dir(1) / "gate-report.json").read_text())
        self.assertEqual([(r["rung"], r["status"]) for r in gate["rungs"]],
                         [("E0", "fail")])
        snapshot = json.loads(
            (campaign.iteration_dir(1) / "manifest.snapshot.json").read_text()
        )
        self.assertEqual(snapshot["record_type"], "rejected_submission")
        self.assertEqual(snapshot["original_submission"], [])
        self.assertTrue(snapshot["validation_errors"])
        if EXPERIMENT_VALIDATOR is not None:
            self.assertEqual(list(EXPERIMENT_VALIDATOR.iter_errors(snapshot)), [])

    def test_materialization_only_failure_is_e1_invalid(self) -> None:
        campaign = self._new_campaign(
            "materialization-only",
            {"kind": "harness-fixture", "file": QUALITY_REL,
             "default_pass_rate": 0.55, "seed": 0},
        )
        worktree = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(worktree, "0.70\n")
        self._write_manifest(worktree, predicted=self.flipping[:1])
        inbox = self.store / "materialization-only-inbox"
        inbox.mkdir()
        bundle = inbox / "candidate.bundle"
        bundle.write_bytes(b"malformed bundle")
        sidecar = inbox / "manifest.json"
        shutil.copyfile(worktree / "manifest.json", sidecar)

        result = run_iteration(
            campaign, candidate_bundle=bundle, candidate_manifest=sidecar
        )

        self.assertEqual(result["decision"], "invalid")
        gate = json.loads((campaign.iteration_dir(1) / "gate-report.json").read_text())
        self.assertEqual([(r["rung"], r["status"]) for r in gate["rungs"]],
                         [("E1", "invalid")])

    def test_static_bundle_and_sidecar_drive_iteration_with_one_manifest_read(self) -> None:
        campaign = self._new_campaign(
            "static-handback",
            {"kind": "harness-fixture", "file": QUALITY_REL,
             "default_pass_rate": 0.55, "seed": 0},
        )
        measure_noise(campaign, runs=2)
        worktree = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(worktree, "0.70\n")
        self._write_manifest(worktree, predicted=self.flipping[:2])
        handback_sha = gitutil.head_sha(worktree)
        bundle, sidecar = self._static_handback(campaign, worktree)
        self._commit_quality(worktree, "0.99\n")
        (worktree / "manifest.json").write_text("[]")
        manifest_reads = 0
        attacker_manifest = sidecar.with_name("attacker-manifest.json")
        attacker_manifest.write_text("[]")
        attacker_bundle = bundle.with_name("attacker.bundle")
        attacker_bundle.write_bytes(b"not a Git bundle")

        def counted_read(path, **kwargs):
            nonlocal manifest_reads
            if path == sidecar:
                manifest_reads += 1
            result = _read_manifest_snapshot(path, **kwargs)
            if path == sidecar:
                sidecar.unlink()
                sidecar.symlink_to(attacker_manifest)
            return result

        def replace_bundle_after_open(**_kwargs):
            bundle.unlink()
            bundle.symlink_to(attacker_bundle)
            return os.getuid()

        with (
            mock.patch("opti_loop.conductor._read_manifest_snapshot", counted_read),
            mock.patch(
                "opti_loop.conductor._benchmark_handback_required",
                return_value=True,
            ),
            mock.patch(
                "opti_loop.conductor._validate_benchmark_handback_ownership",
                side_effect=replace_bundle_after_open,
            ),
        ):
            result = run_iteration(
                campaign, candidate_bundle=bundle, candidate_manifest=sidecar
            )

        gate = json.loads((campaign.iteration_dir(1) / "gate-report.json").read_text())
        self.assertIn(result["decision"], {"accepted", "rejected"}, gate)
        self.assertEqual(manifest_reads, 1)
        self.assertEqual(gate["rungs"][0]["rung"], "E0")
        self.assertEqual(gate["rungs"][0]["status"], "pass")
        activation = gate["rungs"][1]["detail"]["observed_activation"]
        self.assertEqual(activation["parsed_value"], 0.70)
        ledger = json.loads(campaign.ledger_path.read_text().splitlines()[-1])
        self.assertEqual(ledger["candidate_sha"], handback_sha)
        self.assertFalse((campaign.iteration_dir(1) / "eval/smoke_treatment/activation.json").exists())

    def test_accepted_ref_cas_race_finishes_invalid_without_advancement_claim(self) -> None:
        campaign = self._new_campaign(
            "accepted-ref-race",
            {"kind": "harness-fixture", "file": QUALITY_REL,
             "default_pass_rate": 0.55, "seed": 0},
        )
        worktree = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(worktree, "0.70\n")
        self._write_manifest(worktree, predicted=self.flipping[:1])
        bundle, sidecar = self._static_handback(campaign, worktree)
        accepted = GateReport(iteration=1)
        accepted.verdict = Verdict("accepted", "benchmark")
        accepted.run_digests = {
            "dev_treatment": "d" * 64,
            "regression_treatment": "e" * 64,
        }
        accepted.admissions = {
            "dev_treatment": {"admission_receipt": {"receipt": "narrow mock"}}
        }
        accepted.comparison = {
            "fixed": [],
            "candidate_success_rates": {},
            "candidate_protected_tasks": [],
        }
        base_sha = campaign.state["pending_base_sha"]
        accepted_ref = f"refs/opti/{campaign.campaign_id}/accepted"

        real_cas = gitutil.compare_and_swap_ref

        def race_then_publish(repo, ref, sha, *, expected):
            if ref == accepted_ref and sha != base_sha:
                real_cas(self.repo, accepted_ref, base_sha, expected=None)
            return real_cas(repo, ref, sha, expected=expected)

        with (
            mock.patch("opti_loop.conductor._benchmark_handback_required", return_value=True),
            mock.patch(
                "opti_loop.conductor._validate_benchmark_handback_ownership",
                return_value=os.getuid(),
            ),
            mock.patch("opti_loop.conductor.run_gate", return_value=accepted),
            mock.patch(
                "opti_loop.conductor.gitutil.compare_and_swap_ref",
                side_effect=race_then_publish,
            ),
        ):
            result = run_iteration(
                campaign, candidate_bundle=bundle, candidate_manifest=sidecar
            )

        self.assertEqual(result["decision"], "invalid")
        self.assertFalse(result["advanced_accepted_state"])
        self.assertEqual(gitutil.rev_parse(self.repo, accepted_ref), base_sha)
        gate = json.loads((campaign.iteration_dir(1) / "gate-report.json").read_text())
        self.assertEqual(gate["verdict"]["decision"], "invalid")
        self.assertIn("publication preflight", gate["rungs"][0]["detail"]["error"])
        self.assertEqual(campaign.state["accepted_base_sha"], base_sha)
        self.assertEqual(campaign.state["pending_iteration"], 0)
        failed = json.loads(
            (campaign.store.campaign_dir / "accepted-publication.json").read_text()
        )
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(
            set(failed),
            {
                "schema_version",
                "record_type",
                "status",
                "campaign_id",
                "iteration",
                "protocol_digest",
                "base_sha",
                "candidate_sha",
                "candidate_tree",
                "staging_ref",
                "expected_ref",
                "manifest_snapshot_digest",
                "intent_digest",
                "result_summary",
                "record_digest",
                "error",
            },
        )
        self.assertFalse(failed["result_summary"]["advanced_accepted_state"])
        self.assertEqual(failed["result_summary"]["decision"], "invalid")
        self.assertEqual(failed["result_summary"]["promotion_candidates"], [])
        self.assertNotIn("result", failed)
        self.assertNotIn("gate_report", failed)

    def test_transient_accepted_ref_cas_error_retries_pending_intent(self) -> None:
        campaign = self._new_campaign(
            "accepted-ref-transient",
            {"kind": "harness-fixture", "file": QUALITY_REL,
             "default_pass_rate": 0.55, "seed": 0},
        )
        worktree = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(worktree, "0.70\n")
        self._write_manifest(worktree, predicted=self.flipping[:1])
        candidate_sha = gitutil.head_sha(worktree)
        bundle, sidecar = self._static_handback(campaign, worktree)
        accepted_ref = f"refs/opti/{campaign.campaign_id}/accepted"
        staging_ref = f"refs/opti/import/{candidate_sha}"
        publication_path = campaign.store.campaign_dir / "accepted-publication.json"

        with (
            mock.patch("opti_loop.conductor._benchmark_handback_required", return_value=True),
            mock.patch(
                "opti_loop.conductor._validate_benchmark_handback_ownership",
                return_value=os.getuid(),
            ),
            mock.patch(
                "opti_loop.conductor.run_gate",
                return_value=self._accepted_benchmark_report(),
            ),
            mock.patch(
                "opti_loop.conductor.gitutil.compare_and_swap_ref",
                side_effect=gitutil.GitError("accepted ref lock unavailable"),
            ),
            self.assertRaisesRegex(gitutil.GitError, "lock unavailable"),
        ):
            run_iteration(
                campaign, candidate_bundle=bundle, candidate_manifest=sidecar
            )

        pending = json.loads(publication_path.read_text())
        self.assertEqual(pending["status"], "pending")
        self.assertIsNone(gitutil.try_rev_parse(self.repo, accepted_ref))
        self.assertEqual(
            gitutil.try_rev_parse(self.repo, staging_ref), candidate_sha
        )
        self.assertEqual(campaign.ledger_path.read_text(), "")

        recovered = run_iteration(campaign)
        self.assertEqual(recovered["decision"], "accepted")
        self.assertTrue(recovered["advanced_accepted_state"])
        self.assertEqual(gitutil.rev_parse(self.repo, accepted_ref), candidate_sha)
        self.assertIsNone(gitutil.try_rev_parse(self.repo, staging_ref))
        ledger = campaign.ledger_path.read_text().splitlines()
        self.assertEqual(len(ledger), 1)
        self.assertEqual(json.loads(ledger[0])["decision"], "accepted")

    def test_accepted_publication_recovers_every_post_gate_boundary(self) -> None:
        boundaries = (
            "intent",
            "accepted-ref",
            "gate-report",
            "manifest-snapshot",
            "cluster-register",
            "ledger",
            "learnings",
            "campaign-state",
            "complete-receipt",
        )
        for boundary in boundaries:
            with self.subTest(boundary=boundary):
                campaign = self._new_campaign(
                    f"recover-{boundary}",
                    {"kind": "harness-fixture", "file": QUALITY_REL,
                     "default_pass_rate": 0.55, "seed": 0},
                )
                worktree = Path(start_iteration(campaign)["worktree"])
                self._commit_quality(worktree, "0.70\n")
                self._write_manifest(worktree, predicted=self.flipping[:1])
                candidate_sha = gitutil.head_sha(worktree)
                bundle, sidecar = self._static_handback(campaign, worktree)
                injected = False
                intent_record = None

                def interrupt(current):
                    nonlocal injected, intent_record
                    if current == "intent":
                        intent_record = json.loads(
                            (
                                campaign.store.campaign_dir
                                / "accepted-publication.json"
                            ).read_text()
                        )
                    if current == boundary and not injected:
                        injected = True
                        raise OSError(f"interrupt after {boundary}")

                with (
                    mock.patch(
                        "opti_loop.conductor._benchmark_handback_required",
                        return_value=True,
                    ),
                    mock.patch(
                        "opti_loop.conductor._validate_benchmark_handback_ownership",
                        return_value=os.getuid(),
                    ),
                    mock.patch(
                        "opti_loop.conductor.run_gate",
                        return_value=self._accepted_benchmark_report(),
                    ),
                    mock.patch(
                        "opti_loop.conductor._publication_checkpoint",
                        side_effect=interrupt,
                    ),
                    self.assertRaisesRegex(OSError, f"interrupt after {boundary}"),
                ):
                    run_iteration(
                        campaign,
                        candidate_bundle=bundle,
                        candidate_manifest=sidecar,
                    )

                publication_path = (
                    campaign.store.campaign_dir / "accepted-publication.json"
                )
                interrupted_record = json.loads(publication_path.read_text())
                self.assertEqual(
                    interrupted_record["status"],
                    "complete" if boundary == "complete-receipt" else "pending",
                )
                self.assertIsNotNone(intent_record)
                recovered = run_iteration(campaign)
                self.assertEqual(recovered["decision"], "accepted")
                self.assertTrue(recovered["advanced_accepted_state"])
                completed = json.loads(publication_path.read_text())
                self.assertEqual(completed["status"], "complete")
                self.assertEqual(completed["candidate_sha"], candidate_sha)
                reloaded = load_campaign(
                    self.repo, campaign.campaign_id, store_root=self.store
                )
                self.assertEqual(reloaded.state["accepted_base_sha"], candidate_sha)
                self.assertEqual(
                    reloaded.state["accepted_protection"],
                    {
                        "champion_sha": candidate_sha,
                        "protected_tasks": [],
                        "success_rates": {},
                    },
                )
                self.assertEqual(reloaded.state["pending_iteration"], 0)
                self.assertEqual(reloaded.state, intent_record["final_state"])
                self.assertEqual(
                    gitutil.rev_parse(
                        self.repo,
                        f"refs/opti/{campaign.campaign_id}/accepted",
                    ),
                    candidate_sha,
                )
                gate = json.loads(
                    (campaign.iteration_dir(1) / "gate-report.json").read_text()
                )
                snapshot = json.loads(
                    (campaign.iteration_dir(1) / "manifest.snapshot.json").read_text()
                )
                ledger = [
                    json.loads(line)
                    for line in campaign.ledger_path.read_text().splitlines()
                ]
                self.assertEqual(gate, intent_record["gate_report"])
                self.assertEqual(snapshot, intent_record["manifest_snapshot"])
                self.assertEqual(ledger, [intent_record["ledger_row"]])
                self.assertEqual(campaign.state["operation_attempts"], 1)
                self.assertEqual(
                    json.loads(campaign.clusters_path.read_text()),
                    intent_record["cluster_register"],
                )
                self.assertEqual(
                    len(read_records(
                        campaign.learnings_path,
                        campaign_root=campaign.store.campaign_dir,
                    )),
                    1,
                )
                self.assertIsNone(
                    gitutil.try_rev_parse(
                        self.repo, f"refs/opti/import/{candidate_sha}"
                    )
                )
                self.assertEqual(
                    set(completed),
                    {
                        "schema_version",
                        "record_type",
                        "status",
                        "campaign_id",
                        "iteration",
                        "protocol_digest",
                        "base_sha",
                        "candidate_sha",
                        "candidate_tree",
                        "staging_ref",
                        "expected_ref",
                        "manifest_snapshot_digest",
                        "intent_digest",
                        "result_summary",
                        "record_digest",
                    },
                )
                self.assertNotIn("gate_report", completed)
                self.assertNotIn("final_state", completed)
                self.assertEqual(completed["result_summary"], recovered)
                self.assertEqual(run_iteration(campaign), recovered)

    def test_nonaccepted_publication_recovers_every_terminal_boundary(self) -> None:
        boundaries = (
            "intent",
            "gate-report",
            "manifest-snapshot",
            "ledger",
            "learnings",
            "campaign-state",
            "complete-receipt",
        )
        for boundary in boundaries:
            with self.subTest(boundary=boundary):
                campaign = self._new_campaign(
                    f"reject-recover-{boundary}",
                    {"kind": "harness-fixture", "file": QUALITY_REL,
                     "default_pass_rate": 0.55, "seed": 0},
                )
                worktree = Path(start_iteration(campaign)["worktree"])
                self._commit_quality(worktree, "0.00\n")
                self._write_manifest(worktree, predicted=self.flipping[:1])
                injected = False

                def interrupt(current):
                    nonlocal injected
                    if current == boundary and not injected:
                        injected = True
                        raise OSError(f"interrupt after {boundary}")

                with (
                    mock.patch(
                        "opti_loop.conductor._publication_checkpoint",
                        side_effect=interrupt,
                    ),
                    self.assertRaisesRegex(OSError, f"interrupt after {boundary}"),
                ):
                    run_iteration(campaign)

                receipt = json.loads(
                    (campaign.store.campaign_dir / "accepted-publication.json").read_text()
                )
                self.assertEqual(
                    receipt["status"],
                    "complete" if boundary == "complete-receipt" else "pending",
                )
                recovered = run_iteration(campaign)
                self.assertEqual(recovered["decision"], "rejected")
                self.assertFalse(recovered["advanced_accepted_state"])
                self.assertEqual(len(campaign.ledger_path.read_text().splitlines()), 1)
                self.assertEqual(
                    len(read_records(
                        campaign.learnings_path,
                        campaign_root=campaign.store.campaign_dir,
                    )),
                    1,
                )
                self.assertFalse(campaign.worktree_path.exists())
                self.assertEqual(run_iteration(campaign), recovered)

    def test_pivot_publication_recovers_every_terminal_boundary(self) -> None:
        boundaries = (
            "intent", "gate-report", "manifest-snapshot", "ledger",
            "learnings", "campaign-state", "complete-receipt",
        )
        for boundary in boundaries:
            with self.subTest(boundary=boundary):
                campaign = self._new_campaign(
                    f"pivot-recover-{boundary}", self._command_adapter()
                )
                campaign.state["failed_attempts"][
                    "stub/real_v1/failed::policy"
                ] = 2
                campaign.save_state()
                worktree = Path(start_iteration(campaign)["worktree"])
                self._commit_quality(worktree, "0.70\n")
                self._write_manifest(worktree, predicted=self.flipping[:1])
                injected = False

                def interrupt(current):
                    nonlocal injected
                    if current == boundary and not injected:
                        injected = True
                        raise OSError(f"interrupt after {boundary}")

                with (
                    mock.patch(
                        "opti_loop.conductor._publication_checkpoint",
                        side_effect=interrupt,
                    ),
                    self.assertRaisesRegex(OSError, f"interrupt after {boundary}"),
                ):
                    run_iteration(campaign)
                recovered = run_iteration(campaign)
                self.assertEqual(recovered["verdict"], "simulated:rejected")
                self.assertEqual(len(campaign.ledger_path.read_text().splitlines()), 1)
                self.assertEqual(
                    len(read_records(
                        campaign.learnings_path,
                        campaign_root=campaign.store.campaign_dir,
                    )),
                    1,
                )
                self.assertFalse(campaign.worktree_path.exists())

    def test_nonaccepted_terminal_cleanup_failure_replays_receipt(self) -> None:
        campaign = self._new_campaign(
            "reject-cleanup-replay",
            {"kind": "harness-fixture", "file": QUALITY_REL,
             "default_pass_rate": 0.55, "seed": 0},
        )
        worktree = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(worktree, "0.00\n")
        self._write_manifest(worktree, predicted=self.flipping[:1])
        real_remove = gitutil.worktree_remove
        injected = False

        def fail_once(repo, path):
            nonlocal injected
            if not injected:
                injected = True
                raise gitutil.GitError("terminal rejection cleanup failed")
            return real_remove(repo, path)

        with (
            mock.patch(
                "opti_loop.conductor.gitutil.worktree_remove", side_effect=fail_once
            ),
            self.assertRaisesRegex(gitutil.GitError, "rejection cleanup failed"),
        ):
            run_iteration(campaign)
        receipt = json.loads(
            (campaign.store.campaign_dir / "accepted-publication.json").read_text()
        )
        self.assertEqual(receipt["status"], "complete")
        reloaded = load_campaign(
            self.repo, campaign.campaign_id, store_root=self.store
        )
        self.assertIn(
            "terminal rejection cleanup failed",
            reloaded.state["cleanup_health"]["detail"],
        )
        self.assertTrue(any(
            "terminal rejection cleanup failed" in blocker
            for blocker in operation_status(reloaded)["blockers"]
        ))
        recovered = run_iteration(campaign)
        self.assertEqual(recovered["decision"], "rejected")
        self.assertEqual(len(campaign.ledger_path.read_text().splitlines()), 1)
        self.assertEqual(
            len(read_records(
                campaign.learnings_path, campaign_root=campaign.store.campaign_dir
            )),
            1,
        )
        self.assertFalse(campaign.worktree_path.exists())
        self.assertEqual(campaign.state["cleanup_health"]["status"], "clean")

    def test_terminal_staging_cleanup_git_error_replays_accepted_receipt(self) -> None:
        campaign = self._new_campaign(
            "terminal-staging-cleanup",
            {"kind": "harness-fixture", "file": QUALITY_REL,
             "default_pass_rate": 0.55, "seed": 0},
        )
        worktree = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(worktree, "0.70\n")
        self._write_manifest(worktree, predicted=self.flipping[:1])
        candidate_sha = gitutil.head_sha(worktree)
        bundle, sidecar = self._static_handback(campaign, worktree)
        staging_ref = f"refs/opti/import/{candidate_sha}"
        accepted_ref = f"refs/opti/{campaign.campaign_id}/accepted"
        publication_path = campaign.store.campaign_dir / "accepted-publication.json"
        real_delete_ref = gitutil.delete_ref
        injected = False

        def fail_terminal_cleanup(repo, ref, *, expected):
            nonlocal injected
            if (
                ref == staging_ref
                and gitutil.try_rev_parse(self.repo, accepted_ref) == candidate_sha
                and not injected
            ):
                injected = True
                raise gitutil.GitError("terminal staging cleanup failed")
            return real_delete_ref(repo, ref, expected=expected)

        with (
            mock.patch("opti_loop.conductor._benchmark_handback_required", return_value=True),
            mock.patch(
                "opti_loop.conductor._validate_benchmark_handback_ownership",
                return_value=os.getuid(),
            ),
            mock.patch(
                "opti_loop.conductor.run_gate",
                return_value=self._accepted_benchmark_report(),
            ),
            mock.patch(
                "opti_loop.conductor.gitutil.delete_ref",
                side_effect=fail_terminal_cleanup,
            ),
            self.assertRaisesRegex(gitutil.GitError, "terminal staging cleanup failed"),
        ):
            run_iteration(
                campaign, candidate_bundle=bundle, candidate_manifest=sidecar
            )

        completed = json.loads(publication_path.read_text())
        self.assertEqual(completed["status"], "complete")
        self.assertEqual(gitutil.rev_parse(self.repo, accepted_ref), candidate_sha)
        reloaded = load_campaign(
            self.repo, campaign.campaign_id, store_root=self.store
        )
        self.assertEqual(reloaded.state["accepted_base_sha"], candidate_sha)
        ledger = [
            json.loads(line) for line in campaign.ledger_path.read_text().splitlines()
        ]
        self.assertEqual(len(ledger), 1)
        self.assertEqual(ledger[0]["decision"], "accepted")
        gate = json.loads(
            (campaign.iteration_dir(1) / "gate-report.json").read_text()
        )
        self.assertEqual(gate["verdict"]["decision"], "accepted")

        recovered = run_iteration(campaign)
        self.assertEqual(recovered, completed["result_summary"])
        self.assertIsNone(gitutil.try_rev_parse(self.repo, staging_ref))
        self.assertEqual(
            len(campaign.ledger_path.read_text().splitlines()), 1
        )

    def test_durable_intent_readback_failure_preserves_staging_for_retry(self) -> None:
        from opti_loop import conductor as conductor_module

        campaign = self._new_campaign(
            "intent-readback-retry",
            {"kind": "harness-fixture", "file": QUALITY_REL,
             "default_pass_rate": 0.55, "seed": 0},
        )
        worktree = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(worktree, "0.70\n")
        self._write_manifest(worktree, predicted=self.flipping[:1])
        candidate_sha = gitutil.head_sha(worktree)
        bundle, sidecar = self._static_handback(campaign, worktree)
        staging_ref = f"refs/opti/import/{candidate_sha}"
        publication_path = campaign.store.campaign_dir / "accepted-publication.json"
        real_load = conductor_module._load_publication_record

        def fail_durable_readback(current_campaign):
            if publication_path.exists():
                raise RuntimeError("publication readback unavailable")
            return real_load(current_campaign)

        with (
            mock.patch("opti_loop.conductor._benchmark_handback_required", return_value=True),
            mock.patch(
                "opti_loop.conductor._validate_benchmark_handback_ownership",
                return_value=os.getuid(),
            ),
            mock.patch(
                "opti_loop.conductor.run_gate",
                return_value=self._accepted_benchmark_report(),
            ),
            mock.patch(
                "opti_loop.conductor._load_publication_record",
                side_effect=fail_durable_readback,
            ),
            self.assertRaisesRegex(RuntimeError, "readback unavailable"),
        ):
            run_iteration(
                campaign, candidate_bundle=bundle, candidate_manifest=sidecar
            )

        pending = json.loads(publication_path.read_text())
        self.assertEqual(pending["status"], "pending")
        self.assertEqual(
            gitutil.try_rev_parse(self.repo, staging_ref), candidate_sha
        )
        self.assertEqual(campaign.ledger_path.read_text(), "")

        recovered = run_iteration(campaign)
        self.assertEqual(recovered["decision"], "accepted")
        self.assertTrue(recovered["advanced_accepted_state"])
        self.assertIsNone(gitutil.try_rev_parse(self.repo, staging_ref))
        self.assertEqual(
            len(campaign.ledger_path.read_text().splitlines()), 1
        )

    def test_tampered_pending_publication_fails_before_any_recovery_mutation(self) -> None:
        def tamper_ledger(record: dict) -> None:
            record["ledger_row"]["candidate_sha"] = "f" * 40

        def tamper_result(record: dict) -> None:
            record["result"]["accepted_base_sha"] = "f" * 40

        def tamper_candidate(record: dict) -> None:
            record["candidate_sha"] = "f" * 40

        def tamper_state(record: dict) -> None:
            record["final_state"]["accepted_base_sha"] = record["base_sha"]

        def tamper_state_counter(record: dict) -> None:
            record["final_state"]["iterations_since_divergent"] += 10

        def tamper_snapshot(record: dict) -> None:
            record["manifest_snapshot"]["hypothesis"] = "resealed substitution"

        def tamper_register(record: dict) -> None:
            record["cluster_register"]["clusters"]["forged"] = {}

        def tamper_learnings(record: dict) -> None:
            record["learning_record"]["hypothesis"] = "resealed substitution"

        def tamper_version(record: dict) -> None:
            record["schema_version"] = "0.1.0"

        def add_unknown(record: dict) -> None:
            record["unexpected"] = True

        attacks = {
            "ledger": tamper_ledger,
            "result": tamper_result,
            "candidate": tamper_candidate,
            "state": tamper_state,
            "state-counter": tamper_state_counter,
            "snapshot": tamper_snapshot,
            "register": tamper_register,
            "learnings": tamper_learnings,
            "version": tamper_version,
            "unknown-key": add_unknown,
        }
        for label, mutate in attacks.items():
            with self.subTest(attack=label):
                campaign = self._new_campaign(
                    f"tampered-publication-{label}",
                    {"kind": "harness-fixture", "file": QUALITY_REL,
                     "default_pass_rate": 0.55, "seed": 0},
                )
                candidate_sha, intent = self._interrupt_publication(
                    campaign, "intent"
                )
                publication_path = (
                    campaign.store.campaign_dir / "accepted-publication.json"
                )
                tampered = json.loads(json.dumps(intent))
                mutate(tampered)
                tampered = _seal_publication_record(tampered)
                publication_path.write_text(
                    json.dumps(tampered, indent=2, sort_keys=True) + "\n"
                )
                protected = {
                    "state": campaign.store.state_path.read_bytes(),
                    "clusters": campaign.clusters_path.read_bytes(),
                    "ledger": campaign.ledger_path.read_bytes(),
                    "learnings": campaign.learnings_path.read_bytes(),
                }
                accepted_ref = f"refs/opti/{campaign.campaign_id}/accepted"
                staging_ref = f"refs/opti/import/{candidate_sha}"
                self.assertIsNone(gitutil.try_rev_parse(self.repo, accepted_ref))
                self.assertEqual(
                    gitutil.try_rev_parse(self.repo, staging_ref), candidate_sha
                )

                with self.assertRaises(RuntimeError):
                    run_iteration(campaign)

                self.assertEqual(campaign.store.state_path.read_bytes(), protected["state"])
                self.assertEqual(campaign.clusters_path.read_bytes(), protected["clusters"])
                self.assertEqual(campaign.ledger_path.read_bytes(), protected["ledger"])
                self.assertEqual(campaign.learnings_path.read_bytes(), protected["learnings"])
                self.assertIsNone(gitutil.try_rev_parse(self.repo, accepted_ref))
                self.assertEqual(
                    gitutil.try_rev_parse(self.repo, staging_ref), candidate_sha
                )
                self.assertFalse(
                    (campaign.iteration_dir(1) / "gate-report.json").exists()
                )
                self.assertFalse(
                    (campaign.iteration_dir(1) / "manifest.snapshot.json").exists()
                )

    def test_start_refuses_pending_publication_after_campaign_state_checkpoint(self) -> None:
        campaign = self._new_campaign(
            "start-pending-publication",
            {"kind": "harness-fixture", "file": QUALITY_REL,
             "default_pass_rate": 0.55, "seed": 0},
        )
        candidate_sha, _intent = self._interrupt_publication(
            campaign, "campaign-state"
        )
        with self.assertRaisesRegex(RuntimeError, "publication recovery is pending"):
            start_iteration(campaign)
        reloaded = load_campaign(
            self.repo, campaign.campaign_id, store_root=self.store
        )
        self.assertEqual(reloaded.current_iteration, 1)
        self.assertFalse(campaign.iteration_dir(2).exists())

        recovered = run_iteration(campaign)
        self.assertEqual(recovered["decision"], "accepted")
        self.assertEqual(recovered["accepted_base_sha"], candidate_sha)
        self.assertFalse(campaign.worktree_path.exists())

    def test_start_cleans_complete_receipt_before_opening_next_iteration(self) -> None:
        campaign = self._new_campaign(
            "start-complete-publication",
            {"kind": "harness-fixture", "file": QUALITY_REL,
             "default_pass_rate": 0.55, "seed": 0},
        )
        candidate_sha, _intent = self._interrupt_publication(
            campaign, "complete-receipt"
        )
        staging_ref = f"refs/opti/import/{candidate_sha}"
        receipt = json.loads(
            (campaign.store.campaign_dir / "accepted-publication.json").read_text()
        )
        accepted_snapshot = json.loads(
            (campaign.iteration_dir(1) / "manifest.snapshot.json").read_text()
        )
        self.assertEqual(
            receipt["manifest_snapshot_digest"],
            _manifest_snapshot_digest(accepted_snapshot),
        )
        self.assertEqual(gitutil.try_rev_parse(self.repo, staging_ref), candidate_sha)
        self.assertTrue(campaign.worktree_path.exists())

        with mock.patch("opti_loop.conductor._load_accepted_run", return_value=None):
            started = start_iteration(campaign)

        self.assertEqual(started["iteration"], 2)
        self.assertIsNone(gitutil.try_rev_parse(self.repo, staging_ref))
        self.assertTrue(campaign.worktree_path.exists())
        self.assertFalse(
            (campaign.iteration_dir(1) / "candidate.handback.bundle").exists()
        )
        result = run_iteration(campaign)
        self.assertEqual(result["iteration"], 2)
        self.assertEqual(result["decision"], "rejected")
        self.assertEqual(campaign.state["accepted_base_sha"], candidate_sha)

    def test_pre_intent_failures_never_orphan_staging_ref(self) -> None:
        from opti_loop import conductor as conductor_module

        for boundary in ("register", "serialization", "atomic-write"):
            with self.subTest(boundary=boundary):
                campaign = self._new_campaign(
                    f"pre-intent-{boundary}",
                    {"kind": "harness-fixture", "file": QUALITY_REL,
                     "default_pass_rate": 0.55, "seed": 0},
                )
                worktree = Path(start_iteration(campaign)["worktree"])
                self._commit_quality(worktree, "0.70\n")
                self._write_manifest(worktree, predicted=self.flipping[:1])
                candidate_sha = gitutil.head_sha(worktree)
                bundle, sidecar = self._static_handback(campaign, worktree)
                publication_path = (
                    campaign.store.campaign_dir / "accepted-publication.json"
                )
                if boundary == "register":
                    fault = mock.patch(
                        "opti_loop.conductor.load_register",
                        side_effect=OSError("register construction failed"),
                    )
                    error_type = OSError
                elif boundary == "serialization":
                    fault = mock.patch(
                        "opti_loop.conductor._seal_publication_record",
                        side_effect=ValueError("intent serialization failed"),
                    )
                    error_type = ValueError
                else:
                    real_atomic_write = conductor_module.atomic_write_json

                    def fail_intent(path, payload):
                        if Path(path) == publication_path:
                            raise OSError("intent atomic write failed")
                        return real_atomic_write(path, payload)

                    fault = mock.patch(
                        "opti_loop.conductor.atomic_write_json",
                        side_effect=fail_intent,
                    )
                    error_type = OSError
                with (
                    mock.patch(
                        "opti_loop.conductor._benchmark_handback_required",
                        return_value=True,
                    ),
                    mock.patch(
                        "opti_loop.conductor._validate_benchmark_handback_ownership",
                        return_value=os.getuid(),
                    ),
                    mock.patch(
                        "opti_loop.conductor.run_gate",
                        return_value=self._accepted_benchmark_report(),
                    ),
                    fault,
                    self.assertRaises(error_type),
                ):
                    run_iteration(
                        campaign,
                        candidate_bundle=bundle,
                        candidate_manifest=sidecar,
                    )

                self.assertIsNone(
                    gitutil.try_rev_parse(
                        self.repo, f"refs/opti/import/{candidate_sha}"
                    )
                )
                self.assertIsNone(
                    gitutil.try_rev_parse(
                        self.repo, f"refs/opti/{campaign.campaign_id}/accepted"
                    )
                )
                self.assertFalse(publication_path.exists())
                reloaded = load_campaign(
                    self.repo, campaign.campaign_id, store_root=self.store
                )
                self.assertEqual(reloaded.state["pending_iteration"], 1)

    def test_pre_intent_failure_retries_real_gates_without_stale_artifacts(self) -> None:
        from opti_loop import conductor as conductor_module
        from opti_loop import gates as gates_module

        campaign = self._new_campaign(
            "pre-intent-real-retry",
            {"kind": "harness-fixture", "file": QUALITY_REL,
             "default_pass_rate": 0.55, "seed": 0},
        )
        measure_noise(campaign, runs=2)
        worktree = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(worktree, "0.70\n")
        self._write_manifest(worktree, predicted=self.flipping[:2])
        candidate_sha = gitutil.head_sha(worktree)
        bundle, sidecar = self._static_handback(campaign, worktree)
        iteration_dir = campaign.iteration_dir(1)
        real_gate = gates_module.run_gate
        gate_calls = 0

        def run_real_gate(**kwargs):
            nonlocal gate_calls
            if gate_calls:
                for name in (
                    "smoke_treatment",
                    "targeted_screen",
                    "regression_screen",
                ):
                    self.assertFalse((iteration_dir / "eval" / name).exists())
                for name in ("regression_treatment", "dev_treatment"):
                    self.assertTrue((iteration_dir / "eval" / name).exists())
            gate_calls += 1
            report = real_gate(**kwargs)
            self.assertEqual(report.verdict.decision, "accepted")
            report.verdict = Verdict("accepted", "benchmark")
            report.admissions["dev_treatment"] = {
                "admission_receipt": {"receipt": "narrow retry mock"}
            }
            return report

        real_seal = conductor_module._seal_publication_record
        seal_calls = 0

        def fail_first_seal(payload):
            nonlocal seal_calls
            seal_calls += 1
            if seal_calls == 1:
                raise ValueError("intent serialization failed")
            return real_seal(payload)

        def retry_patches():
            return (
                mock.patch(
                    "opti_loop.conductor._benchmark_handback_required",
                    return_value=True,
                ),
                mock.patch(
                    "opti_loop.conductor._validate_benchmark_handback_ownership",
                    return_value=os.getuid(),
                ),
                mock.patch(
                    "opti_loop.conductor.run_gate", side_effect=run_real_gate
                ),
                mock.patch(
                    "opti_loop.conductor._seal_publication_record",
                    side_effect=fail_first_seal,
                ),
            )

        ownership, uid_check, gate_patch, seal_patch = retry_patches()
        with ownership, uid_check, gate_patch, seal_patch, self.assertRaisesRegex(
            ValueError, "serialization failed"
        ):
            run_iteration(
                campaign, candidate_bundle=bundle, candidate_manifest=sidecar
            )

        staging_ref = f"refs/opti/import/{candidate_sha}"
        self.assertIsNone(gitutil.try_rev_parse(self.repo, staging_ref))
        self.assertTrue((iteration_dir / "candidate.handback.bundle").is_file())
        self.assertTrue((iteration_dir / "eval/dev_treatment").is_dir())

        ownership, uid_check, gate_patch, seal_patch = retry_patches()
        with ownership, uid_check, gate_patch, seal_patch:
            result = run_iteration(
                campaign, candidate_bundle=bundle, candidate_manifest=sidecar
            )

        self.assertEqual(gate_calls, 2)
        self.assertEqual(result["decision"], "accepted")
        self.assertTrue(result["advanced_accepted_state"])
        self.assertIsNone(gitutil.try_rev_parse(self.repo, staging_ref))
        self.assertFalse((iteration_dir / "candidate.handback.bundle").exists())

    def test_durable_pending_intent_owns_cleanup_after_late_write_error(self) -> None:
        from opti_loop import conductor as conductor_module

        campaign = self._new_campaign(
            "durable-intent-ownership",
            {"kind": "harness-fixture", "file": QUALITY_REL,
             "default_pass_rate": 0.55, "seed": 0},
        )
        worktree = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(worktree, "0.70\n")
        self._write_manifest(worktree, predicted=self.flipping[:1])
        candidate_sha = gitutil.head_sha(worktree)
        bundle, sidecar = self._static_handback(campaign, worktree)
        publication_path = campaign.store.campaign_dir / "accepted-publication.json"
        real_atomic_write = conductor_module.atomic_write_json
        injected = False

        def write_then_fail(path, payload):
            nonlocal injected
            real_atomic_write(path, payload)
            if Path(path) == publication_path and not injected:
                injected = True
                raise OSError("late intent write error")

        with (
            mock.patch("opti_loop.conductor._benchmark_handback_required", return_value=True),
            mock.patch(
                "opti_loop.conductor._validate_benchmark_handback_ownership",
                return_value=os.getuid(),
            ),
            mock.patch(
                "opti_loop.conductor.run_gate",
                return_value=self._accepted_benchmark_report(),
            ),
            mock.patch(
                "opti_loop.conductor.atomic_write_json",
                side_effect=write_then_fail,
            ),
            self.assertRaisesRegex(OSError, "late intent write error"),
        ):
            run_iteration(
                campaign,
                candidate_bundle=bundle,
                candidate_manifest=sidecar,
            )

        pending = json.loads(publication_path.read_text())
        self.assertEqual(pending["status"], "pending")
        self.assertEqual(
            gitutil.try_rev_parse(self.repo, f"refs/opti/import/{candidate_sha}"),
            candidate_sha,
        )
        recovered = run_iteration(campaign)
        self.assertEqual(recovered["decision"], "accepted")
        self.assertIsNone(
            gitutil.try_rev_parse(self.repo, f"refs/opti/import/{candidate_sha}")
        )

    def test_separate_clone_candidate_is_imported_before_accepted_ref_publication(self) -> None:
        campaign = self._new_campaign(
            "external-publication",
            {"kind": "harness-fixture", "file": QUALITY_REL,
             "default_pass_rate": 0.55, "seed": 0},
        )
        start_iteration(campaign)
        optimizer = Path(self._tmp.name) / "independent-optimizer"
        subprocess.run(
            ["git", "clone", "--quiet", "--no-local", str(self.repo), str(optimizer)],
            check=True,
            capture_output=True,
            env=ENV,
        )
        self._commit_quality(optimizer, "0.70\n")
        self._write_manifest(optimizer, predicted=self.flipping[:1])
        candidate_sha = gitutil.head_sha(optimizer)
        candidate_tree = gitutil.rev_parse(optimizer, f"{candidate_sha}^{{tree}}")
        self.assertNotEqual(candidate_sha, gitutil.head_sha(self.repo))
        self.assertNotEqual(
            subprocess.run(
                ["git", "-C", str(self.repo), "cat-file", "-e", candidate_sha],
                capture_output=True,
            ).returncode,
            0,
        )

        inbox = Path(self._tmp.name) / "external-inbox"
        inbox.mkdir()
        external_bundle = inbox / "candidate.bundle"
        sidecar = inbox / "manifest.json"
        shutil.copyfile(optimizer / "manifest.json", sidecar)
        gitutil.create_candidate_bundle(
            optimizer,
            external_bundle,
            base_sha=campaign.state["pending_base_sha"],
            candidate_sha=candidate_sha,
        )
        with (
            mock.patch("opti_loop.conductor._benchmark_handback_required", return_value=True),
            mock.patch(
                "opti_loop.conductor._validate_benchmark_handback_ownership",
                return_value=os.getuid(),
            ),
            mock.patch(
                "opti_loop.conductor.run_gate",
                return_value=self._accepted_benchmark_report(),
            ),
        ):
            result = run_iteration(
                campaign,
                candidate_bundle=external_bundle,
                candidate_manifest=sidecar,
            )

        self.assertEqual(result["decision"], "accepted")
        self.assertEqual(gitutil.rev_parse(self.repo, candidate_sha), candidate_sha)
        self.assertEqual(gitutil.rev_parse(self.repo, f"{candidate_sha}^{{tree}}"), candidate_tree)
        self.assertEqual(
            gitutil.rev_parse(self.repo, "refs/opti/external-publication/accepted"),
            candidate_sha,
        )

    def test_established_accepted_ref_deletion_never_recreates_or_advances(self) -> None:
        campaign = self._new_campaign(
            "accepted-ref-deletion",
            {"kind": "harness-fixture", "file": QUALITY_REL,
             "default_pass_rate": 0.55, "seed": 0},
        )
        accepted_ref = f"refs/opti/{campaign.campaign_id}/accepted"
        self.assertIsNone(gitutil.try_rev_parse(self.repo, accepted_ref))
        first_candidate, _intent = self._interrupt_publication(campaign, "intent")
        first = run_iteration(campaign)
        self.assertEqual(first["decision"], "accepted")
        self.assertEqual(gitutil.try_rev_parse(self.repo, accepted_ref), first_candidate)

        with mock.patch("opti_loop.conductor._load_accepted_run", return_value=None):
            worktree = Path(start_iteration(campaign)["worktree"])
        gitutil.delete_ref(self.repo, accepted_ref, expected=first_candidate)
        self.assertIsNone(gitutil.try_rev_parse(self.repo, accepted_ref))
        self._commit_quality(worktree, "0.80\n")
        self._write_manifest(worktree, predicted=self.flipping[:1])
        state_before = json.loads(json.dumps(campaign.state))

        with self.assertRaisesRegex(RuntimeError, "established accepted Git ref is missing"):
            run_iteration(campaign)

        reloaded = load_campaign(
            self.repo, campaign.campaign_id, store_root=self.store
        )
        self.assertEqual(reloaded.state, state_before)
        self.assertEqual(reloaded.state["accepted_base_sha"], first_candidate)
        self.assertEqual(reloaded.state["pending_iteration"], 2)
        self.assertIsNone(gitutil.try_rev_parse(self.repo, accepted_ref))
        receipt = json.loads(
            (campaign.store.campaign_dir / "accepted-publication.json").read_text()
        )
        self.assertEqual(receipt["iteration"], 1)
        self.assertEqual(receipt["status"], "complete")

    def test_candidate_branch_is_preserved_across_simulated_bundle_creation(self) -> None:
        campaign = self._new_campaign(
            "preserve-candidate-ref",
            {"kind": "harness-fixture", "file": QUALITY_REL,
             "default_pass_rate": 0.55, "seed": 0},
        )
        prior = campaign.state["accepted_base_sha"]
        _git(self.repo, "update-ref", "refs/heads/candidate", prior)
        measure_noise(campaign, runs=2)
        worktree = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(worktree, "0.70\n")
        self._write_manifest(worktree, predicted=self.flipping[:1])

        run_iteration(campaign)

        self.assertEqual(gitutil.rev_parse(self.repo, "refs/heads/candidate"), prior)

    # ── F09: a shotgun prediction fails the precision floor ──────────────
    def test_shotgun_prediction_rejected(self) -> None:
        campaign = self._new_campaign(
            "cmp",
            {"kind": "harness-fixture", "file": QUALITY_REL,
             "default_pass_rate": 0.55, "seed": 0},
            min_prediction_precision=0.9,
        )
        measure_noise(campaign, runs=2)
        wt = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(wt, "0.70\n")
        # Predict ALL smoke tasks to catch the few that flip -> precision far below 0.9.
        self._write_manifest(wt, predicted=sorted(self.smoke_ids))
        result = run_iteration(campaign)
        self.assertEqual(result["decision"], "rejected")
        gate = json.loads((campaign.iteration_dir(1) / "gate-report.json").read_text())
        e5 = next(r for r in gate["rungs"] if r["rung"] == "E5")
        self.assertLess(
            e5["detail"]["prediction_precision"],
            e5["detail"]["min_prediction_precision"],
        )

    # ── AR-002: malformed manifests reject without splitting transaction ─
    def test_non_object_manifests_finish_truthful_rejected_transactions(self) -> None:
        campaign = self._new_campaign(
            "cmp", {"kind": "harness-fixture", "file": QUALITY_REL,
                    "default_pass_rate": 0.55, "seed": 0}
        )
        for submitted in ([], None, "manifest", 7, True):
            with self.subTest(submitted=submitted):
                wt = Path(start_iteration(campaign)["worktree"])
                self._commit_quality(wt, "0.70\n")
                (wt / "manifest.json").write_text(json.dumps(submitted))

                gate = self._assert_rejected_transaction(
                    campaign,
                    run_iteration(campaign),
                    expected_submission=submitted,
                    expected_error="manifest must be a JSON object",
                )
                errors = gate["rungs"][0]["detail"]["manifest_errors"]
                self.assertIn("manifest must be a JSON object", errors)

    def test_non_object_prediction_finishes_rejected_transaction(self) -> None:
        campaign = self._new_campaign("cmp", self._command_adapter())
        wt = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(wt, "0.70\n")
        self._write_manifest(wt, predicted=self.flipping[:1])
        submitted = json.loads((wt / "manifest.json").read_text())
        submitted["predicted_improvements"] = ["not-an-object"]
        (wt / "manifest.json").write_text(json.dumps(submitted))

        gate = self._assert_rejected_transaction(
            campaign,
            run_iteration(campaign),
            expected_submission=submitted,
            expected_error="predicted_improvements[0] must be an object",
        )
        errors = gate["rungs"][0]["detail"]["manifest_errors"]
        self.assertIn("predicted_improvements[0] must be an object", errors)

    def test_context_invalid_path_preserves_original_submission_and_errors(self) -> None:
        campaign = self._new_campaign("cmp", self._command_adapter())
        wt = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(wt, "0.70\n")
        self._write_manifest(wt, predicted=self.flipping[:1])
        submitted = json.loads((wt / "manifest.json").read_text())
        submitted["treatment"]["change_scope"] = [
            "harness/components/policy/../observation/observation_contract.md"
        ]
        (wt / "manifest.json").write_text(json.dumps(submitted))

        gate = self._assert_rejected_transaction(
            campaign,
            run_iteration(campaign),
            expected_submission=submitted,
            expected_error=(
                "unsafe change_scope path: "
                "'harness/components/policy/../observation/observation_contract.md'"
            ),
        )
        self.assertEqual(gate["rungs"][0]["status"], "fail")

    def test_optimizer_status_spoof_is_rejected_and_overwritten(self) -> None:
        campaign = self._new_campaign("cmp", self._command_adapter())
        wt = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(wt, "0.70\n")
        self._write_manifest(wt, predicted=self.flipping[:1], status="accepted")

        submitted = json.loads((wt / "manifest.json").read_text())
        gate = self._assert_rejected_transaction(
            campaign,
            run_iteration(campaign),
            expected_submission=submitted,
        )
        errors = gate["rungs"][0]["detail"]["manifest_errors"]
        self.assertTrue(any("conductor owns terminal status" in error for error in errors))

    def test_e2_rejection_writes_trusted_terminal_snapshot_status(self) -> None:
        campaign = self._new_campaign(
            "cmp", {"kind": "harness-fixture", "file": QUALITY_REL,
                    "default_pass_rate": 0.55, "seed": 0}
        )
        wt = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(wt, "0.00\n")
        self._write_manifest(wt, predicted=self.flipping[:1])

        gate = self._assert_rejected_transaction(campaign, run_iteration(campaign))
        self.assertEqual(
            [(rung["rung"], rung["status"]) for rung in gate["rungs"]],
            [("E0", "pass"), ("E1", "pass"), ("E2", "fail")],
        )

    def test_pivot_rejection_writes_trusted_terminal_snapshot_status(self) -> None:
        campaign = self._new_campaign("cmp", self._command_adapter())
        campaign.state["failed_attempts"]["stub/real_v1/failed::policy"] = 2
        campaign.state["iterations_since_accept"] = 7
        campaign.state["iterations_since_divergent"] = 9
        campaign.save_state()
        wt = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(wt, "0.70\n")
        self._write_manifest(wt, predicted=self.flipping[:1])
        before = (
            campaign.learnings_path.read_text(encoding="utf-8")
            if campaign.learnings_path.is_file()
            else ""
        )

        gate = self._assert_rejected_transaction(campaign, run_iteration(campaign))
        self.assertIn("pivot_rule", gate["rungs"][0]["detail"])
        after = campaign.learnings_path.read_text(encoding="utf-8")
        self.assertNotEqual(after, before)
        records = read_records(
            campaign.learnings_path, campaign_root=campaign.store.campaign_dir
        )
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["decision"]["label"], "simulated:rejected")
        self.assertEqual(records[0]["hypothesis"], "raise policy quality")
        self.assertEqual(records[0]["cluster_ref"], "stub/real_v1/failed")
        self.assertEqual(records[0]["target_component"], "policy")
        self.assertEqual(campaign.state["iterations_since_accept"], 7)
        self.assertEqual(campaign.state["iterations_since_divergent"], 9)
        self.assertEqual(
            campaign.state["failed_attempts"],
            {"stub/real_v1/failed::policy": 2},
        )

    # ── ADR-0018 D1: one frozen protocol and closed per-run identities ──
    def test_protocol_digest_tracks_content_and_exact_runtime_identities(self) -> None:
        campaign = self._new_campaign("identity", {"kind": "fixture", "seed": 0})
        gitutil.worktree_add(
            campaign.repo_root,
            campaign.worktree_path,
            campaign.state["accepted_base_sha"],
        )
        worktree = campaign.worktree_path
        try:
            original = build_protocol_snapshot(campaign, worktree, iteration=1)
            digests = {original["protocol_digest"]}

            catalog = worktree / "evals/catalog/tasks.jsonl"
            rows = catalog.read_text(encoding="utf-8").splitlines()
            first = json.loads(rows[0])
            first["goal"] = first["goal"] + " content mutation"
            rows[0] = json.dumps(first, sort_keys=True)
            catalog.write_text("\n".join(rows) + "\n", encoding="utf-8")
            digests.add(
                build_protocol_snapshot(campaign, worktree, iteration=1)["protocol_digest"]
            )
            _git(worktree, "checkout", "--", "evals/catalog/tasks.jsonl")

            campaign.config["identity"]["executor"]["revision"] = "simulated:v2"
            digests.add(
                build_protocol_snapshot(campaign, worktree, iteration=1)["protocol_digest"]
            )
            campaign.config["identity"]["executor"]["revision"] = "simulated:v1"

            campaign.config["identity"]["verifier_bundle"]["bundle_digest"] = "1" * 64
            digests.add(
                build_protocol_snapshot(campaign, worktree, iteration=1)["protocol_digest"]
            )
            campaign.config["identity"]["verifier_bundle"]["bundle_digest"] = original[
                "verifier_bundle"
            ]["bundle_digest"]

            source = original["matched_blocks"][0]["source"]
            campaign.config["identity"]["source_runtimes"][source]["reset"]["digest"] = "2" * 64
            digests.add(
                build_protocol_snapshot(campaign, worktree, iteration=1)["protocol_digest"]
            )
            campaign.config["identity"]["source_runtimes"][source]["reset"]["digest"] = original[
                "source_runtimes"
            ][source]["reset"]["digest"]
            campaign.config["identity"]["source_runtimes"][source]["browser"]["digest"] = "3" * 64
            digests.add(
                build_protocol_snapshot(campaign, worktree, iteration=1)["protocol_digest"]
            )

            lane = worktree / "harness/lanes/structured.lane.json"
            lane.write_text(lane.read_text() + "\n", encoding="utf-8")
            digests.add(
                build_protocol_snapshot(campaign, worktree, iteration=1)["protocol_digest"]
            )
            self.assertEqual(len(digests), 7)
        finally:
            gitutil.worktree_remove(campaign.repo_root, worktree)

    def test_frozen_protocol_is_no_overwrite_reloadable_and_tamper_evident(self) -> None:
        campaign = self._new_campaign("freeze", {"kind": "fixture", "seed": 0})
        gitutil.worktree_add(
            campaign.repo_root,
            campaign.worktree_path,
            campaign.state["accepted_base_sha"],
        )
        try:
            snapshot = build_protocol_snapshot(
                campaign, campaign.worktree_path, iteration=1
            )
            iteration_dir = campaign.iteration_dir(1)
            path = freeze_protocol(iteration_dir, snapshot)
            self.assertEqual(load_frozen_protocol(iteration_dir), snapshot)
            with self.assertRaisesRegex(ProtocolError, "will not be overwritten"):
                freeze_protocol(iteration_dir, snapshot)
            tampered = json.loads(path.read_text())
            tampered["executor"]["revision"] = "simulated:tampered"
            path.write_text(json.dumps(tampered) + "\n")
            with self.assertRaisesRegex(ProtocolError, "binding_digest|protocol_digest"):
                load_frozen_protocol(iteration_dir)
        finally:
            gitutil.worktree_remove(campaign.repo_root, campaign.worktree_path)

    def test_start_freezes_before_baseline_and_later_config_mutation_is_inert(self) -> None:
        campaign = self._new_campaign("frozen", {"kind": "fixture", "seed": 0})
        started = start_iteration(campaign)
        iteration_dir = campaign.iteration_dir(started["iteration"])
        protocol_path = iteration_dir / "protocol.snapshot.json"
        frozen_bytes = protocol_path.read_bytes()
        protocol = load_frozen_protocol(iteration_dir)
        baseline_record = json.loads(
            (iteration_dir / "eval/dev_baseline/run.json").read_text()
        )
        self.assertEqual(
            baseline_record["run_context"]["protocol_digest"],
            protocol["protocol_digest"],
        )

        campaign.config["adapter"] = {"kind": "unsupported-after-start"}
        campaign.config["suites"] = {
            "dev": "missing-after-start",
            "smoke": "missing-after-start",
            "regression": "missing-after-start",
        }
        campaign.config["identity"]["executor"]["revision"] = "simulated:mutated"
        campaign.save_config()
        result = run_iteration(campaign)
        self.assertEqual(result["decision"], "rejected")
        self.assertEqual(protocol_path.read_bytes(), frozen_bytes)
        ledger = json.loads(campaign.ledger_path.read_text().splitlines()[-1])
        self.assertEqual(ledger["protocol_digest"], protocol["protocol_digest"])

    def test_start_preflight_preserves_existing_iteration_and_state(self) -> None:
        campaign = self._new_campaign("preflight", {"kind": "fixture", "seed": 0})
        iteration_dir = campaign.iteration_dir(1)
        iteration_dir.mkdir(parents=True)
        sentinel = iteration_dir / "owner-artifact.txt"
        sentinel.write_text("preserve\n", encoding="utf-8")
        state_before = json.loads(json.dumps(campaign.state))

        with self.assertRaisesRegex(RuntimeError, "next iteration path already exists"):
            start_iteration(campaign)

        self.assertEqual(campaign.state, state_before)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve\n")
        self.assertFalse(campaign.worktree_path.exists())

    def test_start_adapter_identity_failure_cleans_only_new_state(self) -> None:
        campaign = self._new_campaign("adapter-drift", {"kind": "fixture", "seed": 0})
        gitutil.worktree_add(
            campaign.repo_root,
            campaign.worktree_path,
            campaign.state["accepted_base_sha"],
        )
        snapshot = build_protocol_snapshot(
            campaign,
            campaign.worktree_path,
            iteration=1,
        )
        gitutil.worktree_remove(campaign.repo_root, campaign.worktree_path)
        mismatched = FixtureAdapter(pass_rate=0.55, seed=99).describe()
        snapshot["adapter"] = normalize_adapter_identity(mismatched)
        for name in (
            "calibration_binding_digest",
            "comparison_apparatus_digest",
            "protocol_digest",
        ):
            snapshot.pop(name)
        snapshot = finalize_protocol_snapshot(snapshot)
        state_before = json.loads(json.dumps(campaign.state))

        with (
            mock.patch(
                "opti_loop.conductor.build_protocol_snapshot",
                return_value=snapshot,
            ),
            self.assertRaisesRegex(ValueError, "adapter identity does not match"),
        ):
            start_iteration(campaign)

        self.assertEqual(campaign.state, state_before)
        self.assertFalse(campaign.worktree_path.exists())
        self.assertFalse(campaign.iteration_dir(1).exists())

    def test_comparison_uses_apparatus_not_campaign_run_or_build_identity(self) -> None:
        left = self._new_campaign("compare-left", {"kind": "fixture", "seed": 0})
        right = self._new_campaign("compare-right", {"kind": "fixture", "seed": 0})

        def protocol(label: str, campaign_id: str, iteration: int) -> dict:
            adapter = FixtureAdapter(pass_rate=1.0, seed=0)
            snapshot = simulated_protocol(
                suite={"id": "comparison-suite", "kind": "test"},
                tasks=[
                    {
                        "id": "comparison-task",
                        "source": "test-source",
                        "goal": "test",
                    }
                ],
                adapter=adapter.describe(),
            )
            snapshot["campaign_id"] = campaign_id
            snapshot["iteration"] = iteration
            snapshot["accepted_build"].update(
                commit_sha=f"simulated:{label}:commit",
                tree_sha=f"simulated:{label}:tree",
                materialized_digest=digest_json(
                    label,
                    domain="test.accepted-build.v1",
                ),
            )
            snapshot["execution"]["accepted_protection"].update(
                champion_sha=f"simulated:{label}:commit",
            )
            for name in (
                "calibration_binding_digest",
                "comparison_apparatus_digest",
                "protocol_digest",
            ):
                snapshot.pop(name)
            return finalize_protocol_snapshot(snapshot)

        left_protocol = protocol("left", left.campaign_id, 2)
        right_protocol = protocol("right", right.campaign_id, 7)
        self.assertNotEqual(left_protocol["protocol_digest"], right_protocol["protocol_digest"])
        self.assertEqual(
            left_protocol["comparison_apparatus_digest"],
            right_protocol["comparison_apparatus_digest"],
        )
        accepted = SimpleNamespace(
            protocol_snapshot=left_protocol,
            summary={"strict_success_rate": 1.0},
        )
        with mock.patch(
            "opti_loop.conductor._load_accepted_run",
            side_effect=[accepted, accepted],
        ):
            report = compare_campaigns(
                self.repo,
                [left.campaign_id, right.campaign_id],
                store_root=self.store,
            )
        self.assertTrue(report["comparable"], report)

    def test_comparison_fails_closed_for_missing_or_different_identity(self) -> None:
        left = self._new_campaign("compare-base", {"kind": "fixture", "seed": 0})
        different = self._new_campaign(
            "compare-different",
            {"kind": "fixture", "seed": 0},
        )
        missing = self._new_campaign("compare-missing", {"kind": "fixture", "seed": 0})
        base_run = SimpleNamespace(
            protocol_snapshot={
                "comparison_apparatus_digest": "a" * 64,
                "executor": {"model": "model-a"},
                "execution": {"suites": {"dev": "suite-a"}},
            },
            summary={"strict_success_rate": 0.75},
        )
        different_run = SimpleNamespace(
            protocol_snapshot={
                "comparison_apparatus_digest": "b" * 64,
                "executor": {"model": "model-a"},
                "execution": {"suites": {"dev": "suite-a"}},
            },
            summary={"strict_success_rate": 0.80},
        )
        with mock.patch(
            "opti_loop.conductor._load_accepted_run",
            side_effect=[base_run, different_run],
        ):
            report = compare_campaigns(
                self.repo,
                [left.campaign_id, different.campaign_id],
                store_root=self.store,
            )
        self.assertFalse(report["comparable"])
        self.assertIn("differ", report["non_comparable_reason"])

        with mock.patch(
            "opti_loop.conductor._load_accepted_run",
            side_effect=[base_run, None],
        ):
            missing_report = compare_campaigns(
                self.repo,
                [left.campaign_id, missing.campaign_id],
                store_root=self.store,
            )
        self.assertFalse(missing_report["comparable"])
        self.assertIn("missing accepted", missing_report["non_comparable_reason"])


    def test_accepted_loader_rejects_simulated_anchor(self) -> None:
        campaign = self._new_campaign("simulated-anchor", {"kind": "fixture", "seed": 0})
        campaign.state.update(
            last_accepted_treatment_dir=str(campaign.store.campaign_dir),
            last_accepted_admission_receipt=None,
        )
        with self.assertRaisesRegex(RuntimeError, "missing.*AR-003 admission"):
            _load_accepted_run(campaign)

    def test_stale_noise_binding_changes_with_executor_identity(self) -> None:
        campaign = self._new_campaign("stale-noise", {"kind": "fixture", "seed": 0})
        band = measure_noise(campaign, runs=2)
        noise_protocol = load_frozen_protocol(campaign.store.campaign_dir / "noise")
        self.assertEqual(band.run_identity, noise_protocol["calibration_binding_digest"])

        campaign.config["identity"]["executor"]["revision"] = "simulated:v2"
        started = start_iteration(campaign)
        iteration_protocol = load_frozen_protocol(
            campaign.iteration_dir(started["iteration"])
        )
        self.assertNotEqual(
            band.run_identity, iteration_protocol["calibration_binding_digest"]
        )
        run_iteration(campaign)

    def test_digest_only_legacy_noise_band_cannot_grant_a_decision(self) -> None:
        campaign = self._new_campaign("digest-only-noise", {"kind": "fixture", "seed": 0})
        base_before = campaign.state["accepted_base_sha"]
        band = measure_noise(campaign, runs=2).to_dict()
        band.pop("sample_anchors")
        band["synthetic"] = False
        band["admission_receipt_digests"] = ["a" * 64, "b" * 64]
        campaign.config["noise_band"] = band
        campaign.save_config()

        started = start_iteration(campaign)
        worktree = Path(started["worktree"])
        self._commit_quality(worktree, "0.70\n")
        self._write_manifest(worktree, predicted=self.flipping[:2])
        result = run_iteration(campaign)

        self.assertEqual(result["decision"], "invalid")
        self.assertFalse(result["advanced_accepted_state"])
        self.assertEqual(campaign.state["accepted_base_sha"], base_before)
        report = json.loads(
            (campaign.iteration_dir(result["iteration"]) / "gate-report.json").read_text()
        )
        self.assertEqual(report["rungs"][-1]["status"], "invalid")
        self.assertNotEqual(report["verdict"]["decision"], "accepted")

    def test_benchmark_preflight_rejects_simulated_identity_before_baseline(self) -> None:
        campaign = self._new_campaign("production", {"kind": "fixture", "seed": 0})
        campaign.config["identity"]["evidence_mode"] = "benchmark"
        with self.assertRaisesRegex(
            ProtocolError, "benchmark verifier admissions file is missing"
        ):
            start_iteration(campaign)
        self.assertEqual(campaign.current_iteration, 0)
        self.assertFalse(campaign.worktree_path.exists())
        self.assertFalse((campaign.iteration_dir(1) / "eval/dev_baseline").exists())

    def test_foreground_lifecycle_pause_resume_and_status_use_existing_transaction(self) -> None:
        campaign = self._new_campaign(
            "foreground-lifecycle",
            {"kind": "harness-fixture", "file": QUALITY_REL,
             "default_pass_rate": 0.55, "seed": 0},
        )
        self.assertEqual(operation_status(campaign)["blockers"], [])
        lifecycle_request(campaign, "pause")
        with self.assertRaisesRegex(RuntimeError, "campaign is paused.*resume"):
            start_iteration(campaign)
        with self.assertRaisesRegex(RuntimeError, "use `opti-loop resume`"):
            lifecycle_request(campaign, "run")
        lifecycle_request(campaign, "run", resume=True)
        worktree = Path(start_iteration(campaign)["worktree"])
        lifecycle_request(campaign, "pause")
        with self.assertRaisesRegex(RuntimeError, "campaign is paused.*resume"):
            run_iteration(campaign)
        lifecycle_request(campaign, "run", resume=True)
        self._commit_quality(worktree, "0.56\n")
        self._write_manifest(worktree, predicted=self.flipping[:1])
        result = run_iteration(campaign)
        self.assertFalse(result["advanced_accepted_state"])
        report = operation_status(campaign)
        self.assertEqual(report["pending_iteration"], 0)
        self.assertEqual(report["attempts_started"], 1)
        record = read_records(
            campaign.learnings_path, campaign_root=campaign.store.campaign_dir
        )[-1]
        self.assertEqual(record["decision"]["evidence_class"], "simulated")
        self.assertEqual(set(record["source_disposition"]), {"sources", "executed"})
        self.assertTrue(record["source_disposition"]["executed"])
        lifecycle_request(campaign, "stop")
        with self.assertRaisesRegex(RuntimeError, "use `opti-loop resume`"):
            lifecycle_request(campaign, "run")
        self.assertEqual(
            lifecycle_request(campaign, "run", resume=True)["state"], "running"
        )

    def test_lifecycle_request_reloads_state_after_campaign_lock(self) -> None:
        stale = self._new_campaign(
            "lifecycle-stale", {"kind": "fixture", "seed": 0}
        )
        concurrent = load_campaign(
            self.repo, stale.campaign_id, store_root=self.store
        )
        concurrent.state["operation_attempts"] = 7
        concurrent.state["cleanup_health"] = {
            "status": "failed", "detail": "conductor cleanup checkpoint"
        }
        concurrent.save_state()

        lifecycle_request(stale, "pause")
        reloaded = load_campaign(
            self.repo, stale.campaign_id, store_root=self.store
        )
        self.assertEqual(reloaded.state["operation_attempts"], 7)
        self.assertEqual(
            reloaded.state["cleanup_health"]["detail"],
            "conductor cleanup checkpoint",
        )
        self.assertEqual(reloaded.state["lifecycle"]["request"], "pause")

    def test_canonical_publication_status_blocks_malformed_cli_routing(self) -> None:
        campaign = self._new_campaign(
            "malformed-routing", {"kind": "fixture", "seed": 0}
        )
        malformed = _seal_publication_record({
            "schema_version": "0.4.0",
            "record_type": "accepted-publication",
            "campaign_id": campaign.campaign_id,
            "status": "pending",
        })
        (campaign.store.campaign_dir / "accepted-publication.json").write_text(
            json.dumps(malformed, indent=2, sort_keys=True) + "\n"
        )
        projected = publication_status(campaign)
        self.assertEqual(projected["status"], "malformed")
        self.assertIn("invalid closed shape", projected["error"])
        self.assertTrue(any(
            "publication record is malformed" in blocker
            for blocker in operation_status(campaign)["blockers"]
        ))
        stderr = StringIO()
        with redirect_stderr(stderr):
            code = cli_main([
                "--repo-root", str(self.repo),
                "--store-root", str(self.store),
                "run", "--campaign", campaign.campaign_id,
            ])
        self.assertEqual(code, 2)
        self.assertIn("publication record is malformed", stderr.getvalue())

    def test_missing_terminal_receipt_blocks_every_iteration_route(self) -> None:
        campaign = self._new_campaign(
            "missing-terminal-receipt",
            {"kind": "harness-fixture", "file": QUALITY_REL,
             "default_pass_rate": 0.55, "seed": 0},
        )
        self.assertEqual(publication_status(campaign)["status"], "none")
        self.assertEqual(operation_status(campaign)["blockers"], [])

        worktree = Path(start_iteration(campaign)["worktree"])
        self.assertEqual(publication_status(campaign)["status"], "none")
        self._commit_quality(worktree, "0.00\n")
        self._write_manifest(worktree, predicted=self.flipping[:1])
        result = run_iteration(campaign)
        self.assertEqual(result["decision"], "rejected")
        publication_path = campaign.store.campaign_dir / "accepted-publication.json"
        self.assertTrue(publication_path.is_file())
        publication_path.unlink()

        projected = publication_status(campaign)
        self.assertEqual(projected["status"], "malformed")
        self.assertIn("receipt is missing", projected["error"])
        self.assertTrue(any(
            "publication record is malformed" in blocker
            for blocker in operation_status(campaign)["blockers"]
        ))
        for route in (
            lambda: start_iteration(campaign),
            lambda: run_iteration(campaign),
            lambda: continue_campaign(campaign),
        ):
            with self.subTest(route=route), self.assertRaisesRegex(
                RuntimeError, "publication receipt is missing"
            ):
                route()

        lifecycle_request(campaign, "stop")
        with self.assertRaisesRegex(RuntimeError, "publication receipt is missing"):
            lifecycle_request(campaign, "run", resume=True)
        reloaded = load_campaign(
            self.repo, campaign.campaign_id, store_root=self.store
        )
        self.assertEqual(reloaded.state["lifecycle"]["state"], "stopped")

        for command in ("run", "resume"):
            stderr = StringIO()
            with self.subTest(command=command), redirect_stderr(stderr):
                code = cli_main([
                    "--repo-root", str(self.repo),
                    "--store-root", str(self.store),
                    command, "--campaign", campaign.campaign_id,
                ])
            self.assertEqual(code, 2)
            self.assertIn("publication receipt is missing", stderr.getvalue())

    def test_cli_run_reloads_locked_state_before_routing_concurrent_pending_work(self) -> None:
        campaign = self._new_campaign(
            "concurrent-cli-route",
            {"kind": "harness-fixture", "file": QUALITY_REL,
             "default_pass_rate": 0.55, "seed": 0},
        )
        lifecycle_request(campaign, "run")
        real_request = lifecycle_request

        def request_then_open_iteration(current, value, *, resume=False):
            lifecycle = real_request(current, value, resume=resume)
            concurrent = load_campaign(
                self.repo, current.campaign_id, store_root=self.store
            )
            worktree = Path(start_iteration(concurrent)["worktree"])
            self._commit_quality(worktree, "0.56\n")
            self._write_manifest(worktree, predicted=self.flipping[:1])
            return lifecycle

        with mock.patch("opti_loop.cli.request", side_effect=request_then_open_iteration):
            code = cli_main([
                "--repo-root", str(self.repo),
                "--store-root", str(self.store),
                "run", "--campaign", campaign.campaign_id,
            ])
        self.assertEqual(code, 0)
        reloaded = load_campaign(self.repo, campaign.campaign_id, store_root=self.store)
        self.assertEqual(reloaded.current_iteration, 1)
        self.assertEqual(reloaded.state["pending_iteration"], 0)
        self.assertEqual(len(reloaded.ledger_path.read_text().splitlines()), 1)

    def test_terminal_publication_status_requires_retained_authoritative_artifacts(self) -> None:
        campaign = self._new_campaign(
            "terminal-status-artifacts",
            {"kind": "harness-fixture", "file": QUALITY_REL,
             "default_pass_rate": 0.55, "seed": 0},
        )
        worktree = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(worktree, "0.56\n")
        self._write_manifest(worktree, predicted=self.flipping[:1])
        run_iteration(campaign)
        self.assertEqual(publication_status(campaign)["status"], "complete")
        ledger = campaign.ledger_path.read_text()
        learning = campaign.learnings_path.read_text()
        snapshot_path = campaign.iteration_dir(1) / "manifest.snapshot.json"
        snapshot = snapshot_path.read_text()
        next_iteration = start_iteration(campaign)
        self.assertEqual(next_iteration["iteration"], 2)
        self.assertEqual(campaign.state["pending_iteration"], 2)
        historical = publication_status(campaign)
        self.assertEqual(historical["status"], "complete")
        self.assertEqual(historical["iteration"], 1)

        ledger_row = json.loads(ledger)
        altered_ledger = {**ledger_row, "hypothesis": "corrupted hypothesis"}
        expanded_ledger = {**ledger_row, "unexpected": "not canonical"}
        altered_snapshot = json.loads(snapshot)
        altered_snapshot["target_component"] = "actions"
        mutations = {
            "missing ledger": ("", learning, snapshot, "run"),
            "duplicate learning": (ledger, learning + learning, snapshot, "resume"),
            "inconsistent learning": (
                ledger,
                learning.replace('"campaign_id": "terminal-status-artifacts"',
                                 '"campaign_id": "other"'),
                snapshot,
                "run",
            ),
            "non-receipt ledger field": (
                json.dumps(altered_ledger, sort_keys=True) + "\n",
                learning,
                snapshot,
                "run",
            ),
            "ledger closed shape": (
                json.dumps(expanded_ledger, sort_keys=True) + "\n",
                learning,
                snapshot,
                "resume",
            ),
            "manifest snapshot field": (
                ledger,
                learning,
                json.dumps(altered_snapshot, indent=2, sort_keys=True) + "\n",
                "resume",
            ),
        }
        for label, (ledger_bytes, learning_bytes, snapshot_bytes, command) in (
            mutations.items()
        ):
            with self.subTest(label=label):
                campaign.ledger_path.write_text(ledger_bytes)
                campaign.learnings_path.write_text(learning_bytes)
                snapshot_path.write_text(snapshot_bytes)
                projected = publication_status(campaign)
                self.assertEqual(projected["status"], "malformed")
                self.assertTrue(projected["recovery_required"])
                stderr = StringIO()
                with redirect_stderr(stderr):
                    code = cli_main([
                        "--repo-root", str(self.repo),
                        "--store-root", str(self.store),
                        command, "--campaign", campaign.campaign_id,
                    ])
                self.assertEqual(code, 2)
                self.assertIn("publication record is malformed", stderr.getvalue())
        campaign.ledger_path.write_text(ledger)
        campaign.learnings_path.write_text(learning)
        snapshot_path.write_text(snapshot)
        self.assertEqual(publication_status(campaign)["status"], "complete")

    def test_canonical_ledger_reader_rejects_invalid_jsonl_rows(self) -> None:
        campaign = self._new_campaign(
            "strict-ledger-reader",
            {"kind": "harness-fixture", "file": QUALITY_REL,
             "default_pass_rate": 0.55, "seed": 0},
        )
        worktree = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(worktree, "0.56\n")
        self._write_manifest(worktree, predicted=self.flipping[:1])
        run_iteration(campaign)
        valid = campaign.ledger_path.read_text()
        valid_record = valid.removesuffix("\n")
        row = json.loads(valid)
        missing = dict(row)
        missing.pop("hypothesis")
        extra = {**row, "unexpected": True}
        duplicate = valid.replace(
            '"iteration": 1', '"iteration": 1, "iteration": 1', 1
        )
        cases = {
            "malformed JSON": "{\n",
            "duplicate key": duplicate,
            "non-object": "[]\n",
            "missing field": json.dumps(missing) + "\n",
            "extra field": json.dumps(extra) + "\n",
        }
        for label, contents in cases.items():
            with self.subTest(label=label):
                campaign.ledger_path.write_text(contents)
                with self.assertRaisesRegex(ValueError, "ledger row 1"):
                    read_rows(campaign.ledger_path)
        campaign.ledger_path.write_text(valid)
        self.assertEqual(len(read_rows(campaign.ledger_path)), 1)

        campaign.ledger_path.write_bytes(b"")
        self.assertEqual(read_rows(campaign.ledger_path), [])
        for label, contents in {
            "LF": valid_record + "\n",
            "CRLF": valid_record + "\r\n",
            "no final delimiter": valid_record,
        }.items():
            with self.subTest(valid_framing=label):
                campaign.ledger_path.write_bytes(contents.encode())
                self.assertEqual(len(read_rows(campaign.ledger_path)), 1)

        framing_cases = {
            "blank physical row": (
                valid_record + "\n\n" + valid_record,
                "ledger JSONL record 2",
            ),
            "whitespace physical row": (
                valid_record + "\n \t\n" + valid_record,
                "ledger JSONL record 2",
            ),
            "extra trailing delimiter": (
                valid_record + "\n\n",
                "ledger JSONL record 2",
            ),
            "raw carriage return": (
                valid_record + "\r" + valid_record,
                "ledger JSONL record 1",
            ),
            "Unicode line separator": (
                valid_record + "\u2028" + valid_record,
                "ledger row 1",
            ),
            "Unicode paragraph separator": (
                valid_record + "\u2029" + valid_record,
                "ledger row 1",
            ),
        }
        for label, (contents, diagnostic) in framing_cases.items():
            with self.subTest(invalid_framing=label):
                campaign.ledger_path.write_bytes(contents.encode())
                with self.assertRaisesRegex(ValueError, diagnostic):
                    read_rows(campaign.ledger_path)
        campaign.ledger_path.write_text(valid)

    def test_status_publication_and_packet_fail_closed_on_invalid_ledger(self) -> None:
        campaign = self._new_campaign(
            "invalid-ledger-consumers",
            {"kind": "harness-fixture", "file": QUALITY_REL,
             "default_pass_rate": 0.55, "seed": 0},
        )
        worktree = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(worktree, "0.56\n")
        self._write_manifest(worktree, predicted=self.flipping[:1])
        run_iteration(campaign)
        valid = campaign.ledger_path.read_text()
        campaign.ledger_path.write_text(
            valid.replace('"iteration": 1', '"iteration": 1, "iteration": 1', 1)
        )

        publication = publication_status(campaign)
        self.assertEqual(publication["status"], "malformed")
        self.assertIn("ledger row 1", publication["error"])
        stdout = StringIO()
        with redirect_stdout(stdout):
            code = cli_main([
                "--repo-root", str(self.repo),
                "--store-root", str(self.store),
                "status", "--campaign", campaign.campaign_id,
            ])
        self.assertEqual(code, 0)
        status = json.loads(stdout.getvalue())
        self.assertNotIn("ledger_rows", status)
        self.assertNotIn("last", status)
        blockers = status["operation"]["blockers"]
        self.assertTrue(any("publication record is malformed" in item for item in blockers))
        self.assertTrue(any("ledger row 1" in item for item in blockers))

        packet_dir = campaign.store.campaign_dir / "invalid-ledger-packet"
        packet_dir.mkdir()
        with self.assertRaisesRegex(ValueError, "ledger row 1"):
            build_packet(
                iteration_dir=packet_dir,
                iteration=2,
                campaign_id=campaign.campaign_id,
                divergent=False,
                ranked_clusters=[],
                ledger_path=campaign.ledger_path,
                baseline_summary={},
                candidate_allowlist=["harness/components/"],
                latest_learning_record=None,
            )
        self.assertFalse((packet_dir / "packet.json").exists())
        campaign.ledger_path.write_text(valid)

    def test_status_exposes_ref_split_failed_cleanup_and_external_meter_blockers(self) -> None:
        campaign = self._new_campaign("status-blockers", {"kind": "fixture", "seed": 0})
        campaign.state["accepted_iterations"] = [1]
        campaign.state["cleanup_health"] = {
            "status": "failed", "detail": "WARC lifecycle cleanup failed: worker not reaped"
        }
        campaign.config["operation"]["external_metering"] = "unavailable"
        campaign.save_state()
        campaign.save_config()
        self.assertFalse(accepted_ref_status(campaign)["ok"])
        found = operation_status(campaign)["blockers"]
        self.assertTrue(any("accepted-ref" in item for item in found))
        self.assertTrue(any("worker not reaped" in item for item in found))
        self.assertTrue(any("external spend/token metering" in item for item in found))
        with self.assertRaisesRegex(RuntimeError, "worker not reaped"):
            start_iteration(campaign)

    def test_malformed_or_exhausted_closed_limits_fail_before_advancement(self) -> None:
        campaign = self._new_campaign("bad-limits", {"kind": "fixture", "seed": 0})
        campaign.config["operation"].pop("max_attempts")
        campaign.save_config()
        self.assertIn("invalid closed shape", operation_blockers(campaign, action="start")[0])
        with self.assertRaisesRegex(RuntimeError, "invalid closed shape"):
            start_iteration(campaign)

        campaign = self._new_campaign("spent-limits", {"kind": "fixture", "seed": 0})
        campaign.config["operation"]["max_iterations"] = 1
        campaign.save_config()
        start_iteration(campaign)
        run_iteration(campaign)
        with self.assertRaisesRegex(RuntimeError, "iteration limit is exhausted"):
            start_iteration(campaign)

        campaign = self._new_campaign("spent-attempts", {"kind": "fixture", "seed": 0})
        start_iteration(campaign)
        campaign.config["operation"]["max_attempts"] = 1
        campaign.state["operation_attempts"] = 1
        campaign.save_config()
        campaign.save_state()
        with self.assertRaisesRegex(RuntimeError, "attempt limit is exhausted"):
            run_iteration(campaign)

        campaign = self._new_campaign("bad-lifecycle", {"kind": "fixture", "seed": 0})
        campaign.state["lifecycle"]["state"] = "mystery"
        campaign.save_state()
        self.assertIn(
            "lifecycle state is invalid",
            operation_status(campaign)["blockers"][0],
        )

    def test_invalid_learning_citation_blocks_the_next_optimizer_packet(self) -> None:
        campaign = self._new_campaign(
            "learning-citation",
            {"kind": "harness-fixture", "file": QUALITY_REL,
             "default_pass_rate": 0.55, "seed": 0},
        )
        worktree = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(worktree, "0.56\n")
        self._write_manifest(worktree, predicted=self.flipping[:1])
        run_iteration(campaign)
        row = json.loads(campaign.learnings_path.read_text().strip())
        row["citations"][0]["sha256"] = "0" * 64
        campaign.learnings_path.write_text(json.dumps(row) + "\n")
        with self.assertRaisesRegex(ValueError, "citation checksum mismatch"):
            start_iteration(campaign)

    def test_invalid_benchmark_learning_is_gate_only_and_nonreportable(self) -> None:
        campaign = self._new_campaign(
            "invalid-benchmark-learning",
            {"kind": "harness-fixture", "file": QUALITY_REL,
             "default_pass_rate": 0.55, "seed": 0},
        )
        worktree = Path(start_iteration(campaign)["worktree"])
        self._commit_quality(worktree, "0.70\n")
        self._write_manifest(worktree, predicted=self.flipping[:1])
        bundle, sidecar = self._static_handback(campaign, worktree)
        invalid = GateReport(iteration=1)
        invalid.verdict = Verdict("invalid", "benchmark")
        invalid.rungs.append(
            RungResult("E1", "invalid", {"error": "trace admission failed"})
        )
        with (
            mock.patch("opti_loop.conductor._benchmark_handback_required", return_value=True),
            mock.patch(
                "opti_loop.conductor._validate_benchmark_handback_ownership",
                return_value=os.getuid(),
            ),
            mock.patch("opti_loop.conductor.run_gate", return_value=invalid),
        ):
            result = run_iteration(
                campaign, candidate_bundle=bundle, candidate_manifest=sidecar
            )
        self.assertEqual(result["decision"], "invalid")
        self.assertEqual(result["evidence_class"], "benchmark")
        record = read_records(
            campaign.learnings_path, campaign_root=campaign.store.campaign_dir
        )[0]
        self.assertEqual(record["decision"]["decision"], "invalid")
        self.assertEqual(record["decision"]["evidence_class"], "benchmark")
        self.assertEqual(set(record["source_disposition"]), {"sources", "executed"})
        self.assertFalse(record["source_disposition"]["executed"])
        self.assertEqual([citation["kind"] for citation in record["citations"]], ["gate"])
        started = start_iteration(campaign)
        packet = json.loads(
            (campaign.iteration_dir(started["iteration"]) / "packet.json").read_text()
        )
        self.assertEqual(packet["latest_learning_record"], record)


if __name__ == "__main__":
    unittest.main()
