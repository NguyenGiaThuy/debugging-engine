# Debugging Engine public API

**Status:** Stable for Phase 3+ (package `1.0.7`).

Debugging Engine is an **agent-agnostic investigation kernel**. This API does **not** run Analyst/Adversary/Implementer LLMs. Coding agents call these methods (or the CLI) to advance Case State.

Release notes: [`CHANGELOG.md`](../CHANGELOG.md). Architecture: [`SPECIFICATION.md`](SPECIFICATION.md) (v1.0.0).

## Kernel invariants (package 1.0.7)

- Judge schedules **one** Task at a time (Spec §10 parallel orchestration is not implemented).
- `submit` events must use types allowed by the current Task **and** `producer` matching that Task `role`.
- Unexpected verify exit → experiment **FAILED** (not COMPLETED); patches / `working_directory` are path-contained.
- After unrebutted SUPPORTS evidence, Judge re-engages Adversary before the next approve/accept.
- `RootCauseAccepted` requires Judge producer + `authority: Judge`, supporting interpretations, all terminal evidence interpreted, a passed verification, successful intervention when any patched experiment exists, and disposed competitors.

## Install

```bash
uv tool install debugging-engine
# or for local development:
uv pip install -e ".[dev]"
```

Scaffold skills into a project: `debugging-engine --agent cursor`.

## Quick start

```python
from debugging_engine import Case, Engine, DomainEvent, EventType, AgentRole
from datetime import datetime, timezone

engine = Engine(repo_root=".")
case = Case.open(engine, "issues/my-bug.md")

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
| `Engine` | `debugging_engine` | Repo/store + optional `SchedulingPolicy` |
| `Case` | `debugging_engine` | Bound investigation (`open`, `load`, `next`, `submit`, `verify`, …) |
| `Task` | `debugging_engine` | Judge handoff (role, projection, allowed events) |
| `DomainEvent` / `EventType` | `debugging_engine` | Event envelope types |
| `ValidationError` | `debugging_engine` | Illegal state transitions / budgets |
| `SchedulingPolicy` | `debugging_engine` / `debugging_engine.policies` | Protocol for custom Judges |
| `DefaultSchedulingPolicy` | `debugging_engine.policies` | Built-in Part IV Judge |
| `schedule_next_task` | `debugging_engine` | Function form of the default policy |

## Engine

```python
Engine(repo_root=".", store_root=None, policy=None)
```

- `repo_root` — project under investigation (cwd of the coding agent)
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
case = Case.open(engine, "issues/my-bug.md")
print(case.next().objective)
```

## Unstable internals

Do not import from `debugging_engine.application`, `debugging_engine.infrastructure`, or `debugging_engine.runtime` in application code — they may change without a major version bump.

## CLI

The `debugging-engine` CLI is a thin wrapper over this API (`open`, `next`, `submit`, `verify`, `demo`, `validate`).
