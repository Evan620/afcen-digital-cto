"""AfCEN Digital CTO - Enhanced visual styling.

Creates a distinctive visual identity with African sunrise colors (orange/gold)
and unique UI elements to differentiate from standard terminal output.
"""

from __future__ import annotations

import os
from typing import Final

# Detect terminal color support
TERM_COLORS = os.environ.get("TERM", "")
COLORTERM = os.environ.get("COLORTERM", "")
SUPPORTS_COLOR = "256color" in TERM_COLORS or "truecolor" in TERM_COLORS or COLORTERM in ("truecolor", "24bit")

# AfCEN Digital CTO Brand Colors - African Sunrise Theme
class BrandColors:
    """Brand colors for AfCEN Digital CTO - African Sunrise theme."""

    # Primary brand colors (warm, earthy tones representing African sunrise)
    SUNRISE_ORANGE: Final[str] = "\033[38;5;208m"      # #FF8700
    GOLDEN_YELLOW: Final[str] = "\033[38;5;220m"     # #FFD700
    SAHEL_RED: Final[str] = "\033[38;5;124m"         # #AF0000
    SAVANNAH_GREEN: Final[str] = "\033[38;5;100m"    # #875F00
    OCEAN_BLUE: Final[str] = "\033[38;5;31m"        # #0066CC
    DESERT_SAND: Final[str] = "\033[38;5;222m"      # #FFDAB9

    # Status colors (bright variants for visibility)
    SUCCESS: Final[str] = "\033[38;5;34m"            # #00AF00 (bright green)
    ERROR: Final[str] = "\033[38;5;196m"             # #FF0000 (bright red)
    WARNING: Final[str] = "\033[38;5;226m"           # #FFD700 (gold)
    INFO: Final[str] = "\033[38;5;39m"               # #00AFFF (bright blue)
    MUTED: Final[str] = "\033[38;5;245m"             # #875F7F (gray)

    # UI Element colors
    HEADER_BG: Final[str] = "\033[48;5;208m"        # Orange background
    HEADER_FG: Final[str] = "\033[38;5;16m"         # Black on orange
    HIGHLIGHT: Final[str] = "\033[48;5;226m"        # Gold background
    BORDER: Final[str] = "\033[38;5;208m"           # Orange border
    BOLD_TEXT: Final[str] = "\033[1m"

    # Agent-specific colors (distinctive palette)
    CODE_REVIEW: Final[str] = "\033[38;5;27m"       # #005FFF (blue)
    SPRINT_PLANNER: Final[str] = "\033[38;5;34m"    # #00AF00 (green)
    ARCHITECTURE: Final[str] = "\033[38;5;129m"     # #AF87FF (purple)
    DEVOPS: Final[str] = "\033[38;5;203m"           # #FF5F87 (pink)
    MARKET: Final[str] = "\033[38;5;178m"           # #D7AF00 (gold)
    MEETING: Final[str] = "\033[38;5;200m"          # #FF87AF (rose)
    CODING: Final[str] = "\033[38;5;213m"           # #FF87D7 (magenta)

    # Reset
    RESET: Final[str] = "\033[0m"


# Reset code (module-level alias for backwards compatibility)
RESET: Final[str] = "\033[0m"


def cto(text: str, *colors: str) -> str:
    """Apply AfCEN Digital CTO brand styling.

    Args:
        text: Text to style
        *colors: Color codes

    Returns:
        Styled text with reset
    """
    return "".join(colors) + text + RESET


def brand(text: str) -> str:
    """Apply brand orange color."""
    return cto(text, BrandColors.BOLD_TEXT, BrandColors.SUNRISE_ORANGE)


def gold(text: str) -> str:
    """Apply gold color."""
    return cto(text, BrandColors.BOLD_TEXT, BrandColors.GOLDEN_YELLOW)


def header_box(text: str) -> str:
    """Style header text (orange background, black text)."""
    return cto(text, BrandColors.HEADER_BG, BrandColors.HEADER_FG, BrandColors.BOLD_TEXT)


def success(text: str) -> str:
    """Style success text."""
    return cto(text, BrandColors.SUCCESS)


def error(text: str) -> str:
    """Style error text."""
    return cto(text, BrandColors.ERROR)


def warning(text: str) -> str:
    """Style warning text."""
    return cto(text, BrandColors.WARNING)


def info(text: str) -> str:
    """Style info text."""
    return cto(text, BrandColors.INFO)


def muted(text: str) -> str:
    """Style muted text."""
    return cto(text, BrandColors.MUTED)


def bold(text: str) -> str:
    """Style bold text."""
    return cto(text, BrandColors.BOLD_TEXT)


def radio_selected(text: str) -> str:
    """Style selected radio option."""
    return cto(f"◆ {text}", BrandColors.SUNRISE_ORANGE, BrandColors.BOLD_TEXT)


def radio_unselected(text: str) -> str:
    """Style unselected radio option."""
    return cto(f"◇ {text}", BrandColors.MUTED)


