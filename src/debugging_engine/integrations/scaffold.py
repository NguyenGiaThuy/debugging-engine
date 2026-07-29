"""Copy packaged skill templates into a project's agent skill directory."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from debugging_engine import __version__
from debugging_engine.integrations.registry import AgentSpec, get_agent

GITIGNORE_ENTRY = ".debugging-engine/"
SKILL_NAMES = (
    "debugging-engine-investigate",
    "debugging-engine-incident",
    "debugging-engine-performance",
)


class ScaffoldError(Exception):
    """Scaffolding failed (conflict without --force, missing templates, etc.)."""


def templates_root() -> Path:
    """Return the filesystem path to packaged skill templates."""
    return Path(__file__).resolve().parent / "templates" / "skills"


def _iter_template_files(skill_dir: Path) -> list[Path]:
    return sorted(p for p in skill_dir.rglob("*") if p.is_file())


def _copy_skill(src: Path, dest: Path, *, force: bool) -> list[str]:
    """Copy one skill tree. Returns absolute paths written."""
    written: list[str] = []
    for src_file in _iter_template_files(src):
        rel = src_file.relative_to(src)
        dest_file = dest / rel
        if dest_file.exists() and not force:
            existing = dest_file.read_bytes()
            incoming = src_file.read_bytes()
            if existing != incoming:
                raise ScaffoldError(
                    f"Refusing to overwrite modified file: {dest_file}. Pass --force to overwrite."
                )
            continue
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dest_file)
        written.append(str(dest_file))
    return written


def ensure_gitignore(project_root: Path) -> bool:
    """Append `.debugging-engine/` to .gitignore if missing. Returns True if changed."""
    gitignore = project_root / ".gitignore"
    markers = {GITIGNORE_ENTRY, GITIGNORE_ENTRY.rstrip("/")}
    if gitignore.exists():
        text = gitignore.read_text(encoding="utf-8")
        lines = {line.strip() for line in text.splitlines()}
        if markers & lines:
            return False
        suffix = "" if text.endswith("\n") or text == "" else "\n"
        gitignore.write_text(
            f"{text}{suffix}\n# Debugging Engine local case data\n{GITIGNORE_ENTRY}\n",
            encoding="utf-8",
        )
        return True
    gitignore.write_text(f"# Debugging Engine local case data\n{GITIGNORE_ENTRY}\n", encoding="utf-8")
    return True


def write_integration_manifest(project_root: Path, agent: AgentSpec) -> Path:
    dest_dir = project_root / ".debugging-engine"
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / "integration.json"
    payload = {
        "agent": agent.key,
        "display_name": agent.display_name,
        "skill_root": agent.skill_root,
        "debugging_engine_version": __version__,
        "skills": list(SKILL_NAMES),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def scaffold_agent(
    agent_key: str,
    project_root: Path,
    *,
    force: bool = False,
) -> dict:
    """
    Scaffold Debugging Engine skills for ``agent_key`` under ``project_root``.

    Returns a summary dict suitable for CLI/JSON output.
    """
    agent = get_agent(agent_key)
    project_root = project_root.resolve()
    if not project_root.is_dir():
        raise ScaffoldError(f"Project path is not a directory: {project_root}")

    templates_path = templates_root()
    if not templates_path.is_dir():
        raise ScaffoldError(f"Packaged skill templates missing at {templates_path}")

    written: list[str] = []
    skill_root = project_root / agent.skill_root
    for name in SKILL_NAMES:
        src = templates_path / name
        if not src.is_dir():
            raise ScaffoldError(f"Template skill missing: {name}")
        dest = skill_root / name
        dest.mkdir(parents=True, exist_ok=True)
        for path in _copy_skill(src, dest, force=force):
            written.append(str(Path(path).relative_to(project_root)).replace("\\", "/"))

    gitignore_updated = ensure_gitignore(project_root)
    manifest = write_integration_manifest(project_root, agent)

    return {
        "agent": agent.key,
        "display_name": agent.display_name,
        "project_root": str(project_root),
        "skill_root": agent.skill_root,
        "files_written": written,
        "gitignore_updated": gitignore_updated,
        "manifest": str(manifest.relative_to(project_root)).replace("\\", "/"),
        "version": __version__,
    }


def _rel(project_root: Path, path: Path) -> str:
    return str(path.relative_to(project_root)).replace("\\", "/")


def _remove_empty_parents(path: Path, stop_at: Path) -> None:
    """Remove empty directories from path up to (but not including) stop_at."""
    current = path
    while current != stop_at and current.is_dir():
        try:
            next(current.iterdir())
            break
        except StopIteration:
            parent = current.parent
            current.rmdir()
            current = parent


def uninstall_agent(
    agent_key: str,
    project_root: Path,
    *,
    force: bool = False,
) -> dict:
    """
    Remove Debugging Engine skills for ``agent_key`` under ``project_root``.

    Without ``force``, only deletes files byte-identical to packaged templates.
    With ``force``, deletes entire ``debugging-engine-*`` skill directories.
    """
    agent = get_agent(agent_key)
    project_root = project_root.resolve()
    if not project_root.is_dir():
        raise ScaffoldError(f"Project path is not a directory: {project_root}")

    templates_path = templates_root()
    if not templates_path.is_dir():
        raise ScaffoldError(f"Packaged skill templates missing at {templates_path}")

    skill_root = project_root / agent.skill_root
    removed: list[str] = []
    preserved: list[str] = []

    for name in SKILL_NAMES:
        dest = skill_root / name
        src = templates_path / name
        if not dest.exists():
            continue

        if force:
            if dest.is_dir():
                for path in sorted((p for p in dest.rglob("*") if p.is_file())):
                    removed.append(_rel(project_root, path))
                shutil.rmtree(dest)
            elif dest.is_file():
                dest.unlink()
                removed.append(_rel(project_root, dest))
            continue

        if not src.is_dir():
            raise ScaffoldError(f"Template skill missing: {name}")

        for src_file in _iter_template_files(src):
            rel = src_file.relative_to(src)
            dest_file = dest / rel
            if not dest_file.is_file():
                continue
            if dest_file.read_bytes() == src_file.read_bytes():
                dest_file.unlink()
                removed.append(_rel(project_root, dest_file))
            else:
                preserved.append(_rel(project_root, dest_file))

        # Extra files under the skill dir (not in templates) are preserved
        if dest.is_dir():
            for leftover in sorted(dest.rglob("*"), reverse=True):
                if leftover.is_file():
                    rel_s = _rel(project_root, leftover)
                    if rel_s not in preserved and rel_s not in removed:
                        preserved.append(rel_s)

        _remove_empty_parents(dest, skill_root)

    manifest_path = project_root / ".debugging-engine" / "integration.json"
    manifest_removed = False
    if manifest_path.is_file():
        should_remove = True
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            recorded = payload.get("agent")
            if recorded is not None and recorded != agent.key:
                should_remove = False
        except (json.JSONDecodeError, OSError):
            should_remove = True
        if should_remove:
            manifest_path.unlink()
            manifest_removed = True
            removed.append(_rel(project_root, manifest_path))

    return {
        "agent": agent.key,
        "display_name": agent.display_name,
        "project_root": str(project_root),
        "skill_root": agent.skill_root,
        "files_removed": removed,
        "preserved": preserved,
        "force": force,
        "manifest_removed": manifest_removed,
        "version": __version__,
    }


def scaffold_agents(
    agent_keys: list[str],
    project_root: Path,
    *,
    force: bool = False,
) -> dict:
    """Scaffold one or more agents. Single key returns the single-agent summary."""
    if len(agent_keys) == 1:
        return scaffold_agent(agent_keys[0], project_root, force=force)

    results = [scaffold_agent(key, project_root, force=force) for key in agent_keys]
    files_written: list[str] = []
    for item in results:
        files_written.extend(item.get("files_written", []))
    return {
        "agents": list(agent_keys),
        "results": results,
        "files_written": files_written,
        "force": force,
        "version": __version__,
    }


def uninstall_agents(
    agent_keys: list[str],
    project_root: Path,
    *,
    force: bool = False,
) -> dict:
    """Uninstall one or more agents. Single key returns the single-agent summary."""
    if len(agent_keys) == 1:
        return uninstall_agent(agent_keys[0], project_root, force=force)

    results = [uninstall_agent(key, project_root, force=force) for key in agent_keys]
    files_removed: list[str] = []
    preserved: list[str] = []
    for item in results:
        files_removed.extend(item.get("files_removed", []))
        preserved.extend(item.get("preserved", []))
    return {
        "agents": list(agent_keys),
        "results": results,
        "files_removed": files_removed,
        "preserved": preserved,
        "force": force,
        "version": __version__,
    }
