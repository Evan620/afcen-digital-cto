"""Chat interface for interacting with Digital CTO agents.

Delegates all intelligence to the Docker backend via HTTP.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING

import httpx

from src.tui.backend_client import get_backend_client
from src.tui.onboard.config import load_config
from src.tui.utils.visual import (
    BrandColors,
    agent_styled,
    brand,
    cto,
    draw_header_bar,
    draw_logo,
    draw_section_header,
    muted,
    success,
    warning,
)
from src.tui.utils.navigation import CommandHistory, clear_screen, edit_text

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ChatMessage:
    """A message in the chat conversation."""

    def __init__(
        self,
        role: str,
        content: str,
        agent: str = "System",
        timestamp: datetime | None = None,
    ):
        """Initialize a chat message.

        Args:
            role: Message role (user, assistant, system)
            content: Message content
            agent: Agent name (for assistant messages)
            timestamp: Message timestamp
        """
        self.role = role
        self.content = content
        self.agent = agent
        self.timestamp = timestamp or datetime.now()

    def format(self) -> str:
        """Format the message for display.

        Returns:
            Formatted message string
        """
        ts = self.timestamp.strftime("%H:%M:%S")

        if self.role == "user":
            return f"{muted(ts)}  {cto('You:', BrandColors.BOLD_TEXT)}\n  {self.content}"

        elif self.role == "assistant":
            agent_emoji = {
                "Sprint Planner": "📊",
                "Code Review": "🔍",
                "Architecture Advisor": "🏗️",
                "DevOps": "🔧",
                "Market Scanner": "📈",
                "Meeting Intelligence": "👥",
                "Supervisor": "🧠",
                "Coding": "💻",
            }.get(self.agent, "🤖")

            styled_agent = agent_styled(self.agent, self.agent)
            return f"\n{muted(ts)}  {agent_emoji} {styled_agent}:\n  {self.content}\n"

        else:
            return f"{muted(ts)}  {muted(self.content)}"


class ChatScreen:
    """Interactive chat screen for agent communication."""

    def __init__(self):
        """Initialize the chat screen."""
        self.config = load_config()
        self.messages: list[ChatMessage] = []
        self.history = CommandHistory()
        self.current_agent = "Auto"  # Auto-selects based on query
        self.running = True
        self.logo_drawn = False

        # Available agents
        self.agents = ["Auto", "Code Review", "Sprint", "Arch", "DevOps", "Market", "Meeting"]

    def add_message(self, role: str, content: str, agent: str = "System") -> None:
        """Add a message to the conversation.

        Args:
            role: Message role
            content: Message content
            agent: Agent name
        """
        msg = ChatMessage(role, content, agent)
        self.messages.append(msg)

    def draw_header(self) -> None:
        """Draw the chat header."""
        if not self.logo_drawn:
            # Only draw logo once at the start
            draw_logo()
            draw_header_bar("Agent Chat Interface")
            self.logo_drawn = True
        else:
            # Just draw a simple header for refreshes
            print()
            print(cto("💬 Chat with Digital CTO Agents", BrandColors.SUNRISE_ORANGE, BrandColors.BOLD_TEXT))
            print(cto("─" * 70, BrandColors.SUNRISE_ORANGE))
            print()

    def draw_conversation(self, lines: int = 10) -> None:
        """Draw the conversation history.

        Args:
            lines: Number of lines of history to show
        """
        draw_section_header("Conversation")

        if not self.messages:
            print(muted("  No messages yet. Start the conversation!"))
            return

        # Show last N messages
        for msg in self.messages[-lines:]:
            print(f"  {msg.format()}")

    def draw_agent_selector(self) -> None:
        """Draw the agent selector bar."""
        print()
        agents_display = " ".join(
            f"{cto(f'[{a}]', BrandColors.SUNRISE_ORANGE, BrandColors.BOLD_TEXT)}" if a == self.current_agent else f"[{a}]"
            for a in self.agents
        )
        print(f"  {agents_display}")
        print()

    def draw_input_prompt(self) -> str:
        """Draw the input prompt and get user input.

        Returns:
            User input string
        """
        try:
            prompt = f"  {brand('Your message:')}: "
            response = input(prompt).strip()

            if response:
                self.history.add(response)

            return response

        except (KeyboardInterrupt, EOFError):
            self.running = False
            return ""

    async def process_message(self, message: str) -> tuple[str, str]:
        """Process a user message by sending it to the backend.

        Args:
            message: User's message

        Returns:
            Tuple of (response content, agent name)
        """
        client = get_backend_client()

        # Map current_agent selector to agent_hint for backend
        agent_hint = self.current_agent if self.current_agent != "Auto" else None

        try:
            result = await client.chat(
                message=message,
                agent_hint=agent_hint,
            )
            return result.get("response", ""), result.get("agent", "Supervisor")

        except httpx.ConnectError:
            return (
                f"{warning('⚠ Backend not reachable.')}\n\n"
                f"Start the backend with:\n"
                f"  {muted('docker compose up -d')}\n\n"
                f"Or check your backend URL in {muted('~/.digital-cto/config.json')}",
                "System",
            )
        except httpx.TimeoutException:
            return (
                f"{warning('⚠ Request timed out.')}\n\n"
                f"The agent is taking too long to respond. Try again or check backend logs.",
                "System",
            )
        except httpx.HTTPStatusError as e:
            detail = ""
            try:
                detail = e.response.json().get("detail", "")
            except Exception:
                detail = e.response.text[:200]
            return (
                f"{warning(f'⚠ Backend error (HTTP {e.response.status_code})')}\n\n"
                f"{muted(detail)}",
                "System",
            )

    def run(self) -> None:
        """Run the chat interface."""
        clear_screen()

        # No welcome message - let the user start the conversation

        while self.running:
            self.draw_header()
            self.draw_conversation()
            self.draw_agent_selector()

            message = self.draw_input_prompt()

            if not message:
                continue

            # Add user message
            self.add_message("user", message)

            # Get agent response
            response, agent = asyncio.run(self.process_message(message))

            # Add assistant response
            self.add_message("assistant", response, agent)

            # Clear and redraw
            clear_screen()


def show_chat_screen() -> None:
    """Display the chat interface."""
    chat = ChatScreen()
    chat.run()
