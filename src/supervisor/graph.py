"""LangGraph Supervisor — the central routing brain of the Digital CTO.

The Supervisor receives incoming events (GitHub webhooks, Slack messages,
scheduled tasks, direct queries) and routes them to the appropriate sub-agent.

Phase 1: Code Review agent
Phase 2: Sprint Planner agent
Future phases: Market Scanner, Architecture Advisor.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Literal, Optional, TypedDict

from langgraph.graph import END, StateGraph

from src.agents.code_review.agent import code_review_graph, CodeReviewState
from src.agents.sprint_planner.agent import (
    sprint_planner_graph,
    SprintPlannerState,
    SprintQueryType,
)

logger = logging.getLogger(__name__)


# ── Supervisor State ──


class SupervisorState(TypedDict):
    """Top-level state for the supervisor routing graph."""

    # Input
    event_type: str  # "pull_request", "sprint_query", "sprint_report", "meeting", etc.
    source: str  # "github_webhook", "jarvis", "scheduler", "direct"
    payload: Dict[str, Any]  # Raw event data

    # Routing
    routed_to: Optional[str]  # Which agent handled it
    result: Optional[Dict[str, Any]]  # Agent output

    # Error
    error: Optional[str]


# ── Node Functions ──


async def classify_event(state: SupervisorState) -> dict:
    """Classify the incoming event and determine which agent should handle it."""
    event_type = state["event_type"]

    if event_type == "pull_request":
        logger.info("Event classified: pull_request → routing to Code Review agent")
        return {"routed_to": "code_review"}

    elif event_type in ("sprint_query", "sprint_report", "sprint_status", "bayes_tracking"):
        logger.info("Event classified: %s → routing to Sprint Planner agent", event_type)
        return {"routed_to": "sprint_planner"}

    # Future: add routing for other event types
    # elif event_type == "meeting":
    #     return {"routed_to": "meeting_intelligence"}
    # elif event_type == "market_scan":
    #     return {"routed_to": "market_scanner"}
    # elif event_type == "architecture_query":
    #     return {"routed_to": "architecture_advisor"}

    logger.warning("Unhandled event type: %s — no agent assigned", event_type)
    return {"routed_to": None, "error": f"No agent registered for event type: {event_type}"}


async def route_to_code_review(state: SupervisorState) -> dict:
    """Execute the Code Review agent subgraph."""
    payload = state["payload"]

    # Build the Code Review agent's input state
    pr_data = payload.get("pull_request", {})
    review_input: CodeReviewState = {
        "repository": payload.get("repository_full_name", ""),
        "pr_number": pr_data.get("number", 0),
        "pr_title": pr_data.get("title", ""),
        "pr_body": pr_data.get("body", ""),
        "pr_author": pr_data.get("user", {}).get("login", "unknown"),
        "base_branch": pr_data.get("base", {}).get("ref", "main"),
        "head_branch": pr_data.get("head", {}).get("ref", ""),
        "diff": "",
        "changed_files": [],
        "file_contexts": {},
        "review_result": None,
        "posted": False,
        "error": None,
    }

    try:
        # Run the code review subgraph
        result = await code_review_graph.ainvoke(review_input)

        logger.info(
            "Code Review complete for PR #%d: posted=%s, error=%s",
            review_input["pr_number"],
            result.get("posted"),
            result.get("error"),
        )

        return {
            "result": {
                "agent": "code_review",
                "posted": result.get("posted", False),
                "review": result.get("review_result"),
                "error": result.get("error"),
            }
        }

    except Exception as e:
        logger.error("Code Review agent crashed: %s", e)
        return {"error": f"Code Review agent failed: {e}"}


async def route_to_sprint_planner(state: SupervisorState) -> dict:
    """Execute the Sprint Planner agent subgraph."""
    payload = state["payload"]
    event_type = state["event_type"]

    # Determine query type
    query_type_map = {
        "sprint_query": SprintQueryType.STATUS,
        "sprint_report": SprintQueryType.REPORT,
        "sprint_status": SprintQueryType.STATUS,
        "bayes_tracking": SprintQueryType.BAYES_TRACKING,
    }
    query_type = query_type_map.get(event_type, SprintQueryType.STATUS)

    # Build the Sprint Planner agent's input state
    planner_input: SprintPlannerState = {
        "query_type": query_type.value,
        "repository": payload.get("repository"),
        "sprint_id": payload.get("sprint_id"),
        "include_bayes": payload.get("include_bayes", True),
        "include_recommendations": payload.get("include_recommendations", True),
        "issues": [],
        "project_items": [],
        "metrics": None,
        "report": None,
        "bayes_summary": None,
        "recommendations": [],
        "error": None,
    }

    try:
        # Run the sprint planner subgraph
        result = await sprint_planner_graph.ainvoke(planner_input)

        logger.info(
            "Sprint Planner complete: query_type=%s, has_report=%s, error=%s",
            query_type.value,
            result.get("report") is not None,
            result.get("error"),
        )

        return {
            "result": {
                "agent": "sprint_planner",
                "query_type": query_type.value,
                "metrics": result.get("metrics"),
                "report": result.get("report"),
                "bayes_summary": result.get("bayes_summary"),
                "recommendations": result.get("recommendations", []),
                "error": result.get("error"),
            }
        }

    except Exception as e:
        logger.error("Sprint Planner agent crashed: %s", e)
        return {"error": f"Sprint Planner agent failed: {e}"}


async def handle_unknown(state: SupervisorState) -> dict:
    """Handle events that no agent can process."""
    logger.info("No agent available for event type: %s", state["event_type"])
    return {"result": {"agent": None, "message": "Event type not handled in current phase"}}


# ── Routing Logic ──


def route_after_classify(state: SupervisorState) -> str:
    """Determine the next node based on event classification."""
    routed_to = state.get("routed_to")

    if routed_to == "code_review":
        return "route_to_code_review"
    elif routed_to == "sprint_planner":
        return "route_to_sprint_planner"
    else:
        return "handle_unknown"


# ── Build the Graph ──


def build_supervisor_graph() -> StateGraph:
    """Construct the Supervisor as a LangGraph StateGraph.

    Flow: classify_event → (code_review | sprint_planner | unknown) → END
    """
    graph = StateGraph(SupervisorState)

    # Add nodes
    graph.add_node("classify_event", classify_event)
    graph.add_node("route_to_code_review", route_to_code_review)
    graph.add_node("route_to_sprint_planner", route_to_sprint_planner)
    graph.add_node("handle_unknown", handle_unknown)

    # Entry point
    graph.set_entry_point("classify_event")

    # Conditional routing after classification
    graph.add_conditional_edges(
        "classify_event",
        route_after_classify,
        {
            "route_to_code_review": "route_to_code_review",
            "route_to_sprint_planner": "route_to_sprint_planner",
            "handle_unknown": "handle_unknown",
        },
    )

    # Terminal edges
    graph.add_edge("route_to_code_review", END)
    graph.add_edge("route_to_sprint_planner", END)
    graph.add_edge("handle_unknown", END)

    return graph


# Compiled supervisor graph ready to invoke
supervisor_graph = build_supervisor_graph().compile()
