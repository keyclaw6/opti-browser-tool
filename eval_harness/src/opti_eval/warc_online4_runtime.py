"""Trusted, task-specific runtime for WARC-Bench ``online.4``."""
from __future__ import annotations

import argparse
import base64
import copy
from contextlib import contextmanager
import hashlib
import importlib
import json
import os
import re
import selectors
import signal
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable


MODEL_ROUTE = "https://opencode.ai/zen/go/v1/messages"
MODEL_NAME = "minimax-m3"
UPSTREAM_START_URL = (
    "https://www.alaskaair.com/search/?A=1&C=0&L=0&O=JFK&D=SFO&"
    "OD=2025-02-18&DD=2025-02-18&RT=true&errorRedirect=true"
)
ONLINE4_MATCHER = (
    "document.querySelector('auro-datepicker')."
    'getAttribute("calendarfocusdate")=="03/21/2025"'
)
ACTION_TOOLS = [
    {
        "name": "browser_action",
        "description": "Apply one BrowserGym action to the current WARC page.",
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["action"],
            "properties": {"action": {"type": "string"}},
        },
    },
    {
        "name": "finish",
        "description": "Finish after the requested browser state has been reached.",
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {},
        },
    },
]
_ACTION = re.compile(
    r"^(?:click|type|scroll|hover|drag_and_release|key_press|wait)\([^\r\n;]*\)$"
)


class RuntimeFailure(RuntimeError):
    pass


class _ModelDeadline(TimeoutError):
    pass


@contextmanager
def _absolute_model_timeout(timeout_seconds: float):
    """Bound one synchronous model call, including the complete response read."""
    if timeout_seconds <= 0:
        raise RuntimeFailure("pinned OpenCode Go messages deadline exhausted")
    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)
    started = time.monotonic()

    def expire(_signum: int, _frame: object) -> None:
        raise _ModelDeadline("absolute model request deadline exhausted")

    try:
        signal.signal(signal.SIGALRM, expire)
    except (ValueError, OSError) as exc:
        raise RuntimeFailure(
            "absolute model deadline requires the main single-host runtime thread"
        ) from exc
    try:
        signal.setitimer(signal.ITIMER_REAL, timeout_seconds)
    except (ValueError, OSError) as exc:
        signal.signal(signal.SIGALRM, previous_handler)
        raise RuntimeFailure("could not arm the absolute model deadline") from exc
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        previous_delay, previous_interval = previous_timer
        if previous_delay > 0:
            previous_delay = max(
                1e-6, previous_delay - (time.monotonic() - started)
            )
        signal.setitimer(signal.ITIMER_REAL, previous_delay, previous_interval)


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def action_tool_schema_digest() -> str:
    return _sha(_canonical(ACTION_TOOLS))


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise RuntimeFailure(f"{label} did not produce valid JSON: {exc}") from exc
    if type(value) is not dict:
        raise RuntimeFailure(f"{label} result must be an object")
    return value


