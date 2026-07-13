"""opti-judge CLI — evaluation-plane judge operations.

    opti-judge t1 --trace T.jsonl --status passed [--expect-side-effects none]
                  [--assertions A.json] [--task-id id] [--run-ref ref]
                  [--queue runs/quarantine/queue.jsonl]   # route disagreements
    opti-judge probe --verifier-id v1 --command "..." --task-id t --kit DIR
                  [--checksum-file F ...] [--archive DIR]
    opti-judge quarantine list|resolve --queue FILE [--entry-id ID]
                  [--resolution R --note "..."] [--corpus FILE]
    opti-judge corpus stats|measure --corpus FILE [--judge-id ID] [--positive failure]
    opti-judge panel --role R --trace T.jsonl --goal "..." --status failed
                  [--corpus FILE]

Environment: OPTI_BROWSER_REPO_ROOT (or --repo-root) for role definitions.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .corpus import CorpusStore
from .evidence import EvidenceContract, EvidenceError, load_trace
from .panel import adjudicate, run_role
from .probekit import ProbeCase, run_probe_kit
from .quarantine import QuarantineQueue
from .router import route
from .t1_checks import run_all

T1_CONTRACT = EvidenceContract(role="t1", visibility=("executor", "judge", "orchestrator"))


def _emit(payload) -> None:
    print(json.dumps(payload, indent=2, default=str))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="opti-judge", description=__doc__)
    parser.add_argument("--repo-root", default=None)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_t1 = sub.add_parser("t1", help="deterministic cross-checks over a trace")
    p_t1.add_argument("--trace", required=True)
    p_t1.add_argument("--status", required=True, choices=["passed", "failed", "invalid", "error", "skipped"])
    p_t1.add_argument("--expect-side-effects", default="unknown", choices=["none", "some", "unknown"])
    p_t1.add_argument("--assertions", default=None, help="JSON file with expected-state assertions")
    p_t1.add_argument("--task-id", default=None)
    p_t1.add_argument("--run-ref", default=None)
    p_t1.add_argument("--queue", default=None, help="quarantine queue file; enables routing")

    p_probe = sub.add_parser("probe", help="run a verifier through the admission probe kit")
    p_probe.add_argument("--verifier-id", required=True)
    p_probe.add_argument("--command", required=True)
    p_probe.add_argument("--task-id", required=True)
    p_probe.add_argument("--kit", required=True, help="directory of <kind>.trace.jsonl / <kind>.task.json pairs")
    p_probe.add_argument("--checksum-file", action="append", default=[])
    p_probe.add_argument("--archive", default=None)

    p_q = sub.add_parser("quarantine")
    p_q.add_argument("action", choices=["list", "resolve"])
    p_q.add_argument("--queue", required=True)
    p_q.add_argument("--entry-id", default=None)
    p_q.add_argument("--resolution", default=None)
    p_q.add_argument("--note", default="")
    p_q.add_argument("--corpus", default=None)

    p_c = sub.add_parser("corpus")
    p_c.add_argument("action", choices=["stats", "measure"])
    p_c.add_argument("--corpus", required=True)
    p_c.add_argument("--judge-id", default=None)
    p_c.add_argument("--positive", default="failure")

    p_panel = sub.add_parser("panel", help="run one T2 role over a trace (non-scoring)")
    p_panel.add_argument("--role", required=True)
    p_panel.add_argument("--trace", required=True)
    p_panel.add_argument("--goal", required=True)
    p_panel.add_argument("--status", required=True)
    p_panel.add_argument("--corpus", default=None)

    args = parser.parse_args(argv)

    if args.cmd == "t1":
        try:
            trace = load_trace(Path(args.trace), T1_CONTRACT)
        except EvidenceError as exc:
            _emit({"result": "invalid", "reason": str(exc)})
            return 3
        assertions = (
            json.loads(Path(args.assertions).read_text(encoding="utf-8"))
            if args.assertions
            else []
        )
        flags = run_all(
            trace,
            verifier_status=args.status,
            side_effect_expectation=args.expect_side_effects,
            assertions=assertions,
        )
        output = {"flags": [f.to_dict() for f in flags]}
        if args.queue and args.task_id:
            queue = QuarantineQueue(Path(args.queue))
            output["routing"] = route(
                queue=queue,
                task_id=args.task_id,
                run_ref=args.run_ref or args.trace,
                verifier_status=args.status,
                t1_flags=flags,
            )
        _emit(output)
        return 0

    if args.cmd == "probe":
        kit_dir = Path(args.kit)
        cases = []
        for trace_file in sorted(kit_dir.glob("*.trace.jsonl")):
            kind = trace_file.name.replace(".trace.jsonl", "")
            task_file = kit_dir / f"{kind}.task.json"
            cases.append(ProbeCase(kind=kind, trace_path=trace_file, task_path=task_file))
        record = run_probe_kit(
            verifier_id=args.verifier_id,
            verifier_command=args.command,
            task_id=args.task_id,
            cases=cases,
            checksum_files=[Path(p) for p in args.checksum_file],
            archive_dir=Path(args.archive) if args.archive else None,
        )
        _emit(record.to_dict())
        return 0 if record.admitted else 1

    if args.cmd == "quarantine":
        queue = QuarantineQueue(Path(args.queue))
        if args.action == "list":
            _emit([e.to_dict() for e in queue.pending()])
            return 0
        if not args.entry_id or not args.resolution:
            print("resolve needs --entry-id and --resolution", file=sys.stderr)
            return 2
        corpus = CorpusStore(Path(args.corpus)) if args.corpus else None
        entry = queue.resolve(
            args.entry_id, resolution=args.resolution, note=args.note, corpus=corpus
        )
        _emit(entry.to_dict())
        return 0

    if args.cmd == "corpus":
        store = CorpusStore(Path(args.corpus))
        if args.action == "stats":
            _emit(store.stats())
            return 0
        if not args.judge_id:
            print("measure needs --judge-id", file=sys.stderr)
            return 2
        _emit(store.measure(args.judge_id, positive=args.positive))
        return 0

    if args.cmd == "panel":
        repo_root = Path(
            args.repo_root or os.environ.get("OPTI_BROWSER_REPO_ROOT", ".")
        ).resolve()
        corpus = CorpusStore(Path(args.corpus)) if args.corpus else None
        judgment = run_role(
            repo_root=repo_root,
            role_id=args.role,
            trace_path=Path(args.trace),
            goal=args.goal,
            verifier_status=args.status,
            corpus=corpus,
        )
        verdict = adjudicate(
            verifier_status=args.status, judgments=[judgment], t1_flags=[]
        )
        _emit({"judgment": judgment.to_dict(), "adjudication": verdict})
        return 0

    parser.error(f"unknown command {args.cmd}")
    return 2
