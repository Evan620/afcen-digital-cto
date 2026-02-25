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

    # ── OpenClaw Gateway (JARVIS Integration) ──
    openclaw_gateway_url: str = Field(
        default="http://100.125.211.92:18789",
        description="OpenClaw Gateway URL (HTTP for health, WS for messaging)",
    )
    openclaw_enabled: bool = Field(
        default=False,
        description="Enable OpenClaw integration for JARVIS communication",
    )
    openclaw_gateway_token: str = Field(
        default="digital_cto_2026",
        description="Token for OpenClaw Gateway authentication",
    )

    # ── GitHub Projects V2 ──
    github_project_number: int = Field(default=0, description="Projects V2 number (0 = disabled)")
    github_org: str = Field(default="", description="GitHub org for Projects V2")

    # ── Scheduler ──
    scheduler_enabled: bool = Field(default=True, description="Enable APScheduler automation")
    daily_standup_cron: str = Field(default="0 8 * * 1-5", description="Daily standup cron (8 AM weekdays)")
    weekly_report_cron: str = Field(default="0 9 * * 1", description="Weekly report cron (9 AM Monday)")
    bayes_alert_cron: str = Field(default="0 10 * * 1,3,5", description="Bayes alert cron (MWF 10 AM)")

    # ── Phase 3: Market Scanner ──
    market_scan_enabled: bool = Field(default=True, description="Enable market data collection")
    morning_brief_enabled: bool = Field(default=True, description="Enable morning brief generation")
    market_scan_cron: str = Field(default="0 3 * * *", description="Market scan cron (3 AM daily)")
    morning_brief_cron: str = Field(default="0 6 * * *", description="Morning brief cron (6 AM daily)")

    # ── Phase 3: Market Data Sources ──
    feedly_api_key: str = Field(default="", description="Feedly API key for news aggregation")
    world_bank_api_key: str = Field(default="", description="World Bank Projects API key")
    verra_api_key: str = Field(default="", description="Verra Registry API key")
    gold_standard_api_key: str = Field(default="", description="Gold Standard Registry API key")
    twitter_api_key: str = Field(default="", description="Twitter/X API key for social listening")
    openalex_api_key: str = Field(default="", description="OpenAlex API key for research papers")

    # ── Phase 3: Meeting Intelligence ──
    recall_api_key: str = Field(default="", description="Recall.ai API key for meeting bots")
    assemblyai_api_key: str = Field(default="", description="AssemblyAI API key for transcript analysis")
    deepgram_api_key: str = Field(default="", description="Deepgram API key for real-time STT")
    elevenlabs_api_key: str = Field(default="", description="ElevenLabs API key for TTS")

    # ── Phase 4: Coding Agents ──
    coding_enabled: bool = Field(default=True, description="Enable coding agent execution")
    claude_code_enabled: bool = Field(default=True, description="Enable Claude Code integration")
    coding_timeout: int = Field(default=300, description="Coding task timeout in seconds")
    coding_sandbox_image: str = Field(
        default="mcr.microsoft.com/devcontainers/base:ubuntu",
        description="Docker image for coding sandbox",
    )
    coding_workspace_path: str = Field(default="/tmp/workspace", description="Path for coding workspaces")

    # ── Phase 4: Knowledge Graph ──
    knowledge_graph_enabled: bool = Field(default=True, description="Enable knowledge graph")
    knowledge_graph_name: str = Field(default="afcen_knowledge", description="Name of Apache AGE graph")

    # ── Phase 4: A2A Protocol ──
    a2a_enabled: bool = Field(default=True, description="Enable A2A protocol")
    a2a_agent_discovery: bool = Field(default=True, description="Enable automatic agent discovery")
    a2a_known_agents: list[str] = Field(
        default_factory=list,
        description="List of known A2A agent endpoints",
    )
    a2a_shared_secret: str = Field(default="", description="Shared secret for A2A message signing")

    # ── Production: Security ──
    digital_cto_api_keys: str = Field(
        default="",
        description="Comma-separated API keys for client authentication (production)",
    )
    require_auth: bool = Field(
        default=False,
        description="Require API key authentication for all endpoints",
    )
    rate_limit_enabled: bool = Field(
        default=True,
        description="Enable rate limiting for API endpoints",
    )
    rate_limit_per_minute: int = Field(
        default=60,
        description="Requests per minute per IP for rate limiting",
    )

    # ── Production: Retry Configuration ──
    retry_max_attempts: int = Field(default=3, description="Maximum retry attempts for transient failures")
    retry_base_delay: float = Field(default=1.0, description="Base delay for exponential backoff (seconds)")

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

    @property
    def has_projects_v2(self) -> bool:
        return bool(self.github_org and self.github_project_number > 0)


# Singleton instance — import this everywhere
settings = Settings()
