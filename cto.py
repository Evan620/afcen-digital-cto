#!/usr/bin/env python3
"""Wrapper script for the 'cto' command.

This allows running the TUI without installing the package.
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.tui.cli import main

if __name__ == "__main__":
    main()
