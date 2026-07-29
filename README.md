# debugging-engine

Reference implementation of **Debugging Engine v3.1** (State Machine–Driven Agentic Debugging Workflow).

Debugging Engine is an **investigation kernel**, not a chat agent. Coding agents (Cursor, Claude Code, Codex, etc.) drive it through a CLI or the Python library. The engine owns Case State, the Event Log, validation, projections, and Judge scheduling. It does **not** embed an LLM.

## Specification

The complete Debugging Engine v3.1 RFC lives in [`docs/rfc/`](docs/rfc/).

| Parts | Status |
| --- | --- |
| I–VI | **Normative** |
| VII | **Informative** |

## Current milestone — Phase 4

Cursor **skills** are the interface; Debugging Engine remains the engine. Project skills:

- `debugging-engine-investigate` — general debugging investigation
- `debugging-engine-incident` — production incidents
- `debugging-engine-performance` — latency / throughput / memory

See [`.cursor/skills/`](.cursor/skills/) and [`docs/roadmap.md`](docs/roadmap.md).

### Library

```python
from debugging_engine import Case, Engine, DomainEvent, EventType

engine = Engine(repo_root=".")
case = Case.open(engine, "subject/issues/001-cache-miss.md")
task = case.next()
# coding agent reasons outside Debugging Engine, then:
# case.submit([... DomainEvent ...])
# case.verify(experiment_id)
```

### CLI

```bash
pip install -e ".[dev]"
debugging-engine demo
debugging-engine validate
debugging-engine open subject/issues/001-cache-miss.md
debugging-engine next <case-id>
debugging-engine submit <case-id> --events path/to/events.json
debugging-engine verify <case-id> <experiment-id>
```

### Agent workflow

1. Open a case (library or CLI)
2. `next` — Judge returns the next Task
3. Reason / edit outside Debugging Engine
4. `submit` domain events
5. `verify` experiments when scheduled
6. Repeat until root cause accepted or escalate

## Layout

| Path | Role |
| --- | --- |
| `docs/rfc/` | Debugging Engine specification |
| `docs/api.md` | Public framework API |
| `docs/roadmap.md` | Phases 1–4 |
| `docs/decisions/` | ADRs |
| `.cursor/skills/` | Cursor skills (interfaces to the kernel) |
| `src/debugging_engine/` | Investigation kernel + public API |
| `subject/` | System under investigation (seeded bugs) |
| `.debugging-engine/cases/` | Local Event Logs (gitignored) |
