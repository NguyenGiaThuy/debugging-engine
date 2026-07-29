# Roadmap

Debugging Engine is architecture (an investigation kernel). Skills and IDE wrappers come last.

## Phase 1 — Runtime MVP (done)

Minimal agent-agnostic Python CLI kernel: domain model, JSONL Event Log, Case State projection, Judge task handoff, in-engine Verifier, stub e2e.

## Phase 2 — Validate the architecture (done)

Stress scenarios + metrics (`debugging-engine validate`), ADRs 0001–0004, surgical kernel policies.

## Phase 3 — Framework API (done)

Stable library surface: `Engine`, `Case`, pluggable `SchedulingPolicy`. See [`api.md`](api.md) and [ADR 0005](decisions/0005-public-framework-api.md).

## Phase 4 — Skills / interfaces (done)

Cursor project skills wrap the kernel (templates now live in-package; see Phase 5).

| Skill | Path |
| --- | --- |
| `debugging-engine-investigate` | [`.cursor/skills/debugging-engine-investigate/`](../.cursor/skills/debugging-engine-investigate/) |
| `debugging-engine-incident` | [`.cursor/skills/debugging-engine-incident/`](../.cursor/skills/debugging-engine-incident/) |
| `debugging-engine-performance` | [`.cursor/skills/debugging-engine-performance/`](../.cursor/skills/debugging-engine-performance/) |

See [ADR 0006](decisions/0006-skills-as-interfaces.md).

## Phase 5 — Agent scaffolding + uv tool install (done)

Install the CLI with `uv tool install`, then scaffold skills into any project:

```bash
debugging-engine --agent claude|cursor|copilot|codex
debugging-engine --agent claude,cursor --uninstall
debugging-engine --agent all --uninstall
debugging-engine uninstall-cli
```

Canonical templates: `src/debugging_engine/integrations/templates/skills/`. See [ADR 0007](decisions/0007-agent-scaffolding.md).

Offline `demo` / `validate` use a packaged cache-miss fixture (not an in-repo `subject/` tree).

## Explicit non-goals (until later)

- Embedding LLM provider SDKs in the kernel
- Hive / multi-agent colony integration
- Distributed Event Bus (Kafka, etc.)
- Knowledge learning pipeline (Level 3)
- Full Spec Kit–style multi-integration lifecycle (switch/uninstall/catalog)
