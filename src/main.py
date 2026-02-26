"""FastAPI application — the Digital CTO's HTTP interface.

Endpoints:
  POST /webhook/github       — Receive GitHub webhook events
  GET  /health               — Health check for all services
  GET  /sprint/*             — Sprint status, reports, Bayes tracking, retrospective
  POST /architecture/query   — Architecture evaluation requests
  GET  /architecture/decisions — Recent architecture decisions
  GET  /devops/status        — Pipeline status and alerts
  GET  /devops/report        — Full DevOps health report
  POST /jarvis/directive     — HTTP fallback for JARVIS directives
  GET  /market/*             — Market intelligence and morning briefs (Phase 3)
  POST /market/scan          — Trigger market data collection
  POST /market/brief         — Generate morning brief on demand
  POST /meeting/analyze      — Analyze meeting transcript (Phase 3)
  POST /meeting/brief        — Generate pre-meeting brief (Phase 3)
  POST /meeting/bot          — Deploy Recall.ai bot to meeting (Phase 3)
  GET  /meeting/status       — Meeting intelligence status (Phase 3)
"""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request, Response, status
from slowapi.errors import RateLimitExceeded

from src.config import settings
from src.logging_config import logger  # Use structured logging
from src.middleware import (
    limiter,
    verify_api_key,
    is_public_endpoint,
    is_webhook_endpoint,
)
from src.validation import validate_and_exit
from src.health import get_deep_health_status
from src.integrations.github_client import GitHubClient
from src.integrations.openclaw_client import OpenClawClient
from src.memory.postgres_store import PostgresStore
from src.memory.qdrant_store import QdrantStore
from src.memory.redis_store import RedisStore
from src.supervisor.graph import supervisor_graph
from src.agents.sprint_planner.agent import (
    get_sprint_status,
    get_sprint_report,
    get_bayes_tracking,
    get_sprint_retrospective,
)
from src.agents.architecture_advisor.agent import query_architecture
from src.agents.devops.agent import get_pipeline_status, get_devops_report
from src.agents.market_scanner.agent import (
    collect_market_data,
    generate_morning_brief,
    get_market_scanner_status,
)
from src.agents.meeting_intelligence.agent import (
    analyze_meeting_transcript,
    generate_pre_meeting_brief,
    deploy_meeting_bot,
)
from src.integrations.jarvis_handler import JarvisDirectiveHandler
from src.models.schemas import JarvisDirective, JarvisDirectiveType
from src.agents.coding_agent.agent import execute_coding_task, get_task_status
from src.agents.coding_agent.models import CodingTask, CodingComplexity
from src.integrations.a2a_handler import get_digital_cto_agent_card, A2AProtocolHandler, A2ADirective
from src.memory.knowledge_graph import KnowledgeGraphStore

# ── Shared Resources ──

redis_store = RedisStore()
postgres_store = PostgresStore()
qdrant_store = QdrantStore()
github_client = GitHubClient()
openclaw_client = OpenClawClient() if settings.openclaw_enabled else None
jarvis_handler = JarvisDirectiveHandler(openclaw_client)

# Phase 4: Knowledge Graph and A2A
knowledge_graph_store = KnowledgeGraphStore() if settings.knowledge_graph_enabled else None
a2a_handler = A2AProtocolHandler(shared_secret=settings.a2a_shared_secret) if settings.a2a_enabled else None


