"""Git file guard: the optimizer's writable surface, mechanically enforced.

Adapted from neosigmaai/auto-harness ``gating.py`` (diff-index + untracked
scan minus allowlist), with two changes for this project:

- the allowlist is a set of directory prefixes (the harness component tree),
  not individual files;
- there is no configuration switch to disable the guard. ADR-0015 treats the
  guard as containment, not convenience; a run without a working git repo is
  a guard failure, not a degraded mode.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

# The only tracked surface the optimizer may modify (ADR-0015 §5, PROGRAM.md §2).
ALLOWED_PREFIXES: tuple[str, ...] = ("harness/components/",)


class GuardError(RuntimeError):
    """Raised when the guard itself cannot run (git missing / not a repo)."""


def _git_lines(repo_root: Path, *args: str) -> list[str]:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(repo_root), *args],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError as exc:  # git binary missing
        raise GuardError("`git` is not installed or not on PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise GuardError(f"git {' '.join(args)} failed in {repo_root}") from exc
    return [line for line in out.strip().splitlines() if line]


def changed_paths(repo_root: Path) -> list[str]:
    """Tracked modifications plus non-ignored new files, repo-relative."""
    _git_lines(repo_root, "rev-parse", "--is-inside-work-tree")
    paths: set[str] = set()
    paths.update(_git_lines(repo_root, "diff-index", "--name-only", "HEAD"))
    paths.update(_git_lines(repo_root, "ls-files", "--others", "--exclude-standard"))
    return sorted(paths)


def is_allowed(path: str, allowed_prefixes: tuple[str, ...] = ALLOWED_PREFIXES) -> bool:
    return any(path.startswith(prefix) for prefix in allowed_prefixes)


@dataclass(slots=True)
class GuardReport:
    changed: list[str]
    violations: list[str]

    @property
    def ok(self) -> bool:
        return not self.violations


def check(
    repo_root: Path,
    *,
    allowed_prefixes: tuple[str, ...] = ALLOWED_PREFIXES,
    baseline_paths: set[str] | None = None,
) -> GuardReport:
    """Compare the working tree against the allowlist.

    ``baseline_paths``: paths already dirty when the iteration started
    (for example this repository's own in-review documentation edits).
    They are excluded from the verdict but still listed in ``changed`` so
    the gate report shows the whole picture.
    """
    changed = changed_paths(repo_root)
    baseline = baseline_paths or set()
    violations = [
        path
        for path in changed
        if path not in baseline and not is_allowed(path, allowed_prefixes)
    ]
    return GuardReport(changed=changed, violations=violations)
