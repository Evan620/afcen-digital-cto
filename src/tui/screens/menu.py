"""Main menu screen for the Digital CTO TUI with enhanced visual styling."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from src.tui.onboard.config import load_config
from src.tui.utils.visual import (
    BrandColors,
    agent_styled,
    brand,
    cto,
    draw_box,
    draw_header_bar,
    draw_logo,
    draw_section_header,
    draw_progress_bar,
    gold,
    header_box,
    menu_item,
    muted,
    status_icon,
    success,
    warning,
)
from src.tui.utils.navigation import clear_screen

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class MainMenu:
    """Main menu screen for the Digital CTO TUI."""

    def __init__(self):
        """Initialize the main menu."""
        self.config = load_config()
        self.running = True

    def draw(self) -> None:
        """Draw the complete main menu."""
        clear_screen()
        self.draw_header()
        self.draw_system_status()
        self.draw_quick_actions()
        self.draw_agents_menu()
        self.draw_system_menu()
        self.draw_footer()

    def draw_header(self) -> None:
        """Draw the menu header with logo."""
        draw_logo()
        draw_header_bar(f"AfCEN Digital CTO                        {muted(f'v{self.config.version}')}")

    def draw_system_status(self) -> None:
        """Draw the system status bar."""
        # Status indicators
        gateway = status_icon("running") + " " + brand("Running")
        agents = status_icon("active") + " " + brand("All Agents Active")
        github = status_icon("connected") + " " + brand("Connected")
        jarvis = status_icon("online") + " " + brand("Online")

        print()
        print(f"     {gateway}    {agents}")
        print(f"     {github}    {jarvis}")

    def draw_quick_actions(self) -> None:
        """Draw quick action options."""
        draw_section_header("Quick Actions")

        options = [
            (1, "Chat with Agents", "Interactive conversation with all agents"),
            (2, "Review PR", "Request code review for a pull request"),
            (3, "Sprint Status", "View current sprint progress and metrics"),
            (4, "Morning Brief", "Generate daily intelligence brief"),
        ]

        for num, text, desc in options:
            print(f"  {menu_item(num, text, desc)}")

    def draw_agents_menu(self) -> None:
        """Draw the agents menu."""
        draw_section_header("Agents")

        agents = [
            (5, "Code Review", "View review history, stats, and settings"),
            (6, "Sprint Planner", "Current sprint, Bayes tracking, reports"),
            (7, "Architecture Advisor", "Query, decisions, tech debt assessment"),
            (8, "DevOps", "Pipeline status, alerts, and reports"),
            (9, "Market Scanner", "Market data, briefs, and intelligence"),
            (10, "Meeting Intelligence", "Meeting analysis and briefs"),
        ]

        for num, text, desc in agents:
            print(f"  {menu_item(num, text, desc)}")

    def draw_system_menu(self) -> None:
        """Draw the system menu."""
        draw_section_header("System")

        options = [
            (11, "Configuration", "Edit Digital CTO settings"),
            (12, "Logs", "View real-time activity logs"),
            (13, "Health Check", "Run system diagnostics"),
            (0, "Exit", "Quit the Digital CTO TUI"),
        ]

        for num, text, desc in options:
            print(f"  {menu_item(num, text, desc)}")

    def draw_footer(self) -> None:
        """Draw the footer with tips."""
        print()
        print(muted("    ──────────────────────────────────────────────────────────"))
        print(muted("    Tip: Use 'cto chat' for direct agent interaction"))
        print(muted("    Tip: Use 'cto status' for quick health check"))
        print()

    def show(self) -> str:
        """Display the main menu and get user selection.

        Returns:
            Selected option identifier
        """
        while self.running:
            self.draw()

            try:
                choice = input(cto("Select option", BrandColors.SUNRISE_ORANGE) + " [0-13]: ").strip()

                if choice == "0":
                    return "exit"
                elif choice == "1":
                    return "chat"
                elif choice == "2":
                    return "review"
                elif choice == "3":
                    return "sprint"
                elif choice == "4":
                    return "brief"
                elif choice == "5":
                    return "agent_code_review"
                elif choice == "6":
                    return "agent_sprint_planner"
                elif choice == "7":
                    return "agent_architecture"
                elif choice == "8":
                    return "agent_devops"
                elif choice == "9":
                    return "agent_market"
                elif choice == "10":
                    return "agent_meeting"
                elif choice == "11":
                    return "config"
                elif choice == "12":
                    return "logs"
                elif choice == "13":
                    return "health"
                else:
                    print()
                    print(warning("  ⚠ Invalid option. Please try again."))
                    print()

            except (KeyboardInterrupt, EOFError):
                print()
                return "exit"


def show_main_menu() -> str:
    """Async wrapper for showing the main menu.

    Returns:
        Selected option identifier
    """
    menu = MainMenu()
    return menu.show()


def main_menu_loop() -> None:
    """Run the main menu event loop.

    This is the primary entry point for the TUI.
    """
    import sys

    from src.tui.screens.status import show_status_dashboard
    from src.tui.screens.logs import show_log_viewer

    menu = MainMenu()

    while True:
        choice = menu.show()

        if choice == "exit":
            print()
            print(brand("Thank you for using AfCEN Digital CTO!"))
            print()
            sys.exit(0)

        elif choice == "chat":
            from src.tui.screens.chat import show_chat_screen
            show_chat_screen()

        elif choice == "status":
            show_status_dashboard()

        elif choice == "logs":
            show_log_viewer()

        elif choice == "health":
            from src.tui.main import cmd_doctor
            cmd_doctor()

        elif choice == "review":
            from src.tui.screens.code_review import show_code_review_screen
            show_code_review_screen()

        elif choice == "sprint":
            from src.tui.screens.sprint import show_sprint_screen
            show_sprint_screen()

        elif choice == "brief":
            from src.tui.screens.market import show_morning_brief
            show_morning_brief()

        elif choice == "agent_code_review":
            from src.tui.screens.code_review import show_code_review_screen
            show_code_review_screen()

        elif choice == "agent_sprint_planner":
            from src.tui.screens.sprint import show_sprint_screen
            show_sprint_screen()

        elif choice == "agent_architecture":
            from src.tui.screens.architecture import show_architecture_screen
            show_architecture_screen()

        elif choice == "agent_devops":
            from src.tui.screens.devops import show_devops_screen
            show_devops_screen()

        elif choice == "agent_market":
            from src.tui.screens.market import show_market_screen
            show_market_screen()

        elif choice == "agent_meeting":
            from src.tui.screens.meeting import show_meeting_screen
            show_meeting_screen()

        elif choice == "config":
            from src.tui.main import cmd_config
            cmd_config()
