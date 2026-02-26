"""Tests for the A2A Protocol Handler (Phase 4)."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from src.integrations.a2a_handler import (
    AgentCard,
    A2ADirective,
    A2AResponse,
    A2AProtocolHandler,
    A2A_TYPE_MAP,
    get_digital_cto_agent_card,
)
from src.models.schemas import JarvisDirective, JarvisDirectiveType


@pytest.mark.asyncio
class TestAgentCard:
    """Tests for the AgentCard model."""

    def test_agent_card_creation(self):
        """Test creating an AgentCard."""
        card = AgentCard(
            name="Test Agent",
            version="1.0.0",
            description="A test agent",
            capabilities=["test_capability"],
            contact={
                "api_endpoint": "https://example.com/api",
            },
        )

        assert card.name == "Test Agent"
        assert card.version == "1.0.0"
        assert "test_capability" in card.capabilities

    def test_agent_card_to_dict(self):
        """Test converting AgentCard to dictionary."""
        card = AgentCard(
            name="Test Agent",
            version="1.0.0",
            description="A test agent",
            capabilities=["test_capability"],
            contact={"api_endpoint": "https://example.com/api"},
        )

        card_dict = card.to_dict()

        assert card_dict["type"] == "agent"
        assert card_dict["name"] == "Test Agent"
        assert card_dict["version"] == "1.0.0"
        assert "capabilities" in card_dict


@pytest.mark.asyncio
class TestA2ADirective:
    """Tests for the A2ADirective model."""

    def test_a2a_directive_creation(self):
        """Test creating an A2ADirective."""
        directive = A2ADirective(
            directive_id="test-directive-123",
            type="test_query",
            payload={"key": "value"},
            sender="jarvis",
            recipient="digital_cto",
        )

        assert directive.directive_id == "test-directive-123"
        assert directive.type == "test_query"
        assert directive.sender == "jarvis"
        assert directive.recipient == "digital_cto"

    def test_a2a_directive_to_dict(self):
        """Test converting A2ADirective to dictionary."""
        now = datetime.utcnow()
        directive = A2ADirective(
            directive_id="test-123",
            type="test_query",
            payload={"test": "data"},
            sender="jarvis",
            recipient="digital_cto",
            timestamp=now,
        )

        directive_dict = directive.to_dict()

        assert directive_dict["directive_id"] == "test-123"
        assert directive_dict["type"] == "test_query"
        assert directive_dict["sender"] == "jarvis"
        assert directive_dict["recipient"] == "digital_cto"

    def test_a2a_directive_from_dict(self):
        """Test creating A2ADirective from dictionary."""
        directive_dict = {
            "directive_id": "test-123",
            "type": "test_query",
            "payload": {"test": "data"},
            "sender": "jarvis",
            "recipient": "digital_cto",
            "timestamp": "2026-02-25T10:00:00",
            "priority": "high",
            "requires_response": True,
        }

        directive = A2ADirective.from_dict(directive_dict)

        assert directive.directive_id == "test-123"
        assert directive.type == "test_query"
        assert directive.priority == "high"
        assert directive.requires_response is True


@pytest.mark.asyncio
class TestA2AResponse:
    """Tests for the A2AResponse model."""

    def test_a2a_response_creation(self):
        """Test creating an A2AResponse."""
        response = A2AResponse(
            response_to="directive-123",
            status="completed",
            result={"key": "value"},
        )

        assert response.response_to == "directive-123"
        assert response.status == "completed"
        assert response.result["key"] == "value"

    def test_a2a_response_with_error(self):
        """Test creating an A2AResponse with error."""
        response = A2AResponse(
            response_to="directive-123",
            status="failed",
            error="Something went wrong",
        )

        assert response.status == "failed"
        assert response.error == "Something went wrong"
        assert response.result == {}

    def test_a2a_response_to_dict(self):
        """Test converting A2AResponse to dictionary."""
        response = A2AResponse(
            response_to="directive-123",
            status="completed",
            result={"success": True},
        )

        response_dict = response.to_dict()

        assert response_dict["response_to"] == "directive-123"
        assert response_dict["status"] == "completed"
        assert response_dict["result"]["success"] is True


@pytest.mark.asyncio
class TestA2ADirectiveTypeMapping:
    """Tests for A2A directive type mapping."""

    def test_type_map_contains_expected_types(self):
        """Test that the type map has all expected entries."""
        assert "code_review_request" in A2A_TYPE_MAP
        assert "code_generation" in A2A_TYPE_MAP
        assert "sprint_query" in A2A_TYPE_MAP
        assert "architecture_query" in A2A_TYPE_MAP

    def test_map_code_review_request(self):
        """Test mapping code_review_request -> pull_request."""
        handler = A2AProtocolHandler()
        assert handler.map_directive_type("code_review_request") == "pull_request"

    def test_map_code_generation(self):
        """Test mapping code_generation -> coding_task."""
        handler = A2AProtocolHandler()
        assert handler.map_directive_type("code_generation") == "coding_task"

    def test_map_unknown_type_passthrough(self):
        """Test that unknown types pass through unchanged."""
        handler = A2AProtocolHandler()
        assert handler.map_directive_type("unknown_type") == "unknown_type"

    def test_all_mapped_types_are_strings(self):
        """Test that all mapped types are valid strings."""
        for key, value in A2A_TYPE_MAP.items():
            assert isinstance(key, str)
            assert isinstance(value, str)
            assert len(key) > 0
            assert len(value) > 0


@pytest.mark.asyncio
class TestA2AProtocolHandler:
    """Tests for the A2AProtocolHandler."""

    @pytest.fixture
    def handler(self):
        """Create a test handler."""
        return A2AProtocolHandler(shared_secret="test_secret")

    async def test_handler_init(self):
        """Test initializing the handler."""
        handler = A2AProtocolHandler(shared_secret="test_secret")
        assert handler.shared_secret == "test_secret"
        assert handler.agent_cards == {}

    async def test_receive_directive(self, handler):
        """Test receiving a directive."""
        directive_data = {
            "directive_id": "test-123",
            "type": "test_query",
            "payload": {"test": "data"},
            "sender": "jarvis",
            "recipient": "digital_cto",
        }

        directive = await handler.receive_directive(directive_data)

        assert directive.directive_id == "test-123"
        assert directive.type == "test_query"
        assert directive.sender == "jarvis"

    async def test_receive_directive_missing_field(self, handler):
        """Test receiving a directive with missing required field."""
        directive_data = {
            "directive_id": "test-123",
            "type": "test_query",
            # Missing sender and recipient
        }

        with pytest.raises(ValueError, match="Missing required field"):
            await handler.receive_directive(directive_data)

    async def test_sign_directive(self, handler):
        """Test signing a directive."""
        directive = A2ADirective(
            directive_id="test-123",
            type="test_query",
            payload={"test": "data"},
            sender="digital_cto",
            recipient="jarvis",
        )

        signature = handler._sign_directive(directive)

        assert signature.startswith("sha256=")
        assert len(signature) > 10

    async def test_verify_signature(self, handler):
        """Test verifying a directive signature."""
        directive = A2ADirective(
            directive_id="test-123",
            type="test_query",
            payload={"test": "data"},
            sender="digital_cto",
            recipient="jarvis",
        )

        # Sign the directive
        signature = handler._sign_directive(directive)
        directive.signature = signature

        # Create directive data for verification
        directive_data = directive.to_dict()

        # Verify should succeed
        assert handler._verify_signature(directive_data) is True

    async def test_verify_signature_invalid(self, handler):
        """Test verifying an invalid signature."""
        directive_data = {
            "directive_id": "test-123",
            "type": "test_query",
            "payload": {"test": "data"},
            "sender": "digital_cto",
            "recipient": "jarvis",
            "timestamp": "2026-02-25T10:00:00",
            "priority": "normal",
            "requires_response": True,
            "signature": "sha256=invalid",
        }

        assert handler._verify_signature(directive_data) is False


@pytest.mark.asyncio
class TestA2ASendDirective:
    """Tests for sending directives via A2A protocol."""

    async def test_send_directive_success(self):
        """Test sending a directive successfully."""
        handler = A2AProtocolHandler(shared_secret="test_secret")

        directive = A2ADirective(
            directive_id="send-001",
            type="architecture_query",
            payload={"query": "Evaluate FastAPI"},
            sender="digital_cto",
            recipient="jarvis",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response_to": "send-001",
            "status": "completed",
            "result": {"recommendation": "Use FastAPI"},
        }

        with patch.object(handler.http_client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await handler.send_directive(
                "https://jarvis.example.com",
                directive,
            )

        assert result is not None
        assert result.status == "completed"
        assert result.response_to == "send-001"
        mock_post.assert_called_once()

    async def test_send_directive_failure(self):
        """Test handling send directive failure."""
        handler = A2AProtocolHandler(shared_secret="test_secret")

        directive = A2ADirective(
            directive_id="send-002",
            type="test_query",
            payload={},
            sender="digital_cto",
            recipient="jarvis",
        )

        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch.object(handler.http_client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await handler.send_directive(
                "https://jarvis.example.com",
                directive,
            )

        assert result is None

    async def test_send_directive_network_error(self):
        """Test handling network error when sending directive."""
        handler = A2AProtocolHandler(shared_secret="test_secret")

        directive = A2ADirective(
            directive_id="send-003",
            type="test_query",
            payload={},
            sender="digital_cto",
            recipient="jarvis",
        )

        with patch.object(handler.http_client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.ConnectError("Connection refused")

            result = await handler.send_directive(
                "https://unreachable.example.com",
                directive,
            )

        assert result is None

    async def test_send_directive_to_jarvis_found(self):
        """Test send_directive_to_jarvis when JARVIS is discovered."""
        handler = A2AProtocolHandler(shared_secret="test_secret")

        # Simulate discovered JARVIS agent
        handler.agent_cards["https://jarvis.example.com"] = {
            "name": "JARVIS",
            "version": "1.0",
        }

        directive = A2ADirective(
            directive_id="jarvis-001",
            type="code_review_request",
            payload={"pr": 42},
            sender="digital_cto",
            recipient="jarvis",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response_to": "jarvis-001",
            "status": "completed",
            "result": {},
        }

        with patch.object(handler.http_client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await handler.send_directive_to_jarvis(directive)

        assert result is not None
        assert result.status == "completed"

    async def test_send_directive_to_jarvis_not_found(self):
        """Test send_directive_to_jarvis when no JARVIS endpoint found."""
        handler = A2AProtocolHandler(shared_secret="test_secret")
        handler.agent_cards = {}  # No agents discovered

        directive = A2ADirective(
            directive_id="jarvis-002",
            type="test",
            payload={},
            sender="digital_cto",
            recipient="jarvis",
        )

        with patch("src.integrations.a2a_handler.settings") as mock_settings:
            mock_settings.a2a_known_agents = []

            result = await handler.send_directive_to_jarvis(directive)

        assert result is None


@pytest.mark.asyncio
class TestA2ADiscoverAgents:
    """Tests for agent discovery."""

    async def test_discover_agents_success(self):
        """Test successful agent discovery."""
        handler = A2AProtocolHandler()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "type": "agent",
            "name": "Test Agent",
            "version": "1.0.0",
            "description": "A test agent",
            "capabilities": ["code_review"],
            "contact": {"webhook_url": "https://test.example.com/webhook"},
            "protocols": ["a2a"],
            "authentication": "bearer_token",
        }

        with patch.object(handler.http_client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            discovered = await handler.discover_agents(["https://test.example.com"])

        assert "https://test.example.com" in discovered
        assert discovered["https://test.example.com"].name == "Test Agent"
        assert "code_review" in discovered["https://test.example.com"].capabilities

    async def test_discover_agents_unreachable(self):
        """Test discovery when agent is unreachable."""
        handler = A2AProtocolHandler()

        with patch.object(handler.http_client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.ConnectError("Connection refused")

            discovered = await handler.discover_agents(["https://unreachable.example.com"])

        assert len(discovered) == 0

    async def test_discover_agents_mixed(self):
        """Test discovery with some reachable and some unreachable agents."""
        handler = A2AProtocolHandler()

        mock_success_response = MagicMock()
        mock_success_response.status_code = 200
        mock_success_response.json.return_value = {
            "name": "Agent A",
            "version": "1.0",
            "description": "Reachable",
            "capabilities": [],
            "contact": {},
        }

        async def mock_get(url, **kwargs):
            if "good-agent.example.com" in url:
                return mock_success_response
            raise httpx.ConnectError("Connection refused")

        with patch.object(handler.http_client, "get", side_effect=mock_get):
            discovered = await handler.discover_agents([
                "https://good-agent.example.com",
                "https://down-host.example.com",
            ])

        assert len(discovered) == 1
        assert "https://good-agent.example.com" in discovered


@pytest.mark.asyncio
class TestDigitalCTOAgentCard:
    """Tests for the Digital CTO agent card."""

    def test_get_digital_cto_agent_card(self):
        """Test getting the Digital CTO agent card."""
        card = get_digital_cto_agent_card()

        assert card.name == "AfCEN Digital CTO"
        assert card.version == "0.4.0"
        assert "code_review" in card.capabilities
        assert "code_generation" in card.capabilities  # Phase 4

    def test_agent_card_contact_info(self):
        """Test agent card has correct contact info."""
        base_url = "https://cto.example.com"
        card = get_digital_cto_agent_card(base_url)

        assert card.contact["a2a_endpoint"] == f"{base_url}/.well-known/a2a"
        assert card.contact["api_endpoint"] == f"{base_url}/api/v1"
        assert card.contact["webhook_url"] == f"{base_url}/webhook/a2a"

    def test_agent_card_phase_4_capabilities(self):
        """Test that Phase 4 capabilities are included."""
        card = get_digital_cto_agent_card()

        assert "code_generation" in card.capabilities
        assert "code_review" in card.capabilities
        assert "sprint_planning" in card.capabilities


@pytest.mark.asyncio
class TestA2AIntegration:
    """Integration tests for A2A with JARVIS and other agents."""

    async def test_convert_jarvis_directive_to_a2a(self):
        """Test converting a JARVIS directive to A2A format."""
        jarvis = JarvisDirective(
            directive_id="jarvis-123",
            type=JarvisDirectiveType.ARCHITECTURE_QUERY,
            payload={"query": "Evaluate FastAPI vs Flask"},
            sender="jarvis",
        )

        # Convert to A2A format
        a2a = A2ADirective(
            directive_id=jarvis.directive_id,
            type=jarvis.type.value,
            payload=jarvis.payload,
            sender=jarvis.sender,
            recipient="digital_cto",
            priority=jarvis.priority,
            requires_response=jarvis.requires_response,
        )

        assert a2a.directive_id == "jarvis-123"
        assert a2a.type == "architecture_query"
        assert a2a.payload["query"] == "Evaluate FastAPI vs Flask"


@pytest.mark.asyncio
async def test_a2a_handler_close():
    """Test closing the A2A handler."""
    handler = A2AProtocolHandler()
    await handler.close()
    # Should not raise an exception
