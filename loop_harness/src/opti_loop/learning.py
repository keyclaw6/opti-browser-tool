"""Canonical trace-cited learning records for the next optimizer packet."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any

from opti_eval.identity import digest_json

from .store import atomic_write_text

SCHEMA_VERSION = "0.1.0"
RECORD_TYPE = "learning-record"
FIELDS = {
    "schema_version", "record_type", "campaign_id", "iteration", "base_sha",
    "candidate_sha", "protocol_digest", "decision", "hypothesis",
    "target_component", "cluster_ref", "source_disposition", "citations",
    "summary", "record_digest",
}
CITATION_FIELDS = {"path", "sha256", "kind"}
DECISION_FIELDS = {"label", "decision", "evidence_class", "advances_accepted_state"}
DISPOSITION_FIELDS = {"sources", "executed"}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _safe_evidence(root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or pure.as_posix() != relative or any(
        part in {"", ".", ".."} for part in pure.parts
    ):
        raise ValueError("learning citation path must be safe campaign-relative POSIX")
    current = root
    for part in pure.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"learning citation redirects through a symlink: {relative}")
    resolved = current.resolve(strict=True)
    if not resolved.is_file() or not resolved.is_relative_to(root.resolve(strict=True)):
        raise ValueError(f"learning citation escapes retained campaign evidence: {relative}")
    return resolved


def _citation(root: Path, path: Path, kind: str) -> dict[str, str]:
    relative = path.relative_to(root).as_posix()
    trusted = _safe_evidence(root, relative)
    return {"path": relative, "sha256": _sha(trusted.read_bytes()), "kind": kind}


def _trusted_execution(gate: object) -> bool:
    """Use only conductor-retained run identity, never file presence."""
    if type(gate) is not dict:
        return False
    run_digests = gate.get("run_digests")
    if type(run_digests) is not dict:
        return False
    return any(
        type(name) is str
        and type(digest) is str
        and len(digest) == 64
        and all(char in "0123456789abcdef" for char in digest)
        for name, digest in run_digests.items()
    )


def build_record(
    *,
    campaign_root: Path,
    campaign_id: str,
    iteration: int,
    base_sha: str,
    candidate_sha: str | None,
    protocol_digest: str,
    verdict: dict[str, Any],
    manifest: dict[str, Any],
    gate_report: dict[str, Any],
) -> dict[str, Any]:
    iteration_dir = campaign_root / "iterations" / f"iter-{iteration:04d}"
    gate_relative = f"iterations/iter-{iteration:04d}/gate-report.json"
    gate_sha = _sha(_json_bytes(gate_report))
    citations: list[dict[str, str]] = [
        {"path": gate_relative, "sha256": gate_sha, "kind": "gate"}
    ]
    traces = sorted((iteration_dir / "eval").glob("**/tasks/*/trace.jsonl"))
    executed = _trusted_execution(gate_report)
    # Invalid means evidence admission or integrity failed. Preserve the trusted
    # gate disposition, but never cite the trace/result bytes it rejected.
    if executed and traces and verdict["decision"] != "invalid":
        citations.append(_citation(campaign_root, traces[-1], "trace"))
        result = traces[-1].parent / "result.json"
        if result.is_file():
            citations.append(_citation(campaign_root, result, "artifact"))
    rungs = gate_report.get("rungs")
    last = rungs[-1] if type(rungs) is list and rungs else {}
    detail = last.get("detail") if type(last) is dict else None
    reason = detail.get("reason") if type(detail) is dict else None
    summary = reason if type(reason) is str and reason else (
        f"{last.get('rung', 'gate')}:{last.get('status', verdict.get('label'))}"
    )
    try:
        protocol = json.loads(
            (iteration_dir / "protocol.snapshot.json").read_text(encoding="utf-8")
        )
        sources = sorted({
            task["source"]
            for suite in protocol["suites"]
            for task in suite["tasks"]
        })
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise ValueError("LearningRecord cannot resolve frozen source disposition") from exc
    record = {
        "schema_version": SCHEMA_VERSION,
        "record_type": RECORD_TYPE,
        "campaign_id": campaign_id,
        "iteration": iteration,
        "base_sha": base_sha,
        "candidate_sha": candidate_sha,
        "protocol_digest": protocol_digest,
        "decision": copy.deepcopy(verdict),
        "hypothesis": str(manifest.get("hypothesis", "")),
        "target_component": str(manifest.get("target_component", "")),
        "cluster_ref": str(manifest.get("cluster_ref", "")),
        "source_disposition": {
            "sources": sources,
            "executed": executed,
        },
        "citations": citations,
        "summary": summary,
    }
    record["record_digest"] = digest_json(record, domain="opti.learning-record.v1")
    validate_record(record, campaign_root=campaign_root, pending_gate=gate_report)
    return record


def validate_record(
    record: object,
    *,
    campaign_root: Path,
    pending_gate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if type(record) is not dict or set(record) != FIELDS:
        raise ValueError("LearningRecord has an invalid closed shape")
    if record["schema_version"] != SCHEMA_VERSION or record["record_type"] != RECORD_TYPE:
        raise ValueError("LearningRecord schema/type is invalid")
    if type(record["campaign_id"]) is not str or not record["campaign_id"]:
        raise ValueError("LearningRecord campaign identity is invalid")
    if type(record["iteration"]) is not int or record["iteration"] < 1:
        raise ValueError("LearningRecord iteration is invalid")
    base = record["base_sha"]
    if type(base) is not str or len(base) not in {40, 64} or any(
        char not in "0123456789abcdef" for char in base
    ):
        raise ValueError("LearningRecord base_sha is invalid")
    protocol_digest = record["protocol_digest"]
    if type(protocol_digest) is not str or len(protocol_digest) != 64 or any(
        char not in "0123456789abcdef" for char in protocol_digest
    ):
        raise ValueError("LearningRecord protocol_digest is invalid")
    candidate = record["candidate_sha"]
    if candidate is not None and (type(candidate) is not str or len(candidate) not in {40, 64}):
        raise ValueError("LearningRecord candidate_sha is invalid")
    decision = record["decision"]
    if type(decision) is not dict or set(decision) != DECISION_FIELDS:
        raise ValueError("LearningRecord decision is invalid")
    if (
        decision["decision"] not in {"accepted", "rejected", "inconclusive", "invalid"}
        or decision["evidence_class"] not in {"benchmark", "simulated"}
        or type(decision["advances_accepted_state"]) is not bool
    ):
        raise ValueError("LearningRecord decision values are invalid")
    expected_label = (
        ("simulated:" if decision["evidence_class"] == "simulated" else "")
        + decision["decision"]
    )
    expected_advance = (
        decision["decision"] == "accepted"
        and decision["evidence_class"] == "benchmark"
    )
    if (
        decision["label"] != expected_label
        or decision["advances_accepted_state"] is not expected_advance
        or expected_advance and candidate is None
    ):
        raise ValueError("LearningRecord decision identity is inconsistent")
    disposition = record["source_disposition"]
    if type(disposition) is not dict or set(disposition) != DISPOSITION_FIELDS:
        raise ValueError("LearningRecord source disposition is invalid")
    if (
        type(disposition["sources"]) is not list
        or not disposition["sources"]
        or disposition["sources"] != sorted(set(disposition["sources"]))
        or any(type(source) is not str or not source for source in disposition["sources"])
        or type(disposition["executed"]) is not bool
    ):
        raise ValueError("LearningRecord source disposition values are invalid")
    citations = record["citations"]
    if type(citations) is not list or not citations:
        raise ValueError("LearningRecord requires retained evidence citations")
    seen: set[str] = set()
    gate_paths: list[str] = []
    cited_gate: object = None
    for citation in citations:
        if type(citation) is not dict or set(citation) != CITATION_FIELDS:
            raise ValueError("LearningRecord citation has an invalid closed shape")
        path = citation["path"]
        if type(path) is not str or path in seen:
            raise ValueError("LearningRecord citations must have unique paths")
        seen.add(path)
        if citation["kind"] not in {"gate", "trace", "artifact"}:
            raise ValueError("LearningRecord citation kind is invalid")
        if citation["kind"] == "gate":
            gate_paths.append(path)
        expected = citation["sha256"]
        if type(expected) is not str or len(expected) != 64:
            raise ValueError("LearningRecord citation checksum is invalid")
        candidate_path = campaign_root / path
        if citation["kind"] == "gate" and pending_gate is not None:
            raw = _json_bytes(pending_gate)
            actual = _sha(raw)
            cited_gate = pending_gate
        elif candidate_path.is_file():
            raw = _safe_evidence(campaign_root, path).read_bytes()
            actual = _sha(raw)
            if citation["kind"] == "gate":
                try:
                    cited_gate = json.loads(raw)
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise ValueError("LearningRecord gate citation is invalid JSON") from exc
        else:
            raise ValueError(f"LearningRecord citation is missing: {path}")
        if actual != expected:
            raise ValueError(f"LearningRecord citation checksum mismatch: {path}")
    expected_gate = f"iterations/iter-{record['iteration']:04d}/gate-report.json"
    if gate_paths != [expected_gate]:
        raise ValueError("LearningRecord must cite its exact gate report once")
    if disposition["executed"] is not _trusted_execution(cited_gate):
        raise ValueError("LearningRecord execution disposition conflicts with trusted gate")
    has_trace = any(citation["kind"] == "trace" for citation in citations)
    has_result_artifact = any(citation["kind"] == "artifact" for citation in citations)
    if decision["decision"] == "invalid" and (has_trace or has_result_artifact):
        raise ValueError("invalid LearningRecord cannot cite ineligible execution evidence")
    if has_trace and not disposition["executed"]:
        raise ValueError("LearningRecord trace citation lacks trusted gate execution")
    unsigned = {key: value for key, value in record.items() if key != "record_digest"}
    if record["record_digest"] != digest_json(unsigned, domain="opti.learning-record.v1"):
        raise ValueError("LearningRecord digest is invalid")
    return record


def read_records(path: Path, *, campaign_root: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError as exc:
            raise ValueError(f"LearningRecord row {index + 1} is not JSON") from exc
        records.append(validate_record(row, campaign_root=campaign_root))
    return records


def ensure_record(path: Path, record: dict[str, Any], *, campaign_root: Path) -> None:
    validate_record(record, campaign_root=campaign_root)
    records = read_records(path, campaign_root=campaign_root)
    matches = [row for row in records if row["iteration"] == record["iteration"]]
    if matches:
        if matches != [record]:
            raise RuntimeError("trusted learning store has a different iteration record")
        return
    records.append(copy.deepcopy(record))
    atomic_write_text(
        path, "".join(json.dumps(row, sort_keys=True) + "\n" for row in records)
    )
