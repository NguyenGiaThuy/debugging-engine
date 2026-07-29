"""Role announcement helpers matching debugging-engine-investigate skill."""

from __future__ import annotations

from debugging_engine.application.judge import Task
from debugging_engine.domain.models import AgentRole


REQUIRED_INVESTIGATE_ROLES = frozenset(
    {
        AgentRole.ANALYST,
        AgentRole.ADVERSARY,
        AgentRole.JUDGE,
        AgentRole.IMPLEMENTER,
        AgentRole.VERIFIER,
    }
)


def format_role_announcement(task: Task | dict) -> str:
    """Chat-visible handoff line required by the investigate skill.

    Format::

        **Role: <role>** — <objective>
    """
    if isinstance(task, dict):
        role = task.get("role", "?")
        objective = task.get("objective", "")
    else:
        role = task.role.value if hasattr(task.role, "value") else str(task.role)
        objective = task.objective
    return f"**Role: {role}** — {objective}"


def roles_from_announcements(announcements: list[str]) -> set[str]:
    """Parse role names from announcement lines."""
    found: set[str] = set()
    prefix = "**Role: "
    for line in announcements:
        if not line.startswith(prefix):
            continue
        rest = line[len(prefix) :]
        role, _, _ = rest.partition("**")
        if role:
            found.add(role.strip())
    return found
