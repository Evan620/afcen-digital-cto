"""Navigation and keyboard handling utilities for TUI.

Provides keyboard input handling, menu navigation, and common interaction patterns.
"""

from __future__ import annotations

import os
import sys
from typing import Callable

# Key codes
class Keys:
    """Special key codes."""

    ENTER = "\r"
    ESC = "\x1b"
    TAB = "\t"
    CTRL_C = "\x03"
    CTRL_L = "\x0c"
    CTRL_D = "\x04"

    # Arrow keys (escape sequences)
    UP = "\x1b[A"
    DOWN = "\x1b[B"
    RIGHT = "\x1b[C"
    LEFT = "\x1b[D"

    # Page keys
    PAGE_UP = "\x1b[5~"
    PAGE_DOWN = "\x1b[6~"
    HOME = "\x1b[H"
    END = "\x1b[F"

    # Delete
    DELETE = "\x1b[3~"
    BACKSPACE = "\x7f"


def clear_screen() -> None:
    """Clear the terminal screen."""
    print("\033[2J\033[H", end="")


def pause(message: str = "Press Enter to continue...") -> None:
    """Pause execution until user presses Enter.

    Args:
        message: Message to display
    """
    print()
    input(message)


def confirm(message: str, default: bool = True) -> bool:
    """Ask user for yes/no confirmation.

    Args:
        message: Confirmation message
        default: Default value if user just presses Enter

    Returns:
        True if user confirms, False otherwise
    """
    prompt = f"{message} [{'Y/n' if default else 'y/N'}]: "
    response = input(prompt).strip().lower()

    if not response:
        return default

    return response in ("y", "yes")


def select_option(
    prompt: str,
    options: list[str],
    default: int | None = None,
) -> int:
    """Let user select an option from a list.

    Args:
        prompt: Prompt message
        options: List of options to display
        default: Default index (1-based)

    Returns:
        Selected index (0-based)
    """
    from src.tui.utils.formatting import bold, dim

    print()
    for i, option in enumerate(options, 1):
        is_default = default is not None and i == default
        prefix = "►" if is_default else " "
        label = bold(f"{i}.") if is_default else f"{i}."
        print(f"  {prefix} {label} {option}")
    print()

    while True:
        try:
            response = input(f"{prompt} [1-{len(options)}]: ").strip()
            if not response and default is not None:
                return default - 1

            index = int(response) - 1
            if 0 <= index < len(options):
                return index

            print(dim("Invalid selection, try again."))
        except (ValueError, KeyboardInterrupt):
            print(dim("Invalid selection, try again."))


def multi_select(
    prompt: str,
    options: list[str],
    defaults: list[int] | None = None,
) -> list[int]:
    """Let user select multiple options from a list.

    Args:
        prompt: Prompt message
        options: List of options to display
        defaults: Default selected indices (1-based)

    Returns:
        List of selected indices (0-based)
    """
    from src.tui.utils.formatting import bold, dim, success

    defaults_set = set(defaults or [])
    selected = set(i - 1 for i in defaults_set)

    print()
    for i, option in enumerate(options, 1):
        is_selected = i - 1 in selected
        is_default = i in defaults_set
        prefix = "☑" if is_selected else "☐"
        label = bold(str(i))
        status = " (default)" if is_default else ""
        print(f"  [{prefix}] {label}. {option}{status}")
    print()

    print(dim("Enter numbers separated by commas (e.g., 1,3,5) or ranges (1-3)"))
    print(dim("Press Enter with no input to confirm current selection"))
    print()

    while True:
        try:
            response = input(f"{prompt}: ").strip()

            if not response:
                return sorted(selected)

            # Parse selection
            new_selected = set()
            parts = response.split(",")

            for part in parts:
                part = part.strip()
                if "-" in part:
                    # Range
                    start, end = part.split("-")
                    start = int(start.strip()) - 1
                    end = int(end.strip()) - 1
                    new_selected.update(range(min(start, end), max(start, end) + 1))
                else:
                    # Single number
                    idx = int(part) - 1
                    new_selected.add(idx)

            # Validate
            if all(0 <= i < len(options) for i in new_selected):
                selected = new_selected
                return sorted(selected)

            print(dim("Some selections were out of range."))
        except (ValueError, KeyboardInterrupt):
            print(dim("Invalid input, try again."))


def _flush_stdin() -> None:
    """Flush any pending data from stdin and /dev/tty.

    This prevents contamination when another process has written to the
    terminal while we're waiting for user input.  We flush both stdin
    (used by input()) and /dev/tty (used by getpass.getpass()).
    """
    import select
    import termios

    # Flush stdin
    try:
        while select.select([sys.stdin], [], [], 0.0)[0]:
            sys.stdin.readline()
    except (OSError, ValueError):
        pass

    # Flush /dev/tty (getpass reads from here on Linux)
    try:
        fd = os.open("/dev/tty", os.O_RDWR | os.O_NONBLOCK)
        try:
            termios.tcflush(fd, termios.TCIFLUSH)
        finally:
            os.close(fd)
    except (OSError, termios.error):
        pass


