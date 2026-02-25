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

    # ── Agent-specific endpoints ──

    async def sprint_status(self) -> dict[str, Any]:
        """Get sprint status (GET /sprint/status)."""
        async with self._client() as client:
            resp = await client.get("/sprint/status")
            resp.raise_for_status()
            return resp.json()

    async def devops_status(self) -> dict[str, Any]:
        """Get DevOps pipeline status (GET /devops/status)."""
        async with self._client() as client:
            resp = await client.get("/devops/status")
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
