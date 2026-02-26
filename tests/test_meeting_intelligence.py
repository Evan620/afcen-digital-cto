"""Tests for Phase 3 Meeting Intelligence agent."""

import json
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

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


class TestAnalyzeMeeting:
    """Test the analyze_meeting node function."""

    @pytest.mark.asyncio
    async def test_returns_error_when_no_transcript(self):
        """Should return error when no transcript provided."""
        from src.agents.meeting_intelligence.agent import analyze_meeting

        state = {
            "meeting_title": "Test Meeting",
            "transcript": None,
        }
        result = await analyze_meeting(state)
        assert result.get("error") == "No transcript provided for analysis"

    @pytest.mark.asyncio
    async def test_analyze_meeting_with_llm_response(self):
        """Should parse LLM response into MeetingAnalysis."""
        from src.agents.meeting_intelligence.agent import analyze_meeting

        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "summary": "Discussed solar project timeline",
            "key_decisions": [
                {
                    "decision": "Approve Phase 2",
                    "decision_maker": "Joseph",
                    "context": "Budget review",
                    "impact": "High",
                }
            ],
            "action_items": [
                {
                    "task": "Draft SOW",
                    "owner": "Alice",
                    "due_date": "2026-03-01",
                    "priority": "high",
                }
            ],
            "technical_topics": ["Solar PV", "Grid integration"],
            "mentioned_systems": ["SCADA"],
            "pain_points": ["Permit delays"],
            "opportunities": ["New grant from AfDB"],
            "suggested_prds": [],
            "suggested_integrations": [],
        })

        state = {
            "meeting_title": "Energy TWG",
            "meeting_date": datetime(2026, 2, 25),
            "participants": ["Joseph", "Alice"],
            "transcript": "Joseph: Let's discuss the solar project...",
            "duration_minutes": 45,
        }

        with patch("src.agents.meeting_intelligence.agent.get_default_llm") as mock_llm, \
             patch("src.agents.meeting_intelligence.agent.store_analysis", new_callable=AsyncMock):
            mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)
            result = await analyze_meeting(state)

        analysis = result.get("analysis")
        assert analysis is not None
        assert analysis.summary == "Discussed solar project timeline"
        assert len(analysis.key_decisions) == 1
        assert len(analysis.action_items) == 1
        assert analysis.technical_topics == ["Solar PV", "Grid integration"]

    @pytest.mark.asyncio
    async def test_handles_llm_failure_gracefully(self):
        """Should return error dict on LLM failure, not raise."""
        from src.agents.meeting_intelligence.agent import analyze_meeting

        state = {
            "meeting_title": "Test",
            "meeting_date": datetime(2026, 2, 25),
            "participants": ["Alice"],
            "transcript": "Some transcript text",
        }

        with patch("src.agents.meeting_intelligence.agent.get_default_llm") as mock_llm:
            mock_llm.return_value.ainvoke = AsyncMock(side_effect=Exception("LLM down"))
            result = await analyze_meeting(state)

        assert "error" in result
        assert "Analysis failed" in result["error"]


class TestGenerateBrief:
    """Test the generate_brief node function."""

    @pytest.mark.asyncio
    async def test_generates_brief_with_context(self):
        """Should generate a PreMeetingBrief from LLM response."""
        from src.agents.meeting_intelligence.agent import generate_brief

        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "recent_meetings_with_participants": ["Previous TWG"],
            "outstanding_action_items": [],
            "github_issues_mentioned": [],
            "sprint_status_summary": "On track",
            "topics_likely_discussed": ["Budget review", "Timeline"],
            "decisions_expected": ["Approve milestone"],
            "context_to_have_ready": ["Budget spreadsheet"],
            "relevant_developments": ["New AfDB grant"],
        })

        state = {
            "meeting_title": "Energy TWG",
            "meeting_date": datetime(2026, 2, 25),
            "participants": ["Joseph", "Alice"],
            "meeting_type": "TWG",
        }

        with patch("src.agents.meeting_intelligence.agent.get_default_llm") as mock_llm, \
             patch("src.agents.meeting_intelligence.agent.assemble_pre_meeting_context", new_callable=AsyncMock) as mock_ctx, \
             patch("src.agents.meeting_intelligence.agent._get_github_status_for_brief", new_callable=AsyncMock) as mock_gh, \
             patch("src.agents.meeting_intelligence.agent._get_market_intel_for_brief", new_callable=AsyncMock) as mock_market:
            mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)
            mock_ctx.return_value = {"recent_meetings": [], "outstanding_action_items": []}
            mock_gh.return_value = "GitHub: Connected"
            mock_market.return_value = "Market Intel: No updates"
            result = await generate_brief(state)

        brief = result.get("brief")
        assert brief is not None
        assert brief.meeting_title == "Energy TWG"
        assert len(brief.topics_likely_discussed) == 2
        assert brief.context_to_have_ready == ["Budget spreadsheet"]

    @pytest.mark.asyncio
    async def test_handles_llm_failure_gracefully(self):
        """Should return error dict on LLM failure."""
        from src.agents.meeting_intelligence.agent import generate_brief

        state = {
            "meeting_title": "Test",
            "participants": ["Alice"],
        }

        with patch("src.agents.meeting_intelligence.agent.assemble_pre_meeting_context", new_callable=AsyncMock) as mock_ctx, \
             patch("src.agents.meeting_intelligence.agent._get_github_status_for_brief", new_callable=AsyncMock) as mock_gh, \
             patch("src.agents.meeting_intelligence.agent._get_market_intel_for_brief", new_callable=AsyncMock) as mock_market, \
             patch("src.agents.meeting_intelligence.agent.get_default_llm") as mock_llm:
            mock_ctx.return_value = {"recent_meetings": [], "outstanding_action_items": []}
            mock_gh.return_value = "GitHub: Unavailable"
            mock_market.return_value = "Market: Unavailable"
            mock_llm.return_value.ainvoke = AsyncMock(side_effect=Exception("LLM down"))
            result = await generate_brief(state)

        assert "error" in result


