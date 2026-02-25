"""JARVIS Directive Handler — processes directives from the CEO agent.

Maps JARVIS directive types to supervisor event_types and routes them
through the LangGraph supervisor graph. Provides HTTP fallback for
when WebSocket is unavailable.

Framework only — no live gateway testing required.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from src.models.schemas import (
    CTOResponse,
    CTOResponseStatus,
    JarvisDirective,
    JarvisDirectiveType,
)

logger = logging.getLogger(__name__)

# Map directive types to supervisor event_types
DIRECTIVE_TO_EVENT: dict[str, str] = {
    JarvisDirectiveType.SPRINT_REPORT.value: "sprint_report",
    JarvisDirectiveType.REVIEW_PR.value: "pull_request",
    JarvisDirectiveType.TRACK_BAYES.value: "bayes_tracking",
    JarvisDirectiveType.ARCHITECTURE_QUERY.value: "architecture_query",
    JarvisDirectiveType.DEVOPS_STATUS.value: "devops_status",
    JarvisDirectiveType.GENERAL_QUERY.value: "general_query",
}


class JarvisDirectiveHandler:
    """Handles directives from JARVIS by routing through the supervisor graph."""

    def __init__(self, openclaw_client: Any | None = None) -> None:
        self._openclaw_client = openclaw_client
        self._pending_approvals: dict[str, dict[str, Any]] = {}

    async def handle_directive(self, directive: JarvisDirective) -> CTOResponse:
        """Main entry: parse directive, route through supervisor, return response.

        Args:
            directive: The JARVIS directive to handle

        Returns:
            CTOResponse with the result
        """
        # Assign ID if not set
        if not directive.directive_id:
            directive.directive_id = str(uuid.uuid4())

        logger.info(
            "Handling JARVIS directive: type=%s, id=%s, priority=%s",
            directive.type.value,
            directive.directive_id,
            directive.priority,
        )

        # Handle approval responses separately
        if directive.type == JarvisDirectiveType.APPROVAL_RESPONSE:
            return await self.handle_approval_response(directive)

        # Map to supervisor event type
        event_type = DIRECTIVE_TO_EVENT.get(directive.type.value)
        if not event_type:
            return CTOResponse(
                response_to=directive.directive_id,
                status=CTOResponseStatus.FAILED,
                error=f"Unknown directive type: {directive.type.value}",
            )

        try:
            # Import supervisor graph lazily to avoid circular imports
            from src.supervisor.graph import supervisor_graph

            supervisor_input = {
                "event_type": event_type,
                "source": "jarvis",
                "payload": directive.payload,
                "routed_to": None,
                "result": None,
                "error": None,
            }

            result = await supervisor_graph.ainvoke(supervisor_input)

            if result.get("error"):
                return CTOResponse(
                    response_to=directive.directive_id,
                    status=CTOResponseStatus.FAILED,
                    result=result.get("result") or {},
                    error=result["error"],
                )

            agent_result = result.get("result", {})

            # Check if result needs approval
            if agent_result.get("needs_approval"):
                self._pending_approvals[directive.directive_id] = agent_result
                return CTOResponse(
                    response_to=directive.directive_id,
                    status=CTOResponseStatus.NEEDS_APPROVAL,
                    result=agent_result,
                    approval_request={
                        "title": agent_result.get("approval_title", "Approval Required"),
                        "description": agent_result.get("approval_description", ""),
                        "actions": ["approve", "reject", "defer"],
                    },
                )

            return CTOResponse(
                response_to=directive.directive_id,
                status=CTOResponseStatus.COMPLETED,
                result=agent_result,
            )

        except Exception as e:
            logger.error("Directive handling failed: %s", e)
            return CTOResponse(
                response_to=directive.directive_id,
                status=CTOResponseStatus.FAILED,
                error=str(e),
            )

    async def handle_approval_response(self, directive: JarvisDirective) -> CTOResponse:
        """Handle an approval response from JARVIS."""
        original_id = directive.payload.get("original_directive_id", "")
        action = directive.payload.get("action", "reject")

        if original_id not in self._pending_approvals:
            return CTOResponse(
                response_to=directive.directive_id,
                status=CTOResponseStatus.FAILED,
                error=f"No pending approval found for directive: {original_id}",
            )

        pending = self._pending_approvals.pop(original_id)
        logger.info("Approval response for %s: %s", original_id, action)

        return CTOResponse(
            response_to=directive.directive_id,
            status=CTOResponseStatus.COMPLETED,
            result={
                "original_directive_id": original_id,
                "action": action,
                "resolved": True,
            },
        )

    async def send_response(self, response: CTOResponse) -> bool:
        """Send a CTOResponse back to JARVIS via OpenClaw.

        Returns True if sent successfully, False otherwise.
        """
        if not self._openclaw_client:
            logger.debug("No OpenClaw client — response not sent via WebSocket")
            return False

        try:
            from src.integrations.openclaw_client import OpenClawClient

            client: OpenClawClient = self._openclaw_client
            if not client.is_connected:
                logger.warning("OpenClaw not connected — cannot send response")
                return False

            result = await client.send_agent_message(
                recipient="jarvis",
                message=f"CTO Response [{response.status.value}]: {response.response_to}",
                context={
                    "response_to": response.response_to,
                    "status": response.status.value,
                    "result": response.result,
                    "error": response.error,
                },
            )
            return result.success

        except Exception as e:
            logger.error("Failed to send response via OpenClaw: %s", e)
            return False

    def register_event_handlers(self) -> None:
        """Wire up event handlers on the OpenClaw client for incoming directives."""
        if not self._openclaw_client:
            logger.info("No OpenClaw client — skipping event handler registration")
            return

        async def on_agent_message(event: Any) -> None:
            """Handle incoming agent.message events from JARVIS."""
            payload = event.payload if hasattr(event, "payload") else event
            try:
                directive = JarvisDirective(
                    directive_id=payload.get("directive_id", str(uuid.uuid4())),
                    type=JarvisDirectiveType(payload.get("type", "general_query")),
                    payload=payload.get("payload", {}),
                    priority=payload.get("priority", "normal"),
                    sender=payload.get("sender", "jarvis"),
                )
                response = await self.handle_directive(directive)
                await self.send_response(response)
            except Exception as e:
                logger.error("Failed to handle JARVIS message: %s", e)

        self._openclaw_client.on_event("agent.message", on_agent_message)
        logger.info("JARVIS directive handler event listeners registered")