# ── App Lifecycle ──


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: connect to all services. Shutdown: disconnect gracefully."""
    logger.info("=" * 60)
    logger.info("  AfCEN Digital CTO starting up...")
    logger.info("  Environment: %s", settings.environment)
    logger.info("  Monitored repos: %s", settings.monitored_repos or "(none configured)")
    logger.info("  OpenClaw enabled: %s", settings.openclaw_enabled)
    logger.info("  Scheduler enabled: %s", settings.scheduler_enabled)
    logger.info("=" * 60)

    # Validate configuration before connecting to services
    validate_and_exit()

    # Connect memory stores
    await redis_store.connect()
    await postgres_store.init_db()
    await qdrant_store.connect()

    # Connect to OpenClaw if enabled
    if openclaw_client:
        openclaw_ok = await openclaw_client.health_check()
        if openclaw_ok:
            logger.info("OpenClaw Gateway connected: %s", settings.openclaw_gateway_url)
            # Register Digital CTO capabilities
            await openclaw_client.register_agent(
                agent_name="Digital CTO",
                capabilities=[
                    "code_review",
                    "sprint_planning",
                    "bayes_tracking",
                    "metrics_reporting",
                    "architecture_advisory",
                    "devops_monitoring",
                    "market_intelligence",
                    "morning_briefs",
                    "ceo_commands",
                    "code_generation",  # Phase 4
                ],
                endpoints={
                    "health": "/health",
                    "sprint_status": "/sprint/status",
                    "sprint_report": "/sprint/report",
                    "sprint_retrospective": "/sprint/retrospective",
                    "bayes_tracking": "/sprint/bayes",
                    "sprint_query": "/sprint/query",
                    "architecture_query": "/architecture/query",
                    "architecture_decisions": "/architecture/decisions",
                    "devops_status": "/devops/status",
                    "devops_report": "/devops/report",
                    "market_scan": "/market/scan",
                    "market_brief": "/market/brief",
                    "market_status": "/market/status",
                    "jarvis_directive": "/jarvis/directive",
                    "coding_task": "/coding/task",  # Phase 4
                },
            )
            # Register JARVIS directive event handlers
            jarvis_handler.register_event_handlers()
        else:
            logger.warning("OpenClaw Gateway not reachable at %s", settings.openclaw_gateway_url)

    # Initialize knowledge graph if enabled
    if knowledge_graph_store:
        try:
            await knowledge_graph_store.init_graph()
            logger.info("Knowledge graph initialized")
        except Exception as e:
            logger.warning("Failed to initialize knowledge graph: %s", e)

    # Auto-discover A2A agents if enabled
    if a2a_handler and settings.a2a_known_agents:
        try:
            discovered = await a2a_handler.discover_agents(settings.a2a_known_agents)
            logger.info("A2A agent discovery complete: %d agents found", len(discovered))
        except Exception as e:
            logger.warning("A2A agent discovery failed: %s", e)

    # Start APScheduler if enabled
    scheduler = None
    if settings.scheduler_enabled:
        try:
            from src.scheduler import configure_scheduler

            scheduler = configure_scheduler()
            scheduler.start()
            logger.info("APScheduler started with %d jobs", len(scheduler.get_jobs()))
        except Exception as e:
            logger.error("Failed to start scheduler: %s", e)

    logger.info("All memory stores connected. Digital CTO is online.")

    yield  # App runs here

    # Graceful Shutdown
    logger.info("Digital CTO shutting down...")
    shutdown_start = time.time()

    # 1. Stop accepting new requests (FastAPI handles this)
    # 2. Wait for in-progress requests to complete (timeout: 30s)
    # 3. Shutdown scheduler jobs gracefully
    if scheduler:
        try:
            scheduler.shutdown(wait=True)
            logger.info("APScheduler stopped gracefully")
        except Exception as e:
            logger.warning("Scheduler shutdown had issues: %s", e)

    # 4. Close WebSocket connections
    if openclaw_client:
        try:
            await openclaw_client.close()
            logger.info("OpenClaw connection closed")
        except Exception as e:
            logger.warning("OpenClaw close had issues: %s", e)

    # 5. Disconnect memory stores with timeout
    disconnect_tasks = [
        redis_store.disconnect(),
        postgres_store.disconnect(),
        qdrant_store.disconnect(),
    ]

    try:
        await asyncio.gather(*disconnect_tasks, return_exceptions=True)
        logger.info("All memory stores disconnected")
    except Exception as e:
        logger.warning("Some store disconnects had issues: %s", e)

    shutdown_duration = time.time() - shutdown_start
    logger.info("Shutdown complete in %.2fs. Goodbye.", shutdown_duration)


# ── FastAPI App ──

app = FastAPI(
    title="AfCEN Digital CTO",
    description="AI-powered multi-agent technical leadership system",
    version="0.5.0",  # Bump for production features
    lifespan=lifespan,
)

# Add rate limiter to app state
app.state.limiter = limiter


# ── Exception Handlers ──


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Handle rate limit exceeded errors."""
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail={
            "error": "Rate limit exceeded",
            "message": "Too many requests. Please slow down.",
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with consistent JSON format."""
    from starlette.responses import JSONResponse

    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail},
    )


# ── Middleware ──


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Apply API key authentication to protected endpoints."""
    # Skip auth for public endpoints
    if is_public_endpoint(request) or is_webhook_endpoint(request):
        return await call_next(request)

    # Skip auth if not required in config
    if not settings.require_auth:
        return await call_next(request)

    # Verify API key
    api_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
    configured_keys = settings.digital_cto_api_keys.split(",") if settings.digital_cto_api_keys else []

    if not configured_keys or not any(k.strip() for k in configured_keys):
        # No keys configured - allow in development
        if settings.environment == "development":
            return await call_next(request)
        # But fail in production
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "API authentication not configured on server"},
        )

    if not api_key or api_key not in [k.strip() for k in configured_keys]:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"error": "Invalid or missing API key"},
        )

    return await call_next(request)


from fastapi.responses import JSONResponse


# ── Endpoints ──


