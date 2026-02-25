"""Configuration management for the Digital CTO TUI.

Handles loading, saving, and validating the ~/.digital-cto/config.json file.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, field_validator

if TYPE_CHECKING:
    from collections.abc import Mapping

logger = logging.getLogger(__name__)

# Default configuration path
CONFIG_DIR = Path.home() / ".digital-cto"
CONFIG_FILE = CONFIG_DIR / "config.json"


class LLMConfig(BaseModel):
    """LLM provider configuration.

    Secrets (api_key) are stored in .env only, not in this config.
    """

    provider: str = "anthropic"  # anthropic, azure_openai, zai
    model: str = "claude-opus-4-6"
    fallback_provider: str = "azure_openai"


class GitHubConfig(BaseModel):
    """GitHub integration configuration.

    Secrets (token, webhook_secret) are stored in .env only, not in this config.
    """

    repos: list[str] = Field(default_factory=list)


class AgentConfig(BaseModel):
    """Configuration for individual agents."""

    enabled: bool = True
    auto_review: bool = False  # For code review agent


class AgentsConfig(BaseModel):
    """All agents configuration."""

    code_review: AgentConfig = Field(default_factory=AgentConfig)
    sprint_planner: AgentConfig = Field(default_factory=AgentConfig)
    architecture_advisor: AgentConfig = Field(default_factory=AgentConfig)
    devops: AgentConfig = Field(default_factory=AgentConfig)
    market_scanner: AgentConfig = Field(default_factory=lambda: AgentConfig(enabled=False))
    meeting_intelligence: AgentConfig = Field(default_factory=lambda: AgentConfig(enabled=False))
    coding_agent: AgentConfig = Field(default_factory=lambda: AgentConfig(enabled=False))


class SchedulerConfig(BaseModel):
    """Scheduler configuration."""

    enabled: bool = True
    timezone: str = "Africa/Nairobi"
    daily_standup: str = "0 8 * * 1-5"
    weekly_report: str = "0 9 * * 1"
    bayes_alerts: str = "0 10 * * 1,3,5"
    market_scan: str = "0 3 * * *"
    morning_brief: str = "0 6 * * *"


class JarvisConfig(BaseModel):
    """JARVIS integration configuration."""

    enabled: bool = True
    gateway_url: str = "ws://100.125.211.92:18789"
    token: str = "digital_cto_2026"


class IntegrationsConfig(BaseModel):
    """External integrations configuration."""

    jarvis: JarvisConfig = Field(default_factory=JarvisConfig)


class TUIConfig(BaseModel):
    """Main Digital CTO TUI configuration."""

    version: str = "0.3.0"
    onboarded: bool = False
    onboarded_at: str = ""
    backend_url: str = "http://localhost:8000"

    llm: LLMConfig = Field(default_factory=LLMConfig)
    github: GitHubConfig = Field(default_factory=GitHubConfig)
    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    integrations: IntegrationsConfig = Field(default_factory=IntegrationsConfig)

    @field_validator("onboarded_at", mode="before")
    @classmethod
    def parse_onboarded_at(cls, v: str | None) -> str:
        """Parse and validate the onboarded_at timestamp."""
        if not v:
            return ""
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
            return v
        except ValueError:
            return ""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return self.model_dump(mode="json", exclude_none=True)


def get_default_config() -> TUIConfig:
    """Get the default configuration."""
    return TUIConfig()


def load_config(config_path: Path | None = None) -> TUIConfig:
    """Load configuration from file.

    Args:
        config_path: Path to config file. Defaults to ~/.digital-cto/config.json

    Returns:
        TUIConfig instance with loaded or default values
    """
    path = config_path or CONFIG_FILE

    if not path.exists():
        logger.debug("Config file not found at %s, using defaults", path)
        return get_default_config()

    try:
        with open(path) as f:
            data = json.load(f)
        config = TUIConfig(**data)
        logger.debug("Loaded config from %s", path)
        return config
    except json.JSONDecodeError as e:
        logger.warning("Invalid JSON in config file: %s", e)
        return get_default_config()
    except Exception as e:
        logger.warning("Error loading config: %s", e)
        return get_default_config()


def save_config(config: TUIConfig, config_path: Path | None = None) -> bool:
    """Save configuration to file.

    Args:
        config: Configuration to save
        config_path: Path to save to. Defaults to ~/.digital-cto/config.json

    Returns:
        True if save was successful, False otherwise
    """
    path = config_path or CONFIG_FILE

    # Ensure config directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(path, "w") as f:
            json.dump(config.to_dict(), f, indent=2)
        logger.debug("Saved config to %s", path)
        return True
    except Exception as e:
        logger.error("Error saving config: %s", e)
        return False


def migrate_config(old_data: Mapping) -> dict:
    """Migrate old configuration format to new format.

    Handles version upgrades and schema changes.
    """
    # For now, just return the data as-is
    # Future versions will handle migrations
    return dict(old_data)


def is_onboarded(config_path: Path | None = None) -> bool:
    """Check if the user has completed onboarding.

    Args:
        config_path: Path to config file. Defaults to ~/.digital-cto/config.json

    Returns:
        True if onboarded, False otherwise
    """
    config = load_config(config_path)
    return config.onboarded


def mark_onboarded(config_path: Path | None = None) -> bool:
    """Mark the user as having completed onboarding.

    Args:
        config_path: Path to config file. Defaults to ~/.digital-cto/config.json

    Returns:
        True if successful, False otherwise
    """
    config = load_config(config_path)
    config.onboarded = True
    config.onboarded_at = datetime.now().isoformat()
    return save_config(config, config_path)


def reset_config(config_path: Path | None = None) -> bool:
    """Reset configuration to defaults.

    Useful for testing or starting fresh.

    Args:
        config_path: Path to config file. Defaults to ~/.digital-cto/config.json

    Returns:
        True if successful, False otherwise
    """
    path = config_path or CONFIG_FILE
    default_config = get_default_config()
    return save_config(default_config, path)
