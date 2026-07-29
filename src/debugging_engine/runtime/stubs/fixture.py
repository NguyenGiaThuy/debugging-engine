"""Materialize the offline cache-miss workspace used by demo/validate/tests."""

from __future__ import annotations

import shutil
from pathlib import Path

FIXTURE_NAME = "cache_miss"


def fixture_root() -> Path:
    return Path(__file__).resolve().parent / "fixtures" / FIXTURE_NAME


def materialize_cache_miss(dest: Path) -> Path:
    """
    Copy the cache-miss fixture into ``dest`` and return that workspace root.

    Layout:
      cache.py
      issues/001-cache-miss.md
      tests/test_cache.py
    """
    src = fixture_root()
    if not src.is_dir():
        raise FileNotFoundError(f"Cache-miss fixture missing at {src}")
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


def cache_miss_issue(workspace: Path) -> Path:
    return workspace / "issues" / "001-cache-miss.md"