def checkbox_checked(text: str) -> str:
    """Style checked checkbox."""
    return cto(f"☒ {text}", BrandColors.SUCCESS, BrandColors.BOLD_TEXT)


def checkbox_unchecked(text: str) -> str:
    """Style unchecked checkbox."""
    return cto(f"☐ {text}", BrandColors.MUTED)


def agent_styled(agent_name: str, text: str) -> str:
    """Apply agent-specific coloring.

    Args:
        agent_name: Agent name
        text: Text to style

    Returns:
        Color-styled text
    """
    agent_lower = agent_name.lower()

    if "code" in agent_lower or "review" in agent_lower:
        return cto(text, BrandColors.CODE_REVIEW, BrandColors.BOLD_TEXT)
    if "sprint" in agent_lower:
        return cto(text, BrandColors.SPRINT_PLANNER, BrandColors.BOLD_TEXT)
    if "arch" in agent_lower:
        return cto(text, BrandColors.ARCHITECTURE, BrandColors.BOLD_TEXT)
    if "devops" in agent_lower:
        return cto(text, BrandColors.DEVOPS, BrandColors.BOLD_TEXT)
    if "market" in agent_lower:
        return cto(text, BrandColors.MARKET, BrandColors.BOLD_TEXT)
    if "meeting" in agent_lower:
        return cto(text, BrandColors.MEETING, BrandColors.BOLD_TEXT)
    if "coding" in agent_lower:
        return cto(text, BrandColors.CODING, BrandColors.BOLD_TEXT)

    return text


# ASCII Art Logo - African Continent + Digital CTO
DTI_LOGO = r"""
╔════════════════════════════════════════════════════════════════════════╗
║                                                                          ║
║                  🌍  AfCEN Digital CTO                                  ║
║                                                                          ║
║              AI-Powered Multi-Agent Technical Leadership                    ║
║                  for Africa Climate Energy Nexus                          ║
║                                                                          ║
╚════════════════════════════════════════════════════════════════════════╝
"""

SIMPLE_LOGO = r"""
┌──────────────────────────────────────────────────────────────────────┐
│                                                                          │
│    ╔═════════════════════════════════════════════════════════════╗  │
│    ║                                                                  ║  │
│    ║         🌍  AfCEN Digital CTO                                   ║  │
│    ║                                                                  ║  │
│    ║         AI-Powered Technical Leadership                        ║  │
│    ║                                                                  ║  │
│    ╚═══════════════════════════════════════════════════════════════╝  │
│                                                                          │
└──────────────────────────────────────────────────────────────────────┘
"""

AFRICAN_SUNRISE_LOGO = r"""
╔════════════════════════════════════════════════════════════════════════╗
║                                                                          ║
║              🌅                                                      ║
║           ╱  ╲  ╱  ╲  ╱  ╲                                          ║
║          ╱    ╲╱    ╲╱    ╲                                        ║
║         ╱      ╲╱      ╲╱      ╲          🌍                   ║
║        ╱        ╲        ╲        ╲        AfCEN Digital CTO     ║
║       ╱    ╱──────────────╱    ╱                                 ║
║      ╲    ╲                ╲    ╲                                 ║
║       ╲  ╲                  ╲  ╲                                 ║
║        ╲                    ╲                                   ║
║         ───────────────────                                ║
║                                                          ║
╚════════════════════════════════════════════════════════════════════════╝
"""


def draw_logo(width: int = 70) -> None:
    """Draw the AfCEN Digital CTO logo.

    Args:
        width: Width for centering
    """
    print(DTI_LOGO)


def draw_header_bar(title: str, width: int = 70) -> None:
    """Draw a header bar with brand colors.

    Args:
        title: Header title
        width: Width of the bar
    """
    # Orange background bar with title
    title_padding = (width - len(title) - 4) // 2
    bar = (
        cto("┏", BrandColors.SUNRISE_ORANGE) +
        "━" * title_padding +
        header_box(f" {title} ") +
        "━" * (width - title_padding - len(title) - 4) +
        cto("┓", BrandColors.SUNRISE_ORANGE)
    )
    print(bar)

    # Sub-header line
    print(
        cto("┃", BrandColors.SUNRISE_ORANGE) +
        " " * width +
        cto("┃", BrandColors.SUNRISE_ORANGE)
    )


def draw_section_header(title: str, width: int = 70) -> None:
    """Draw a section header with styling.

    Args:
        title: Section title
        width: Width of the line
    """
    print()
    line = cto("├─" + "─" * (width - 3) + "┤", BrandColors.SUNRISE_ORANGE)
    print(line)
    print(cto(f"│  {title}", BrandColors.SUNRISE_ORANGE, BrandColors.BOLD_TEXT))


