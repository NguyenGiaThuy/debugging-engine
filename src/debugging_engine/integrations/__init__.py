"""Agent skill scaffolding for coding-agent integrations."""

from debugging_engine.integrations.registry import (
    AGENTS,
    AgentSpec,
    get_agent,
    parse_agent_keys,
)
from debugging_engine.integrations.scaffold import (
    ScaffoldError,
    scaffold_agent,
    scaffold_agents,
    uninstall_agent,
    uninstall_agents,
)

__all__ = [
    "AGENTS",
    "AgentSpec",
    "ScaffoldError",
    "get_agent",
    "parse_agent_keys",
    "scaffold_agent",
    "scaffold_agents",
    "uninstall_agent",
    "uninstall_agents",
]
