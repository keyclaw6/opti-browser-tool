"""T1 deterministic cross-checks (ADR-0016): cheap flags, never scores.

Each check reads a visibility-filtered trace (and optionally the task
record's expectations) and emits ``Flag`` records with event citations.
Flags carry a *direction* so the closure argument stays explicit:

- ``fp_suspect``   — evidence that a pass may be false (T0 said passed, but…)
- ``fn_suspect``   — evidence that a fail may be false
- ``side_effect``  — unexpected mutation exposure (safety axis)
- ``anomaly``      — behavioral oddity worth diagnosis (loops, stale refs)

Disagreement handling is the caller's job (quarantine module): T1 never
adjusts a score, per the constitution and ADR-0016.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from opti_eval.models import has_edge_whitespace

from .evidence import Trace, event_refs, validate_json_value

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
SIDE_EFFECT_EXPECTATIONS = {"none", "some", "unknown"}
ASSERTION_OPS = {"equals", "contains", "exists"}
_MISSING = object()


@dataclass(slots=True)
class Flag:
    check: str
    direction: str  # fp_suspect | fn_suspect | side_effect | anomaly
    severity: str  # info | suspicion
    detail: str
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "check": self.check,
            "direction": self.direction,
            "severity": self.severity,
            "detail": self.detail,
            "evidence": self.evidence,
        }


def side_effect_monitor(trace: Trace, *, expectation: str = "unknown") -> list[Flag]:
    """HTTP-method side-effect monitor.

    ``expectation``: ``"none"`` (task should mutate nothing),
    ``"some"`` (task is expected to mutate state), or ``"unknown"``.
    A mutation where none is expected — or none where one is expected —
    raises suspicion (ADR-0016 T1).
    """
    flags: list[Flag] = []
    mutations = [
        e
        for e in trace.of_type("network_event")
        if str(e.get("payload", {}).get("method", "")).upper() in MUTATING_METHODS
    ]
    if expectation == "none" and mutations:
        flags.append(
            Flag(
                check="side_effect_monitor",
                direction="side_effect",
                severity="suspicion",
                detail=f"{len(mutations)} mutating request(s) where none was expected",
                evidence=event_refs(mutations[:10]),
            )
        )
    elif expectation == "some" and not mutations:
        flags.append(
            Flag(
                check="side_effect_monitor",
                direction="fp_suspect",
                severity="suspicion",
                detail="task expects a state mutation but no mutating request was observed",
            )
        )
    elif expectation == "unknown" and mutations:
        flags.append(
            Flag(
                check="side_effect_monitor",
                direction="anomaly",
                severity="info",
                detail=f"{len(mutations)} mutating request(s); task expectation unrecorded",
                evidence=event_refs(mutations[:10]),
            )
        )
    return flags


def zero_action_pass(trace: Trace, *, verifier_status: str) -> list[Flag]:
    """A claimed success with no executed actions is a classic verifier FP."""
    actions = trace.of_type("action_result")
    if verifier_status == "passed" and not actions:
        return [
            Flag(
                check="zero_action_pass",
                direction="fp_suspect",
                severity="suspicion",
                detail="verifier passed a run that executed zero actions",
            )
        ]
    return []


def action_count_anomaly(
    trace: Trace, *, max_actions: int = 120
) -> list[Flag]:
    actions = trace.of_type("action_result")
    if len(actions) > max_actions:
        return [
            Flag(
                check="action_count_anomaly",
                direction="anomaly",
                severity="info",
                detail=f"{len(actions)} actions exceeds the {max_actions} budget signal",
                evidence=event_refs(actions[-3:]),
            )
        ]
    return []


def loop_detector(trace: Trace, *, repeat_threshold: int = 4) -> list[Flag]:
    """N identical consecutive action signatures = stuck loop."""
    actions = trace.of_type("action_requested")
    streak = 1
    previous: str | None = None
    worst: tuple[int, list[dict[str, Any]]] = (1, [])
    window: list[dict[str, Any]] = []
    for event in actions:
        payload = event.get("payload", {})
        signature = f"{payload.get('action')}::{payload.get('target')}"
        if signature == previous:
            streak += 1
            window.append(event)
        else:
            streak = 1
            window = [event]
            previous = signature
        if streak > worst[0]:
            worst = (streak, list(window))
    if worst[0] >= repeat_threshold:
        return [
            Flag(
                check="loop_detector",
                direction="anomaly",
                severity="suspicion",
                detail=f"identical action repeated {worst[0]} times consecutively",
                evidence=event_refs(worst[1][:10]),
            )
        ]
    return []


def stale_epoch_check(trace: Trace) -> list[Flag]:
    """An action that used a reference from an older browser_state_epoch and
    still 'succeeded' points at wrong-target risk (the architecture demands
    stale references fail explicitly)."""
    flags: list[Flag] = []
    current_epoch = -1
    for event in trace.events:
        epoch = event.get("browser_state_epoch")
        if event.get("event_type") == "browser_state" and isinstance(epoch, int):
            current_epoch = max(current_epoch, epoch)
        if event.get("event_type") == "action_result" and isinstance(epoch, int):
            outcome = str(event.get("payload", {}).get("outcome", ""))
            if epoch < current_epoch and outcome == "ok":
                flags.append(
                    Flag(
                        check="stale_epoch",
                        direction="fp_suspect",
                        severity="suspicion",
                        detail=(
                            f"action succeeded against epoch {epoch} while the page "
                            f"was at epoch {current_epoch} — stale reference did not fail explicitly"
                        ),
                        evidence=event_refs([event]),
                    )
                )
    return flags


def expected_state_assertions(
    trace: Trace, assertions: list[dict[str, Any]], *, verifier_status: str
) -> list[Flag]:
    """Browser-side expected-state assertions from the task record.

    Assertion mini-language (deliberately tiny): ``{"path": "a.b.c",
    "op": "equals"|"contains"|"exists", "value": ...}`` evaluated against the
    final ``browser_state`` payload. Disagreement with T0 raises the matching
    suspicion direction.
    """
    flags: list[Flag] = []
    final_state = trace.final_of_type("browser_state")
    if final_state is None:
        if assertions:
            flags.append(
                Flag(
                    check="expected_state",
                    direction="anomaly",
                    severity="suspicion",
                    detail="task declares state assertions but the trace has no browser_state event",
                )
            )
        return flags
    payload = final_state.get("payload", {})
    for assertion in assertions:
        holds = _evaluate(payload, assertion)
        if holds and verifier_status == "failed":
            flags.append(
                Flag(
                    check="expected_state",
                    direction="fn_suspect",
                    severity="suspicion",
                    detail=f"final state satisfies {assertion} but the verifier failed the run",
                    evidence=event_refs([final_state]),
                )
            )
        elif not holds and verifier_status == "passed":
            flags.append(
                Flag(
                    check="expected_state",
                    direction="fp_suspect",
                    severity="suspicion",
                    detail=f"verifier passed the run but final state violates {assertion}",
                    evidence=event_refs([final_state]),
                )
            )
    return flags


def _evaluate(payload: dict[str, Any], assertion: dict[str, Any]) -> bool:
    node: Any = payload
    for part in assertion["path"].split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            node = _MISSING
            break
    op = assertion["op"]
    if op == "exists":
        return node is not _MISSING
    if op == "equals":
        return node is not _MISSING and _json_equal(node, assertion["value"])
    if op == "contains":
        return node is not _MISSING and _json_contains(node, assertion["value"])
    raise ValueError(f"unknown assertion op: {op}")


def _json_kind(value: object) -> str:
    if value is None:
        return "null"
    if type(value) is bool:
        return "boolean"
    if type(value) in {int, float}:
        return "number"
    if type(value) is str:
        return "string"
    if type(value) is list:
        return "array"
    if type(value) is dict:
        return "object"
    return "invalid"


def _json_equal(left: object, right: object) -> bool:
    """JSON-type-strict recursive equality (booleans are not numbers)."""
    kind = _json_kind(left)
    if kind == "invalid" or kind != _json_kind(right):
        return False
    if kind == "array":
        return len(left) == len(right) and all(  # type: ignore[arg-type]
            _json_equal(l_item, r_item)
            for l_item, r_item in zip(left, right, strict=True)  # type: ignore[arg-type]
        )
    if kind == "object":
        return set(left) == set(right) and all(  # type: ignore[arg-type]
            _json_equal(left[key], right[key]) for key in left  # type: ignore[index,union-attr]
        )
    return left == right


def _json_contains(container: object, expected: object) -> bool:
    """Preserve JSON container semantics without Python's bool/int coercion."""
    if type(container) is list:
        return any(_json_equal(item, expected) for item in container)
    if type(container) is str:
        return type(expected) is str and expected in container
    if type(container) is dict:
        return type(expected) is str and expected in container
    return False