def _state(value: object, label: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise RuntimeFailure(f"{label} state must be an object")
    kept: dict[str, Any] = {}
    for key in (
        "url", "goal", "chat_messages", "axtree_txt", "pruned_html",
        "last_action_error", "date", "calendarfocusdate",
    ):
        if key in value:
            item = value.get(key)
            if item is None or type(item) in {str, int, float, bool, list, dict}:
                kept[key] = item
    return kept or dict(value)


def _model_request(
    request: dict[str, Any], treatment: bytes, treatment_sha256: str,
    state: dict[str, Any],
) -> bytes:
    encoded = base64.b64encode(treatment).decode("ascii")
    policy = (
        "You are the fixed browser executor for WARC-Bench online.4. Apply the "
        "following exact materialized candidate policy bytes when choosing the next action.\n"
        f"OPTI_CANDIDATE_SHA256={treatment_sha256}\n"
        f"OPTI_CANDIDATE_BASE64_BEGIN\n{encoded}\nOPTI_CANDIDATE_BASE64_END"
    )
    settings = request["executor"]["settings"]
    body = {
        "model": request["executor"]["model"],
        "max_tokens": settings["max_tokens"],
        "temperature": settings["temperature"],
        "system": policy,
        "messages": [{
            "role": "user",
            "content": _canonical({"goal": request["goal"], "state": state}).decode(),
        }],
        "tools": ACTION_TOOLS,
        "tool_choice": {"type": "any"},
    }
    raw = _canonical(body)
    _verify_applied_request(raw, treatment, treatment_sha256)
    return raw


def _verify_applied_request(raw: bytes, treatment: bytes, treatment_sha256: str) -> None:
    try:
        body = json.loads(raw)
    except (UnicodeError, ValueError) as exc:
        raise RuntimeFailure("applied model request is not valid JSON") from exc
    marker = base64.b64encode(treatment).decode("ascii")
    system = body.get("system") if type(body) is dict else None
    if (
        type(system) is not str
        or f"OPTI_CANDIDATE_SHA256={treatment_sha256}" not in system
        or f"OPTI_CANDIDATE_BASE64_BEGIN\n{marker}\nOPTI_CANDIDATE_BASE64_END" not in system
        or body.get("tools") != ACTION_TOOLS
    ):
        raise RuntimeFailure("model request dropped or substituted the exact treatment bytes")


def _verifier_evidence(
    passed: object, *, page_url: object, state: dict[str, Any], request: dict[str, Any]
) -> dict[str, Any]:
    if type(passed) is not bool:
        raise RuntimeFailure("live online.4 verifier did not return a boolean")
    if type(page_url) is not str:
        raise RuntimeFailure("live online.4 verifier page URL is unavailable")
    verifier = request["verifier"]
    return {
        "passed": passed,
        "verifier_id": verifier["id"],
        "verifier_sha256": verifier["sha256"],
        "upstream_commit": request["source_identity"]["upstream_commit"],
        "manifest_blob_sha1": request["source_identity"]["manifest_blob_sha1"],
        "page_url": page_url,
        "state_sha256": _sha(_canonical(state)),
    }


class _LocalSource:
    """Deterministic substitute at the live replay/browser boundary."""

    def __init__(self, work: Path, treatment: bytes, request: dict[str, Any]) -> None:
        self.work = work
        self.mode = treatment.decode("utf-8", errors="replace").strip()
        self.request = request
        self.closed = False
        self.live_state: object = {"date": None, "calendarfocusdate": None}

    def start(self) -> str:
        return self.request["wacz_start_url"]

    def reset(self) -> dict[str, Any]:
        if self.mode == "malformed-reset":
            self.live_state = "not-an-object"
            return self.live_state  # type: ignore[return-value]
        if self.mode == "bad-reset":
            self.live_state = {"date": "03/21/2025", "calendarfocusdate": "03/21/2025"}
        else:
            self.live_state = {"date": None, "calendarfocusdate": None}
        return dict(self.live_state)

    def source_manifest(self) -> dict[str, Any]:
        source = self.request["source_identity"]
        return {
            "git_blob_sha1": source["manifest_blob_sha1"],
            "content_sha256": _sha(_canonical(source)),
            "online4_row_sha256": _sha(_canonical({"task_id": "online.4"})),
            "verified_from_installed_bytes": False,
        }

    def verify(self) -> dict[str, Any]:
        if self.mode == "bad-verifier":
            raise RuntimeFailure("local fixture live verifier failed")
        state = _state(self.live_state, "local live page")
        passed = state.get("calendarfocusdate") == "03/21/2025"
        return _verifier_evidence(
            passed, page_url=self.request["wacz_start_url"], state=state,
            request=self.request,
        )

    def step(self, action: str) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, str]]]:
        self.live_state = {"date": "03/21/2025", "calendarfocusdate": "03/21/2025"}
        final: object = self.live_state
        if self.mode == "bad-final":
            final = "not-an-object"
        shot = self.work / "shot.bin"
        shot.write_bytes(b"local fixture screenshot")
        artifacts = [{
            "path": "shot.bin", "kind": "screenshot",
            "media_type": "application/octet-stream",
        }]
        if self.mode == "bad-artifact":
            artifacts[0]["path"] = "missing.bin"
        return {"reward": 1.0, "terminated": False, "truncated": False}, final, artifacts  # type: ignore[return-value]

    def close(self) -> None:
        self.closed = True
        if self.mode == "bad-cleanup":
            raise RuntimeFailure("local fixture cleanup failed")


