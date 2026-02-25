"""Data models for the Meeting Intelligence agent.

Models for meeting records, transcripts, analysis, and briefs.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class MeetingQueryType(str, Enum):
    """Types of queries the Meeting Intelligence agent can handle."""

    POST_MEETING = "post_meeting"  # Analyze a completed meeting
    PRE_MEETING = "pre_meeting"  # Generate pre-meeting brief
    STATUS = "status"  # Status of recent meetings
    TRANSCRIPT = "transcript"  # Retrieve or store transcript


class MeetingAnalysis(BaseModel):
    """Post-meeting structured analysis.

    Extracted from transcript and participants.
    """

    meeting_id: str
    title: str
    date: datetime
    participants: list[str]
    duration_minutes: int

    # Core analysis
    summary: str
    key_decisions: list[dict]  # Decision, who made it, context
    action_items: list[dict]  # Task, assignee, due date
    follow_ups: list[dict]  # Commitment, owner, deadline

    # Technical extraction
    technical_topics: list[str]
    mentioned_systems: list[str]  # Platform components referenced
    pain_points: list[str]  # Problems discussed
    opportunities: list[str]  # Ideas worth exploring

    # Cross-reference
    related_meetings: list[str]  # Past meetings on similar topics
    related_issues: list[int]  # GitHub issues mentioned
    related_prs: list[int]  # PRs discussed

    # Proactive recommendations
    suggested_prds: list[dict]  # PRDs the CTO could draft
    suggested_integrations: list[str]

    # Timestamps
    analysis_time: datetime = Field(default_factory=datetime.utcnow)


class PreMeetingBrief(BaseModel):
    """Generated before each meeting.

    Provides context for participants.
    """

    meeting_title: str
    scheduled_time: datetime
    participants: list[str]

    # Context
    recent_meetings_with_participants: list[str]
    outstanding_action_items: list[dict]

    # Status
    github_issues_mentioned: list[dict]
    sprint_status_summary: str

    # Preparation
    topics_likely_discussed: list[str]
    decisions_expected: list[str]
    context_to_have_ready: list[str]

    # Market context (if relevant)
    relevant_developments: list[str]

    # Generation timestamp
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class MeetingRecord(BaseModel):
    """Meeting metadata record."""

    meeting_id: str
    title: str
    meeting_date: datetime
    participants: list[str]
    duration_minutes: int | None = None
    meeting_type: str | None = None  # e.g., "Weekly Team Meeting", "Energy TWG"

    # Recall.ai integration
    recall_bot_id: str | None = None
    recall_transcript_id: str | None = None

    # Created timestamp
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TranscriptRecord(BaseModel):
    """Meeting transcript record."""

    meeting_id: str
    transcript_text: str
    raw_transcript: dict | None = None  # Full raw data from Recall.ai/AssemblyAI
    speaker_labels: bool = True  # Whether speakers are identified
    collected_at: datetime = Field(default_factory=datetime.utcnow)


class MeetingDecision(BaseModel):
    """Decision made in a meeting."""

    meeting_id: str
    decision: str
    decision_maker: str | None = None  # Who made the decision
    context: str | None = None  # Additional context
    impact: str | None = None  # Expected impact
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ActionItem(BaseModel):
    """Action item from a meeting or brief."""

    task: str
    owner: str
    meeting_id: str | None = None  # Linked to meeting
    brief_id: str | None = None  # Linked to brief
    due_date: datetime | None = None
    priority: str = "medium"  # low, medium, high, urgent
    status: str = "pending"  # pending, in_progress, complete, cancelled
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None


class MeetingIntelligenceState(BaseModel):
    """State for the Meeting Intelligence agent workflow."""

    query_type: MeetingQueryType = MeetingQueryType.STATUS
    query: str = ""

    # Input data
    meeting_id: str | None = None
    meeting_title: str | None = None
    meeting_date: datetime | None = None
    participants: list[str] = Field(default_factory=list)
    transcript: str | None = None
    transcript_id: str | None = None

    # Output
    analysis: MeetingAnalysis | None = None
    brief: PreMeetingBrief | None = None
    report: dict | None = None

    # Error handling
    error: str | None = None
