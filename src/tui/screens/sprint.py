"""Sprint Planner screen — status, reports, Bayes tracking, retrospective."""

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
    draw_progress_bar,
    draw_section_header,
    gold,
    muted,
    status_icon,
    success,
    warning,
)
from src.tui.utils.navigation import clear_screen, pause

logger = logging.getLogger(__name__)

_BACKEND_DOWN = (
    "\n"
    "     {icon} {msg}\n"
    "\n"
    "     Start the backend with:\n"
    "       {hint}\n"
)


def _fetch(coro) -> dict[str, Any] | None:
    """Run an async backend call, return None on connection error."""
    try:
        return asyncio.run(coro)
    except (httpx.ConnectError, httpx.TimeoutException, OSError):
        return None
    except httpx.HTTPStatusError as e:
        logger.debug("Backend HTTP error: %s", e)
        return None


def _show_unreachable() -> None:
    print(_BACKEND_DOWN.format(
        icon=status_icon("error"),
        msg=warning("Backend Unreachable"),
        hint=muted("docker compose up -d"),
    ))
    pause("    Press Enter to go back...")


# ── Sub-screens ──


def _show_status() -> None:
    """Show sprint status with metrics."""
    clear_screen()
    draw_logo()
    draw_header_bar("Sprint Status")

    data = _fetch(get_backend_client().sprint_status())
    if data is None:
        _show_unreachable()
        return

    metrics = data.get("metrics", {})
    draw_section_header("Current Sprint")

    sprint_name = metrics.get("sprint_name", metrics.get("current_sprint", "N/A"))
    total = metrics.get("total_tasks", 0)
    completed = metrics.get("completed_tasks", 0)
    pct = int((completed / total * 100) if total else 0)
    velocity = metrics.get("velocity", "N/A")
    points = metrics.get("story_points", {})
    blocked = metrics.get("blocked_items", metrics.get("blocked", 0))

    print(f"     Sprint:     {brand(str(sprint_name))}")
    print(f"     Progress:   {completed}/{total} tasks  {draw_progress_bar(pct)}  {gold(f'{pct}%')}")
    print(f"     Velocity:   {gold(str(velocity))} pts/sprint")

    if isinstance(points, dict):
        done = points.get("completed", 0)
        rem = points.get("remaining", 0)
        print(f"     Points:     {success(str(done))} done  /  {muted(str(rem))} remaining")
    elif points:
        print(f"     Points:     {gold(str(points))}")

    if blocked:
        print(f"     Blocked:    {warning(str(blocked))} items")

    print()
    pause("    Press Enter to go back...")


def _show_report() -> None:
    """Show full sprint report."""
    clear_screen()
    draw_logo()
    draw_header_bar("Sprint Report")

    print()
    print(muted("     Generating report (this may take a moment)..."))

    data = _fetch(get_backend_client().sprint_report())
    if data is None:
        _show_unreachable()
        return

    report = data.get("report", {})
    clear_screen()
    draw_logo()
    draw_header_bar("Sprint Report")

    if isinstance(report, str):
        print()
        print(f"     {report}")
    elif isinstance(report, dict):
        for key, val in report.items():
            draw_section_header(key.replace("_", " ").title())
            if isinstance(val, list):
                for item in val:
                    print(f"       - {item}")
            elif isinstance(val, dict):
                for k, v in val.items():
                    print(f"       {k}: {v}")
            else:
                print(f"       {val}")
    else:
        print(f"     {report}")

    print()
    pause("    Press Enter to go back...")


def _show_bayes() -> None:
    """Show Bayes deliverable tracking."""
    clear_screen()
    draw_logo()
    draw_header_bar("Bayes Consulting Tracking")

    data = _fetch(get_backend_client().sprint_bayes())
    if data is None:
        _show_unreachable()
        return

    bayes = data.get("bayes_summary", {})

    if isinstance(bayes, str):
        print()
        print(f"     {bayes}")
    elif isinstance(bayes, dict):
        budget = bayes.get("budget", bayes.get("sow_budget", {}))
        if budget:
            draw_section_header("SOW Budget")
            if isinstance(budget, dict):
                for k, v in budget.items():
                    print(f"       {k.replace('_', ' ').title()}: {gold(str(v))}")
            else:
                print(f"       {budget}")

        deliverables = bayes.get("deliverables", [])
        if deliverables:
            draw_section_header("Deliverables")
            for d in deliverables:
                if isinstance(d, dict):
                    name = d.get("name", d.get("title", "Unknown"))
                    st = d.get("status", "unknown")
                    icon = status_icon("running" if st in ("done", "completed") else "pending")
                    print(f"       {icon} {name}: {st}")
                else:
                    print(f"       - {d}")

        timeline = bayes.get("timeline", {})
        if timeline:
            draw_section_header("Timeline")
            if isinstance(timeline, dict):
                for k, v in timeline.items():
                    print(f"       {k.replace('_', ' ').title()}: {v}")
            else:
                print(f"       {timeline}")
    else:
        print(f"     {bayes}")

    print()
    pause("    Press Enter to go back...")


def _show_retrospective() -> None:
    """Show sprint retrospective."""
    clear_screen()
    draw_logo()
    draw_header_bar("Sprint Retrospective")

    print()
    print(muted("     Generating retrospective (this may take a moment)..."))

    data = _fetch(get_backend_client().sprint_retrospective())
    if data is None:
        _show_unreachable()
        return

    retro = data.get("retrospective", {})
    clear_screen()
    draw_logo()
    draw_header_bar("Sprint Retrospective")

    if isinstance(retro, str):
        print()
        print(f"     {retro}")
    elif isinstance(retro, dict):
        for key, val in retro.items():
            draw_section_header(key.replace("_", " ").title())
            if isinstance(val, list):
                for item in val:
                    print(f"       - {item}")
            else:
                print(f"       {val}")
    else:
        print(f"     {retro}")

    print()
    pause("    Press Enter to go back...")


# ── Main entry point ──


def show_sprint_screen() -> None:
    """Sprint Planner main screen with sub-menu."""
    while True:
        clear_screen()
        draw_logo()
        draw_header_bar("Sprint Planner")

        print()
        print(f"  {cto('[1]', BrandColors.SUNRISE_ORANGE)} Sprint Status")
        print(f"  {cto('[2]', BrandColors.SUNRISE_ORANGE)} Full Report")
        print(f"  {cto('[3]', BrandColors.SUNRISE_ORANGE)} Bayes Tracking")
        print(f"  {cto('[4]', BrandColors.SUNRISE_ORANGE)} Retrospective")
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
            _show_report()
        elif choice == "3":
            _show_bayes()
        elif choice == "4":
            _show_retrospective()