class _WorkerClient:
    """Deadline-bounded JSON-lines transport for the one source worker."""

    def __init__(self, process: subprocess.Popen[str], deadline: float) -> None:
        self.process = process
        self.deadline = deadline
        self._output = b""

    def _remaining(self) -> float:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeFailure("BrowserGym source worker deadline exhausted")
        return remaining

    def call(self, operation: str, **payload: object) -> dict[str, Any]:
        if self.process.stdin is None or self.process.stdout is None:
            raise RuntimeFailure("BrowserGym source worker pipes are unavailable")
        try:
            self.process.stdin.write(
                json.dumps({"operation": operation, **payload}, sort_keys=True) + "\n"
            )
            self.process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise RuntimeFailure("BrowserGym source worker input closed") from exc
        while b"\n" not in self._output:
            with selectors.DefaultSelector() as selector:
                selector.register(self.process.stdout, selectors.EVENT_READ)
                if not selector.select(self._remaining()):
                    raise RuntimeFailure(
                        f"BrowserGym source worker {operation} exceeded lifecycle deadline"
                    )
            chunk = os.read(self.process.stdout.fileno(), 65536)
            if not chunk:
                detail = ""
                if self.process.stderr is not None and self.process.poll() is not None:
                    detail = self.process.stderr.read().strip()
                raise RuntimeFailure(
                    f"BrowserGym source worker exited without a result: {detail}"
                )
            self._output += chunk
        line, self._output = self._output.split(b"\n", 1)
        try:
            row = json.loads(line.decode("utf-8"))
        except (UnicodeError, ValueError) as exc:
            raise RuntimeFailure("BrowserGym source worker returned malformed JSON") from exc
        if type(row) is not dict:
            raise RuntimeFailure("BrowserGym source worker result must be an object")
        if row.get("error"):
            raise RuntimeFailure(f"BrowserGym source worker failed: {row['error']}")
        return row

    def reap(self) -> None:
        for pipe in (self.process.stdin, self.process.stdout, self.process.stderr):
            if pipe is not None:
                try:
                    pipe.close()
                except OSError:
                    pass
        if self.process.poll() is not None:
            self.process.wait()
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=min(1.0, max(0.05, self.deadline - time.monotonic())))
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=1.0)


class _SandboxedBrowserGymSource:
    def __init__(
        self, request: dict[str, Any], request_path: Path, work: Path, deadline: float
    ) -> None:
        launcher = Path(__file__).resolve()
        python = request["runtime"]["python"]["path"]
        command = [python, str(launcher), "--source-worker", "--request", str(request_path)]
        sandbox = request["runtime"]["sandbox"]["path"]
        argv = [
            sandbox, "--die-with-parent", "--new-session", "--unshare-all",
            "--ro-bind", "/", "/", "--proc", "/proc", "--dev", "/dev",
            "--tmpfs", "/tmp", "--bind", str(work), str(work), "--chdir", str(work),
            "--", *command,
        ]
        env = {
            "LC_ALL": "C", "LANG": "C", "HOME": str(work),
            "PATH": str(Path(request["runtime"]["node"]["path"]).parent),
        }
        process = subprocess.Popen(
            argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, env=env,
        )
        self.client = _WorkerClient(process, deadline)

    def start(self) -> str:
        row = self.client.call("reset")
        self._reset_row = row
        url = row.get("start_url")
        if url != UPSTREAM_START_URL or url != self._reset_row.get("configured_start_url"):
            raise RuntimeFailure(
                "BrowserGym reset page URL does not match the pinned online.4 start URL"
            )
        self._source_manifest = row.get("source_manifest")
        return url

    def reset(self) -> dict[str, Any]:
        return self._reset_row.get("state")

    def source_manifest(self) -> dict[str, Any]:
        if type(self._source_manifest) is not dict:
            raise RuntimeFailure("BrowserGym worker omitted pinned source-manifest evidence")
        return self._source_manifest

    def verify(self) -> dict[str, Any]:
        return self.client.call("verify")["verifier"]

    def step(self, action: str) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, str]]]:
        row = self.client.call("step", action=action)
        return row["outcome"], row["state"], row["artifacts"]

    def close(self) -> None:
        try:
            if self.client.process.poll() is None:
                self.client.call("close")
        finally:
            self.client.reap()


