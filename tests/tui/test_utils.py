"""Tests for TUI utility functions."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from src.tui.utils.formatting import (
    style,
    success,
    error,
    warning,
    info,
    dim,
    bold,
    status_indicator,
    status_emoji,
    truncate,
    format_timestamp,
    format_duration,
    format_list,
    draw_box,
)
from src.tui.utils.navigation import (
    confirm,
    select_option,
    multi_select,
    edit_text,
    progress_bar,
)


class TestFormatting:
    """Tests for formatting utilities."""

    def test_style(self) -> None:
        """Test basic text styling."""
        result = style("test", "\033[31m")
        assert "\033[31m" in result
        assert "\033[0m" in result
        assert "test" in result

    def test_success(self) -> None:
        """Test success styling."""
        result = success("test")
        assert "test" in result
        assert "\033[" in result  # ANSI code

    def test_error(self) -> None:
        """Test error styling."""
        result = error("test")
        assert "test" in result

    def test_warning(self) -> None:
        """Test warning styling."""
        result = warning("test")
        assert "test" in result

    def test_dim(self) -> None:
        """Test dim styling."""
        result = dim("test")
        assert "test" in result

    def test_bold(self) -> None:
        """Test bold styling."""
        result = bold("test")
        assert "test" in result

    def test_status_indicator(self) -> None:
        """Test status indicator function."""
        assert status_indicator("running") == status_indicator("active")
        assert status_indicator("running") == status_indicator("online")
        assert status_indicator("stopped") == status_indicator("offline")
        assert status_indicator("error") == status_indicator("failed")

    def test_status_emoji(self) -> None:
        """Test status emoji function."""
        assert "🟢" in status_emoji("running")
        assert "🔴" in status_emoji("stopped")
        assert "❌" in status_emoji("error")

    def test_truncate(self) -> None:
        """Test text truncation."""
        assert truncate("hello world", 5) == "he..."
        assert truncate("hi", 5) == "hi"
        assert truncate("hello world", 11) == "hello world"

    def test_format_timestamp(self) -> None:
        """Test timestamp formatting."""
        ts = "2026-02-25T14:30:00Z"
        result = format_timestamp(ts)
        assert "2026-02-25" in result
        assert "14:30:00" in result

    def test_format_timestamp_empty(self) -> None:
        """Test formatting empty timestamp."""
        result = format_timestamp("")
        assert "Never" in result or "never" in result

    def test_format_duration(self) -> None:
        """Test duration formatting."""
        assert format_duration(30) == "30s"
        assert format_duration(90) == "1m"
        assert format_duration(3600) == "1h 0m"
        assert format_duration(7200) == "2h 0m"
        assert format_duration(90000) == "1d 1h"
        assert format_duration(86400) == "1d 0h"

    def test_format_list(self) -> None:
        """Test list formatting."""
        items = ["item1", "item2", "item3"]
        result = format_list(items)
        assert "• item1" in result
        assert "• item2" in result
        assert "• item3" in result

    def test_draw_box(self) -> None:
        """Test box drawing."""
        result = draw_box("Title", "content")
        assert "Title" in result or "title" in result.lower()
        assert "content" in result
        assert "│" in result or "|" in result


class TestNavigation:
    """Tests for navigation utilities."""

    def test_progress_bar(self) -> None:
        """Test progress bar generation."""
        bar = progress_bar(5, 10, width=20)
        assert len(bar) == 20
        assert "█" in bar or "░" in bar

    def test_progress_bar_full(self) -> None:
        """Test full progress bar."""
        bar = progress_bar(10, 10, width=10)
        assert bar.count("░") == 0 or bar.count(" ") == 0

    def test_progress_bar_empty(self) -> None:
        """Test empty progress bar."""
        bar = progress_bar(0, 10, width=10)
        assert bar.count("█") == 0


class TestCommandHistory:
    """Tests for command history."""

    def test_add_and_retrieve(self) -> None:
        """Test adding and retrieving from history."""
        from src.tui.utils.navigation import CommandHistory

        history = CommandHistory(max_size=5)
        history.add("command1")
        history.add("command2")

        assert "command1" in history.history
        assert "command2" in history.history

    def test_max_size(self) -> None:
        """Test max size enforcement."""
        from src.tui.utils.navigation import CommandHistory

        history = CommandHistory(max_size=3)
        for i in range(5):
            history.add(f"command{i}")

        assert len(history.history) == 3
        assert "command4" in history.history
        assert "command0" not in history.history

    def test_no_duplicates(self) -> None:
        """Test that duplicates are not added."""
        from src.tui.utils.navigation import CommandHistory

        history = CommandHistory()
        history.add("same")
        history.add("same")

        assert history.history.count("same") == 1


@pytest.mark.parametrize(
    "status,expected",
    [
        ("running", "🟢"),
        ("active", "🟢"),
        ("online", "🟢"),
        ("stopped", "🔴"),
        ("offline", "🔴"),
        ("error", "❌"),
        ("warning", "⚠️"),
        ("disabled", "⭕"),
    ],
)
def test_status_emoji_parametrized(status: str, expected: str) -> None:
    """Parametrized test for status emoji."""
    result = status_emoji(status)
    assert expected in result or result == "•"
