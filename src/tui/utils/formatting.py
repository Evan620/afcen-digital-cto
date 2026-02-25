"""Formatting utilities for TUI display with rich visual styling.

Provides consistent text styling, status indicators, and layout helpers.
"""

from __future__ import annotations

from typing import Final

# ANSI color codes
class Colors:
    """ANSI color codes for terminal output."""

    RESET: Final[str] = "\033[0m"
    BOLD: Final[str] = "\033[1m"
    DIM: Final[str] = "\033[2m"
    ITALIC: Final[str] = "\033[3m"
    UNDERLINE: Final[str] = "\033[4m"

    # Foreground colors
    BLACK: Final[str] = "\033[30m"
    RED: Final[str] = "\033[31m"
    GREEN: Final[str] = "\033[32m"
    YELLOW: Final[str] = "\033[33m"
    BLUE: Final[str] = "\033[34m"
    MAGENTA: Final[str] = "\033[35m"
    CYAN: Final[str] = "\033[36m"
    WHITE: Final[str] = "\033[37m"

    # Bright foreground colors
    BRIGHT_RED: Final[str] = "\033[91m"
    BRIGHT_GREEN: Final[str] = "\033[92m"
    BRIGHT_YELLOW: Final[str] = "\033[93m"
    BRIGHT_BLUE: Final[str] = "\033[94m"
    BRIGHT_MAGENTA: Final[str] = "\033[95m"
    BRIGHT_CYAN: Final[str] = "\033[96m"
    BRIGHT_WHITE: Final[str] = "\033[97m"

    # Background colors
    BG_BLACK: Final[str] = "\033[40m"
    BG_RED: Final[str] = "\033[41m"
    BG_GREEN: Final[str] = "\033[42m"
    BG_YELLOW: Final[str] = "\033[43m"
    BG_BLUE: Final[str] = "\033[44m"
    BG_MAGENTA: Final[str] = "\033[45m"
    BG_CYAN: Final[str] = "\033[46m"
    BG_WHITE: Final[str] = "\033[47m"

    # 256-color palette (popular colors)
    ORANGE: Final[str] = "\033[38;5;208m"
    PINK: Final[str] = "\033[38;5;213m"
    PURPLE: Final[str] = "\033[38;5;141m"
    LIME: Final[str] = "\033[38;5;154m"
    AQUA: Final[str] = "\033[38;5;51m"
    VIOLET: Final[str] = "\033[38;5;147m"
    GOLD: Final[str] = "\033[38;5;220m"
    SILVER: Final[str] = "\033[38;5;250m"
    GRAY: Final[str] = "\033[38;5;245m"


# Predefined color themes
class Theme:
    """Color themes for the TUI."""

    # Primary colors
    PRIMARY = Colors.BRIGHT_BLUE
    SECONDARY = Colors.BRIGHT_CYAN
    ACCENT = Colors.BRIGHT_MAGENTA

    # Status colors
    SUCCESS = Colors.BRIGHT_GREEN
    ERROR = Colors.BRIGHT_RED
    WARNING = Colors.BRIGHT_YELLOW
    INFO = Colors.BRIGHT_CYAN

    # Agent-specific colors
    CODE_REVIEW = Colors.BRIGHT_BLUE
    SPRINT_PLANNER = Colors.BRIGHT_GREEN
    ARCHITECTURE = Colors.PURPLE
    DEVOPS = Colors.ORANGE
    MARKET = Colors.GOLD
    MEETING = Colors.PINK
    CODING = Colors.VIOLET


def style(text: str, *colors: str) -> str:
    """Apply ANSI color codes to text.

    Args:
        text: The text to style
        *colors: Color codes to apply (from Colors class)

    Returns:
        Styled text with ANSI codes
    """
    return "".join(colors) + text + Colors.RESET


def success(text: str) -> str:
    """Style text as success (green)."""
    return style(text, Colors.BOLD, Colors.BRIGHT_GREEN)


def error(text: str) -> str:
    """Style text as error (red)."""
    return style(text, Colors.BOLD, Colors.BRIGHT_RED)


def warning(text: str) -> str:
    """Style text as warning (yellow)."""
    return style(text, Colors.BOLD, Colors.BRIGHT_YELLOW)


def info(text: str) -> str:
    """Style text as info (cyan)."""
    return style(text, Colors.BOLD, Colors.BRIGHT_CYAN)


def dim(text: str) -> str:
    """Style text as dimmed."""
    return style(text, Colors.DIM)


def bold(text: str) -> str:
    """Style text as bold."""
    return style(text, Colors.BOLD)


def primary(text: str) -> str:
    """Style text with primary color (blue)."""
    return style(text, Colors.BOLD, Theme.PRIMARY)


def secondary(text: str) -> str:
    """Style text with secondary color (cyan)."""
    return style(text, Colors.BOLD, Theme.SECONDARY)


def accent(text: str) -> str:
    """Style text with accent color (magenta)."""
    return style(text, Colors.BOLD, Theme.ACCENT)


