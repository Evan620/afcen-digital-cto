# AfCEN Digital CTO - Meeting Intelligence

## Overview

The Digital CTO eradicates the silo between engineering and strategic conversations by actively participating in AfCEN's meeting cadence, ensuring total real-time organizational context.

## AfCEN Meeting Ecosystem

| Meeting | Frequency | CTO Role |
|---------|-----------|----------|
| Weekly Team Meeting | Mondays | Cross-departmental bottleneck detection |
| Platform Dev Stand-up | Weekly | Blocked task identification |
| Energy TWG | Bi-weekly | Technical requirements extraction |
| Strategic Minerals TWG | Bi-weekly | Supply chain technical needs |
| Agribusiness TWG | Bi-weekly | Data collection architecture |

---

## Phase 1: Passive Observation (Weeks 9-10)

### Tool: Recall.ai

**Cost:** $0.15-0.25/minute (usage-based)

Recall.ai programmatically sends a bot to join Zoom, Teams, or Google Meet calls via REST API.

### Integration

```python
import httpx

async def deploy_meeting_bot(meeting_url: str, meeting_title: str):
    """Deploy Recall.ai bot to meeting."""
    response = await httpx.post(
        "https://api.recall.ai/api/v1/bot/",
        headers={"Authorization": f"Token {RECALL_API_KEY}"},
        json={
            "meeting_url": meeting_url,
            "transcription_options": {
                "provider": "deepgram",
                "language": "multi"  # Supports 30+ languages
            },
            "recording_options": {
                "audio": True,
                "video": False
            }
        }
    )
    return response.json()
```

### Why Recall.ai vs Google Meet Native

AfCEN's current Google Meet + Gemini transcription frequently fails with "not enough conversation in a supported language."

**Recall.ai advantages:**
- Supports 30+ languages via Deepgram
- OpenAI Whisper backend supports 99 languages
- Critical for multilingual African meetings

---

## Post-Meeting Analysis Pipeline

### Tool: AssemblyAI LeMUR

**Cost:** $0.37/hour async transcription + token-based LLM costs

LeMUR directly integrates LLMs with transcript data.

### Pipeline

```
┌─────────────────────────────────────────────────────┐
│  1. RECEIVE TRANSCRIPT                              │
│     (from Recall.ai)                                │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│  2. STRUCTURED SUMMARY                              │
│     - Key decisions made                            │
│     - Action items with assignees                   │
│     - Follow-up commitments                         │
│     - Technical topics mentioned                    │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│  3. STORAGE                                         │
│     - PostgreSQL: Metadata, decisions               │
│     - Qdrant: Searchable transcript chunks          │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│  4. PROACTIVE OUTPUT                                │
│     - Technical recommendations                     │
│     - PRD drafts for discussed needs                │
│     - Integration proposals                         │
└─────────────────────────────────────────────────────┘
```

### Output Model

```python
class MeetingAnalysis(BaseModel):
    """Post-meeting structured analysis."""
    meeting_id: str
    title: str
    date: datetime
    participants: list[str]
    duration_minutes: int

    # Core analysis
    summary: str
    key_decisions: list[dict]  # Decision, who made it, context
    action_items: list[dict]   # Task, assignee, due date
    follow_ups: list[dict]     # Commitment, owner, deadline

    # Technical extraction
    technical_topics: list[str]
    mentioned_systems: list[str]  # Platform components referenced
    pain_points: list[str]        # Problems discussed
    opportunities: list[str]      # Ideas worth exploring

    # Cross-reference
    related_meetings: list[str]   # Past meetings on similar topics
    related_issues: list[int]     # GitHub issues mentioned
    related_prs: list[int]        # PRs discussed

    # Proactive recommendations
    suggested_prds: list[dict]    # PRDs the CTO could draft
    suggested_integrations: list[str]
```

---

## Phase 2: Pre-Meeting Intelligence (Weeks 11-12)

### Before Each Meeting

The CTO agent generates a pre-meeting brief by querying:

| Source | Query |
|--------|-------|
| Past transcripts | Meetings with same participants |
| GitHub | Open issues, sprint status |
| Action items | Previous items due before this meeting |
| Market intel | Relevant developments since last meeting |

### Pre-Meeting Brief Structure

```python
class PreMeetingBrief(BaseModel):
    """Generated before each meeting."""
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
```

---

## Phase 3: Active Participation (Months 4-6)

### Technical Pipeline

```
Recall.ai audio stream
        │
        ▼
Deepgram real-time STT ($0.0059/minute)
        │
        ▼
LLM processes + formulates response
        │
        ▼
OpenAI TTS / ElevenLabs speech synthesis
        │
        ▼
Recall.ai outputs audio to meeting
```

### Latency Requirements

- **Target:** <2-3 seconds round-trip
- **Critical for:** Natural conversation feel
- **Achievable with:** Careful optimization

### Prerequisites

- ✅ Passive system thoroughly proven
- ✅ Trust established through accurate summaries
- ✅ Clear guidelines on when CTO speaks
- ✅ Fallback to text-only if latency issues

### Active Participation Rules

1. **Speak only when:**
   - Directly addressed
   - Technical clarification needed
   - Action item needs assignment

2. **Defer to humans:**
   - Strategic decisions
   - Priority conflicts
   - Stakeholder management

3. **Never:**
   - Interrupt speakers
   - Dominate conversation
   - Make commitments without approval

---

## Proactive Product Development

### How CTO Generates Solutions

When stakeholders discuss challenges, the CTO processes in real-time:

1. **Identify** the problem being discussed
2. **Cross-reference** against existing platform capabilities
3. **Draft** a PRD for potential solution
4. **Estimate** development cost
5. **Map** integration points
6. **Present** to CEO as strategic recommendation

### Example Flow

```
Agribusiness TWG discusses:
"How to standardize data collection from 1,500 smallholder farmers?"

CTO processes:
├── Cross-reference with existing AfCEN platform
├── Identify gap: No mobile data collection module
├── Draft PRD: "Mobile Data Collection for Smallholders"
├── Estimate: 3 weeks, $15K
├── Integration: Connects to existing farmer registry
└── Present to CEO with recommendation
```

---

## Cost Summary

| Phase | Tool | Monthly Cost (40 meetings) |
|-------|------|----------------------------|
| Phase 1 | Recall.ai | $200-400 |
| Phase 1 | AssemblyAI | $50-100 |
| Phase 3 | Deepgram (streaming) | $15 |
| Phase 3 | TTS (ElevenLabs/OpenAI) | $50-100 |
| **Total** | | **$315-615/month** |
