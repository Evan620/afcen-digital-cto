"""Prometheus metrics export for Digital CTO.

Provides standardized metrics for monitoring and observability.
"""

from __future__ import annotations

import logging
import time
from functools import wraps
from typing import Callable, TypeVar

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Summary,
    Info,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
from fastapi import Response

from src.config import settings

logger = logging.getLogger(__name__)

# ── Registry ──

# Default registry for all metrics
registry = CollectorRegistry()

# Disable default metrics that create noise
# from prometheus_client import REGISTRY as DEFAULT_REGISTRY
# DEFAULT_REGISTRY.clear()  # Optional: Start fresh


# ── HTTP Metrics ──

http_requests_total = Counter(
    "digital_cto_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
    registry=registry,
)

http_request_duration_seconds = Histogram(
    "digital_cto_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=registry,
)

http_requests_in_progress = Gauge(
    "digital_cto_http_requests_in_progress",
    "HTTP requests currently in progress",
    ["method", "endpoint"],
    registry=registry,
)


# ── Agent Metrics ──

agent_invocations_total = Counter(
    "digital_cto_agent_invocations_total",
    "Total agent invocations",
    ["agent", "event_type"],
    registry=registry,
)

agent_duration_seconds = Histogram(
    "digital_cto_agent_duration_seconds",
    "Agent execution duration",
    ["agent"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 300.0),
    registry=registry,
)

agent_errors_total = Counter(
    "digital_cto_agent_errors_total",
    "Total agent errors",
    ["agent", "error_type"],
    registry=registry,
)


# ── LLM Metrics ──

llm_requests_total = Counter(
    "digital_cto_llm_requests_total",
    "Total LLM API requests",
    ["provider", "model"],
    registry=registry,
)

llm_tokens_total = Counter(
    "digital_cto_llm_tokens_total",
    "Total LLM tokens used",
    ["provider", "model", "type"],  # type: input, output
    registry=registry,
)

llm_duration_seconds = Histogram(
    "digital_cto_llm_duration_seconds",
    "LLM API request duration",
    ["provider", "model"],
    buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0),
    registry=registry,
)

llm_errors_total = Counter(
    "digital_cto_llm_errors_total",
    "Total LLM API errors",
    ["provider", "error_type"],
    registry=registry,
)


# ── GitHub Metrics ──

github_requests_total = Counter(
    "digital_cto_github_requests_total",
    "Total GitHub API requests",
    ["endpoint", "status"],
    registry=registry,
)

github_rate_limit_remaining = Gauge(
    "digital_cto_github_rate_limit_remaining",
    "GitHub API rate limit remaining",
    registry=registry,
)


# ── Memory Store Metrics ──

redis_operations_total = Counter(
    "digital_cto_redis_operations_total",
    "Total Redis operations",
    ["operation", "status"],
    registry=registry,
)

postgres_queries_total = Counter(
    "digital_cto_postgres_queries_total",
    "Total PostgreSQL queries",
    ["operation", "status"],
    registry=registry,
)

qdrant_operations_total = Counter(
    "digital_cto_qdrant_operations_total",
    "Total Qdrant operations",
    ["operation", "status"],
    registry=registry,
)


# ── Coding Agent Metrics ──

coding_tasks_total = Counter(
    "digital_cto_coding_tasks_total",
    "Total coding tasks submitted",
    ["complexity", "status"],
    registry=registry,
)

coding_task_duration_seconds = Histogram(
    "digital_cto_coding_task_duration_seconds",
    "Coding task execution duration",
    ["complexity"],
    buckets=(5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0),
    registry=registry,
)

coding_files_modified_total = Counter(
    "digital_cto_coding_files_modified_total",
    "Total files modified by coding agent",
    ["agent"],
    registry=registry,
)


# ── System Info ──

build_info = Info(
    "digital_cto_build_info",
    "Digital CTO build information",
    registry=registry,
)

# Set build info
build_info.info({
    "version": "0.5.0",
    "environment": settings.environment,
    "python_version": "3.12",
})


# ── Decorators for Easy Metrics ──

T = TypeVar("T")


def track_http_request(method: str, endpoint: str):
    """Decorator to track HTTP request metrics."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            http_requests_in_progress.labels(
                method=method,
                endpoint=endpoint,
            ).inc()

            status = "unknown"
            start = time.time()

            try:
                result = await func(*args, **kwargs)
                status = "success"
                return result
            except Exception as e:
                status = type(e).__name__
                raise
            finally:
                duration = time.time() - start
                http_requests_in_progress.labels(
                    method=method,
                    endpoint=endpoint,
                ).dec()
                http_request_duration_seconds.labels(
                    method=method,
                    endpoint=endpoint,
                ).observe(duration)
                http_requests_total.labels(
                    method=method,
                    endpoint=endpoint,
                    status=status,
                ).inc()

        return wrapper
    return decorator


def track_agent_invocation(agent: str, event_type: str):
    """Decorator to track agent execution metrics."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            agent_invocations_total.labels(
                agent=agent,
                event_type=event_type,
            ).inc()

            start = time.time()
            error_type = None

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                error_type = type(e).__name__
                agent_errors_total.labels(
                    agent=agent,
                    error_type=error_type,
                ).inc()
                raise
            finally:
                duration = time.time() - start
                agent_duration_seconds.labels(
                    agent=agent,
                ).observe(duration)

        return wrapper
    return decorator


def track_llm_request(provider: str, model: str):
    """Decorator to track LLM API metrics."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            llm_requests_total.labels(
                provider=provider,
                model=model,
            ).inc()

            start = time.time()
            error_type = None

            try:
                result = await func(*args, **kwargs)
                # Try to extract token count from result
                # This depends on the actual LLM client implementation
                return result
            except Exception as e:
                error_type = type(e).__name__
                llm_errors_total.labels(
                    provider=provider,
                    error_type=error_type,
                ).inc()
                raise
            finally:
                duration = time.time() - start
                llm_duration_seconds.labels(
                    provider=provider,
                    model=model,
                ).observe(duration)

        return wrapper
    return decorator


# ── Metrics Endpoint for FastAPI ──


async def metrics_endpoint() -> Response:
    """Return Prometheus metrics text format."""
    from fastapi.responses import Response

    output = generate_latest(registry)
    return Response(content=output, media_type=CONTENT_TYPE_LATEST)
