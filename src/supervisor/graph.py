"""LangGraph Supervisor — the central routing brain of the Digital CTO.

The Supervisor receives incoming events (GitHub webhooks, Slack messages,
scheduled tasks, direct queries) and routes them to the appropriate sub-agent.

Phase 1: Code Review agent
Phase 2: Sprint Planner, Architecture Advisor, DevOps agents + JARVIS directives
Phase 3: Market Scanner, Meeting Intelligence.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, TypedDict

from langgraph.graph import END, StateGraph

from src.agents.code_review.agent import code_review_graph, CodeReviewState
from src.agents.sprint_planner.agent import (
    sprint_planner_graph,
    SprintPlannerState,
    SprintQueryType,
    _default_state as sprint_default_state,
)
from src.agents.architecture_advisor.agent import (
    architecture_advisor_graph,
    ArchitectureAdvisorState,
)
from src.agents.architecture_advisor.models import ArchitectureQueryType
from src.agents.devops.agent import devops_graph, DevOpsState
from src.agents.devops.models import DevOpsQueryType
from src.agents.market_scanner.agent import (
    market_scanner_graph,
    _default_state as market_default_state,
)
from src.agents.market_scanner.models import MarketScannerQueryType
from src.agents.meeting_intelligence.agent import (
    meeting_intelligence_graph,
    _default_state as meeting_default_state,
)
from src.agents.meeting_intelligence.models import MeetingQueryType
from src.agents.coding_agent.agent import (
    coding_graph,
    _default_state as coding_default_state,
)
from src.agents.coding_agent.models import CodingComplexity

logger = logging.getLogger(__name__)


# ── Supervisor State ──


class SupervisorState(TypedDict):
    """Top-level state for the supervisor routing graph."""

    # Input
    event_type: str  # "pull_request", "sprint_query", "architecture_query", "devops_status", etc.
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

    elif event_type in (
        "sprint_query", "sprint_report", "sprint_status",
        "bayes_tracking", "retrospective",
    ):
        logger.info("Event classified: %s → routing to Sprint Planner agent", event_type)
        return {"routed_to": "sprint_planner"}

    elif event_type in ("architecture_query", "design_review", "tech_debt"):
        logger.info("Event classified: %s → routing to Architecture Advisor agent", event_type)
        return {"routed_to": "architecture_advisor"}

    elif event_type in ("devops_status", "pipeline_status", "devops_report"):
        logger.info("Event classified: %s → routing to DevOps agent", event_type)
        return {"routed_to": "devops"}

    elif event_type in ("market_scan", "morning_brief", "market_intel", "market_status"):
        logger.info("Event classified: %s → routing to Market Scanner agent", event_type)
        return {"routed_to": "market_scanner"}

    elif event_type in ("post_meeting", "pre_meeting", "meeting_brief", "meeting_status"):
        logger.info("Event classified: %s → routing to Meeting Intelligence agent", event_type)
        return {"routed_to": "meeting_intelligence"}

    elif event_type in ("coding_task", "code_generation", "fix_issue", "implement_feature"):
        logger.info("Event classified: %s → routing to Coding agent", event_type)
        return {"routed_to": "coding_agent"}

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
        "retrospective": SprintQueryType.RETROSPECTIVE,
    }
    query_type = query_type_map.get(event_type, SprintQueryType.STATUS)

    planner_input = sprint_default_state(
        query_type=query_type.value,
        repository=payload.get("repository"),
        sprint_id=payload.get("sprint_id"),
        include_bayes=payload.get("include_bayes", True),
        include_recommendations=payload.get("include_recommendations", True),
    )

    try:
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


async def route_to_architecture_advisor(state: SupervisorState) -> dict:
    """Execute the Architecture Advisor agent subgraph."""
    payload = state["payload"]
    event_type = state["event_type"]

    # Map event type to query type
    query_type_map = {
        "architecture_query": "technology_evaluation",
        "design_review": "design_review",
        "tech_debt": "tech_debt_assessment",
    }
    query_type = payload.get("query_type", query_type_map.get(event_type, "technology_evaluation"))

    advisor_input: ArchitectureAdvisorState = {
        "query_type": query_type,
        "query": payload.get("query", ""),
        "repository": payload.get("repository"),
        "context": payload.get("context", {}),
        "repo_context": "",
        "prior_decisions": [],
        "llm_output": "",
        "recommendation": None,
        "error": None,
    }

    try:
        result = await architecture_advisor_graph.ainvoke(advisor_input)

        logger.info(
            "Architecture Advisor complete: query_type=%s, has_recommendation=%s, error=%s",
            query_type,
            result.get("recommendation") is not None,
            result.get("error"),
        )

        return {
            "result": {
                "agent": "architecture_advisor",
                "query_type": query_type,
                "recommendation": result.get("recommendation"),
                "error": result.get("error"),
            }
        }

    except Exception as e:
        logger.error("Architecture Advisor agent crashed: %s", e)
        return {"error": f"Architecture Advisor agent failed: {e}"}


async def route_to_devops(state: SupervisorState) -> dict:
    """Execute the DevOps agent subgraph."""
    payload = state["payload"]

    devops_input: DevOpsState = {
        "query_type": payload.get("query_type", DevOpsQueryType.PIPELINE_STATUS.value),
        "repositories": payload.get("repositories", []),
        "workflow_runs": [],
        "failed_runs": [],
        "failure_details": [],
        "llm_output": "",
        "report": None,
        "error": None,
    }

    try:
        result = await devops_graph.ainvoke(devops_input)

        logger.info(
            "DevOps agent complete: has_report=%s, error=%s",
            result.get("report") is not None,
            result.get("error"),
        )

        return {
            "result": {
                "agent": "devops",
                "report": result.get("report"),
                "error": result.get("error"),
            }
        }

    except Exception as e:
        logger.error("DevOps agent crashed: %s", e)
        return {"error": f"DevOps agent failed: {e}"}


async def route_to_market_scanner(state: SupervisorState) -> dict:
    """Execute the Market Scanner agent subgraph."""
    payload = state["payload"]
    event_type = state["event_type"]

    # Map event type to query type
    query_type_map = {
        "market_scan": MarketScannerQueryType.COLLECT,
        "morning_brief": MarketScannerQueryType.BRIEF,
        "market_intel": MarketScannerQueryType.STATUS,
        "market_status": MarketScannerQueryType.STATUS,
    }
    query_type = query_type_map.get(event_type, MarketScannerQueryType.STATUS)

    scanner_input = market_default_state(
        query_type=query_type.value,
        query=payload.get("query", ""),
    )

    try:
        result = await market_scanner_graph.ainvoke(scanner_input)

        logger.info(
            "Market Scanner complete: query_type=%s, has_brief=%s, error=%s",
            query_type.value,
            result.get("brief") is not None,
            result.get("error"),
        )

        return {
            "result": {
                "agent": "market_scanner",
                "query_type": query_type.value,
                "brief": result.get("brief"),
                "report": result.get("report"),
                "error": result.get("error"),
            }
        }

    except Exception as e:
        logger.error("Market Scanner agent crashed: %s", e)
        return {"error": f"Market Scanner agent failed: {e}"}


async def route_to_meeting_intelligence(state: SupervisorState) -> dict:
    """Execute the Meeting Intelligence agent subgraph."""
    payload = state["payload"]
    event_type = state["event_type"]

    # Map event type to query type
    query_type_map = {
        "post_meeting": MeetingQueryType.POST_MEETING,
        "pre_meeting": MeetingQueryType.PRE_MEETING,
        "meeting_brief": MeetingQueryType.PRE_MEETING,
        "meeting_status": MeetingQueryType.STATUS,
    }
    query_type = query_type_map.get(event_type, MeetingQueryType.STATUS)

    meeting_input = meeting_default_state(
        query_type=query_type.value,
        query=payload.get("query", ""),
        meeting_id=payload.get("meeting_id"),
        meeting_title=payload.get("meeting_title"),
        meeting_date=payload.get("meeting_date"),
        participants=payload.get("participants", []),
        transcript=payload.get("transcript"),
    )

    try:
        result = await meeting_intelligence_graph.ainvoke(meeting_input)

        logger.info(
            "Meeting Intelligence complete: query_type=%s, has_analysis=%s, has_brief=%s",
            query_type.value,
            result.get("analysis") is not None,
            result.get("brief") is not None,
        )

        return {
            "result": {
                "agent": "meeting_intelligence",
                "query_type": query_type.value,
                "analysis": result.get("analysis"),
                "brief": result.get("brief"),
                "report": result.get("report"),
                "error": result.get("error"),
            }
        }

    except Exception as e:
        logger.error("Meeting Intelligence agent crashed: %s", e)
        return {"error": f"Meeting Intelligence agent failed: {e}"}


async def handle_unknown(state: SupervisorState) -> dict:
    """Handle events that no agent can process."""
    logger.info("No agent available for event type: %s", state["event_type"])
    return {"result": {"agent": None, "message": "Event type not handled in current phase"}}


async def route_to_coding_agent(state: SupervisorState) -> dict:
    """Execute the Coding agent subgraph."""
    payload = state["payload"]

    # Build the Coding agent's input state
    coding_input = coding_default_state(
        task_id=payload.get("task_id"),
        description=payload.get("description", ""),
        repository=payload.get("repository", ""),
        base_branch=payload.get("base_branch", "main"),
        complexity=CodingComplexity(payload.get("complexity", "moderate")),
        estimated_files=payload.get("estimated_files", 1),
        requires_testing=payload.get("requires_testing", True),
        cost_sensitivity=payload.get("cost_sensitivity", "medium"),
        autonomy_level=payload.get("autonomy_level", "semi_autonomous"),
        context=payload.get("context", {}),
        related_issue=payload.get("related_issue"),
        related_pr=payload.get("related_pr"),
    )

    try:
        result = await coding_graph.ainvoke(coding_input)

        logger.info(
            "Coding agent complete: task_id=%s, status=%s",
            coding_input["task"].task_id if coding_input.get("task") else "unknown",
            result.get("status"),
        )

        return {
            "result": {
                "agent": "coding_agent",
                "task_id": coding_input.get("task", {}).task_id if coding_input.get("task") else None,
                "status": result.get("status"),
                "result": result.get("result").to_dict() if result.get("result") else None,
                "error": result.get("error"),
            }
        }

    except Exception as e:
        logger.error("Coding agent crashed: %s", e)
        return {"error": f"Coding agent failed: {e}"}


# ── Routing Logic ──


def route_after_classify(state: SupervisorState) -> str:
    """Determine the next node based on event classification."""
    routed_to = state.get("routed_to")

    routing_map = {
        "code_review": "route_to_code_review",
        "sprint_planner": "route_to_sprint_planner",
        "architecture_advisor": "route_to_architecture_advisor",
        "devops": "route_to_devops",
        "market_scanner": "route_to_market_scanner",
        "meeting_intelligence": "route_to_meeting_intelligence",
        "coding_agent": "route_to_coding_agent",
    }
    return routing_map.get(routed_to, "handle_unknown")


# ── Build the Graph ──


def build_supervisor_graph() -> StateGraph:
    """Construct the Supervisor as a LangGraph StateGraph.

    Flow: classify_event → (code_review | sprint_planner | architecture_advisor | devops | market_scanner | meeting_intelligence | coding_agent | unknown) → END
    """
    graph = StateGraph(SupervisorState)

    # Add nodes
    graph.add_node("classify_event", classify_event)
    graph.add_node("route_to_code_review", route_to_code_review)
    graph.add_node("route_to_sprint_planner", route_to_sprint_planner)
    graph.add_node("route_to_architecture_advisor", route_to_architecture_advisor)
    graph.add_node("route_to_devops", route_to_devops)
    graph.add_node("route_to_market_scanner", route_to_market_scanner)
    graph.add_node("route_to_meeting_intelligence", route_to_meeting_intelligence)
    graph.add_node("route_to_coding_agent", route_to_coding_agent)
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
            "route_to_architecture_advisor": "route_to_architecture_advisor",
            "route_to_devops": "route_to_devops",
            "route_to_market_scanner": "route_to_market_scanner",
            "route_to_meeting_intelligence": "route_to_meeting_intelligence",
            "route_to_coding_agent": "route_to_coding_agent",
            "handle_unknown": "handle_unknown",
        },
    )

    # Terminal edges
    graph.add_edge("route_to_code_review", END)
    graph.add_edge("route_to_sprint_planner", END)
    graph.add_edge("route_to_architecture_advisor", END)
    graph.add_edge("route_to_devops", END)
    graph.add_edge("route_to_market_scanner", END)
    graph.add_edge("route_to_meeting_intelligence", END)
    graph.add_edge("route_to_coding_agent", END)
    graph.add_edge("handle_unknown", END)

    return graph


# Compiled supervisor graph ready to invoke
supervisor_graph = build_supervisor_graph().compile()
