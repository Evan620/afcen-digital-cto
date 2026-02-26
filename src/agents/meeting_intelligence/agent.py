"""Meeting Intelligence Agent — LangGraph subgraph for meeting analysis.

Handles post-meeting analysis, pre-meeting briefs, and meeting records.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from langgraph.graph import END, StateGraph

from src.agents.meeting_intelligence.models import (
    MeetingAnalysis,
    MeetingIntelligenceState,
    MeetingQueryType,
    PreMeetingBrief,
)
from src.agents.meeting_intelligence.prompts import (
    get_post_meeting_prompt,
    get_pre_meeting_prompt,
)
from src.agents.meeting_intelligence.tools import (
    RecallClient,
    MeetingStore,
    assemble_pre_meeting_context,
)
from src.config import settings
from src.llm.utils import extract_json_from_llm_output, get_default_llm

logger = logging.getLogger(__name__)


# ── Node Functions ──


async def analyze_meeting(state: MeetingIntelligenceState) -> dict:
    """Analyze a meeting transcript and extract structured information."""
    logger.info("Analyzing meeting: %s", state.get("meeting_title", "Unknown"))

    transcript = state.get("transcript")
    if not transcript:
        return {"error": "No transcript provided for analysis"}

    try:
        llm = get_default_llm(temperature=0.3)

        prompt = get_post_meeting_prompt(
            meeting_title=state.get("meeting_title", "Unknown"),
            meeting_date=state.get("meeting_date", datetime.utcnow()).isoformat(),
            participants=", ".join(state.get("participants", [])),
            duration_minutes=state.get("duration_minutes", 0),
            transcript=transcript,
        )

        response = await llm.ainvoke(prompt)
        response_text = response.content if hasattr(response, "content") else str(response)

        # Extract JSON
        analysis_data = extract_json_from_llm_output(response_text)

        if not analysis_data:
            logger.warning("Failed to extract analysis JSON")
            return {"error": "Failed to parse analysis"}

        # Build MeetingAnalysis
        meeting_id = state.get("meeting_id", f"meeting_{datetime.utcnow().strftime('%Y%m%d%H%M')}")

        analysis = MeetingAnalysis(
            meeting_id=meeting_id,
            title=state.get("meeting_title", "Unknown"),
            date=state.get("meeting_date", datetime.utcnow()),
            participants=state.get("participants", []),
            duration_minutes=state.get("duration_minutes", 0),
            summary=analysis_data.get("summary", ""),
            key_decisions=analysis_data.get("key_decisions", []),
            action_items=analysis_data.get("action_items", []),
            follow_ups=[],  # Could be extracted from action items
            technical_topics=analysis_data.get("technical_topics", []),
            mentioned_systems=analysis_data.get("mentioned_systems", []),
            pain_points=analysis_data.get("pain_points", []),
            opportunities=analysis_data.get("opportunities", []),
            related_meetings=[],
            related_issues=[],
            related_prs=[],
            suggested_prds=analysis_data.get("suggested_prds", []),
            suggested_integrations=analysis_data.get("suggested_integrations", []),
        )

        # Store the analysis
        await store_analysis(analysis)

        logger.info(
            "Meeting analysis complete: %d decisions, %d action items",
            len(analysis.key_decisions),
            len(analysis.action_items),
        )

        return {"analysis": analysis}

    except Exception as e:
        logger.error("Meeting analysis failed: %s", e)
        return {"error": f"Analysis failed: {e}"}


async def generate_brief(state: MeetingIntelligenceState) -> dict:
    """Generate a pre-meeting brief with context."""
    logger.info("Generating pre-meeting brief for: %s", state.get("meeting_title", "Unknown"))

    try:
        # Assemble context
        participants = state.get("participants", [])
        context = await assemble_pre_meeting_context(
            participants=participants,
            meeting_type=state.get("meeting_type"),
        )

        # Format context for prompt
        recent_meetings_str = "\n".join([
            f"- {m.get('title', 'Unknown')} ({m.get('meeting_date', 'Unknown')[:10]})"
            for m in context.get("recent_meetings", [])
        ])

        action_items_str = "\n".join([
            f"- {item.get('task', 'Unknown')} (Owner: {item.get('owner', 'Unknown')})"
            for item in context.get("outstanding_action_items", [])
        ])

        # Get actual GitHub status and market intel from other agents
        github_status = await _get_github_status_for_brief()
        market_intel = await _get_market_intel_for_brief()

        llm = get_default_llm(temperature=0.5)

        prompt = get_pre_meeting_prompt(
            meeting_title=state.get("meeting_title", "Unknown"),
            meeting_time=state.get("meeting_date", datetime.utcnow()).isoformat(),
            participants=", ".join(participants),
            meeting_type=state.get("meeting_type", "Meeting"),
            recent_meetings=recent_meetings_str or "No recent meetings found",
            action_items=action_items_str or "No outstanding items",
            github_status=github_status,
            market_intel=market_intel,
        )

        response = await llm.ainvoke(prompt)
        response_text = response.content if hasattr(response, "content") else str(response)

        brief_data = extract_json_from_llm_output(response_text)

        if not brief_data:
            brief_data = {}

        brief = PreMeetingBrief(
            meeting_title=state.get("meeting_title", "Unknown"),
            scheduled_time=state.get("meeting_date", datetime.utcnow()),
            participants=participants,
            recent_meetings_with_participants=brief_data.get("recent_meetings_with_participants", []),
            outstanding_action_items=brief_data.get("outstanding_action_items", []),
            github_issues_mentioned=brief_data.get("github_issues_mentioned", []),
            sprint_status_summary=brief_data.get("sprint_status_summary", ""),
            topics_likely_discussed=brief_data.get("topics_likely_discussed", []),
            decisions_expected=brief_data.get("decisions_expected", []),
            context_to_have_ready=brief_data.get("context_to_have_ready", []),
            relevant_developments=brief_data.get("relevant_developments", []),
        )

        logger.info("Pre-meeting brief generated: %d topics, %d context items",
                   len(brief.topics_likely_discussed), len(brief.context_to_have_ready))

        return {"brief": brief}

    except Exception as e:
        logger.error("Brief generation failed: %s", e)
        return {"error": f"Brief generation failed: {e}"}


async def generate_status(state: MeetingIntelligenceState) -> dict:
    """Generate status report for meeting intelligence."""
    try:
        store = MeetingStore()

        recent_meetings = await store.get_recent_meetings(days=30, limit=20)
        outstanding_actions = await store.get_outstanding_actions()

        report = {
            "status": "operational",
            "recent_meetings_count": len(recent_meetings),
            "outstanding_action_items": len(outstanding_actions),
            "recall_configured": bool(settings.recall_api_key),
            "last_meeting": recent_meetings[0] if recent_meetings else None,
        }

        return {"report": report}

    except Exception as e:
        logger.error("Status generation failed: %s", e)
        return {"error": f"Status failed: {e}"}


async def handle_error(state: MeetingIntelligenceState) -> dict:
    """Handle errors in the meeting intelligence workflow."""
    error = state.get("error", "Unknown error")
    logger.error("Meeting Intelligence error: %s", error)

    return {"report": {"status": "error", "message": error}}


# ── Helper Functions ──


async def store_analysis(analysis: MeetingAnalysis) -> None:
    """Store meeting analysis in database."""
    try:
        store = MeetingStore()

        # Save meeting record
        await store.save_meeting(
            meeting_id=analysis.meeting_id,
            title=analysis.title,
            meeting_date=analysis.date,
            participants=analysis.participants,
            duration_minutes=analysis.duration_minutes,
        )

        # Save decisions
        for decision in analysis.key_decisions:
            await store.save_decision(
                meeting_id=analysis.meeting_id,
                decision=decision.get("decision", ""),
                decision_maker=decision.get("decision_maker"),
                context=decision.get("context"),
                impact=decision.get("impact"),
            )

        # Save action items
        if analysis.action_items:
            await store.save_action_items(
                action_items=analysis.action_items,
                meeting_id=analysis.meeting_id,
            )

        logger.info("Meeting analysis stored: %s", analysis.meeting_id)

    except Exception as e:
        logger.error("Failed to store analysis: %s", e)


# ── Routing Logic ──


def route_after_query_type(state: MeetingIntelligenceState) -> str:
    """Route based on query type."""
    query_type = state.get("query_type", MeetingQueryType.STATUS)

    if query_type == MeetingQueryType.POST_MEETING:
        return "analyze_meeting"
    elif query_type == MeetingQueryType.PRE_MEETING:
        return "generate_brief"
    else:
        return "generate_status"


# ── Build the Graph ──


def build_meeting_intelligence_graph() -> StateGraph:
    """Construct the Meeting Intelligence agent as a LangGraph StateGraph.

    Workflows:
    - POST_MEETING: analyze_meeting → END
    - PRE_MEETING: generate_brief → END
    - STATUS: generate_status → END
    """
    graph = StateGraph(MeetingIntelligenceState)

    # Add a router node that dispatches based on query_type
    graph.add_node("router", lambda state: state)

    # Add workflow nodes
    graph.add_node("analyze_meeting", analyze_meeting)
    graph.add_node("generate_brief", generate_brief)
    graph.add_node("generate_status", generate_status)
    graph.add_node("handle_error", handle_error)

    # Entry point
    graph.set_entry_point("router")

    # Add conditional routing from router
    graph.add_conditional_edges(
        "router",
        route_after_query_type,
        {
            "analyze_meeting": "analyze_meeting",
            "generate_brief": "generate_brief",
            "generate_status": "generate_status",
        },
    )

    # Terminal edges
    graph.add_edge("analyze_meeting", END)
    graph.add_edge("generate_brief", END)
    graph.add_edge("generate_status", END)
    graph.add_edge("handle_error", END)

    return graph


# Compiled graph
meeting_intelligence_graph = build_meeting_intelligence_graph().compile()


# ── Convenience Functions ──


def _default_state(
    query_type: str = MeetingQueryType.STATUS.value,
    **kwargs,
) -> dict:
    """Create a default state for the meeting intelligence agent."""
    return {
        "query_type": query_type,
        "query": kwargs.get("query", ""),
        "meeting_id": kwargs.get("meeting_id"),
        "meeting_title": kwargs.get("meeting_title"),
        "meeting_date": kwargs.get("meeting_date"),
        "participants": kwargs.get("participants", []),
        "transcript": kwargs.get("transcript"),
        "analysis": None,
        "brief": None,
        "report": None,
        "error": None,
    }


async def analyze_meeting_transcript(
    transcript: str,
    meeting_title: str,
    participants: list[str],
    meeting_date: datetime | None = None,
) -> MeetingAnalysis | None:
    """Analyze a meeting transcript.

    Main entry point for post-meeting analysis.
    """
    state = {
        "query_type": MeetingQueryType.POST_MEETING,
        "transcript": transcript,
        "meeting_title": meeting_title,
        "participants": participants,
        "meeting_date": meeting_date or datetime.utcnow(),
        "analysis": None,
        "brief": None,
        "report": None,
        "error": None,
    }

    try:
        result = await meeting_intelligence_graph.ainvoke(state)
        return result.get("analysis")
    except Exception as e:
        logger.error("Meeting transcript analysis failed: %s", e)
        return None


async def generate_pre_meeting_brief(
    meeting_title: str,
    participants: list[str],
    meeting_date: datetime | None = None,
    meeting_type: str | None = None,
) -> PreMeetingBrief | None:
    """Generate a pre-meeting brief.

    Main entry point for pre-meeting intelligence.
    """
    state = {
        "query_type": MeetingQueryType.PRE_MEETING,
        "meeting_title": meeting_title,
        "participants": participants,
        "meeting_date": meeting_date or datetime.utcnow(),
        "meeting_type": meeting_type,
        "analysis": None,
        "brief": None,
        "report": None,
        "error": None,
    }

    try:
        result = await meeting_intelligence_graph.ainvoke(state)
        return result.get("brief")
    except Exception as e:
        logger.error("Pre-meeting brief generation failed: %s", e)
        return None


async def deploy_meeting_bot(meeting_url: str, meeting_title: str = "") -> dict | None:
    """Deploy a Recall.ai bot to a meeting.

    Main entry point for meeting bot deployment.
    """
    if not settings.recall_api_key:
        logger.warning("Recall.ai API key not configured")
        return None

    try:
        client = RecallClient()
        result = await client.deploy_bot(
            meeting_url=meeting_url,
            meeting_title=meeting_title,
        )
        await client.close()
        return result
    except Exception as e:
        logger.error("Failed to deploy meeting bot: %s", e)
        return None


async def get_meeting_status() -> dict | None:
    """Get the current status of meeting intelligence.

    Entry point for the scheduler job.
    """
    state = _default_state(query_type=MeetingQueryType.STATUS.value)

    try:
        result = await meeting_intelligence_graph.ainvoke(state)
        return result.get("report")
    except Exception as e:
        logger.error("Meeting status generation failed: %s", e)
        return None


# ── Cross-Agent Integration Helpers ──


async def _get_github_status_for_brief() -> str:
    """Get GitHub/sprint status from Sprint Planner agent for pre-meeting briefs.

    Returns a formatted string with current sprint status, open PRs, etc.
    """
    try:
        from src.agents.sprint_planner.agent import sprint_planner_graph
        from src.agents.sprint_planner.models import SprintQueryType

        # Build state dict directly (avoids importing private _default_state)
        state = {
            "query_type": SprintQueryType.STATUS.value,
            "repository": getattr(settings, "github_repository", ""),
            "report": None,
            "metrics": None,
            "error": None,
        }

        result = await sprint_planner_graph.ainvoke(state)

        # Format the status into a readable string
        if result.get("metrics"):
            m = result["metrics"]
            return (
                f"Sprint: {m.get('current_sprint', 'Unknown')}\n"
                f"Open PRs: {m.get('open_prs', 0)}\n"
                f"Open Issues: {m.get('open_issues', 0)}\n"
                f"Velocity: {m.get('velocity', 'N/A')}"
            )
        elif result.get("report"):
            return result["report"].get("summary", "GitHub: Connected")

        return "GitHub: Connected (no sprint data available)"

    except Exception as e:
        logger.debug("Failed to get GitHub status for brief: %s", e)
        return "GitHub: Status unavailable"


async def _get_market_intel_for_brief() -> str:
    """Get market intelligence for pre-meeting briefs.

    Returns a formatted string with recent market developments.
    """
    try:
        from src.agents.market_scanner.tools import MarketIntelStore

        store = MarketIntelStore()
        intel_items = await store.get_recent_intel(hours=48, min_relevance=0.5, limit=5)

        if not intel_items:
            return "Market Intel: No significant developments in last 48 hours"

        # Format top items
        top_items = []
        for item in intel_items[:5]:
            source_emoji = {
                "news": "📰",
                "dfi_opportunity": "💰",
                "carbon_market": "🌱",
            }.get(item.source, "•")
            top_items.append(f"{source_emoji} {item.title[:80]}...")

        return "Market Intel (last 48h):\n" + "\n".join(top_items)

    except Exception as e:
        logger.debug("Failed to get market intel for brief: %s", e)
        return "Market Intel: Status unavailable"
