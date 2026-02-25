"""LLM prompts for the Meeting Intelligence agent.

Templates for meeting analysis and brief generation.
"""

from __future__ import annotations


# ── Post-Meeting Analysis Prompt ──

POST_MEETING_ANALYSIS_PROMPT = """You are the Digital CTO analyzing a meeting transcript.

Your task is to extract structured information from this meeting transcript.

## Meeting Details

- **Title**: {meeting_title}
- **Date**: {meeting_date}
- **Participants**: {participants}
- **Duration**: {duration_minutes} minutes

## Transcript

{transcript}

## Instructions

Extract and structure the following information:

### 1. Summary (2-3 sentences)
Brief overview of what was discussed.

### 2. Key Decisions
Extract all decisions made. For each:
- What was decided
- Who made the decision (if identifiable)
- Context/background
- Expected impact

### 3. Action Items
Extract all action items with:
- Task description
- Who is responsible
- Due date (if mentioned)
- Priority level

### 4. Technical Topics
List all technical topics, systems, or technologies mentioned.

### 5. Pain Points
Problems, issues, or blockers that were discussed.

### 6. Opportunities
Ideas, improvements, or possibilities mentioned.

### 7. Suggested PRDs
Based on the discussion, suggest any PRDs that should be drafted:
- Title
- Brief description
- Estimated effort
- Priority

### 8. Suggested Integrations
Any systems, tools, or services that should be integrated.

## Output Format

Return JSON only:

```json
{{
  "summary": "Brief meeting summary",
  "key_decisions": [
    {{
      "decision": "What was decided",
      "decision_maker": "Who decided",
      "context": "Background context",
      "impact": "Expected impact"
    }}
  ],
  "action_items": [
    {{
      "task": "Description",
      "owner": "Person/Team",
      "due_date": "Date if mentioned",
      "priority": "high|medium|low"
    }}
  ],
  "technical_topics": ["topic1", "topic2"],
  "mentioned_systems": ["system1", "system2"],
  "pain_points": ["issue1", "issue2"],
  "opportunities": ["opportunity1"],
  "suggested_prds": [
    {{
      "title": "PRD Title",
      "description": "Brief description",
      "estimated_effort": "2 weeks",
      "priority": "high|medium|low"
    }}
  ],
  "suggested_integrations": ["integration1"]
}}
```

Focus on actionable information. Be specific with task descriptions and ownership.
"""


# ── Pre-Meeting Brief Prompt ──

PRE_MEETING_BRIEF_PROMPT = """Generate a comprehensive pre-meeting brief for the Digital CTO.

## Meeting Details

- **Title**: {meeting_title}
- **Scheduled**: {meeting_time}
- **Participants**: {participants}
- **Type**: {meeting_type}

## Available Context

### Recent Meetings with These Participants
{recent_meetings}

### Outstanding Action Items
{action_items}

### GitHub Status
{github_status}

### Relevant Market Intelligence
{market_intel}

## Instructions

Generate a pre-meeting brief that prepares Joseph with all necessary context.

### 1. Recent Meeting Context
Summarize key points from recent meetings with the same participants.

### 2. Outstanding Items
List any pending action items or commitments relevant to these participants.

### 3. GitHub Status
Brief overview of relevant issues, PRs, or sprint status.

### 4. Topics Likely to Be Discussed
Based on the meeting type and context, what will probably be discussed?

### 5. Decisions Expected
What decisions might need to be made?

### 6. Context to Have Ready
What information, data, or documents should be prepared?

### 7. Relevant Market Developments
Any recent market news relevant to this meeting.

## Output Format

```json
{{
  "meeting_title": "Meeting title",
  "scheduled_time": "datetime",
  "participants": ["list"],
  "recent_meetings_with_participants": [
    "Summary of meeting 1",
    "Summary of meeting 2"
  ],
  "outstanding_action_items": [
    {{
      "task": "action item",
      "owner": "who",
      "due_date": "date"
    }}
  ],
  "github_issues_mentioned": [
    {{
      "issue_id": 123,
      "title": "issue",
      "status": "open"
    }}
  ],
  "sprint_status_summary": "Brief sprint status",
  "topics_likely_discussed": ["topic1", "topic2"],
  "decisions_expected": ["decision1"],
  "context_to_have_ready": ["info1", "info2"],
  "relevant_developments": ["market news1"]
}}
```
"""


def get_post_meeting_prompt(
    meeting_title: str,
    meeting_date: str,
    participants: str,
    duration_minutes: int,
    transcript: str,
) -> str:
    """Format the post-meeting analysis prompt with meeting data."""
    return POST_MEETING_ANALYSIS_PROMPT.format(
        meeting_title=meeting_title,
        meeting_date=meeting_date,
        participants=participants,
        duration_minutes=duration_minutes,
        transcript=transcript[:50000],  # Limit transcript length
    )


def get_pre_meeting_prompt(
    meeting_title: str,
    meeting_time: str,
    participants: str,
    meeting_type: str,
    recent_meetings: str,
    action_items: str,
    github_status: str,
    market_intel: str,
) -> str:
    """Format the pre-meeting brief prompt with meeting data."""
    return PRE_MEETING_BRIEF_PROMPT.format(
        meeting_title=meeting_title,
        meeting_time=meeting_time,
        participants=participants,
        meeting_type=meeting_type,
        recent_meetings=recent_meetings,
        action_items=action_items,
        github_status=github_status,
        market_intel=market_intel,
    )