def draw_box(
    title: str = "",
    content: str = "",
    width: int = 70,
    style_type: str = "default",
) -> str:
    """Draw a stylized box with AfCEN branding.

    Args:
        title: Box title
        content: Box content
        width: Box width
        style_type: 'default', 'highlight', 'muted'

    Returns:
        Box as string
    """
    if style_type == "highlight":
        border = cto("║", BrandColors.SUNRISE_ORANGE)
        h = cto("═", BrandColors.SUNRISE_ORANGE)
        corners = [cto("╔", BrandColors.SUNRISE_ORANGE), cto("╗", BrandColors.SUNRISE_ORANGE),
                   cto("╚", BrandColors.SUNRISE_ORANGE), cto("╝", BrandColors.SUNRISE_ORANGE)]
        title_color = BrandColors.SUNRISE_ORANGE
    elif style_type == "muted":
        border = cto("║", BrandColors.MUTED)
        h = cto("─", BrandColors.MUTED)
        corners = [cto("┌", BrandColors.MUTED), cto("┐", BrandColors.MUTED),
                   cto("└", BrandColors.MUTED), cto("┘", BrandColors.MUTED)]
        title_color = BrandColors.MUTED
    else:
        border = cto("║", BrandColors.MUTED)
        h = cto("─", BrandColors.MUTED)
        corners = [cto("┌", BrandColors.MUTED), cto("┐", BrandColors.MUTED),
                   cto("└", BrandColors.MUTED), cto("┘", BrandColors.MUTED)]
        title_color = BrandColors.SUNRISE_ORANGE

    # Ensure minimum width
    width = max(width, len(title) + 4)

    # Title line
    if title:
        title_padding = (width - len(title) - 2) // 2
        title_line = (
            corners[0] + h * title_padding + " " +
            cto(title, title_color, BrandColors.BOLD_TEXT) +
            " " + h * (width - title_padding - len(title) - 2) + corners[1]
        )
    else:
        title_line = corners[0] + h * width + corners[1]

    # Content lines
    lines = content.split("\n") if content else []
    content_lines = []
    for line in lines:
        # Wrap long lines
        while len(line) > width - 2:
            content_lines.append(border + line[: width - 2] + " " * (width - 2 - len(line[: width - 2])) + border)
            line = line[width - 2:]
        content_lines.append(border + line + " " * (width - 2 - len(line)) + border)

    # Bottom line
    bottom_line = corners[2] + h * width + corners[3]

    return "\n".join([title_line] + content_lines + [bottom_line])


def status_icon(status: str) -> str:
    """Return a colored status icon.

    Args:
        status: Status string

    Returns:
        Colored icon
    """
    status_lower = status.lower()

    icons = {
        ("running", "active", "online", "connected", "up", "healthy", "ok", "ready"): ("🟢", BrandColors.SUCCESS),
        ("stopped", "inactive", "offline", "disconnected", "down"): ("🔴", BrandColors.ERROR),
        ("error", "failed", "unhealthy", "crashed"): ("❌", BrandColors.ERROR),
        ("warning", "degraded", "slow"): ("⚠️", BrandColors.WARNING),
        ("pending", "starting", "loading"): ("⏳", BrandColors.INFO),
        ("disabled", "off"): ("⭕", BrandColors.MUTED),
    }

    for keys, (icon, color) in icons.items():
        if status_lower in keys:
            return cto(icon, color)

    return cto("•", BrandColors.MUTED)


def menu_item(num: int, text: str, description: str = "", selected: bool = False) -> str:
    """Format a menu item.

    Args:
        num: Menu number
        text: Item text
        description: Optional description
        selected: Whether this item is selected

    Returns:
        Formatted menu item
    """
    if selected:
        prefix = cto("►", BrandColors.SUNRISE_ORANGE)
        num_str = cto(str(num).rjust(2), BrandColors.SUNRISE_ORANGE, BrandColors.BOLD_TEXT)
        text_str = cto(text, BrandColors.SUNRISE_ORANGE, BrandColors.BOLD_TEXT)
    else:
        prefix = " "
        num_str = str(num).rjust(2)
        text_str = text

    result = f"  {prefix} {num_str}. {text_str}"
    if description:
        result += cto(f" - {description}", BrandColors.MUTED)

    return result


def draw_progress_bar(percent: int, width: int = 30) -> str:
    """Draw a progress bar with AfCEN colors.

    Args:
        percent: Progress percentage (0-100)
        width: Bar width in characters

    Returns:
        Progress bar string
    """
    filled = int((percent / 100) * width)

    # Orange filled bar with gold leading edge
    if percent > 0:
        bar = (
            cto("█" * (filled - 1), BrandColors.SUNRISE_ORANGE) +
            cto("█", BrandColors.GOLDEN_YELLOW) +
            cto("░" * (width - filled), BrandColors.MUTED)
        )
    else:
        bar = cto("░" * width, BrandColors.MUTED)

    return bar


def clear_screen() -> None:
    """Clear the terminal screen."""
    print("\033[2J\033[H", end="")


# Re-export commonly used functions
from src.tui.utils.formatting import format_timestamp, format_duration, truncate, Colors, Theme
