"""PostgreSQL-based episodic memory for the Digital CTO.

Stores long-term records: PR review logs, agent decisions, and audit trails.
Uses SQLAlchemy async with asyncpg.
"""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text, JSON, Enum as SAEnum, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from src.config import settings

logger = logging.getLogger(__name__)


# ── ORM Base ──


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all tables."""
    pass


# ── Tables ──


class ReviewLog(Base):
    """Log of every PR review performed by the Code Review agent."""

    __tablename__ = "review_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    repository = Column(String(255), nullable=False, index=True)
    pr_number = Column(Integer, nullable=False)
    pr_title = Column(String(500), nullable=False)
    pr_author = Column(String(100), nullable=False)
    verdict = Column(String(50), nullable=False)  # APPROVE, REQUEST_CHANGES, COMMENT
    summary = Column(Text, nullable=False)
    comments_json = Column(JSON, default=list)
    security_issues = Column(JSON, default=list)
    deprecated_deps = Column(JSON, default=list)
    reviewed_at = Column(DateTime, default=func.now(), nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)


class AgentDecision(Base):
    """Log of significant decisions made by any agent for audit trail."""

    __tablename__ = "agent_decisions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_name = Column(String(100), nullable=False, index=True)
    decision_type = Column(String(100), nullable=False)
    context = Column(JSON, default=dict)
    reasoning = Column(Text, nullable=False)
    outcome = Column(Text, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)


class PREvent(Base):
    """Raw PR webhook events for replay and debugging."""

    __tablename__ = "pr_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    repository = Column(String(255), nullable=False, index=True)
    pr_number = Column(Integer, nullable=False)
    action = Column(String(50), nullable=False)
    payload = Column(JSON, nullable=False)
    received_at = Column(DateTime, default=func.now(), nullable=False)


# ── Store Class ──


class PostgresStore:
    """Async PostgreSQL client for episodic memory."""

    def __init__(self, url: str | None = None) -> None:
        self._url = url or settings.postgres_url
        self._engine = create_async_engine(self._url, echo=False, pool_size=10, max_overflow=20)
        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)

    async def init_db(self) -> None:
        """Create all tables if they don't exist."""
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("PostgreSQL episodic memory initialized")

    async def disconnect(self) -> None:
        """Dispose of the engine connection pool."""
        await self._engine.dispose()
        logger.info("PostgreSQL connection closed")

    def session(self) -> AsyncSession:
        """Get a new async session."""
        return self._session_factory()

    # ── Review Logs ──

    async def log_review(
        self,
        repository: str,
        pr_number: int,
        pr_title: str,
        pr_author: str,
        verdict: str,
        summary: str,
        comments: list[dict] | None = None,
        security_issues: list[str] | None = None,
        deprecated_deps: list[str] | None = None,
    ) -> int:
        """Persist a code review result and return the log ID."""
        async with self.session() as session:
            log = ReviewLog(
                repository=repository,
                pr_number=pr_number,
                pr_title=pr_title,
                pr_author=pr_author,
                verdict=verdict,
                summary=summary,
                comments_json=comments or [],
                security_issues=security_issues or [],
                deprecated_deps=deprecated_deps or [],
                reviewed_at=datetime.utcnow(),
            )
            session.add(log)
            await session.commit()
            await session.refresh(log)
            logger.info("Review logged: %s PR #%d → %s (id=%d)", repository, pr_number, verdict, log.id)
            return log.id

    async def log_event(self, repository: str, pr_number: int, action: str, payload: dict) -> None:
        """Store a raw PR webhook event for replay/debugging."""
        async with self.session() as session:
            event = PREvent(
                repository=repository,
                pr_number=pr_number,
                action=action,
                payload=payload,
            )
            session.add(event)
            await session.commit()

    async def log_decision(
        self, agent_name: str, decision_type: str, reasoning: str, outcome: str, context: dict | None = None
    ) -> None:
        """Store a significant agent decision for audit trail."""
        async with self.session() as session:
            decision = AgentDecision(
                agent_name=agent_name,
                decision_type=decision_type,
                context=context or {},
                reasoning=reasoning,
                outcome=outcome,
            )
            session.add(decision)
            await session.commit()

    # ── Health ──

    async def health_check(self) -> bool:
        """Return True if PostgreSQL is reachable."""
        try:
            async with self._engine.connect() as conn:
                await conn.execute(func.now())  # simple query
            return True
        except Exception:
            return False
