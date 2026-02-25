"""Meeting Intelligence tools for the Meeting Intelligence agent.

Integrations with Recall.ai for meeting bots and transcript handling.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

import httpx

from src.config import settings
from src.memory.postgres_store import PostgresStore

logger = logging.getLogger(__name__)


# ── Recall.ai Client ──


class RecallClient:
    """Client for Recall.ai meeting bot API.

    Recall.ai deploys bots to Zoom, Teams, and Google Meet for
    transcription and recording.
    """

    BASE_URL = "https://api.recall.ai/api/v1"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.recall_api_key
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={"Authorization": f"Token {self.api_key}"},
            timeout=30.0,
        )

    async def health_check(self) -> bool:
        """Check if Recall.ai API is accessible."""
        if not self.api_key:
            return False
        try:
            response = await self.client.get("/bots")
            return response.status_code == 200
        except Exception as e:
            logger.debug("Recall.ai health check failed: %s", e)
            return False

    async def deploy_bot(
        self,
        meeting_url: str,
        meeting_title: str = "",
        transcription_options: dict | None = None,
    ) -> dict[str, Any]:
        """Deploy a Recall.ai bot to a meeting.

        Args:
            meeting_url: URL of the meeting (Zoom, Teams, Google Meet)
            meeting_title: Optional title for the meeting
            transcription_options: Options for transcription

        Returns:
            Bot deployment response with bot_id
        """
        if not self.api_key:
            raise ValueError("Recall.ai API key not configured")

        defaults = {
            "provider": "deepgram",
            "language": "multi",  # Supports 30+ languages
        }
        transcription = transcription_options or defaults

        payload = {
            "meeting_url": meeting_url,
            "meeting_title": meeting_title,
            "transcription_options": transcription,
            "recording_options": {
                "audio": True,
                "video": False,
            },
        }

        logger.info("Deploying Recall.ai bot to meeting: %s", meeting_title)

        try:
            response = await self.client.post("/bot/", json=payload)
            response.raise_for_status()
            result = response.json()
            logger.info("Bot deployed successfully: %s", result.get("bot_id"))
            return result
        except Exception as e:
            logger.error("Failed to deploy Recall.ai bot: %s", e)
            raise

    async def get_transcript(self, bot_id: str) -> dict[str, Any] | None:
        """Get transcript from a completed meeting bot.

        Args:
            bot_id: The bot ID from deployment

        Returns:
            Transcript data with text, speakers, timestamps
        """
        if not self.api_key:
            return None

        try:
            response = await self.client.get(f"/bot/{bot_id}/transcript")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("Failed to get transcript for bot %s: %s", bot_id, e)
            return None

    async def get_bot_status(self, bot_id: str) -> dict[str, Any] | None:
        """Get the status of a deployed bot.

        Args:
            bot_id: The bot ID to check

        Returns:
            Bot status including state (processing, ready, etc.)
        """
        if not self.api_key:
            return None

        try:
            response = await self.client.get(f"/bot/{bot_id}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("Failed to get bot status for %s: %s", bot_id, e)
            return None

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()


# ── Meeting Store ──


class MeetingStore:
    """Store and retrieve meeting records from PostgreSQL."""

    def __init__(self):
        self.store = PostgresStore()

    async def save_meeting(
        self,
        meeting_id: str,
        title: str,
        meeting_date: datetime,
        participants: list[str],
        duration_minutes: int | None = None,
        meeting_type: str | None = None,
        recall_bot_id: str | None = None,
        recall_transcript_id: str | None = None,
    ) -> int:
        """Save a meeting record."""
        return await self.store.save_meeting(
            meeting_id=meeting_id,
            title=title,
            meeting_date=meeting_date,
            participants=participants,
            duration_minutes=duration_minutes,
            meeting_type=meeting_type,
            recall_bot_id=recall_bot_id,
            recall_transcript_id=recall_transcript_id,
        )

    async def save_transcript(
        self,
        meeting_id: str,
        transcript_text: str,
        raw_transcript: dict | None = None,
        speaker_labels: bool = True,
    ) -> int:
        """Save a meeting transcript."""
        return await self.store.save_transcript(
            meeting_id=meeting_id,
            transcript_text=transcript_text,
            raw_transcript=raw_transcript,
            speaker_labels=speaker_labels,
        )

    async def save_decision(
        self,
        meeting_id: str,
        decision: str,
        decision_maker: str | None = None,
        context: str | None = None,
        impact: str | None = None,
    ) -> int:
        """Save a meeting decision."""
        return await self.store.save_decision(
            meeting_id=meeting_id,
            decision=decision,
            decision_maker=decision_maker,
            context=context,
            impact=impact,
        )

    async def save_action_items(
        self,
        action_items: list[dict],
        meeting_id: str | None = None,
        brief_id: str | None = None,
    ) -> list[int]:
        """Save multiple action items."""
        ids = []
        for item in action_items:
            id = await self.store.save_action_item(
                task=item.get("task", ""),
                owner=item.get("owner", ""),
                meeting_id=meeting_id,
                brief_id=brief_id,
                due_date=self._parse_date(item.get("due_date")),
                priority=item.get("priority", "medium"),
                status=item.get("status", "pending"),
            )
            ids.append(id)
        return ids

    async def get_meeting(self, meeting_id: str) -> dict | None:
        """Get meeting record by ID."""
        try:
            from sqlalchemy import select
            from src.memory.postgres_store import MeetingRecord

            async with self.store.session() as session:
                stmt = select(MeetingRecord).where(MeetingRecord.meeting_id == meeting_id)
                result = await session.execute(stmt)
                row = result.scalar_one_or_none()

                if not row:
                    return None

                return {
                    "id": row.id,
                    "meeting_id": row.meeting_id,
                    "title": row.title,
                    "meeting_date": row.meeting_date.isoformat() if row.meeting_date else None,
                    "participants": row.participants or [],
                    "duration_minutes": row.duration_minutes,
                    "meeting_type": row.meeting_type,
                    "recall_bot_id": row.recall_bot_id,
                    "recall_transcript_id": row.recall_transcript_id,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
        except Exception as e:
            logger.error("Failed to get meeting %s: %s", meeting_id, e)
            return None

    async def get_recent_meetings(self, days: int = 30, limit: int = 50) -> list[dict]:
        """Get recent meetings."""
        return await self.store.get_recent_meetings(days=days, limit=limit)

    async def get_outstanding_actions(self, owner: str | None = None) -> list[dict]:
        """Get outstanding action items."""
        return await self.store.get_outstanding_actions(owner=owner)

    def _parse_date(self, date_str: str | None) -> datetime | None:
        """Parse various date formats."""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str)
        except Exception:
            return None


# ── Transcript Analysis ──


async def analyze_transcript(
    transcript: str,
    meeting_title: str,
    meeting_date: str,
    participants: str,
    duration_minutes: int,
) -> dict[str, Any]:
    """Analyze a meeting transcript using LLM.

    This is a placeholder - the actual analysis happens in the agent's LLM call.
    """
    # The agent will handle the actual LLM analysis
    # This function is for preprocessing if needed
    return {
        "transcript_length": len(transcript),
        "word_count": len(transcript.split()),
        "estimated_speakers": participants.count(",") + 1 if participants else 0,
    }


# ── Pre-Meeting Context Assembly ──


async def assemble_pre_meeting_context(
    participants: list[str],
    meeting_type: str | None = None,
) -> dict[str, Any]:
    """Assemble context for pre-meeting brief generation.

    Args:
        participants: List of meeting participants
        meeting_type: Type of meeting (TWG, standup, etc.)

    Returns:
        Context dict with recent meetings, action items, etc.
    """
    store = MeetingStore()

    # Get recent meetings with these participants
    recent_meetings = await store.get_recent_meetings(days=30, limit=10)

    # Filter by participant overlap
    relevant_meetings = []
    for meeting in recent_meetings:
        meeting_participants = meeting.get("participants", [])
        if any(p in participants for p in meeting_participants):
            relevant_meetings.append(meeting)

    # Get outstanding action items
    outstanding = await store.get_outstanding_actions()

    return {
        "recent_meetings": relevant_meetings[:5],
        "outstanding_action_items": outstanding[:10],
        "participant_count": len(participants),
        "meeting_type": meeting_type,
    }
