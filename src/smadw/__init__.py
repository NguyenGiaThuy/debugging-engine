"""SMADW investigation kernel — agent-agnostic framework API."""

from smadw.api import Case, Engine
from smadw.application.judge import Task, schedule_next_task
from smadw.domain.models import AgentRole, DomainEvent, EventType
from smadw.domain.validation import ValidationError
from smadw.policies import DefaultSchedulingPolicy, SchedulingPolicy

__version__ = "0.3.0"

__all__ = [
    "Case",
    "Engine",
    "Task",
    "schedule_next_task",
    "DomainEvent",
    "EventType",
    "AgentRole",
    "ValidationError",
    "SchedulingPolicy",
    "DefaultSchedulingPolicy",
    "__version__",
]
