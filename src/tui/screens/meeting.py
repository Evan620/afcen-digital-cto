"""Meeting Intelligence screen — status and transcript analysis."""

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
    """Show meeting intelligence status."""
    clear_screen()
    draw_logo()
    draw_header_bar("Meeting Intelligence Status")

    data = _fetch(get_backend_client().meeting_status())
    if data is None:
        _show_unreachable()
        return

    mi = data.get("meeting_intelligence", {})

    draw_section_header("Overview")
    recent = mi.get("recent_meetings", 0)
    outstanding = mi.get("outstanding_actions", 0)
    recall = mi.get("recall_configured", False)

    print(f"     Recent meetings (30d): {gold(str(recent))}")
    print(f"     Outstanding actions:   {warning(str(outstanding)) if outstanding else success('0')}")
    print(f"     Recall.ai:             {status_icon('running' if recall else 'disabled')} {'Configured' if recall else 'Not configured'}")

    meetings_list = mi.get("recent_meetings_list", [])
    if meetings_list:
        draw_section_header("Recent Meetings")
        for m in meetings_list:
            title = m.get("title", "Unknown")
            date = m.get("date", "")[:10] if m.get("date") else ""
            participants = m.get("participants", [])
            p_str = ", ".join(participants[:3]) if participants else ""
            if len(participants) > 3:
                p_str += f" +{len(participants) - 3}"
            print(f"     {brand(title)}  {muted(date)}")
            if p_str:
                print(f"       {muted(p_str)}")

    print()
    pause("    Press Enter to go back...")


def _analyze_transcript() -> None:
    """Prompt for transcript text and analyze it."""
    print()
    print(muted("  Paste your meeting transcript below."))
    print(muted("  Enter a blank line when done."))
    print()

    lines = []
    try:
        while True:
            line = input()
            if line == "":
                break
            lines.append(line)
    except (KeyboardInterrupt, EOFError):
        if not lines:
            return

    transcript = "\n".join(lines)
    if not transcript.strip():
        print(warning("  No transcript provided."))
        pause("    Press Enter to continue...")
        return

    print()
    try:
        title = input(brand("  Meeting title: ")).strip() or "Unknown Meeting"
        participants_raw = input(brand("  Participants (comma-separated): ")).strip()
    except (KeyboardInterrupt, EOFError):
        return

    participants = [p.strip() for p in participants_raw.split(",") if p.strip()] if participants_raw else []

    print()
    print(muted("  Analyzing transcript (this may take a moment)..."))

    data = _fetch(get_backend_client().meeting_analyze(
        transcript=transcript,
        title=title,
        participants=participants,
    ))

    if data is None:
        _show_unreachable()
        return

    analysis = data.get("analysis", {})

    clear_screen()
    draw_logo()
    draw_header_bar("Meeting Analysis")

    if isinstance(analysis, str):
        print()
        print(f"     {analysis}")
    elif isinstance(analysis, dict):
        mtitle = analysis.get("title", title)
        print()
        print(f"     {brand(mtitle)}")

        summary = analysis.get("summary", "")
        if summary:
            draw_section_header("Summary")
            print(f"     {summary}")

        decisions = analysis.get("key_decisions", [])
        if decisions:
            draw_section_header("Key Decisions")
            for d in decisions:
                print(f"     {success('>')} {d}")

        actions = analysis.get("action_items", [])
        if actions:
            draw_section_header("Action Items")
            for a in actions:
                if isinstance(a, dict):
                    owner = a.get("owner", a.get("assignee", ""))
                    desc = a.get("description", a.get("action", str(a)))
                    print(f"     {gold('*')} {desc}")
                    if owner:
                        print(f"       Owner: {owner}")
                else:
                    print(f"     {gold('*')} {a}")

        topics = analysis.get("technical_topics", [])
        if topics:
            draw_section_header("Technical Topics")
            for t in topics:
                print(f"     - {t}")

        pains = analysis.get("pain_points", [])
        if pains:
            draw_section_header("Pain Points")
            for p in pains:
                print(f"     {warning('!')} {p}")

        opps = analysis.get("opportunities", [])
        if opps:
            draw_section_header("Opportunities")
            for o in opps:
                print(f"     {success('+')} {o}")
    else:
        print(f"     {analysis}")

    print()
    pause("    Press Enter to go back...")


def show_meeting_screen() -> None:
    """Meeting Intelligence main screen with sub-menu."""
    while True:
        clear_screen()
        draw_logo()
        draw_header_bar("Meeting Intelligence")

        print()
        print(f"  {cto('[1]', BrandColors.SUNRISE_ORANGE)} Status")
        print(f"  {cto('[2]', BrandColors.SUNRISE_ORANGE)} Analyze Transcript")
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
            _analyze_transcript()
