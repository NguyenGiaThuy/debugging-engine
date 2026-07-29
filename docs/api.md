# Debugging Engine public API

**Status:** Stable for Phase 3+ (package `0.7.0`). See [ADR 0005](decisions/0005-public-framework-api.md).

Debugging Engine is an **agent-agnostic investigation kernel**. This API does **not** run Analyst/Adversary/Implementer LLMs. Coding agents call these methods (or the CLI) to advance Case State.

## Install

```bash
uv tool install debugging-engine --from git+https://github.com/NguyenGiaThuy/debugging-engine
# or for local development:
uv pip install -e ".[dev]"
```

Scaffold skills into a project: `debugging-engine --agent cursor` (see [ADR 0007](decisions/0007-agent-scaffolding.md)).

## Quick start

```python
from debugging_engine import Case, Engine, DomainEvent, EventType, AgentRole
from datetime import datetime, timezone

engine = Engine(repo_root=".")
case = Case.open(engine, "subject/issues/001-cache-miss.md")

task = case.next()          # Judge scheduling → Task
print(task.role, task.objective)

# After the coding agent reasons, submit domain events:
# case.submit([DomainEvent(...)])
# case.verify(experiment_id)

print(case.status()["status"])
```

## Symbols

| Symbol | Module | Purpose |
| --- | --- | --- |
| `Engine` | `debugging-engine` | Repo/store + optional `SchedulingPolicy` |
| `Case` | `debugging-engine` | Bound investigation (`open`, `load`, `next`, `submit`, `verify`, …) |
| `Task` | `debugging-engine` | Judge handoff (role, projection, allowed events) |
| `DomainEvent` / `EventType` | `debugging-engine` | Event envelope types |
| `ValidationError` | `debugging-engine` | Illegal state transitions / budgets |
| `SchedulingPolicy` | `debugging-engine` / `debugging_engine.policies` | Protocol for custom Judges |
| `DefaultSchedulingPolicy` | `debugging_engine.policies` | Built-in Part IV Judge |
| `schedule_next_task` | `debugging-engine` | Function form of the default policy |

## Engine

```python
Engine(repo_root=".", store_root=None, policy=None)
```

- `repo_root` — workspace containing `subject/` (or any project under investigation)
- `store_root` — Event Log root (default `<repo>/.debugging-engine/cases`)
- `policy` — `SchedulingPolicy` used by `Case.next()`

## Case

| Method | Description |
| --- | --- |
| `Case.open(engine, issue_path)` | Create Case + Unknown from markdown |
| `Case.load(engine, case_id)` | Reattach to existing case |
| `next()` | Schedule next `Task` (bumps stall cycles when not terminal) |
| `submit(events)` | Append validated `DomainEvent`s |
| `verify(experiment_id)` | Run Verification Spec; record Evidence |
| `query(q)` | Projection slice (`summary`, `hypotheses`, …) |
| `status()` / `log()` / `replay()` | Inspect Case State / Event Log |
| `metrics()` | Phase 2 case metrics |

## Custom scheduling policy

```python
from debugging_engine import Case, Engine, Task
from debugging_engine.domain.models import AgentRole, CaseState, InvestigationStatus

class AlwaysEscalate:
    def schedule(self, state: CaseState) -> Task:
        return Task(
            case_id=state.case_id,
            role=AgentRole.JUDGE,
            objective="Custom policy: escalate",
            allowed_event_types=["InvestigationEscalated"],
            done=state.status != InvestigationStatus.ACTIVE,
            terminal_status=state.status.value if state.status != InvestigationStatus.ACTIVE else None,
        )

engine = Engine(repo_root=".", policy=AlwaysEscalate())
case = Case.open(engine, "subject/issues/001-cache-miss.md")
print(case.next().objective)
```

## Unstable internals

Do not import from `debugging_engine.application`, `debugging_engine.infrastructure`, or `debugging_engine.runtime` in application code — they may change without a major version bump.

## CLI

The `debugging-engine` CLI is a thin wrapper over this API (`open`, `next`, `submit`, `verify`, `demo`, `validate`).
