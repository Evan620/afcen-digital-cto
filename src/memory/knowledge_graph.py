"""Knowledge Graph Store — Apache AGE integration for decision history.

Phase 4: Adds graph-based memory for tracking:
- Agent decisions and relationships
- Pattern discovery across decisions
- Organizational memory

Uses Apache AGE extension on PostgreSQL for graph queries.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

import asyncpg
from sqlalchemy import text

from src.config import settings
from src.memory.postgres_store import PostgresStore

logger = logging.getLogger(__name__)


# ── Input Sanitization Helpers ──

_IDENTIFIER_RE = re.compile(r"^[a-zA-Z0-9_]+$")


def _validate_identifier(value: str) -> str:
    """Validate a Cypher identifier (graph name, label, etc.).

    Only allows alphanumeric characters and underscores.
    Raises ValueError for invalid identifiers.
    """
    if not _IDENTIFIER_RE.match(value):
        raise ValueError(f"Invalid identifier: {value!r}")
    return value


def _sanitize_cypher_value(value: str, max_length: int = 2000) -> str:
    """Sanitize a string value for safe interpolation into Cypher queries.

    Escapes quotes, backslashes, dollar signs, and null bytes.
    Truncates to max_length to prevent oversized payloads.
    """
    value = value[:max_length]
    value = value.replace("\\", "\\\\")
    value = value.replace("'", "\\'")
    value = value.replace('"', '\\"')
    value = value.replace("$$", "\\$\\$")
    value = value.replace("\x00", "")
    return value


# ── Cypher Query Templates ──

# Vertex creation
CREATE_AGENT_VERTEX = """
SELECT ag_catalog.cypher('afcen_knowledge', $$
    MERGE (a:Agent {{name: '{agent_name}', type: '{agent_type}'}})
    SET a.last_seen = timestamp()
    RETURN a
$$) AS (vertex ag_catalog.agtype);
"""

CREATE_DECISION_VERTEX = """
SELECT ag_catalog.cypher('afcen_knowledge', $$
    CREATE (d:Decision {{
        id: '{decision_id}',
        type: '{decision_type}',
        reasoning: $reasoning,
        outcome: $outcome,
        created_at: timestamp(),
        agent_name: '{agent_name}'
    }})
    RETURN d
$$, ${{"reasoning": "{reasoning}", "outcome": "{outcome}"}}) AS (vertex ag_catalog.agtype);
"""

# Edge creation
CREATE_MAKES_EDGE = """
SELECT ag_catalog.cypher('afcen_knowledge', $$
    MATCH (a:Agent {{name: '{agent_name}'}})
    MATCH (d:Decision {{id: '{decision_id}'}})
    MERGE (a)-[:MAKES {{at: timestamp()}}]->(d)
    RETURN a, d
$$) AS (result ag_catalog.agtype);
"""

CREATE_AFFECTS_EDGE = """
SELECT ag_catalog.cypher('afcen_knowledge', $$
    MATCH (d:Decision {{id: '{decision_id}'}})
    MERGE (p:Project {{repo: '{repository}'}})
    MERGE (d)-[:AFFECTS]->(p)
    RETURN d, p
$$) AS (result ag_catalog.agtype);
"""

CREATE_RELATES_TO_EDGE = """
SELECT ag_catalog.cypher('afcen_knowledge', $$
    MATCH (d:Decision {{id: '{decision_id}'}})
    MERGE (i:Issue {{number: {issue_number}, repo: '{repo}'}})
    MERGE (d)-[:RELATES_TO]->(i)
    RETURN d, i
$$) AS (result ag_catalog.agtype);
"""

# Query templates
QUERY_SIMILAR_DECISIONS = """
SELECT ag_catalog.cypher('afcen_knowledge', $$
    MATCH (d:Decision {{type: '{decision_type}'}})
    WHERE d.outcome CONTAINS '{outcome_term}'
    OPTIONAL MATCH (d)-[:MAKES]-(a:Agent)
    OPTIONAL MATCH (d)-[:AFFECTS]->(p:Project)
    RETURN d, a.name as agent_name, p.repo as repository
    ORDER BY d.created_at DESC
    LIMIT {limit}
$$) AS (result ag_catalog.agtype);
"""

QUERY_AGENT_DECISIONS = """
SELECT ag_catalog.cypher('afcen_knowledge', $$
    MATCH (a:Agent {{name: '{agent_name}'}})-[:MAKES]->(d:Decision)
    OPTIONAL MATCH (d)-[:AFFECTS]->(p:Project)
    RETURN d, p.repo as repository
    ORDER BY d.created_at DESC
    LIMIT {limit}
$$) AS (result ag_catalog.agtype);
"""

QUERY_DECISION_PATH = """
SELECT ag_catalog.cypher('afcen_knowledge', $$
    MATCH path = (a:Agent {{name: '{agent_name}'}})-[:MAKES*1..3]->(d:Decision)
    RETURN path
    LIMIT 10
$$) AS (path ag_catalog.agtype);
"""


# ── Knowledge Graph Store Class ──


class KnowledgeGraphStore(PostgresStore):
    """Knowledge graph operations using Apache AGE.

    Extends PostgresStore to add graph database capabilities
    for tracking decisions and their relationships.
    """

    def __init__(self, url: str | None = None) -> None:
        super().__init__(url)
        self.graph_name = settings.knowledge_graph_name

    async def init_graph(self) -> None:
        """Initialize the knowledge graph, creating AGE extension if needed.

        This method has robust error handling for production deployments:
        - Works with or without Apache AGE extension
        - Handles existing graphs gracefully
        - Provides clear logging for troubleshooting
        """
        # First, try to load the AGE extension
        age_loaded = False
        try:
            async with self._engine.begin() as conn:
                # Try to load AGE extension
                await conn.execute(text("LOAD 'age';"))
                logger.info("Apache AGE extension loaded successfully")
                age_loaded = True
        except Exception as e:
            logger.warning(
                "Apache AGE extension not available: %s. "
                "Knowledge graph features will be limited. "
                "Install AGE for full decision tracking capabilities.",
                e,
            )
            # Continue without graph functionality
            return

        if not age_loaded:
            return

        # Now try to create/use the graph
        try:
            async with self._engine.begin() as conn:
                # Check if graph exists
                result = await conn.execute(text(
                    f"SELECT graphname FROM ag_graph WHERE graphname = '{self.graph_name}'"
                ))

                if result.rowcount == 0:
                    # Create the graph
                    await conn.execute(text(
                        f"SELECT ag_catalog.create_graph('{self.graph_name}');"
                    ))
                    logger.info(f"Created knowledge graph: {self.graph_name}")
                else:
                    logger.info(f"Knowledge graph {self.graph_name} already exists")

        except Exception as e:
            # Graph might already exist or other benign errors
            error_str = str(e).lower()
            if "already exists" in error_str:
                logger.info(f"Knowledge graph '{self.graph_name}' already exists")
            else:
                logger.warning(f"Failed to initialize knowledge graph: {e}")

    async def log_decision_to_graph(
        self,
        agent_name: str,
        decision_type: str,
        reasoning: str,
        outcome: str,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Store a decision in the knowledge graph with relationships.

        Args:
            agent_name: Name of the agent making the decision
            decision_type: Type of decision
            reasoning: Reasoning behind the decision
            outcome: Result of the decision
            context: Additional context (repository, issue, etc.)

        Returns:
            The decision ID
        """
        context = context or {}

        # Sanitize all inputs
        safe_agent = _sanitize_cypher_value(agent_name, 200)
        safe_type = _sanitize_cypher_value(decision_type, 200)
        safe_reasoning = _sanitize_cypher_value(reasoning, 1000)
        safe_outcome = _sanitize_cypher_value(outcome, 1000)
        graph = _validate_identifier(self.graph_name)

        decision_id = f"{safe_agent}_{safe_type}_{datetime.utcnow().timestamp()}"

        try:
            async with self._engine.begin() as conn:
                # Create agent vertex
                await conn.execute(text(
                    f"SELECT ag_catalog.cypher('{graph}', $$ "
                    f"MERGE (a:Agent {{name: '{safe_agent}'}}) "
                    f"SET a.last_seen = timestamp() "
                    f"RETURN a $$) AS (vertex ag_catalog.agtype);"
                ))

                # Create decision vertex
                await conn.execute(text(
                    f"SELECT ag_catalog.cypher('{graph}', $$ "
                    f"CREATE (d:Decision {{ "
                    f"id: '{decision_id}', "
                    f"type: '{safe_type}', "
                    f"reasoning: '{safe_reasoning}', "
                    f"outcome: '{safe_outcome}', "
                    f"created_at: timestamp(), "
                    f"agent_name: '{safe_agent}' "
                    f"}}) "
                    f"RETURN d $$) AS (vertex ag_catalog.agtype);"
                ))

                # Create MAKES edge
                await conn.execute(text(
                    f"SELECT ag_catalog.cypher('{graph}', $$ "
                    f"MATCH (a:Agent {{name: '{safe_agent}'}}) "
                    f"MATCH (d:Decision {{id: '{decision_id}'}}) "
                    f"MERGE (a)-[:MAKES {{at: timestamp()}}]->(d) "
                    f"RETURN a, d $$) AS (result ag_catalog.agtype);"
                ))

                # Create AFFECTS edge if repository in context
                if repository := context.get("repository"):
                    safe_repo = _sanitize_cypher_value(str(repository), 500)
                    await conn.execute(text(
                        f"SELECT ag_catalog.cypher('{graph}', $$ "
                        f"MATCH (d:Decision {{id: '{decision_id}'}}) "
                        f"MERGE (p:Project {{repo: '{safe_repo}'}}) "
                        f"MERGE (d)-[:AFFECTS]->(p) "
                        f"RETURN d, p $$) AS (result ag_catalog.agtype);"
                    ))

                # Create RELATES_TO edge if issue/PR in context
                if issue_number := context.get("issue_number") or context.get("pr_number"):
                    safe_issue = int(issue_number)  # ensure integer
                    safe_repo = _sanitize_cypher_value(
                        str(context.get("repository", "unknown")), 500,
                    )
                    await conn.execute(text(
                        f"SELECT ag_catalog.cypher('{graph}', $$ "
                        f"MATCH (d:Decision {{id: '{decision_id}'}}) "
                        f"MERGE (i:Issue {{number: {safe_issue}, repo: '{safe_repo}'}}) "
                        f"MERGE (d)-[:RELATES_TO]->(i) "
                        f"RETURN d, i $$) AS (result ag_catalog.agtype);"
                    ))

            logger.info(
                "Logged decision to graph: %s by %s",
                decision_id,
                agent_name,
            )
            return decision_id

        except Exception as e:
            logger.error("Failed to log decision to graph: %s", e)
            raise

    async def query_similar_decisions(
        self,
        decision_type: str,
        context: dict[str, Any] | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Find similar historical decisions for context.

        Args:
            decision_type: Type of decision to search for
            context: Context for matching (repository, etc.)
            limit: Maximum results to return

        Returns:
            List of similar decisions with metadata
        """
        context = context or {}
        results = []
        safe_type = _sanitize_cypher_value(decision_type, 200)
        graph = _validate_identifier(self.graph_name)
        safe_limit = max(1, min(int(limit), 100))

        try:
            async with self._engine.begin() as conn:
                where_clauses = [f"d.type = '{safe_type}'"]
                if repository := context.get("repository"):
                    safe_repo = _sanitize_cypher_value(str(repository), 500)
                    where_clauses.append(f"p.repo = '{safe_repo}'")

                where_clause = " AND ".join(where_clauses)

                query = f"""
                SELECT ag_catalog.cypher('{graph}', $$
                    MATCH (d:Decision)
                    WHERE {where_clause}
                    OPTIONAL MATCH (d)-[:MAKES]-(a:Agent)
                    OPTIONAL MATCH (d)-[:AFFECTS]->(p:Project)
                    RETURN d, a.name as agent_name, p.repo as repository
                    ORDER BY d.created_at DESC
                    LIMIT {safe_limit}
                $$) AS (result ag_catalog.agtype);
                """

                result_set = await conn.execute(text(query))
                rows = result_set.fetchall()

                for row in rows:
                    if row[0]:
                        results.append({
                            "decision_id": row[0].get("id", "unknown"),
                            "type": row[0].get("type", ""),
                            "reasoning": row[0].get("reasoning", ""),
                            "outcome": row[0].get("outcome", ""),
                            "created_at": row[0].get("created_at", ""),
                        })

        except Exception as e:
            logger.warning("Failed to query similar decisions: %s", e)

        return results

    async def query_agent_decisions(
        self,
        agent_name: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get recent decisions by a specific agent.

        Args:
            agent_name: Name of the agent
            limit: Maximum results

        Returns:
            List of decisions by the agent
        """
        results = []
        safe_agent = _sanitize_cypher_value(agent_name, 200)
        graph = _validate_identifier(self.graph_name)
        safe_limit = max(1, min(int(limit), 100))

        try:
            async with self._engine.begin() as conn:
                query = f"""
                SELECT ag_catalog.cypher('{graph}', $$
                    MATCH (a:Agent {{name: '{safe_agent}'}})-[:MAKES]->(d:Decision)
                    OPTIONAL MATCH (d)-[:AFFECTS]->(p:Project)
                    RETURN d, p.repo as repository
                    ORDER BY d.created_at DESC
                    LIMIT {safe_limit}
                $$) AS (result ag_catalog.agtype);
                """

                result_set = await conn.execute(text(query))
                rows = result_set.fetchall()

                for row in rows:
                    if row[0]:
                        results.append({
                            "decision_id": row[0].get("id", "unknown"),
                            "type": row[0].get("type", ""),
                            "reasoning": row[0].get("reasoning", ""),
                            "outcome": row[0].get("outcome", ""),
                            "repository": row[1] if len(row) > 1 else None,
                        })

        except Exception as e:
            logger.warning("Failed to query agent decisions: %s", e)

        return results

    async def get_decision_patterns(
        self,
        repository: str | None = None,
        days: int = 30,
    ) -> dict[str, Any]:
        """Analyze decision patterns for insights.

        Args:
            repository: Optional repository filter
            days: Days to look back

        Returns:
            Dictionary with pattern analysis
        """
        graph = _validate_identifier(self.graph_name)
        safe_days = max(1, min(int(days), 365))
        patterns: dict[str, Any] = {
            "total_decisions": 0,
            "by_agent": {},
            "by_type": {},
            "success_rate": 0.0,
        }

        try:
            async with self._engine.begin() as conn:
                # Count decisions by agent
                query = f"""
                SELECT ag_catalog.cypher('{graph}', $$
                    MATCH (a:Agent)-[:MAKES]->(d:Decision)
                    RETURN a.name as agent, count(d) as count
                $$) AS (agent ag_catalog.agtype, count ag_catalog.agtype);
                """

                result_set = await conn.execute(text(query))
                rows = result_set.fetchall()

                total = 0
                for row in rows:
                    try:
                        agent_name = str(row[0]).strip('"')
                        count = int(str(row[1]))
                        patterns["by_agent"][agent_name] = count
                        total += count
                    except (ValueError, TypeError, IndexError):
                        continue
                patterns["total_decisions"] = total

                # Count decisions by type
                type_query = f"""
                SELECT ag_catalog.cypher('{graph}', $$
                    MATCH (d:Decision)
                    RETURN d.type as type, count(d) as count
                $$) AS (type ag_catalog.agtype, count ag_catalog.agtype);
                """

                result_set = await conn.execute(text(type_query))
                rows = result_set.fetchall()

                for row in rows:
                    try:
                        dtype = str(row[0]).strip('"')
                        count = int(str(row[1]))
                        patterns["by_type"][dtype] = count
                    except (ValueError, TypeError, IndexError):
                        continue

                # Calculate success rate (decisions with positive outcome keywords)
                if total > 0:
                    success_query = f"""
                    SELECT ag_catalog.cypher('{graph}', $$
                        MATCH (d:Decision)
                        WHERE d.outcome CONTAINS 'APPROVE'
                           OR d.outcome CONTAINS 'success'
                           OR d.outcome CONTAINS 'passed'
                        RETURN count(d) as success_count
                    $$) AS (count ag_catalog.agtype);
                    """

                    result_set = await conn.execute(text(success_query))
                    row = result_set.fetchone()
                    if row:
                        try:
                            success_count = int(str(row[0]))
                            patterns["success_rate"] = round(
                                success_count / total, 3,
                            )
                        except (ValueError, TypeError):
                            pass

        except Exception as e:
            logger.warning("Failed to analyze decision patterns: %s", e)

        return patterns

    async def health_check(self) -> bool:
        """Check if the knowledge graph is healthy."""
        try:
            graph = _validate_identifier(self.graph_name)
            async with self._engine.begin() as conn:
                await conn.execute(text(
                    f"SELECT ag_catalog.cypher('{graph}', $$"
                    "MATCH (n) RETURN count(n) LIMIT 1 $$) AS (count ag_catalog.agtype);"
                ))
            return True
        except Exception:
            return False


# ── Singleton instance ──

_kg_store: KnowledgeGraphStore | None = None


def get_knowledge_graph() -> KnowledgeGraphStore:
    """Get the singleton knowledge graph store."""
    global _kg_store
    if _kg_store is None:
        _kg_store = KnowledgeGraphStore()
    return _kg_store