@app.get("/health")
@limiter.limit("60/minute")
async def health_check(request: Request):
    """Quick health check for load balancers.

    For detailed health including external services, use /health/deep.
    """
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

    # OpenClaw check
    openclaw_ok = False
    if openclaw_client:
        openclaw_ok = await openclaw_client.health_check()

    # Scheduler check
    scheduler_ok = False
    if settings.scheduler_enabled:
        from src.scheduler import get_scheduler

        sched = get_scheduler()
        scheduler_ok = sched is not None and sched.running

    all_ok = redis_ok and postgres_ok and qdrant_ok
    if settings.openclaw_enabled:
        all_ok = all_ok and openclaw_ok

    # Knowledge graph check
    knowledge_graph_ok = False
    if settings.knowledge_graph_enabled and knowledge_graph_store:
        try:
            knowledge_graph_ok = await knowledge_graph_store.health_check()
        except Exception:
            knowledge_graph_ok = False

    services = {
        "redis": "ok" if redis_ok else "down",
        "postgres": "ok" if postgres_ok else "down",
        "qdrant": "ok" if qdrant_ok else "down",
    }
    if settings.openclaw_enabled:
        services["openclaw"] = "ok" if openclaw_ok else "down"
    if settings.scheduler_enabled:
        services["scheduler"] = "ok" if scheduler_ok else "down"
    if settings.knowledge_graph_enabled:
        services["knowledge_graph"] = "ok" if knowledge_graph_ok else "down"

    return {
        "status": "ok" if all_ok else "degraded",
        "services": services,
        "environment": settings.environment,
        "monitored_repos": settings.monitored_repos,
        "openclaw_enabled": settings.openclaw_enabled,
        "agents": ["code_review", "sprint_planner", "architecture_advisor", "devops", "market_scanner", "coding_agent"],
        "phase": "5 — Production Ready",
    }


@app.get("/health/deep")
async def deep_health_check():
    """Comprehensive health check including external services.

    Checks:
    - Internal stores (Redis, PostgreSQL, Qdrant)
    - LLM APIs (Anthropic, Azure OpenAI, z.ai)
    - GitHub API
    - OpenClaw Gateway
    - Knowledge Graph
    """
    return await get_deep_health_status()


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
        "version": "0.4.0",
        "phase": "4 — Advanced Capabilities",
        "capabilities": [
            "code_review",
            "sprint_planner",
            "bayes_tracking",
            "architecture_advisor",
            "devops_monitoring",
            "market_intelligence",
            "morning_briefs",
            "jarvis_directives",
            "code_generation",  # Phase 4
            "knowledge_graph",  # Phase 4
        ],
        "docs": "/docs",
    }


# ── Sprint Planner Endpoints ──


@app.get("/sprint/status")
async def sprint_status(repository: str | None = None):
    """Get quick sprint status with metrics."""
    try:
        metrics = await get_sprint_status(repository)
        return {"status": "ok", "metrics": metrics}
    except Exception as e:
        logger.error("Failed to get sprint status: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sprint/report")
async def sprint_report(repository: str | None = None, sprint_id: str | None = None):
    """Get comprehensive sprint report."""
    try:
        report = await get_sprint_report(repository, sprint_id)
        return {"status": "ok", "report": report}
    except Exception as e:
        logger.error("Failed to get sprint report: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sprint/bayes")
async def bayes_tracking(repository: str | None = None):
    """Get Bayes Consulting deliverable tracking."""
    try:
        bayes = await get_bayes_tracking(repository)
        return {"status": "ok", "bayes_summary": bayes}
    except Exception as e:
        logger.error("Failed to get Bayes tracking: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sprint/retrospective")
async def sprint_retrospective(repository: str | None = None):
    """Generate a sprint retrospective analysis."""
    try:
        retro = await get_sprint_retrospective(repository)
        return {"status": "ok", "retrospective": retro}
    except Exception as e:
        logger.error("Failed to generate retrospective: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/sprint/query")
async def sprint_query(request: Request):
    """Generic sprint query endpoint for JARVIS integration."""
    body = await request.json()
    query_type = body.get("query_type", "status")
    repository = body.get("repository")
    sprint_id = body.get("sprint_id")

    # Route through the supervisor graph
    supervisor_input = {
        "event_type": query_type,
        "source": "jarvis",
        "payload": {
            "repository": repository,
            "sprint_id": sprint_id,
            "include_bayes": body.get("include_bayes", True),
            "include_recommendations": body.get("include_recommendations", True),
        },
        "routed_to": None,
        "result": None,
        "error": None,
    }

    result = await supervisor_graph.ainvoke(supervisor_input)

    if result.get("error"):
        logger.error("Sprint query error: %s", result["error"])
        raise HTTPException(status_code=500, detail=result["error"])

    return {"status": "ok", "result": result.get("result")}


# ── Architecture Advisor Endpoints ──


