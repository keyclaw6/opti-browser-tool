"""Minimal foreground lifecycle and closed campaign limits."""
from __future__ import annotations

import copy
import datetime as dt
from typing import TYPE_CHECKING, Any

from . import gitutil
if TYPE_CHECKING:
    from .campaign import Campaign

LIFECYCLE_VERSION = "0.1.0"
OPERATION_VERSION = "0.1.0"


def operation_config(
    *, max_iterations: int, max_attempts: int, deadline_seconds: int
) -> dict[str, Any]:
    for name, value in (
        ("max_iterations", max_iterations),
        ("max_attempts", max_attempts),
        ("deadline_seconds", deadline_seconds),
    ):
        if type(value) is not int or value < 1:
            raise ValueError(f"--{name.replace('_', '-')} must be an integer >= 1")
    deadline = dt.datetime.now(dt.timezone.utc) + dt.timedelta(
        seconds=deadline_seconds
    )
    return {
        "schema_version": OPERATION_VERSION,
        "max_iterations": max_iterations,
        "max_attempts": max_attempts,
        "deadline_at": deadline.isoformat(),
        "external_metering": "not_required",
        "authorization": "offline_only",
    }


def initial_lifecycle() -> dict[str, Any]:
    return {
        "schema_version": LIFECYCLE_VERSION,
        "state": "idle",
        "request": "run",
    }


def _deadline(value: object) -> dt.datetime:
    if type(value) is not str:
        raise ValueError("operation deadline_at must be an RFC3339 string")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("operation deadline_at must be valid RFC3339") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("operation deadline_at must include a timezone")
    return parsed.astimezone(dt.timezone.utc)


def validate_operation(campaign: Campaign) -> tuple[dict[str, Any], dict[str, Any]]:
    operation = campaign.config.get("operation")
    expected_operation = {
        "schema_version", "max_iterations", "max_attempts", "deadline_at",
        "external_metering",
        "authorization",
    }
    if type(operation) is not dict or set(operation) != expected_operation:
        raise ValueError("campaign operation limits have an invalid closed shape")
    if operation["schema_version"] != OPERATION_VERSION:
        raise ValueError("campaign operation schema_version is unsupported")
    for name in ("max_iterations", "max_attempts"):
        if type(operation[name]) is not int or operation[name] < 1:
            raise ValueError(f"campaign operation {name} must be an integer >= 1")
    _deadline(operation["deadline_at"])
    metering = operation["external_metering"]
    available_identity = (
        metering.removeprefix("available:")
        if type(metering) is str and metering.startswith("available:")
        else ""
    )
    if metering not in {"not_required", "unavailable"} and (
        not available_identity or available_identity != available_identity.strip()
    ):
        raise ValueError(
            "campaign external_metering must be not_required, unavailable, or available:<identity>"
        )
    if operation["authorization"] not in {
        "offline_only", "required", "owner_authorized"
    }:
        raise ValueError("campaign authorization state is invalid")

    lifecycle = campaign.state.get("lifecycle")
    if type(lifecycle) is not dict or set(lifecycle) != {
        "schema_version", "state", "request"
    }:
        raise ValueError("campaign lifecycle has an invalid closed shape")
    if lifecycle["schema_version"] != LIFECYCLE_VERSION:
        raise ValueError("campaign lifecycle schema_version is unsupported")
    if lifecycle["state"] not in {"idle", "running", "paused", "stopped"}:
        raise ValueError("campaign lifecycle state is invalid")
    if lifecycle["request"] not in {"run", "pause", "stop"}:
        raise ValueError("campaign lifecycle request is invalid")
    attempts = campaign.state.get("operation_attempts")
    if type(attempts) is not int or attempts < 0:
        raise ValueError("campaign operation_attempts must be an integer >= 0")
    active_attempt = campaign.state.get("active_attempt_iteration")
    if active_attempt is not None and (
        type(active_attempt) is not int or active_attempt < 1
    ):
        raise ValueError("campaign active_attempt_iteration must be null or an integer >= 1")
    cleanup = campaign.state.get("cleanup_health")
    if type(cleanup) is not dict or set(cleanup) != {"status", "detail"}:
        raise ValueError("campaign cleanup_health has an invalid closed shape")
    if cleanup["status"] not in {"clean", "failed"} or type(cleanup["detail"]) is not str:
        raise ValueError("campaign cleanup_health is invalid")
    return operation, lifecycle


