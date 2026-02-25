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
    async def test_sprint_event_routes_to_sprint_planner(self):
        """Sprint-related events should route to sprint_planner."""
        from src.supervisor.graph import classify_event, SupervisorState

        for event_type in ("sprint_query", "sprint_report", "sprint_status", "bayes_tracking"):
            state: SupervisorState = {
                "event_type": event_type,
                "source": "jarvis",
                "payload": {},
                "routed_to": None,
                "result": None,
                "error": None,
            }
            result = await classify_event(state)
            assert result["routed_to"] == "sprint_planner", f"Failed for {event_type}"

    @pytest.mark.asyncio
    async def test_retrospective_routes_to_sprint_planner(self):
        """Retrospective events should route to sprint_planner."""
        from src.supervisor.graph import classify_event, SupervisorState

        state: SupervisorState = {
            "event_type": "retrospective",
            "source": "direct",
            "payload": {},
            "routed_to": None,
            "result": None,
            "error": None,
        }

        result = await classify_event(state)
        assert result["routed_to"] == "sprint_planner"

    @pytest.mark.asyncio
    async def test_architecture_event_routes_to_advisor(self):
        """Architecture events should route to architecture_advisor."""
        from src.supervisor.graph import classify_event, SupervisorState

        for event_type in ("architecture_query", "design_review", "tech_debt"):
            state: SupervisorState = {
                "event_type": event_type,
                "source": "jarvis",
                "payload": {},
                "routed_to": None,
                "result": None,
                "error": None,
            }
            result = await classify_event(state)
            assert result["routed_to"] == "architecture_advisor", f"Failed for {event_type}"

    @pytest.mark.asyncio
    async def test_devops_event_routes_to_devops(self):
        """DevOps events should route to devops agent."""
        from src.supervisor.graph import classify_event, SupervisorState

        for event_type in ("devops_status", "pipeline_status", "devops_report"):
            state: SupervisorState = {
                "event_type": event_type,
                "source": "scheduler",
                "payload": {},
                "routed_to": None,
                "result": None,
                "error": None,
            }
            result = await classify_event(state)
            assert result["routed_to"] == "devops", f"Failed for {event_type}"

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


class TestRoutingDecisions:
    """Test route_after_classify for all agent types."""

    def test_routing_decision_for_pr(self):
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

    def test_routing_decision_for_sprint(self):
        from src.supervisor.graph import route_after_classify, SupervisorState

        state: SupervisorState = {
            "event_type": "sprint_report",
            "source": "jarvis",
            "payload": {},
            "routed_to": "sprint_planner",
            "result": None,
            "error": None,
        }
        assert route_after_classify(state) == "route_to_sprint_planner"

    def test_routing_decision_for_architecture(self):
        from src.supervisor.graph import route_after_classify, SupervisorState

        state: SupervisorState = {
            "event_type": "architecture_query",
            "source": "jarvis",
            "payload": {},
            "routed_to": "architecture_advisor",
            "result": None,
            "error": None,
        }
        assert route_after_classify(state) == "route_to_architecture_advisor"

    def test_routing_decision_for_devops(self):
        from src.supervisor.graph import route_after_classify, SupervisorState

        state: SupervisorState = {
            "event_type": "devops_status",
            "source": "scheduler",
            "payload": {},
            "routed_to": "devops",
            "result": None,
            "error": None,
        }
        assert route_after_classify(state) == "route_to_devops"

    def test_routing_decision_for_unknown(self):
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


class TestSupervisorGraphStructure:
    """Test that the graph is properly constructed."""

    def test_graph_has_all_nodes(self):
        """The supervisor graph should have nodes for all 6 agents + unknown."""
        from src.supervisor.graph import build_supervisor_graph

        graph = build_supervisor_graph()
        node_names = set(graph.nodes.keys())

        assert "classify_event" in node_names
        # Phase 1-2 agents
        assert "route_to_code_review" in node_names
        assert "route_to_sprint_planner" in node_names
        assert "route_to_architecture_advisor" in node_names
        assert "route_to_devops" in node_names
        # Phase 3 agents
        assert "route_to_market_scanner" in node_names
        assert "route_to_meeting_intelligence" in node_names
        assert "handle_unknown" in node_names
