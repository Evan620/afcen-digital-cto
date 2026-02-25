"""GitHub GraphQL client for Projects V2 and Actions workflow data.

Uses httpx for GraphQL POST to api.github.com/graphql.
Dual-mode: returns None when no project exists, enabling graceful fallback.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from src.config import settings

logger = logging.getLogger(__name__)

GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"
GITHUB_REST_URL = "https://api.github.com"


class GitHubGraphQLClient:
    """Client for GitHub GraphQL API (Projects V2) and REST (Actions)."""

    def __init__(self, token: str | None = None) -> None:
        self._token = token or settings.github_token
        self._headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
        }

    async def execute(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """Execute a raw GraphQL query.

        Returns the 'data' portion of the response, or None on error.
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                GITHUB_GRAPHQL_URL,
                headers=self._headers,
                json={"query": query, "variables": variables or {}},
            )
            resp.raise_for_status()
            body = resp.json()

            if "errors" in body:
                logger.error("GraphQL errors: %s", body["errors"])
                return None

            return body.get("data")

    async def get_project_v2(self, org: str, project_number: int) -> dict[str, Any] | None:
        """Fetch a Projects V2 board by org and number.

        Returns project metadata or None if not found.
        """
        query = """
        query($org: String!, $number: Int!) {
          organization(login: $org) {
            projectV2(number: $number) {
              id
              title
              shortDescription
              url
              fields(first: 20) {
                nodes {
                  ... on ProjectV2Field {
                    id
                    name
                    dataType
                  }
                  ... on ProjectV2IterationField {
                    id
                    name
                    configuration {
                      iterations {
                        id
                        title
                        startDate
                        duration
                      }
                    }
                  }
                  ... on ProjectV2SingleSelectField {
                    id
                    name
                    options {
                      id
                      name
                    }
                  }
                }
              }
            }
          }
        }
        """
        data = await self.execute(query, {"org": org, "number": project_number})
        if not data:
            return None

        project = data.get("organization", {}).get("projectV2")
        if not project:
            logger.warning("Project V2 #%d not found in org %s", project_number, org)
            return None

        return project

    async def get_current_sprint_iteration(
        self, org: str, project_number: int
    ) -> dict[str, Any] | None:
        """Get the currently active iteration (sprint) from a Projects V2 board.

        Returns iteration dict with id, title, startDate, duration, or None.
        """
        project = await self.get_project_v2(org, project_number)
        if not project:
            return None

        # Find the iteration field
        for field in project.get("fields", {}).get("nodes", []):
            config = field.get("configuration")
            if not config:
                continue

            iterations = config.get("iterations", [])
            if iterations:
                # The first iteration in the list is typically the current one
                current = iterations[0]
                logger.info(
                    "Current sprint iteration: %s (start=%s, duration=%d days)",
                    current["title"],
                    current["startDate"],
                    current["duration"],
                )
                return {
                    "id": current["id"],
                    "title": current["title"],
                    "start_date": current["startDate"],
                    "duration_days": current["duration"],
                    "field_id": field["id"],
                }

        logger.warning("No iteration field found in project %d", project_number)
        return None

    async def get_project_items(
        self,
        org: str,
        project_number: int,
        iteration_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Fetch items from a Projects V2 board, optionally filtered by iteration.

        Returns list of item dicts with title, status, assignees, etc.
        """
        query = """
        query($org: String!, $number: Int!, $first: Int!) {
          organization(login: $org) {
            projectV2(number: $number) {
              items(first: $first) {
                nodes {
                  id
                  content {
                    ... on Issue {
                      number
                      title
                      state
                      labels(first: 10) {
                        nodes { name }
                      }
                      assignees(first: 5) {
                        nodes { login }
                      }
                      milestone {
                        title
                        dueOn
                      }
                    }
                    ... on PullRequest {
                      number
                      title
                      state
                    }
                  }
                  fieldValues(first: 10) {
                    nodes {
                      ... on ProjectV2ItemFieldIterationValue {
                        iterationId
                        title
                        startDate
                        duration
                      }
                      ... on ProjectV2ItemFieldSingleSelectValue {
                        name
                        field { ... on ProjectV2SingleSelectField { name } }
                      }
                      ... on ProjectV2ItemFieldNumberValue {
                        number
                        field { ... on ProjectV2Field { name } }
                      }
                    }
                  }
                }
              }
            }
          }
        }
        """
        data = await self.execute(query, {"org": org, "number": project_number, "first": limit})
        if not data:
            return []

        items_data = (
            data.get("organization", {})
            .get("projectV2", {})
            .get("items", {})
            .get("nodes", [])
        )

        items = []
        for item in items_data:
            content = item.get("content") or {}
            field_values = item.get("fieldValues", {}).get("nodes", [])

            # Filter by iteration if specified
            if iteration_id:
                in_iteration = any(
                    fv.get("iterationId") == iteration_id for fv in field_values
                )
                if not in_iteration:
                    continue

            # Extract status and story points from field values
            status = None
            story_points = None
            for fv in field_values:
                field_info = fv.get("field", {})
                if field_info.get("name", "").lower() == "status":
                    status = fv.get("name")
                if field_info.get("name", "").lower() in ("story points", "points", "estimate"):
                    story_points = fv.get("number")

            items.append({
                "id": item["id"],
                "number": content.get("number"),
                "title": content.get("title", ""),
                "state": content.get("state", ""),
                "status": status,
                "story_points": story_points,
                "labels": [n["name"] for n in content.get("labels", {}).get("nodes", [])],
                "assignees": [n["login"] for n in content.get("assignees", {}).get("nodes", [])],
                "milestone": content.get("milestone"),
            })

        logger.info("Fetched %d project items from %s project #%d", len(items), org, project_number)
        return items

    # ── GitHub Actions (REST API) ──

    async def get_workflow_runs(
        self,
        repo: str,
        status: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Fetch recent GitHub Actions workflow runs.

        Args:
            repo: 'owner/repo' format
            status: Filter by status (completed, in_progress, queued, failure, success)
            limit: Max number of runs to return
        """
        url = f"{GITHUB_REST_URL}/repos/{repo}/actions/runs"
        params: dict[str, Any] = {"per_page": limit}
        if status:
            params["status"] = status

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers=self._headers, params=params)
            resp.raise_for_status()
            data = resp.json()

        runs = []
        for run in data.get("workflow_runs", [])[:limit]:
            runs.append({
                "id": run["id"],
                "name": run.get("name", ""),
                "status": run["status"],
                "conclusion": run.get("conclusion"),
                "workflow_id": run["workflow_id"],
                "branch": run.get("head_branch", ""),
                "commit_sha": run.get("head_sha", ""),
                "event": run.get("event", ""),
                "created_at": run.get("created_at", ""),
                "updated_at": run.get("updated_at", ""),
                "html_url": run.get("html_url", ""),
                "run_attempt": run.get("run_attempt", 1),
            })

        logger.info("Fetched %d workflow runs from %s", len(runs), repo)
        return runs

    async def get_workflow_run_jobs(
        self, repo: str, run_id: int
    ) -> list[dict[str, Any]]:
        """Fetch job details for a specific workflow run.

        Args:
            repo: 'owner/repo' format
            run_id: Workflow run ID
        """
        url = f"{GITHUB_REST_URL}/repos/{repo}/actions/runs/{run_id}/jobs"

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers=self._headers)
            resp.raise_for_status()
            data = resp.json()

        jobs = []
        for job in data.get("jobs", []):
            steps = [
                {
                    "name": s["name"],
                    "status": s["status"],
                    "conclusion": s.get("conclusion"),
                    "number": s["number"],
                }
                for s in job.get("steps", [])
            ]
            jobs.append({
                "id": job["id"],
                "name": job["name"],
                "status": job["status"],
                "conclusion": job.get("conclusion"),
                "started_at": job.get("started_at", ""),
                "completed_at": job.get("completed_at", ""),
                "steps": steps,
            })

        return jobs
