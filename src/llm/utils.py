"""Shared LLM utilities for all agents.

Provides:
- get_default_llm(): LLM cascade (Claude > GLM-5 > Azure OpenAI)
- extract_json_from_llm_output(): Parse JSON from LLM responses
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_openai import AzureChatOpenAI, ChatOpenAI

from src.config import settings

logger = logging.getLogger(__name__)


def get_default_llm(temperature: float = 0.7):
    """Get default LLM respecting the preferred provider from onboarding.

    If PREFERRED_LLM_PROVIDER is set, use that provider if its key is available.
    Otherwise, fall back to auto-detection: Claude > GLM-5 > Azure OpenAI.

    Args:
        temperature: Sampling temperature for generation

    Returns:
        LangChain LLM instance
    """
    preferred = settings.preferred_llm_provider.lower() if settings.preferred_llm_provider else ""

    # If user set a preferred provider during onboarding, try that first
    if preferred == "zai" and settings.has_zai:
        logger.debug("Using preferred LLM: z.ai (GLM-5)")
        return ChatOpenAI(
            model=settings.zai_model,
            api_key=settings.zai_api_key,
            base_url=settings.zai_base_url,
            temperature=temperature,
            max_tokens=8192,
        )

    if preferred == "anthropic" and settings.has_anthropic:
        logger.debug("Using preferred LLM: Anthropic (Claude)")
        return ChatAnthropic(
            model="claude-sonnet-4-20250514",
            api_key=settings.anthropic_api_key,
            temperature=temperature,
            max_tokens=8192,
        )

    if preferred == "azure_openai" and settings.has_azure_openai:
        logger.debug("Using preferred LLM: Azure OpenAI")
        return AzureChatOpenAI(
            azure_deployment=settings.azure_openai_deployment,
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
            temperature=temperature,
            max_tokens=8192,
        )

    # Auto-detect fallback: Claude > GLM-5 > Azure OpenAI
    if settings.has_anthropic:
        logger.debug("Auto-detected LLM: Anthropic (Claude)")
        return ChatAnthropic(
            model="claude-sonnet-4-20250514",
            api_key=settings.anthropic_api_key,
            temperature=temperature,
            max_tokens=8192,
        )

    elif settings.has_zai:
        logger.debug("Auto-detected LLM: z.ai (GLM-5)")
        return ChatOpenAI(
            model=settings.zai_model,
            api_key=settings.zai_api_key,
            base_url=settings.zai_base_url,
            temperature=temperature,
            max_tokens=8192,
        )

    elif settings.has_azure_openai:
        logger.debug("Auto-detected LLM: Azure OpenAI")
        return AzureChatOpenAI(
            azure_deployment=settings.azure_openai_deployment,
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
            temperature=temperature,
            max_tokens=8192,
        )

    else:
        raise ValueError(
            "No LLM configured. Set ANTHROPIC_API_KEY, ZAI_API_KEY, or AZURE_OPENAI_API_KEY + AZURE_OPENAI_ENDPOINT"
        )


def extract_json_from_llm_output(text: str) -> dict[str, Any] | None:
    """Extract JSON from LLM output, handling markdown code blocks and various formats.

    Args:
        text: Raw LLM response text

    Returns:
        Parsed JSON dict, or None if parsing fails
    """
    if not text:
        return None

    text = text.strip()

    # Try direct JSON parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code blocks
    # Pattern 1: ```json ... ```
    json_pattern = r"```json\s*(.*?)\s*```"
    matches = re.findall(json_pattern, text, re.DOTALL)
    if matches:
        try:
            return json.loads(matches[0].strip())
        except json.JSONDecodeError:
            pass

    # Pattern 2: ``` ... ```
    code_pattern = r"```\s*(.*?)\s*```"
    matches = re.findall(code_pattern, text, re.DOTALL)
    if matches:
        try:
            return json.loads(matches[0].strip())
        except json.JSONDecodeError:
            pass

    # Pattern 3: Find first { ... } with brace matching
    try:
        start = text.find("{")
        if start != -1:
            # Count braces to find matching end
            depth = 0
            for i, char in enumerate(text[start:], start):
                if char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        json_str = text[start:i + 1]
                        return json.loads(json_str)
    except (json.JSONDecodeError, ValueError):
        pass

    # Pattern 4: Find first [ ... ] for array responses
    try:
        start = text.find("[")
        if start != -1:
            depth = 0
            for i, char in enumerate(text[start:], start):
                if char == "[":
                    depth += 1
                elif char == "]":
                    depth -= 1
                    if depth == 0:
                        json_str = text[start:i + 1]
                        return json.loads(json_str)
    except (json.JSONDecodeError, ValueError):
        pass

    logger.warning("Failed to extract JSON from LLM output (first 200 chars): %s", text[:200])
    return None


def format_json_schema(schema: dict[str, Any]) -> str:
    """Format a JSON schema for inclusion in an LLM prompt.

    Args:
        schema: Pydantic model schema or dict

    Returns:
        Formatted schema string
    """
    return json.dumps(schema, indent=2)