@app.post("/architecture/query")
async def architecture_query(request: Request):
    """Submit an architecture evaluation request."""
    body = await request.json()
    query = body.get("query", "")
    query_type = body.get("query_type", "technology_evaluation")
    repository = body.get("repository")
    context = body.get("context", {})

    if not query:
        raise HTTPException(status_code=400, detail="'query' field is required")

    try:
        recommendation = await query_architecture(
            query=query,
            query_type=query_type,
            repository=repository,
            context=context,
        )
        return {"status": "ok", "recommendation": recommendation}
    except Exception as e:
        logger.error("Architecture query failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/architecture/decisions")
async def architecture_decisions(limit: int = 10):
    """List recent architecture decisions from PostgreSQL."""
    try:
        from sqlalchemy import select
        from src.memory.postgres_store import AgentDecision

        async with postgres_store.session() as session:
            stmt = (
                select(AgentDecision)
                .where(AgentDecision.agent_name == "architecture_advisor")
                .order_by(AgentDecision.created_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()

        decisions = [
            {
                "id": r.id,
                "decision_type": r.decision_type,
                "reasoning": r.reasoning,
                "outcome": r.outcome,
                "context": r.context,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
        return {"status": "ok", "decisions": decisions}
    except Exception as e:
        logger.error("Failed to fetch architecture decisions: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ── DevOps Endpoints ──


@app.get("/devops/status")
async def devops_status(repository: str | None = None):
    """Get current pipeline status and alerts."""
    try:
        repos = [repository] if repository else None
        status = await get_pipeline_status(repos)
        return {"status": "ok", "devops": status}
    except Exception as e:
        logger.error("Failed to get DevOps status: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/devops/report")
async def devops_report(repository: str | None = None):
    """Get full DevOps health report with failure analysis."""
    try:
        repos = [repository] if repository else None
        report = await get_devops_report(repos)
        return {"status": "ok", "report": report}
    except Exception as e:
        logger.error("Failed to get DevOps report: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ── JARVIS Directive Endpoint ──


@app.post("/jarvis/directive")
async def jarvis_directive(request: Request):
    """HTTP fallback endpoint for receiving JARVIS directives."""
    body = await request.json()

    try:
        directive = JarvisDirective(
            directive_id=body.get("directive_id", ""),
            type=JarvisDirectiveType(body.get("type", "general_query")),
            payload=body.get("payload", {}),
            priority=body.get("priority", "normal"),
            sender=body.get("sender", "jarvis"),
        )
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid directive: {e}")

    try:
        response = await jarvis_handler.handle_directive(directive)
        return {
            "status": "ok",
            "response": {
                "response_to": response.response_to,
                "status": response.status.value,
                "result": response.result,
                "error": response.error,
            },
        }
    except Exception as e:
        logger.error("JARVIS directive failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ── Market Scanner Endpoints (Phase 3) ──


@app.post("/market/scan")
async def market_scan(hours_back: int = 24):
    """Trigger market data collection from all sources.

    Args:
        hours_back: Number of hours to look back for news items

    Returns summary of collected data.
    """
    try:
        result = await collect_market_data(hours_back=hours_back)
        return {
            "status": "ok",
            "result": {
                "news_items_collected": len(result.get("news_items", [])),
                "dfi_opportunities_collected": len(result.get("dfi_opportunities", [])),
                "carbon_updates_collected": len(result.get("carbon_updates", [])),
                "sources_succeeded": result.get("sources_succeeded", []),
                "sources_failed": result.get("sources_failed", {}),
            },
        }
    except Exception as e:
        logger.error("Market scan failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/market/brief")
async def market_brief():
    """Generate a morning brief on demand.

    Returns the generated brief with all sections.
    """
    try:
        brief = await generate_morning_brief()
        if not brief:
            raise HTTPException(status_code=500, detail="Brief generation failed")

        return {
            "status": "ok",
            "brief": {
                "brief_id": brief.brief_id,
                "brief_date": brief.brief_date.isoformat() if brief.brief_date else None,
                "market_moves": [m.model_dump() for m in brief.market_moves],
                "policy_updates": [p.model_dump() for p in brief.policy_updates],
                "funding_opportunities": [f.model_dump() for f in brief.funding_opportunities],
                "competitive_intelligence": brief.competitive_intelligence,
                "recommended_actions": [a.model_dump() for a in brief.recommended_actions],
                "intel_items_collected": brief.intel_items_collected,
                "delivered": brief.delivered,
            },
        }
    except Exception as e:
        logger.error("Morning brief generation failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/market/status")
async def market_status():
    """Get current market scanner status and recent statistics."""
    try:
        status = await get_market_scanner_status()
        return {"status": "ok", "market_scanner": status}
    except Exception as e:
        logger.error("Market status check failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/market/intel")
async def market_intel(hours: int = 24, min_relevance: float = 0.3, limit: int = 50):
    """Retrieve recent market intelligence from the database.

    Args:
        hours: Hours to look back
        min_relevance: Minimum relevance score (0.0-1.0)
        limit: Maximum items to return
    """
    try:
        from src.agents.market_scanner.tools import MarketIntelStore

        store = MarketIntelStore()
        intel = await store.get_recent_intel(hours=hours, min_relevance=min_relevance, limit=limit)
        return {"status": "ok", "intel": intel, "count": len(intel)}
    except Exception as e:
        logger.error("Failed to retrieve market intel: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/market/briefs")
async def morning_briefs(limit: int = 10):
    """Retrieve recent morning briefs from the database.

    Args:
        limit: Maximum number of briefs to return
    """
    try:
        briefs = await postgres_store.get_morning_briefs(limit=limit)
        return {"status": "ok", "briefs": briefs, "count": len(briefs)}
    except Exception as e:
        logger.error("Failed to retrieve morning briefs: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ── Meeting Intelligence Endpoints (Phase 3) ──


@app.post("/meeting/analyze")
async def meeting_analyze(request: Request):
    """Analyze a meeting transcript and extract structured information.

    Expected body:
    {
        "transcript": "Full meeting transcript text",
        "meeting_title": "Meeting title",
        "participants": ["Person 1", "Person 2"],
        "meeting_date": "2024-01-15T10:00:00Z" (optional)
    }
    """
    body = await request.json()

    transcript = body.get("transcript", "")
    if not transcript:
        raise HTTPException(status_code=400, detail="'transcript' field is required")

    meeting_title = body.get("meeting_title", "Unknown Meeting")
    participants = body.get("participants", [])

    from datetime import datetime

    meeting_date = None
    if body.get("meeting_date"):
        try:
            meeting_date = datetime.fromisoformat(body["meeting_date"])
        except Exception:
            meeting_date = None

    try:
        analysis = await analyze_meeting_transcript(
            transcript=transcript,
            meeting_title=meeting_title,
            participants=participants,
            meeting_date=meeting_date,
        )

        if not analysis:
            raise HTTPException(status_code=500, detail="Analysis failed")

        return {
            "status": "ok",
            "analysis": {
                "meeting_id": analysis.meeting_id,
                "title": analysis.title,
                "date": analysis.date.isoformat() if analysis.date else None,
                "summary": analysis.summary,
                "key_decisions": analysis.key_decisions,
                "action_items": analysis.action_items,
                "technical_topics": analysis.technical_topics,
                "pain_points": analysis.pain_points,
                "opportunities": analysis.opportunities,
                "suggested_prds": analysis.suggested_prds,
                "suggested_integrations": analysis.suggested_integrations,
            },
        }
    except Exception as e:
        logger.error("Meeting analysis failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/meeting/brief")
async def meeting_brief(request: Request):
    """Generate a pre-meeting brief with context.

    Expected body:
    {
        "meeting_title": "Meeting title",
        "participants": ["Person 1", "Person 2"],
        "meeting_date": "2024-01-15T10:00:00Z" (optional),
        "meeting_type": "TWG / standup / etc" (optional)
    }
    """
    body = await request.json()

    meeting_title = body.get("meeting_title", "Unknown Meeting")
    participants = body.get("participants", [])

    from datetime import datetime

    meeting_date = None
    if body.get("meeting_date"):
        try:
            meeting_date = datetime.fromisoformat(body["meeting_date"])
        except Exception:
            meeting_date = None

    meeting_type = body.get("meeting_type")

    try:
        brief = await generate_pre_meeting_brief(
            meeting_title=meeting_title,
            participants=participants,
            meeting_date=meeting_date,
            meeting_type=meeting_type,
        )

        if not brief:
            raise HTTPException(status_code=500, detail="Brief generation failed")

        return {
            "status": "ok",
            "brief": {
                "meeting_title": brief.meeting_title,
                "scheduled_time": brief.scheduled_time.isoformat() if brief.scheduled_time else None,
                "participants": brief.participants,
                "recent_meetings_with_participants": brief.recent_meetings_with_participants,
                "outstanding_action_items": brief.outstanding_action_items,
                "topics_likely_discussed": brief.topics_likely_discussed,
                "decisions_expected": brief.decisions_expected,
                "context_to_have_ready": brief.context_to_have_ready,
                "relevant_developments": brief.relevant_developments,
            },
        }
    except Exception as e:
        logger.error("Meeting brief generation failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/meeting/bot")
async def meeting_bot(request: Request):
    """Deploy a Recall.ai bot to a meeting.

    Expected body:
    {
        "meeting_url": "https://zoom.us/j/...",
        "meeting_title": "Meeting title" (optional)
    }
    """
    body = await request.json()

    meeting_url = body.get("meeting_url", "")
    if not meeting_url:
        raise HTTPException(status_code=400, detail="'meeting_url' field is required")

    meeting_title = body.get("meeting_title", "")

    if not settings.recall_api_key:
        raise HTTPException(
            status_code=501,
            detail="Recall.ai API key not configured. Set RECALL_API_KEY.",
        )

    try:
        result = await deploy_meeting_bot(
            meeting_url=meeting_url,
            meeting_title=meeting_title,
        )

        if not result:
            raise HTTPException(status_code=500, detail="Bot deployment failed")

        return {
            "status": "ok",
            "bot": {
                "bot_id": result.get("bot_id"),
                "status": result.get("status"),
                "meeting_url": meeting_url,
            },
        }
    except Exception as e:
        logger.error("Meeting bot deployment failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/meeting/status")
async def meeting_status():
    """Get meeting intelligence status and recent statistics."""
    try:
        recent_meetings = await postgres_store.get_recent_meetings(days=30, limit=10)
        outstanding_actions = await postgres_store.get_outstanding_actions()

        return {
            "status": "ok",
            "meeting_intelligence": {
                "recent_meetings": len(recent_meetings),
                "outstanding_actions": len(outstanding_actions),
                "recall_configured": bool(settings.recall_api_key),
                "recent_meetings_list": [
                    {
                        "meeting_id": m.get("meeting_id"),
                        "title": m.get("title"),
                        "date": m.get("meeting_date"),
                        "participants": m.get("participants"),
                    }
                    for m in recent_meetings[:5]
                ],
            },
        }
    except Exception as e:
        logger.error("Meeting status check failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ── Coding Agent Endpoints (Phase 4) ──


@app.post("/coding/task")
async def submit_coding_task(request: Request):
    """Submit a coding task to the Coding Agent.

    Expected body:
    {
        "description": "Add a health check endpoint",
        "repository": "afcen/platform",
        "complexity": "simple",
        "base_branch": "main",
        "requires_testing": true,
        "cost_sensitivity": "medium",
        "autonomy_level": "semi_autonomous"
    }
    """
    if not settings.coding_enabled:
        raise HTTPException(status_code=501, detail="Coding agent is not enabled")

    body = await request.json()

    description = body.get("description", "")
    if not description:
        raise HTTPException(status_code=400, detail="'description' field is required")

    repository = body.get("repository", "")
    if not repository:
        raise HTTPException(status_code=400, detail="'repository' field is required")

    # Create the coding task
    import uuid

    task = CodingTask(
        task_id=body.get("task_id") or str(uuid.uuid4()),
        description=description,
        repository=repository,
        base_branch=body.get("base_branch", "main"),
        complexity=CodingComplexity(body.get("complexity", "moderate")),
        estimated_files=body.get("estimated_files", 1),
        requires_testing=body.get("requires_testing", True),
        cost_sensitivity=body.get("cost_sensitivity", "medium"),
        autonomy_level=body.get("autonomy_level", "semi_autonomous"),
        context=body.get("context", {}),
        related_issue=body.get("related_issue"),
        related_pr=body.get("related_pr"),
        branch_name=body.get("branch_name"),
        timeout_seconds=body.get("timeout_seconds", 300),
    )

    # Validate safety
    is_safe, reason = task.is_safe_to_execute()
    if not is_safe:
        raise HTTPException(status_code=400, detail=reason)

    try:
        # Execute the task (runs in background)
        result = await execute_coding_task(task)

        return {
            "status": "ok",
            "task_id": task.task_id,
            "result": result.to_dict(),
        }

    except Exception as e:
        logger.error("Coding task execution failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/coding/status/{task_id}")
async def get_coding_task_status(task_id: str):
    """Get the status of a coding task.

    Args:
        task_id: The task identifier
    """
    if not settings.coding_enabled:
        raise HTTPException(status_code=501, detail="Coding agent is not enabled")

    try:
        result = await get_task_status(task_id)

        if not result:
            raise HTTPException(status_code=404, detail="Task not found")

        return {
            "status": "ok",
            "task": result.to_dict(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get coding task status: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/coding/history")
async def get_coding_task_history(limit: int = 20):
    """Get recent coding task history.

    Args:
        limit: Maximum number of tasks to return
    """
    if not settings.coding_enabled:
        raise HTTPException(status_code=501, detail="Coding agent is not enabled")

    try:
        from src.agents.coding_agent.agent import _task_store

        tasks = list(_task_store.values())[-limit:]
        return {
            "status": "ok",
            "tasks": [t.to_dict() for t in tasks],
            "count": len(tasks),
        }

    except Exception as e:
        logger.error("Failed to get coding task history: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ── Knowledge Graph Endpoints (Phase 4) ──


@app.get("/graph/decisions")
async def get_graph_decisions(
    agent_name: str | None = None,
    decision_type: str | None = None,
    limit: int = 20,
):
    """Query decisions from the knowledge graph.

    Args:
        agent_name: Filter by agent name
        decision_type: Filter by decision type
        limit: Maximum results
    """
    if not knowledge_graph_store:
        raise HTTPException(status_code=501, detail="Knowledge graph not enabled")

    try:
        if agent_name:
            decisions = await knowledge_graph_store.query_agent_decisions(
                agent_name=agent_name,
                limit=limit,
            )
        else:
            decisions = await knowledge_graph_store.query_similar_decisions(
                decision_type=decision_type or "architecture_decision",
                limit=limit,
            )

        return {
            "status": "ok",
            "decisions": decisions,
            "count": len(decisions),
        }

    except Exception as e:
        logger.error("Failed to query knowledge graph: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/graph/patterns")
async def get_graph_patterns(
    repository: str | None = None,
    days: int = 30,
):
    """Analyze decision patterns from the knowledge graph.

    Args:
        repository: Optional repository filter
        days: Days to look back
    """
    if not knowledge_graph_store:
        raise HTTPException(status_code=501, detail="Knowledge graph not enabled")

    try:
        patterns = await knowledge_graph_store.get_decision_patterns(
            repository=repository,
            days=days,
        )

        return {
            "status": "ok",
            "patterns": patterns,
        }

    except Exception as e:
        logger.error("Failed to analyze patterns: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ── Metrics Endpoint (Prometheus) ──


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint for monitoring.

    Returns metrics in Prometheus text format for scraping by Prometheus server.
    """
    from src.metrics import metrics_endpoint

    return await metrics_endpoint()


# ── A2A Protocol Endpoints (Phase 4) ──


@app.get("/.well-known/agent.json")
async def agent_card():
    """A2A Protocol: Agent discovery endpoint.

    Returns the agent card with capabilities and endpoints for
    other agents to discover and interact with this agent.
    """
    if not settings.a2a_enabled:
        raise HTTPException(status_code=501, detail="A2A protocol is not enabled")

    import os

    base_url = os.getenv("AGENT_BASE_URL", "https://cto.afcen.org")
    card = get_digital_cto_agent_card(base_url)

    return card.to_dict()


@app.post("/webhook/a2a")
async def a2a_webhook(request: Request):
    """A2A Protocol: Receive directives from other agents.

    Expected body:
    {
        "directive_id": "...",
        "type": "architecture_query",
        "payload": {...},
        "sender": "jarvis",
        "recipient": "digital_cto"
    }
    """
    if not a2a_handler:
        raise HTTPException(status_code=501, detail="A2A protocol not enabled")

    body = await request.json()

    try:
        directive = await a2a_handler.receive_directive(body)

        # Map A2A type to internal supervisor event type
        mapped_type = a2a_handler.map_directive_type(directive.type)

        # Process the directive through the supervisor
        supervisor_input = {
            "event_type": mapped_type,
            "source": "a2a",
            "payload": directive.payload,
            "routed_to": None,
            "result": None,
            "error": None,
        }

        result = await supervisor_graph.ainvoke(supervisor_input)

        from src.integrations.a2a_handler import A2AResponse

        response = A2AResponse(
            response_to=directive.directive_id,
            status="completed" if not result.get("error") else "failed",
            result=result.get("result"),
            error=result.get("error"),
        )

        return response.to_dict()

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("A2A webhook error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/a2a/discover")
async def a2a_discover(request: Request):
    """Discover other A2A-compatible agents.

    Expected body:
    {
        "endpoints": ["https://jarvis.example.com/.well-known/agent.json"]
    }
    """
    if not a2a_handler:
        raise HTTPException(status_code=501, detail="A2A protocol not enabled")

    body = await request.json()
    endpoints = body.get("endpoints", [])

    if not endpoints:
        raise HTTPException(status_code=400, detail="'endpoints' field required")

    try:
        discovered = await a2a_handler.discover_agents(endpoints)

        return {
            "status": "ok",
            "agents": {
                endpoint: card.to_dict()
                for endpoint, card in discovered.items()
            },
            "count": len(discovered),
        }

    except Exception as e:
        logger.error("A2A discovery failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ── TUI Chat Endpoint ──


_AGENT_HINT_MAP = {
    "Code Review": "pull_request",
    "Sprint": "sprint_query",
    "Arch": "architecture_query",
    "DevOps": "devops_status",
    "Market": "market_status",
    "Meeting": "meeting_status",
    "Coding": "coding_task",
}


async def _classify_chat_intent(message: str) -> str:
    """Use the LLM to classify a chat message into a supervisor event_type.

    Returns one of: pull_request, sprint_query, architecture_query,
    devops_status, market_status, meeting_status, or 'general'.
    """
    from src.llm.utils import get_default_llm

    llm = get_default_llm(temperature=0.0)

    classification_prompt = (
        "Classify the following user message into exactly one category.\n"
        "Reply with ONLY the category name, nothing else.\n\n"
        "Categories:\n"
        "- pull_request: code review, PR review, diff analysis\n"
        "- sprint_query: sprint status, velocity, backlog, tickets, issues\n"
        "- architecture_query: architecture, design, tech debt, technology choice\n"
        "- devops_status: CI/CD, pipeline, deployment, infrastructure, monitoring\n"
        "- market_status: market data, competitors, trends, morning brief\n"
        "- meeting_status: meetings, agenda, action items\n"
        "- coding_task: write code, implement feature, fix bug, generate code, create endpoint, coding agent\n"
        "- general: greetings, broad questions, capabilities, anything else\n\n"
        f"User message: {message}\n\n"
        "Category:"
    )

    try:
        response = await llm.ainvoke([
            {"role": "user", "content": classification_prompt},
        ])
        category = response.content.strip().lower().replace('"', "").replace("'", "")
        valid = {
            "pull_request", "sprint_query", "architecture_query",
            "devops_status", "market_status", "meeting_status",
            "coding_task", "general",
        }
        return category if category in valid else "general"
    except Exception as e:
        logger.warning("Chat intent classification failed: %s", e)
        return "general"


async def _format_agent_result(result: dict, event_type: str) -> str:
    """Format a structured agent result dict into human-readable text."""
    from src.llm.utils import get_default_llm

    # If result is already a string, return it
    if isinstance(result, str):
        return result

    # Use LLM to summarize structured output
    try:
        llm = get_default_llm(temperature=0.7)
        import json
        result_str = json.dumps(result, indent=2, default=str)[:4000]

        response = await llm.ainvoke([
            {"role": "user", "content": (
                "Summarize the following agent result into a clear, concise response "
                "for the user. Use plain text, no markdown.\n\n"
                f"Agent type: {event_type}\n"
                f"Result:\n{result_str}"
            )},
        ])
        return response.content
    except Exception:
        # Fallback: just stringify
        import json
        return json.dumps(result, indent=2, default=str)


@app.post("/api/chat")
async def chat_endpoint(request: Request):
    """Interactive chat endpoint for the TUI.

    Request body:
        {
            "message": "What's our sprint velocity?",
            "agent_hint": "Sprint" | null,
            "conversation_id": "abc123" | null
        }

    Response:
        {
            "response": "Your current sprint velocity is...",
            "agent": "Sprint Planner",
            "event_type": "sprint_query" | null
        }
    """
    body = await request.json()
    message = body.get("message", "").strip()
    agent_hint = body.get("agent_hint")
    # conversation_id reserved for future stateful conversations

    if not message:
        raise HTTPException(status_code=400, detail="'message' field required")

    # Determine event_type (case-insensitive hint matching)
    if agent_hint and agent_hint != "Auto":
        # Build case-insensitive lookup
        hint_lower = {k.lower(): v for k, v in _AGENT_HINT_MAP.items()}
        event_type = hint_lower.get(agent_hint.lower())
        if not event_type:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown agent_hint: {agent_hint}",
            )
    else:
        event_type = await _classify_chat_intent(message)

    # General queries get a direct LLM response (no supervisor routing)
    if event_type == "general":
        from src.llm.utils import get_default_llm

        try:
            llm = get_default_llm(temperature=0.7)
            response = await llm.ainvoke([
                {"role": "system", "content": (
                    "You are the Digital CTO, an AI-powered technical leadership system "
                    "for the Africa Climate Energy Nexus. You coordinate specialized agents "
                    "for code review, sprint planning, architecture, DevOps, market scanning, "
                    "and meeting intelligence. Be concise and helpful."
                )},
                {"role": "user", "content": message},
            ])
            return {
                "response": response.content,
                "agent": "Supervisor",
                "event_type": None,
            }
        except Exception as e:
            logger.error("Chat direct LLM error: %s", e)
            raise HTTPException(status_code=500, detail=f"LLM error: {str(e)[:200]}")

    # Route through supervisor graph
    try:
        supervisor_input = {
            "event_type": event_type,
            "source": "tui_chat",
            "payload": {"message": message},
            "routed_to": None,
            "result": None,
            "error": None,
        }

        result = await supervisor_graph.ainvoke(supervisor_input)

        if result.get("error"):
            raise HTTPException(status_code=500, detail=result["error"])

        agent_name = result.get("routed_to", event_type)
        agent_result = result.get("result", "")

        # Format structured result into readable text
        formatted = await _format_agent_result(agent_result, event_type)

        return {
            "response": formatted,
            "agent": agent_name or "Supervisor",
            "event_type": event_type,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Chat supervisor error: %s", e)
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)[:200]}")
