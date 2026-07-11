#!/usr/bin/env python3
"""Example external bridge that deterministically passes or fails one task.

This does not launch a browser. It exists only to verify the command-adapter
contract end to end.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-json", required=True)
    parser.add_argument("--result-json", required=True)
    parser.add_argument("--pass-rate", type=float, default=0.5)
    args = parser.parse_args()

    task = json.loads(Path(args.task_json).read_text(encoding="utf-8"))
    task_id = task["id"]
    value = int.from_bytes(hashlib.sha256(task_id.encode()).digest(), "big") / 2**256
    passed = value < args.pass_rate
    result = {
        "task_id": task_id,
        "status": "passed" if passed else "failed",
        "reward": 1.0 if passed else 0.0,
        "verifier": {
            "kind": "example_fixture_bridge",
            "valid": True,
            "detail": "Synthetic bridge used only to test the external command contract."
        },
        "metadata": {"synthetic": True, "benchmark_reportable": False}
    }
    Path(args.result_json).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
