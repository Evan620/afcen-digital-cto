"""Tests for the JARVIS directive handler."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from src.models.schemas import (
    CTOResponse,
    CTOResponseStatus,
    JarvisDirective,
    JarvisDirectiveType,
)
from src.integrations.jarvis_handler import (
    JarvisDirectiveHandler,
    DIRECTIVE_TO_EVENT,
)


class TestDirectiveModels:
    """Test JARVIS directive data models."""

    def test_directive_types(self):
        assert JarvisDirectiveType.SPRINT_REPORT == "sprint_report"
        assert JarvisDirectiveType.REVIEW_PR == "review_pr"
        assert JarvisDirectiveType.ARCHITECTURE_QUERY == "architecture_query"
        assert JarvisDirectiveType.DEVOPS_STATUS == "devops_status"

    def test_directive_creation(self):
        directive = JarvisDirective(
            directive_id="dir-001",
            type=JarvisDirectiveType.SPRINT_REPORT,
            payload={"repository": "afcen/platform"},
            priority="high",
        )
        assert directive.type == JarvisDirectiveType.SPRINT_REPORT
        assert directive.requires_response is True

    def test_cto_response_creation(self):
        response = CTOResponse(
            response_to="dir-001",
            status=CTOResponseStatus.COMPLETED,
            result={"agent": "sprint_planner", "report": {}},
        )
        assert response.status == CTOResponseStatus.COMPLETED
        assert response.error is None

    def test_directive_to_event_mapping(self):
        """All directive types should map to supervisor event types."""
        assert DIRECTIVE_TO_EVENT["sprint_report"] == "sprint_report"
        assert DIRECTIVE_TO_EVENT["review_pr"] == "pull_request"
        assert DIRECTIVE_TO_EVENT["architecture_query"] == "architecture_query"
        assert DIRECTIVE_TO_EVENT["devops_status"] == "devops_status"


class TestDirectiveHandler:
    """Test JarvisDirectiveHandler routing and response."""

    @pytest.mark.asyncio
    async def test_handle_sprint_report_directive(self):
        """Sprint report directive should route through supervisor."""
        handler = JarvisDirectiveHandler(openclaw_client=None)

        directive = JarvisDirective(
            directive_id="dir-001",
            type=JarvisDirectiveType.SPRINT_REPORT,
            payload={"repository": "afcen/platform"},
        )

        mock_result = {
            "result": {
                "agent": "sprint_planner",
                "report": {"summary": "Sprint on track"},
            },
            "error": None,
        }

        with patch(
            "src.supervisor.graph.supervisor_graph"
        ) as mock_graph:
            mock_graph.ainvoke = AsyncMock(return_value=mock_result)
            response = await handler.handle_directive(directive)

        assert response.status == CTOResponseStatus.COMPLETED
        assert response.response_to == "dir-001"
        assert response.result["agent"] == "sprint_planner"

    @pytest.mark.asyncio
    async def test_handle_unknown_directive_type(self):
        """general_query directive should route through supervisor."""
        handler = JarvisDirectiveHandler(openclaw_client=None)

        directive = JarvisDirective(
            directive_id="dir-bad",
            type=JarvisDirectiveType.GENERAL_QUERY,
            payload={},
        )

        mock_result = {
            "result": {"agent": None, "message": "Event type not handled"},
            "error": None,
        }

        with patch(
            "src.supervisor.graph.supervisor_graph"
        ) as mock_graph:
            mock_graph.ainvoke = AsyncMock(return_value=mock_result)
            response = await handler.handle_directive(directive)

        assert response.status == CTOResponseStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_handle_supervisor_error(self):
        """Supervisor errors should be reflected in the response."""
        handler = JarvisDirectiveHandler(openclaw_client=None)

        directive = JarvisDirective(
            directive_id="dir-err",
            type=JarvisDirectiveType.DEVOPS_STATUS,
            payload={},
        )

        mock_result = {
            "result": None,
            "error": "DevOps agent failed: connection timeout",
        }

        with patch(
            "src.supervisor.graph.supervisor_graph"
        ) as mock_graph:
            mock_graph.ainvoke = AsyncMock(return_value=mock_result)
            response = await handler.handle_directive(directive)

        assert response.status == CTOResponseStatus.FAILED
        assert "connection timeout" in response.error

    @pytest.mark.asyncio
    async def test_handle_approval_response(self):
        """Approval responses should resolve pending approvals."""
        handler = JarvisDirectiveHandler(openclaw_client=None)

        # Simulate a pending approval
        handler._pending_approvals["dir-original"] = {"some": "data"}

        directive = JarvisDirective(
            directive_id="dir-approve",
            type=JarvisDirectiveType.APPROVAL_RESPONSE,
            payload={
                "original_directive_id": "dir-original",
                "action": "approve",
            },
        )

        response = await handler.handle_directive(directive)
        assert response.status == CTOResponseStatus.COMPLETED
        assert response.result["action"] == "approve"
        assert "dir-original" not in handler._pending_approvals

    @pytest.mark.asyncio
    async def test_approval_response_missing_original(self):
        """Approval for non-existent directive should fail."""
        handler = JarvisDirectiveHandler(openclaw_client=None)

        directive = JarvisDirective(
            directive_id="dir-orphan",
            type=JarvisDirectiveType.APPROVAL_RESPONSE,
            payload={
                "original_directive_id": "nonexistent",
                "action": "approve",
            },
        )

        response = await handler.handle_directive(directive)
        assert response.status == CTOResponseStatus.FAILED
        assert "No pending approval" in response.error

    @pytest.mark.asyncio
    async def test_send_response_without_client(self):
        """send_response should return False when no OpenClaw client."""
        handler = JarvisDirectiveHandler(openclaw_client=None)
        response = CTOResponse(
            response_to="dir-001",
            status=CTOResponseStatus.COMPLETED,
            result={},
        )

        sent = await handler.send_response(response)
        assert sent is False

    def test_register_event_handlers_without_client(self):
        """register_event_handlers should not crash without a client."""
        handler = JarvisDirectiveHandler(openclaw_client=None)
        handler.register_event_handlers()  # Should not raise