class TestCrossAgentHelpers:
    """Test the cross-agent integration helpers."""

    @pytest.mark.asyncio
    async def test_github_status_returns_fallback_on_error(self):
        """_get_github_status_for_brief should return fallback string on error."""
        from src.agents.meeting_intelligence.agent import _get_github_status_for_brief

        with patch("src.agents.meeting_intelligence.agent.settings") as mock_settings:
            # Force an import error by setting a bad attribute
            mock_settings.github_repository = ""
            result = await _get_github_status_for_brief()

        # Should return the fallback string, not raise
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_market_intel_returns_fallback_on_error(self):
        """_get_market_intel_for_brief should return fallback string on error."""
        from src.agents.meeting_intelligence.agent import _get_market_intel_for_brief

        with patch("src.agents.market_scanner.tools.MarketIntelStore") as mock_store:
            mock_store.return_value.get_recent_intel = AsyncMock(side_effect=Exception("DB down"))
            result = await _get_market_intel_for_brief()

        assert isinstance(result, str)
        assert "unavailable" in result.lower() or "Market Intel" in result


class TestRecallClientMock:
    """Test RecallClient with mocked HTTP responses."""

    @pytest.mark.asyncio
    async def test_health_check_without_api_key(self):
        """Should return False when no API key is configured."""
        from src.agents.meeting_intelligence.tools import RecallClient

        client = RecallClient(api_key="")
        result = await client.health_check()
        assert result is False
        await client.close()

    @pytest.mark.asyncio
    async def test_deploy_bot_raises_without_api_key(self):
        """Should raise ValueError when deploying without API key."""
        from src.agents.meeting_intelligence.tools import RecallClient

        client = RecallClient(api_key="")
        with pytest.raises(ValueError, match="not configured"):
            await client.deploy_bot(meeting_url="https://zoom.us/j/123")
        await client.close()

    @pytest.mark.asyncio
    async def test_get_transcript_without_api_key(self):
        """Should return None when no API key."""
        from src.agents.meeting_intelligence.tools import RecallClient

        client = RecallClient(api_key="")
        result = await client.get_transcript("bot_123")
        assert result is None
        await client.close()


class TestGetMeetingStatus:
    """Test the get_meeting_status convenience function."""

    @pytest.mark.asyncio
    async def test_returns_report_dict(self):
        """get_meeting_status should return the status report dict."""
        from src.agents.meeting_intelligence.agent import get_meeting_status

        mock_report = {
            "status": "operational",
            "recent_meetings_count": 5,
            "outstanding_action_items": 3,
            "recall_configured": False,
            "last_meeting": None,
        }

        with patch("src.agents.meeting_intelligence.agent.meeting_intelligence_graph") as mock_graph:
            mock_graph.ainvoke = AsyncMock(return_value={"report": mock_report})
            result = await get_meeting_status()

        assert result is not None
        assert result["status"] == "operational"
        assert result["recent_meetings_count"] == 5

    @pytest.mark.asyncio
    async def test_returns_none_on_failure(self):
        """get_meeting_status should return None on graph failure."""
        from src.agents.meeting_intelligence.agent import get_meeting_status

        with patch("src.agents.meeting_intelligence.agent.meeting_intelligence_graph") as mock_graph:
            mock_graph.ainvoke = AsyncMock(side_effect=Exception("Graph failure"))
            result = await get_meeting_status()

        assert result is None
