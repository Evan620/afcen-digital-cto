"""FastAPI application — the Digital CTO's HTTP interface.

Endpoints:
  POST /webhook/github  — Receive GitHub webhook events
  GET  /health          — Health check for all services
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request

from src.config import settings
from src.integrations.github_client import GitHubClient
from src.memory.postgres_store import PostgresStore
from src.memory.qdrant_store import QdrantStore
from src.memory.redis_store import RedisStore
from src.supervisor.graph import supervisor_graph

# ── Logging ──

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(name)-30s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("digital_cto")

# ── Shared Resources ──

redis_store = RedisStore()
postgres_store = PostgresStore()
qdrant_store = QdrantStore()
github_client = GitHubClient()


# ── App Lifecycle ──


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: connect to all services. Shutdown: disconnect gracefully."""
    logger.info("=" * 60)
    logger.info("  AfCEN Digital CTO starting up...")
    logger.info("  Environment: %s", settings.environment)
    logger.info("  Monitored repos: %s", settings.monitored_repos or "(none configured)")
    logger.info("=" * 60)

    # Connect memory stores
    await redis_store.connect()
    await postgres_store.init_db()
    await qdrant_store.connect()

    logger.info("All memory stores connected. Digital CTO is online.")

    yield  # App runs here

    # Shutdown
    logger.info("Digital CTO shutting down...")
    await redis_store.disconnect()
    await postgres_store.disconnect()
    await qdrant_store.disconnect()
    logger.info("All connections closed. Goodbye.")


# ── FastAPI App ──

app = FastAPI(
    title="AfCEN Digital CTO",
    description="AI-powered multi-agent technical leadership system",
    version="0.1.0",
    lifespan=lifespan,
)


# ── Endpoints ──


@app.get("/health")
async def health_check():
    """Check the health of all connected services."""
    redis_ok = await redis_store.health_check()
    qdrant_ok = await qdrant_store.health_check()

    # Simple postgres check
    postgres_ok = True
    try:
        async with postgres_store._engine.connect() as conn:
            await conn.execute(
                __import__("sqlalchemy").text("SELECT 1")
            )
    except Exception:
        postgres_ok = False

    all_ok = redis_ok and postgres_ok and qdrant_ok

    return {
        "status": "ok" if all_ok else "degraded",
        "services": {
            "redis": "ok" if redis_ok else "down",
            "postgres": "ok" if postgres_ok else "down",
            "qdrant": "ok" if qdrant_ok else "down",
        },
        "environment": settings.environment,
        "monitored_repos": settings.monitored_repos,
    }


@app.post("/webhook/github")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str = Header(default="", alias="X-Hub-Signature-256"),
    x_github_event: str = Header(default="", alias="X-GitHub-Event"),
):
    """Receive and process GitHub webhook events.

    Currently handles: pull_request events (routes to Code Review agent).
    """
    body = await request.body()

    # Verify webhook signature
    if not github_client.verify_webhook_signature(body, x_hub_signature_256):
        logger.warning("Webhook signature verification failed")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payload = await request.json()

    # Only process pull_request events
    if x_github_event != "pull_request":
        logger.info("Ignoring GitHub event type: %s", x_github_event)
        return {"status": "ignored", "event": x_github_event}

    # Parse the PR event
    try:
        pr_event = github_client.parse_pr_event(payload)
    except Exception as e:
        logger.error("Failed to parse PR event: %s", e)
        raise HTTPException(status_code=400, detail=f"Failed to parse event: {e}")

    # Only review actionable events
    if not pr_event.is_reviewable:
        logger.info("PR event action '%s' is not reviewable — skipping", pr_event.action)
        return {"status": "skipped", "reason": f"Action '{pr_event.action}' not reviewable"}

    # Check if this repo is in our monitored list (if configured)
    if settings.monitored_repos and pr_event.repository_full_name not in settings.monitored_repos:
        logger.info("Repo %s not in monitored list — skipping", pr_event.repository_full_name)
        return {"status": "skipped", "reason": "Repository not monitored"}

    logger.info(
        "Processing PR #%d on %s: '%s' by %s",
        pr_event.pull_request.number,
        pr_event.repository_full_name,
        pr_event.pull_request.title,
        pr_event.pull_request.user.login,
    )

    # Log the raw event for replay/debugging
    await postgres_store.log_event(
        repository=pr_event.repository_full_name,
        pr_number=pr_event.pull_request.number,
        action=pr_event.action,
        payload=payload,
    )

    # Route through the supervisor graph
    supervisor_input = {
        "event_type": "pull_request",
        "source": "github_webhook",
        "payload": {
            "repository_full_name": pr_event.repository_full_name,
            "action": pr_event.action,
            "pull_request": pr_event.pull_request.model_dump(),
        },
        "routed_to": None,
        "result": None,
        "error": None,
    }

    result = await supervisor_graph.ainvoke(supervisor_input)

    if result.get("error"):
        logger.error("Supervisor error: %s", result["error"])
        return {"status": "error", "detail": result["error"]}

    return {
        "status": "processed",
        "pr": f"{pr_event.repository_full_name}#{pr_event.pull_request.number}",
        "result": result.get("result"),
    }


@app.get("/")
async def root():
    """Landing page with basic info."""
    return {
        "name": "AfCEN Digital CTO",
        "version": "0.1.0",
        "phase": "1 — Foundation",
        "capabilities": ["code_review", "pr_management"],
        "docs": "/docs",
    }