def edit_text(
    prompt: str,
    default: str = "",
    password: bool = False,
) -> str:
    """Get text input from user.

    Args:
        prompt: Prompt message
        default: Default value
        password: Hide input (for passwords)

    Returns:
        User input
    """
    import getpass

    if default:
        prompt = f"{prompt} [{default}]: "
    else:
        prompt = f"{prompt}: "

    # Flush stale stdin to avoid reading garbage from concurrent processes
    _flush_stdin()

    if password:
        response = getpass.getpass(prompt)
        # Strip whitespace but keep the actual key (no trimming for secrets)
        # Only use default if response is truly empty (user just pressed Enter)
        return response if response is not None and response != "" else default

    response = input(prompt)
    return response if response else default


def progress_bar(
    current: int,
    total: int,
    width: int = 40,
    filled_char: str = "█",
    empty_char: str = "░",
) -> str:
    """Generate a progress bar string.

    Args:
        current: Current progress value
        total: Total value
        width: Width of the bar in characters
        filled_char: Character for filled portion
        empty_char: Character for empty portion

    Returns:
        Progress bar string
    """
    if total <= 0:
        return filled_char * width

    filled = int((current / total) * width)
    filled = max(0, min(filled, width))
    return filled_char * filled + empty_char * (width - filled)


class MenuNavigator:
    """Simple menu navigator for keyboard-driven menus."""

    def __init__(
        self,
        items: list[str],
        title: str = "",
        allow_exit: bool = True,
    ):
        """Initialize the menu navigator.

        Args:
            items: List of menu items
            title: Optional menu title
            allow_exit: Whether to allow exiting with 0/q
        """
        self.items = items
        self.title = title
        self.allow_exit = allow_exit
        self.current_index = 0

    def display(self) -> str:
        """Display the menu and return the selected index.

        Returns:
            Selected index (0-based) or None if exited
        """
        from src.tui.utils.formatting import bold, dim, success

        while True:
            print()
            if self.title:
                print(bold(self.title))
                print()

            for i, item in enumerate(self.items):
                is_current = i == self.current_index
                prefix = success("►") if is_current else " "
                num = bold(f"{i + 1}")
                print(f"  {prefix} {num}. {item}")

            if self.allow_exit:
                print()
                print(f"    0. {dim('Exit')}")

            print()
            print(dim("Use arrow keys or number to select, Enter to confirm"))

            # Get user input
            try:
                response = input("Selection: ").strip()

                if not response:
                    return self.current_index

                # Check for exit
                if response in ("0", "q", "Q", "exit"):
                    if self.allow_exit:
                        return None
                    continue

                # Number input
                try:
                    index = int(response) - 1
                    if 0 <= index < len(self.items):
                        return index
                except ValueError:
                    pass

                print(dim("Invalid selection."))
            except KeyboardInterrupt:
                if self.allow_exit:
                    return None
                continue


async def async_input(prompt: str) -> str:
    """Async version of input().

    Args:
        prompt: Prompt message

    Returns:
        User input
    """
    import asyncio

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, input, prompt)


class CommandHistory:
    """Command history for chat interfaces."""

    def __init__(self, max_size: int = 100):
        """Initialize command history.

        Args:
            max_size: Maximum number of commands to store
        """
        self.history: list[str] = []
        self.max_size = max_size
        self.index = -1
        self._temp_input = ""

    def add(self, command: str) -> None:
        """Add a command to history.

        Args:
            command: Command to add
        """
        if command and (not self.history or self.history[-1] != command):
            self.history.append(command)
            if len(self.history) > self.max_size:
                self.history.pop(0)

    def up(self, current: str) -> str:
        """Go up in history.

        Args:
            current: Current input

        Returns:
            Previous command or current if at start
        """
        if self.index == -1:
            self._temp_input = current

        if self.index < len(self.history) - 1:
            self.index += 1
            return self.history[-(self.index + 1)]

        return current

    def down(self, current: str) -> str:
        """Go down in history.

        Args:
            current: Current input

        Returns:
            Next command or temp input if at end
        """
        if self.index > 0:
            self.index -= 1
            return self.history[-(self.index + 1)]

        if self.index == 0:
            self.index = -1
            return self._temp_input

        return current

    def reset(self) -> None:
        """Reset history navigation."""
        self.index = -1
        self._temp_input = ""
