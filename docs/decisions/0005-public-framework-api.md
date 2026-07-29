# ADR 0005 — Public framework API (Engine + Case)

## Context

Phases 1–2 produced a working kernel (`CaseService`, Judge, Verifier) reachable mainly via CLI and internal imports (`debugging_engine.application.service`). Integrators need a stable library surface without depending on internal modules.

## Decision

1. Public API is `Engine` and `Case` in `debugging_engine.api`, re-exported from `debugging_engine`.
2. `SchedulingPolicy` (protocol) and `DefaultSchedulingPolicy` are public for Judge replacement without forking the kernel.
3. Modules under `debugging_engine.application`, `debugging_engine.infrastructure`, and `debugging_engine.runtime` are **unstable** internals.
4. Package version advances to **0.3.0** for Phase 3 (superseded by 0.4.0 rename release). Analyst/Adversary/Implementer are **not** library runners — coding agents remain external.

## Rationale

Keeps Debugging Engine agent-agnostic while enabling frameworks, CLIs, and (later) skills to build on a documented contract.

## Consequences

- Breaking changes to public symbols require a minor/major bump and ADR.
- CLI becomes a thin consumer of `Engine`/`Case`.

## Alternatives considered

- Expose `CaseService` directly — rejected; name/shape coupled to application layer.
- Embed `Analyst.run()` with LLM providers — rejected (agent-agnostic kernel).
