"""Onboarding wizard steps with enhanced visual styling."""

from __future__ import annotations

import logging
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Callable

from src.tui.onboard.config import TUIConfig
from src.tui.utils.visual import (
    BrandColors,
    agent_styled,
    brand,
    cto,
    checkbox_checked,
    checkbox_unchecked,
    draw_box,
    draw_header_bar,
    draw_logo,
    draw_section_header,
    draw_progress_bar,
    gold,
    header_box,
    muted,
    radio_selected,
    radio_unselected,
    status_icon,
    success,
    warning,
)
from src.tui.utils.navigation import (
    confirm,
    edit_text,
    multi_select,
    select_option,
)

logger = logging.getLogger(__name__)


def _find_project_root() -> Path:
    """Find the project root by looking for pyproject.toml."""
    # Start from the file's location and walk up
    candidate = Path(__file__).resolve().parent
    for _ in range(10):
        if (candidate / "pyproject.toml").exists():
            return candidate
        candidate = candidate.parent
    # Fallback: cwd
    cwd = Path.cwd()
    if (cwd / "pyproject.toml").exists():
        return cwd
    return cwd


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
        # Ensure trailing newline before appending
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        lines.append(f"{key}={value}\n")

    env_path.write_text("".join(lines))


def welcome_screen() -> bool:
    """Display the welcome screen and get user consent to continue.

    Returns:
        True if user wants to continue, False if they want to exit
    """
    print()
    draw_logo()
    draw_header_bar("Welcome to AfCEN Digital CTO")

    print()
    print(brand("The Digital CTO") + " is a network of AI agents that help you:")
    print()

    features = [
        ("🔍", "Review code changes", "Security, Architecture, Quality"),
        ("📊", "Plan and track sprints", "AI recommendations and reports"),
        ("🏗️", "Advise on architecture", "Design decisions and tech debt"),
        ("🔧", "Monitor DevOps", "Pipeline health and alerts"),
        ("📈", "Scan market data", "Generate morning briefs"),
        ("💻", "Execute coding tasks", "Autonomous code generation"),
    ]

    for icon, feature, description in features:
        print(f"     {icon}  {brand(feature)}  {muted('─ ')}{muted(description)}")

    print()
    print(cto("    This onboarding will take 2-3 minutes.", BrandColors.WARNING))

    return confirm("    Ready to begin?", default=True)


def step_llm_config(config: TUIConfig) -> TUIConfig:
    """Step 1: Configure LLM provider."""
    print_header("LLM Configuration", "Step 1 of 5")

    print()
    print(brand("The Digital CTO needs access to LLM providers."))
    print("  Select your preferred provider (you can add more later):")
    print()

    # Radio-style options
    print()
    print(f"     {radio_selected('Anthropic (Claude)')}")
    print(muted("         Recommended for code review, long-context strength"))
    print()
    print(f"     {radio_unselected('Azure OpenAI')}")
    print(muted("         Enterprise-grade, GPT-4o"))
    print()
    print(f"     {radio_unselected('z.ai (GLM-5)')}")
    print(muted("         Cost-effective alternative"))
    print()
    print(f"     {radio_unselected('Skip for now')}")
    print(muted("         Configure manually later"))
    print()

    provider_idx = select_option(
        "Choose LLM provider",
        ["Anthropic (Claude)", "Azure OpenAI", "z.ai (GLM-5)", "Skip for now"],
        default=1,
    )

    providers = ["anthropic", "azure_openai", "zai", "none"]
    selected = providers[provider_idx]

    if selected == "none":
        print()
        print(warning("    ⚠ Skipping LLM configuration."))
        print("       You can configure this later by running 'cto onboard'.")
        return config

    config.llm.provider = selected

    # Get API key
    print()
    api_key = edit_text(
        f"     Enter {cto(selected.upper(), BrandColors.BOLD_TEXT)} API key",
        password=True,
    )

    if api_key and len(api_key) > 5:
        # Validate the key doesn't contain obvious garbage (e.g. terminal output
        # from a concurrent process). Valid API keys are printable ASCII without
        # leading/trailing whitespace or box-drawing characters.
        stripped = api_key.strip()
        has_garbage = (
            stripped != api_key
            or any(ord(c) > 127 for c in stripped)
            or any(c in stripped for c in "│┃├┤┌┐└┘─━═║╔╗╚╝☑☐►◆◇")
        )
        if has_garbage:
            print()
            print(warning("    ⚠ API key appears invalid (contains unexpected characters)."))
            print(warning("      Make sure no other 'cto' process is running and try again."))
        else:
            # Write API key to .env (secrets stay out of config.json)
            env_key_map = {
                "anthropic": "ANTHROPIC_API_KEY",
                "azure_openai": "AZURE_OPENAI_API_KEY",
                "zai": "ZAI_API_KEY",
            }
            env_key = env_key_map.get(selected)
            if env_key:
                _write_env_key(env_key, stripped)
            print()
            print(success(f"    ✓ API key written to .env ({len(stripped)} chars)!"))
    else:
        print()
        print(warning("    ⚠ No API key entered (or too short). You can configure this later."))

    return config


