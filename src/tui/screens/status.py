"""Status dashboard screen — fetches real data from the Docker backend."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

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
    gold,
    muted,
    status_icon,
    success,
    warning,
)
from src.tui.utils.navigation import clear_screen, pause

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def _fetch_health() -> dict[str, Any] | None:
    """Fetch /health from backend (sync wrapper)."""
    client = get_backend_client()
    try:
        return asyncio.run(client.health())
    except (httpx.ConnectError, httpx.TimeoutException, OSError):
        return None
    except Exception as e:
        logger.debug("Health fetch failed: %s", e)
        return None


def _fetch_health_deep() -> dict[str, Any] | None:
    """Fetch /health/deep from backend (sync wrapper)."""
    client = get_backend_client()
    try:
        return asyncio.run(client.health_deep())
    except (httpx.ConnectError, httpx.TimeoutException, OSError):
        return None
    except Exception as e:
        logger.debug("Deep health fetch failed: %s", e)
        return None


def show_status_dashboard() -> None:
    """Display the system status dashboard with real backend data."""
    config = load_config()

    clear_screen()
    draw_logo()
    draw_header_bar("System Health Status")

    # Fetch real data
    health = _fetch_health()
    deep = _fetch_health_deep()

    if health is None:
        # Backend unreachable
        print()
        print(f"     {status_icon('error')} {warning('Backend Unreachable')}")
        print()
        print(muted(f"     Could not connect to {config.backend_url}"))
        print()
        print(brand("     To start the backend:"))
        print(muted("       docker compose up -d"))
        print()
        print(muted("     Then run 'cto status' again."))
        print()
        print(muted("    ──────────────────────────────────────────────────────────"))
        print(muted("    Press any key to return to main menu..."))
        print()
        pause()
        return

    # Overview
    print()
    overall_status = health.get("status", "unknown")
    is_ok = overall_status == "ok"
    overall_text = "All Systems Operational" if is_ok else f"System {overall_status.title()}"
    overall_icon = status_icon("running" if is_ok else "error")

    print(f"     {overall_icon} {brand(overall_text)}")
    env = health.get("environment", "")
    phase = health.get("phase", "")
    if env or phase:
        print(f"     Environment: {gold(env)}    Phase: {muted(phase)}")
    print()

    # Core Services (from /health)
    draw_section_header("Core Services")
    services = health.get("services", {})
    for name, svc_status in services.items():
        icon = status_icon("running" if svc_status == "ok" else "error")
        display_name = name.replace("_", " ").title()
        print(f"     {icon} {display_name:20} {brand(svc_status)}")
    print()

    # Memory Stores (from /health/deep if available)
    if deep:
        draw_section_header("Memory Stores")
        components = deep.get("components", {})
        memory_keys = ["redis", "postgres", "qdrant"]
        for key in memory_keys:
            comp = components.get(key, {})
            comp_status = comp.get("status", "unknown")
            icon = status_icon("running" if comp_status == "ok" else "error")
            display = {"redis": "Redis (working)", "postgres": "PostgreSQL", "qdrant": "Qdrant (semantic)"}
            msg = comp.get("message", "")
            print(f"     {icon} {display.get(key, key):20} {brand(comp_status):12}    {muted(msg)}")
        print()

        # External services
        draw_section_header("External Services")
        ext_keys = ["llm", "github", "openclaw", "knowledge_graph"]
        for key in ext_keys:
            comp = components.get(key, {})
            if not comp:
                continue
            comp_status = comp.get("status", "unknown")
            icon = status_icon("running" if comp_status == "ok" else "error")
            display = {
                "llm": "LLM API",
                "github": "GitHub",
                "openclaw": "OpenClaw",
                "knowledge_graph": "Knowledge Graph",
            }
            msg = comp.get("message", "")
            latency = comp.get("latency_ms")
            extra = f"{latency:.0f}ms" if latency else ""
            print(f"     {icon} {display.get(key, key):20} {brand(comp_status):12}    {muted(msg)}  {gold(extra)}")
        print()

    # Agents (from /health response)
    draw_section_header("Agents")
    agent_list = health.get("agents", [])
    config_agents = config.agents
    agent_display = {
        "code_review": ("Code Review", config_agents.code_review.enabled),
        "sprint_planner": ("Sprint Planner", config_agents.sprint_planner.enabled),
        "architecture_advisor": ("Architecture", config_agents.architecture_advisor.enabled),
        "devops": ("DevOps", config_agents.devops.enabled),
        "market_scanner": ("Market Scanner", config_agents.market_scanner.enabled),
        "meeting_intelligence": ("Meeting Intel", config_agents.meeting_intelligence.enabled),
        "coding_agent": ("Coding", config_agents.coding_agent.enabled),
    }

    for agent_key in agent_list:
        display_name, enabled = agent_display.get(agent_key, (agent_key, True))
        if enabled:
            icon = status_icon("running")
            print(f"     {icon} {agent_styled(display_name, display_name):24}    {success('loaded')}")
        else:
            print(f"       {muted('○')} {agent_styled(display_name, display_name + ' (disabled)'):24}    {muted('Enable in config')}")
    print()

    # Monitored repos
    repos = health.get("monitored_repos")
    if repos:
        draw_section_header("Monitored Repositories")
        repo_list = repos if isinstance(repos, list) else [r.strip() for r in repos.split(",") if r.strip()]
        for repo in repo_list:
            print(f"     {status_icon('connected')}  {gold(repo)}")
        print()

    # Footer
    print(muted("    ──────────────────────────────────────────────────────────"))
    print(muted("    Press any key to return to main menu..."))
    print()

    pause()
