from __future__ import annotations

import os
from pathlib import Path

from .errors import ConfigurationError


def _looks_like_repo(path: Path) -> bool:
    return (path / "evals" / "catalog" / "tasks.jsonl").is_file() and (
        path / "evals" / "suites"
    ).is_dir()


def find_repo_root(explicit: str | Path | None = None) -> Path:
    candidates: list[Path] = []
    if explicit is not None:
        candidates.append(Path(explicit))
    env_root = os.environ.get("OPTI_BROWSER_REPO_ROOT")
    if env_root:
        candidates.append(Path(env_root))
    candidates.extend([Path.cwd(), Path(__file__).resolve()])

    seen: set[Path] = set()
    for candidate in candidates:
        candidate = candidate.expanduser().resolve()
        starts = [candidate] if candidate.is_dir() else [candidate.parent]
        for start in starts:
            for path in (start, *start.parents):
                if path in seen:
                    continue
                seen.add(path)
                if _looks_like_repo(path):
                    return path
    raise ConfigurationError(
        "Could not locate repository root. Run inside the repository, pass --repo-root, "
        "or set OPTI_BROWSER_REPO_ROOT."
    )
