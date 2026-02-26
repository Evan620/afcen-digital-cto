"""Market Scanner screen — status, intel, scan, morning brief."""

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


def _show_status() -> None:
    """Show market scanner status."""
    clear_screen()
    draw_logo()
    draw_header_bar("Market Scanner Status")

    data = _fetch(get_backend_client().market_status())
    if data is None:
        _show_unreachable()
        return

    scanner = data.get("market_scanner", {})

    if isinstance(scanner, str):
        print()
        print(f"     {scanner}")
    elif isinstance(scanner, dict):
        for key, val in scanner.items():
            label = key.replace("_", " ").title()
            if isinstance(val, dict):
                draw_section_header(label)
                for k, v in val.items():
                    print(f"       {k.replace('_', ' ').title()}: {v}")
            elif isinstance(val, list):
                draw_section_header(label)
                for item in val:
                    print(f"       - {item}")
            else:
                print(f"     {label}: {gold(str(val))}")
    else:
        print(f"     {scanner}")

    print()
    pause("    Press Enter to go back...")


def _show_intel() -> None:
    """Show recent market intelligence."""
    clear_screen()
    draw_logo()
    draw_header_bar("Market Intelligence")

    data = _fetch(get_backend_client().market_intel())
    if data is None:
        _show_unreachable()
        return

    intel = data.get("intel", [])
    count = data.get("count", len(intel))

    draw_section_header(f"Recent Intel ({count} items)")

    if not intel:
        print()
        print(muted("     No intelligence items found."))
    else:
        for item in intel[:20]:
            if isinstance(item, dict):
                title = item.get("title", item.get("headline", "Unknown"))
                source = item.get("source", "")
                relevance = item.get("relevance_score", item.get("relevance", ""))
                print()
                print(f"     {brand(title)}")
                extras = []
                if source:
                    extras.append(f"Source: {source}")
                if relevance:
                    extras.append(f"Relevance: {gold(str(relevance))}")
                if extras:
                    print(f"       {muted('  |  '.join(extras))}")
            else:
                print(f"     - {item}")

    print()
    pause("    Press Enter to go back...")


def _trigger_scan() -> None:
    """Trigger a market data collection scan."""
    clear_screen()
    draw_logo()
    draw_header_bar("Market Scan")

    print()
    print(muted("     Triggering market data collection (this may take a moment)..."))

    data = _fetch(get_backend_client().market_scan())
    if data is None:
        _show_unreachable()
        return

    result = data.get("result", {})

    clear_screen()
    draw_logo()
    draw_header_bar("Scan Results")

    if isinstance(result, dict):
        draw_section_header("Collection Summary")
        for key, val in result.items():
            label = key.replace("_", " ").title()
            if isinstance(val, list):
                print(f"     {label}: {gold(str(len(val)))} items")
                for item in val[:5]:
                    print(f"       - {item}")
            else:
                print(f"     {label}: {gold(str(val))}")
    else:
        print(f"     {result}")

    print()
    pause("    Press Enter to go back...")


def _show_morning_brief_full() -> None:
    """Generate and display a full morning brief."""
    clear_screen()
    draw_logo()
    draw_header_bar("Morning Brief")

    print()
    print(muted("     Generating morning brief (this may take a moment)..."))

    data = _fetch(get_backend_client().market_brief())
    if data is None:
        _show_unreachable()
        return

    brief = data.get("brief", {})

    clear_screen()
    draw_logo()
    draw_header_bar("Morning Brief")

    if isinstance(brief, str):
        print()
        print(f"     {brief}")
    elif isinstance(brief, dict):
        # Market moves
        moves = brief.get("market_moves", [])
        if moves:
            draw_section_header("Market Moves")
            for m in moves:
                if isinstance(m, dict):
                    print(f"     {brand(m.get('title', m.get('description', 'Unknown')))}")
                    if m.get("impact"):
                        print(f"       Impact: {m['impact']}")
                else:
                    print(f"     - {m}")

        # Policy updates
        policies = brief.get("policy_updates", [])
        if policies:
            draw_section_header("Policy Updates")
            for p in policies:
                if isinstance(p, dict):
                    print(f"     {brand(p.get('title', p.get('description', 'Unknown')))}")
                else:
                    print(f"     - {p}")

        # Funding
        funding = brief.get("funding_opportunities", [])
        if funding:
            draw_section_header("Funding Opportunities")
            for f in funding:
                if isinstance(f, dict):
                    print(f"     {gold(f.get('title', f.get('name', 'Unknown')))}")
                    if f.get("amount"):
                        print(f"       Amount: {f['amount']}")
                    if f.get("deadline"):
                        print(f"       Deadline: {f['deadline']}")
                else:
                    print(f"     - {f}")

        # Competitive intelligence
        comp = brief.get("competitive_intelligence", "")
        if comp:
            draw_section_header("Competitive Intelligence")
            if isinstance(comp, str):
                print(f"     {comp}")
            elif isinstance(comp, list):
                for c in comp:
                    print(f"     - {c}")

        # Recommended actions
        actions = brief.get("recommended_actions", [])
        if actions:
            draw_section_header("Recommended Actions")
            for a in actions:
                if isinstance(a, dict):
                    print(f"     {success('>')} {a.get('action', a.get('description', 'Unknown'))}")
                    if a.get("priority"):
                        print(f"       Priority: {gold(a['priority'])}")
                else:
                    print(f"     {success('>')} {a}")

        # Stats
        collected = brief.get("intel_items_collected", "")
        if collected:
            print()
            print(muted(f"     Intel items collected: {collected}"))
    else:
        print(f"     {brief}")

    print()
    pause("    Press Enter to go back...")


def show_morning_brief() -> None:
    """Quick entry point for morning brief (used by menu item 4)."""
    _show_morning_brief_full()


def show_market_screen() -> None:
    """Market Scanner main screen with sub-menu."""
    while True:
        clear_screen()
        draw_logo()
        draw_header_bar("Market Scanner")

        print()
        print(f"  {cto('[1]', BrandColors.SUNRISE_ORANGE)} Status")
        print(f"  {cto('[2]', BrandColors.SUNRISE_ORANGE)} Recent Intel")
        print(f"  {cto('[3]', BrandColors.SUNRISE_ORANGE)} Trigger Scan")
        print(f"  {cto('[4]', BrandColors.SUNRISE_ORANGE)} Morning Brief")
        print(f"  {muted('[q] Back')}")
        print()

        try:
            choice = input(cto("  Select: ", BrandColors.SUNRISE_ORANGE)).strip().lower()
        except (KeyboardInterrupt, EOFError):
            return

        if choice in ("q", "quit", "exit", ""):
            return
        elif choice == "1":
            _show_status()
        elif choice == "2":
            _show_intel()
        elif choice == "3":
            _trigger_scan()
        elif choice == "4":
            _show_morning_brief_full()


def quick_brief() -> str | None:
    """CLI quick-mode: generate brief and return text.

    Returns None if backend is unreachable.
    """
    data = _fetch(get_backend_client().market_brief())
    if data is None:
        return None
    brief = data.get("brief", {})
    if isinstance(brief, str):
        return brief
    if isinstance(brief, dict):
        parts = []
        for key, val in brief.items():
            parts.append(f"## {key.replace('_', ' ').title()}")
            if isinstance(val, list):
                for item in val:
                    if isinstance(item, dict):
                        parts.append(f"  - {item.get('title', item.get('description', str(item)))}")
                    else:
                        parts.append(f"  - {item}")
            elif isinstance(val, str):
                parts.append(f"  {val}")
            else:
                parts.append(f"  {val}")
        return "\n".join(parts)
    return str(brief)
