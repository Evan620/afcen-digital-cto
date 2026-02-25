"""LLM prompts for the Market Scanner agent.

Templates for generating morning briefs and analyzing market intelligence.
"""

from __future__ import annotations


# ── Morning Brief Generation Prompt ──

MORNING_BRIEF_PROMPT = """You are the Digital CTO for the Africa Climate Energy Nexus (AfCEN).

Generate a concise, actionable morning brief for Joseph based on the market intelligence collected overnight.

## Context

AfCEN is a Pan-African climate energy nexus focused on:
- Energy access and renewable energy deployment
- Carbon markets and climate finance
- Agribusiness and sustainable agriculture
- Development Finance Institution (DFI) partnerships
- East African regional focus (Kenya, Ethiopia, Tanzania, Uganda)

## Instructions

Create a morning brief with these sections:

### 1. Market Moves (3-5 bullet points)
Notable overnight developments that affect AfCEN's mission. Focus on:
- Energy sector announcements
- Carbon market developments
- Major partnerships or investments
- Competitor activities

### 2. Policy Updates (2-4 bullet points)
Regulatory changes that impact operations:
- EUDR (EU Deforestation Regulation) updates
- Carbon tax changes
- Feed-in tariffs
- Cross-border energy policies

### 3. Funding & Partnership Opportunities (5-7 bullet points)
Actionable opportunities with:
- Source (World Bank, AfDB, IFC, etc.)
- Sector
- Funding amount (if available)
- Deadline
- AfCEN relevance

### 4. Competitive Intelligence (2-3 bullet points)
What competitors or similar organizations are doing.

### 5. Recommended Actions (3-5 prioritized items)
Specific actions Joseph should consider, with:
- Priority (HIGH/MEDIUM/LOW)
- Category (partnership/funding/compliance/competitive)
- Brief description
- Suggested deadline

## Input Data

{intel_data}

## Output Format

Return a JSON object with this structure:

```json
{{
  "market_moves": [
    {{
      "title": "Brief headline",
      "description": "1-2 sentence summary",
      "impact_level": "high|medium|low",
      "category": "partnership|funding|regulation|competition",
      "url": "source_url_if_available"
    }}
  ],
  "policy_updates": [
    {{
      "title": "Policy name",
      "jurisdiction": "EU/Kenya/EAC/etc",
      "policy_type": "EUDR/Carbon Tariff/etc",
      "description": "Brief description",
      "implications": ["implication 1", "implication 2"],
      "effective_date": "date if available"
    }}
  ],
  "funding_opportunities": [
    {{
      "source": "World Bank/AfDB/etc",
      "title": "Project/opportunity name",
      "description": "Brief description",
      "sector": "Energy/Agriculture/etc",
      "country": "Country name",
      "funding_amount": "$X if available",
      "status": "Open/Closing Soon/etc",
      "deadline": "date if available",
      "url": "source_url",
      "relevance_score": 0.8
    }}
  ],
  "competitive_intelligence": [
    "Brief point about competitor activity"
  ],
  "recommended_actions": [
    {{
      "priority": "high|medium|low",
      "category": "partnership|funding|compliance|competitive",
      "title": "Action title",
      "description": "What to do",
      "rationale": "Why this matters",
      "suggested_deadline": "timeframe"
    }}
  ],
  "sources_consulted": ["Source 1", "Source 2"]
}}
```

Keep each section concise. Prioritize actionability over completeness.
"""


# ── Market Intelligence Analysis Prompt ──

