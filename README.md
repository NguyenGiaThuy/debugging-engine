# Debugging Engine

**Debugging Engine** (State Machine–Driven Agentic Debugging Workflow) is an **investigation kernel**, not a chat agent.

Coding agents (Cursor, Claude Code, Copilot, Codex, …) drive it through a CLI or the Python library. The engine owns Case State, the Event Log, validation, projections, and Judge scheduling. It does **not** embed an LLM.

## Why

- Investigation state is explicit (Case / Unknown / Hypothesis / Experiment / Evidence), not buried in chat
- A Judge schedules the next role and allowed events — agents advance the case, they don’t “find the answer” alone
- Experiments carry Verification Specs; evidence beats persuasion
- Same kernel for every coding agent via project skills

## Install

```bash
uv tool install debugging-engine
```

Local checkout:

```bash
uv tool install --force .
# or
uv pip install -e ".[dev]"
```

## Quick start

```bash
# Scaffold skills into the current project
debugging-engine --agent cursor   # or: claude, copilot, codex, all

# Describe the unknown
# (create issues/my-bug.md with symptoms + success criteria)

debugging-engine open issues/my-bug.md
debugging-engine next <case-id>
# … reason / edit outside the kernel …
debugging-engine submit <case-id> --events events.json
debugging-engine verify <case-id> <experiment-id>
```

Loop until `RootCauseAccepted` or escalate.

## Scaffold & uninstall

| Agent | Skill root |
| --- | --- |
| `claude` | `.claude/skills/` |
| `cursor` | `.cursor/skills/` |
| `copilot` | `.github/skills/` |
| `codex` | `.agents/skills/` |

```bash
debugging-engine --agent claude,cursor
debugging-engine --agent all
debugging-engine --agent cursor --force
debugging-engine --agent cursor --path /other/repo

debugging-engine --uninstall claude
debugging-engine --uninstall all --force
debugging-engine uninstall-cli    # uv tool uninstall debugging-engine
```

Skills:

- `debugging-engine-investigate` — general debugging
- `debugging-engine-incident` — production incidents
- `debugging-engine-performance` — latency / throughput / memory

## CLI

```bash
debugging-engine open <issue.md>
debugging-engine next <case-id>
debugging-engine submit <case-id> --events events.json
debugging-engine verify <case-id> <experiment-id>
debugging-engine status|log|replay <case-id>
debugging-engine query <case-id> [slice]

debugging-engine demo       # offline stub investigation (temp fixture)
debugging-engine validate   # Phase 2 architectural scenarios (temp fixture)
```

## Python API

```python
from debugging_engine import Case, Engine

engine = Engine(repo_root=".")
case = Case.open(engine, "issues/my-bug.md")
task = case.next()
# case.submit([...]); case.verify(experiment_id)
```

Full surface: [`docs/api.md`](docs/api.md).

## Specification

Debugging Engine **v3.1** RFC: [`docs/rfc/`](docs/rfc/).

| Parts | Status |
| --- | --- |
| I–VI | Normative |
| VII | Informative |

Roadmap and ADRs: [`docs/roadmap.md`](docs/roadmap.md), [`docs/decisions/`](docs/decisions/).

## Repository layout

| Path | Role |
| --- | --- |
| `docs/rfc/` | Specification |
| `docs/api.md` | Public framework API |
| `docs/decisions/` | ADRs |
| `src/debugging_engine/` | Kernel, CLI, skill templates, offline fixtures |
| `.cursor/skills/` | Cursor skills (synced from package templates) |
| `.debugging-engine/cases/` | Local Event Logs (gitignored) |

## Development

```bash
uv pip install -e ".[dev]"
pytest
uv build
uv publish   # requires UV_PUBLISH_TOKEN / PyPI credentials
```
