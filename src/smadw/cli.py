from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich import print_json
from rich.console import Console

from smadw.application.service import CaseService
from smadw.domain.models import DomainEvent
from smadw.domain.validation import ValidationError
from smadw.runtime.stubs.demo import run_stub_investigation

app = typer.Typer(help="SMADW investigation kernel — agent-agnostic CLI", no_args_is_help=True)
console = Console()


def repo_root() -> Path:
    # Prefer cwd (project root when invoked from repo)
    cwd = Path.cwd()
    if (cwd / "subject").exists() and (cwd / "pyproject.toml").exists():
        return cwd
    # Fallback: walk up from package
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists() and (parent / "subject").exists():
            return parent
    return cwd


def service() -> CaseService:
    return CaseService(repo_root())


@app.command()
def open(
    issue: Path = typer.Argument(..., help="Path to issue markdown under subject/issues/"),
) -> None:
    """Create a Case + Unknown from an issue file."""
    path = issue if issue.is_absolute() else repo_root() / issue
    if not path.exists():
        raise typer.BadParameter(f"Issue not found: {path}")
    case_id, events = service().open_issue(path)
    console.print({"case_id": case_id, "events": [e.event_type for e in events]})


@app.command("next")
def next_task(case_id: str) -> None:
    """Ask the Judge for the next Task handoff."""
    try:
        task = service().next_task(case_id)
    except KeyError:
        raise typer.Exit(code=1) from None
    print_json(data=task)


@app.command()
def query(case_id: str, q: str = typer.Argument("summary")) -> None:
    """Query a Case State projection slice."""
    try:
        print_json(data=service().query(case_id, q))
    except KeyError:
        raise typer.Exit(code=1) from None


@app.command()
def submit(
    case_id: str,
    events: Path = typer.Option(..., "--events", help="JSON file: event object or list of events"),
) -> None:
    """Submit one or more domain events (coding-agent handoff)."""
    raw = json.loads(events.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        raw = [raw]
    parsed: list[DomainEvent] = []
    for item in raw:
        item.setdefault("case_id", case_id)
        parsed.append(DomainEvent.model_validate(item))
    try:
        print_json(data=service().submit(parsed))
    except ValidationError as exc:
        console.print(f"[red]ValidationFailed[/red]: {exc}")
        raise typer.Exit(code=2) from exc


@app.command()
def verify(case_id: str, experiment_id: str) -> None:
    """Run the Verification Spec for an experiment; record Evidence events."""
    try:
        print_json(data=service().verify(case_id, experiment_id))
    except (KeyError, ValueError, RuntimeError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc


@app.command()
def status(case_id: str) -> None:
    """Show Case State summary."""
    try:
        print_json(data=service().status(case_id))
    except KeyError:
        raise typer.Exit(code=1) from None


@app.command()
def log(case_id: str) -> None:
    """Print the Event Log."""
    print_json(data=service().log(case_id))


@app.command()
def replay(case_id: str) -> None:
    """Rebuild Case State from the Event Log and print it."""
    try:
        print_json(data=service().replay(case_id))
    except KeyError:
        raise typer.Exit(code=1) from None


@app.command()
def demo(
    issue: Optional[Path] = typer.Option(
        None,
        help="Issue path (default: subject/issues/001-cache-miss.md)",
    ),
) -> None:
    """Stub-driven end-to-end investigation (no coding agent / no LLM)."""
    root = repo_root()
    path = issue if issue else root / "subject" / "issues" / "001-cache-miss.md"
    if not path.is_absolute():
        path = root / path
    # Restore buggy subject before demo so reruns are deterministic
    buggy = '''\
"""Tiny in-memory cache used as the SMADW investigation subject."""


def normalize_key(key: str) -> str:
    # BUG: unused on set path — get lowercases, set does not.
    return key.strip().lower()


class Cache:
    def __init__(self) -> None:
        self._store: dict[str, object] = {}

    def set(self, key: str, value: object) -> None:
        # BUG: stores raw key without normalization
        self._store[key] = value

    def get(self, key: str) -> object | None:
        return self._store.get(key.lower())

    def __contains__(self, key: str) -> bool:
        return key.lower() in self._store
'''
    (root / "subject" / "cache.py").write_text(buggy, encoding="utf-8")
    try:
        result = run_stub_investigation(service(), path)
        print_json(data=result)
    finally:
        (root / "subject" / "cache.py").write_text(buggy, encoding="utf-8")


if __name__ == "__main__":
    app()
