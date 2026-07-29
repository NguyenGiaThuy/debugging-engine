# ADR 0003 — Scheduling cycle escalation

## Context

Part IV requires starvation recovery and prohibits waiting indefinitely. Phase 1 only re-prompted the Analyst when stalled, with no cycle counter (`starvation` scenario).

## Decision

1. Persist `scheduling_cycles`, `stall_cycles`, and `last_progress_revision` in a per-case scheduler meta sidecar (not domain events), merged into Case State views for the Judge.
2. `smadw next` without progress increments `stall_cycles`.
3. Progress events / successful verify reset `stall_cycles`.
4. When `stall_cycles >= STALL_CYCLES_BEFORE_ESCALATION` (5), the Judge’s next task requires escalation or a productive experiment proposal.

## Rationale

Cycle accounting is orchestration metadata, not an investigative object. Keeping it out of the Event Log avoids polluting epistemic history while still driving Part IV starvation policy.

## Consequences

- Sidecar meta must be present for correct Judge behavior after process restart.
- Future Level-2 may promote cycle markers to explicit events if cross-implementation interoperability requires it.

## Alternatives considered

- Emit `SchedulingCycleTick` domain events — rejected for Phase 2 to avoid Event Log noise.
- Time-based timeouts — rejected; investigations are event-driven, not wall-clock-driven.
