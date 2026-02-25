"""Fixtures for TUI tests."""

from __future__ import annotations

import pytest
from src.tui.onboard.config import TUIConfig


@pytest.fixture
def sample_config() -> TUIConfig:
    """Create a sample configuration for testing."""
    config = TUIConfig()
    config.github.repos = ["afcen/platform", "bayes/app"]
    config.llm.provider = "anthropic"
    config.llm.model = "claude-opus-4-6"
    return config
