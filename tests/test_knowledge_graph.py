"""Tests for the Knowledge Graph (Phase 4)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

from src.memory.knowledge_graph import (
    KnowledgeGraphStore,
    get_knowledge_graph,
    _sanitize_cypher_value,
    _validate_identifier,
)
from src.config import settings


# ── Input Sanitization Tests ──


class TestCypherSanitization:
    """Test Cypher query input sanitization helpers."""

    def test_sanitize_escapes_single_quotes(self):
        assert "\\'" in _sanitize_cypher_value("it's a test")

    def test_sanitize_escapes_double_quotes(self):
        assert '\\"' in _sanitize_cypher_value('say "hello"')

    def test_sanitize_escapes_backslashes(self):
        assert "\\\\" in _sanitize_cypher_value("path\\to\\file")

    def test_sanitize_escapes_dollar_signs(self):
        result = _sanitize_cypher_value("$$injection$$")
        assert "$$" not in result

    def test_sanitize_removes_null_bytes(self):
        result = _sanitize_cypher_value("hello\x00world")
        assert "\x00" not in result
        assert "helloworld" == result

    def test_sanitize_truncates_to_max_length(self):
        long_str = "a" * 5000
        result = _sanitize_cypher_value(long_str, max_length=100)
        assert len(result) == 100

    def test_sanitize_injection_attempt(self):
        """Test that a Cypher injection attempt is neutralized."""
        payload = "'}}) RETURN 1; DROP GRAPH afcen_knowledge CASCADE; // "
        result = _sanitize_cypher_value(payload)
        assert "\\'" in result  # Quotes are escaped

    def test_validate_identifier_valid(self):
        assert _validate_identifier("afcen_knowledge") == "afcen_knowledge"
        assert _validate_identifier("test123") == "test123"

    def test_validate_identifier_invalid(self):
        with pytest.raises(ValueError):
            _validate_identifier("afcen-knowledge")  # hyphens not allowed

        with pytest.raises(ValueError):
            _validate_identifier("graph'; DROP TABLE")

        with pytest.raises(ValueError):
            _validate_identifier("graph name")  # spaces not allowed


# ── Knowledge Graph Store Tests with Mocks ──


@pytest.mark.asyncio
class TestKnowledgeGraphStore:
    """Tests for the Knowledge Graph store with mocked DB."""

    @pytest.fixture
    def kg_store(self):
        """Create a test knowledge graph store."""
        return KnowledgeGraphStore(url=None)

    async def test_kg_store_init(self, kg_store):
        """Test initializing the knowledge graph store."""
        assert kg_store is not None
        assert kg_store.graph_name == settings.knowledge_graph_name

    async def test_log_decision_creates_vertices_and_edges(self):
        """Test log_decision_to_graph creates correct vertices and edges."""
        kg = KnowledgeGraphStore(url=None)

        # Mock the engine on the instance
        mock_conn = AsyncMock()
        mock_engine = MagicMock()
        mock_engine.begin.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_engine.begin.return_value.__aexit__ = AsyncMock(return_value=False)
        kg._engine = mock_engine

        decision_id = await kg.log_decision_to_graph(
            agent_name="code_review",
            decision_type="pr_review",
            reasoning="Found issues in code",
            outcome="REQUEST_CHANGES",
            context={"repository": "afcen/platform", "pr_number": 42},
        )

        assert decision_id is not None
        assert "code_review" in decision_id
        assert "pr_review" in decision_id

        # Should have executed: agent vertex, decision vertex, MAKES edge,
        # AFFECTS edge (repository), RELATES_TO edge (pr_number) = 5 calls
        assert mock_conn.execute.call_count == 5

    async def test_log_decision_without_context(self):
        """Test log_decision with no context (no AFFECTS/RELATES_TO edges)."""
        kg = KnowledgeGraphStore(url=None)

        mock_conn = AsyncMock()
        mock_engine = MagicMock()
        mock_engine.begin.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_engine.begin.return_value.__aexit__ = AsyncMock(return_value=False)
        kg._engine = mock_engine

        decision_id = await kg.log_decision_to_graph(
            agent_name="architecture_advisor",
            decision_type="tech_eval",
            reasoning="Evaluated FastAPI",
            outcome="APPROVED",
        )

        assert decision_id is not None
        # Only: agent vertex, decision vertex, MAKES edge = 3 calls
        assert mock_conn.execute.call_count == 3

    async def test_log_decision_sanitizes_inputs(self):
        """Test that injection payloads are sanitized in log_decision."""
        kg = KnowledgeGraphStore(url=None)

        mock_conn = AsyncMock()
        mock_engine = MagicMock()
        mock_engine.begin.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_engine.begin.return_value.__aexit__ = AsyncMock(return_value=False)
        kg._engine = mock_engine

        # Try injection in agent_name
        decision_id = await kg.log_decision_to_graph(
            agent_name="agent'; DROP GRAPH --",
            decision_type="test",
            reasoning="normal reasoning",
            outcome="normal outcome",
        )

        # Should not raise — injection is sanitized
        assert decision_id is not None

        # Verify the executed queries contain escaped values
        for call_args in mock_conn.execute.call_args_list:
            query_text = str(call_args[0][0].text)
            assert "DROP GRAPH" not in query_text or "\\'" in query_text

    async def test_get_decision_patterns_returns_populated_structure(self):
        """Test get_decision_patterns returns fully populated dict."""
        kg = KnowledgeGraphStore(url=None)

        mock_conn = AsyncMock()
        mock_engine = MagicMock()
        mock_engine.begin.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_engine.begin.return_value.__aexit__ = AsyncMock(return_value=False)
        kg._engine = mock_engine

        # Mock three query results: by_agent, by_type, success_rate
        mock_result_agent = MagicMock()
        mock_result_agent.fetchall.return_value = [
            ('"code_review"', "15"),
            ('"sprint_planner"', "8"),
        ]

        mock_result_type = MagicMock()
        mock_result_type.fetchall.return_value = [
            ('"pr_review"', "12"),
            ('"sprint_query"', "8"),
            ('"tech_eval"', "3"),
        ]

        mock_result_success = MagicMock()
        mock_result_success.fetchone.return_value = ("18",)

        mock_conn.execute = AsyncMock(
            side_effect=[mock_result_agent, mock_result_type, mock_result_success]
        )

        patterns = await kg.get_decision_patterns(repository="afcen/platform", days=30)

        assert patterns["total_decisions"] == 23
        assert patterns["by_agent"]["code_review"] == 15
        assert patterns["by_agent"]["sprint_planner"] == 8
        assert patterns["by_type"]["pr_review"] == 12
        assert patterns["by_type"]["sprint_query"] == 8
        assert patterns["by_type"]["tech_eval"] == 3
        assert patterns["success_rate"] == round(18 / 23, 3)

    async def test_query_similar_decisions_returns_list(self, kg_store):
        """Test querying similar decisions (returns empty list without DB)."""
        results = await kg_store.query_similar_decisions(
            decision_type="architecture_decision",
            limit=10,
        )
        assert isinstance(results, list)

    async def test_query_agent_decisions_returns_list(self, kg_store):
        """Test querying decisions by agent (returns empty list without DB)."""
        results = await kg_store.query_agent_decisions(
            agent_name="architecture_advisor",
            limit=20,
        )
        assert isinstance(results, list)

    async def test_get_decision_patterns_defaults_without_db(self, kg_store):
        """Test get_decision_patterns returns default structure without DB."""
        patterns = await kg_store.get_decision_patterns(
            repository="afcen/platform",
            days=30,
        )
        assert isinstance(patterns, dict)
        assert "total_decisions" in patterns
        assert "by_agent" in patterns
        assert "by_type" in patterns
        assert "success_rate" in patterns


@pytest.mark.asyncio
class TestKnowledgeGraphSingleton:
    """Tests for the knowledge graph singleton."""

    async def test_get_knowledge_graph(self):
        """Test getting the singleton instance."""
        kg = get_knowledge_graph()
        assert kg is not None

        # Should return the same instance
        kg2 = get_knowledge_graph()
        assert kg is kg2


def test_knowledge_graph_config():
    """Test knowledge graph configuration."""
    assert hasattr(settings, "knowledge_graph_enabled")
    assert hasattr(settings, "knowledge_graph_name")
    assert settings.knowledge_graph_name == "afcen_knowledge"


@pytest.mark.asyncio
async def test_kg_health_check():
    """Test knowledge graph health check."""
    kg = KnowledgeGraphStore(url=None)
    result = await kg.health_check()
    assert isinstance(result, bool)