def blockers(campaign: Campaign, *, action: str) -> list[str]:
    try:
        operation, lifecycle = validate_operation(campaign)
    except ValueError as exc:
        return [f"configuration: {exc}"]
    result: list[str] = []
    if lifecycle["request"] == "pause" or lifecycle["state"] == "paused":
        result.append("lifecycle: campaign is paused; run `opti-loop resume --campaign ID`")
    if lifecycle["request"] == "stop" or lifecycle["state"] == "stopped":
        result.append("lifecycle: campaign is stopped; run `opti-loop resume --campaign ID`")
    if (
        campaign.state["cleanup_health"]["status"] == "failed"
        and action != "reconcile"
    ):
        result.append(
            "cleanup: " + campaign.state["cleanup_health"]["detail"]
            + "; inspect retained evidence before any further transition"
        )
    if action == "start" and campaign.current_iteration >= operation["max_iterations"]:
        result.append("budget: campaign iteration limit is exhausted")
    if action == "attempt" and campaign.state["operation_attempts"] >= operation["max_attempts"]:
        result.append("budget: campaign attempt limit is exhausted")
    if action != "reconcile":
        if dt.datetime.now(dt.timezone.utc) >= _deadline(operation["deadline_at"]):
            result.append("budget: campaign wall-clock deadline is exhausted")
        if operation["external_metering"] == "unavailable":
            result.append(
                "budget: external spend/token metering is required but unavailable; "
                "supply an approved meter before production advancement"
            )
        if operation["authorization"] == "required":
            result.append(
                "authorization: explicit owner authorization for this production campaign is missing"
            )
    return result


def require_transition(campaign: Campaign, *, action: str) -> None:
    found = blockers(campaign, action=action)
    if found:
        raise RuntimeError("campaign transition blocked: " + "; ".join(found))


def request(
    campaign: Campaign, value: str, *, resume: bool = False
) -> dict[str, Any]:
    if value not in {"run", "pause", "stop"}:
        raise ValueError("lifecycle request must be run, pause, or stop")
    # Import locally: campaign initialization imports ``initial_lifecycle``.
    from .campaign import load_campaign
    from .materialization import CampaignLock

    materialization_store = campaign.store.campaign_dir / "materializations"
    materialization_store.mkdir(mode=0o700, exist_ok=True)
    materialization_store.chmod(0o700)
    with CampaignLock(materialization_store):
        fresh = load_campaign(
            campaign.repo_root,
            campaign.campaign_id,
            store_root=campaign.store.root,
        )
        campaign.config = fresh.config
        campaign.state = fresh.state
        validate_operation(campaign)
        current = campaign.state["lifecycle"]["state"]
        if value == "run" and current in {"paused", "stopped"} and not resume:
            raise RuntimeError(
                f"campaign is {current}; use `opti-loop resume` to clear the owner request"
            )
        campaign.state["lifecycle"] = {
            "schema_version": LIFECYCLE_VERSION,
            "state": {"run": "running", "pause": "paused", "stop": "stopped"}[value],
            "request": value,
        }
        campaign.save_state()
    return copy.deepcopy(campaign.state["lifecycle"])


def note_attempt(campaign: Campaign) -> None:
    pending = campaign.state.get("pending_iteration")
    if campaign.state.get("active_attempt_iteration") == pending and pending:
        require_transition(campaign, action="resume_attempt")
        return
    require_transition(campaign, action="attempt")
    campaign.state["operation_attempts"] += 1
    campaign.state["active_attempt_iteration"] = pending
    campaign.state["lifecycle"] = {
        "schema_version": LIFECYCLE_VERSION,
        "state": "running",
        "request": "run",
    }
    campaign.save_state()


def accepted_ref_status(campaign: Campaign) -> dict[str, Any]:
    ref = f"refs/opti/{campaign.campaign_id}/accepted"
    try:
        observed = gitutil.try_rev_parse(campaign.repo_root, ref)
    except gitutil.GitError as exc:
        return {"state": campaign.state.get("accepted_base_sha"), "ref": None, "ok": False,
                "error": str(exc)}
    expected = campaign.state.get("accepted_base_sha")
    accepted = campaign.state.get("accepted_iterations")
    ok = observed == expected if accepted else observed in {None, expected}
    return {"state": expected, "ref": observed, "ok": ok}


def status(campaign: Campaign) -> dict[str, Any]:
    # The conductor owns the sole closed publication shape and validator.
    from .conductor import publication_status

    pending = campaign.state.get("pending_iteration")
    action = (
        "resume_attempt"
        if pending and campaign.state.get("active_attempt_iteration") == pending
        else "attempt" if pending else "start"
    )
    operation_errors = blockers(campaign, action=action)
    ref = accepted_ref_status(campaign)
    publication = publication_status(campaign)
    try:
        operation, lifecycle = validate_operation(campaign)
    except ValueError:
        operation, lifecycle = campaign.config.get("operation"), campaign.state.get("lifecycle")
    return {
        "lifecycle": lifecycle,
        "limits": operation,
        "attempts_started": campaign.state.get("operation_attempts"),
        "active_attempt_iteration": campaign.state.get("active_attempt_iteration"),
        "accepted_ref": ref,
        "pending_iteration": campaign.state.get("pending_iteration"),
        "publication": publication,
        "cleanup": campaign.state.get("cleanup_health"),
        "blockers": (
            ["accepted-ref: campaign state and accepted ref differ"]
            if not ref["ok"] else []
        )
        + (
            ["publication: publication record is malformed; inspect retained receipt"]
            if publication["status"] == "malformed" else []
        )
        + operation_errors,
    }