def _http_model_transport(
    request: dict[str, Any], body: bytes, timeout_seconds: float
) -> dict[str, Any]:
    credential_env = request["credential_env"]
    if len(credential_env) != 1 or not os.environ.get(credential_env[0]):
        raise RuntimeFailure("pinned OpenCode Go credential is unavailable")
    call = urllib.request.Request(
        request["executor"]["route"], data=body, method="POST",
        headers={
            "content-type": "application/json", "anthropic-version": "2023-06-01",
            "x-api-key": os.environ[credential_env[0]],
        },
    )
    try:
        with _absolute_model_timeout(timeout_seconds):
            with urllib.request.urlopen(call, timeout=timeout_seconds) as response:
                raw = response.read()
    except _ModelDeadline as exc:
        raise RuntimeFailure(
            "pinned OpenCode Go messages request exceeded its absolute deadline"
        ) from exc
    except (OSError, urllib.error.URLError) as exc:
        raise RuntimeFailure(f"pinned OpenCode Go messages request failed: {exc}") from exc
    try:
        value = json.loads(raw)
    except (UnicodeError, ValueError) as exc:
        raise RuntimeFailure("pinned OpenCode Go response is not JSON") from exc
    if type(value) is not dict:
        raise RuntimeFailure("pinned OpenCode Go response must be an object")
    return value


def _local_model_transport(
    request: dict[str, Any], body: bytes, timeout_seconds: float
) -> dict[str, Any]:
    calls = request.get("_local_model_calls", 0)
    request["_local_model_calls"] = calls + 1
    if calls or Path(request["treatment_path"]).read_text().strip() == "bad-steps":
        return {"content": [{"type": "tool_use", "name": "finish", "input": {}}]}
    return {"content": [{
        "type": "tool_use", "name": "browser_action",
        "input": {"action": "click('March 21 2025')"},
    }]}


def _parse_action(response: dict[str, Any]) -> tuple[bool, str | None]:
    content = response.get("content")
    if type(content) is not list or len(content) != 1 or type(content[0]) is not dict:
        raise RuntimeFailure("executor response must contain exactly one tool use")
    tool = content[0]
    if tool.get("type") != "tool_use" or type(tool.get("input")) is not dict:
        raise RuntimeFailure("executor response must be a tool use")
    if tool.get("name") == "finish" and tool["input"] == {}:
        return True, None
    action = tool["input"].get("action") if tool.get("name") == "browser_action" else None
    if type(action) is not str or not _ACTION.fullmatch(action):
        raise RuntimeFailure("executor returned an unsupported BrowserGym action")
    return False, action


