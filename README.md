# reasoning-engine

Reference implementation of **SMADW v3.1** (State Machine–Driven Agentic Debugging Workflow).

SMADW is an **investigation kernel**, not a chat agent. Coding agents (Cursor, Claude Code, Codex, etc.) drive it through a CLI contract. The engine owns Case State, the Event Log, validation, projections, and Judge scheduling. It does **not** embed an LLM.

## Specification

The complete SMADW v3.1 RFC lives in [`docs/rfc/`](docs/rfc/).

| Parts | Status |
| --- | --- |
| I–VI | **Normative** |
| VII | **Informative** |

## Current milestone — Phase 1

Minimal Python CLI kernel + seeded `subject/` defects. See [`docs/roadmap.md`](docs/roadmap.md).

### Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Stub-driven end-to-end (no coding agent / no API keys)
smadw demo

# Or drive manually as a coding agent would:
smadw open subject/issues/001-cache-miss.md
smadw next <case-id>
smadw submit <case-id> --events path/to/events.json
smadw verify <case-id> <experiment-id>
smadw status <case-id>
smadw replay <case-id>
```

### Agent workflow

1. `smadw open <issue>` — create Case + Unknown
2. `smadw next <case-id>` — Judge returns the next Task
3. Do reasoning / edits outside SMADW (your coding agent)
4. `smadw submit <case-id> --events …` — append validated domain events
5. `smadw verify <case-id> <experiment-id>` — run Verification Spec, record Evidence
6. Repeat until root cause accepted or escalate

## Layout

| Path | Role |
| --- | --- |
| `docs/rfc/` | SMADW specification |
| `docs/roadmap.md` | Phases 1–4 (skill last) |
| `docs/decisions/` | ADRs from architectural validation |
| `src/smadw/` | Investigation kernel |
| `subject/` | System under investigation (seeded bugs) |
| `.smadw/cases/` | Local Event Logs (gitignored) |
