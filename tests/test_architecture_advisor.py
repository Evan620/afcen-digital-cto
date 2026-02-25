"""Tests for the Architecture Advisor agent."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from src.agents.architecture_advisor.models import (
    ArchitectureQueryType,
    ArchitectureRecommendation,
    OptionConsidered,
)
from src.agents.architecture_advisor.agent import (
    ArchitectureAdvisorState,
    gather_context,
    build_recommendation,
)


class TestArchitectureModels:
    """Test Architecture Advisor data models."""

    def test_query_type_values(self):
        """All query types should be valid enum values."""
        assert ArchitectureQueryType.TECHNOLOGY_EVALUATION == "technology_evaluation"
        assert ArchitectureQueryType.DESIGN_REVIEW == "design_review"
        assert ArchitectureQueryType.TECH_DEBT_ASSESSMENT == "tech_debt_assessment"

    def test_recommendation_creation(self):
        """An ArchitectureRecommendation should serialize cleanly."""
        rec = ArchitectureRecommendation(
            decision_id="arch-20260224-120000",
            title="Use Redis for caching",
            context="Need to cache API responses",
            query_type=ArchitectureQueryType.TECHNOLOGY_EVALUATION,
            options_considered=[
                OptionConsidered(
                    name="Redis",
                    pros=["Fast", "Well-supported"],
                    cons=["Requires server"],
                    estimated_cost="$50/month",
                ),
                OptionConsidered(
                    name="In-memory",
                    pros=["No extra infra"],
                    cons=["Not shared across instances"],
                    estimated_cost="$0",
                ),
            ],
            recommendation="Use Redis for caching",
            rationale="Redis provides shared caching across instances",
            risks=["Redis downtime"],
        )

        data = rec.model_dump()
        assert data["title"] == "Use Redis for caching"
        assert len(data["options_considered"]) == 2
        assert data["options_considered"][0]["name"] == "Redis"

    def test_option_considered_model(self):
        """OptionConsidered should have pros, cons, and optional cost."""
        opt = OptionConsidered(
            name="PostgreSQL",
            pros=["ACID compliant", "Rich ecosystem"],
            cons=["Scaling complexity"],
        )
        assert opt.estimated_cost is None
        assert len(opt.pros) == 2


class TestArchitecturePipeline:
    """Test individual pipeline nodes."""

    @pytest.mark.asyncio
    async def test_gather_context_without_repo(self):
        """gather_context should work without a repository specified."""
        state: ArchitectureAdvisorState = {
            "query_type": "technology_evaluation",
            "query": "Should we use Redis or Memcached?",
            "repository": None,
            "context": {},
            "repo_context": "",
            "prior_decisions": [],
            "llm_output": "",
            "recommendation": None,
            "error": None,
        }

        result = await gather_context(state)
        assert "repo_context" in result
        assert result["repo_context"] == "No repository specified."

    @pytest.mark.asyncio
    async def test_build_recommendation_from_valid_json(self):
        """build_recommendation should parse valid LLM JSON output."""
        llm_json = """{
            "title": "Use PostgreSQL for persistence",
            "context": "Need a relational database",
            "options_considered": [
                {"name": "PostgreSQL", "pros": ["ACID"], "cons": ["Complex"]},
                {"name": "MongoDB", "pros": ["Flexible"], "cons": ["No ACID"]}
            ],
            "recommendation": "Use PostgreSQL",
            "rationale": "Best fit for structured data",
            "cost_implications": "$100/month",
            "timeline": "1 week",
            "risks": ["Migration complexity"],
            "migration_plan": "Set up Docker Compose service"
        }"""

        state: ArchitectureAdvisorState = {
            "query_type": "technology_evaluation",
            "query": "Database choice",
            "repository": None,
            "context": {},
            "repo_context": "",
            "prior_decisions": [],
            "llm_output": f"Here's my analysis:\n\n{llm_json}\n\nHope this helps!",
            "recommendation": None,
            "error": None,
        }

        result = await build_recommendation(state)
        assert result.get("recommendation") is not None
        rec = result["recommendation"]
        assert rec["title"] == "Use PostgreSQL for persistence"
        assert len(rec["options_considered"]) == 2
        assert rec["risks"] == ["Migration complexity"]

    @pytest.mark.asyncio
    async def test_build_recommendation_handles_invalid_json(self):
        """build_recommendation should set error on invalid JSON."""
        state: ArchitectureAdvisorState = {
            "query_type": "technology_evaluation",
            "query": "test",
            "repository": None,
            "context": {},
            "repo_context": "",
            "prior_decisions": [],
            "llm_output": "This is not JSON at all",
            "recommendation": None,
            "error": None,
        }

        result = await build_recommendation(state)
        assert result.get("error") is not None

    @pytest.mark.asyncio
    async def test_build_recommendation_skips_on_error(self):
        """build_recommendation should skip if state has error."""
        state: ArchitectureAdvisorState = {
            "query_type": "technology_evaluation",
            "query": "test",
            "repository": None,
            "context": {},
            "repo_context": "",
            "prior_decisions": [],
            "llm_output": "",
            "recommendation": None,
            "error": "Previous step failed",
        }

        result = await build_recommendation(state)
        assert result == {}


class TestArchitecturePrompts:
    """Test Architecture Advisor prompt formatting."""

    def test_query_prompt_fills_fields(self):
        """The architecture query prompt should accept all fields."""
        from src.agents.architecture_advisor.prompts import ARCHITECTURE_QUERY_PROMPT

        formatted = ARCHITECTURE_QUERY_PROMPT.format(
            query_type="technology_evaluation",
            query="Should we use Redis?",
            repo_context="Repository: afcen/platform",
            prior_decisions="No prior decisions.",
            additional_context="Budget is limited.",
        )

        assert "technology_evaluation" in formatted
        assert "Should we use Redis?" in formatted
        assert "Budget is limited." in formatted
