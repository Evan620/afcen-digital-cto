"""Redis-based working memory for the Digital CTO.

Stores active agent state, current conversation context, and short-lived data
that needs fast access. Data here is ephemeral — important decisions get
persisted to PostgreSQL.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import redis.asyncio as aioredis

from src.config import settings

logger = logging.getLogger(__name__)


class RedisStore:
    """Async Redis client for agent working memory."""

    def __init__(self, url: str | None = None) -> None:
        self._url = url or settings.redis_url
        self._client: aioredis.Redis | None = None

    async def connect(self) -> None:
        """Establish connection to Redis."""
        self._client = aioredis.from_url(
            self._url,
            decode_responses=True,
            max_connections=20,
        )
        # Verify connection
        await self._client.ping()
        logger.info("Redis working memory connected at %s", self._url)

    async def disconnect(self) -> None:
        """Close the Redis connection."""
        if self._client:
            await self._client.aclose()
            logger.info("Redis connection closed")

    @property
    def client(self) -> aioredis.Redis:
        if self._client is None:
            raise RuntimeError("Redis not connected. Call connect() first.")
        return self._client

    # ── State Operations ──

    async def set_state(self, key: str, value: dict[str, Any], ttl: int = 3600) -> None:
        """Store agent state with automatic expiry (default 1 hour)."""
        await self.client.setex(key, ttl, json.dumps(value))

    async def get_state(self, key: str) -> dict[str, Any] | None:
        """Retrieve agent state, or None if expired/missing."""
        raw = await self.client.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    async def delete_state(self, key: str) -> None:
        """Remove a state key."""
        await self.client.delete(key)

    # ── PR Review Queue ──

    async def enqueue_pr(self, pr_data: dict[str, Any]) -> None:
        """Add a PR event to the review queue."""
        await self.client.rpush("pr_review_queue", json.dumps(pr_data))
        logger.info("PR enqueued for review: %s", pr_data.get("number", "?"))

    async def dequeue_pr(self) -> dict[str, Any] | None:
        """Pop the next PR from the review queue."""
        raw = await self.client.lpop("pr_review_queue")
        if raw is None:
            return None
        return json.loads(raw)

    async def queue_length(self) -> int:
        """Get the number of PRs waiting for review."""
        return await self.client.llen("pr_review_queue")

    # ── Health ──

    async def health_check(self) -> bool:
        """Return True if Redis is reachable."""
        try:
            return await self.client.ping()
        except Exception:
            return False
