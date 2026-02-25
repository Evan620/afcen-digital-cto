"""Tests for Sprint Planner V2 improvements (Projects V2, LLM recommendations, retrospective)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from src.agents.sprint_planner.models import SprintQueryType
from src.agents.sprint_planner.agent import (
    SprintPlannerState,
    fetch_sprint_data,
    generate_recommendations,
    _static_recommendations,
    _default_state,
)


class TestSprintQueryTypes:
    """Test the new RETROSPECTIVE query type."""

    def test_retrospective_query_type(self):
        assert SprintQueryType.RETROSPECTIVE == "retrospective"
        assert SprintQueryType.RETROSPECTIVE.value == "retrospective"

    def test_all_query_types_exist(self):
        types = [t.value for t in SprintQueryType]
        assert "status" in types
        assert "report" in types
        assert "bayes_tracking" in types
        assert "retrospective" in types


class TestDefaultState:
    """Test the _default_state helper."""

    def test_default_state_has_all_keys(self):
        state = _default_state()
        assert "query_type" in state
        assert "use_projects_v2" in state
        assert "sprint_start_date" in state
        assert "sprint_end_date" in state
        assert state["use_projects_v2"] is False

    def test_default_state_with_overrides(self):
        state = _default_state(
            query_type="retrospective",
            repository="afcen/platform",
            include_recommendations=True,
        )
        assert state["query_type"] == "retrospective"
        assert state["repository"] == "afcen/platform"
        assert state["include_recommendations"] is True


class TestProjectsV2Fallback:
    """Test Projects V2 vs Issues fallback in fetch_sprint_data."""

    @pytest.mark.asyncio
    async def test_fetch_data_issues_only_when_no_projects_v2(self):
        """When has_projects_v2 is False, should only use Issues."""
        state = _default_state(repository="afcen/platform")

        mock_issues = [
            {"number": 1, "title": "Test", "state": "open", "labels": []},
        ]

        with patch("src.config.settings") as mock_settings:
            mock_settings.has_projects_v2 = False
            mock_settings.monitored_repos = ["afcen/platform"]

            with patch(
                "src.agents.sprint_planner.agent.GitHubClient"
            ) as mock_gh_cls:
                mock_gh = MagicMock()
                mock_gh.get_repository_issues.return_value = mock_issues
                mock_gh_cls.return_value = mock_gh

                result = await fetch_sprint_data(state)

                assert result["use_projects_v2"] is False
                assert len(result["issues"]) >= 1

    @pytest.mark.asyncio
    async def test_fetch_data_uses_projects_v2_when_available(self):
        """When has_projects_v2 is True, should fetch from Projects V2."""
        state = _default_state(repository="afcen/platform")

        mock_iteration = {
            "id": "ITER_1",
            "title": "Sprint 5",
            "start_date": "2026-02-17",
            "duration_days": 14,
        }
        mock_items = [
            {"id": "item-1", "number": 10, "title": "Task A", "state": "OPEN"},
        ]

        with patch("src.config.settings") as mock_settings:
            mock_settings.has_projects_v2 = True
            mock_settings.github_org = "afcen"
            mock_settings.github_project_number = 1
            mock_settings.monitored_repos = ["afcen/platform"]

            with patch(
                "src.agents.sprint_planner.agent.GitHubClient"
            ) as mock_gh_cls, patch(
                "src.integrations.github_graphql.GitHubGraphQLClient"
            ) as mock_gql_cls:
                mock_gh = MagicMock()
                mock_gh.get_repository_issues.return_value = []
                mock_gh_cls.return_value = mock_gh

                mock_gql = AsyncMock()
                mock_gql.get_current_sprint_iteration.return_value = mock_iteration
                mock_gql.get_project_items.return_value = mock_items
                mock_gql_cls.return_value = mock_gql

                result = await fetch_sprint_data(state)

                assert result["use_projects_v2"] is True
                assert result["sprint_start_date"] == "2026-02-17"
                assert len(result["project_items"]) == 1


class TestStaticRecommendations:
    """Test static fallback recommendations."""

    def test_critical_sprint(self):
        recs = _static_recommendations(
            {"health_status": "critical", "completion_rate": 20, "blocked_items": 5, "overdue_items": 3},
            {},
        )
        assert any("risk" in r.lower() or "20%" in r for r in recs)

    def test_healthy_sprint(self):
        recs = _static_recommendations(
            {"health_status": "healthy", "completion_rate": 80, "blocked_items": 0, "overdue_items": 0},
            {},
        )
        assert any("on track" in r.lower() for r in recs)

    def test_bayes_issues(self):
        recs = _static_recommendations(
            {},
            {"sow_summary": {"blocked_deliverables": 2, "overdue_deliverables": 1}},
        )
        assert any("bayes" in r.lower() for r in recs)


class TestLLMRecommendations:
    """Test LLM-powered recommendations."""

    @pytest.mark.asyncio
    async def test_falls_back_to_static_when_no_llm(self):
        """When no LLM is configured, should use static recommendations."""
        state = _default_state(
            include_recommendations=True,
            query_type="report",
        )
        state["metrics"] = {"health_status": "healthy", "completion_rate": 80, "blocked_items": 0, "overdue_items": 0}
        state["bayes_summary"] = {}
        state["issues"] = []

        with patch("src.agents.sprint_planner.agent._get_llm", return_value=None):
            result = await generate_recommendations(state)
            assert len(result["recommendations"]) >= 1


class TestSprintPrompts:
    """Test sprint planner prompt formatting."""

    def test_recommendations_prompt_fills_fields(self):
        from src.agents.sprint_planner.prompts import SPRINT_RECOMMENDATIONS_PROMPT

        formatted = SPRINT_RECOMMENDATIONS_PROMPT.format(
            metrics_summary="Completion: 75%",
            bayes_summary="2 deliverables blocked",
            issue_highlights="- [BLOCKED] #42: Auth middleware",
        )
        assert "75%" in formatted
        assert "BLOCKED" in formatted

    def test_retrospective_prompt_fills_fields(self):
        from src.agents.sprint_planner.prompts import SPRINT_RETROSPECTIVE_PROMPT

        formatted = SPRINT_RETROSPECTIVE_PROMPT.format(
            metrics_summary="Velocity: 2.5 pts/day",
            completed_count=8,
            in_progress_count=3,
            blocked_count=1,
            overdue_count=0,
            bayes_summary="5/10 completed",
        )
        assert "2.5" in formatted
        assert "8" in formatted
