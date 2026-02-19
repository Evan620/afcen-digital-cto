"""Application configuration loaded from environment variables."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for the Digital CTO system.

    Values are loaded from environment variables or a .env file.
    Docker Compose sets REDIS_URL, POSTGRES_URL, and QDRANT_URL automatically.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Environment ──
    environment: str = Field(default="development", description="development | staging | production")
    log_level: str = Field(default="INFO", description="Python logging level")

    # ── LLM: Azure OpenAI ──
    azure_openai_api_key: str = Field(default="", description="Azure OpenAI API key")
    azure_openai_endpoint: str = Field(default="", description="Azure OpenAI endpoint URL")
    azure_openai_deployment: str = Field(default="gpt-4o", description="Azure deployment name")
    azure_openai_api_version: str = Field(default="2024-10-21", description="Azure API version")

    # ── LLM: Anthropic (Claude) — preferred for code review ──
    anthropic_api_key: str = Field(default="", description="Anthropic API key for Claude")

    # ── LLM: z.ai (GLM) — OpenAI-compatible ──
    zai_api_key: str = Field(default="", description="z.ai API key")
    zai_base_url: str = Field(default="https://api.z.ai/api/coding/paas/v4", description="z.ai base URL")
    zai_model: str = Field(default="glm-5", description="z.ai model name")

    # ── GitHub ──
    github_token: str = Field(default="", description="GitHub Personal Access Token")
    github_webhook_secret: str = Field(default="", description="Secret for webhook HMAC verification")
    github_repos: str = Field(default="", description="Comma-separated owner/repo list to monitor")

    # ── Memory Stores ──
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis connection URL")
    postgres_url: str = Field(
        default="postgresql+asyncpg://cto:cto_secret@localhost:5432/digital_cto",
        description="PostgreSQL async connection URL",
    )
    qdrant_url: str = Field(default="http://localhost:6333", description="Qdrant server URL")

    @property
    def monitored_repos(self) -> list[str]:
        """Parse comma-separated repo list into a list of 'owner/repo' strings."""
        if not self.github_repos:
            return []
        return [r.strip() for r in self.github_repos.split(",") if r.strip()]

    @property
    def has_azure_openai(self) -> bool:
        return bool(self.azure_openai_api_key and self.azure_openai_endpoint)

    @property
    def has_anthropic(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def has_zai(self) -> bool:
        return bool(self.zai_api_key)


# Singleton instance — import this everywhere
settings = Settings()
