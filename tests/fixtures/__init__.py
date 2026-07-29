"""Test helpers for materializing offline investigation workspaces."""

from __future__ import annotations

from pathlib import Path

from debugging_engine.runtime.stubs.fixture import (
    cache_miss_issue,
    materialize_cache_miss,
    materialize_session_ttl,
    session_ttl_issue,
)

__all__ = [
    "cache_miss_issue",
    "materialize_cache_miss",
    "cache_miss_workspace",
    "materialize_session_ttl",
    "session_ttl_issue",
    "session_ttl_workspace",
]


def cache_miss_workspace(tmp_path: Path) -> tuple[Path, Path]:
    """Return (workspace_root, issue_path) under ``tmp_path``."""
    workspace = materialize_cache_miss(tmp_path / "cache_miss")
    return workspace, cache_miss_issue(workspace)


def session_ttl_workspace(tmp_path: Path) -> tuple[Path, Path]:
    """Return (workspace_root, issue_path) for the session TTL fixture."""
    workspace = materialize_session_ttl(tmp_path / "session_ttl")
    return workspace, session_ttl_issue(workspace)
