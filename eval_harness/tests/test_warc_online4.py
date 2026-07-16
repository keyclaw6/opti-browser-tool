from __future__ import annotations

import copy
import hashlib
import json
import os
import signal
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import types
import unittest
from pathlib import Path
from unittest import mock

from opti_eval.adapters.base import AdapterExecutionContext
from opti_eval.adapters.warc_online4 import (
    CONFIG_FIELDS,
    RUNTIME_FIELDS,
    TASK_ID,
    WarcOnline4Adapter,
    WarcOnline4Error,
    load_and_preflight_config,
)
from opti_eval.identity import digest_json, simulated_identity_defaults
from opti_eval.warc_online4_runtime import action_tool_schema_digest, run_lifecycle
from opti_eval.warc_online4_runtime import (
    ONLINE4_MATCHER,
    UPSTREAM_START_URL,
    RuntimeFailure,
    _WorkerClient,
    _git_blob_sha1,
    _http_model_transport,
    _make_upstream_environment,
)


VERIFIER = ONLINE4_MATCHER + "\n"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class WarcOnline4Test(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.root = root
        self.candidate = root / "candidate"
        self.treatment = self.candidate / "harness/components/policy/quality.txt"
        self.treatment.parent.mkdir(parents=True)
        self.treatment.write_text("ok\n")
        self.verifier = root / "verifier.js"
        self.verifier.write_text(VERIFIER)
        self.wacz = root / "online4.wacz"
        self.wacz.write_bytes(b"fixture wacz")
        self.license = root / "LICENSE"
        self.license.write_text("fixture only\n")
        self.admissions = root / "admissions.jsonl"
        self.admissions.write_text(
            json.dumps(
                {
                    "verifier_id": "fixture-native-js",
                    "task_id": TASK_ID,
                    "verifier_checksum": _digest(self.verifier),
                    "admitted": True,
                }
            )
            + "\n"
        )
        self.inbox = root / "inbox"
        self.inbox.mkdir()
        python = str(Path(sys.executable).resolve())
        version = subprocess.run(
            [python, "--version"], capture_output=True, text=True, check=True
        )
        expected_version = "\n".join(
            value.strip() for value in (version.stdout, version.stderr) if value.strip()
        )
        runtime = {
            "path": python,
            "sha256": _digest(Path(python)),
            "version_command": [python, "--version"],
            "expected_version": expected_version,
        }
        defaults = simulated_identity_defaults(["warc_bench"])
        defaults["executor"]["settings"] = {"temperature": 0, "max_tokens": 256}
        defaults["executor"]["tool_schema_digest"] = action_tool_schema_digest()
        defaults["executor"].pop("snapshot", None)
        defaults["executor"].pop("revision", None)
        self.config = {
            "schema_version": "0.1.0",
            "mode": "local_fixture",
            "task": {"id": TASK_ID, "source": "warc_bench", "native_task_id": "online.4"},
            "source": {
                "upstream_commit": "98d213ccd2b4380761738e1d144467a8695e37c5",
                "manifest_path": "src/orby/subtask_benchmark/environments/benchmark.json",
                "manifest_blob_sha1": "6b2bc7ee04b3231325fe3a84b195d26d0c589287",
                "data_path": "environments/web_archives/alaska_airlines/alaska_airlines_flight_booking.wacz",
            },
            "wacz": {
                "path": str(self.wacz), "sha256": _digest(self.wacz),
                "start_url": UPSTREAM_START_URL,
            },
            "verifier": {
                "id": "fixture-native-js", "path": str(self.verifier),
                "sha256": _digest(self.verifier), "admissions_path": str(self.admissions),
                "admissions_sha256": _digest(self.admissions),
            },
            "provenance": {
                "wacz_origin": "local-fixture:generated", "verifier_origin": "local-fixture:generated",
                "license_id": "fixture-only", "license_evidence_path": str(self.license),
                "license_evidence_sha256": _digest(self.license), "acknowledged": True,
            },
            "runtime": {
                **{name: dict(runtime) for name in
                   ("python", "node", "warc_bench", "replay", "browsergym", "gymnasium",
                    "playwright", "playwright_driver", "browser", "sandbox")},
                "cdp_port": 4222,
            },
            "executor": defaults["executor"],
            "credentials": {"required_env": []},
            "confinement": {
                "single_host": True, "network": "loopback-only",
                "filesystem": "read-only-except-task-output", "optimizer_uid": os.getuid(),
                "static_inbox": str(self.inbox),
            },
            "limits": {"timeout_seconds": 30, "deadline_seconds": 60, "action_budget": 3},
            "treatment_path": "harness/components/policy/quality.txt",
            "protocol_identity": {
                "source_runtime": defaults["source_runtimes"]["warc_bench"],
                "activation_instrumentation": defaults["activation_instrumentation"],
                "lane": {"id": "structured", "config_path": "harness/lanes/structured.lane.json"},
                "repeated_protocol": defaults["repeated_protocol"],
            },
        }
        self.config_path = root / "config.json"
        self._write()
        self.task = json.loads(
            (Path(os.environ["OPTI_BROWSER_REPO_ROOT"])
             / "evals/catalog/by-id/warc_bench/warc-bench-online-4.json").read_text()
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write(self) -> None:
        self.config_path.write_text(json.dumps(self.config, indent=2) + "\n")

    def _adapter(self) -> WarcOnline4Adapter:
        return WarcOnline4Adapter(self.config_path, candidate_root=self.candidate)

    def _protocol(self) -> dict:
        identity = self.config["protocol_identity"]
        return {
            "evidence_mode": "simulated",
            "executor": {
                **self.config["executor"],
                "snapshot": self.config["executor"]["model"],
                "revision": self.config["executor"]["model"],
                "settings_digest": digest_json(
                    self.config["executor"]["settings"],
                    domain="opti.executor-settings.v1",
                ),
            },
            "verifier_bundle": {
                "id": self.config["verifier"]["id"],
                "checksum": self.config["verifier"]["sha256"],
                "bundle_digest": self.config["verifier"]["sha256"],
                "admissions_digest": hashlib.sha256(
                    b"opti.admissions.v1\0" + self.admissions.read_bytes()
                ).hexdigest(),
            },
            "source_runtimes": {"warc_bench": identity["source_runtime"]},
            "activation_instrumentation": identity["activation_instrumentation"],
            "lane": {**identity["lane"], "config_digest": "a" * 64},
            "repeated_protocol": identity["repeated_protocol"],
        }

    def _run(self):
        task_dir = self.root / f"task-{len(list(self.root.glob('task-*')))}"
        task_dir.mkdir()
        return self._adapter().run(
            self.task,
            task_dir,
            execution_context=AdapterExecutionContext(
                run_id="run-1", run_context_digest="a" * 64
            ),
        )

    def test_complete_local_fixture_shape_is_nonreportable(self) -> None:
        result = self._run()
        self.assertEqual(result.status, "passed")
        self.assertFalse(result.metadata["benchmark_reportable"])
        self.assertEqual(result.metadata["evidence_class"], "local_fixture")
        self.assertEqual(result.trace_path, "trace.jsonl")
        self.assertGreaterEqual(len(result.artifacts), 3)
        self.assertTrue(result.metadata["cleanup_completed"])
        runtime_result = json.loads(
            (self.root / "task-0" / "warc-online4" / "runtime-result.json").read_text()
        )
        self.assertIs(runtime_result["verifier"]["initial"]["passed"], False)
        self.assertIs(runtime_result["verifier"]["final"]["passed"], True)

    def test_static_production_template_tracks_closed_preflight_shape(self) -> None:
        repo_root = Path(os.environ["OPTI_BROWSER_REPO_ROOT"])
        template_path = repo_root / "evals/warc-online4.production.template.json"
        template = json.loads(template_path.read_text(encoding="utf-8"))
        self.assertEqual(set(template), CONFIG_FIELDS)
        self.assertEqual(template["schema_version"], "0.1.0")
        self.assertEqual(template["mode"], "production")
        self.assertEqual(set(template["runtime"]), RUNTIME_FIELDS)
        self.assertEqual(template["credentials"], {"required_env": ["OPENCODE_API_KEY"]})
        self.assertEqual(
            set(template["confinement"]),
            {"single_host", "network", "filesystem", "optimizer_uid", "static_inbox"},
        )
        self.assertEqual(
            set(template["protocol_identity"]["repeated_protocol"]),
            {
                "matched_blocks", "coverage", "repeats", "stopping",
                "outcome_handling", "effect", "non_inferiority", "regression",
                "champion", "transfer", "multiplicity", "limits", "calibration",
            },
        )
        rendered = template_path.read_text(encoding="utf-8")
        for placeholder in (
            "OWNER_WACZ_SHA256",
            "OWNER_VERIFIER_SHA256",
            "OWNER_ADMISSIONS_SHA256",
            "OWNER_LICENSE_EVIDENCE_SHA256",
            "OWNER_OPTIMIZER_UID_INTEGER",
            "OWNER_REAL_CALIBRATION_SHA256",
        ):
            self.assertIn(placeholder, rendered)
        qualification = (repo_root / "docs/WARC_ONLINE4_QUALIFICATION.md").read_text()
        self.assertIn(template_path.name, qualification)
        self.assertIn("--external-metering-id OWNER_APPROVED_METER_IDENTITY", qualification)
        self.assertIn("--authorize-production-campaign", qualification)

    def test_applied_model_request_contains_exact_treatment_bytes(self) -> None:
        result = self._run()
        request_ref = next(item for item in result.artifacts if item["kind"] == "executor_request")
        body = json.loads((self.root / "task-0" / request_ref["uri"]).read_text())
        self.assertIn(_digest(self.treatment), body["system"])
        self.assertIn("b2sK", body["system"])

    def test_missing_or_mismatched_external_identity_classes_fail_preflight(self) -> None:
        cases = {
            "wacz": lambda row: row["wacz"].update(sha256="0" * 64),
            "start-url": lambda row: row["wacz"].update(start_url="https://wrong.invalid/"),
            "verifier": lambda row: row["verifier"].update(sha256="0" * 64),
            "source": lambda row: row["source"].update(upstream_commit="wrong"),
            "runtime": lambda row: row["runtime"]["playwright"].update(expected_version="wrong"),
            "provenance": lambda row: row["provenance"].update(acknowledged=False),
            "inbox-owner": lambda row: row["confinement"].update(optimizer_uid=os.getuid() + 1),
            "protocol-identity": lambda row: row["protocol_identity"][
                "source_runtime"
            ].pop("reset"),
        }
        for label, mutate in cases.items():
            with self.subTest(label=label):
                original = copy.deepcopy(self.config)
                mutate(self.config)
                self._write()
                with self.assertRaises(WarcOnline4Error):
                    load_and_preflight_config(self.config_path)
                self.config = original

    def test_missing_credentials_fail_without_storing_values(self) -> None:
        self.config["mode"] = "production"
        replay = self.root / "webreplay-standalone/dist/index.js"
        replay.parent.mkdir(parents=True)
        sandbox = self.root / "bwrap"
        shutil.copy2(sys.executable, replay)
        shutil.copy2(sys.executable, sandbox)
        self.config["runtime"]["replay"].update(path=str(replay), sha256=_digest(replay))
        self.config["runtime"]["sandbox"].update(path=str(sandbox), sha256=_digest(sandbox))
        self.config["executor"].update(
            provider="opencode-go",
            route="https://opencode.ai/zen/go/v1/messages",
            model="minimax-m3",
        )
        self.config["credentials"]["required_env"] = ["OPENCODE_API_KEY"]
        self._write()
        with self.assertRaisesRegex(WarcOnline4Error, "missing required credential"):
            load_and_preflight_config(self.config_path)
        self.assertNotIn("secret-value", self.config_path.read_text())

    def test_verifier_admission_must_be_strict_positive_and_exact(self) -> None:
        cases = {
            "missing": "",
            "false": json.dumps({
                "verifier_id": "fixture-native-js", "task_id": TASK_ID,
                "verifier_checksum": _digest(self.verifier), "admitted": False,
            }) + "\n",
            "malformed": "{not-json}\n",
            "mismatch": json.dumps({
                "verifier_id": "fixture-native-js", "task_id": TASK_ID,
                "verifier_checksum": "0" * 64, "admitted": True,
            }) + "\n",
        }
        for label, contents in cases.items():
            with self.subTest(label=label):
                self.admissions.write_text(contents)
                self.config["verifier"]["admissions_sha256"] = _digest(self.admissions)
                self._write()
                with self.assertRaisesRegex(WarcOnline4Error, "verifier admission failed"):
                    load_and_preflight_config(self.config_path)

    def test_symlinked_config_is_rejected(self) -> None:
        config_link = self.root / "config-link.json"
        config_link.symlink_to(self.config_path)
        with self.assertRaisesRegex(WarcOnline4Error, "regular non-symlink"):
            WarcOnline4Adapter(config_link, candidate_root=self.candidate)

    def test_executor_identity_mismatch_fails_before_lifecycle(self) -> None:
        adapter = self._adapter()
        protocol = {"executor": {**self.config["executor"], "settings_digest": "0" * 64},
                    "verifier_bundle": {"id": self.config["verifier"]["id"],
                                        "checksum": self.config["verifier"]["sha256"]}}
        with self.assertRaisesRegex(WarcOnline4Error, "executor identity"):
            adapter.validate_protocol(protocol)

    def test_complete_frozen_protocol_identity_is_required(self) -> None:
        protocol = self._protocol()
        self._adapter().validate_protocol(protocol)
        protocol["source_runtimes"]["warc_bench"] = {"wrong": True}
        with self.assertRaisesRegex(WarcOnline4Error, "source runtime identity"):
            self._adapter().validate_protocol(protocol)

    def test_wrong_task_or_source_is_rejected(self) -> None:
        for field, value in (("id", "warc-bench-online-6"), ("source", "other")):
            wrong = copy.deepcopy(self.task)
            wrong[field] = value
            task_dir = self.root / f"wrong-{field}"
            task_dir.mkdir()
            with self.assertRaisesRegex(WarcOnline4Error, "accepts only"):
                self._adapter().run(
                    wrong, task_dir,
                    execution_context=AdapterExecutionContext("run-1", "a" * 64),
                )

    def test_reset_final_state_trace_artifact_and_activation_fail_closed(self) -> None:
        cases = {
            "bad-reset": "reset live page must independently fail",
            "bad-final": "browser step state must be an object",
            "bad-verifier": "local fixture live verifier failed",
            "bad-steps": "completed without a browser action",
            "bad-artifact": "runtime artifact is missing",
            "bad-cleanup": "cleanup failed",
        }
        for mode, message in cases.items():
            with self.subTest(mode=mode):
                self.treatment.write_text(mode)
                with self.assertRaisesRegex(WarcOnline4Error, message):
                    self._run()
        self.treatment.write_text("ok")
        with mock.patch(
            "opti_eval.adapters.warc_online4.write_jsonl", side_effect=OSError("trace full")
        ), self.assertRaisesRegex(OSError, "trace full"):
            self._run()

    def test_malformed_reset_still_closes_retained_source(self) -> None:
        class Source:
            closed = False

            def start(self):
                return UPSTREAM_START_URL

            def reset(self):
                return "not-an-object"

            def close(self):
                self.closed = True

        source = Source()
        task_dir = self.root / "malformed-reset-cleanup"
        task_dir.mkdir()
        request = {
            "schema_version": "0.2.0", "mode": "local_fixture", "task_id": TASK_ID,
            "goal": self.task["goal"], "wacz_path": str(self.wacz),
            "wacz_start_url": self.config["wacz"]["start_url"],
            "source_identity": self.config["source"],
            "verifier": {
                "id": self.config["verifier"]["id"],
                "path": str(self.verifier), "sha256": _digest(self.verifier),
            },
            "treatment_path": str(self.treatment),
            "treatment_relative_path": "harness/components/policy/quality.txt",
            "treatment_sha256": _digest(self.treatment), "runtime": self.config["runtime"],
            "executor": self.config["executor"], "credential_env": [],
            "limits": self.config["limits"], "confinement": {}, "request_digest": "a" * 64,
        }
        request_path = task_dir / "request.json"
        request_path.write_text(json.dumps(request))
        with self.assertRaisesRegex(Exception, "browser reset state must be an object"):
            run_lifecycle(request_path, task_dir / "result.json", source=source)
        self.assertTrue(source.closed)

    def test_malformed_subprocess_reset_reaps_retained_worker(self) -> None:
        program = (
            "import json,sys\n"
            "sys.stdin.readline(); print(json.dumps({'start_url':"
            + repr(UPSTREAM_START_URL)
            + ",'state':'bad'}),flush=True)\n"
            "sys.stdin.readline(); print(json.dumps({'completed':True}),flush=True)\n"
        )
        client = self._worker_client(program, 1.0)

        class Source:
            def start(inner_self):
                inner_self.row = client.call("reset")
                return inner_self.row["start_url"]

            def reset(inner_self):
                return inner_self.row["state"]

            def close(inner_self):
                try:
                    client.call("close")
                finally:
                    client.reap()

        task_dir = self.root / "malformed-subprocess-reset"
        task_dir.mkdir()
        request = {
            "mode": "local_fixture", "task_id": TASK_ID, "goal": self.task["goal"],
            "wacz_start_url": self.config["wacz"]["start_url"],
            "source_identity": self.config["source"],
            "verifier": {
                "id": self.config["verifier"]["id"], "path": str(self.verifier),
                "sha256": _digest(self.verifier),
            },
            "treatment_path": str(self.treatment),
            "treatment_relative_path": "harness/components/policy/quality.txt",
            "treatment_sha256": _digest(self.treatment), "runtime": self.config["runtime"],
            "executor": self.config["executor"], "credential_env": [],
            "limits": self.config["limits"], "confinement": {}, "request_digest": "a" * 64,
        }
        request_path = task_dir / "request.json"
        request_path.write_text(json.dumps(request))
        with self.assertRaisesRegex(RuntimeFailure, "browser reset state must be an object"):
            run_lifecycle(request_path, task_dir / "result.json", source=Source())
        self.assertIsNotNone(client.process.returncode)

    def test_echo_only_activation_is_rejected_without_trusted_runtime_trace(self) -> None:
        def echo_only(request_path: Path, result_path: Path) -> None:
            request = json.loads(request_path.read_text())
            result_path.write_text(json.dumps({
                "schema_version": "0.4.0", "task_id": TASK_ID,
                "request_digest": request["request_digest"],
                "reset": {
                    "start_url": UPSTREAM_START_URL,
                    "initial_state": {"date": None},
                    "source_manifest": {
                        "git_blob_sha1": request["source_identity"]["manifest_blob_sha1"],
                        "content_sha256": "0" * 64,
                        "online4_row_sha256": "0" * 64,
                        "verified_from_installed_bytes": False,
                    },
                },
                "steps": [{"action": {"kind": "click"}, "outcome": {"status": "ok"},
                           "browser_state": {"date": "03/21/2025"}}],
                "final_state": {"date": "03/21/2025"}, "artifacts": [],
                "verifier": {
                    "initial": {
                        "passed": False, "verifier_id": request["verifier"]["id"],
                        "verifier_sha256": request["verifier"]["sha256"],
                        "upstream_commit": request["source_identity"]["upstream_commit"],
                        "manifest_blob_sha1": request["source_identity"]["manifest_blob_sha1"],
                        "page_url": request["wacz_start_url"], "state_sha256": "0" * 64,
                    },
                    "final": {
                        "passed": True, "verifier_id": request["verifier"]["id"],
                        "verifier_sha256": request["verifier"]["sha256"],
                        "upstream_commit": request["source_identity"]["upstream_commit"],
                        "manifest_blob_sha1": request["source_identity"]["manifest_blob_sha1"],
                        "page_url": request["wacz_start_url"], "state_sha256": "0" * 64,
                    },
                },
                "activation": {
                    "path": request["treatment_relative_path"],
                    "sha256": request["treatment_sha256"],
                    "runtime_trace_path": "missing.jsonl", "runtime_trace_sha256": "0" * 64,
                    "treatment_event_id": "echo", "model_request_event_ids": ["echo"],
                },
                "cleanup": {"completed": True},
            }) + "\n")

        with mock.patch(
            "opti_eval.adapters.warc_online4.run_lifecycle", side_effect=echo_only
        ), self.assertRaisesRegex(WarcOnline4Error, "trusted lifecycle trace"):
            self._run()

    def test_runtime_artifact_symlink_cannot_escape_task_output(self) -> None:
        from opti_eval.warc_online4_runtime import run_lifecycle as real_lifecycle

        outside = self.root / "outside.bin"
        outside.write_bytes(b"outside")

        def symlink_artifact(request_path: Path, result_path: Path) -> None:
            real_lifecycle(request_path, result_path)
            shot = result_path.parent / "shot.bin"
            shot.unlink()
            shot.symlink_to(outside)

        with mock.patch(
            "opti_eval.adapters.warc_online4.run_lifecycle",
            side_effect=symlink_artifact,
        ), self.assertRaisesRegex(WarcOnline4Error, "escapes its trusted root"):
            self._run()

    def test_production_preflight_missing_asset_executes_no_lifecycle(self) -> None:
        self.config["wacz"]["path"] = str(self.root / "missing.wacz")
        self.config["mode"] = "production"
        self._write()
        with mock.patch("opti_eval.adapters.warc_online4.run_lifecycle") as lifecycle:
            with self.assertRaisesRegex(WarcOnline4Error, "wacz.path is not readable"):
                load_and_preflight_config(self.config_path)
            lifecycle.assert_not_called()

    def test_pinned_upstream_handler_and_browsergym_constructor_contract(self) -> None:
        upstream = self.root / "upstream"
        utils_public = upstream / "utils" / "__init__.py"
        utils = upstream / "utils" / "utils.py"
        replay = upstream / "webreplay-standalone" / "dist" / "index.js"
        manifest = upstream / "environments" / "benchmark.json"
        utils.parent.mkdir(parents=True)
        replay.parent.mkdir(parents=True)
        manifest.parent.mkdir(parents=True)
        utils_public.write_text("# fixture package\n")
        utils.write_text("# fixture module\n")
        replay.write_text("// fixture replay\n")
        pinned_task_config = {
            "task_id": "online.4",
            "timestamp": "2025-02-18T00:00:00Z",
            "env": {
                "data_path": "pinned/default.wacz",
                "start_url": "https://pinned.invalid/default",
                "other": "preserved",
            },
        }
        manifest.write_text(json.dumps([pinned_task_config], separators=(",", ":")))
        browsergym_file = self.root / "browser_env.py"
        gymnasium_file = self.root / "gymnasium.py"
        playwright_file = self.root / "pw/playwright/sync_api/__init__.py"
        playwright_driver = self.root / "pw/playwright/driver/package/cli.js"
        playwright_file.parent.mkdir(parents=True)
        playwright_driver.parent.mkdir(parents=True)
        for path in (browsergym_file, gymnasium_file, playwright_file, playwright_driver):
            path.write_text("# fixture module\n")
        calls: list[tuple] = []

        class RecordingHandler(type):
            def __call__(cls, *args, **kwargs):
                calls.append(("handler_call", args, kwargs))
                return super().__call__(*args, **kwargs)

        class Handler(metaclass=RecordingHandler):
            bad_config = False

            def __init__(
                self,
                task_id: str,
                wacz_file: str | None = None,
                start_url: str | None = None,
                debugging_port: int = 9222,
                browser_args: dict | None = None,
                viewport_width: int | None = None,
                viewport_height: int | None = None,
            ):
                self.task_config = copy.deepcopy(pinned_task_config)
                if self.bad_config:
                    self.task_config["env"] = {}

            def setup_webreplay_server(self, run_headless: bool = True):
                calls.append(("setup", run_headless, copy.deepcopy(self.task_config)))

            def cleanup(self):
                calls.append(("cleanup",))

        class Env:
            def close(self):
                pass

        browsergym = types.ModuleType("browsergym.subtaskbench")
        browsergym.__file__ = str(browsergym_file)
        gymnasium = types.ModuleType("gymnasium")
        gymnasium.__file__ = str(gymnasium_file)
        gymnasium.make = mock.Mock(return_value=Env())
        gymnasium.spec = mock.Mock(
            return_value=types.SimpleNamespace(
                entry_point="fixture_browser_env:BrowserEnv"
            )
        )
        browser_environment = types.ModuleType("fixture_browser_env")
        browser_environment.__file__ = str(browsergym_file)
        playwright = types.ModuleType("playwright.sync_api")
        playwright.__file__ = str(playwright_file)
        Handler.__module__ = "orby.subtask_benchmark.utils.utils"
        warc = types.ModuleType("orby.subtask_benchmark.utils")
        warc.__file__ = str(utils_public)
        warc_impl = types.ModuleType("orby.subtask_benchmark.utils.utils")
        warc_impl.__file__ = str(utils)
        warc.WebReplayServerSessionHandler = Handler
        parents = {
            "browsergym": types.ModuleType("browsergym"),
            "playwright": types.ModuleType("playwright"),
            "orby": types.ModuleType("orby"),
            "orby.subtask_benchmark": types.ModuleType("orby.subtask_benchmark"),
        }
        parents["browsergym"].subtaskbench = browsergym
        parents["playwright"].sync_api = playwright
        parents["orby"].subtask_benchmark = parents["orby.subtask_benchmark"]
        parents["orby.subtask_benchmark"].utils = warc

        def identity(path: Path) -> dict:
            return {"path": str(path), "sha256": _digest(path)}

        request = {
            "wacz_path": str(self.wacz),
            "wacz_start_url": self.config["wacz"]["start_url"],
            "source_identity": {
                "manifest_blob_sha1": _git_blob_sha1(manifest.read_bytes())
            },
            "runtime": {
                "browsergym": identity(browsergym_file),
                "gymnasium": identity(gymnasium_file),
                "playwright": identity(playwright_file),
                "playwright_driver": identity(playwright_driver),
                "warc_bench": identity(utils),
                "replay": identity(replay),
                "node": {"path": str(self.root / "node")},
                "cdp_port": 4222,
            },
        }
        modules = {
            **parents,
            "browsergym.subtaskbench": browsergym,
            "gymnasium": gymnasium,
            "fixture_browser_env": browser_environment,
            "playwright.sync_api": playwright,
            "orby.subtask_benchmark.utils": warc,
            "orby.subtask_benchmark.utils.utils": warc_impl,
        }
        with mock.patch.dict(sys.modules, modules), mock.patch(
            "opti_eval.warc_online4_runtime.shutil.which",
            return_value=str(self.root / "node"),
        ):
            handler, _, manifest_evidence = _make_upstream_environment(request)
        self.assertEqual(
            gymnasium.make.call_args,
            mock.call(
                "browsergym/subtaskbench.online.4",
                cdp_port=4222,
                connect_via_cdp=True,
            ),
        )
        self.assertEqual(calls[0], (
            "handler_call",
            (),
            {
                "task_id": "online.4",
                "wacz_file": str(self.wacz),
                "start_url": UPSTREAM_START_URL,
                "debugging_port": 4222,
            },
        ))
        self.assertEqual(calls[1][0:2], ("setup", True))
        adapted = calls[1][2]
        self.assertEqual(adapted["task_id"], "online.4")
        self.assertEqual(adapted["timestamp"], "2025-02-18T00:00:00Z")
        self.assertEqual(adapted["env"], {
            "data_path": str(self.wacz),
            "start_url": UPSTREAM_START_URL,
            "other": "preserved",
        })
        self.assertEqual(
            manifest_evidence["git_blob_sha1"],
            request["source_identity"]["manifest_blob_sha1"],
        )
        self.assertTrue(manifest_evidence["verified_from_installed_bytes"])
        handler.cleanup()

        Handler.bad_config = True
        with mock.patch.dict(sys.modules, modules), mock.patch(
            "opti_eval.warc_online4_runtime.shutil.which",
            return_value=str(self.root / "node"),
        ), self.assertRaisesRegex(RuntimeFailure, "does not equal the pinned online.4"):
            _make_upstream_environment(request)
        Handler.bad_config = False

        pinned_blob = request["source_identity"]["manifest_blob_sha1"]
        request["source_identity"]["manifest_blob_sha1"] = "0" * 40
        with mock.patch.dict(sys.modules, modules), mock.patch(
            "opti_eval.warc_online4_runtime.shutil.which",
            return_value=str(self.root / "node"),
        ), self.assertRaisesRegex(RuntimeFailure, "Git blob does not match"):
            _make_upstream_environment(request)
        request["source_identity"]["manifest_blob_sha1"] = pinned_blob

        (self.root / "decoy.py").write_text("# decoy\n")
        request["runtime"]["playwright_driver"] = identity(self.root / "decoy.py")
        with mock.patch.dict(sys.modules, modules), mock.patch(
            "opti_eval.warc_online4_runtime.shutil.which",
            return_value=str(self.root / "node"),
        ), self.assertRaisesRegex(RuntimeFailure, "loaded Playwright driver"):
            _make_upstream_environment(request)
        request["runtime"]["playwright_driver"] = identity(playwright_driver)

        decoy_environment = types.ModuleType("decoy_browser_env")
        decoy_environment.__file__ = str(self.root / "decoy.py")
        modules["decoy_browser_env"] = decoy_environment
        gymnasium.spec.return_value = types.SimpleNamespace(
            entry_point="decoy_browser_env:BrowserEnv"
        )
        with mock.patch.dict(sys.modules, modules), mock.patch(
            "opti_eval.warc_online4_runtime.shutil.which",
            return_value=str(self.root / "node"),
        ), self.assertRaisesRegex(
            RuntimeFailure, "resolved BrowserGym online.4 environment origin/digest"
        ):
            _make_upstream_environment(request)

    def _worker_client(self, program: str, seconds: float = 0.25) -> _WorkerClient:
        process = subprocess.Popen(
            [sys.executable, "-u", "-c", program],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True,
        )
        return _WorkerClient(process, time.monotonic() + seconds)

    def test_upstream_stdout_cannot_corrupt_real_worker_client_ipc(self) -> None:
        task_dir = self.root / "worker-logging"
        task_dir.mkdir()
        request = {
            "wacz_start_url": UPSTREAM_START_URL,
            "verifier": {
                "id": "fixture-native-js", "path": str(self.verifier),
                "sha256": _digest(self.verifier),
            },
            "source_identity": {
                "upstream_commit": self.config["source"]["upstream_commit"],
                "manifest_blob_sha1": self.config["source"]["manifest_blob_sha1"],
            },
            "runtime": {"browser": {"path": str(Path(sys.executable).resolve())}},
        }
        request_path = task_dir / "request.json"
        request_path.write_text(json.dumps(request))
        program = textwrap.dedent(
            f"""
            import sys
            from pathlib import Path
            from types import SimpleNamespace
            from opti_eval import warc_online4_runtime as runtime

            START = {UPSTREAM_START_URL!r}
            BROWSER = {str(Path(sys.executable).resolve())!r}

            class Page:
                def __init__(self):
                    self.url = START
                    self.passed = False
                    self.context = SimpleNamespace(browser=SimpleNamespace(
                        browser_type=SimpleNamespace(executable_path=BROWSER)))
                def evaluate(self, script):
                    print('page evaluate diagnostic')
                    return self.passed

            class Env:
                def __init__(self):
                    self.page = Page()
                    self.unwrapped = self
                    self._elapsed_steps = 0
                def reset(self):
                    print('reset diagnostic')
                    return {{'url': START, 'calendarfocusdate': None}}, {{}}
                def step(self, action):
                    print('step diagnostic')
                    self._elapsed_steps += 1
                    self.page.passed = True
                    return ({{'url': START, 'calendarfocusdate': '03/21/2025'}},
                            1.0, False, False, {{}})
                def close(self):
                    print('close diagnostic')

            class Handler:
                def setup_webreplay_server(self):
                    print('handler setup diagnostic')
                def cleanup(self):
                    print('handler cleanup diagnostic', file=sys.stderr)

            def fake_environment(request):
                handler = Handler()
                handler.setup_webreplay_server()
                return handler, Env(), {{
                    'git_blob_sha1': request['source_identity']['manifest_blob_sha1'],
                    'content_sha256': '1' * 64,
                    'online4_row_sha256': '2' * 64,
                    'verified_from_installed_bytes': True,
                }}

            runtime._make_upstream_environment = fake_environment
            raise SystemExit(runtime._source_worker(Path(sys.argv[1])))
            """
        )
        process = subprocess.Popen(
            [sys.executable, "-u", "-c", program, str(request_path)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True,
        )
        client = _WorkerClient(process, time.monotonic() + 3.0)
        try:
            reset = client.call("reset")
            self.assertEqual(reset["start_url"], UPSTREAM_START_URL)
            self.assertFalse(client.call("verify")["verifier"]["passed"])
            client.call("step", action="click('March 21 2025')")
            self.assertTrue(client.call("verify")["verifier"]["passed"])
            self.assertTrue(client.call("close")["completed"])
        finally:
            client.reap()
        self.assertIsNotNone(process.returncode)

        substituted_program = program.replace(
            "self.page.passed = True",
            "self.page = Page()\n        self.page.passed = True",
        )
        substituted_process = subprocess.Popen(
            [sys.executable, "-u", "-c", substituted_program, str(request_path)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True,
        )
        substituted = _WorkerClient(
            substituted_process, time.monotonic() + 3.0
        )
        try:
            substituted.call("reset")
            self.assertFalse(substituted.call("verify")["verifier"]["passed"])
            with self.assertRaisesRegex(RuntimeFailure, "substituted the reset-time"):
                substituted.call("step", action="click('March 21 2025')")
        finally:
            substituted.reap()
        self.assertIsNotNone(substituted_process.returncode)

    def test_model_transport_timeout_is_clipped_to_remaining_lifecycle(self) -> None:
        task_dir = self.root / "late-model-call"
        task_dir.mkdir()
        request = {
            "mode": "local_fixture", "task_id": TASK_ID, "goal": self.task["goal"],
            "wacz_start_url": UPSTREAM_START_URL,
            "source_identity": self.config["source"],
            "verifier": {
                "id": self.config["verifier"]["id"], "path": str(self.verifier),
                "sha256": _digest(self.verifier),
            },
            "treatment_path": str(self.treatment),
            "treatment_relative_path": "harness/components/policy/quality.txt",
            "treatment_sha256": _digest(self.treatment), "runtime": self.config["runtime"],
            "executor": self.config["executor"], "credential_env": [],
            "limits": {"timeout_seconds": 30, "deadline_seconds": 10, "action_budget": 3},
            "confinement": {}, "request_digest": "a" * 64,
        }
        request_path = task_dir / "request.json"
        request_path.write_text(json.dumps(request))
        clock_values = iter(
            [100.0, 101.0, 102.0, 108.5, 109.0, 109.1, 109.2, 109.3, 109.4, 109.5, 109.6]
        )
        observed_timeouts: list[float] = []

        def transport(_request, _body, timeout_seconds):
            observed_timeouts.append(timeout_seconds)
            if len(observed_timeouts) == 1:
                return {"content": [{
                    "type": "tool_use", "name": "browser_action",
                    "input": {"action": "click('March 21 2025')"},
                }]}
            return {"content": [{"type": "tool_use", "name": "finish", "input": {}}]}

        run_lifecycle(
            request_path, task_dir / "result.json",
            model_transport=transport, monotonic=lambda: next(clock_values),
        )
        self.assertEqual(len(observed_timeouts), 2)
        self.assertAlmostEqual(observed_timeouts[0], 1.0)
        self.assertAlmostEqual(observed_timeouts[1], 0.6)

    def test_model_transport_deadline_bounds_complete_response_read(self) -> None:
        class BlockingResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                time.sleep(60)
                return b"{}"

        request = {
            "credential_env": ["OPTI_TEST_WARC_MODEL_KEY"],
            "executor": {"route": "https://invalid.local/messages"},
        }
        previous_handler = signal.getsignal(signal.SIGALRM)
        previous_timer = signal.getitimer(signal.ITIMER_REAL)
        started = time.monotonic()
        with (
            mock.patch.dict(
                os.environ, {"OPTI_TEST_WARC_MODEL_KEY": "fixture-secret"}
            ),
            mock.patch(
                "opti_eval.warc_online4_runtime.urllib.request.urlopen",
                return_value=BlockingResponse(),
            ),
            self.assertRaisesRegex(RuntimeFailure, "absolute deadline"),
        ):
            _http_model_transport(request, b"{}", 0.05)
        self.assertLess(time.monotonic() - started, 0.5)
        self.assertIs(signal.getsignal(signal.SIGALRM), previous_handler)
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL), previous_timer)

    def test_hung_reset_is_deadline_bounded_and_reaped(self) -> None:
        client = self._worker_client(
            "import sys,time; sys.stdin.readline(); sys.stdout.write('{'); "
            "sys.stdout.flush(); time.sleep(60)"
        )
        started = time.monotonic()
        with self.assertRaisesRegex(RuntimeFailure, "exceeded lifecycle deadline"):
            client.call("reset")
        client.reap()
        self.assertLess(time.monotonic() - started, 2)
        self.assertIsNotNone(client.process.returncode)

    def test_hung_close_and_terminate_resistant_worker_is_killed_and_reaped(self) -> None:
        program = (
            "import json,signal,sys,time\n"
            "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
            "sys.stdin.readline(); print(json.dumps({'ok':True}),flush=True)\n"
            "sys.stdin.readline(); time.sleep(60)\n"
        )
        client = self._worker_client(program, 0.35)
        self.assertTrue(client.call("reset")["ok"])
        with self.assertRaisesRegex(RuntimeFailure, "exceeded lifecycle deadline"):
            client.call("close")
        client.reap()
        self.assertIsNotNone(client.process.returncode)
        self.assertLess(client.process.returncode, 0)


if __name__ == "__main__":
    unittest.main()
