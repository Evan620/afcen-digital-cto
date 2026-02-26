"""Interactive configuration editor screen for the Digital CTO TUI."""

from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path

from src.tui.onboard.config import (
    AgentConfig,
    load_config,
    save_config,
    TUIConfig,
)
from src.tui.utils.navigation import (
    confirm,
    edit_text,
    multi_select,
    select_option,
)
from src.tui.utils.visual import (
    BrandColors,
    brand,
    cto,
    draw_header_bar,
    draw_section_header,
    gold,
    muted,
    status_icon,
    success,
    warning,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_project_root() -> Path:
    """Find the project root by looking for pyproject.toml."""
    candidate = Path(__file__).resolve().parent
    for _ in range(10):
        if (candidate / "pyproject.toml").exists():
            return candidate
        candidate = candidate.parent
    cwd = Path.cwd()
    if (cwd / "pyproject.toml").exists():
        return cwd
    return cwd


def _mask_secret(value: str) -> str:
    """Mask a secret value for display, e.g. 'sk-ant...AAA'."""
    if not value:
        return muted("(not set)")
    if len(value) <= 9:
        return "*" * len(value)
    return value[:6] + "..." + value[-3:]


def _read_env_value(key: str) -> str:
    """Read a single key's current value from the project .env file."""
    env_path = _find_project_root() / ".env"
    if not env_path.exists():
        return ""
    for line in env_path.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith(f"{key}=") or stripped.startswith(f"{key} ="):
            _, _, val = stripped.partition("=")
            return val.strip()
    return ""


def _write_env_key(key: str, value: str) -> None:
    """Write or update a key in the project's .env file."""
    env_path = _find_project_root() / ".env"

    lines: list[str] = []
    found = False

    if env_path.exists():
        lines = env_path.read_text().splitlines(keepends=True)
        new_lines: list[str] = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(f"{key}=") or stripped.startswith(f"{key} ="):
                new_lines.append(f"{key}={value}\n")
                found = True
            else:
                new_lines.append(line)
        lines = new_lines

    if not found:
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        lines.append(f"{key}={value}\n")

    env_path.write_text("".join(lines))


# ---------------------------------------------------------------------------
# Section editors
# ---------------------------------------------------------------------------

def _edit_llm_settings(config: TUIConfig) -> bool:
    """Edit LLM provider, model, and API key. Returns True if anything changed."""
    dirty = False

    draw_section_header("LLM Configuration")
    print()

    # Current values
    print(f"  Provider:          {gold(config.llm.provider)}")
    print(f"  Model:             {gold(config.llm.model)}")
    print(f"  Fallback:          {gold(config.llm.fallback_provider)}")

    env_keys = {
        "anthropic": "ANTHROPIC_API_KEY",
        "azure_openai": "AZURE_OPENAI_API_KEY",
        "zai": "ZAI_API_KEY",
    }
    current_env_key = env_keys.get(config.llm.provider, "ANTHROPIC_API_KEY")
    current_secret = _read_env_value(current_env_key)
    print(f"  API Key ({current_env_key}): {_mask_secret(current_secret)}")
    print()

    # Provider
    provider_idx = select_option(
        "LLM provider",
        ["Anthropic (Claude)", "Azure OpenAI", "z.ai (GLM-5)", "Keep current"],
        default=4,
    )
    providers = ["anthropic", "azure_openai", "zai", None]
    new_provider = providers[provider_idx]
    if new_provider and new_provider != config.llm.provider:
        config.llm.provider = new_provider
        dirty = True

    # Model
    new_model = edit_text("  Model", default=config.llm.model)
    if new_model != config.llm.model:
        config.llm.model = new_model
        dirty = True

    # Fallback
    fallback_idx = select_option(
        "Fallback provider",
        ["Anthropic", "Azure OpenAI", "z.ai (GLM-5)", "Keep current"],
        default=4,
    )
    fallbacks = ["anthropic", "azure_openai", "zai", None]
    new_fallback = fallbacks[fallback_idx]
    if new_fallback and new_fallback != config.llm.fallback_provider:
        config.llm.fallback_provider = new_fallback
        dirty = True

    # API key
    active_env_key = env_keys.get(config.llm.provider, "ANTHROPIC_API_KEY")
    print()
    print(muted(f"  (Press Enter to keep current {active_env_key} value)"))
    new_key = edit_text(f"  {active_env_key}", password=True)
    if new_key and new_key.strip():
        _write_env_key(active_env_key, new_key.strip())
        _write_env_key("PREFERRED_LLM_PROVIDER", config.llm.provider)
        print(success(f"  ✓ {active_env_key} updated"))
        dirty = True

    return dirty


def _edit_github_settings(config: TUIConfig) -> bool:
    """Edit GitHub token, repos, webhook secret. Returns True if changed."""
    dirty = False

    draw_section_header("GitHub Configuration")
    print()

    current_token = _read_env_value("GITHUB_TOKEN")
    current_secret = _read_env_value("GITHUB_WEBHOOK_SECRET")
    print(f"  Token:           {_mask_secret(current_token)}")
    print(f"  Repos:           {', '.join(config.github.repos) or muted('(none)')}")
    print(f"  Webhook Secret:  {_mask_secret(current_secret)}")
    print()

    # Token
    print(muted("  (Press Enter to keep current value)"))
    new_token = edit_text("  GitHub Token", password=True)
    if new_token and new_token.strip():
        _write_env_key("GITHUB_TOKEN", new_token.strip())
        print(success("  ✓ GITHUB_TOKEN updated"))
        dirty = True

    # Repos
    repos_str = ", ".join(config.github.repos)
    new_repos = edit_text("  Repositories (comma-separated)", default=repos_str)
    parsed = [r.strip() for r in new_repos.split(",") if r.strip()]
    if parsed != config.github.repos:
        config.github.repos = parsed
        _write_env_key("GITHUB_REPOS", ",".join(parsed))
        dirty = True

    # Webhook secret
    new_secret = edit_text("  Webhook Secret", password=True)
    if new_secret and new_secret.strip():
        _write_env_key("GITHUB_WEBHOOK_SECRET", new_secret.strip())
        print(success("  ✓ GITHUB_WEBHOOK_SECRET updated"))
        dirty = True

    return dirty


def _edit_agent_settings(config: TUIConfig) -> bool:
    """Toggle agents on/off. Returns True if changed."""
    draw_section_header("Agent Configuration")
    print()

    agent_info = [
        ("code_review", "Code Review Agent"),
        ("sprint_planner", "Sprint Planner Agent"),
        ("architecture_advisor", "Architecture Advisor"),
        ("devops", "DevOps Agent"),
        ("market_scanner", "Market Scanner (Beta)"),
        ("meeting_intelligence", "Meeting Intelligence (Beta)"),
        ("coding_agent", "Coding Agent (Alpha)"),
    ]

    options = []
    currently_enabled: list[int] = []
    for i, (key, label) in enumerate(agent_info):
        agent_cfg: AgentConfig = getattr(config.agents, key)
        icon = status_icon("ready") if agent_cfg.enabled else status_icon("disabled")
        options.append(f"{icon} {label}")
        if agent_cfg.enabled:
            currently_enabled.append(i + 1)  # 1-based for multi_select defaults

    selected = multi_select("  Toggle agents", options, defaults=currently_enabled)

    dirty = False
    for i, (key, _) in enumerate(agent_info):
        agent_cfg = getattr(config.agents, key)
        should_enable = i in selected
        if agent_cfg.enabled != should_enable:
            agent_cfg.enabled = should_enable
            dirty = True

    if dirty:
        print(success(f"  ✓ {len(selected)} agents enabled"))
    else:
        print(muted("  No changes"))

    return dirty


def _edit_scheduler_settings(config: TUIConfig) -> bool:
    """Edit scheduler toggle, timezone, cron expressions. Returns True if changed."""
    dirty = False

    draw_section_header("Scheduler Configuration")
    print()

    print(f"  Enabled:        {gold('Yes') if config.scheduler.enabled else muted('No')}")
    print(f"  Timezone:       {gold(config.scheduler.timezone)}")
    print(f"  Daily Standup:  {config.scheduler.daily_standup}")
    print(f"  Weekly Report:  {config.scheduler.weekly_report}")
    print(f"  Bayes Alerts:   {config.scheduler.bayes_alerts}")
    print(f"  Market Scan:    {config.scheduler.market_scan}")
    print(f"  Morning Brief:  {config.scheduler.morning_brief}")
    print()

    # Toggle
    if confirm("  Enable scheduler?", default=config.scheduler.enabled):
        if not config.scheduler.enabled:
            config.scheduler.enabled = True
            dirty = True
    else:
        if config.scheduler.enabled:
            config.scheduler.enabled = False
            dirty = True

    if not config.scheduler.enabled:
        return dirty

    # Timezone
    tz_idx = select_option(
        "  Timezone",
        ["UTC", "Africa/Nairobi", "Africa/Lagos", "Africa/Cairo", "Keep current"],
        default=5,
    )
    tz_choices = ["UTC", "Africa/Nairobi", "Africa/Lagos", "Africa/Cairo", None]
    new_tz = tz_choices[tz_idx]
    if new_tz and new_tz != config.scheduler.timezone:
        config.scheduler.timezone = new_tz
        dirty = True

    # Cron expressions
    cron_fields = [
        ("daily_standup", "Daily Standup cron"),
        ("weekly_report", "Weekly Report cron"),
        ("bayes_alerts", "Bayes Alerts cron"),
        ("market_scan", "Market Scan cron"),
        ("morning_brief", "Morning Brief cron"),
    ]

    print()
    print(muted("  (Press Enter to keep current cron expression)"))
    for attr, label in cron_fields:
        current = getattr(config.scheduler, attr)
        new_val = edit_text(f"  {label}", default=current)
        if new_val != current:
            setattr(config.scheduler, attr, new_val)
            dirty = True

    return dirty


def _edit_jarvis_settings(config: TUIConfig) -> bool:
    """Edit JARVIS/OpenClaw gateway settings. Returns True if changed."""
    dirty = False
    jarvis = config.integrations.jarvis

    draw_section_header("JARVIS / OpenClaw Configuration")
    print()

    current_gw_env = _read_env_value("JARVIS_GATEWAY_URL")
    current_token_env = _read_env_value("JARVIS_TOKEN")
    print(f"  Enabled:      {gold('Yes') if jarvis.enabled else muted('No')}")
    print(f"  Gateway URL:  {gold(jarvis.gateway_url)}")
    print(f"  Token:        {_mask_secret(jarvis.token)}")
    if current_gw_env:
        print(f"  .env URL:     {muted(current_gw_env)}")
    if current_token_env:
        print(f"  .env Token:   {_mask_secret(current_token_env)}")
    print()

    # Toggle
    if confirm("  Enable JARVIS?", default=jarvis.enabled):
        if not jarvis.enabled:
            jarvis.enabled = True
            dirty = True
    else:
        if jarvis.enabled:
            jarvis.enabled = False
            dirty = True

    if not jarvis.enabled:
        return dirty

    # Gateway URL
    new_url = edit_text("  Gateway URL", default=jarvis.gateway_url)
    if new_url != jarvis.gateway_url:
        jarvis.gateway_url = new_url
        _write_env_key("JARVIS_GATEWAY_URL", new_url)
        dirty = True

    # Token
    print(muted("  (Press Enter to keep current token)"))
    new_token = edit_text("  JARVIS Token", password=True)
    if new_token and new_token.strip():
        jarvis.token = new_token.strip()
        _write_env_key("JARVIS_TOKEN", new_token.strip())
        print(success("  ✓ JARVIS_TOKEN updated"))
        dirty = True

    return dirty


def _edit_database_urls() -> bool:
    """Edit Redis, Postgres, Qdrant URLs in .env. Returns True if changed."""
    dirty = False

    draw_section_header("Database URLs")
    print()

    db_keys = [
        ("REDIS_URL", "Redis URL"),
        ("DATABASE_URL", "PostgreSQL URL"),
        ("QDRANT_URL", "Qdrant URL"),
    ]

    for key, label in db_keys:
        current = _read_env_value(key)
        print(f"  {label}: {gold(current) if current else muted('(not set)')}")
    print()

    print(muted("  (Press Enter to keep current value)"))
    for key, label in db_keys:
        current = _read_env_value(key)
        new_val = edit_text(f"  {label}", default=current)
        if new_val != current:
            _write_env_key(key, new_val)
            print(success(f"  ✓ {key} updated"))
            dirty = True

    return dirty


# ---------------------------------------------------------------------------
# Docker restart
# ---------------------------------------------------------------------------

def _restart_services(config: TUIConfig) -> None:
    """Restart Docker services and poll for health."""
    if not confirm("  Restart Docker services to apply changes?", default=True):
        print(muted("  Skipped restart."))
        return

    project_root = _find_project_root()
    print()
    print(muted("  Restarting Docker containers..."))

    try:
        result = subprocess.run(
            ["docker-compose", "restart", "cto-app"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            print(success("  ✓ Docker restart complete"))
        else:
            print(warning(f"  ⚠ docker-compose exited with code {result.returncode}"))
            if result.stderr:
                for line in result.stderr.strip().splitlines()[:5]:
                    print(muted(f"    {line}"))
            return
    except FileNotFoundError:
        print(warning("  ⚠ 'docker-compose' not found. Install Docker to use the backend."))
        return
    except subprocess.TimeoutExpired:
        print(warning("  ⚠ Docker restart timed out (60s). Check 'docker-compose logs'."))
        return

    # Health poll
    print(muted("  Waiting for backend to become healthy..."))

    import httpx

    healthy = False
    for attempt in range(30):
        try:
            with httpx.Client(timeout=2.0) as client:
                resp = client.get(f"{config.backend_url}/health")
                if resp.status_code == 200:
                    healthy = True
                    break
        except (httpx.ConnectError, httpx.TimeoutException, OSError):
            pass
        time.sleep(2)
        if attempt % 5 == 4:
            print(muted(f"    Still waiting... ({(attempt + 1) * 2}s)"))

    if healthy:
        print(success("  ✓ Backend is healthy!"))
    else:
        print(warning("  ⚠ Backend not reachable after 60s."))
        print(muted("    Check logs: docker-compose logs cto-app"))


# ---------------------------------------------------------------------------
# Main config menu
# ---------------------------------------------------------------------------

def _draw_config_menu(config: TUIConfig) -> None:
    """Display the configuration submenu."""
    print()
    draw_header_bar("Configuration")
    print()

    items = [
        ("1", "LLM Provider", f"current: {config.llm.provider}"),
        ("2", "GitHub", f"{len(config.github.repos)} repo(s)"),
        ("3", "Agents", "Enable/disable individual agents"),
        ("4", "Scheduler", f"{'on' if config.scheduler.enabled else 'off'}, {config.scheduler.timezone}"),
        ("5", "JARVIS / OpenClaw", f"{'on' if config.integrations.jarvis.enabled else 'off'}"),
        ("6", "Database URLs", "Redis, Postgres, Qdrant"),
    ]

    for num, label, desc in items:
        print(f"  {gold(num)}.  {brand(label):<30s} {muted('— ' + desc)}")

    print(f"  {muted('─' * 50)}")
    print(f"  {gold('7')}.  {brand('Restart Services'):<30s} {muted('— Apply changes (restart Docker)')}")
    print(f"  {gold('0')}.  {brand('Back'):<30s} {muted('— Return to main menu')}")
    print()


def show_config_screen() -> None:
    """Main loop for the interactive configuration editor."""
    config = load_config()
    dirty = False

    while True:
        _draw_config_menu(config)

        try:
            choice = input(
                cto("  Select section", BrandColors.SUNRISE_ORANGE) + " [0-7]: "
            ).strip()
        except (KeyboardInterrupt, EOFError):
            choice = "0"

        changed = False

        if choice == "1":
            changed = _edit_llm_settings(config)
        elif choice == "2":
            changed = _edit_github_settings(config)
        elif choice == "3":
            changed = _edit_agent_settings(config)
        elif choice == "4":
            changed = _edit_scheduler_settings(config)
        elif choice == "5":
            changed = _edit_jarvis_settings(config)
        elif choice == "6":
            changed = _edit_database_urls()
        elif choice == "7":
            _restart_services(config)
            continue
        elif choice == "0":
            if dirty:
                print()
                _restart_services(config)
            break
        else:
            print(warning("  ⚠ Invalid option."))
            continue

        if changed:
            dirty = True
            save_config(config)
            print(success("  ✓ config.json saved"))
