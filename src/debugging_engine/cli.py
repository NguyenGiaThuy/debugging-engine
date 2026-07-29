from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import typer
from rich import print_json
from rich.console import Console

from debugging_engine import Case, DomainEvent, Engine, ValidationError
from debugging_engine.application.metrics import write_phase2_report
from debugging_engine.integrations.registry import list_agent_keys, parse_agent_keys
from debugging_engine.integrations.scaffold import (
    ScaffoldError,
    scaffold_agents,
    uninstall_agents,
)
from debugging_engine.runtime.stubs.demo import run_stub_investigation
from debugging_engine.runtime.stubs.scenarios import run_all_scenarios

app = typer.Typer(
    help="Debugging Engine investigation kernel — agent-agnostic CLI",
    no_args_is_help=True,
    invoke_without_command=True,
)
console = Console()


def repo_root() -> Path:
    cwd = Path.cwd()
    if (cwd / "subject").exists() and (cwd / "pyproject.toml").exists():
        return cwd
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists() and (parent / "subject").exists():
            return parent
    return cwd


def engine() -> Engine:
    return Engine(repo_root=repo_root())


@app.callback()
def main(
    ctx: typer.Context,
    agent: Optional[str] = typer.Option(
        None,
        "--agent",
        help="Scaffold or uninstall Debugging Engine skills for coding agents. "
        "Comma-separated list or 'all' (claude, cursor, copilot, codex).",
    ),
    uninstall: bool = typer.Option(
        False,
        "--uninstall",
        help="Remove scaffolded skills for --agent (use with --agent).",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="With --agent: overwrite on install, or delete modified files on --uninstall.",
    ),
    path: Path = typer.Option(
        Path("."),
        "--path",
        help="Project root for --agent scaffolding/uninstall (default: cwd).",
        file_okay=False,
        dir_okay=True,
        writable=True,
        resolve_path=True,
    ),
) -> None:
    """Scaffold or uninstall agent skills when --agent is set without a subcommand."""
    if ctx.invoked_subcommand is not None:
        return
    if uninstall and agent is None:
        console.print("[red]--uninstall requires --agent <name>.[/red]")
        console.print(f"Supported agents: {', '.join(list_agent_keys())} (or 'all')")
        raise typer.Exit(code=1)
    if agent is None:
        typer.echo(ctx.get_help())
        raise typer.Exit(code=0)

    try:
        keys = parse_agent_keys(agent)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        console.print(f"Supported agents: {', '.join(list_agent_keys())} (or 'all')")
        raise typer.Exit(code=1) from exc
    except KeyError as exc:
        console.print(f"[red]{exc}[/red]")
        console.print(f"Supported agents: {', '.join(list_agent_keys())} (or 'all')")
        raise typer.Exit(code=1) from exc

    try:
        if uninstall:
            result = uninstall_agents(keys, path, force=force)
        else:
            result = scaffold_agents(keys, path, force=force)
    except KeyError as exc:
        console.print(f"[red]{exc}[/red]")
        console.print(f"Supported agents: {', '.join(list_agent_keys())} (or 'all')")
        raise typer.Exit(code=1) from exc
    except ScaffoldError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    print_json(data=result)


@app.command("uninstall-cli")
def uninstall_cli() -> None:
    """Uninstall the debugging-engine uv tool from this machine."""
    manual = "uv tool uninstall debugging-engine"
    uv = shutil.which("uv")
    if uv is None:
        console.print("[red]uv not found on PATH.[/red]")
        console.print(f"Run manually: {manual}")
        raise typer.Exit(code=1)

    completed = subprocess.run(
        [uv, "tool", "uninstall", "debugging-engine"],
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        if completed.stdout.strip():
            console.print(completed.stdout.strip())
        if completed.stderr.strip():
            console.print(f"[red]{completed.stderr.strip()}[/red]")
        console.print(f"Run manually: {manual}")
        raise typer.Exit(code=completed.returncode or 1)

    message = completed.stdout.strip() or "Uninstalled debugging-engine uv tool."
    console.print(message)



@app.command()
def open(
    issue: Path = typer.Argument(..., help="Path to issue markdown under subject/issues/"),
) -> None:
    """Create a Case + Unknown from an issue file."""
    path = issue if issue.is_absolute() else repo_root() / issue
    if not path.exists():
        raise typer.BadParameter(f"Issue not found: {path}")
    case = Case.open(engine(), path)
    console.print({"case_id": case.case_id})


@app.command("next")
def next_task(case_id: str) -> None:
    """Ask the Judge for the next Task handoff."""
    try:
        case = Case.load(engine(), case_id)
        print_json(data=case.next().model_dump(mode="json"))
    except KeyError:
        raise typer.Exit(code=1) from None


@app.command()
def query(case_id: str, q: str = typer.Argument("summary")) -> None:
    """Query a Case State projection slice."""
    try:
        print_json(data=Case.load(engine(), case_id).query(q))
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
        print_json(data=Case.load(engine(), case_id).submit(parsed))
    except KeyError:
        raise typer.Exit(code=1) from None
    except ValidationError as exc:
        console.print(f"[red]ValidationFailed[/red]: {exc}")
        raise typer.Exit(code=2) from exc


@app.command()
def verify(case_id: str, experiment_id: str) -> None:
    """Run the Verification Spec for an experiment; record Evidence events."""
    try:
        print_json(data=Case.load(engine(), case_id).verify(experiment_id))
    except (KeyError, ValueError, RuntimeError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc


@app.command()
def status(case_id: str) -> None:
    """Show Case State summary."""
    try:
        print_json(data=Case.load(engine(), case_id).status())
    except KeyError:
        raise typer.Exit(code=1) from None


@app.command()
def log(case_id: str) -> None:
    """Print the Event Log."""
    try:
        print_json(data=Case.load(engine(), case_id).log())
    except KeyError:
        raise typer.Exit(code=1) from None


@app.command()
def replay(case_id: str) -> None:
    """Rebuild Case State from the Event Log and print it."""
    try:
        print_json(data=Case.load(engine(), case_id).replay())
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
    buggy = '''\
"""Tiny in-memory cache used as the Debugging Engine investigation subject."""


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
        result = run_stub_investigation(engine().service, path)
        print_json(data=result)
    finally:
        (root / "subject" / "cache.py").write_text(buggy, encoding="utf-8")


@app.command()
def validate(
    issue: Optional[Path] = typer.Option(
        None,
        help="Issue path (default: subject/issues/001-cache-miss.md)",
    ),
    report: Optional[Path] = typer.Option(
        None,
        help="Write markdown report (default: docs/validation/phase2-report.md)",
    ),
) -> None:
    """Run Phase 2 architectural validation scenarios and emit metrics."""
    root = repo_root()
    path = issue if issue else root / "subject" / "issues" / "001-cache-miss.md"
    if not path.is_absolute():
        path = root / path
    report_path = report if report else root / "docs" / "validation" / "phase2-report.md"
    if report_path and not report_path.is_absolute():
        report_path = root / report_path

    buggy = (root / "subject" / "cache.py").read_text(encoding="utf-8")
    import tempfile

    with tempfile.TemporaryDirectory(prefix="debugging-engine-validate-") as tmp:
        eng = Engine(repo_root=root, store_root=Path(tmp) / "cases")
        try:
            rows = run_all_scenarios(eng.service, path)
        finally:
            (root / "subject" / "cache.py").write_text(buggy, encoding="utf-8")

    write_phase2_report(report_path, rows)
    print_json(data={"report": str(report_path), "scenarios": rows})
    if any(not r.get("ok", False) for r in rows):
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
