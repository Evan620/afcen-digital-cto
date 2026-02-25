"""Health check utilities for deep service verification.

Provides comprehensive health checks for all external dependencies.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

import httpx
from github import GithubException

from src.config import settings
from src.integrations.github_client import GitHubClient

logger = logging.getLogger(__name__)


class HealthCheckResult:
    """Result of a health check."""

    def __init__(
        self,
        service: str,
        healthy: bool,
        latency_ms: float | None = None,
        message: str = "",
        details: dict[str, Any] | None = None,
    ):
        self.service = service
        self.healthy = healthy
        self.latency_ms = latency_ms
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "service": self.service,
            "status": "ok" if self.healthy else "unhealthy",
            "latency_ms": self.latency_ms,
            "message": self.message,
            **self.details,
        }


async def check_llm_api() -> HealthCheckResult:
    """Check if LLM API is accessible and responding.

    Tries Anthropic, then Azure OpenAI, then z.ai.
    """
    start = time.time()

    # Try Anthropic (Claude)
    if settings.has_anthropic:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": settings.anthropic_api_key,
                        "anthropic-version": "2023-06-01",
                    },
                    json={
                        "model": "claude-3-haiku-20240307",
                        "max_tokens": 1,
                        "messages": [{"role": "user", "content": "Hi"}],
                    },
                )
                latency_ms = (time.time() - start) * 1000

                if response.status_code == 200:
                    return HealthCheckResult(
                        service="anthropic",
                        healthy=True,
                        latency_ms=latency_ms,
                        message="API responding",
                    )
                elif response.status_code == 401:
                    return HealthCheckResult(
                        service="anthropic",
                        healthy=False,
                        latency_ms=latency_ms,
                        message="Authentication failed",
                    )
                else:
                    return HealthCheckResult(
                        service="anthropic",
                        healthy=False,
                        latency_ms=latency_ms,
                        message=f"HTTP {response.status_code}",
                    )
        except Exception as e:
            return HealthCheckResult(
                service="anthropic",
                healthy=False,
                latency_ms=None,
                message=f"Connection failed: {str(e)[:100]}",
            )

    # Try Azure OpenAI
    if settings.has_azure_openai:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(
                    f"{settings.azure_openai_endpoint}/openai/deployments/{settings.azure_openai_deployment}/chat/completions?api-version={settings.azure_openai_api_version}",
                    headers={
                        "api-key": settings.azure_openai_api_key,
                    },
                    json={
                        "messages": [{"role": "user", "content": "Hi"}],
                        "max_tokens": 1,
                    },
                )
                latency_ms = (time.time() - start) * 1000

                if response.status_code == 200:
                    return HealthCheckResult(
                        service="azure_openai",
                        healthy=True,
                        latency_ms=latency_ms,
                        message="API responding",
                    )
                else:
                    return HealthCheckResult(
                        service="azure_openai",
                        healthy=False,
                        latency_ms=latency_ms,
                        message=f"HTTP {response.status_code}",
                    )
        except Exception as e:
            return HealthCheckResult(
                service="azure_openai",
                healthy=False,
                latency_ms=None,
                message=f"Connection failed: {str(e)[:100]}",
            )

    # Try z.ai
    if settings.has_zai:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(
                    f"{settings.zai_base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.zai_api_key}",
                    },
                    json={
                        "model": settings.zai_model,
                        "messages": [{"role": "user", "content": "Hi"}],
                        "max_tokens": 1,
                    },
                )
                latency_ms = (time.time() - start) * 1000

                if response.status_code == 200:
                    return HealthCheckResult(
                        service="zai",
                        healthy=True,
                        latency_ms=latency_ms,
                        message="API responding",
                    )
        except Exception as e:
            return HealthCheckResult(
                service="zai",
                healthy=False,
                latency_ms=None,
                message=f"Connection failed: {str(e)[:100]}",
            )

    # No LLM configured
    return HealthCheckResult(
        service="llm",
        healthy=False,
        message="No LLM API configured",
    )


async def check_github_api() -> HealthCheckResult:
    """Check if GitHub API is accessible."""
    start = time.time()

    if not settings.github_token:
        return HealthCheckResult(
            service="github",
            healthy=False,
            message="No GitHub token configured",
        )

    try:
        client = GitHubClient()
        user = client.github.get_user()
        latency_ms = (time.time() - start) * 1000

        return HealthCheckResult(
            service="github",
            healthy=True,
            latency_ms=latency_ms,
            message=f"Authenticated as {user.login}",
            details={"login": user.login},
        )
    except GithubException as e:
        latency_ms = (time.time() - start) * 1000
        return HealthCheckResult(
            service="github",
            healthy=False,
            latency_ms=latency_ms,
            message=f"GitHub API error: {str(e)[:100]}",
        )
    except Exception as e:
        latency_ms = (time.time() - start) * 1000
        return HealthCheckResult(
            service="github",
            healthy=False,
            latency_ms=latency_ms,
            message=f"Connection failed: {str(e)[:100]}",
        )


async def check_openclaw_gateway() -> HealthCheckResult:
    """Check if OpenClaw Gateway is reachable."""
    start = time.time()

    if not settings.openclaw_enabled:
        return HealthCheckResult(
            service="openclaw",
            healthy=True,  # Not configured, so not a failure
            message="Not enabled",
        )

    try:
        from src.integrations.openclaw_client import OpenClawClient

        client = OpenClawClient()
        ok = await client.health_check()
        latency_ms = (time.time() - start) * 1000

        return HealthCheckResult(
            service="openclaw",
            healthy=ok,
            latency_ms=latency_ms,
            message="Connected" if ok else "Connection failed",
        )
    except Exception as e:
        latency_ms = (time.time() - start) * 1000
        return HealthCheckResult(
            service="openclaw",
            healthy=False,
            latency_ms=latency_ms,
            message=f"Health check failed: {str(e)[:100]}",
        )


async def check_knowledge_graph() -> HealthCheckResult:
    """Check if knowledge graph is accessible."""
    start = time.time()

    if not settings.knowledge_graph_enabled:
        return HealthCheckResult(
            service="knowledge_graph",
            healthy=True,
            message="Not enabled",
        )

    try:
        from src.memory.knowledge_graph import KnowledgeGraphStore

        store = KnowledgeGraphStore()
        ok = await store.health_check()
        latency_ms = (time.time() - start) * 1000

        return HealthCheckResult(
            service="knowledge_graph",
            healthy=ok,
            latency_ms=latency_ms,
            message="Graph accessible" if ok else "Graph not accessible",
        )
    except Exception as e:
        latency_ms = (time.time() - start) * 1000
        return HealthCheckResult(
            service="knowledge_graph",
            healthy=False,
            latency_ms=latency_ms,
            message=f"Health check failed: {str(e)[:100]}",
        )


async def check_all_external_services() -> dict[str, HealthCheckResult]:
    """Run all external service health checks in parallel."""
    results = {}

    # Run all checks in parallel
    import asyncio

    checks = {
        "llm": check_llm_api(),
        "github": check_github_api(),
        "openclaw": check_openclaw_gateway(),
        "knowledge_graph": check_knowledge_graph(),
    }

    # Execute in parallel
    tasks = {name: asyncio.create_task(coro) for name, coro in checks.items()}

    for name, task in tasks.items():
        try:
            results[name] = await task
        except Exception as e:
            results[name] = HealthCheckResult(
                service=name,
                healthy=False,
                message=f"Check failed: {str(e)[:100]}",
            )

    return results


async def get_deep_health_status() -> dict[str, Any]:
    """Get comprehensive health status including external services.

    Returns:
        Dict with overall status and detailed component health
    """
    from src.memory.postgres_store import PostgresStore
    from src.memory.qdrant_store import QdrantStore
    from src.memory.redis_store import RedisStore

    overall_status = "healthy"
    components = {}

    # Check internal stores
    redis_store = RedisStore()
    postgres_store = PostgresStore()
    qdrant_store = QdrantStore()

    try:
        redis_ok = await asyncio.wait_for(redis_store.health_check(), timeout=2.0)
        components["redis"] = {"status": "ok" if redis_ok else "down"}
        if not redis_ok:
            overall_status = "degraded"
    except Exception as e:
        components["redis"] = {"status": "error", "message": str(e)[:100]}
        overall_status = "degraded"

    try:
        async with postgres_store._engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        components["postgres"] = {"status": "ok"}
    except Exception as e:
        components["postgres"] = {"status": "error", "message": str(e)[:100]}
        overall_status = "degraded"

    try:
        qdrant_ok = await asyncio.wait_for(qdrant_store.health_check(), timeout=2.0)
        components["qdrant"] = {"status": "ok" if qdrant_ok else "down"}
        if not qdrant_ok:
            overall_status = "degraded"
    except Exception as e:
        components["qdrant"] = {"status": "error", "message": str(e)[:100]}
        overall_status = "degraded"

    # Check external services
    external = await check_all_external_services()

    for name, result in external.items():
        components[name] = result.to_dict()
        if not result.healthy:
            # External services being down is not necessarily degraded
            # unless they're critical
            if name == "llm":
                overall_status = "degraded"

    return {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat(),
        "environment": settings.environment,
        "components": components,
    }
