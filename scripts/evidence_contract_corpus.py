"""Shared positive/adversarial corpus for the AR-003 evidence contracts.

The optional JSON-Schema audit and dependency-free runtime tests consume the
same values.  Cross-event closure cases remain schema-valid per event and are
rejected by the trace runtime, where ordering can actually be evaluated.
"""
from __future__ import annotations

import copy
import json
from typing import Any

EPOCH_EVENT_TYPES = {
    "model_observation",
    "action_requested",
    "action_result",
    "browser_state",
    "browser_event",
    "page_transition",
    "tab_event",
}
EDGE_WHITESPACE_CASES = (
    ("crlf", "\r\n"),
    ("nel", "\u0085"),
    ("bom", "\ufeff"),
)


def artifact_ref(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "kind": "trace",
        "uri": "trace.jsonl",
        "sha256": "0" * 64,
        "media_type": "application/x-ndjson",
        "visibility": ["judge", "orchestrator"],
    }
    row.update(overrides)
    return row


def persisted_result(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "schema_version": "0.1.0",
        "run_id": "run-1",
        "task_id": "task-a",
        "source": "test-source",
        "status": "passed",
        "reward": 1.0,
        "verifier": {
            "id": "verifier-v1",
            "checksum": "checksum-v1",
            "outcome": "passed",
        },
        "error": None,
        "trace_path": "trace.jsonl",
        "artifacts": [artifact_ref()],
        "metrics": {},
        "metadata": {"benchmark_reportable": True},
        "timing": {
            "started_at": "2026-07-14T00:00:00Z",
            "finished_at": "2026-07-14T00:00:01+00:00",
            "elapsed_seconds": 1.0,
        },
    }
    row.update(copy.deepcopy(overrides))
    return row


def bridge_result(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "task_id": "task-a",
        "status": "passed",
        "reward": 1.0,
        "verifier": {"id": "verifier-v1", "checksum": "checksum-v1"},
        "error": None,
        "trace_path": "trace.jsonl",
        "artifacts": [artifact_ref()],
        "metrics": {},
        "metadata": {"benchmark_reportable": False},
    }
    row.update(copy.deepcopy(overrides))
    return row


def normalized_task(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "schema_version": "0.1.0",
        "id": "task-a",
        "source": "real_v1",
        "upstream": {
            "benchmark": "REAL",
            "version": "v1",
            "native_task_id": "1",
            "site": "example",
            "source_manifest": "manifest.json",
            "source_checksum": "checksum",
        },
        "goal": "Complete the task",
        "site": "example",
        "interaction_class": "form",
        "state_change_expected": False,
        "suite_membership": ["candidate-pool", "primary"],
        "difficulty_evidence": {
            "reference_success_percent": 50,
            "evidence_scope": "benchmark_aggregate_not_task_level",
            "per_task_success_percent": None,
            "per_task_calibration_status": "pending",
        },
        "verification": {},
        "runtime": {},
        "provenance": {},
    }
    row.update(copy.deepcopy(overrides))
    return row


def suite_manifest(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "schema_version": "0.1.0",
        "id": "primary",
        "kind": "primary",
        "status": "provisional",
        "task_count": 1,
        "task_ids": ["task-a"],
        "policy": {},
    }
    row.update(copy.deepcopy(overrides))
    return row


