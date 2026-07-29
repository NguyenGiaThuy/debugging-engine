"""Path containment helpers for experiment execution under a repo root."""

from __future__ import annotations

from pathlib import Path

from debugging_engine.domain.validation import ValidationError


def resolve_under_root(repo_root: Path, rel: str, *, what: str = "path") -> Path:
    """Resolve ``rel`` under ``repo_root``; reject absolute paths and escapes."""
    root = repo_root.resolve()
    if not rel or rel.strip() == "":
        raise ValidationError(f"{what} must be a non-empty relative path")
    candidate = Path(rel)
    if candidate.is_absolute():
        raise ValidationError(
            f"{what} must be relative to the repository root",
            {"path": rel},
        )
    # Disallow parent segments before resolve so ".."/escape is explicit.
    if ".." in candidate.parts:
        raise ValidationError(
            f"{what} must not contain '..' path segments",
            {"path": rel},
        )
    target = (root / candidate).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValidationError(
            f"{what} escapes the repository root",
            {"path": rel, "resolved": str(target), "root": str(root)},
        ) from exc
    return target
