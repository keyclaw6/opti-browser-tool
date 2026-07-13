"""T2 judge panel runner: calibrated flaggers, structurally non-scoring.

Role definitions are versioned JSON assets in ``evals/judges/roles/`` —
pinned like verifiers (ADR-0016 calibration rule 4). This runner:

1. loads a role definition and enforces its evidence contract;
2. assembles the role's inputs (deliberately simple — final observation +
   goal beats captioning pipelines per AgentRewardBench);
3. calls the pinned model through ``llm.call_model``;
4. parses a structured judgment (opinion, confidence, evidence refs,
   rationale — per EVALUATION_PRINCIPLES judges never emit a bare score);
5. wraps it with trust metadata: ``trusted`` is computed from the calibration
   corpus at call time and is ``false`` until the role's operating point is
   met. Untrusted judgments are diagnostic only.

The adjudicator role is deterministic and does not call a model: its tie
rule (unresolved disagreement → quarantine, never averaging) is code, in
``adjudicate``.
"""
from __future__ import annotations

import dataclasses
import datetime as _dt
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .corpus import CorpusStore, OperatingPoint, trusted
from .evidence import EvidenceContract, Trace, load_trace
from .llm import ModelResponse, call_model

ROLES_RELPATH = "evals/judges/roles"
OPINIONS = ("success", "failure", "undecidable")


@dataclass(slots=True)
class Judgment:
    role_id: str
    role_version: str
    opinion: str
    confidence: float
    rationale: str
    evidence_refs: list[str]
    labels: dict[str, Any]
    model: dict[str, Any]
    trusted: bool
    calibration: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "role_id": self.role_id,
            "role_version": self.role_version,
            "opinion": self.opinion,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "evidence_refs": self.evidence_refs,
            "labels": self.labels,
            "model": self.model,
            "trusted": self.trusted,
            "calibration": self.calibration,
            "note": "non-scoring flag; untrusted judgments are diagnostic only",
            "recorded_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        }


def load_role(repo_root: Path, role_id: str) -> dict[str, Any]:
    path = repo_root / ROLES_RELPATH / f"{role_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"no role definition: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _contract(role: dict[str, Any]) -> EvidenceContract:
    contract = role.get("evidence_contract", {})
    return EvidenceContract(
        role=role["role_id"],
        visibility=tuple(contract.get("visibility", ("executor", "judge", "orchestrator"))),
        event_types=tuple(contract.get("event_types", ())),
    )


def _assemble_messages(
    role: dict[str, Any], *, goal: str, trace: Trace, verifier_status: str
) -> tuple[list[dict[str, str]], list[str]]:
    """Simple inputs by design: goal + final observation + action digest."""
    final_obs = trace.final_of_type("browser_state") or trace.final_of_type(
        "model_observation"
    )
    actions = trace.of_type("action_requested")
    action_digest = [
        f"{e.get('payload', {}).get('action')} -> {e.get('payload', {}).get('target')}"
        for e in actions[-30:]
    ]
    refs = []
    if final_obs is not None:
        refs.append(f"{final_obs.get('run_id')}/{final_obs.get('event_id')}")
    evidence_block = {
        "task_goal": goal,
        "verifier_status": verifier_status,
        "final_observation": (final_obs or {}).get("payload", {}),
        "recent_actions": action_digest,
    }
    messages = [
        {"role": "system", "content": role["prompt_template"]},
        {
            "role": "user",
            "content": json.dumps(evidence_block, indent=2, ensure_ascii=False),
        },
    ]
    return messages, refs


def _parse_judgment_text(text: str) -> dict[str, Any]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {"opinion": "undecidable", "confidence": 0.0, "rationale": text[:400]}
    if not isinstance(payload, dict):
        return {"opinion": "undecidable", "confidence": 0.0, "rationale": str(payload)[:400]}
    opinion = str(payload.get("opinion", "undecidable"))
    if opinion not in OPINIONS:
        opinion = "undecidable"
    return {
        "opinion": opinion,
        "confidence": float(payload.get("confidence", 0.0)),
        "rationale": str(payload.get("rationale", ""))[:2000],
        "labels": {
            k: v
            for k, v in payload.items()
            if k not in {"opinion", "confidence", "rationale"}
        },
    }


def run_role(
    *,
    repo_root: Path,
    role_id: str,
    trace_path: Path,
    goal: str,
    verifier_status: str,
    corpus: CorpusStore | None = None,
    model_override: dict[str, Any] | None = None,
) -> Judgment:
    role = load_role(repo_root, role_id)
    if role.get("kind") == "deterministic":
        raise ValueError(
            f"role {role_id} is deterministic (adjudicator); use adjudicate()"
        )
    contract = _contract(role)
    trace = load_trace(trace_path, contract)
    messages, refs = _assemble_messages(
        role, goal=goal, trace=trace, verifier_status=verifier_status
    )
    model_config = model_override or role.get("model", {"provider": "fixture"})
    response: ModelResponse = call_model(messages, model_config)
    parsed = _parse_judgment_text(response.text)

    point = OperatingPoint(
        min_cases=int(role.get("calibration", {}).get("min_cases", 25)),
        min_precision=role.get("calibration", {}).get("min_precision"),
        min_recall=role.get("calibration", {}).get("min_recall"),
    )
    measurement: dict[str, Any] = {"cases_measured": 0}
    if corpus is not None:
        measurement = corpus.measure(
            role_id, positive=str(role.get("calibration", {}).get("positive_class", "failure"))
        )
    is_trusted = trusted(measurement, point)

    return Judgment(
        role_id=role_id,
        role_version=str(role.get("version", "0")),
        opinion=parsed["opinion"],
        confidence=parsed["confidence"],
        rationale=parsed["rationale"],
        evidence_refs=refs,
        labels=parsed.get("labels", {}),
        model=response.to_dict(),
        trusted=is_trusted,
        calibration={"measurement": measurement, "operating_point": dataclasses.asdict(point)},
    )


def adjudicate(
    *, verifier_status: str, judgments: list[Judgment], t1_flags: list[dict[str, Any]]
) -> dict[str, Any]:
    """Deterministic adjudication (the fifth role).

    Tie rule per ADR-0016: any unresolved disagreement quarantines; nothing
    here adjusts a score, and untrusted judgments cannot force agreement —
    they can only *raise* a quarantine, weaker evidence never suppresses
    stronger doubt.
    """
    verifier_opinion = "success" if verifier_status == "passed" else "failure"
    disagreements: list[str] = []
    for judgment in judgments:
        if judgment.opinion == "undecidable":
            continue
        if judgment.opinion != verifier_opinion:
            qualifier = "trusted" if judgment.trusted else "untrusted"
            disagreements.append(
                f"{qualifier} {judgment.role_id} says {judgment.opinion} "
                f"vs verifier {verifier_opinion}"
            )
    suspicion_flags = [f for f in t1_flags if f.get("severity") == "suspicion"]
    if suspicion_flags:
        disagreements.append(
            f"{len(suspicion_flags)} T1 suspicion flag(s): "
            + ", ".join(sorted({f["check"] for f in suspicion_flags}))
        )
    resolution = "quarantine" if disagreements else "agree"
    return {
        "role_id": "adjudicator",
        "kind": "deterministic",
        "resolution": resolution,
        "disagreements": disagreements,
        "note": "unresolved disagreement always quarantines; scores are never adjusted",
    }
