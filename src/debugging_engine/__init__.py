"""Debugging Engine investigation kernel — agent-agnostic framework API."""

from debugging_engine.api import Case, Engine
from debugging_engine.application.judge import Task, schedule_next_task
from debugging_engine.domain.models import (
    AgentRole,
    DomainEvent,
    EventType,
    InvestigationMode,
    ObjectionCategory,
)
from debugging_engine.domain.validation import ValidationError
from debugging_engine.policies import DefaultSchedulingPolicy, SchedulingPolicy

__version__ = "1.0.11"

__all__ = [
    "Case",
    "Engine",
    "Task",
    "schedule_next_task",
    "DomainEvent",
    "EventType",
    "AgentRole",
    "InvestigationMode",
    "ObjectionCategory",
    "ValidationError",
    "SchedulingPolicy",
    "DefaultSchedulingPolicy",
    "__version__",
]
