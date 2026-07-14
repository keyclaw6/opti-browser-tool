from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .adapters.command import CommandAdapter
from .adapters.fixture import FixtureAdapter
from .adapters.registry import RegistryAdapter
from .catalog import load_catalog, load_suite, select_tasks
from .doctor import inspect_registry
from .errors import OptiEvalError
from .paths import find_repo_root
from .runner import run_evaluation
from .summary import load_run_summary
from .validation import validate_repository


def _json_print(value: Any) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False))


def _add_root_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo-root", help="Path to the Opti Browser Tool repository")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="opti-eval")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="Validate catalog, manifests, and provenance")
    _add_root_argument(validate)
    validate.add_argument("--json", action="store_true", dest="as_json")

    list_cmd = sub.add_parser("list", help="List tasks from a suite")
    _add_root_argument(list_cmd)
    list_cmd.add_argument("--suite", default="primary")
    list_cmd.add_argument("--source")
    list_cmd.add_argument("--limit", type=int)
    list_cmd.add_argument("--jsonl", action="store_true")

    doctor = sub.add_parser("doctor", help="Inspect a source bridge registry")
    _add_root_argument(doctor)
    doctor.add_argument("--config", required=True)

    run = sub.add_parser("run", help="Run a suite through an execution adapter")
    _add_root_argument(run)
    run.add_argument("--suite", default="primary")
    run.add_argument("--source")
    run.add_argument("--task-id", action="append", default=[])
    run.add_argument("--limit", type=int)
    run.add_argument("--adapter", choices=["fixture", "command", "registry"], required=True)
    run.add_argument("--command", dest="bridge_command")
    run.add_argument("--config")
    run.add_argument("--timeout-seconds", type=int, default=900)
    run.add_argument("--fixture-pass-rate", type=float, default=0.55)
    run.add_argument("--fixture-seed", type=int, default=0)
    run.add_argument("--max-workers", type=int, default=1)
    run.add_argument("--output", required=True)
    run.add_argument("--overwrite", action="store_true")

    summarize = sub.add_parser("summarize", help="Print a prior run summary")
    summarize.add_argument("run_dir")
    return parser


def _make_adapter(args: argparse.Namespace, repo_root: Path):
    if args.adapter == "fixture":
        return FixtureAdapter(args.fixture_pass_rate, args.fixture_seed)
    if args.adapter == "command":
        if not args.bridge_command:
            raise OptiEvalError("--command is required for the command adapter")
        return CommandAdapter(args.bridge_command, timeout_seconds=args.timeout_seconds)
    if args.adapter == "registry":
        if not args.config:
            raise OptiEvalError("--config is required for the registry adapter")
        config_path = Path(args.config)
        if not config_path.is_absolute():
            config_path = repo_root / config_path
        return RegistryAdapter(config_path.resolve())
    raise OptiEvalError(f"Unsupported adapter: {args.adapter}")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "summarize":
            _json_print(load_run_summary(Path(args.run_dir)))
            return 0

        repo_root = find_repo_root(args.repo_root)
        if args.command == "validate":
            report = validate_repository(repo_root)
            if args.as_json:
                _json_print(report)
            else:
                print(f"Repository: {report['repo_root']}")
                print(f"Candidates/catalog: {report['candidate_count']}/{report['catalog_count']}")
                print(f"Primary/smoke/regression: {report['primary_count']}/{report['smoke_count']}/{report['regression_count']}")
                print("Sources:")
                for source, count in report["source_counts"].items():
                    print(f"  {source}: {count}")
                for warning in report["warnings"]:
                    print(f"WARNING: {warning}", file=sys.stderr)
                if report["errors"]:
                    for error in report["errors"]:
                        print(f"ERROR: {error}", file=sys.stderr)
                else:
                    print("Validation: PASS")
            return 0 if report["ok"] else 1

        if args.command == "list":
            _, tasks = select_tasks(
                repo_root,
                args.suite,
                source=args.source,
                limit=args.limit,
            )
            if args.jsonl:
                for task in tasks:
                    print(json.dumps(task, ensure_ascii=False))
            else:
                for task in tasks:
                    print(
                        f"{task['id']}\t{task['source']}\t{task['site']}\t{task['goal']}"
                    )
                print(f"Total: {len(tasks)}", file=sys.stderr)
            return 0

        if args.command == "doctor":
            config_path = Path(args.config)
            if not config_path.is_absolute():
                config_path = repo_root / config_path
            report = inspect_registry(config_path.resolve())
            _json_print(report)
            return 0 if report["ok"] else 1

        if args.command == "run":
            suite, tasks = select_tasks(
                repo_root,
                args.suite,
                source=args.source,
                task_ids=args.task_id,
                limit=args.limit,
            )
            if not tasks:
                raise OptiEvalError("Task selection is empty")
            adapter = _make_adapter(args, repo_root)
            output = Path(args.output)
            if not output.is_absolute():
                output = repo_root / output
            run_record = run_evaluation(
                repo_root=repo_root,
                suite=suite,
                tasks=tasks,
                adapter=adapter,
                output_dir=output.resolve(),
                max_workers=args.max_workers,
                overwrite=args.overwrite,
            )
            _json_print(run_record["summary"])
            return 0 if run_record["summary"]["run_valid"] else 2

        parser.error("Unknown command")
        return 2
    except (OptiEvalError, ValueError, FileNotFoundError, FileExistsError) as exc:
        print(f"opti-eval: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