def run_lifecycle(
    request_path: Path,
    result_path: Path,
    *,
    source: Any | None = None,
    model_transport: Callable[[dict[str, Any], bytes, float], dict[str, Any]] | None = None,
    monotonic: Callable[[], float] = time.monotonic,
) -> None:
    request = _read_json(request_path, "WARC lifecycle request")
    deadline = monotonic() + request["limits"]["deadline_seconds"]

    def remaining_time() -> float:
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise RuntimeFailure("WARC online.4 lifecycle deadline exhausted")
        return remaining

    def require_time() -> None:
        remaining_time()

    work = result_path.parent.resolve()
    treatment = Path(request["treatment_path"])
    raw = treatment.read_bytes()
    actual_sha = _sha(raw)
    if actual_sha != request["treatment_sha256"]:
        raise RuntimeFailure("trusted lifecycle loaded treatment bytes with the wrong digest")
    if request["mode"] == "production":
        confinement = request["confinement"]
        optimizer_uid = confinement["optimizer_uid"]
        inbox = Path(confinement["static_inbox"])
        if (
            os.geteuid() == optimizer_uid or inbox.is_symlink() or not inbox.is_dir()
            or inbox.stat().st_uid != optimizer_uid
        ):
            raise RuntimeFailure("production UID/static inbox confinement changed after preflight")
    source = source or (
        _LocalSource(work, raw, request)
        if request["mode"] == "local_fixture"
        else _SandboxedBrowserGymSource(request, request_path, work, deadline)
    )
    transport = model_transport or (
        _local_model_transport if request["mode"] == "local_fixture"
        else _http_model_transport
    )
    events: list[dict[str, Any]] = []

    def record(event: str, **payload: object) -> str:
        event_id = f"runtime-{len(events) + 1}"
        events.append({"event_id": event_id, "event": event, **payload})
        return event_id

    treatment_event = record(
        "treatment_loaded", path=request["treatment_relative_path"],
        sha256=actual_sha, byte_count=len(raw),
    )
    steps: list[dict[str, Any]] = []
    artifacts: list[dict[str, str]] = []
    request_events: list[str] = []
    cleanup_error: Exception | None = None
    try:
        require_time()
        start_url = source.start()
        record("replay_started", start_url=start_url)
        initial_state = _state(source.reset(), "browser reset")
        source_manifest = source.source_manifest()
        if type(source_manifest) is not dict:
            raise RuntimeFailure("source manifest evidence must be an object")
        initial_verifier = source.verify()
        if initial_verifier.get("passed") is not False:
            raise RuntimeFailure("reset live page must independently fail the native verifier")
        require_time()
        record(
            "browser_reset", state_sha256=_sha(_canonical(initial_state)),
            verifier_passed=False,
            source_manifest_git_blob_sha1=source_manifest.get("git_blob_sha1"),
        )
        state = initial_state
        completed = False
        for action_index in range(request["limits"]["action_budget"]):
            require_time()
            body = _model_request(request, raw, actual_sha, state)
            request_file = work / f"model-request-{action_index}.json"
            request_file.write_bytes(body + b"\n")
            applied_digest = _sha(body)
            event_id = record(
                "model_request_applied", action_index=action_index,
                treatment_sha256=actual_sha, request_path=request_file.name,
                applied_request_sha256=applied_digest,
            )
            request_events.append(event_id)
            request_timeout = min(
                float(request["limits"]["timeout_seconds"]), remaining_time()
            )
            done, action = _parse_action(transport(request, body, request_timeout))
            require_time()
            artifacts.append({
                "path": request_file.name, "kind": "executor_request",
                "media_type": "application/json",
            })
            if done:
                completed = True
                break
            outcome, state_value, step_artifacts = source.step(action)
            require_time()
            state = _state(state_value, "browser step")
            record(
                "browser_action_applied", action_index=action_index,
                applied_request_sha256=applied_digest,
            )
            steps.append({
                "action": {"browsergym": action}, "outcome": outcome,
                "browser_state": state,
            })
            artifacts.extend(step_artifacts)
        if not completed:
            raise RuntimeFailure("executor did not finish within action_budget")
        if not steps:
            raise RuntimeFailure("executor completed without a browser action")
        final_state: object = state
        final_verifier = source.verify()
        require_time()
        record(
            "native_verifier_evaluated", passed=final_verifier.get("passed"),
            state_sha256=final_verifier.get("state_sha256"),
        )
    finally:
        try:
            source.close()
            record("browser_closed")
            record("replay_stopped")
        except Exception as exc:
            cleanup_error = exc
    if cleanup_error is not None:
        raise RuntimeFailure(f"WARC lifecycle cleanup failed: {cleanup_error}")
    trace_path = work / "runtime-trace.jsonl"
    trace_path.write_text(
        "".join(json.dumps(event, sort_keys=True) + "\n" for event in events),
        encoding="utf-8",
    )
    _write_json(result_path, {
        "schema_version": "0.4.0", "task_id": request["task_id"],
        "request_digest": request["request_digest"],
        "reset": {
            "start_url": start_url, "initial_state": initial_state,
            "source_manifest": source_manifest,
        },
        "steps": steps, "final_state": final_state,
        "verifier": {"initial": initial_verifier, "final": final_verifier},
        "artifacts": artifacts,
        "activation": {
            "path": request["treatment_relative_path"], "sha256": actual_sha,
            "runtime_trace_path": "runtime-trace.jsonl",
            "runtime_trace_sha256": _sha(trace_path.read_bytes()),
            "treatment_event_id": treatment_event,
            "model_request_event_ids": request_events,
        },
        "cleanup": {"completed": True},
    })


