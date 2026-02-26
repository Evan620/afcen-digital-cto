"""HTTP client for communicating with the Digital CTO Docker backend.

All intelligence lives in the backend (FastAPI + LangGraph + agents).
The TUI is a thin client that delegates everything here.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from src.tui.onboard.config import load_config

logger = logging.getLogger(__name__)

# Timeouts: 10s connect (backend should be local), 120s read (agent ops are slow)
_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0)


class BackendClient:
    """Async HTTP client for the Digital CTO backend."""

    def __init__(self, base_url: str | None = None):
        config = load_config()
        self.base_url = (base_url or config.backend_url).rstrip("/")

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self.base_url, timeout=_TIMEOUT)

    # ── Chat ──

    async def chat(
        self,
        message: str,
        agent_hint: str | None = None,
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        """Send a chat message to the backend and get agent response.

        Returns:
            {"response": str, "agent": str, "event_type": str|None}
        """
        async with self._client() as client:
            resp = await client.post(
                "/api/chat",
                json={
                    "message": message,
                    "agent_hint": agent_hint,
                    "conversation_id": conversation_id,
                },
            )
            resp.raise_for_status()
            return resp.json()

    # ── Health ──

    async def health(self) -> dict[str, Any]:
        """Quick health check (GET /health)."""
        async with self._client() as client:
            resp = await client.get("/health")
            resp.raise_for_status()
            return resp.json()

    async def health_deep(self) -> dict[str, Any]:
        """Deep health check including external services (GET /health/deep)."""
        async with self._client() as client:
            resp = await client.get("/health/deep")
            resp.raise_for_status()
            return resp.json()

    # ── Sprint ──

    async def sprint_status(self, repository: str | None = None) -> dict[str, Any]:
        """Get sprint status (GET /sprint/status)."""
        params = {}
        if repository:
            params["repository"] = repository
        async with self._client() as client:
            resp = await client.get("/sprint/status", params=params)
            resp.raise_for_status()
            return resp.json()

    async def sprint_report(self, repository: str | None = None) -> dict[str, Any]:
        """Get comprehensive sprint report (GET /sprint/report)."""
        params = {}
        if repository:
            params["repository"] = repository
        async with self._client() as client:
            resp = await client.get("/sprint/report", params=params)
            resp.raise_for_status()
            return resp.json()

    async def sprint_bayes(self, repository: str | None = None) -> dict[str, Any]:
        """Get Bayes deliverable tracking (GET /sprint/bayes)."""
        params = {}
        if repository:
            params["repository"] = repository
        async with self._client() as client:
            resp = await client.get("/sprint/bayes", params=params)
            resp.raise_for_status()
            return resp.json()

    async def sprint_retrospective(self, repository: str | None = None) -> dict[str, Any]:
        """Get sprint retrospective (GET /sprint/retrospective)."""
        params = {}
        if repository:
            params["repository"] = repository
        async with self._client() as client:
            resp = await client.get("/sprint/retrospective", params=params)
            resp.raise_for_status()
            return resp.json()

    # ── Architecture ──

    async def architecture_query(
        self,
        query: str,
        query_type: str = "technology_evaluation",
        repository: str | None = None,
    ) -> dict[str, Any]:
        """Submit architecture evaluation (POST /architecture/query)."""
        payload: dict[str, Any] = {"query": query, "query_type": query_type}
        if repository:
            payload["repository"] = repository
        async with self._client() as client:
            resp = await client.post("/architecture/query", json=payload)
            resp.raise_for_status()
            return resp.json()

    async def architecture_decisions(self, limit: int = 10) -> dict[str, Any]:
        """List recent architecture decisions (GET /architecture/decisions)."""
        async with self._client() as client:
            resp = await client.get("/architecture/decisions", params={"limit": limit})
            resp.raise_for_status()
            return resp.json()

    # ── DevOps ──

    async def devops_status(self, repository: str | None = None) -> dict[str, Any]:
        """Get DevOps pipeline status (GET /devops/status)."""
        params = {}
        if repository:
            params["repository"] = repository
        async with self._client() as client:
            resp = await client.get("/devops/status", params=params)
            resp.raise_for_status()
            return resp.json()

    async def devops_report(self, repository: str | None = None) -> dict[str, Any]:
        """Get full DevOps health report (GET /devops/report)."""
        params = {}
        if repository:
            params["repository"] = repository
        async with self._client() as client:
            resp = await client.get("/devops/report", params=params)
            resp.raise_for_status()
            return resp.json()

    # ── Market Scanner ──

    async def market_status(self) -> dict[str, Any]:
        """Get market scanner status (GET /market/status)."""
        async with self._client() as client:
            resp = await client.get("/market/status")
            resp.raise_for_status()
            return resp.json()

    async def market_intel(self, hours: int = 24, limit: int = 50) -> dict[str, Any]:
        """Get recent market intelligence (GET /market/intel)."""
        async with self._client() as client:
            resp = await client.get("/market/intel", params={"hours": hours, "limit": limit})
            resp.raise_for_status()
            return resp.json()

    async def market_scan(self, hours_back: int = 24) -> dict[str, Any]:
        """Trigger market data collection (POST /market/scan)."""
        async with self._client() as client:
            resp = await client.post("/market/scan", params={"hours_back": hours_back})
            resp.raise_for_status()
            return resp.json()

    async def market_brief(self) -> dict[str, Any]:
        """Generate morning brief on demand (POST /market/brief)."""
        async with self._client() as client:
            resp = await client.post("/market/brief")
            resp.raise_for_status()
            return resp.json()

    # ── Meeting Intelligence ──

    async def meeting_status(self) -> dict[str, Any]:
        """Get meeting intelligence status (GET /meeting/status)."""
        async with self._client() as client:
            resp = await client.get("/meeting/status")
            resp.raise_for_status()
            return resp.json()

    async def meeting_analyze(
        self,
        transcript: str,
        title: str = "Unknown Meeting",
        participants: list[str] | None = None,
    ) -> dict[str, Any]:
        """Analyze a meeting transcript (POST /meeting/analyze)."""
        async with self._client() as client:
            resp = await client.post(
                "/meeting/analyze",
                json={
                    "transcript": transcript,
                    "meeting_title": title,
                    "participants": participants or [],
                },
            )
            resp.raise_for_status()
            return resp.json()

    # ── Coding Agent ──

    async def coding_submit(
        self,
        description: str,
        repository: str,
        complexity: str = "moderate",
        requires_testing: bool = True,
    ) -> dict[str, Any]:
        """Submit a coding task (POST /coding/task)."""
        async with self._client() as client:
            resp = await client.post(
                "/coding/task",
                json={
                    "description": description,
                    "repository": repository,
                    "complexity": complexity,
                    "requires_testing": requires_testing,
                },
            )
            resp.raise_for_status()
            return resp.json()

    async def coding_status(self, task_id: str) -> dict[str, Any]:
        """Get coding task status (GET /coding/status/{task_id})."""
        async with self._client() as client:
            resp = await client.get(f"/coding/status/{task_id}")
            resp.raise_for_status()
            return resp.json()

    async def coding_history(self, limit: int = 20) -> dict[str, Any]:
        """Get coding task history (GET /coding/history)."""
        async with self._client() as client:
            resp = await client.get("/coding/history", params={"limit": limit})
            resp.raise_for_status()
            return resp.json()

    # ── Reachability ──

    async def is_reachable(self) -> bool:
        """Check if the backend is reachable at all."""
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(connect=3.0, read=5.0, write=3.0, pool=3.0),
            ) as client:
                resp = await client.get("/health")
                return resp.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException, OSError):
            return False


def _run_async(coro):
    """Run an async coroutine from synchronous TUI code."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # We're inside an existing event loop (shouldn't happen in TUI, but handle it)
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)


# Module singleton
_client: BackendClient | None = None


def get_backend_client(base_url: str | None = None) -> BackendClient:
    """Get or create the module-level BackendClient singleton."""
    global _client
    if _client is None or base_url is not None:
        _client = BackendClient(base_url=base_url)
    return _client