def agent_color(agent_name: str, text: str) -> str:
    """Apply agent-specific coloring.

    Args:
        agent_name: Name of the agent
        text: Text to style

    Returns:
        Styled text
    """
    agent_lower = agent_name.lower()

    if "code" in agent_lower or "review" in agent_lower:
        return style(text, Theme.CODE_REVIEW)
    if "sprint" in agent_lower:
        return style(text, Theme.SPRINT_PLANNER)
    if "arch" in agent_lower:
        return style(text, Theme.ARCHITECTURE)
    if "devops" in agent_lower:
        return style(text, Theme.DEVOPS)
    if "market" in agent_lower:
        return style(text, Theme.MARKET)
    if "meeting" in agent_lower:
        return style(text, Theme.MEETING)
    if "coding" in agent_lower:
        return style(text, Theme.CODING)

    return text


def status_indicator(status: str) -> str:
    """Return a colored status indicator.

    Args:
        status: Status string (running, stopped, error, etc.)

    Returns:
        Colored emoji or symbol
    """
    status_lower = status.lower()

    if status_lower in ("running", "active", "online", "connected", "up", "healthy", "ok", "ready"):
        return style("●", Colors.BRIGHT_GREEN)
    if status_lower in ("stopped", "inactive", "offline", "disconnected", "down"):
        return style("●", Colors.BRIGHT_RED)
    if status_lower in ("error", "failed", "unhealthy", "crashed"):
        return style("●", Colors.BRIGHT_RED)
    if status_lower in ("warning", "degraded", "slow"):
        return style("●", Colors.BRIGHT_YELLOW)
    if status_lower in ("pending", "starting", "loading", "buffering"):
        return style("●", Colors.BRIGHT_YELLOW)
    if status_lower in ("disabled", "off"):
        return style("○", Colors.DIM)

    return style("●", Colors.DIM)


def status_emoji(status: str) -> str:
    """Return an emoji status indicator.

    Args:
        status: Status string

    Returns:
        Emoji indicator
    """
    status_lower = status.lower()

    if status_lower in ("running", "active", "online", "connected", "up", "healthy", "ok", "ready"):
        return "🟢"
    if status_lower in ("stopped", "inactive", "offline", "disconnected", "down"):
        return "🔴"
    if status_lower in ("error", "failed", "unhealthy", "crashed"):
        return "❌"
    if status_lower in ("warning", "degraded", "slow"):
        return "⚠️"
    if status_lower in ("pending", "starting", "loading"):
        return "⏳"
    if status_lower in ("disabled", "off"):
        return "⭕"

    return "•"