def step_github_config(config: TUIConfig) -> TUIConfig:
    """Step 2: Configure GitHub integration."""
    print_header("GitHub Configuration", "Step 2 of 5")

    print()
    print(brand("Connect to GitHub") + " for code review and sprint tracking.")
    print()

    # GitHub Token
    github_token = edit_text(
        "     GitHub Personal Access Token",
        password=True,
    )

    if github_token:
        stripped = github_token.strip()
        has_garbage = (
            stripped != github_token
            or any(ord(c) > 127 for c in stripped)
            or any(c in stripped for c in "│┃├┤┌┐└┘─━═║╔╗╚╝☑☐►◆◇")
        )
        if has_garbage:
            print()
            print(warning("    ⚠ Token appears invalid (contains unexpected characters)."))
            print(warning("      Make sure no other 'cto' process is running and try again."))
        else:
            # Write token to .env (secrets stay out of config.json)
            _write_env_key("GITHUB_TOKEN", stripped)
            print()
            print(success("    ✓ GitHub token written to .env!"))
    else:
        print()
        print(muted("    Skipped GitHub token. You can add it later."))

    # Repositories
    print()
    repos_input = edit_text(
        "     Repositories to monitor (comma-separated)",
        default="afcen/platform",
    )

    if repos_input:
        repos = [r.strip() for r in repos_input.split(",") if r.strip()]
        config.github.repos = repos
        # Also write repos to .env for the backend
        _write_env_key("GITHUB_REPOS", ",".join(repos))

        print()
        print(brand("    Detected repos:"))
        for repo in repos:
            print(f"       {status_icon('connected')}  {gold(repo)}")

    return config


def step_agent_config(config: TUIConfig) -> TUIConfig:
    """Step 3: Configure which agents to enable."""
    print_header("Agent Selection", "Step 3 of 5")

    print()
    print(brand("Select which agents to enable") + " (you can change this later):")
    print()

    agent_descriptions = [
        ("Code Review Agent", "Reviews PRs for security, architecture, quality"),
        ("Sprint Planner Agent", "Tracks sprints, generates reports, Bayes tracking"),
        ("Architecture Advisor", "Design guidance, tech debt assessment"),
        ("DevOps Agent", "Pipeline monitoring, failure analysis"),
        ("Market Scanner", "Market intelligence, morning briefs (Beta)"),
        ("Meeting Intelligence", "Meeting analysis, briefs (Beta)"),
        ("Coding Agent", "Autonomous coding tasks (Alpha)"),
    ]

    options = [f"{name} - {desc}" for name, desc in agent_descriptions]

    # Defaults: first 4 enabled
    defaults = [1, 2, 3, 4]
    selected = multi_select("     Select agents to enable", options, defaults)

    # Map selection to config
    agent_keys = [
        "code_review",
        "sprint_planner",
        "architecture_advisor",
        "devops",
        "market_scanner",
        "meeting_intelligence",
        "coding_agent",
    ]

    for i, key in enumerate(agent_keys):
        agent_config = getattr(config.agents, key)
        agent_config.enabled = (i in selected)

    print()
    print(success(f"    ✓ {len(selected)} agents enabled!"))

    return config


