# ADR 0007 — Agent scaffolding via `--agent`

## Context

Phase 4 shipped Cursor skills in-repo. Consumers need the same skills in arbitrary projects for Claude Code, Copilot, Codex, and Cursor, after installing the CLI with `uv tool install`.

## Decision

1. Canonical skill markdown lives as **package data** under `debugging_engine/integrations/templates/skills/`.
2. Top-level CLI flag `debugging-engine --agent <name>` scaffolds those templates into the agent’s project skill root (`--path` defaults to cwd; `--force` overwrites).
3. Supported agents (v1): `claude` → `.claude/skills/`, `cursor` → `.cursor/skills/`, `copilot` → `.github/skills/`, `codex` → `.agents/skills/`.
4. Scaffolding also ensures `.debugging-engine/` is gitignored and writes `.debugging-engine/integration.json`.
5. Uninstall skills with `debugging-engine --agent <name> --uninstall` (template-identical files only; `--force` deletes modified skill trees). Uninstall the uv tool with `debugging-engine uninstall-cli` (`uv tool uninstall debugging-engine`).
6. `--agent` accepts a comma-separated list or `all` for batch install/uninstall in one call.
7. Package version advances to **0.7.0**.

## Rationale

Keeps the kernel agent-agnostic while making the CLI the single distribution path for interfaces (like Spec Kit’s install story, with a simpler `--agent` UX).

## Consequences

- This repo’s `.cursor/skills/` must stay in sync with package templates (enforced by tests).
- Adding an agent is a registry entry + skill-root path; no per-agent markdown forks unless needed later.
- Skill uninstall does not wipe `.debugging-engine/cases/` or `.gitignore` entries.
- `uninstall-cli` requires `uv` on PATH; otherwise it prints the manual command.
- Batch `--agent claude,cursor` / `--agent all` uninstalls each skill root independently; `integration.json` still records a single last-installed agent.

## Alternatives considered

- `debugging-engine init --integration …` (Spec Kit style) — rejected for a flatter `--agent` flag.
- Publishing only Cursor skills in-git without a scaffolder — insufficient for multi-agent use.
