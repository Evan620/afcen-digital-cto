"""Command-line interface for the Digital CTO TUI.

This module provides the 'cto' command for terminal-based interaction with the
Digital CTO system.
"""

from __future__ import annotations

import atexit
import fcntl
import os
import sys
from pathlib import Path
from typing import Optional

import click
from click import echo, style

from src.tui.main import (
    cmd_chat,
    cmd_config,
    cmd_doctor,
    cmd_logs,
    cmd_onboard,
    cmd_status,
)

# Process lock to prevent concurrent cto instances from corrupting each other's I/O
_lock_fd = None


def _acquire_lock() -> bool:
    """Acquire an exclusive process lock.

    Returns:
        True if lock acquired, False if another instance is running.
    """
    global _lock_fd
    lock_path = Path.home() / ".digital-cto" / "cto.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        _lock_fd = open(lock_path, "w")
        fcntl.flock(_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _lock_fd.write(str(os.getpid()))
        _lock_fd.flush()
        atexit.register(_release_lock)
        return True
    except OSError:
        if _lock_fd:
            _lock_fd.close()
            _lock_fd = None
        return False


def _release_lock() -> None:
    """Release the process lock."""
    global _lock_fd
    if _lock_fd:
        try:
            fcntl.flock(_lock_fd, fcntl.LOCK_UN)
            _lock_fd.close()
        except OSError:
            pass
        _lock_fd = None


def _kill_stale_cto_processes() -> None:
    """Kill any other cto processes to prevent terminal I/O corruption.

    Old cto instances (started before the lock mechanism existed) may
    still be writing to the terminal, corrupting input for new instances.
    """
    import signal
    import subprocess

    my_pid = os.getpid()
    parent_pid = os.getppid()

    try:
        result = subprocess.run(
            ["pgrep", "-f", "src.tui.cli"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.strip().splitlines():
            pid = int(line.strip())
            if pid != my_pid and pid != parent_pid:
                try:
                    os.kill(pid, signal.SIGTERM)
                except (ProcessLookupError, PermissionError):
                    pass
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        pass


@click.group(invoke_without_command=True)
@click.option("--version", is_flag=True, help="Show version and exit")
@click.pass_context
def cli(ctx: click.Context, version: bool) -> None:
    """AfCEN Digital CTO - AI-powered technical leadership system.

    The Digital CTO is a network of AI agents that help with code review,
    sprint planning, architecture decisions, DevOps monitoring, and more.
    """
    if version:
        from src.tui import __version__
        echo(f"Digital CTO TUI v{__version__}")
        return

    # If no subcommand, run the main TUI
    if ctx.invoked_subcommand is None:
        sys.exit(cmd_main())


@cli.command()
@click.option("--force", "-f", is_flag=True, help="Force re-run onboarding")
def onboard(force: bool) -> None:
    """Run the onboarding wizard to configure the Digital CTO."""
    sys.exit(cmd_onboard(force=force))


@cli.command()
def status() -> None:
    """Show system health status."""
    sys.exit(cmd_status())


@cli.command()
@click.argument("message", required=False)
def chat(message: Optional[str]) -> None:
    """Open the chat interface with Digital CTO agents.

    If MESSAGE is provided, send it directly and exit.
    """
    if message:
        # Quick message mode - send and get response
        import asyncio
        import httpx
        from src.tui.backend_client import get_backend_client

        client = get_backend_client()
        try:
            result = asyncio.run(client.chat(message=message))
            agent = result.get("agent", "Supervisor")
            response = result.get("response", "")
            echo(style(f"[{agent}]", fg="cyan", bold=True))
            echo(response)
        except (httpx.ConnectError, httpx.TimeoutException, OSError):
            echo(style("Backend unreachable. Start with: docker compose up -d", fg="yellow"), err=True)
            sys.exit(1)
        except httpx.HTTPStatusError as e:
            echo(style(f"Backend error (HTTP {e.response.status_code})", fg="red"), err=True)
            sys.exit(1)
        sys.exit(0)
    else:
        sys.exit(cmd_chat())


@cli.command()
@click.option("--follow", "-f", is_flag=True, help="Follow logs in real-time")
@click.option("--lines", "-n", default=50, help="Number of lines to show")
def logs(follow: bool, lines: int) -> None:
    """View system logs."""
    sys.exit(cmd_logs())


@cli.command()
def config() -> None:
    """Show or edit configuration."""
    sys.exit(cmd_config())


@cli.command()
def doctor() -> None:
    """Run diagnostics on the Digital CTO system."""
    sys.exit(cmd_doctor())


@cli.command()
@click.argument("pr_url", required=False)
@click.option("--repo", "-r", help="Repository name")
@click.option("--number", "-n", type=int, help="PR number")
def review(pr_url: Optional[str], repo: Optional[str], number: Optional[int]) -> None:
    """Request a code review for a pull request.

    You can specify the PR by URL, or by repo and number.
    """
    if pr_url:
        pr_ref = pr_url
    elif repo and number:
        pr_ref = f"{repo}#{number}"
    else:
        echo("Error: Specify PR URL or use --repo and --number", err=True)
        sys.exit(1)

    echo(f"Requesting review for: {pr_ref}")
    from src.tui.screens.code_review import quick_review

    result = quick_review(pr_ref)
    if result is None:
        echo(style("Backend unreachable. Start with: docker compose up -d", fg="yellow"), err=True)
        sys.exit(1)
    echo(result)
    sys.exit(0)


@cli.command()
def sprint() -> None:
    """Show current sprint status."""
    import asyncio
    import httpx
    from src.tui.backend_client import get_backend_client

    client = get_backend_client()
    try:
        data = asyncio.run(client.sprint_status())
    except (httpx.ConnectError, httpx.TimeoutException, OSError):
        echo(style("Backend unreachable. Start with: docker compose up -d", fg="yellow"), err=True)
        sys.exit(1)
    except httpx.HTTPStatusError as e:
        echo(style(f"Backend error (HTTP {e.response.status_code})", fg="red"), err=True)
        sys.exit(1)

    metrics = data.get("metrics", {})
    sprint_name = metrics.get("sprint_name", metrics.get("current_sprint", "N/A"))
    total = metrics.get("total_tasks", 0)
    completed = metrics.get("completed_tasks", 0)
    pct = int((completed / total * 100) if total else 0)
    velocity = metrics.get("velocity", "N/A")
    blocked = metrics.get("blocked_items", metrics.get("blocked", 0))

    echo(style("Sprint Status", bold=True))
    echo(f"  Sprint:    {sprint_name}")
    echo(f"  Progress:  {completed}/{total} tasks ({pct}%)")
    echo(f"  Velocity:  {velocity} pts/sprint")
    if blocked:
        echo(style(f"  Blocked:   {blocked} items", fg="yellow"))
    sys.exit(0)


@cli.command()
def brief() -> None:
    """Generate morning brief."""
    echo("Generating morning brief...")
    from src.tui.screens.market import quick_brief

    result = quick_brief()
    if result is None:
        echo(style("Backend unreachable. Start with: docker compose up -d", fg="yellow"), err=True)
        sys.exit(1)
    echo()
    echo(result)
    sys.exit(0)


def cmd_main() -> int:
    """Run the main TUI menu.

    Returns:
        Exit code
    """
    from src.tui.main import main as tui_main
    return tui_main()


def main() -> None:
    """Entry point for the CLI."""
    _kill_stale_cto_processes()
    if not _acquire_lock():
        echo(
            style("Another 'cto' instance is already running.", fg="yellow")
            + "\nPlease close it first, or use that terminal instead."
        )
        sys.exit(1)
    cli()


if __name__ == "__main__":
    main()
