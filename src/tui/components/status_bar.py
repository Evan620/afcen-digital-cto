"""Status bar component for showing system status."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING

from src.tui.utils.formatting import (
    Colors,
    dim,
    status_indicator,
    style,
)

if TYPE_CHECKING:
    pass


class StatusBar:
    """Status bar showing connection and system status."""

    def __init__(self):
        """Initialize the status bar."""
        self.gateway_status = "unknown"
        self.jarvis_status = "unknown"
        self.github_status = "unknown"
        self.last_update = None

    async def update_status(self) -> None:
        """Update status from actual system health."""
        # This would call health endpoints
        # For now, mock the status
        self.gateway_status = "running"
        self.jarvis_status = "connected"
        self.github_status = "connected"
        self.last_update = datetime.now()

    def render(self, compact: bool = False) -> str:
        """Render the status bar.

        Args:
            compact: Whether to render in compact mode

        Returns:
            Rendered status bar string
        """
        gateway = status_indicator(self.gateway_status)
        jarvis = status_indicator(self.jarvis_status)
        github = status_indicator(self.github_status)

        if compact:
            return f"Gateway:{gateway} JARVIS:{jarvis} GitHub:{github}"

        return (
            f"Gateway: {gateway} {'Running' if self.gateway_status == 'running' else 'Unknown'}  "
            f"JARVIS: {jarvis} {'Connected' if self.jarvis_status == 'connected' else 'Disconnected'}  "
            f"GitHub: {github} {'Connected' if self.github_status == 'connected' else 'Disconnected'}"
        )


# Global status bar instance
_status_bar = StatusBar()


def get_status_bar() -> StatusBar:
    """Get the global status bar instance.

    Returns:
        StatusBar instance
    """
    return _status_bar


def print_status_bar(compact: bool = False) -> None:
    """Print the status bar to stdout.

    Args:
        compact: Whether to print in compact mode
    """
    bar = get_status_bar()
    print(dim(bar.render(compact)))
