"""Generality lint: reject benchmark-specific knowledge in harness changes.

ADR-0015 §5.2. The real overfitting vector in harness auto-research is
task-specific knowledge smuggled into diffs, skills, or memory. This lint
scans the optimizer's changed files for:

- exact task IDs from the evaluation catalog;
- benchmark-family tokens (source names and their obvious variants);
- benchmark host URL fragments recorded in the task catalog.

Findings are E0 failures. The lint reads the catalog at runtime, so it stays
current as suites evolve, and it never needs benchmark names hard-coded here.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

CATALOG_RELPATH = "evals/catalog/tasks.jsonl"

# Generic hosts that appear in benchmark URLs but are not benchmark-identifying.
_HOST_STOPLIST = {"localhost", "127.0.0.1", "github.com", "example.com"}


@dataclass(slots=True)
class LintFinding:
    path: str
    line: int
    kind: str  # task_id | source_token | benchmark_host
    token: str
    excerpt: str


@dataclass(slots=True)
class LintReport:
    findings: list[LintFinding] = field(default_factory=list)
    scanned_files: int = 0

    @property
    def ok(self) -> bool:
        return not self.findings


def _catalog_rows(repo_root: Path) -> list[dict]:
    path = repo_root / CATALOG_RELPATH
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def build_vocabulary(repo_root: Path) -> dict[str, set[str]]:
    """Derive forbidden tokens from the task catalog itself."""
    task_ids: set[str] = set()
    sources: set[str] = set()
    hosts: set[str] = set()
    for row in _catalog_rows(repo_root):
        task_ids.add(str(row["id"]))
        source = str(row.get("source", ""))
        if source:
            sources.add(source)
            sources.add(source.replace("_", "-"))
            sources.add(source.replace("_", ""))
        locator = row.get("upstream", {}) or {}
        for value in _iter_strings(locator):
            if value.startswith(("http://", "https://")):
                host = urlparse(value).hostname or ""
                if host and host not in _HOST_STOPLIST:
                    hosts.add(host)
    return {"task_ids": task_ids, "sources": sources, "hosts": hosts}


def _iter_strings(value: object):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _iter_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_strings(item)


def scan_files(
    repo_root: Path,
    files: list[str],
    *,
    vocabulary: dict[str, set[str]] | None = None,
) -> LintReport:
    vocab = vocabulary or build_vocabulary(repo_root)
    report = LintReport()
    source_patterns = [
        (token, re.compile(re.escape(token), re.IGNORECASE))
        for token in sorted(vocab["sources"])
        if len(token) >= 4
    ]
    for relpath in files:
        path = repo_root / relpath
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        report.scanned_files += 1
        for lineno, line in enumerate(text.splitlines(), start=1):
            for task_id in vocab["task_ids"]:
                if task_id in line:
                    report.findings.append(
                        LintFinding(relpath, lineno, "task_id", task_id, line.strip()[:160])
                    )
            for token, pattern in source_patterns:
                if pattern.search(line):
                    report.findings.append(
                        LintFinding(relpath, lineno, "source_token", token, line.strip()[:160])
                    )
            for host in vocab["hosts"]:
                if host in line:
                    report.findings.append(
                        LintFinding(relpath, lineno, "benchmark_host", host, line.strip()[:160])
                    )
    return report