def step_scheduler_config(config: TUIConfig) -> TUIConfig:
    """Step 4: Configure scheduled tasks."""
    print_header("Scheduler Configuration", "Step 4 of 5")

    print()
    print(brand("Configure automated reports and tasks."))
    print()

    # Timezone selection
    print()
    print("     Select your timezone:")
    print()

    timezone_idx = select_option(
        "     Timezone",
        [
            "UTC",
            "Africa/Nairobi",
            "Africa/Lagos",
            "Africa/Cairo",
            "Other (will prompt manually)",
        ],
        default=1,
    )

    timezones = ["UTC", "Africa/Nairobi", "Africa/Lagos", "Africa/Cairo", None]
    selected_tz = timezones[timezone_idx]

    if selected_tz is None:
        selected_tz = edit_text("     Enter timezone (e.g., Africa/Nairobi)")
        if not selected_tz:
            selected_tz = "UTC"

    config.scheduler.timezone = selected_tz

    # Scheduled tasks
    print()
    print(brand("Enable scheduled tasks:"))
    print()

    tasks = [
        ("Daily Standup", config.scheduler.daily_standup, "Every weekday at 8:00 AM"),
        ("Weekly Report", config.scheduler.weekly_report, "Every Monday at 9:00 AM"),
        ("Bayes Alerts", config.scheduler.bayes_alerts, "Mon/Wed/Fri at 10:00 AM"),
        ("Market Scan", config.scheduler.market_scan, "Daily at 3:00 AM"),
        ("Morning Brief", config.scheduler.morning_brief, "Daily at 6:00 AM"),
    ]

    task_names = []
    for name, _, desc in tasks:
        task_names.append(f"{name} - {desc}")

    enabled_tasks = multi_select(
        "     Select tasks to enable",
        task_names,
        defaults=[1, 2, 3],  # First 3 enabled by default
    )

    config.scheduler.enabled = len(enabled_tasks) > 0

    print()
    print(success(f"    ✓ Scheduler configured for {gold(selected_tz)}!"))

    return config


