"""Retry utilities with exponential backoff.

Provides decorators and utilities for retrying operations with
exponential backoff and jitter for production resilience.
"""

from __future__ import annotations

import logging
import random
import time
from functools import wraps
from typing import Any, Callable, TypeVar

from tenacity import (
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    retry,
)

from src.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ── Retry Decorators ──


def retry_on_llm_error(max_attempts: int = 3) -> Callable:
    """Retry function on LLM API errors with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts

    Returns:
        Decorated function with retry logic
    """
    import httpx

    @retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.RemoteProtocolError, OSError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            return func(*args, **kwargs)
        return wrapper

    return decorator


def retry_on_github_error(max_attempts: int = 3) -> Callable:
    """Retry function on GitHub API errors.

    Handles rate limiting (403) and server errors (500+).
    """
    from github import GithubException

    def is_retryable_error(exc: Exception) -> bool:
        """Check if exception is retryable."""
        if isinstance(exc, GithubException):
            # Rate limited (403) or server error (5xx)
            return exc.status in (403, 500, 502, 503, 504) if hasattr(exc, "status") else False
        return isinstance(exc, (ConnectionError, TimeoutError))

    @retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(GithubException) if is_retryable_error else retry_if_exception_type(Exception),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            return func(*args, **kwargs)
        return wrapper

    return decorator


def retry_on_database_error(max_attempts: int = 3) -> Callable:
    """Retry function on database connection errors.

    Handles connection drops, timeouts, and transient errors.
    """
    import asyncpg
    import sqlalchemy.exc

    @retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type((
            asyncpg.PostgresConnectionError,
            asyncpg.InterfaceError,
            sqlalchemy.exc.OperationalError,
            ConnectionError,
            TimeoutError,
        )),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            return await func(*args, **kwargs)
        return wrapper

    return decorator


def retry_on_websocket_error(max_attempts: int = 5) -> Callable:
    """Retry function on WebSocket connection errors.

    WebSockets are more prone to disconnects; use more retries.
    """
    import websockets

    @retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((
            websockets.exceptions.ConnectionClosed,
            websockets.exceptions.ConnectionClosedError,
            ConnectionError,
            TimeoutError,
        )),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            return await func(*args, **kwargs)
        return wrapper

    return decorator


# ── Retry Context Manager ──


class RetryManager:
    """Context manager for retrying operations with custom logic."""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for this attempt with exponential backoff."""
        delay = min(self.base_delay * (self.exponential_base ** (attempt - 1)), self.max_delay)

        if self.jitter:
            # Add random jitter (±25%)
            delay = delay * (0.75 + random.random() * 0.5)

        return delay

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False


async def retry_async(
    func: Callable,
    *args: Any,
    max_attempts: int = 3,
    **kwargs: Any,
) -> Any:
    """Retry an async function with exponential backoff.

    Args:
        func: Async function to retry
        *args: Positional arguments for func
        max_attempts: Maximum number of attempts
        **kwargs: Keyword arguments for func

    Returns:
        Result of func

    Raises:
        Last exception if all attempts fail
    """
    last_exception = None
    manager = RetryManager(max_attempts=max_attempts)

    for attempt in range(1, max_attempts + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            if attempt < max_attempts:
                delay = manager.get_delay(attempt)
                logger.warning(
                    "Attempt %d/%d failed: %s. Retrying in %.1fs...",
                    attempt,
                    max_attempts,
                    str(e),
                    delay,
                )
                await asyncio.sleep(delay)  # type: ignore
            else:
                logger.error("All %d attempts failed", max_attempts)

    raise last_exception


# Import asyncio at module level for retry_async
import asyncio
