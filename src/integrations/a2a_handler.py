"""A2A Protocol Handler — Google Agent-to-Agent communication.

Phase 4: Implements Google's Agent-to-Agent protocol for inter-agent
communication, allowing JARVIS and other agents to communicate
with the Digital CTO via a standardized protocol.

Key features:
- Agent discovery via /.well-known/agent.json
- Directive sending/receiving
- Capability negotiation
- Authentication/authorization

Reference: https://agents.google.com/agent-to-agent
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime
from typing import Any

import httpx

from src.config import settings

logger = logging.getLogger(__name__)


# ── Agent Card Model ──


class AgentCard:
    """Agent card for A2A protocol discovery."""

    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        capabilities: list[str],
        contact: dict[str, str],
        protocols: list[str] | None = None,
        authentication: str = "bearer_token",
    ):
        self.name = name
        self.version = version
        self.description = description
        self.capabilities = capabilities
        self.contact = contact
        self.protocols = protocols or ["a2a", "rest"]
        self.authentication = authentication

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "agent",
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "capabilities": self.capabilities,
            "contact": self.contact,
            "protocols": self.protocols,
            "authentication": self.authentication,
        }


# ── A2A Directive Model ──


class A2ADirective:
    """Directive message in A2A protocol format."""

    def __init__(
        self,
        directive_id: str,
        type: str,
        payload: dict[str, Any],
        sender: str,
        recipient: str,
        timestamp: datetime | None = None,
        priority: str = "normal",
        requires_response: bool = True,
        signature: str | None = None,
    ):
        self.directive_id = directive_id
        self.type = type
        self.payload = payload
        self.sender = sender
        self.recipient = recipient
        self.timestamp = timestamp or datetime.utcnow()
        self.priority = priority
        self.requires_response = requires_response
        self.signature = signature

    def to_dict(self) -> dict[str, Any]:
        return {
            "directive_id": self.directive_id,
            "type": self.type,
            "payload": self.payload,
            "sender": self.sender,
            "recipient": self.recipient,
            "timestamp": self.timestamp.isoformat(),
            "priority": self.priority,
            "requires_response": self.requires_response,
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "A2ADirective":
        """Create an A2ADirective from a dictionary."""
        timestamp = None
        if timestamp_str := data.get("timestamp"):
            try:
                timestamp = datetime.fromisoformat(timestamp_str)
            except (ValueError, TypeError):
                pass

        return cls(
            directive_id=data["directive_id"],
            type=data["type"],
            payload=data.get("payload", {}),
            sender=data["sender"],
            recipient=data["recipient"],
            timestamp=timestamp,
            priority=data.get("priority", "normal"),
            requires_response=data.get("requires_response", True),
            signature=data.get("signature"),
        )


class A2AResponse:
    """Response message in A2A protocol format."""

    def __init__(
        self,
        response_to: str,
        status: str,
        result: dict[str, Any] | None = None,
        error: str | None = None,
        timestamp: datetime | None = None,
        sender: str = "digital_cto",
    ):
        self.response_to = response_to
        self.status = status  # completed, failed, in_progress, needs_approval
        self.result = result or {}
        self.error = error
        self.timestamp = timestamp or datetime.utcnow()
        self.sender = sender

    def to_dict(self) -> dict[str, Any]:
        return {
            "response_to": self.response_to,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
            "sender": self.sender,
        }


# ── A2A Protocol Handler ──


# ── A2A Directive Type Routing ──

# Maps A2A directive types to internal supervisor event types
A2A_TYPE_MAP: dict[str, str] = {
    "code_review_request": "pull_request",
    "code_generation": "coding_task",
    "sprint_query": "sprint_query",
    "architecture_query": "architecture_query",
    "devops_status": "devops_status",
    "market_scan": "market_scan",
    "meeting_analysis": "meeting_analysis",
    "health_check": "health_check",
}


class A2AProtocolHandler:
    """Google Agent-to-Agent protocol handler.

    Manages agent discovery, directive sending/receiving, and
    communication with other A2A-compatible agents.
    """

    def __init__(self, shared_secret: str | None = None):
        """Initialize the A2A handler.

        Args:
            shared_secret: Shared secret for signing messages
        """
        self.shared_secret = shared_secret
        self.agent_cards: dict[str, dict[str, Any]] = {}
        self.http_client = httpx.AsyncClient(timeout=30.0)

    def map_directive_type(self, a2a_type: str) -> str:
        """Map an A2A directive type to an internal supervisor event type.

        Falls back to the original type if no mapping exists.
        """
        return A2A_TYPE_MAP.get(a2a_type, a2a_type)

    async def discover_agents(self, endpoints: list[str]) -> dict[str, AgentCard]:
        """Discover agents via their agent cards.

        Args:
            endpoints: List of agent base URLs

        Returns:
            Dictionary mapping endpoint to AgentCard
        """
        discovered = {}

        for endpoint in endpoints:
            try:
                agent_card_url = f"{endpoint}/.well-known/agent.json"
                response = await self.http_client.get(agent_card_url)

                if response.status_code == 200:
                    card_data = response.json()
                    self.agent_cards[endpoint] = card_data
                    discovered[endpoint] = AgentCard(
                        name=card_data.get("name", "Unknown"),
                        version=card_data.get("version", "0.0.0"),
                        description=card_data.get("description", ""),
                        capabilities=card_data.get("capabilities", []),
                        contact=card_data.get("contact", {}),
                        protocols=card_data.get("protocols", []),
                        authentication=card_data.get("authentication", "bearer_token"),
                    )
                    logger.info("Discovered agent: %s at %s", card_data.get("name"), endpoint)

            except Exception as e:
                logger.warning("Failed to discover agent at %s: %s", endpoint, e)

        return discovered

    async def receive_directive(self, directive_data: dict[str, Any]) -> A2ADirective:
        """Receive and validate a directive via A2A protocol.

        Args:
            directive_data: Raw directive data

        Returns:
            Parsed A2ADirective

        Raises:
            ValueError: If directive is invalid
        """
        # Validate required fields
        required_fields = ["directive_id", "type", "sender", "recipient"]
        for field in required_fields:
            if field not in directive_data:
                raise ValueError(f"Missing required field: {field}")

        # Verify signature if shared secret is configured
        if self.shared_secret and directive_data.get("signature"):
            if not self._verify_signature(directive_data):
                raise ValueError("Invalid directive signature")

        directive = A2ADirective.from_dict(directive_data)

        logger.info(
            "Received A2A directive %s from %s: type=%s",
            directive.directive_id,
            directive.sender,
            directive.type,
        )

        return directive

    async def send_directive(
        self,
        recipient_endpoint: str,
        directive: A2ADirective,
        api_key: str | None = None,
    ) -> A2AResponse | None:
        """Send a directive to another agent via A2A protocol.

        Args:
            recipient_endpoint: Recipient's A2A endpoint
            directive: Directive to send
            api_key: Optional API key for authentication

        Returns:
            A2AResponse if successful, None otherwise
        """
        # Sign the directive
        if self.shared_secret:
            directive.signature = self._sign_directive(directive)

        # Prepare request
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            response = await self.http_client.post(
                f"{recipient_endpoint}/webhook/a2a",
                json=directive.to_dict(),
                headers=headers,
            )

            if response.status_code == 200:
                response_data = response.json()
                return A2AResponse(
                    response_to=response_data.get("response_to", ""),
                    status=response_data.get("status", "failed"),
                    result=response_data.get("result"),
                    error=response_data.get("error"),
                )
            else:
                logger.error(
                    "Failed to send directive to %s: status=%d",
                    recipient_endpoint,
                    response.status_code,
                )
                return None

        except Exception as e:
            logger.error("Error sending directive to %s: %s", recipient_endpoint, e)
            return None

    async def send_directive_to_jarvis(
        self,
        directive: A2ADirective,
    ) -> A2AResponse | None:
        """Send a directive to JARVIS via A2A protocol.

        Searches discovered agent cards and a2a_known_agents config
        for a JARVIS endpoint and sends the directive.

        Args:
            directive: Directive to send

        Returns:
            A2AResponse if successful, None otherwise
        """
        jarvis_endpoint = None

        # Search discovered agent cards for JARVIS
        for endpoint, card_data in self.agent_cards.items():
            name = card_data.get("name", "").lower()
            if "jarvis" in name:
                jarvis_endpoint = endpoint
                break

        # Fall back to known agents config
        if not jarvis_endpoint:
            for endpoint in settings.a2a_known_agents:
                if "jarvis" in endpoint.lower():
                    jarvis_endpoint = endpoint
                    break

        if not jarvis_endpoint:
            logger.warning("No JARVIS endpoint found for A2A directive")
            return None

        logger.info("Sending A2A directive to JARVIS at %s", jarvis_endpoint)
        return await self.send_directive(jarvis_endpoint, directive)

    def _sign_directive(self, directive: A2ADirective) -> str:
        """Sign a directive with HMAC."""
        if not self.shared_secret:
            return ""

        # Create payload for signing - match to_dict() format
        payload_str = json.dumps(directive.to_dict(), sort_keys=True)

        # Remove signature field from payload for signing
        payload_obj = json.loads(payload_str)
        payload_obj.pop("signature", None)
        payload_str = json.dumps(payload_obj, sort_keys=True)

        signature = hmac.new(
            self.shared_secret.encode(),
            payload_str.encode(),
            hashlib.sha256,
        ).hexdigest()

        return f"sha256={signature}"

    def _verify_signature(self, directive_data: dict[str, Any]) -> bool:
        """Verify a directive's signature."""
        signature = directive_data.get("signature", "")
        if not signature.startswith("sha256="):
            return False

        expected_sig = signature.split("=", 1)[1]

        # Recreate payload - match to_dict() format
        payload_data = {k: v for k, v in directive_data.items() if k != "signature"}
        payload_str = json.dumps(payload_data, sort_keys=True)

        computed_sig = hmac.new(
            self.shared_secret.encode(),
            payload_str.encode(),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(computed_sig, expected_sig)

    async def close(self):
        """Close the HTTP client."""
        await self.http_client.aclose()


# ── Digital CTO Agent Card ──


def get_digital_cto_agent_card(base_url: str = "https://cto.afcen.org") -> AgentCard:
    """Get the Digital CTO's agent card for A2A discovery.

    Args:
        base_url: Base URL for the Digital CTO API

    Returns:
        AgentCard with Digital CTO's capabilities
    """
    return AgentCard(
        name="AfCEN Digital CTO",
        version="0.4.0",
        description="AI-powered multi-agent technical leadership system",
        capabilities=[
            "code_review",
            "sprint_planning",
            "bayes_tracking",
            "metrics_reporting",
            "architecture_advisory",
            "devops_monitoring",
            "market_intelligence",
            "morning_briefs",
            "meeting_intelligence",
            "code_generation",  # Phase 4
        ],
        contact={
            "a2a_endpoint": f"{base_url}/.well-known/a2a",
            "api_endpoint": f"{base_url}/api/v1",
            "webhook_url": f"{base_url}/webhook/a2a",
            "health": f"{base_url}/health",
        },
        protocols=["a2a", "rest", "websocket"],
        authentication="bearer_token",
    )
