"""Tests for the DevOps & CI/CD agent."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.agents.devops.models import (
    AlertCategory,
    AlertSeverity,
    DevOpsAlert,
    DevOpsQueryType,
    DevOpsReport,
)
from src.agents.devops.agent import (
    DevOpsState,
    fetch_pipeline_data,
    analyze_failures,
    generate_devops_report,
)


class TestDevOpsModels:
    """Test DevOps data models."""

    def test_alert_categories(self):
        assert AlertCategory.BUILD_FAILURE == "build_failure"
        assert AlertCategory.TEST_FAILURE == "test_failure"
        assert AlertCategory.SECURITY_VULNERABILITY == "security_vulnerability"

    def test_alert_creation(self):
        alert = DevOpsAlert(
            alert_id="alert-001",
            category=AlertCategory.BUILD_FAILURE,
            severity=AlertSeverity.CRITICAL,
            title="Docker build failed",
            description="Missing dependency in requirements.txt",
            repository="afcen/platform",
        )
        data = alert.model_dump()
        assert data["category"] == "build_failure"
        assert data["severity"] == "critical"

    def test_report_creation(self):
        report = DevOpsReport(
            report_id="devops-20260224",
            summary="All pipelines healthy",
            total_runs=10,
            successful_runs=10,
            failed_runs=0,
            pipeline_health="healthy",
            repositories=["afcen/platform"],
        )
        assert report.pipeline_health == "healthy"
        assert len(report.alerts) == 0

    def test_query_types(self):
        assert DevOpsQueryType.PIPELINE_STATUS == "pipeline_status"
        assert DevOpsQueryType.FAILURE_ANALYSIS == "failure_analysis"
        assert DevOpsQueryType.DEVOPS_REPORT == "devops_report"


class TestDevOpsPipeline:
    """Test individual pipeline nodes."""

    @pytest.mark.asyncio
    async def test_fetch_pipeline_data(self):
        """fetch_pipeline_data should collect workflow runs."""
        state: DevOpsState = {
            "query_type": "pipeline_status",
            "repositories": ["afcen/platform"],
            "workflow_runs": [],
            "failed_runs": [],
            "failure_details": [],
            "llm_output": "",
            "report": None,
            "error": None,
        }

        mock_runs = [
            {"id": 1, "conclusion": "success", "name": "CI", "status": "completed"},
            {"id": 2, "conclusion": "failure", "name": "CI", "status": "completed"},
        ]

        with patch(
            "src.integrations.github_graphql.GitHubGraphQLClient.get_workflow_runs",
            new_callable=AsyncMock,
            return_value=mock_runs,
        ):
            result = await fetch_pipeline_data(state)
            assert len(result["workflow_runs"]) == 2
            assert len(result["failed_runs"]) == 1

    @pytest.mark.asyncio
    async def test_analyze_failures_gets_job_details(self):
        """analyze_failures should fetch job details for failed runs."""
        state: DevOpsState = {
            "query_type": "failure_analysis",
            "repositories": ["afcen/platform"],
            "workflow_runs": [],
            "failed_runs": [
                {
                    "id": 124,
                    "repository": "afcen/platform",
                    "name": "CI",
                    "branch": "feat/broken",
                    "commit_sha": "abc123",
                    "html_url": "https://example.com",
                }
            ],
            "failure_details": [],
            "llm_output": "",
            "report": None,
            "error": None,
        }

        mock_jobs = [
            {
                "id": 1001,
                "name": "test",
                "status": "completed",
                "conclusion": "failure",
                "started_at": "",
                "completed_at": "",
                "steps": [
                    {"name": "Run tests", "status": "completed", "conclusion": "failure", "number": 3}
                ],
            }
        ]

        with patch(
            "src.integrations.github_graphql.GitHubGraphQLClient.get_workflow_run_jobs",
            new_callable=AsyncMock,
            return_value=mock_jobs,
        ):
            result = await analyze_failures(state)
            assert len(result["failure_details"]) == 1
            assert len(result["failure_details"][0]["failed_jobs"]) == 1

    @pytest.mark.asyncio
    async def test_generate_report_healthy_when_no_failures(self):
        """Report should show 'healthy' when all runs succeed."""
        state: DevOpsState = {
            "query_type": "devops_report",
            "repositories": ["afcen/platform"],
            "workflow_runs": [
                {"id": 1, "conclusion": "success"},
                {"id": 2, "conclusion": "success"},
            ],
            "failed_runs": [],
            "failure_details": [],
            "llm_output": "",
            "report": None,
            "error": None,
        }

        result = await generate_devops_report(state)
        assert result["report"]["pipeline_health"] == "healthy"
        assert result["report"]["failed_runs"] == 0


class TestDevOpsPrompts:
    """Test DevOps prompt formatting."""

    def test_analysis_prompt_fills_fields(self):
        from src.agents.devops.prompts import DEVOPS_ANALYSIS_PROMPT

        formatted = DEVOPS_ANALYSIS_PROMPT.format(
            repositories="afcen/platform",
            workflow_runs_summary="Total: 10, Success: 8, Failed: 2",
            failure_details="CI failed on main branch",
        )

        assert "afcen/platform" in formatted
        assert "Total: 10" in formatted
