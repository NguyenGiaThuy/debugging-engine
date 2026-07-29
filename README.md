# debugging-engine

Reference implementation of **Debugging Engine v3.1** (State Machine–Driven Agentic Debugging Workflow).

Debugging Engine is an **investigation kernel**, not a chat agent. Coding agents (Cursor, Claude Code, Codex, etc.) drive it through a CLI or the Python library. The engine owns Case State, the Event Log, validation, projections, and Judge scheduling. It does **not** embed an LLM.

## Install

```bash
# Preferred once published to PyPI
uv tool install debugging-engine

# Until PyPI publish — install from GitHub
uv tool install debugging-engine --from git+https://github.com/NguyenGiaThuy/debugging-engine

# Local checkout
uv tool install --force .
```

## Scaffold agent skills

In any project:

```bash
debugging-engine --agent claude    # .claude/skills/
debugging-engine --agent cursor    # .cursor/skills/
debugging-engine --agent copilot   # .github/skills/
debugging-engine --agent codex     # .agents/skills/

debugging-engine --agent claude,cursor   # multiple agents in one call
debugging-engine --agent all             # all supported agents

debugging-engine --agent claude --force
debugging-engine --agent cursor --path /path/to/project
```

## Uninstall

```bash
# Remove scaffolded skills (keeps modified files unless --force)
debugging-engine --agent claude --uninstall
debugging-engine --agent claude,cursor --uninstall
debugging-engine --agent all --uninstall
debugging-engine --agent cursor --uninstall --force
debugging-engine --agent claude --uninstall --path /path/to/project

# Remove the globally installed uv tool
debugging-engine uninstall-cli
# same as: uv tool uninstall debugging-engine
```

Skills installed:

- `debugging-engine-investigate` — general debugging investigation
- `debugging-engine-incident` — production incidents
- `debugging-engine-performance` — latency / throughput / memory

See [`docs/roadmap.md`](docs/roadmap.md) and [ADR 0007](docs/decisions/0007-agent-scaffolding.md).

## Specification

The complete Debugging Engine v3.1 RFC lives in [`docs/rfc/`](docs/rfc/).

| Parts | Status |
| --- | --- |
| I–VI | **Normative** |
| VII | **Informative** |

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

### CLI (investigation)

```bash
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
| `docs/roadmap.md` | Phases 1–5 |
| `docs/decisions/` | ADRs |
| `src/debugging_engine/integrations/` | Agent scaffold + skill templates |
| `.cursor/skills/` | Cursor skills (synced from package templates) |
| `src/debugging_engine/` | Investigation kernel + public API |
| `subject/` | System under investigation (seeded bugs) |
| `.debugging-engine/cases/` | Local Event Logs (gitignored) |

## Release (PyPI)

```bash
uv build
uv publish   # or twine upload dist/*
```

Then users can run `uv tool install debugging-engine`.
