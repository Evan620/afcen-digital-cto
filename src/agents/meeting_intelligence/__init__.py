"""Meeting Intelligence Agent — Phase 3B.

Handles post-meeting analysis, pre-meeting briefs, and Recall.ai integration.
"""

from src.agents.meeting_intelligence.agent import (
    meeting_intelligence_graph,
    analyze_meeting_transcript,
    generate_pre_meeting_brief,
    deploy_meeting_bot,
)
from src.agents.meeting_intelligence.models import (
    MeetingAnalysis,
    PreMeetingBrief,
    MeetingQueryType,
    MeetingIntelligenceState,
    MeetingRecord,
    ActionItem,
    MeetingDecision,
)

__all__ = [
    "meeting_intelligence_graph",
    "analyze_meeting_transcript",
    "generate_pre_meeting_brief",
    "deploy_meeting_bot",
    "MeetingAnalysis",
    "PreMeetingBrief",
    "MeetingQueryType",
    "MeetingIntelligenceState",
    "MeetingRecord",
    "ActionItem",
    "MeetingDecision",
]
