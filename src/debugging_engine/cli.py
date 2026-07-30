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
    """Investigation workspace defaults to the current working directory."""
    return Path.cwd()


def engine() -> Engine:
    return Engine(repo_root=repo_root())


@app.callback()
def main(
    ctx: typer.Context,
    agent: Optional[str] = typer.Option(
        None,
        "--agent",
        help="Scaffold Debugging Engine skills for coding agents. "
        "Comma-separated list or 'all' (claude, cursor, copilot, codex).",
        metavar="AGENTS",
    ),
    uninstall: Optional[str] = typer.Option(
        None,
        "--uninstall",
        help="Remove scaffolded skills. Pass agent name(s) or 'all' "
        "(e.g. --uninstall claude or --uninstall all).",
        metavar="AGENTS",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite on --agent install, or delete modified files on --uninstall.",
    ),
    path: Path = typer.Option(
        Path("."),
        "--path",
        help="Project root for --agent / --uninstall (default: cwd).",
        file_okay=False,
        dir_okay=True,
        writable=True,
        resolve_path=True,
    ),
) -> None:
    """Scaffold or uninstall agent skills when --agent / --uninstall is set without a subcommand."""
    if ctx.invoked_subcommand is not None:
        return
    if agent is not None and uninstall is not None:
        console.print("[red]Use either --agent or --uninstall, not both.[/red]")
        raise typer.Exit(code=1)
    if agent is None and uninstall is None:
        typer.echo(ctx.get_help())
        raise typer.Exit(code=0)

    raw = uninstall if uninstall is not None else agent
    assert raw is not None
    try:
        keys = parse_agent_keys(raw)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        console.print(f"Supported agents: {', '.join(list_agent_keys())} (or 'all')")
        raise typer.Exit(code=1) from exc
    except KeyError as exc:
        console.print(f"[red]{exc}[/red]")
        console.print(f"Supported agents: {', '.join(list_agent_keys())} (or 'all')")
        raise typer.Exit(code=1) from exc

    try:
        if uninstall is not None:
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
    issue: Path = typer.Argument(..., help="Path to issue markdown file"),
    mode: str = typer.Option(
        "incident",
        "--mode",
        help="Investigation mode: investigate | incident | production",
    ),
) -> None:
    """Create a Case + Unknown from an issue file."""
    path = issue if issue.is_absolute() else repo_root() / issue
    if not path.exists():
        raise typer.BadParameter(f"Issue not found: {path}")
    try:
        case = Case.open(engine(), path, mode=mode)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    console.print({"case_id": case.case_id, "mode": mode})


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


@app.command("human-approve")
def human_approve(
    case_id: str,
    experiment_id: str,
    decision: str = typer.Option("approve", "--decision", help="approve | reject"),
    message: str = typer.Option("", "--message", help="Optional approval note"),
) -> None:
    """Record a real-user approval/rejection for a HIGH/CRITICAL intervention."""
    try:
        print_json(
            data=Case.load(engine(), case_id).human_approve(
                experiment_id,
                decision=decision,
                message=message,
            )
        )
    except KeyError:
        raise typer.Exit(code=1) from None
    except ValidationError as exc:
        console.print(f"[red]ValidationFailed[/red]: {exc}")
        raise typer.Exit(code=2) from exc


@app.command("org-approve")
def org_approve(
    case_id: str,
    rationale: str = typer.Option(
        "Organizational approval granted",
        "--rationale",
        help="Approval rationale",
    ),
) -> None:
    """Record real-user org approval before FixAccepted (production mode)."""
    try:
        print_json(data=Case.load(engine(), case_id).org_approve(rationale=rationale))
    except KeyError:
        raise typer.Exit(code=1) from None
    except ValidationError as exc:
        console.print(f"[red]ValidationFailed[/red]: {exc}")
        raise typer.Exit(code=2) from exc


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
        help="Issue path inside a workspace (default: materialize offline cache-miss fixture)",
    ),
) -> None:
    """Stub-driven end-to-end investigation (no coding agent / no LLM)."""
    import tempfile

    from debugging_engine.runtime.stubs.fixture import cache_miss_issue, materialize_cache_miss

    with tempfile.TemporaryDirectory(prefix="debugging-engine-demo-") as tmp:
        if issue is None:
            workspace = materialize_cache_miss(Path(tmp) / "workspace")
            path = cache_miss_issue(workspace)
        else:
            workspace = repo_root()
            path = issue if issue.is_absolute() else workspace / issue
            if not path.exists():
                raise typer.BadParameter(f"Issue not found: {path}")
        eng = Engine(repo_root=workspace, store_root=Path(tmp) / "cases")
        result = run_stub_investigation(eng.service, path)
        print_json(data=result)


@app.command()
def validate(
    issue: Optional[Path] = typer.Option(
        None,
        help="Issue path inside a workspace (default: materialize offline cache-miss fixture)",
    ),
    report: Optional[Path] = typer.Option(
        None,
        help="Write markdown report (default: phase2-report.md under cwd)",
    ),
) -> None:
    """Run Phase 2 architectural validation scenarios and emit metrics."""
    import tempfile

    from debugging_engine.runtime.stubs.fixture import cache_miss_issue, materialize_cache_miss

    cwd = Path.cwd()
    report_path = report if report else cwd / "phase2-report.md"
    if report_path and not report_path.is_absolute():
        report_path = cwd / report_path

    with tempfile.TemporaryDirectory(prefix="debugging-engine-validate-") as tmp:
        if issue is None:
            workspace = materialize_cache_miss(Path(tmp) / "workspace")
            path = cache_miss_issue(workspace)
        else:
            workspace = repo_root()
            path = issue if issue.is_absolute() else workspace / issue
            if not path.exists():
                raise typer.BadParameter(f"Issue not found: {path}")
        eng = Engine(repo_root=workspace, store_root=Path(tmp) / "cases")
        rows = run_all_scenarios(eng.service, path)

    report_path.parent.mkdir(parents=True, exist_ok=True)
    write_phase2_report(report_path, rows)
    print_json(data={"report": str(report_path), "scenarios": rows})
    if any(not r.get("ok", False) for r in rows):
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