def _worker_state(observation: object) -> dict[str, Any]:
    return _state(observation, "BrowserGym")


def _worker_artifacts(observation: object, index: int) -> list[dict[str, str]]:
    if type(observation) is not dict or "screenshot" not in observation:
        return []
    screenshot = observation["screenshot"]
    try:
        raw = screenshot.tobytes()
    except AttributeError:
        raw = bytes(screenshot) if isinstance(screenshot, (bytes, bytearray)) else b""
    if not raw:
        return []
    name = f"browser-screenshot-{index}.bin"
    Path(name).write_bytes(raw)
    return [{"path": name, "kind": "screenshot", "media_type": "application/octet-stream"}]


def _module_file(module: object, label: str) -> Path:
    value = getattr(module, "__file__", None)
    if type(value) is not str:
        raise RuntimeFailure(f"loaded {label} module has no file origin")
    return Path(value).resolve()


def _require_loaded_file(module: object, configured: dict[str, Any], label: str) -> None:
    origin = _module_file(module, label)
    expected = Path(configured["path"]).resolve()
    if origin != expected or _sha(origin.read_bytes()) != configured["sha256"]:
        raise RuntimeFailure(
            f"loaded {label} origin/digest does not match the preflighted runtime file"
        )


def _git_blob_sha1(raw: bytes) -> str:
    header = f"blob {len(raw)}\0".encode("ascii")
    return hashlib.sha1(header + raw).hexdigest()  # noqa: S324 - Git object identity


