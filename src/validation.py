"""Configuration validation for startup.

Validates that required API keys and configuration are present
before the application starts. Fails fast with clear error messages.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

from pydantic import ValidationError

from src.config import settings

logger = logging.getLogger(__name__)


# ── Validation Rules ──

VALIDATION_RULES = {
    "development": [
        # Required in all environments
        "has_anthropic_or_azure_or_zai",
        # Optional in dev
        # "github_token",
        # "redis_url",
        # "postgres_url",
        # "qdrant_url",
    ],
    "staging": [
        "has_anthropic_or_azure_or_zai",
        "github_token",
        "redis_url",
        "postgres_url",
        "qdrant_url",
    ],
    "production": [
        "has_anthropic_or_azure_or_zai",
        "github_token",
        "redis_url",
        "postgres_url",
        "qdrant_url",
        # Production-specific security
        "has_api_keys_configured",
    ],
}


# ── Validation Functions ──


def validate_config() -> list[str]:
    """Validate configuration for the current environment.

    Returns:
        List of error messages (empty if valid)
    """
    errors = []
    env = settings.environment

    # Get validation rules for this environment
    rules = VALIDATION_RULES.get(env, VALIDATION_RULES["development"])

    for rule in rules:
        error = _run_validation(rule)
        if error:
            errors.append(error)

    return errors


def _run_validation(rule: str) -> str | None:
    """Run a single validation rule.

    Returns:
        Error message if validation fails, None otherwise
    """
    if rule == "has_anthropic_or_azure_or_zai":
        if not (settings.has_anthropic or settings.has_azure_openai or settings.has_zai):
            return "At least one LLM API key must be configured (ANTHROPIC_API_KEY, AZURE_OPENAI_API_KEY, or ZAI_API_KEY)"

    elif rule == "github_token":
        if not settings.github_token:
            return "GITHUB_TOKEN is required"

    elif rule == "redis_url":
        if not settings.redis_url:
            return "REDIS_URL is required"

    elif rule == "postgres_url":
        if not settings.postgres_url:
            return "POSTGRES_URL is required"

    elif rule == "qdrant_url":
        if not settings.qdrant_url:
            return "QDRANT_URL is required"

    elif rule == "has_api_keys_configured":
        api_keys = settings.model_dump().get("digital_cto_api_keys", "")
        if not api_keys or not api_keys.strip():
            return "DIGITAL_CTO_API_KEYS must be configured in production (comma-separated list of API keys)"

    return None


def validate_and_exit() -> None:
    """Validate configuration on startup and exit if invalid.

    Call this in the lifespan function before connecting to services.
    """
    logger.info("Validating configuration for environment: %s", settings.environment)

    errors = validate_config()

    if errors:
        logger.error("=" * 60)
        logger.error("Configuration validation FAILED:")
        for i, error in enumerate(errors, 1):
            logger.error("  %d. %s", i, error)
        logger.error("=" * 60)
        logger.error("Please set the required environment variables and restart.")
        sys.exit(1)

    logger.info("Configuration validation PASSED")

    # Log what's configured
    if settings.has_anthropic:
        logger.info("  ✓ Anthropic Claude configured")
    if settings.has_azure_openai:
        logger.info("  ✓ Azure OpenAI configured")
    if settings.has_zai:
        logger.info("  ✓ z.ai (GLM) configured")
    if settings.github_token:
        logger.info("  ✓ GitHub token configured")
    if settings.openclaw_enabled:
        logger.info("  ✓ OpenClaw/JARVIS enabled")
    if settings.knowledge_graph_enabled:
        logger.info("  ✓ Knowledge Graph enabled")