def state_assertion(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {"path": "done", "op": "exists"}
    row.update(copy.deepcopy(overrides))
    return row


def trace_event(
    seq: int,
    event_type: str = "browser_state",
    **overrides: Any,
) -> dict[str, Any]:
    verifier = event_type == "verifier_result"
    row: dict[str, Any] = {
        "schema_version": "0.1-draft",
        "run_id": "run-1",
        "task_id": "task-a",
        "event_id": f"event-{seq}",
        "sequence": seq,
        "timestamp": f"2026-07-14T00:00:{seq:02d}Z",
        "monotonic_ms": float(seq),
        "actor": "verifier" if verifier else "browser",
        "event_type": event_type,
        "visibility": ["judge", "orchestrator"],
        "payload": (
            {
                "status": "passed",
                "verifier_id": "verifier-v1",
                "verifier_checksum": "checksum-v1",
            }
            if verifier
            else {"ready": True}
        ),
        "artifact_refs": [],
    }
    if event_type in EPOCH_EVENT_TYPES:
        row["browser_state_epoch"] = 0
    row.update(copy.deepcopy(overrides))
    return row


def raw_constant_event(token: str) -> str:
    rendered = json.dumps(trace_event(1), separators=(",", ":"))
    return rendered.replace('"ready":true', f'"ready":{token}')


def raw_trace(
    events: list[dict[str, Any]],
    *,
    separator: str = "\n",
    final_separator: bool = True,
    ensure_ascii: bool = False,
) -> str:
    rendered = separator.join(
        json.dumps(event, separators=(",", ":"), ensure_ascii=ensure_ascii)
        for event in events
    )
    return rendered + (separator if final_separator else "")


def build_evidence_contract_corpus() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []

    def add(
        label: str,
        target: str,
        value: object,
        *,
        valid: bool,
        schema_valid: bool | None = None,
        json_domain_valid: bool = True,
    ) -> None:
        cases.append(
            {
                "label": label,
                "target": target,
                "value": value,
                "runtime_valid": valid,
                "schema_valid": valid if schema_valid is None else schema_valid,
                "json_domain_valid": json_domain_valid,
            }
        )

    def changed(value: dict[str, Any], path: tuple[object, ...], replacement: Any) -> dict[str, Any]:
        row = copy.deepcopy(value)
        node: Any = row
        for part in path[:-1]:
            node = node[part]
        node[path[-1]] = replacement
        return row

    add("result-valid-producer-shape", "result", persisted_result(), valid=True)
    add("result-traversal-trace", "result", persisted_result(trace_path="../trace.jsonl"), valid=False)
    add("result-absolute-trace", "result", persisted_result(trace_path="/tmp/trace.jsonl"), valid=False)
    add("result-leading-space-trace", "result", persisted_result(trace_path=" trace.jsonl"), valid=False)
    add("result-trailing-space-trace", "result", persisted_result(trace_path="trace.jsonl "), valid=False)
    for label, uri in (
        ("final-lf", "trace.jsonl\n"),
        ("lf-space", "trace.jsonl\n "),
        ("multiline-dotdot", "safe\n/../secret"),
        ("multiline-dot", "safe\n/./secret"),
    ):
        add(
            f"result-{label}-trace",
            "result",
            persisted_result(trace_path=uri),
            valid=False,
        )
    add(
        "result-nested-trailing-space-artifact",
        "result",
        persisted_result(artifacts=[artifact_ref(uri="a/b ")]),
        valid=False,
    )
    add(
        "result-traversal-artifact",
        "result",
        persisted_result(artifacts=[artifact_ref(uri="nested/../../secret")]),
        valid=False,
    )
    add("result-whitespace-task-id", "result", persisted_result(task_id=" task-a"), valid=False)
    add("result-unsafe-task-id", "result", persisted_result(task_id="../../escaped"), valid=False)
    add("result-final-lf-task-id", "result", persisted_result(task_id="task-a\n"), valid=False)
    add("result-final-lf-run-id", "result", persisted_result(run_id="run-1\n"), valid=False)
    add("result-final-lf-source", "result", persisted_result(source="test-source\n"), valid=False)
    for field in ("id", "checksum"):
        add(
            f"result-final-lf-verifier-{field}",
            "result",
            changed(persisted_result(), ("verifier", field), f"verifier-{field}\n"),
            valid=False,
        )
    for field, replacement in (
        ("kind", "trace\n"),
        ("media_type", "application/x-ndjson\n"),
        ("sha256", "0" * 64 + "\n"),
    ):
        add(
            f"result-final-lf-artifact-{field}",
            "result",
            persisted_result(artifacts=[artifact_ref(**{field: replacement})]),
            valid=False,
        )
    add("result-bool-reward", "result", persisted_result(reward=True), valid=False)
    add(
        "result-duplicate-visibility",
        "result",
        persisted_result(artifacts=[artifact_ref(visibility=["judge", "judge"])]),
        valid=False,
    )
    add(
        "result-bad-hash",
        "result",
        persisted_result(artifacts=[artifact_ref(sha256="F" * 64)]),
        valid=False,
    )
    bad_timing = copy.deepcopy(persisted_result()["timing"])
    bad_timing["started_at"] = "2026-99-99T00:00:00Z"
    add("result-invalid-date", "result", persisted_result(timing=bad_timing), valid=False)
    for field in ("started_at", "finished_at"):
        add(
            f"result-final-lf-{field}",
            "result",
            changed(
                persisted_result(),
                ("timing", field),
                "2026-07-14T00:00:00Z\n",
            ),
            valid=False,
        )
    bool_timing = copy.deepcopy(persisted_result()["timing"])
    bool_timing["elapsed_seconds"] = True
    add("result-bool-elapsed", "result", persisted_result(timing=bool_timing), valid=False)
    add("result-nested-metrics-type", "result", persisted_result(metrics=[]), valid=False)
    add("result-nested-verifier-type", "result", persisted_result(verifier=[]), valid=False)
    for label, edge in EDGE_WHITESPACE_CASES:
        add(
            f"result-{label}-run-id-prefix",
            "result",
            persisted_result(run_id=edge + "run-1"),
            valid=False,
        )
        add(
            f"result-{label}-trace-suffix",
            "result",
            persisted_result(trace_path="trace.jsonl" + edge),
            valid=False,
        )
        add(
            f"result-{label}-verifier-id-suffix",
            "result",
            changed(
                persisted_result(),
                ("verifier", "id"),
                "verifier-v1" + edge,
            ),
            valid=False,
        )
    add(
        "result-nonfinite-reward",
        "result",
        persisted_result(reward=float("nan")),
        valid=False,
        schema_valid=False,
        json_domain_valid=False,
    )
    add(
        "result-nested-nonfinite-metrics",
        "result",
        persisted_result(metrics={"timing": {"p95": float("inf")}}),
        valid=False,
        schema_valid=False,
        json_domain_valid=False,
    )
    add(
        "result-nested-nonfinite-metadata",
        "result",
        persisted_result(metadata={"score": float("-inf")}),
        valid=False,
        schema_valid=False,
        json_domain_valid=False,
    )

    add("bridge-valid", "bridge", bridge_result(), valid=True)
    add("bridge-traversal-trace", "bridge", bridge_result(trace_path="../trace.jsonl"), valid=False)
    add("bridge-absolute-trace", "bridge", bridge_result(trace_path="/tmp/trace.jsonl"), valid=False)
    add("bridge-leading-space-trace", "bridge", bridge_result(trace_path=" trace.jsonl"), valid=False)
    add("bridge-trailing-space-trace", "bridge", bridge_result(trace_path="trace.jsonl "), valid=False)
    for label, uri in (
        ("final-lf", "trace.jsonl\n"),
        ("lf-space", "trace.jsonl\n "),
        ("multiline-dotdot", "safe\n/../secret"),
        ("multiline-dot", "safe\n/./secret"),
    ):
        add(
            f"bridge-{label}-trace",
            "bridge",
            bridge_result(trace_path=uri),
            valid=False,
        )
    add(
        "bridge-nested-trailing-space-artifact",
        "bridge",
        bridge_result(artifacts=[artifact_ref(uri="a/b ")]),
        valid=False,
    )
    add("bridge-whitespace-task-id", "bridge", bridge_result(task_id=" task-a"), valid=False)
    add("bridge-unsafe-task-id", "bridge", bridge_result(task_id="../task-a"), valid=False)
    add("bridge-final-lf-task-id", "bridge", bridge_result(task_id="task-a\n"), valid=False)
    for field in ("id", "checksum"):
        add(
            f"bridge-final-lf-verifier-{field}",
            "bridge",
            changed(bridge_result(), ("verifier", field), f"verifier-{field}\n"),
            valid=False,
        )
    for field, replacement in (
        ("kind", "trace\n"),
        ("media_type", "application/x-ndjson\n"),
        ("sha256", "0" * 64 + "\n"),
    ):
        add(
            f"bridge-final-lf-artifact-{field}",
            "bridge",
            bridge_result(artifacts=[artifact_ref(**{field: replacement})]),
            valid=False,
        )
    add("bridge-bool-reward", "bridge", bridge_result(reward=True), valid=False)
    add("bridge-nested-metadata-type", "bridge", bridge_result(metadata=[]), valid=False)
    add(
        "bridge-invalid-artifact-visibility",
        "bridge",
        bridge_result(artifacts=[artifact_ref(visibility=["owner"])]),
        valid=False,
    )
    for label, edge in EDGE_WHITESPACE_CASES:
        add(
            f"bridge-{label}-task-id-suffix",
            "bridge",
            bridge_result(task_id="task-a" + edge),
            valid=False,
        )
        add(
            f"bridge-{label}-trace-prefix",
            "bridge",
            bridge_result(trace_path=edge + "trace.jsonl"),
            valid=False,
        )
        add(
            f"bridge-{label}-verifier-checksum-suffix",
            "bridge",
            changed(
                bridge_result(),
                ("verifier", "checksum"),
                "checksum-v1" + edge,
            ),
            valid=False,
        )
    add(
        "bridge-nonfinite-reward",
        "bridge",
        bridge_result(reward=float("nan")),
        valid=False,
        schema_valid=False,
        json_domain_valid=False,
    )
    add(
        "bridge-nested-nonfinite-metrics",
        "bridge",
        bridge_result(metrics={"nested": [float("inf")]}),
        valid=False,
        schema_valid=False,
        json_domain_valid=False,
    )

    add("task-valid", "task", normalized_task(), valid=True)
    add(
        "task-final-lf-id",
        "task",
        normalized_task(id="task-a\n"),
        valid=False,
    )
    add(
        "task-final-lf-source",
        "task",
        normalized_task(source="real_v1\n"),
        valid=False,
    )
    for label, edge in EDGE_WHITESPACE_CASES:
        add(
            f"task-{label}-goal-prefix",
            "task",
            normalized_task(goal=edge + "Complete the task"),
            valid=False,
        )
        add(
            f"task-{label}-site-suffix",
            "task",
            normalized_task(site="example" + edge),
            valid=False,
        )
    add(
        "task-nested-nonfinite-runtime",
        "task",
        normalized_task(runtime={"timeout": float("inf")}),
        valid=False,
        schema_valid=False,
        json_domain_valid=False,
    )

    add("suite-valid", "suite", suite_manifest(), valid=True)
    add(
        "suite-final-lf-id",
        "suite",
        suite_manifest(id="primary\n"),
        valid=False,
    )
    add(
        "suite-final-lf-task-id",
        "suite",
        suite_manifest(task_ids=["task-a\n"]),
        valid=False,
    )
    add(
        "suite-duplicate-task-id",
        "suite",
        suite_manifest(task_count=2, task_ids=["task-a", "task-a"]),
        valid=False,
    )
    add(
        "suite-bool-task-count",
        "suite",
        suite_manifest(task_count=True),
        valid=False,
    )
    for label, edge in EDGE_WHITESPACE_CASES:
        add(
            f"suite-{label}-id-suffix",
            "suite",
            suite_manifest(id="primary" + edge),
            valid=False,
        )
        add(
            f"suite-{label}-task-id-prefix",
            "suite",
            suite_manifest(task_ids=[edge + "task-a"]),
            valid=False,
        )
    add(
        "suite-nested-nonfinite-policy",
        "suite",
        suite_manifest(policy={"threshold": float("nan")}),
        valid=False,
        schema_valid=False,
        json_domain_valid=False,
    )

    add("assertion-valid", "assertion", state_assertion(), valid=True)
    for label, path in (
        ("final-lf", "done\n"),
        ("multiline-double-dot", "a\n..b"),
        ("multiline-final-dot", "a\nb."),
    ):
        add(
            f"assertion-{label}-path",
            "assertion",
            state_assertion(path=path),
            valid=False,
        )
    add(
        "assertion-equals-missing-value",
        "assertion",
        state_assertion(op="equals"),
        valid=False,
    )
    add(
        "assertion-exists-with-value",
        "assertion",
        state_assertion(value=True),
        valid=False,
    )
    for label, edge in EDGE_WHITESPACE_CASES:
        add(
            f"assertion-{label}-path-prefix",
            "assertion",
            state_assertion(path=edge + "done"),
            valid=False,
        )
        add(
            f"assertion-{label}-path-suffix",
            "assertion",
            state_assertion(path="done" + edge),
            valid=False,
        )
    add(
        "assertion-nonfinite-equals-value",
        "assertion",
        state_assertion(op="equals", value=float("nan")),
        valid=False,
        schema_valid=False,
        json_domain_valid=False,
    )

    add("event-valid", "event", trace_event(1), valid=True)
    add("event-valid-terminal", "event", trace_event(2, "verifier_result"), valid=True)
    add("event-whitespace-task-id", "event", trace_event(1, task_id=" task-a"), valid=False)
    add("event-unsafe-task-id", "event", trace_event(1, task_id="../../escaped"), valid=False)
    add("event-final-lf-task-id", "event", trace_event(1, task_id="task-a\n"), valid=False)
    add("event-final-lf-run-id", "event", trace_event(1, run_id="run-1\n"), valid=False)
    add(
        "event-final-lf-event-id",
        "event",
        trace_event(1, event_id="event-1\n"),
        valid=False,
    )
    add(
        "event-final-lf-parent-id",
        "event",
        trace_event(1, parent_event_id="event-0\n"),
        valid=False,
    )
    add("event-bool-sequence", "event", trace_event(1, sequence=True), valid=False)
    add("event-bool-monotonic", "event", trace_event(1, monotonic_ms=True), valid=False)
    add("event-invalid-date", "event", trace_event(1, timestamp="yesterday"), valid=False)
    add(
        "event-final-lf-timestamp",
        "event",
        trace_event(1, timestamp="2026-07-14T00:00:01Z\n"),
        valid=False,
    )
    add("event-nested-payload-type", "event", trace_event(1, payload=[]), valid=False)
    missing_epoch = trace_event(1)
    del missing_epoch["browser_state_epoch"]
    add("event-missing-required-epoch", "event", missing_epoch, valid=False)
    add(
        "event-traversal-artifact",
        "event",
        trace_event(1, artifact_refs=[artifact_ref(uri="../secret")]),
        valid=False,
    )
    add(
        "event-absolute-artifact",
        "event",
        trace_event(1, artifact_refs=[artifact_ref(uri="/tmp/secret")]),
        valid=False,
    )
    for label, uri in (
        ("leading-space", " trace.jsonl"),
        ("trailing-space", "trace.jsonl "),
        ("nested-trailing-space", "a/b "),
        ("final-lf", "trace.jsonl\n"),
        ("lf-space", "trace.jsonl\n "),
        ("multiline-dotdot", "safe\n/../secret"),
        ("multiline-dot", "safe\n/./secret"),
    ):
        add(
            f"event-{label}-artifact",
            "event",
            trace_event(1, artifact_refs=[artifact_ref(uri=uri)]),
            valid=False,
        )
    add(
        "event-bad-hash",
        "event",
        trace_event(1, artifact_refs=[artifact_ref(sha256="x" * 64)]),
        valid=False,
    )
    for field, replacement in (
        ("kind", "trace\n"),
        ("media_type", "application/x-ndjson\n"),
        ("sha256", "0" * 64 + "\n"),
    ):
        add(
            f"event-final-lf-artifact-{field}",
            "event",
            trace_event(1, artifact_refs=[artifact_ref(**{field: replacement})]),
            valid=False,
        )
    missing_identity = trace_event(2, "verifier_result")
    del missing_identity["payload"]["verifier_checksum"]
    add("event-terminal-missing-identity", "event", missing_identity, valid=False)
    for field in ("verifier_id", "verifier_checksum"):
        add(
            f"event-final-lf-terminal-{field}",
            "event",
            changed(
                trace_event(2, "verifier_result"),
                ("payload", field),
                f"{field}\n",
            ),
            valid=False,
        )
    add(
        "event-terminal-wrong-actor",
        "event",
        trace_event(2, "verifier_result", actor="browser"),
        valid=False,
    )
    for label, edge in EDGE_WHITESPACE_CASES:
        add(
            f"event-{label}-run-id-prefix",
            "event",
            trace_event(1, run_id=edge + "run-1"),
            valid=False,
        )
        add(
            f"event-{label}-artifact-uri-suffix",
            "event",
            trace_event(
                1,
                artifact_refs=[artifact_ref(uri="trace.jsonl" + edge)],
            ),
            valid=False,
        )
        add(
            f"event-{label}-terminal-verifier-id-suffix",
            "event",
            changed(
                trace_event(2, "verifier_result"),
                ("payload", "verifier_id"),
                "verifier-v1" + edge,
            ),
            valid=False,
        )
    add(
        "event-nonfinite-monotonic",
        "event",
        trace_event(1, monotonic_ms=float("nan")),
        valid=False,
        schema_valid=False,
        json_domain_valid=False,
    )
    add(
        "event-nested-nonfinite-payload",
        "event",
        trace_event(1, payload={"nested": {"score": float("inf")}}),
        valid=False,
        schema_valid=False,
        json_domain_valid=False,
    )
    add(
        "event-nested-nonfinite-redaction",
        "event",
        trace_event(1, redaction={"confidence": float("-inf")}),
        valid=False,
        schema_valid=False,
        json_domain_valid=False,
    )
    for token in ("NaN", "Infinity", "-Infinity"):
        add(
            f"raw-event-{token.lower().replace('-', 'negative-')}",
            "raw_event",
            raw_constant_event(token),
            valid=False,
            schema_valid=False,
        )

    raw_events = [trace_event(1), trace_event(2, "verifier_result")]
    add(
        "raw-trace-no-final-lf",
        "raw_trace",
        raw_trace(raw_events, final_separator=False),
        valid=True,
        schema_valid=False,
    )
    add(
        "raw-trace-one-final-lf",
        "raw_trace",
        raw_trace(raw_events),
        valid=True,
        schema_valid=False,
    )
    add(
        "raw-trace-crlf",
        "raw_trace",
        raw_trace(raw_events, separator="\r\n"),
        valid=True,
        schema_valid=False,
    )
    for label, interior in (
        ("nel-payload", "left\u0085right"),
        ("line-separator-payload", "left\u2028right"),
        ("paragraph-separator-payload", "left\u2029right"),
    ):
        events = copy.deepcopy(raw_events)
        events[0]["payload"]["text"] = interior
        add(
            f"raw-trace-{label}",
            "raw_trace",
            raw_trace(events, ensure_ascii=False),
            valid=True,
            schema_valid=False,
        )
    for label, separator in (
        ("lone-cr", "\r"),
        ("vertical-tab", "\v"),
        ("form-feed", "\f"),
        ("file-separator", "\x1c"),
        ("nel", "\u0085"),
        ("line-separator", "\u2028"),
        ("paragraph-separator", "\u2029"),
    ):
        add(
            f"raw-trace-{label}-record-separator",
            "raw_trace",
            raw_trace(raw_events, separator=separator),
            valid=False,
            schema_valid=False,
        )
    first_line = raw_trace([raw_events[0]], final_separator=False)
    second_line = raw_trace([raw_events[1]], final_separator=False)
    add(
        "raw-trace-interior-blank-record",
        "raw_trace",
        first_line + "\n\n" + second_line + "\n",
        valid=False,
        schema_valid=False,
    )
    add(
        "raw-trace-double-trailing-lf",
        "raw_trace",
        first_line + "\n" + second_line + "\n\n",
        valid=False,
        schema_valid=False,
    )
    add(
        "raw-trace-final-lone-cr",
        "raw_trace",
        first_line + "\n" + second_line + "\r",
        valid=False,
        schema_valid=False,
    )
    add(
        "raw-trace-truncated-final-record",
        "raw_trace",
        first_line + '\n{"schema_version":"0.1-draft"',
        valid=False,
        schema_valid=False,
    )

    add(
        "trace-valid-terminal-closure",
        "trace",
        [trace_event(1), trace_event(2, "verifier_result")],
        valid=True,
        schema_valid=True,
    )
    add(
        "trace-duplicate-verifier-result",
        "trace",
        [
            trace_event(1),
            trace_event(2, "verifier_result"),
            trace_event(3, "verifier_result"),
        ],
        valid=False,
        schema_valid=True,
    )
    add(
        "trace-event-after-verifier-result",
        "trace",
        [trace_event(1), trace_event(2, "verifier_result"), trace_event(3)],
        valid=False,
        schema_valid=True,
    )
    add(
        "trace-sequence-gap",
        "trace",
        [trace_event(1), trace_event(10, "verifier_result")],
        valid=False,
        schema_valid=True,
    )
    add(
        "trace-backwards-wall-clock",
        "trace",
        [
            trace_event(1, timestamp="2026-07-14T00:00:10Z"),
            trace_event(2, "verifier_result", timestamp="2026-07-14T00:00:09Z"),
        ],
        valid=False,
        schema_valid=True,
    )
    add(
        "trace-decreasing-browser-epoch",
        "trace",
        [
            trace_event(1, browser_state_epoch=2),
            trace_event(2, "action_result", browser_state_epoch=1),
            trace_event(3, "verifier_result"),
        ],
        valid=False,
        schema_valid=True,
    )
    add(
        "trace-decreasing-optional-network-epoch",
        "trace",
        [
            trace_event(1, browser_state_epoch=2),
            trace_event(2, "network_event", browser_state_epoch=1),
            trace_event(3, browser_state_epoch=2),
            trace_event(4, "verifier_result"),
        ],
        valid=False,
        schema_valid=True,
    )
    add(
        "trace-decreasing-optional-console-epoch",
        "trace",
        [
            trace_event(1, browser_state_epoch=1),
            trace_event(2, "console_event", browser_state_epoch=0),
            trace_event(3, browser_state_epoch=1),
            trace_event(4, "verifier_result"),
        ],
        valid=False,
        schema_valid=True,
    )
    add(
        "trace-equal-and-increasing-optional-epochs",
        "trace",
        [
            trace_event(1, browser_state_epoch=0),
            trace_event(2, "network_event", browser_state_epoch=0),
            trace_event(3, "console_event", browser_state_epoch=1),
            trace_event(4, browser_state_epoch=1),
            trace_event(5, "verifier_result"),
        ],
        valid=True,
        schema_valid=True,
    )
    missing_epoch_trace = trace_event(1)
    del missing_epoch_trace["browser_state_epoch"]
    add(
        "trace-missing-required-epoch",
        "trace",
        [missing_epoch_trace, trace_event(2, "verifier_result")],
        valid=False,
        schema_valid=False,
    )
    add(
        "trace-missing-final-browser-state",
        "trace",
        [
            trace_event(1, "network_event"),
            trace_event(2, "verifier_result"),
        ],
        valid=False,
        schema_valid=True,
    )
    add(
        "trace-action-after-final-browser-state",
        "trace",
        [
            trace_event(1),
            trace_event(2, "action_result"),
            trace_event(3, "verifier_result"),
        ],
        valid=False,
        schema_valid=True,
    )
    add(
        "trace-nested-nonfinite-payload",
        "trace",
        [
            trace_event(1, payload={"score": float("inf")}),
            trace_event(2, "verifier_result"),
        ],
        valid=False,
        schema_valid=False,
        json_domain_valid=False,
    )
    return cases