def truncate(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate text to a maximum length.

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def format_timestamp(ts: str | None) -> str:
    """Format a timestamp for display.

    Args:
        ts: ISO timestamp string

    Returns:
        Formatted timestamp
    """
    if not ts:
        return dim("Never")

    try:
        from datetime import datetime

        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ts


def format_duration(seconds: int | float) -> str:
    """Format a duration in seconds to human-readable format.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted duration string
    """
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        minutes = int(seconds // 60)
        return f"{minutes}m"
    if seconds < 86400:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"

    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    return f"{days}d {hours}h"


def format_list(items: list[str], indent: int = 2) -> str:
    """Format a list of items with bullet points.

    Args:
        items: List of items to format
        indent: Indentation spaces

    Returns:
        Formatted list string
    """
    prefix = " " * indent
    return "\n".join(f"{prefix}{style('•', Colors.CYAN)} {item}" for item in items)


def draw_box(
    title: str = "",
    content: str = "",
    width: int = 60,
    double_border: bool = False,
    title_color: str = Colors.BRIGHT_WHITE,
    border_color: str = Colors.BRIGHT_BLUE,
) -> str:
    """Draw a text box around content with colored borders.

    Args:
        title: Box title
        content: Content inside the box
        width: Box width
        double_border: Use double border characters
        title_color: Color for title
        border_color: Color for border

    Returns:
        Box as string
    """
    if double_border:
        tl, tr, bl, br, h, v = "╔", "╗", "╚", "╝", "═", "║"
    else:
        tl, tr, bl, br, h, v = "┌", "┐", "└", "┘", "─", "│"

    # Ensure minimum width
    width = max(width, len(title) + 4)

    # Build border with color
    colored_h = style(h * width, border_color)
    colored_v = style(v, border_color)

    # Title line
    if title:
        title_padding = (width - len(title) - 2) // 2
        title_line = (
            style(tl, border_color) +
            style(h * title_padding, border_color) +
            " " +
            style(title, title_color, Colors.BOLD) +
            " " +
            style(h * (width - title_padding - len(title) - 2), border_color) +
            style(tr, border_color)
        )
    else:
        title_line = style(tl, border_color) + colored_h + style(tr, border_color)

    # Content lines
    lines = content.split("\n") if content else []
    content_lines = []
    for line in lines:
        # Wrap long lines
        while len(line) > width - 2:
            content_lines.append(colored_v + line[: width - 2] + " " * (width - 2 - len(line[: width - 2])) + style(v, border_color))
            line = line[width - 2:]
        content_lines.append(colored_v + line + " " * (width - 2 - len(line)) + style(v, border_color))

    # Bottom line
    bottom_line = style(bl, border_color) + colored_h + style(br, border_color)

    return "\n".join([title_line] + content_lines + [bottom_line])


def draw_title(title: str, subtitle: str = "", width: int = 70) -> None:
    """Draw a large title banner.

    Args:
        title: Main title
        subtitle: Optional subtitle
        width: Width of the banner
    """
    print()

    # Top decorative line
    print(style("┏" + "━" * width + "┓", Colors.BRIGHT_BLUE))

    # Title line
    if title:
        padding = (width - len(title)) // 2
        print(
            style("┃", Colors.BRIGHT_BLUE) +
            " " * padding +
            style(title, Colors.BRIGHT_WHITE, Colors.BOLD) +
            " " * (width - padding - len(title)) +
            style("┃", Colors.BRIGHT_BLUE)
        )

    # Subtitle line
    if subtitle:
        padding = (width - len(subtitle)) // 2
        print(
            style("┃", Colors.BRIGHT_BLUE) +
            " " * padding +
            style(subtitle, Colors.BRIGHT_CYAN) +
            " " * (width - padding - len(subtitle)) +
            style("┃", Colors.BRIGHT_BLUE)
        )

    # Bottom decorative line
    print(style("┗" + "━" * width + "┛", Colors.BRIGHT_BLUE))
    print()


def draw_separator(char: str = "─", width: int = 70, color: str = Colors.BRIGHT_BLUE) -> None:
    """Draw a separator line.

    Args:
        char: Character to use
        width: Width of the line
        color: ANSI color code
    """
    print(style(char * width, color))


def draw_table(headers: list[str], rows: list[list[str]], padding: int = 2) -> str:
    """Draw a simple table.

    Args:
        headers: Column headers
        rows: Table rows
        padding: Cell padding

    Returns:
        Formatted table string
    """
    if not rows:
        return ""

    # Calculate column widths
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(cell))

    # Build separator
    separator = "+" + "+".join("-" * (w + padding * 2) for w in col_widths) + "+"

    # Build header
    header_cells = []
    for i, h in enumerate(headers):
        header_cells.append(" " * padding + style(h, Colors.BOLD, Colors.BRIGHT_CYAN) + " " * padding)
    header = "|" + "|".join(header_cells) + "|"

    # Build rows
    row_lines = []
    for row in rows:
        cells = []
        for i, cell in enumerate(row):
            if i < len(col_widths):
                cells.append(" " * padding + cell.ljust(col_widths[i] + padding) + " " * padding)
        row_lines.append("|" + "|".join(cells) + "|")

    return "\n".join([separator, header, separator] + row_lines + [separator])


def progress_bar(
    current: int,
    total: int,
    width: int = 40,
    filled_char: str = "█",
    empty_char: str = "░",
    filled_color: str = Colors.BRIGHT_GREEN,
    empty_color: str = Colors.DIM,
) -> str:
    """Generate a progress bar string with colors.

    Args:
        current: Current progress value
        total: Total value
        width: Width of the bar in characters
        filled_char: Character for filled portion
        empty_char: Character for empty portion
        filled_color: Color for filled portion
        empty_color: Color for empty portion

    Returns:
        Progress bar string
    """
    if total <= 0:
        return style(filled_char * width, filled_color)

    filled = int((current / total) * width)
    filled = max(0, min(filled, width))

    return (
        style(filled_char * filled, filled_color) +
        style(empty_char * (width - filled), empty_color)
    )


def clear_screen() -> None:
    """Clear the terminal screen."""
    print("\033[2J\033[H", end="")


def print_header(title: str, subtitle: str = "") -> None:
    """Print a formatted header.

    Args:
        title: Main title
        subtitle: Optional subtitle
    """
    print()
    print(bold(title))
    if subtitle:
        print(dim(subtitle))
    print()


def print_section(title: str, icon: str = "├", color: str = Colors.BRIGHT_CYAN) -> None:
    """Print a section header.

    Args:
        title: Section title
        icon: Icon character to use
        color: Color for the icon
    """
    print()
    print(f"{style(icon, color)}─ {bold(title)} ")
    print(f"{style('│', color)}")


def print_kv(key: str, value: str, indent: int = 2, key_color: str = Colors.CYAN) -> None:
    """Print a key-value pair.

    Args:
        key: Key label
        value: Value to display
        indent: Indentation spaces
        key_color: Color for the key
    """
    prefix = " " * indent
    print(f"{prefix}{style(key, key_color)}: {value}")


def print_highlight(text: str, color: str = Colors.BRIGHT_YELLOW) -> None:
    """Print highlighted text.

    Args:
        text: Text to highlight
        color: Color to use
    """
    print(style("  ► " + text, color, Colors.BOLD))
