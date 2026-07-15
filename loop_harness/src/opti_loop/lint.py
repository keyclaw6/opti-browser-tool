"""Generality lint: a literal-and-decoded benchmark-token DENYLIST.

Honest framing (F08): this is **not** a generality proof. It is a denylist
that raises the cost of smuggling benchmark-specific knowledge into shipping
harness components. The decisive anti-overfitting control is unseen-site /
unseen-layout transfer evaluation (the transfer checkpoints, ADR-0004/ADR-0015
and the transfer module), never this lint.

Improvements over the diff-only v1 the review defeated:

- **Whole candidate tree** is scanned (``scan_tree``), not only the diff, so a
  benchmark token planted in a file the diff didn't touch is still caught.
- **Non-scannable payloads are rejected, not skipped**: symlinks, non-regular
  files, and binary/undecodable files under the component tree are E0
  findings (a file the lint cannot read cannot be certified).
- **Decode heuristics** catch base64-encoded and split-string-reconstructed
  task IDs and hosts that the literal scan missed.

Known residual escapes (documented, not claimed closed): paraphrase, novel
site-specific selectors/logic keyed on page structure, and semantic hints.
Those are why transfer evaluation is the real control.
"""
from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

CATALOG_RELPATH = "evals/catalog/tasks.jsonl"
_HOST_STOPLIST = {"localhost", "127.0.0.1", "github.com", "example.com"}
_B64_RE = re.compile(r"[A-Za-z0-9+/]{16,}={0,2}")
# Punctuation used to break a literal token across string fragments.
_COLLAPSE = str.maketrans("", "", " \t'\"+,()[]{}\\`")


@dataclass(slots=True)
class LintFinding:
    path: str
    line: int
    kind: str  # task_id | source_token | benchmark_host | encoded_token | split_string | non_regular_file | binary_payload
    token: str
    excerpt: str

    def to_dict(self) -> dict:
        return {"path": self.path, "line": self.line, "kind": self.kind, "token": self.token}


@dataclass(slots=True)
class LintReport:
    findings: list[LintFinding] = field(default_factory=list)
    scanned_files: int = 0

    @property
    def ok(self) -> bool:
        return not self.findings


def _catalog_rows(repo_root: Path) -> list[dict]:
    path = repo_root / CATALOG_RELPATH
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _iter_strings(value: object):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _iter_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_strings(item)


def build_vocabulary(repo_root: Path) -> dict[str, set[str]]:
    task_ids: set[str] = set()
    sources: set[str] = set()
    hosts: set[str] = set()
    for row in _catalog_rows(repo_root):
        task_ids.add(str(row["id"]))
        source = str(row.get("source", ""))
        if source:
            sources.update({source, source.replace("_", "-"), source.replace("_", "")})
        for value in _iter_strings(row.get("upstream", {}) or {}):
            if value.startswith(("http://", "https://")):
                host = urlparse(value).hostname or ""
                if host and host not in _HOST_STOPLIST:
                    hosts.add(host)
    return {"task_ids": task_ids, "sources": sources, "hosts": hosts}


def _scan_text(relpath: str, text: str, vocab: dict[str, set[str]], source_patterns) -> list[LintFinding]:
    findings: list[LintFinding] = []
    ids = vocab["task_ids"]
    hosts = vocab["hosts"]
    for lineno, line in enumerate(text.splitlines(), start=1):
        excerpt = line.strip()[:160]
        for task_id in ids:
            if task_id in line:
                findings.append(LintFinding(relpath, lineno, "task_id", task_id, excerpt))
        for token, pattern in source_patterns:
            if pattern.search(line):
                findings.append(LintFinding(relpath, lineno, "source_token", token, excerpt))
        for host in hosts:
            if host in line:
                findings.append(LintFinding(relpath, lineno, "benchmark_host", host, excerpt))
        # split-string reconstruction: collapse quoting/concat punctuation.
        collapsed = line.translate(_COLLAPSE)
        if collapsed != line:
            for task_id in ids:
                if task_id in collapsed and task_id not in line:
                    findings.append(LintFinding(relpath, lineno, "split_string", task_id, excerpt))
        # base64-encoded tokens.
        for blob in _B64_RE.findall(line):
            try:
                decoded = base64.b64decode(blob, validate=True).decode("utf-8", "ignore")
            except (ValueError, UnicodeDecodeError):
                continue
            for task_id in ids:
                if task_id in decoded:
                    findings.append(LintFinding(relpath, lineno, "encoded_token", task_id, excerpt))
            for host in hosts:
                if host in decoded:
                    findings.append(LintFinding(relpath, lineno, "encoded_token", host, excerpt))
    return findings


def _source_patterns(vocab):
    return [
        (token, re.compile(re.escape(token), re.IGNORECASE))
        for token in sorted(vocab["sources"])
        if len(token) >= 4
    ]


def scan_files(repo_root: Path, files: list[str], *, vocabulary: dict[str, set[str]] | None = None) -> LintReport:
    """Scan an explicit list of repo-relative files (used by the diff path/tests)."""
    vocab = vocabulary or build_vocabulary(repo_root)
    patterns = _source_patterns(vocab)
    report = LintReport()
    for relpath in files:
        path = repo_root / relpath
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            report.findings.append(LintFinding(relpath, 0, "binary_payload", "", ""))
            continue
        report.scanned_files += 1
        report.findings.extend(_scan_text(relpath, text, vocab, patterns))
    return report


def scan_tree(
    worktree: Path,
    *,
    allowed_prefixes: tuple[str, ...],
    vocabulary: dict[str, set[str]] | None = None,
) -> LintReport:
    """Scan every file under the frozen candidate-owned boundary."""
    vocab = vocabulary or build_vocabulary(worktree)
    patterns = _source_patterns(vocab)
    report = LintReport()
    for prefix in allowed_prefixes:
        root = worktree / prefix.rstrip("/")
        if root.is_symlink() or not root.is_dir():
            report.findings.append(
                LintFinding(prefix.rstrip("/"), 0, "non_regular_file", "", "")
            )
            continue
        for path in sorted(root.rglob("*")):
            rel = path.relative_to(worktree).as_posix()
            if path.is_symlink() or (path.exists() and not (path.is_file() or path.is_dir())):
                report.findings.append(LintFinding(rel, 0, "non_regular_file", "", ""))
                continue
            if not path.is_file():
                continue
            raw = path.read_bytes()
            if b"\x00" in raw:
                report.findings.append(LintFinding(rel, 0, "binary_payload", "", ""))
                continue
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                report.findings.append(LintFinding(rel, 0, "binary_payload", "", ""))
                continue
            report.scanned_files += 1
            report.findings.extend(_scan_text(rel, text, vocab, patterns))
    return report
