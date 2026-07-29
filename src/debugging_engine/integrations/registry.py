"""Supported coding agents and where their project skills live."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentSpec:
    key: str
    display_name: str
    skill_root: str  # relative to project root


AGENTS: dict[str, AgentSpec] = {
    "claude": AgentSpec(
        key="claude",
        display_name="Claude Code",
        skill_root=".claude/skills",
    ),
    "cursor": AgentSpec(
        key="cursor",
        display_name="Cursor",
        skill_root=".cursor/skills",
    ),
    "copilot": AgentSpec(
        key="copilot",
        display_name="GitHub Copilot",
        skill_root=".github/skills",
    ),
    "codex": AgentSpec(
        key="codex",
        display_name="Codex",
        skill_root=".agents/skills",
    ),
}


def get_agent(key: str) -> AgentSpec:
    try:
        return AGENTS[key]
    except KeyError as exc:
        supported = ", ".join(sorted(AGENTS))
        raise KeyError(f"Unknown agent {key!r}. Supported: {supported}") from exc


def list_agent_keys() -> list[str]:
    return sorted(AGENTS)


def parse_agent_keys(raw: str) -> list[str]:
    """
    Parse a comma-separated agent list, or the special value ``all``.

    ``all`` must be the sole token. Duplicates are removed while preserving order.
    """
    parts = [p.strip() for p in raw.split(",")]
    parts = [p for p in parts if p]
    if not parts:
        raise ValueError("Empty --agent value. Pass a name, comma list, or 'all'.")

    if "all" in parts:
        if parts != ["all"]:
            raise ValueError(
                "Do not mix 'all' with other agent names (e.g. use --agent all, not all,claude)."
            )
        return list_agent_keys()

    seen: set[str] = set()
    keys: list[str] = []
    for part in parts:
        get_agent(part)  # validate
        if part not in seen:
            seen.add(part)
            keys.append(part)
    return keys
