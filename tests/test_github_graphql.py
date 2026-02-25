"""Tests for the GitHub GraphQL client."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from src.integrations.github_graphql import GitHubGraphQLClient


class TestGraphQLExecution:
    """Test raw GraphQL query execution."""

    @pytest.mark.asyncio
    async def test_execute_returns_data_on_success(self):
        """A successful GraphQL response should return the data portion."""
        client = GitHubGraphQLClient(token="test-token")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "data": {"organization": {"projectV2": {"title": "Test Project"}}}
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await client.execute("query { test }")
            assert result is not None
            assert "organization" in result

    @pytest.mark.asyncio
    async def test_execute_returns_none_on_graphql_error(self):
        """GraphQL errors in the response should return None."""
        client = GitHubGraphQLClient(token="test-token")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "errors": [{"message": "Not found"}],
            "data": None,
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await client.execute("query { test }")
            assert result is None


class TestProjectV2:
    """Test Projects V2 methods."""

    @pytest.mark.asyncio
    async def test_get_project_v2_returns_none_when_missing(self):
        """When org has no project, get_project_v2 returns None."""
        client = GitHubGraphQLClient(token="test-token")

        with patch.object(client, "execute", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {"organization": {"projectV2": None}}
            result = await client.get_project_v2("afcen", 1)
            assert result is None

    @pytest.mark.asyncio
    async def test_get_project_v2_returns_project(self):
        """A valid project should be returned with fields."""
        client = GitHubGraphQLClient(token="test-token")

        mock_data = {
            "organization": {
                "projectV2": {
                    "id": "PVT_123",
                    "title": "Sprint Board",
                    "shortDescription": "AfCEN sprints",
                    "url": "https://github.com/orgs/afcen/projects/1",
                    "fields": {"nodes": []},
                }
            }
        }

        with patch.object(client, "execute", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_data
            result = await client.get_project_v2("afcen", 1)
            assert result is not None
            assert result["title"] == "Sprint Board"

    @pytest.mark.asyncio
    async def test_get_current_sprint_iteration(self):
        """Should extract the current iteration from project fields."""
        client = GitHubGraphQLClient(token="test-token")

        mock_project = {
            "id": "PVT_123",
            "title": "Sprint Board",
            "fields": {
                "nodes": [
                    {
                        "id": "FIELD_1",
                        "name": "Sprint",
                        "configuration": {
                            "iterations": [
                                {
                                    "id": "ITER_1",
                                    "title": "Sprint 5",
                                    "startDate": "2026-02-17",
                                    "duration": 14,
                                }
                            ]
                        },
                    }
                ]
            },
        }

        with patch.object(client, "get_project_v2", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_project
            result = await client.get_current_sprint_iteration("afcen", 1)
            assert result is not None
            assert result["title"] == "Sprint 5"
            assert result["duration_days"] == 14


class TestWorkflowRuns:
    """Test GitHub Actions workflow run methods."""

    @pytest.mark.asyncio
    async def test_get_workflow_runs(self):
        """Should parse workflow runs from REST API response."""
        client = GitHubGraphQLClient(token="test-token")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "workflow_runs": [
                {
                    "id": 123,
                    "name": "CI",
                    "status": "completed",
                    "conclusion": "success",
                    "workflow_id": 1,
                    "head_branch": "main",
                    "head_sha": "abc123",
                    "event": "push",
                    "created_at": "2026-02-20T10:00:00Z",
                    "updated_at": "2026-02-20T10:05:00Z",
                    "html_url": "https://github.com/afcen/platform/actions/runs/123",
                    "run_attempt": 1,
                },
                {
                    "id": 124,
                    "name": "CI",
                    "status": "completed",
                    "conclusion": "failure",
                    "workflow_id": 1,
                    "head_branch": "feat/broken",
                    "head_sha": "def456",
                    "event": "push",
                    "created_at": "2026-02-20T11:00:00Z",
                    "updated_at": "2026-02-20T11:05:00Z",
                    "html_url": "https://github.com/afcen/platform/actions/runs/124",
                    "run_attempt": 1,
                },
            ]
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            runs = await client.get_workflow_runs("afcen/platform", limit=10)
            assert len(runs) == 2
            assert runs[0]["conclusion"] == "success"
            assert runs[1]["conclusion"] == "failure"

    @pytest.mark.asyncio
    async def test_get_workflow_run_jobs(self):
        """Should parse job details for a workflow run."""
        client = GitHubGraphQLClient(token="test-token")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "jobs": [
                {
                    "id": 1001,
                    "name": "test",
                    "status": "completed",
                    "conclusion": "failure",
                    "started_at": "2026-02-20T11:00:00Z",
                    "completed_at": "2026-02-20T11:03:00Z",
                    "steps": [
                        {
                            "name": "Run tests",
                            "status": "completed",
                            "conclusion": "failure",
                            "number": 3,
                        }
                    ],
                }
            ]
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            jobs = await client.get_workflow_run_jobs("afcen/platform", 124)
            assert len(jobs) == 1
            assert jobs[0]["conclusion"] == "failure"
            assert jobs[0]["steps"][0]["name"] == "Run tests"
