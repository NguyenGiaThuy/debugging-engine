# reasoning-engine

Reference implementation of **SMADW v3.1** (State Machine–Driven Agentic Debugging Workflow).

SMADW is an **investigation kernel**, not a chat agent. Coding agents (Cursor, Claude Code, Codex, etc.) drive it through a CLI or the Python library. The engine owns Case State, the Event Log, validation, projections, and Judge scheduling. It does **not** embed an LLM.

## Specification

The complete SMADW v3.1 RFC lives in [`docs/rfc/`](docs/rfc/).

| Parts | Status |
| --- | --- |
| I–VI | **Normative** |
| VII | **Informative** |

## Current milestone — Phase 3

Stable framework API (`Engine`, `Case`, `SchedulingPolicy`). See [`docs/api.md`](docs/api.md) and [`docs/roadmap.md`](docs/roadmap.md).

### Library

```python
from smadw import Case, Engine, DomainEvent, EventType

engine = Engine(repo_root=".")
case = Case.open(engine, "subject/issues/001-cache-miss.md")
task = case.next()
# coding agent reasons outside SMADW, then:
# case.submit([... DomainEvent ...])
# case.verify(experiment_id)
```

### CLI

```bash
pip install -e ".[dev]"
smadw demo
smadw validate
smadw open subject/issues/001-cache-miss.md
smadw next <case-id>
smadw submit <case-id> --events path/to/events.json
smadw verify <case-id> <experiment-id>
```

### Agent workflow

1. Open a case (library or CLI)
2. `next` — Judge returns the next Task
3. Reason / edit outside SMADW
4. `submit` domain events
5. `verify` experiments when scheduled
6. Repeat until root cause accepted or escalate

## Layout

| Path | Role |
| --- | --- |
| `docs/rfc/` | SMADW specification |
| `docs/api.md` | Public framework API |
| `docs/roadmap.md` | Phases 1–4 (skill last) |
| `docs/decisions/` | ADRs |
| `src/smadw/` | Investigation kernel + public API |
| `subject/` | System under investigation (seeded bugs) |
| `.smadw/cases/` | Local Event Logs (gitignored) |
