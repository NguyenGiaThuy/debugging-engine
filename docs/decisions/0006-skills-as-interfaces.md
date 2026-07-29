# ADR 0006 — Skills are interfaces to the Debugging Engine kernel

## Context

Phases 1–3 produced a runnable, agent-agnostic kernel and public `Engine`/`Case` API. Users still need ergonomic entry points inside coding agents (Cursor skills) without embedding LLMs into Debugging Engine.

## Decision

1. Ship **project Cursor skills** under `.cursor/skills/`:
   - `debugging-engine-investigate` — general debugging investigation
   - `debugging-engine-incident` — production incident specialization
   - `debugging-engine-performance` — performance bottleneck specialization
2. Skills instruct the agent to drive Debugging Engine via CLI/API; they do **not** replace Case State, Judge, or Verifier.
3. Skills use `disable-model-invocation: true` so they load when explicitly relevant/named.
4. Track `.cursor/skills/**` in git; ignore other `.cursor/` paths.

## Rationale

Matches the roadmap: Debugging Engine is infrastructure (like Git); skills are interfaces (like GitHub Desktop / IDE integrations).

## Consequences

- Improving investigation quality is mostly kernel/ADR work, not skill prompt inflation.
- New domains (security, architecture review) should add thin skills that reuse the same loop.

## Alternatives considered

- Personal-only skills in `~/.cursor/skills` — rejected for this repo; project skills travel with the code.
- Auto-invocation without disable flag — deferred; prefer explicit investigation intent first.
