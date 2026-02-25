"""Agent selector component for choosing which agent to interact with."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.tui.onboard.config import TUIConfig
from src.tui.utils.formatting import bold, dim, status_emoji

if TYPE_CHECKING:
    pass


class AgentInfo:
    """Information about a Digital CTO agent."""

    def __init__(
        self,
        key: str,
        name: str,
        emoji: str,
        description: str,
        enabled: bool = True,
    ):
        """Initialize agent info.

        Args:
            key: Agent config key
            name: Display name
            emoji: Emoji indicator
            description: Short description
            enabled: Whether agent is enabled
        """
        self.key = key
        self.name = name
        self.emoji = emoji
        self.description = description
        self.enabled = enabled


ALL_AGENTS = [
    AgentInfo("code_review", "Code Review", "🔍", "Reviews PRs for security, architecture, quality"),
    AgentInfo("sprint_planner", "Sprint Planner", "📊", "Tracks sprints, generates reports"),
    AgentInfo("architecture_advisor", "Architecture Advisor", "🏗️", "Design guidance, tech debt"),
    AgentInfo("devops", "DevOps", "🔧", "Pipeline monitoring, failure analysis"),
    AgentInfo("market_scanner", "Market Scanner", "📈", "Market intelligence, briefs"),
    AgentInfo("meeting_intelligence", "Meeting Intelligence", "👥", "Meeting analysis, briefs"),
    AgentInfo("coding_agent", "Coding Agent", "💻", "Autonomous coding tasks"),
]


def get_enabled_agents(config: TUIConfig) -> list[AgentInfo]:
    """Get list of enabled agents from config.

    Args:
        config: TUI configuration

    Returns:
        List of enabled AgentInfo objects
    """
    enabled = []

    for agent in ALL_AGENTS:
        agent_config = getattr(config.agents, agent.key, None)
        if agent_config and agent_config.enabled:
            agent.enabled = True
            enabled.append(agent)

    return enabled


def format_agent_list(agents: list[AgentInfo], show_status: bool = True) -> str:
    """Format a list of agents for display.

    Args:
        agents: List of agents to format
        show_status: Whether to show status indicators

    Returns:
        Formatted string
    """
    lines = []
    for i, agent in enumerate(agents, 1):
        status = f" {status_emoji('running' if agent.enabled else 'disabled')}" if show_status else ""
        lines.append(f"  {i}. {agent.emoji} {bold(agent.name)}{status}")
        lines.append(f"      {dim(agent.description)}")

    return "\n".join(lines)


def select_agent(config: TUIConfig) -> str | None:
    """Prompt user to select an agent.

    Args:
        config: TUI configuration

    Returns:
        Selected agent key or None if cancelled
    """
    from src.tui.utils.navigation import select_option

    agents = get_enabled_agents(config)

    if not agents:
        print("No agents enabled. Please enable agents in configuration.")
        return None

    options = [
        f"{agent.emoji} {agent.name} - {agent.description}"
        for agent in agents
    ]

    index = select_option("Select an agent", options)

    if index is not None:
        return agents[index].key

    return None