INTELLIGENCE_ANALYSIS_PROMPT = """Analyze the following market intelligence items and categorize them by relevance to AfCEN.

## AfCEN Focus Areas

1. **Energy Access**: Renewable energy deployment, mini-grids, geothermal, solar
2. **Carbon Markets**: Carbon credits, registries (Verra, Gold Standard), carbon finance
3. **Agribusiness**: Sustainable agriculture, smallholder farmers, data collection
4. **Climate Finance**: DFI partnerships, blended finance, grants
5. **East Africa**: Kenya, Ethiopia, Tanzania, Uganda, Rwanda

## Instructions

For each intelligence item:
1. Assign a relevance score (0.0-1.0)
2. Identify which focus areas it relates to
3. Extract key organizations mentioned
4. Suggest appropriate tags

## Input Intelligence

{intel_items}

## Output Format

For each item, return:

```json
{{
  "item_id": "identifier",
  "relevance_score": 0.8,
  "focus_areas": ["energy", "carbon_markets"],
  "tags": ["geothermal", "kenya", "world_bank"],
  "organizations": ["Organization 1", "Organization 2"],
  "region": "East Africa",
  "sector": "Energy"
}}
```
"""


# ── Pre-Meeting Brief Prompt ──

PRE_MEETING_BRIEF_PROMPT = """Generate a pre-meeting brief for Joseph based on upcoming meeting context.

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

### Relevant GitHub Status
{github_status}

### Relevant Market Intelligence
{market_intel}

## Instructions

Generate a concise pre-meeting brief that prepares Joseph with:
1. Context from recent interactions
2. Outstanding commitments
3. Relevant market developments
4. Topics likely to be discussed
5. Suggested preparation items

## Output Format

```json
{{
  "meeting_title": "Meeting title",
  "scheduled_time": "datetime",
  "participants": ["list"],
  "recent_meetings_with_participants": ["brief summaries"],
  "outstanding_action_items": [
    {{"task": "action item", "owner": "who", "due_date": "date"}}
  ],
  "github_issues_mentioned": [
    {{"issue_id": 123, "title": "issue", "status": "open"}}
  ],
  "sprint_status_summary": "brief status",
  "topics_likely_discussed": ["topic 1", "topic 2"],
  "decisions_expected": ["decision 1"],
  "context_to_have_ready": ["info to prepare"],
  "relevant_developments": ["recent market news"]
}}
```
"""


# ── Meeting Follow-up Prompt ──

MEETING_FOLLOWUP_PROMPT = """Generate actionable follow-up items from a meeting transcript.

## Meeting Details

- **Title**: {meeting_title}
- **Date**: {meeting_date}
- **Participants**: {participants}

## Transcript Summary

{transcript_summary}

## Decisions Made

{decisions}

## Instructions

Extract and format:
1. Action items with owners and due dates
2. PRDs that should be drafted
3. Follow-up commitments
4. Technical requirements mentioned
5. Integration opportunities identified

## Output Format

```json
{{
  "action_items": [
    {{
      "task": "description",
      "owner": "person/team",
      "due_date": "date",
      "priority": "high|medium|low"
    }}
  ],
  "suggested_prds": [
    {{
      "title": "PRD title",
      "description": "brief description",
      "estimated_effort": "3 weeks",
      "priority": "high|medium|low"
    }}
  ],
  "follow_ups": [
    {{
      "commitment": "what was committed",
      "owner": "who owns it",
      "deadline": "date"
    }}
  ],
  "technical_requirements": ["requirement 1", "requirement 2"],
  "integration_opportunities": ["opportunity 1"]
}}
```
"""


def get_morning_brief_prompt(intel_data: dict[str, any]) -> str:
    """Get the morning brief generation prompt with populated data."""
    # Format intel data for prompt
    formatted = []

    if news_items := intel_data.get("news_items"):
        formatted.append(f"## News Items ({len(news_items)})")
        for item in news_items[:20]:  # Limit to avoid token bloat
            formatted.append(f"- {item.title}: {item.summary[:200]}")

    if dfi_items := intel_data.get("dfi_opportunities"):
        formatted.append(f"\n## DFI Opportunities ({len(dfi_items)})")
        for item in dfi_items[:15]:
            formatted.append(f"- [{item.source}] {item.title}: {item.description[:200]}")

    if carbon_updates := intel_data.get("carbon_updates"):
        formatted.append(f"\n## Carbon Market Updates ({len(carbon_updates)})")
        for item in carbon_updates[:10]:
            formatted.append(f"- [{item.registry}] {item.project_name}: {item.update_type}")

    return MORNING_BRIEF_PROMPT.format(intel_data="\n".join(formatted))
