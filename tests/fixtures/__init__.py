"""Test helpers for materializing the offline cache-miss workspace."""

from __future__ import annotations

from pathlib import Path

from debugging_engine.runtime.stubs.fixture import cache_miss_issue, materialize_cache_miss

__all__ = ["cache_miss_issue", "materialize_cache_miss", "cache_miss_workspace"]


def cache_miss_workspace(tmp_path: Path) -> tuple[Path, Path]:
    """Return (workspace_root, issue_path) under ``tmp_path``."""
    workspace = materialize_cache_miss(tmp_path / "cache_miss")
    return workspace, cache_miss_issue(workspace)