def step_backend_config(config: TUIConfig) -> TUIConfig:
    """Step 5: Configure and start the Docker backend."""
    print_header("Backend Connection", "Step 5 of 5")

    print()
    print(brand("Connect to the Digital CTO backend") + " (Docker).")
    print()

    # Ask for backend URL
    backend_url = edit_text(
        "     Backend URL",
        default=config.backend_url,
    )
    if backend_url:
        config.backend_url = backend_url.strip().rstrip("/")

    # Offer to start Docker
    print()
    if confirm("     Start backend with 'docker compose up -d'?", default=True):
        project_root = _find_project_root()
        print()
        print(muted("    Starting Docker containers..."))

        try:
            result = subprocess.run(
                ["docker", "compose", "up", "-d"],
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                print(success("    ✓ Docker containers started!"))
            else:
                print(warning(f"    ⚠ docker compose exited with code {result.returncode}"))
                if result.stderr:
                    for line in result.stderr.strip().splitlines()[:5]:
                        print(muted(f"      {line}"))
        except FileNotFoundError:
            print(warning("    ⚠ 'docker' not found. Install Docker to use the backend."))
        except subprocess.TimeoutExpired:
            print(warning("    ⚠ Docker startup timed out (120s). Check 'docker compose logs'."))

        # Poll /health until healthy (up to 60s)
        print()
        print(muted("    Waiting for backend to become healthy..."))

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
            print(success("    ✓ Backend is healthy!"))
        else:
            print(warning("    ⚠ Backend not reachable after 60s."))
            print(muted("      You can start it later: docker compose up -d"))
    else:
        print()
        print(muted("    Skipped Docker startup. Start manually: docker compose up -d"))

    return config


def step_complete(config: TUIConfig) -> None:
    """Display completion message."""
    print()
    print()
    print()

    # Success banner
    print(cto("╔════════════════════════════════════════════════════════════════╗", BrandColors.SUNRISE_ORANGE))
    print(cto("║                                                              ║", BrandColors.SUNRISE_ORANGE))
    print(cto("║" + " " * 62 + "║", BrandColors.SUNRISE_ORANGE))
    print(cto("║" + " " * 20 + brand("✅ Setup Complete!") + " " * 27 + "║", BrandColors.SUNRISE_ORANGE))
    print(cto("║" + " " * 62 + "║", BrandColors.SUNRISE_ORANGE))
    print(cto("╚════════════════════════════════════════════════════════════════╝", BrandColors.SUNRISE_ORANGE))
    print()
    print()

    # Configuration info
    print(brand("Configuration saved to:") + " ~/.digital-cto/config.json")
    print()

    # Next steps
    print(cto("┌─ What's Next? ───────────────────────────────────────────────────┐", BrandColors.SUNRISE_ORANGE))
    print(cto("│", BrandColors.SUNRISE_ORANGE))
    print(cto("│  • Type 'cto' to open the main menu", BrandColors.RESET))
    print(cto("│  • Type 'cto chat' to talk to your agents", BrandColors.RESET))
    print(cto("│  • Type 'cto status' to check system health", BrandColors.RESET))
    print(cto("│  • Type 'cto logs' to view real-time activity", BrandColors.RESET))
    print(cto("│", BrandColors.SUNRISE_ORANGE))
    print(cto("│  The Digital CTO will now:", BrandColors.RESET))
    print(cto("│", BrandColors.SUNRISE_ORANGE))

    if config.agents.code_review.enabled:
        print(cto("│  ✓ Monitor GitHub PRs for code review", BrandColors.SUCCESS))
    else:
        print(cto("│  ○ Monitor GitHub PRs for code review (disabled)", BrandColors.MUTED))

    if config.scheduler.enabled:
        print(cto("│  ✓ Generate scheduled reports via JARVIS", BrandColors.SUCCESS))
    else:
        print(cto("│  ○ Generate scheduled reports (disabled)", BrandColors.MUTED))

    if config.agents.architecture_advisor.enabled:
        print(cto("│  ✓ Respond to architecture queries", BrandColors.SUCCESS))
    else:
        print(cto("│  ○ Respond to architecture queries (disabled)", BrandColors.MUTED))

    print(cto("│", BrandColors.SUNRISE_ORANGE))
    print(cto("└────────────────────────────────────────────────────────────────────┘", BrandColors.SUNRISE_ORANGE))
    print()

    # Docs link
    print(muted("    Documentation: https://docs.afcen.org/digital-cto"))
    print()


def validate_config(config: TUIConfig) -> list[str]:
    """Validate configuration and return list of issues."""
    issues = []

    if config.llm.provider == "none":
        issues.append("No LLM provider configured")

    needs_github = (
        config.agents.code_review.enabled or config.agents.sprint_planner.enabled
    )
    if needs_github and not config.github.repos:
        issues.append("GitHub-enabled agents active but no repos configured")

    return issues


def print_header(title: str, subtitle: str = "") -> None:
    """Print a styled section header."""
    print()
    print()
    draw_header_bar(title + (f" - {subtitle}" if subtitle else ""))
    print()


def run_onboarding() -> TUIConfig:
    """Run the complete onboarding wizard."""
    from src.tui.onboard.config import TUIConfig

    config = TUIConfig()

    # Welcome screen
    if not welcome_screen():
        print()
        print(muted("    Onboarding cancelled."))
        return config

    # Run through all steps
    config = step_llm_config(config)
    config = step_github_config(config)
    config = step_agent_config(config)
    config = step_scheduler_config(config)
    config = step_backend_config(config)

    # Show completion
    step_complete(config)

    # Validate and warn
    issues = validate_config(config)
    if issues:
        print()
        print(warning("    ⚠ Configuration Notes:"))
        for issue in issues:
            print(f"       • {issue}")

    return config
