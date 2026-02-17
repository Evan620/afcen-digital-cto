"""Tests for the LangGraph Supervisor routing logic."""

from __future__ import annotations

import pytest


class TestEventClassification:
    """Test that the supervisor routes events to the correct agent."""

    @pytest.mark.asyncio
    async def test_pr_event_routes_to_code_review(self):
        """A pull_request event should be classified as 'code_review'."""
        from src.supervisor.graph import classify_event, SupervisorState

        state: SupervisorState = {
            "event_type": "pull_request",
            "source": "github_webhook",
            "payload": {},
            "routed_to": None,
            "result": None,
            "error": None,
        }

        result = await classify_event(state)
        assert result["routed_to"] == "code_review"

    @pytest.mark.asyncio
    async def test_unknown_event_type_returns_none(self):
        """An unhandled event type should not crash, just return None routing."""
        from src.supervisor.graph import classify_event, SupervisorState

        state: SupervisorState = {
            "event_type": "meeting_transcript",
            "source": "recall_ai",
            "payload": {},
            "routed_to": None,
            "result": None,
            "error": None,
        }

        result = await classify_event(state)
        assert result["routed_to"] is None
        assert result.get("error") is not None

    def test_routing_decision_for_pr(self):
        """route_after_classify should return 'route_to_code_review' for PR events."""
        from src.supervisor.graph import route_after_classify, SupervisorState

        state: SupervisorState = {
            "event_type": "pull_request",
            "source": "github_webhook",
            "payload": {},
            "routed_to": "code_review",
            "result": None,
            "error": None,
        }

        assert route_after_classify(state) == "route_to_code_review"

    def test_routing_decision_for_unknown(self):
        """route_after_classify should return 'handle_unknown' for unhandled types."""
        from src.supervisor.graph import route_after_classify, SupervisorState

        state: SupervisorState = {
            "event_type": "unknown",
            "source": "test",
            "payload": {},
            "routed_to": None,
            "result": None,
            "error": None,
        }

        assert route_after_classify(state) == "handle_unknown"
