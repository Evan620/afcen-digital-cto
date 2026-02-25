"""Tests for Phase 3 Meeting Intelligence agent."""

import pytest
from datetime import datetime

from src.agents.meeting_intelligence.models import (
    MeetingQueryType,
    MeetingAnalysis,
    PreMeetingBrief,
    MeetingIntelligenceState,
    MeetingRecord,
    ActionItem,
    MeetingDecision,
)


class TestMeetingIntelligenceModels:
    """Test Meeting Intelligence data models."""

    def test_query_type_values(self):
        """MeetingQueryType should have all expected values."""
        assert MeetingQueryType.POST_MEETING.value == "post_meeting"
        assert MeetingQueryType.PRE_MEETING.value == "pre_meeting"
        assert MeetingQueryType.STATUS.value == "status"
        assert MeetingQueryType.TRANSCRIPT.value == "transcript"

    def test_meeting_analysis_creation(self):
        """MeetingAnalysis should create with all fields."""
        analysis = MeetingAnalysis(
            meeting_id="meeting_123",
            title="Weekly Standup",
            date=datetime.utcnow(),
            participants=["Alice", "Bob", "Charlie"],
            duration_minutes=30,
            summary="Discussed sprint progress",
            key_decisions=[
                {
                    "decision": "Approve feature X",
                    "decision_maker": "Alice",
                    "context": "Sprint planning",
                    "impact": "High",
                }
            ],
            action_items=[
                {
                    "task": "Update documentation",
                    "owner": "Bob",
                    "due_date": "2026-02-26",
                    "priority": "medium",
                }
            ],
            follow_ups=[],  # Required field
            technical_topics=["API", "database"],
            mentioned_systems=["platform", "auth"],
            pain_points=["Slow API response"],
            opportunities=["Cache optimization"],
            related_meetings=[],
            related_issues=[],
            related_prs=[],
            suggested_prds=[],
            suggested_integrations=["Redis"],
        )
        assert analysis.meeting_id == "meeting_123"
        assert len(analysis.key_decisions) == 1
        assert len(analysis.action_items) == 1
        assert analysis.technical_topics == ["API", "database"]

    def test_pre_meeting_brief_creation(self):
        """PreMeetingBrief should create with context."""
        brief = PreMeetingBrief(
            meeting_title="Energy TWG",
            scheduled_time=datetime.utcnow(),
            participants=["Alice", "Bob"],
            recent_meetings_with_participants=["Previous TWG meeting"],
            outstanding_action_items=[
                {"task": "Review PR", "owner": "Alice", "due_date": "2026-02-26"}
            ],
            github_issues_mentioned=[{"issue_id": 42, "title": "Bug fix", "status": "open"}],
            sprint_status_summary="Sprint on track",
            topics_likely_discussed=["Solar project", "Grid integration"],
            decisions_expected=["Approve milestone"],
            context_to_have_ready=["Project timeline", "Budget figures"],
            relevant_developments=["New funding available"],
        )
        assert brief.meeting_title == "Energy TWG"
        assert len(brief.topics_likely_discussed) == 2
        assert len(brief.context_to_have_ready) == 2

    def test_meeting_record_creation(self):
        """MeetingRecord should store metadata."""
        record = MeetingRecord(
            meeting_id="meeting_456",
            title="Platform Dev Standup",
            meeting_date=datetime.utcnow(),
            participants=["Dev Team"],
            duration_minutes=15,
            meeting_type="standup",
            recall_bot_id="bot_abc",
            recall_transcript_id="transcript_xyz",
        )
        assert record.meeting_id == "meeting_456"
        assert record.meeting_type == "standup"
        assert record.recall_bot_id == "bot_abc"

    def test_action_item_creation(self):
        """ActionItem should create with defaults."""
        item = ActionItem(
            task="Write documentation",
            owner="Alice",
            meeting_id="meeting_456",
            priority="high",
        )
        assert item.task == "Write documentation"
        assert item.owner == "Alice"
        assert item.status == "pending"
        assert item.priority == "high"

    def test_meeting_decision_creation(self):
        """MeetingDecision should store decision details."""
        decision = MeetingDecision(
            meeting_id="meeting_456",
            decision="Use PostgreSQL for new feature",
            decision_maker="CTO",
            context="Database selection for analytics",
            impact="Scalability improvement",
        )
        assert decision.decision == "Use PostgreSQL for new feature"
        assert decision.decision_maker == "CTO"
        assert decision.impact == "Scalability improvement"


class TestMeetingIntelligenceState:
    """Test MeetingIntelligenceState."""

    def test_default_state_structure(self):
        """MeetingIntelligenceState should have all expected keys."""
        state: MeetingIntelligenceState = {
            "query_type": MeetingQueryType.STATUS,
            "query": "",
            "meeting_id": None,
            "meeting_title": None,
            "meeting_date": None,
            "participants": [],
            "transcript": None,
            "transcript_id": None,
            "analysis": None,
            "brief": None,
            "report": None,
            "error": None,
        }
        assert state["query_type"] == MeetingQueryType.STATUS
        assert state["analysis"] is None
        assert state["brief"] is None


class TestMeetingIntelligenceIntegration:
    """Integration-style tests for Meeting Intelligence."""

    def test_recall_client_initialization(self):
        """RecallClient should initialize with API key."""
        from src.agents.meeting_intelligence.tools import RecallClient

        # Test without API key
        client = RecallClient(api_key="")
        assert client.api_key == ""

        # Test with API key
        client = RecallClient(api_key="test_key")
        assert client.api_key == "test_key"

    def test_meeting_store_initialization(self):
        """MeetingStore should initialize."""
        from src.agents.meeting_intelligence.tools import MeetingStore

        store = MeetingStore()
        assert store is not None
