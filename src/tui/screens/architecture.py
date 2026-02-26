"""Architecture Advisor screen — query and view decisions."""

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


def _fetch(coro) -> dict[str, Any] | None:
    try:
        return asyncio.run(coro)
    except (httpx.ConnectError, httpx.TimeoutException, OSError):
        return None
    except httpx.HTTPStatusError as e:
        logger.debug("Backend HTTP error: %s", e)
        return None


def _show_unreachable() -> None:
    print()
    print(f"     {status_icon('error')} {warning('Backend Unreachable')}")
    print()
    print(f"     Start the backend with:")
    print(f"       {muted('docker compose up -d')}")
    print()
    pause("    Press Enter to go back...")


def _ask_question() -> None:
    """Prompt user for an architecture question, submit to backend."""
    print()
    print(muted("  Describe your architecture question or technology to evaluate:"))
    print()

    try:
        query = input(brand("  Question: ")).strip()
    except (KeyboardInterrupt, EOFError):
        return

    if not query:
        print(warning("  No question provided."))
        pause("    Press Enter to continue...")
        return

    print()
    print(muted("  Querying Architecture Advisor (this may take a moment)..."))

    data = _fetch(get_backend_client().architecture_query(query))

    if data is None:
        _show_unreachable()
        return

    rec = data.get("recommendation", {})

    clear_screen()
    draw_logo()
    draw_header_bar("Architecture Recommendation")

    if isinstance(rec, str):
        print()
        print(f"     {rec}")
    elif isinstance(rec, dict):
        for key, val in rec.items():
            draw_section_header(key.replace("_", " ").title())
            if isinstance(val, list):
                for item in val:
                    if isinstance(item, dict):
                        for k, v in item.items():
                            print(f"       {k}: {v}")
                        print()
                    else:
                        print(f"       - {item}")
            elif isinstance(val, dict):
                for k, v in val.items():
                    print(f"       {k}: {v}")
            else:
                print(f"       {val}")
    else:
        print(f"     {rec}")

    print()
    pause("    Press Enter to go back...")


def _view_decisions() -> None:
    """Show recent architecture decisions."""
    clear_screen()
    draw_logo()
    draw_header_bar("Architecture Decisions")

    data = _fetch(get_backend_client().architecture_decisions())

    if data is None:
        _show_unreachable()
        return

    decisions = data.get("decisions", [])

    if not decisions:
        print()
        print(muted("     No architecture decisions recorded yet."))
        print()
        pause("    Press Enter to go back...")
        return

    draw_section_header(f"Recent Decisions ({len(decisions)})")

    for d in decisions:
        dtype = d.get("decision_type", "unknown")
        reasoning = d.get("reasoning", "")
        outcome = d.get("outcome", "")
        created = d.get("created_at", "")[:10] if d.get("created_at") else ""

        print()
        print(f"     {gold(dtype.replace('_', ' ').title())}  {muted(created)}")
        if reasoning:
            print(f"       Reasoning: {reasoning[:120]}{'...' if len(reasoning) > 120 else ''}")
        if outcome:
            print(f"       Outcome:   {outcome[:120]}{'...' if len(outcome) > 120 else ''}")

    print()
    pause("    Press Enter to go back...")


def show_architecture_screen() -> None:
    """Architecture Advisor main screen with sub-menu."""
    while True:
        clear_screen()
        draw_logo()
        draw_header_bar("Architecture Advisor")

        print()
        print(f"  {cto('[1]', BrandColors.SUNRISE_ORANGE)} Ask a Question")
        print(f"  {cto('[2]', BrandColors.SUNRISE_ORANGE)} Recent Decisions")
        print(f"  {muted('[q] Back')}")
        print()

        try:
            choice = input(cto("  Select: ", BrandColors.SUNRISE_ORANGE)).strip().lower()
        except (KeyboardInterrupt, EOFError):
            return

        if choice in ("q", "quit", "exit", ""):
            return
        elif choice == "1":
            _ask_question()
        elif choice == "2":
            _view_decisions()