def expectations_from_task(task: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    """Derive T1 inputs from a normalized task record.

    ``judge_expectations`` (optional, see evals/schemas/normalized-task.schema.json)
    wins when present; otherwise ``side_effect_expectation`` defaults from the
    required ``state_change_expected`` boolean (true -> "some", false -> "none").
    """
    if not isinstance(task, dict):
        raise ValueError("T1 task expectations require a task object")
    state_change_expected = task.get("state_change_expected")
    if type(state_change_expected) is not bool:
        raise ValueError("state_change_expected must be a boolean for T1")

    raw_expectations = task.get("judge_expectations", _MISSING)
    if raw_expectations is _MISSING:
        expectations: dict[str, Any] = {}
    elif not isinstance(raw_expectations, dict):
        raise ValueError("judge_expectations must be an object")
    else:
        expectations = raw_expectations
    unsupported = set(expectations) - {
        "side_effect_expectation",
        "state_assertions",
    }
    if unsupported:
        raise ValueError(
            "judge_expectations has unsupported fields: "
            + ", ".join(sorted(unsupported))
        )

    if "side_effect_expectation" not in expectations:
        side_effects = "some" if state_change_expected else "none"
    else:
        side_effects = expectations["side_effect_expectation"]
    if type(side_effects) is not str or side_effects not in SIDE_EFFECT_EXPECTATIONS:
        raise ValueError(
            "judge_expectations side_effect_expectation must be none, some, or unknown"
        )

    raw_assertions = expectations.get("state_assertions", [])
    if not isinstance(raw_assertions, list):
        raise ValueError("judge_expectations state_assertions must be an array")
    assertions: list[dict[str, Any]] = []
    for index, assertion in enumerate(raw_assertions):
        if not isinstance(assertion, dict):
            raise ValueError(f"state_assertions[{index}] must be an object")
        if set(assertion) - {"path", "op", "value"}:
            raise ValueError(f"state_assertions[{index}] has unsupported fields")
        path = assertion.get("path")
        if (
            not isinstance(path, str)
            or not path
            or has_edge_whitespace(path)
            or any(not part for part in path.split("."))
        ):
            raise ValueError(
                f"state_assertions[{index}] path must be a non-empty dotted path"
            )
        op = assertion.get("op")
        if type(op) is not str or op not in ASSERTION_OPS:
            raise ValueError(f"state_assertions[{index}] op is not supported")
        if op in {"equals", "contains"} and "value" not in assertion:
            raise ValueError(f"state_assertions[{index}] {op} requires value")
        if op == "exists" and "value" in assertion:
            raise ValueError(f"state_assertions[{index}] exists must not include value")
        if "value" in assertion:
            validate_json_value(
                assertion["value"], label=f"state_assertions[{index}] value"
            )
        assertions.append(dict(assertion))
    return side_effects, assertions


def run_all(
    trace: Trace,
    *,
    verifier_status: str,
    side_effect_expectation: str = "unknown",
    assertions: list[dict[str, Any]] | None = None,
) -> list[Flag]:
    flags: list[Flag] = []
    flags += side_effect_monitor(trace, expectation=side_effect_expectation)
    flags += zero_action_pass(trace, verifier_status=verifier_status)
    flags += action_count_anomaly(trace)
    flags += loop_detector(trace)
    flags += stale_epoch_check(trace)
    flags += expected_state_assertions(
        trace, assertions or [], verifier_status=verifier_status
    )
    return flags
