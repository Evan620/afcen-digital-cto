# ── Production Middleware ──
"""API authentication, rate limiting, and validation for production.

This module provides security and reliability middleware for FastAPI.
"""

from __future__ import annotations

import os
from functools import wraps
from typing import Callable

from fastapi import Header, HTTPException, Request, status
from fastapi.security import APIKeyHeader, APIKeyQuery
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from src.config import settings

# ── Rate Limiter ──

limiter = Limiter(key_func=get_remote_address)


# ── API Key Authentication ──

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
api_key_query = APIKeyQuery(name="api_key", auto_error=False)


async def verify_api_key(
    api_key_header: str | None = None,
    api_key_query: str | None = None,
) -> None:
    """Verify API key from header or query parameter.

    In development, bypass auth if DEVELOPMENT_MODE is set.
    In production, require valid API key.
    """
    # Skip auth in development if explicitly allowed
    if settings.environment == "development" and os.getenv("DEVELOPMENT_MODE") == "true":
        return

    # Get the API key from header or query
    api_key = api_key_header or api_key_query

    # If no API keys are configured, allow all (for local dev)
    configured_keys = os.getenv("DIGITAL_CTO_API_KEYS", "").split(",")
    if not any(k.strip() for k in configured_keys):
        # No keys configured - allow in development only
        if settings.environment == "development":
            return
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API authentication not configured on server",
        )

    # Verify the provided key
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Provide via X-API-Key header or api_key query parameter.",
        )

    if api_key not in [k.strip() for k in configured_keys if k.strip()]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )


# ── Optional Auth Decorator ──

def require_auth(f: Callable) -> Callable:
    """Decorator to require authentication for an endpoint.

    Use this for endpoints that should always require auth,
    even in development (unless DEVELOPMENT_MODE=true).
    """
    @wraps(f)
    async def wrapper(*args, **kwargs):
        # The actual auth check is done by FastAPI dependency injection
        # This decorator is for documentation purposes
        return await f(*args, **kwargs)
    return wrapper


# ── Public Endpoints List ──

PUBLIC_ENDPOINTS = {
    "/",
    "/health",
    "/docs",
    "/openapi.json",
    "/.well-known/agent.json",  # A2A discovery
}

# Webhook endpoints (use signature-based auth, not API keys)
WEBHOOK_ENDPOINTS = {
    "/webhook/github",
    "/webhook/a2a",
}


def is_public_endpoint(request: Request) -> bool:
    """Check if an endpoint is public (no auth required)."""
    path = request.url.path
    return path in PUBLIC_ENDPOINTS or path.startswith("/docs")


def is_webhook_endpoint(request: Request) -> bool:
    """Check if an endpoint is a webhook (uses signature auth)."""
    return request.url.path in WEBHOOK_ENDPOINTS
