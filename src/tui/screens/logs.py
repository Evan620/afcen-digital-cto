"""Log viewer screen — fetches real service status from backend."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any

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

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class LogEntry:
    """A single log entry."""

    def __init__(self, timestamp: str, level: str, logger_name: str, message: str):
        self.timestamp = timestamp
        self.level = level
        self.logger_name = logger_name
        self.message = message

    def format(self, colorize: bool = True) -> str:
        ts = muted(self.timestamp)
        lvl = self.level.upper().ljust(5)

        if colorize:
            if self.level == "INFO":
                lvl = cto(lvl, BrandColors.INFO)
            elif self.level == "WARNING":
                lvl = cto(lvl, BrandColors.WARNING)
            elif self.level == "ERROR":
                lvl = cto(lvl, BrandColors.ERROR)
            elif self.level == "DEBUG":
                lvl = muted(lvl)
            elif self.level == "SUCCESS":
                lvl = cto(lvl, BrandColors.SUCCESS)

        return f"{ts} │ {lvl} │ {self.message}"


def _health_to_log_entries(health: dict[str, Any]) -> list[tuple[str, str, str, str]]:
    """Convert a /health response into log-style entries."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entries: list[tuple[str, str, str, str]] = []

    overall = health.get("status", "unknown")
    entries.append((now, "SUCCESS" if overall == "ok" else "WARNING", "Health", f"Overall status: {overall}"))

    for name, svc_status in health.get("services", {}).items():
        level = "SUCCESS" if svc_status == "ok" else "ERROR"
        display = name.replace("_", " ").title()
        entries.append((now, level, display, f"{display}: {svc_status}"))

    env = health.get("environment", "")
    if env:
        entries.append((now, "INFO", "Config", f"Environment: {env}"))

    phase = health.get("phase", "")
    if phase:
        entries.append((now, "INFO", "Config", f"Phase: {phase}"))

    agents = health.get("agents", [])
    if agents:
        entries.append((now, "INFO", "Supervisor", f"Loaded agents: {', '.join(agents)}"))

    repos = health.get("monitored_repos")
    if repos:
        repo_str = repos if isinstance(repos, str) else ", ".join(repos)
        entries.append((now, "INFO", "GitHub", f"Monitored repos: {repo_str}"))

    return entries


class LogViewer:
    """Log viewer that fetches real status from the backend."""

    def __init__(self, filter_level: str = "ALL"):
        self.filter_level = filter_level.upper()
        self.logs: list[LogEntry] = []
        self.auto_scroll = True
        self.running = True

        # Fetch initial data from backend
        self._refresh_from_backend()

    def _refresh_from_backend(self) -> None:
        """Fetch health data from backend and convert to log entries."""
        client = get_backend_client()
        try:
            health = asyncio.run(client.health())
            entries = _health_to_log_entries(health)
            for ts, level, logger_name, message in entries:
                self.add_log(ts, level, logger_name, message)
        except (httpx.ConnectError, httpx.TimeoutException, OSError):
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.add_log(now, "ERROR", "Backend", "Cannot connect to backend")
            self.add_log(now, "INFO", "Backend", "Start with: docker compose up -d")
        except Exception as e:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.add_log(now, "ERROR", "Backend", f"Health check failed: {str(e)[:100]}")

    def add_log(self, timestamp: str, level: str, logger_name: str, message: str) -> None:
        """Add a log entry.

        Args:
            timestamp: Log timestamp
            level: Log level
            logger_name: Logger name
            message: Log message
        """
        entry = LogEntry(timestamp, level, logger_name, message)
        self.logs.append(entry)

        # Keep only last 1000 logs
        if len(self.logs) > 1000:
            self.logs = self.logs[-1000:]

    def should_display(self, entry: LogEntry) -> bool:
        """Check if a log entry should be displayed based on filter.

        Args:
            entry: Log entry to check

        Returns:
            True if entry should be displayed
        """
        if self.filter_level == "ALL":
            return True

        level_priority = {
            "DEBUG": 0,
            "INFO": 1,
            "WARNING": 2,
            "ERROR": 3,
            "CRITICAL": 4,
            "SUCCESS": 1,
        }

        filter_priority = level_priority.get(self.filter_level, 0)
        entry_priority = level_priority.get(entry.level.upper(), 0)

        return entry_priority >= filter_priority

    def display(self, lines: int = 15) -> None:
        """Display the current log view.

        Args:
            lines: Number of lines to display
        """
        print()
        print(cto("📜 Real-time Logs", BrandColors.SUNRISE_ORANGE, BrandColors.BOLD_TEXT))
        print(cto("─" * 70, BrandColors.SUNRISE_ORANGE))

        # Filter controls
        filters = ["All", "Info", "Warning", "Error"]
        current = self.filter_level if self.filter_level != "ALL" else "All"
        filter_display = " ".join(
            f"{cto(f'[{f}]', BrandColors.SUNRISE_ORANGE, BrandColors.BOLD_TEXT)}" if f.upper() == current else f"[{f}]"
            for f in filters
        )

        search = "[___________]"
        print(f"  Filter: {filter_display}              Search: {search}")
        print()

        # Logs
        draw_section_header("Logs")

        visible_logs = [log for log in self.logs if self.should_display(log)]
        display_logs = visible_logs[-lines:] if self.auto_scroll else visible_logs[:lines]

        for log in display_logs:
            print(f"  {log.format()}")

        # Footer
        print()
        total = len(visible_logs)
        auto_scroll_status = cto("ON", BrandColors.SUCCESS) if self.auto_scroll else muted("OFF")
        print(f"  Line: {len(display_logs)} of {total}{' of ' + str(len(self.logs)) if total < len(self.logs) else ''}            Auto-scroll: [{auto_scroll_status}]")

    def run(self) -> None:
        """Run the log viewer interactively."""
        clear_screen()

        # Draw header
        draw_logo()
        draw_header_bar("Log Viewer")

        while self.running:
            self.display()

            print()
            print(muted("  Commands: [f]ilter  [s]earch  [a]uto-scroll  [r]efresh  [q]uit"))
            print()

            try:
                cmd = input(cto("  >", BrandColors.SUNRISE_ORANGE)).strip().lower()

                if cmd in ("q", "quit", "exit"):
                    self.running = False
                elif cmd == "f":
                    self.change_filter()
                elif cmd == "a":
                    self.auto_scroll = not self.auto_scroll
                elif cmd == "r":
                    print("  Refreshing from backend...")
                    self._refresh_from_backend()
                elif cmd == "s":
                    print("  Search: (not yet implemented)")

            except (KeyboardInterrupt, EOFError):
                self.running = False

    def change_filter(self) -> None:
        """Change the log level filter."""
        print()
        levels = ["All", "Info", "Warning", "Error", "Debug"]
        for i, level in enumerate(levels, 1):
            current = cto(" (current)", BrandColors.SUCCESS) if level.upper() == self.filter_level else ""
            print(f"    {i}. {level}{current}")

        try:
            choice = input("\n  Select filter level: ").strip()
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(levels):
                    self.filter_level = levels[idx].upper()
        except (ValueError, KeyboardInterrupt):
            pass


def show_log_viewer() -> None:
    """Display the log viewer screen."""
    viewer = LogViewer()
    viewer.run()
