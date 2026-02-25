"""Tests for TUI configuration management."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from pydantic import ValidationError

from src.tui.onboard.config import (
    LLMConfig,
    GitHubConfig,
    AgentConfig,
    AgentsConfig,
    SchedulerConfig,
    JarvisConfig,
    IntegrationsConfig,
    TUIConfig,
    get_default_config,
    load_config,
    save_config,
    is_onboarded,
    mark_onboarded,
    reset_config,
)


class TestLLMConfig:
    """Tests for LLMConfig."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = LLMConfig()
        assert config.provider == "anthropic"
        assert config.model == "claude-opus-4-6"
        assert config.fallback_provider == "azure_openai"

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = LLMConfig(provider="azure_openai", model="gpt-4o")
        assert config.provider == "azure_openai"
        assert config.model == "gpt-4o"


class TestGitHubConfig:
    """Tests for GitHubConfig."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = GitHubConfig()
        assert config.repos == []

    def test_with_repos(self) -> None:
        """Test configuration with repos."""
        config = GitHubConfig(repos=["afcen/platform", "bayes/app"])
        assert config.repos == ["afcen/platform", "bayes/app"]


class TestTUIConfig:
    """Tests for TUIConfig."""

    def test_default_config(self) -> None:
        """Test default configuration."""
        config = TUIConfig()
        assert config.onboarded is False
        assert config.llm.provider == "anthropic"
        assert config.github.repos == []
        assert config.backend_url == "http://localhost:8000"

    def test_to_dict(self) -> None:
        """Test converting config to dictionary."""
        config = TUIConfig()
        data = config.to_dict()
        assert "version" in data
        assert "llm" in data
        assert "github" in data

    def test_from_dict(self) -> None:
        """Test creating config from dictionary."""
        data = {
            "version": "0.3.0",
            "llm": {"provider": "azure_openai", "model": "gpt-4o"},
            "github": {"repos": ["test/repo"]},
        }
        config = TUIConfig(**data)
        assert config.llm.provider == "azure_openai"
        assert config.github.repos == ["test/repo"]


class TestConfigPersistence:
    """Tests for configuration persistence."""

    @pytest.fixture
    def temp_config_path(self, tmp_path: Path) -> Path:
        """Create a temporary config path."""
        return tmp_path / "config.json"

    def test_save_and_load(self, temp_config_path: Path) -> None:
        """Test saving and loading configuration."""
        config = TUIConfig()
        config.github.repos = ["afcen/platform"]

        # Save
        assert save_config(config, temp_config_path) is True
        assert temp_config_path.exists()

        # Load
        loaded = load_config(temp_config_path)
        assert loaded.github.repos == ["afcen/platform"]

    def test_load_nonexistent_returns_default(self, temp_config_path: Path) -> None:
        """Test loading non-existent config returns default."""
        config = load_config(temp_config_path)
        assert isinstance(config, TUIConfig)
        assert config.onboarded is False

    def test_is_onboarded(self, temp_config_path: Path) -> None:
        """Test is_onboarded function."""
        # Not onboarded initially
        assert is_onboarded(temp_config_path) is False

        # Mark as onboarded
        config = TUIConfig()
        save_config(config, temp_config_path)
        mark_onboarded(temp_config_path)

        # Now should be onboarded
        assert is_onboarded(temp_config_path) is True

    def test_mark_onboarded_updates_timestamp(self, temp_config_path: Path) -> None:
        """Test that mark_onboarded sets timestamp."""
        config = TUIConfig()
        save_config(config, temp_config_path)

        mark_onboarded(temp_config_path)
        loaded = load_config(temp_config_path)

        assert loaded.onboarded is True
        assert loaded.onboarded_at != ""
        assert "T" in loaded.onboarded_at  # ISO format

    def test_reset_config(self, temp_config_path: Path) -> None:
        """Test resetting configuration."""
        # Create a config with changes
        config = TUIConfig()
        config.github.repos = ["test/repo"]
        config.llm.provider = "azure_openai"
        save_config(config, temp_config_path)

        # Reset
        assert reset_config(temp_config_path) is True

        # Should be back to defaults
        loaded = load_config(temp_config_path)
        assert loaded.github.repos == []
        assert loaded.llm.provider == "anthropic"

    def test_invalid_json_graceful_handling(self, temp_config_path: Path) -> None:
        """Test handling of invalid JSON in config file."""
        # Write invalid JSON
        temp_config_path.write_text("{ invalid json }")

        # Should return default config instead of crashing
        config = load_config(temp_config_path)
        assert isinstance(config, TUIConfig)


class TestAgentConfig:
    """Tests for agent configuration."""

    def test_default_agent_enabled(self) -> None:
        """Test that agents are enabled by default."""
        config = AgentConfig()
        assert config.enabled is True

    def test_agents_config_default(self) -> None:
        """Test default agents configuration."""
        config = AgentsConfig()
        assert config.code_review.enabled is True
        assert config.sprint_planner.enabled is True
        assert config.market_scanner.enabled is False
        assert config.meeting_intelligence.enabled is False


class TestSchedulerConfig:
    """Tests for scheduler configuration."""

    def test_default_cron_schedules(self) -> None:
        """Test default cron schedule values."""
        config = SchedulerConfig()
        assert config.daily_standup == "0 8 * * 1-5"
        assert config.weekly_report == "0 9 * * 1"
        assert config.bayes_alerts == "0 10 * * 1,3,5"

    def test_timezone(self) -> None:
        """Test default timezone."""
        config = SchedulerConfig()
        assert config.timezone == "Africa/Nairobi"
