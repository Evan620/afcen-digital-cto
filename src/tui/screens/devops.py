"""DevOps screen — pipeline status and reports."""

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


def _show_pipeline_status() -> None:
    """Show pipeline status from backend."""
    clear_screen()
    draw_logo()
    draw_header_bar("Pipeline Status")

    data = _fetch(get_backend_client().devops_status())
    if data is None:
        _show_unreachable()
        return

    devops = data.get("devops", {})

    if isinstance(devops, str):
        print()
        print(f"     {devops}")
    elif isinstance(devops, dict):
        repos = devops.get("repositories", devops.get("repos", {}))
        if isinstance(repos, dict):
            for repo, info in repos.items():
                draw_section_header(repo)
                if isinstance(info, dict):
                    for k, v in info.items():
                        label = k.replace("_", " ").title()
                        if isinstance(v, bool):
                            icon = status_icon("running" if v else "error")
                            print(f"       {icon} {label}")
                        else:
                            print(f"       {label}: {v}")
                else:
                    print(f"       {info}")
        elif isinstance(repos, list):
            for item in repos:
                if isinstance(item, dict):
                    name = item.get("name", item.get("repo", "unknown"))
                    st = item.get("status", "unknown")
                    icon = status_icon("running" if st in ("ok", "success", "passing") else "error")
                    print(f"     {icon} {name}: {st}")
                else:
                    print(f"     - {item}")

        # Show any top-level status fields
        for key in ("overall_status", "success_rate", "total_workflows", "failed_workflows"):
            if key in devops:
                label = key.replace("_", " ").title()
                val = devops[key]
                print(f"     {label}: {gold(str(val))}")
    else:
        print(f"     {devops}")

    print()
    pause("    Press Enter to go back...")


def _show_report() -> None:
    """Show full DevOps health report."""
    clear_screen()
    draw_logo()
    draw_header_bar("DevOps Report")

    print()
    print(muted("     Generating report (this may take a moment)..."))

    data = _fetch(get_backend_client().devops_report())
    if data is None:
        _show_unreachable()
        return

    report = data.get("report", {})

    clear_screen()
    draw_logo()
    draw_header_bar("DevOps Report")

    if isinstance(report, str):
        print()
        print(f"     {report}")
    elif isinstance(report, dict):
        for key, val in report.items():
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
                    print(f"       {k.replace('_', ' ').title()}: {v}")
            else:
                print(f"       {val}")
    else:
        print(f"     {report}")

    print()
    pause("    Press Enter to go back...")


def show_devops_screen() -> None:
    """DevOps main screen with sub-menu."""
    while True:
        clear_screen()
        draw_logo()
        draw_header_bar("DevOps & CI/CD")

        print()
        print(f"  {cto('[1]', BrandColors.SUNRISE_ORANGE)} Pipeline Status")
        print(f"  {cto('[2]', BrandColors.SUNRISE_ORANGE)} Full Report")
        print(f"  {muted('[q] Back')}")
        print()

        try:
            choice = input(cto("  Select: ", BrandColors.SUNRISE_ORANGE)).strip().lower()
        except (KeyboardInterrupt, EOFError):
            return

        if choice in ("q", "quit", "exit", ""):
            return
        elif choice == "1":
            _show_pipeline_status()
        elif choice == "2":
            _show_report()
