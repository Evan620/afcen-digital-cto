"""Main TUI entry point - coordinates all TUI functionality."""

from __future__ import annotations

import logging
import sys

from src.tui.onboard.config import is_onboarded
from src.tui.onboard.wizard import run_wizard
from src.tui.screens.menu import MainMenu, main_menu_loop
from src.tui.utils.visual import (
    BrandColors,
    brand,
    cto,
    draw_box,
    draw_header_bar,
    draw_logo,
    gold,
    header_box,
    muted,
    status_icon,
    success,
    warning,
)

logger = logging.getLogger(__name__)


def main() -> int:
    """Main entry point for the Digital CTO TUI.

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    try:
        # Check if onboarding is needed
        if not is_onboarded():
            print()
            draw_logo()
            print()
            print(brand("Welcome to AfCEN Digital CTO!"))
            print()
            print(muted("It looks like this is your first time."))
            print()
            print(cto("Let's get you set up...", BrandColors.SUNRISE_ORANGE))
            print()

            config = run_wizard()
            if config is None:
                print()
                print(warning("Setup cancelled. Run 'cto' again when you're ready."))
                return 1

        # Show main menu
        main_menu_loop()

        return 0

    except KeyboardInterrupt:
        print()
        print()
        print(muted("Goodbye! 👋"))
        print()
        return 0

    except Exception as e:
        logger.error("TUI error: %s", e)
        print()
        print(cto(f"An error occurred: {e}", BrandColors.ERROR))
        return 1


def cmd_onboard(force: bool = False) -> int:
    """Run the onboarding wizard.

    Args:
        force: Force re-running onboarding

    Returns:
        Exit code
    """
    # Clear screen to avoid confusion with old terminal scrollback
    print("\033[2J\033[H", end="", flush=True)
    print()
    draw_logo()
    draw_header_bar("Onboarding Wizard")
    print()

    config = run_wizard(force=force)

    if config is None:
        print()
        print(warning("Onboarding cancelled."))
        return 1

    print()
    print(success("✅ Onboarding complete!"))
    print()
    return 0


def cmd_status() -> int:
    """Show system status.

    Returns:
        Exit code
    """
    from src.tui.screens.status import show_status_dashboard

    show_status_dashboard()
    return 0


def cmd_chat() -> int:
    """Open the chat interface.

    Returns:
        Exit code
    """
    from src.tui.screens.chat import show_chat_screen

    show_chat_screen()
    return 0


def cmd_logs() -> int:
    """Open the log viewer.

    Returns:
        Exit code
    """
    from src.tui.screens.logs import show_log_viewer

    show_log_viewer()
    return 0


def cmd_config() -> int:
    """Show or edit configuration.

    Returns:
        Exit code
    """
    from src.tui.onboard.config import CONFIG_FILE, load_config

    config = load_config()

    print()
    print(brand("📝 Digital CTO Configuration"))
    print()
    print(muted(f"Config file: {CONFIG_FILE}"))
    print()

    # Show current config
    print(f"  {cto('Version:', BrandColors.BOLD_TEXT)} {config.version}")
    print(f"  {cto('Onboarded:', BrandColors.BOLD_TEXT)} {status_icon('ready') if config.onboarded else muted('No')}")
    print(f"  {cto('LLM Provider:', BrandColors.BOLD_TEXT)} {gold(config.llm.provider.upper())}")
    print(f"  {cto('GitHub Repos:', BrandColors.BOLD_TEXT)} {', '.join(config.github.repos) or muted('None')}")

    # Agent status
    print()
    print(brand("  Agents:"))
    agents = config.agents
    print(f"    {status_icon('ready' if agents.code_review.enabled else 'disabled')} Code Review: {brand('Enabled') if agents.code_review.enabled else muted('Disabled')}")
    print(f"    {status_icon('ready' if agents.sprint_planner.enabled else 'disabled')} Sprint Planner: {brand('Enabled') if agents.sprint_planner.enabled else muted('Disabled')}")
    print(f"    {status_icon('ready' if agents.architecture_advisor.enabled else 'disabled')} Architecture: {brand('Enabled') if agents.architecture_advisor.enabled else muted('Disabled')}")
    print(f"    {status_icon('ready' if agents.devops.enabled else 'disabled')} DevOps: {brand('Enabled') if agents.devops.enabled else muted('Disabled')}")

    print()
    print(muted("Use 'cto onboard' to reconfigure or edit the file directly."))
    print()

    return 0


def cmd_doctor() -> int:
    """Run diagnostics on the Digital CTO system.

    Returns:
        Exit code (0 if healthy, 1 if issues found)
    """
    print()
    draw_logo()
    draw_header_bar("System Health Check")
    print()

    issues = []

    # Check configuration
    from src.tui.onboard.config import load_config, CONFIG_FILE

    if not CONFIG_FILE.exists():
        issues.append("Configuration file not found. Run 'cto onboard'.")
    else:
        config = load_config()

        # Check LLM provider
        if config.llm.provider == "none":
            issues.append("No LLM provider configured.")

        # GitHub token is now in .env, not in TUI config

        # Check repos
        if config.github.repos:
            print(f"  {status_icon('connected')} Monitoring {gold(str(len(config.github.repos)))} repositories")
        else:
            print(f"  {status_icon('warning')} No repositories configured")

    # Check services
    print()
    print(cto("Checking services...", BrandColors.INFO))

    import asyncio

    async def check_health():
        try:
            from src.health import get_deep_health_status
            health = await get_deep_health_status()

            if health.get("gateway", {}).get("status") == "healthy":
                print(f"  {status_icon('running')} Gateway API is reachable")
            else:
                issues.append("Gateway API is not responding")

            # Check memory stores
            for store, status_data in health.get("stores", {}).items():
                if status_data.get("status") == "healthy":
                    print(f"  {status_icon('running')} {store} is connected")
                else:
                    issues.append(f"{store} is not responding")

        except Exception as e:
            issues.append(f"Health check failed: {e}")

    asyncio.run(check_health())

    # Results
    print()
    if issues:
        print(cto("Issues found:", BrandColors.ERROR))
        for issue in issues:
            print(f"  {cto('•', BrandColors.ERROR)} {issue}")
        print()
        return 1
    else:
        print(success("✓ All systems healthy!"))
        print()
        return 0
