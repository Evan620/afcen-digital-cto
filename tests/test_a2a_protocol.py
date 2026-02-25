"""Tests for the A2A Protocol Handler (Phase 4)."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.integrations.a2a_handler import (
    AgentCard,
    A2ADirective,
    A2AResponse,
    A2AProtocolHandler,
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

        # Phase 4 additions
        assert "code_generation" in card.capabilities  # Check for exact string

        # Existing capabilities
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
