"""Materialize offline investigation workspaces used by demo/validate/tests."""

from __future__ import annotations

import shutil
from pathlib import Path

FIXTURES = {
    "cache_miss": "cache_miss",
    "session_ttl": "session_ttl",
}


def fixtures_dir() -> Path:
    return Path(__file__).resolve().parent / "fixtures"


def fixture_root(name: str = "cache_miss") -> Path:
    if name not in FIXTURES:
        raise KeyError(f"Unknown fixture {name!r}; known: {sorted(FIXTURES)}")
    return fixtures_dir() / FIXTURES[name]


def materialize_fixture(name: str, dest: Path) -> Path:
    """Copy a named fixture into ``dest`` and return that workspace root."""
    src = fixture_root(name)
    if not src.is_dir():
        raise FileNotFoundError(f"Fixture missing at {src}")
    dest = dest.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    for path in src.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(src)
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    return dest


def materialize_cache_miss(dest: Path) -> Path:
    return materialize_fixture("cache_miss", dest)


def materialize_session_ttl(dest: Path) -> Path:
    return materialize_fixture("session_ttl", dest)


def cache_miss_issue(workspace: Path) -> Path:
    return workspace / "issues" / "001-cache-miss.md"


def session_ttl_issue(workspace: Path) -> Path:
    return workspace / "issues" / "001-session-ttl.md"
