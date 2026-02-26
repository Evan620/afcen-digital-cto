"""Code Review screen — trigger reviews via chat agent hint."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from src.tui.backend_client import get_backend_client
from src.tui.utils.visual import (
    BrandColors,
    brand,
    cto,
    draw_header_bar,
    draw_logo,
    draw_section_header,
    gold,
    muted,
    status_icon,
    success,
    warning,
)
from src.tui.utils.navigation import clear_screen, pause

logger = logging.getLogger(__name__)


def _request_review(pr_ref: str) -> dict[str, Any] | None:
    """Send a code review request via the chat endpoint with Code Review hint."""
    client = get_backend_client()
    try:
        return asyncio.run(
            client.chat(
                message=f"Please review this pull request: {pr_ref}",
                agent_hint="Code Review",
            )
        )
    except (httpx.ConnectError, httpx.TimeoutException, OSError):
        return None
    except httpx.HTTPStatusError as e:
        logger.debug("Review request failed: %s", e)
        return None


def _show_unreachable() -> None:
    print()
    print(f"     {status_icon('error')} {warning('Backend Unreachable')}")
    print()
    print(f"     Start the backend with:")
    print(f"       {muted('docker compose up -d')}")
    print()
    pause("    Press Enter to go back...")


def show_code_review_screen() -> None:
    """Code Review main screen — prompt for PR, display result."""
    while True:
        clear_screen()
        draw_logo()
        draw_header_bar("Code Review Agent")

        print()
        print(f"  {cto('[1]', BrandColors.SUNRISE_ORANGE)} Review a Pull Request")
        print(f"  {muted('[q] Back')}")
        print()

        try:
            choice = input(cto("  Select: ", BrandColors.SUNRISE_ORANGE)).strip().lower()
        except (KeyboardInterrupt, EOFError):
            return

        if choice in ("q", "quit", "exit", ""):
            return
        elif choice == "1":
            _review_pr_interactive()


def _review_pr_interactive() -> None:
    """Interactive flow: ask for PR reference, submit review, display result."""
    print()
    print(muted("  Enter a PR URL or owner/repo#number (e.g. afcen/platform#42)"))
    print()

    try:
        pr_ref = input(brand("  PR: ")).strip()
    except (KeyboardInterrupt, EOFError):
        return

    if not pr_ref:
        print(warning("  No PR specified."))
        pause("    Press Enter to continue...")
        return

    print()
    print(muted(f"  Requesting review for {pr_ref} (this may take a moment)..."))

    result = _request_review(pr_ref)

    if result is None:
        _show_unreachable()
        return

    clear_screen()
    draw_logo()
    draw_header_bar("Code Review Result")

    response = result.get("response", "")
    agent = result.get("agent", "Code Review")

    draw_section_header(f"Review by {agent}")
    print()

    for line in response.split("\n"):
        print(f"     {line}")

    print()
    pause("    Press Enter to go back...")


def quick_review(pr_ref: str) -> str | None:
    """CLI quick-mode: request a review and return the text result.

    Returns None if backend is unreachable.
    """
    result = _request_review(pr_ref)
    if result is None:
        return None
    return result.get("response", "")
