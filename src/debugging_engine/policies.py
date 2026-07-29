"""Public scheduling policy types (ADR 0005)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from debugging_engine.application.judge import Task, schedule_next_task
from debugging_engine.domain.models import CaseState

# Re-export Phase 2 policy constants for convenience
from debugging_engine.domain.policies import (  # noqa: F401
    INACTIVE_HYPOTHESIS_STATUSES,
    MAX_ACTIVE_HYPOTHESES_PER_UNKNOWN,
    MAX_OBSERVATION_CHARS,
    MAX_PROJECTION_FIELD_CHARS,
    STALL_CYCLES_BEFORE_ESCALATION,
)


@runtime_checkable
class SchedulingPolicy(Protocol):
    """Judge scheduling strategy — meta-technical only."""

    def schedule(self, state: CaseState) -> Task:
        """Return the next Task handoff for an external coding agent."""
        ...


class DefaultSchedulingPolicy:
    """Default Judge policy (Part IV orchestration rules)."""

    def schedule(self, state: CaseState) -> Task:
        return schedule_next_task(state)
