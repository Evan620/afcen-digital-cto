"""OpenClaw Gateway client for JARVIS communication.

This client connects to the OpenClaw Gateway running on the Mac mini
and enables the Digital CTO to communicate with JARVIS via WebSocket.

Architecture:
- OpenClaw Gateway: Mac mini at 100.125.211.92:18789 (tailnet)
- Digital CTO: Docker container or local dev
- Communication: WebSocket for real-time, HTTP for health checks

Protocol: https://docs.openclaw.ai/gateway/protocol

Phase 2: JARVIS Integration
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

import httpx
import websockets
from pydantic import BaseModel
from websockets.asyncio.client import ClientConnection

from src.config import settings

logger = logging.getLogger(__name__)


# ── Message Models ──


class OpenClawRequest(BaseModel):
    """Request frame for OpenClaw WebSocket protocol."""

    type: str = "req"
    id: str
    method: str
    params: dict[str, Any]


class OpenClawResponse(BaseModel):
    """Response frame from OpenClaw WebSocket."""

    type: str
    id: str | None = None
    ok: bool = True
    payload: dict[str, Any] | None = None
    error: str | dict[str, Any] | None = None


class OpenClawEvent(BaseModel):
    """Event frame from OpenClaw WebSocket."""

    type: str = "event"
    event: str
    payload: dict[str, Any]
    seq: int | None = None


class JARVISResponse(BaseModel):
    """Response from JARVIS."""

    success: bool
    message: str
    data: dict[str, Any] = {}
    suggested_actions: list[str] = []


# ── OpenClaw Client ──


class OpenClawClient:
    """Client for communicating with OpenClaw Gateway and JARVIS.

    Uses WebSocket for real-time bidirectional communication.
    Falls back to HTTP for health checks and simple queries.
    """

    def __init__(
        self,
        gateway_url: str | None = None,
        node_id: str = "digital_cto",
        gateway_token: str | None = None,
    ) -> None:
        self._gateway_url = gateway_url or settings.openclaw_gateway_url
        self._ws_url = self._gateway_url.replace("http://", "ws://").replace("https://", "wss://")
        self._node_id = node_id
        self._gateway_token = gateway_token or settings.openclaw_gateway_token
        self._device_token: str | None = None

        # HTTP client for health checks
        self._http_client: httpx.AsyncClient | None = None

        # WebSocket state
        self._ws: ClientConnection | None = None
        self._ws_connected = False
        self._ws_task: asyncio.Task | None = None
        self._receive_task: asyncio.Task | None = None

        # Request/response correlation
        self._pending_requests: dict[str, asyncio.Future[OpenClawResponse]] = {}
        self._message_handlers: dict[str, Callable] = {}

    @property
    def http_client(self) -> httpx.AsyncClient:
        """Lazy-init HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    @property
    def is_connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self._ws_connected and self._ws is not None

    # ── Lifecycle ──

    async def connect(self) -> bool:
        """Connect to OpenClaw Gateway via WebSocket.

        Uses gateway token auth (no device signing required when
        gateway.remote.token is configured on the gateway).
        """
        if self._ws_connected:
            return True

        try:
            logger.info("Connecting to OpenClaw Gateway: %s", self._ws_url)
            self._ws = await websockets.connect(
                self._ws_url,
                additional_headers={"User-Agent": f"digital-cto/1.0 ({self._node_id})"},
            )

            # Wait for challenge
            challenge = await asyncio.wait_for(self._ws.recv(), timeout=10.0)
            challenge_data = json.loads(challenge)

            if challenge_data.get("event") != "connect.challenge":
                logger.error("Expected connect.challenge, got: %s", challenge_data)
                await self._ws.close()
                self._ws = None
                return False

            # Send connect request with token auth
            connect_params = {
                "minProtocol": 3,
                "maxProtocol": 3,
                "client": {
                    "id": "cli",
                    "version": "1.0.0",
                    "platform": "docker" if settings.environment == "production" else "dev",
                    "mode": "cli",
                },
                "role": "operator",
                "scopes": ["operator.read", "operator.write", "operator.admin"],
                "caps": [],
                "commands": [],
                "permissions": {},
                "locale": "en-US",
                "userAgent": f"digital-cto/1.0 ({self._node_id})",
            }

            # Add auth token (required)
            if self._gateway_token:
                connect_params["auth"] = {"token": self._gateway_token}

            request = OpenClawRequest(
                id=str(uuid.uuid4()),
                method="connect",
                params=connect_params,
            )

            await self._ws.send(request.model_dump_json())

            # Wait for response
            response = await asyncio.wait_for(self._ws.recv(), timeout=10.0)
            response_data = json.loads(response)

            if response_data.get("ok"):
                self._ws_connected = True
                payload = response_data.get("payload", {})
                logger.info(
                    "Connected to OpenClaw Gateway (protocol %s)",
                    payload.get("protocol", "unknown"),
                )

                # Store device token if provided
                if "auth" in payload and "deviceToken" in payload["auth"]:
                    self._device_token = payload["auth"]["deviceToken"]
                    logger.debug("Received device token from gateway")

                # Start receive loop
                self._receive_task = asyncio.create_task(self._receive_loop())
                return True
            else:
                error = response_data.get("error", "Unknown error")
                logger.error("OpenClaw connection failed: %s", error)
                await self._ws.close()
                self._ws = None
                return False

        except asyncio.TimeoutError:
            logger.error("OpenClaw connection timed out")
            if self._ws:
                await self._ws.close()
                self._ws = None
            return False
        except Exception as e:
            logger.error("Failed to connect to OpenClaw Gateway: %s", e)
            if self._ws:
                await self._ws.close()
                self._ws = None
            return False

    async def disconnect(self) -> None:
        """Disconnect from OpenClaw Gateway."""
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
            self._receive_task = None

        if self._ws:
            await self._ws.close()
            self._ws = None

        self._ws_connected = False
        logger.info("Disconnected from OpenClaw Gateway")

    async def close(self) -> None:
        """Close all connections."""
        await self.disconnect()
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    # ── WebSocket Receive Loop ──

    async def _receive_loop(self) -> None:
        """Background task to receive messages from WebSocket."""
        try:
            while self._ws and self._ws_connected:
                try:
                    message = await self._ws.recv()
                    data = json.loads(message)

                    if data.get("type") == "res":
                        # Response to a request
                        request_id = data.get("id")
                        if request_id and request_id in self._pending_requests:
                            future = self._pending_requests.pop(request_id)
                            if not future.done():
                                future.set_result(OpenClawResponse(**data))

                    elif data.get("type") == "event":
                        # Async event from gateway
                        event = data.get("event", "")
                        handler = self._message_handlers.get(event)
                        if handler:
                            try:
                                await handler(OpenClawEvent(**data))
                            except Exception as e:
                                logger.error("Event handler error for %s: %s", event, e)

                except websockets.ConnectionClosed:
                    logger.warning("OpenClaw WebSocket connection closed")
                    self._ws_connected = False
                    break
                except json.JSONDecodeError as e:
                    logger.error("Failed to decode WebSocket message: %s", e)
                except Exception as e:
                    logger.error("Error in receive loop: %s", e)

        except asyncio.CancelledError:
            pass
        finally:
            self._ws_connected = False

    # ── Health Check (HTTP) ──

    async def health_check(self) -> bool:
        """Check if OpenClaw Gateway is reachable via HTTP."""
        try:
            resp = await self.http_client.get(f"{self._gateway_url}/health", timeout=5.0)
            return resp.status_code == 200
        except Exception as e:
            logger.warning("OpenClaw Gateway health check failed: %s", e)
            return False

    # ── WebSocket RPC Methods ──

    async def call(
        self,
        method: str,
        params: dict[str, Any],
        timeout: float = 30.0,
    ) -> OpenClawResponse:
        """Call a method on the OpenClaw Gateway.

        Args:
            method: RPC method name
            params: Method parameters
            timeout: Response timeout in seconds

        Returns:
            Response from gateway
        """
        if not self.is_connected:
            connected = await self.connect()
            if not connected:
                return OpenClawResponse(
                    type="res",
                    ok=False,
                    error="Not connected to OpenClaw Gateway",
                )

        request_id = str(uuid.uuid4())
        request = OpenClawRequest(
            id=request_id,
            method=method,
            params=params,
        )

        # Create future for response
        future: asyncio.Future[OpenClawResponse] = asyncio.get_event_loop().create_future()
        self._pending_requests[request_id] = future

        try:
            await self._ws.send(request.model_dump_json())

            # Wait for response
            response = await asyncio.wait_for(future, timeout=timeout)
            return response

        except asyncio.TimeoutError:
            self._pending_requests.pop(request_id, None)
            return OpenClawResponse(
                type="res",
                id=request_id,
                ok=False,
                error=f"Request timed out after {timeout}s",
            )
        except Exception as e:
            self._pending_requests.pop(request_id, None)
            return OpenClawResponse(
                type="res",
                id=request_id,
                ok=False,
                error=str(e),
            )

    # ── JARVIS Communication ──

    async def send_agent_message(
        self,
        recipient: str,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> JARVISResponse:
        """Send a message to JARVIS or another agent.

        Args:
            recipient: Target agent (e.g., "jarvis")
            message: Natural language message
            context: Additional context

        Returns:
            JARVIS response
        """
        response = await self.call(
            "agent.message",
            {
                "recipient": recipient,
                "message": message,
                "context": context or {},
                "sender": self._node_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        if response.ok and response.payload:
            return JARVISResponse(
                success=True,
                message=response.payload.get("message", ""),
                data=response.payload.get("data", {}),
                suggested_actions=response.payload.get("suggested_actions", []),
            )
        else:
            return JARVISResponse(
                success=False,
                message=response.error or "Failed to send message",
            )

    async def query_jarvis(
        self,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> JARVISResponse:
        """Send a natural language query to JARVIS.

        Args:
            query: Natural language query
            context: Additional context for the query

        Returns:
            JARVIS response
        """
        return await self.send_agent_message("jarvis", query, context)

    async def notify_sprint_update(self, sprint_data: dict[str, Any]) -> bool:
        """Notify JARVIS of a sprint status update.

        Args:
            sprint_data: Sprint metrics and status

        Returns:
            True if notification was successful
        """
        response = await self.call(
            "agent.notify",
            {
                "recipient": "jarvis",
                "notification_type": "sprint_update",
                "data": sprint_data,
                "sender": self._node_id,
            },
        )
        return response.ok

    async def request_approval(
        self,
        title: str,
        description: str,
        urgency: str = "normal",
        actions: list[str] | None = None,
    ) -> dict[str, Any]:
        """Request human-in-the-loop approval via JARVIS.

        Args:
            title: Approval request title
            description: Detailed description
            urgency: "low", "normal", "high", "urgent"
            actions: Available actions for approval

        Returns:
            Approval request result
        """
        response = await self.call(
            "agent.approval.request",
            {
                "recipient": "jarvis",
                "title": title,
                "description": description,
                "urgency": urgency,
                "actions": actions or ["approve", "reject", "defer"],
                "requester": self._node_id,
            },
        )

        if response.ok and response.payload:
            return response.payload
        return {"success": False, "error": response.error}

    # ── Event Handlers ──

    def on_event(self, event_name: str, handler: Callable[[OpenClawEvent], Any]) -> None:
        """Register a handler for a specific event type.

        Args:
            event_name: Event name (e.g., "agent.message", "exec.approval.requested")
            handler: Async or sync function to handle the event
        """
        self._message_handlers[event_name] = handler

    def on_jarvis_message(self, handler: Callable[[dict[str, Any]], Any]) -> None:
        """Register handler for messages from JARVIS."""
        async def wrapper(event: OpenClawEvent) -> None:
            if event.payload:
                await handler(event.payload)

        self._message_handlers["agent.message"] = wrapper

    # ── Agent Registration ──

    async def register_agent(
        self,
        agent_name: str,
        capabilities: list[str],
        endpoints: dict[str, str],
    ) -> bool:
        """Register this agent with the OpenClaw Gateway.

        Args:
            agent_name: Name of the agent
            capabilities: List of agent capabilities
            endpoints: Available HTTP endpoints

        Returns:
            True if registration successful
        """
        response = await self.call(
            "agent.register",
            {
                "agent_id": self._node_id,
                "agent_name": agent_name,
                "capabilities": capabilities,
                "endpoints": endpoints,
                "status": "online",
            },
        )

        if response.ok:
            logger.info("Registered %s with OpenClaw Gateway", agent_name)
        else:
            logger.error("Failed to register with OpenClaw Gateway: %s", response.error)

        return response.ok


# ── Global Client Instance ──

_openclaw_client: OpenClawClient | None = None


def get_openclaw_client() -> OpenClawClient:
    """Get or create the global OpenClaw client instance."""
    global _openclaw_client
    if _openclaw_client is None:
        _openclaw_client = OpenClawClient()
    return _openclaw_client