def _pinned_online4_config(
    handler_module: object, request: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest_path = (
        _module_file(handler_module, "WARC-Bench handler").parent.parent
        / "environments" / "benchmark.json"
    )
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise RuntimeFailure(
            "installed WARC-Bench handler lacks a regular environments/benchmark.json"
        )
    raw = manifest_path.read_bytes()
    blob_sha1 = _git_blob_sha1(raw)
    expected = request["source_identity"]["manifest_blob_sha1"]
    if blob_sha1 != expected:
        raise RuntimeFailure(
            "installed WARC-Bench benchmark.json Git blob does not match the pinned manifest"
        )
    try:
        parsed = json.loads(raw)
    except (UnicodeError, ValueError) as exc:
        raise RuntimeFailure("installed WARC-Bench benchmark.json is invalid JSON") from exc
    if type(parsed) is not list:
        raise RuntimeFailure("pinned WARC-Bench benchmark.json must be an array")
    matches = [
        row for row in parsed
        if type(row) is dict and row.get("task_id") == "online.4"
    ]
    if len(matches) != 1:
        raise RuntimeFailure(
            "pinned WARC-Bench benchmark.json must contain one online.4 row"
        )
    row = matches[0]
    return copy.deepcopy(row), {
        "git_blob_sha1": blob_sha1,
        "content_sha256": _sha(raw),
        "online4_row_sha256": _sha(_canonical(row)),
        "verified_from_installed_bytes": True,
    }


def _live_page(env: Any) -> Any:
    unwrapped = getattr(env, "unwrapped", env)
    page = getattr(unwrapped, "page", None)
    if page is None or not callable(getattr(page, "evaluate", None)):
        raise RuntimeFailure("BrowserGym online.4 did not expose its live Playwright Page")
    return page


def _live_verify(page: Any, request: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    script_path = Path(request["verifier"]["path"])
    script = script_path.read_text(encoding="utf-8").strip()
    if _sha(script_path.read_bytes()) != request["verifier"]["sha256"]:
        raise RuntimeFailure("live verifier file changed after preflight")
    if script != ONLINE4_MATCHER:
        raise RuntimeFailure("admitted verifier is not the pinned online.4 JavaScript matcher")
    passed = page.evaluate(f"() => ({script})")
    return _verifier_evidence(
        passed, page_url=page.url, state=state, request=request,
    )


def _make_upstream_environment(request: dict[str, Any]) -> tuple[Any, Any, dict[str, Any]]:
    """Construct exactly the pinned WARC handler + BrowserGym online.4 env."""
    import browsergym.subtaskbench  # noqa: F401 - registers pinned task
    import gymnasium
    import playwright.sync_api as playwright_sync_api
    import orby.subtask_benchmark.utils as warc_public_utils

    _require_loaded_file(gymnasium, request["runtime"]["gymnasium"], "Gymnasium")
    _require_loaded_file(
        playwright_sync_api, request["runtime"]["playwright"], "Playwright"
    )
    handler_class = warc_public_utils.WebReplayServerSessionHandler
    warc_handler_module = importlib.import_module(handler_class.__module__)
    _require_loaded_file(
        warc_handler_module, request["runtime"]["warc_bench"], "WARC-Bench handler"
    )
    task_config, manifest_evidence = _pinned_online4_config(
        warc_handler_module, request
    )
    try:
        environment_spec = gymnasium.spec("browsergym/subtaskbench.online.4")
    except Exception as exc:
        raise RuntimeFailure(
            "Gymnasium lacks registered browsergym/subtaskbench.online.4"
        ) from exc
    entry_point = environment_spec.entry_point
    if type(entry_point) is str and ":" in entry_point:
        environment_module_name = entry_point.split(":", 1)[0]
    elif callable(entry_point) and type(getattr(entry_point, "__module__", None)) is str:
        environment_module_name = entry_point.__module__
    else:
        raise RuntimeFailure("online.4 Gymnasium entry point is not import-addressable")
    environment_module = importlib.import_module(environment_module_name)
    _require_loaded_file(
        environment_module,
        request["runtime"]["browsergym"],
        "resolved BrowserGym online.4 environment",
    )
    playwright_driver = (
        _module_file(playwright_sync_api, "Playwright").parent.parent
        / "driver" / "package" / "cli.js"
    ).resolve()
    configured_driver = request["runtime"]["playwright_driver"]
    if (
        playwright_driver != Path(configured_driver["path"]).resolve()
        or _sha(playwright_driver.read_bytes()) != configured_driver["sha256"]
    ):
        raise RuntimeFailure(
            "loaded Playwright driver does not match the preflighted driver bytes"
        )
    replay = Path(request["runtime"]["replay"]["path"]).resolve()
    if replay.name != "index.js" or replay.parent.name != "dist":
        raise RuntimeFailure("preflighted WARC replay is not dist/index.js")
    node = shutil.which("node")
    if node is None or Path(node).resolve() != Path(request["runtime"]["node"]["path"]).resolve():
        raise RuntimeFailure("WARC handler node resolution does not match the preflighted node")

    cdp_port = request["runtime"]["cdp_port"]
    handler = handler_class(
        task_id="online.4",
        wacz_file=request["wacz_path"],
        start_url=request["wacz_start_url"],
        debugging_port=cdp_port,
    )
    try:
        original_task_config = getattr(handler, "task_config", None)
        if original_task_config != task_config:
            raise RuntimeFailure(
                "WARC handler task_config does not equal the pinned online.4 manifest row"
            )
        env_config = original_task_config.get("env")
        if (
            type(env_config) is not dict
            or "data_path" not in env_config
            or "start_url" not in env_config
        ):
            raise RuntimeFailure(
                "WARC handler online.4 task_config lacks env.data_path/start_url"
            )
        env_config["data_path"] = request["wacz_path"]
        env_config["start_url"] = request["wacz_start_url"]
        handler.setup_webreplay_server(run_headless=True)
        actual_replay = (
            _module_file(warc_handler_module, "WARC-Bench handler").parent.parent
            / "webreplay-standalone" / "dist" / "index.js"
        ).resolve()
        if actual_replay != replay or _sha(actual_replay.read_bytes()) != request["runtime"]["replay"]["sha256"]:
            raise RuntimeFailure(
                "WARC handler replay dist/index.js does not match the preflighted replay"
            )
        env = gymnasium.make(
            "browsergym/subtaskbench.online.4",
            cdp_port=cdp_port,
            connect_via_cdp=True,
        )
        return handler, env, manifest_evidence
    except Exception:
        handler.cleanup()
        raise


def _source_worker(request_path: Path) -> int:
    control_stdout = os.fdopen(os.dup(1), "w", buffering=1, encoding="utf-8")
    diagnostic_fd = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(diagnostic_fd, 1)
        os.dup2(diagnostic_fd, 2)
    finally:
        os.close(diagnostic_fd)
    request = _read_json(request_path, "source worker request")
    handler: Any | None = None
    env: Any | None = None
    retained_page: Any | None = None
    state: dict[str, Any] | None = None
    try:
        for line in os.sys.stdin:
            try:
                command = json.loads(line)
                operation = command.get("operation")
                if operation == "reset" and env is None:
                    handler, env, manifest_evidence = _make_upstream_environment(request)
                    observation, info = env.reset()
                    state = _worker_state(observation)
                    retained_page = _live_page(env)
                    browser_path = Path(
                        retained_page.context.browser.browser_type.executable_path
                    ).resolve()
                    if browser_path != Path(request["runtime"]["browser"]["path"]).resolve():
                        raise RuntimeFailure(
                            "live Playwright browser does not match the preflighted browser binary"
                        )
                    start_url = (
                        state.get("url") or info.get("url") or retained_page.url
                    )
                    result = {
                        "start_url": start_url,
                        "configured_start_url": request["wacz_start_url"],
                        "source_manifest": manifest_evidence,
                        "state": state,
                    }
                elif (
                    operation == "verify"
                    and env is not None
                    and state is not None
                    and retained_page is not None
                ):
                    if _live_page(env) is not retained_page:
                        raise RuntimeFailure(
                            "BrowserGym online.4 substituted the reset-time Playwright Page"
                        )
                    result = {
                        "verifier": _live_verify(retained_page, request, state)
                    }
                elif operation == "step" and env is not None and retained_page is not None:
                    observation, reward, terminated, truncated, info = env.step(command["action"])
                    if _live_page(env) is not retained_page:
                        raise RuntimeFailure(
                            "BrowserGym online.4 substituted the reset-time Playwright Page"
                        )
                    state = _worker_state(observation)
                    result = {
                        "outcome": {
                            "reward": reward, "terminated": terminated,
                            "truncated": truncated, "info": info,
                        },
                        "state": state,
                        "artifacts": _worker_artifacts(
                            observation, int(getattr(env, "_elapsed_steps", 0))
                        ),
                    }
                elif operation == "close" and env is not None:
                    env.close()
                    env = None
                    retained_page = None
                    handler.cleanup()
                    handler = None
                    result = {"completed": True}
                else:
                    raise RuntimeFailure("invalid BrowserGym source operation")
            except Exception as exc:
                result = {"error": str(exc)}
            print(
                json.dumps(result, sort_keys=True, default=str),
                file=control_stdout,
                flush=True,
            )
    finally:
        if env is not None:
            try:
                env.close()
            finally:
                if handler is not None:
                    handler.cleanup()
        elif handler is not None:
            handler.cleanup()
    control_stdout.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--result")
    parser.add_argument("--source-worker", action="store_true")
    args = parser.parse_args()
    try:
        if args.source_worker:
            return _source_worker(Path(args.request))
        if not args.result:
            raise RuntimeFailure("--result is required")
        run_lifecycle(Path(args.request), Path(args.result))
    except (OSError, ValueError, RuntimeFailure) as exc:
        print(f"WARC online.4 runtime failed: {exc}", file=os.sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
