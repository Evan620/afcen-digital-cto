"""Market Scanner Agent — LangGraph subgraph for market intelligence.

Collects data from multiple sources (news, DFI databases, carbon registries)
and generates structured morning briefs for the CEO.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from src.agents.market_scanner.models import (
    MarketIntelItem,
    MarketScannerQueryType,
    MarketScannerState,
    MorningBrief,
)
from src.agents.market_scanner.prompts import (
    get_morning_brief_prompt,
    INTELLIGENCE_ANALYSIS_PROMPT,
)
from src.agents.market_scanner.tools import (
    collect_all_sources,
    MarketIntelStore,
    RSSFeedCollector,
    WorldBankClient,
    VerraRegistryClient,
    GoldStandardClient,
    AfDBClient,
)
from src.config import settings
from src.llm.utils import get_default_llm, extract_json_from_llm_output

logger = logging.getLogger(__name__)


# ── Node Functions ──


async def collect_data(state: MarketScannerState) -> dict:
    """Collect market intelligence from all enabled sources."""
    logger.info("Starting market data collection...")

    hours_back = 24  # Collect last 24 hours
    sources_succeeded = []
    sources_failed = {}

    intel_items = []
    dfi_opportunities = []
    carbon_updates = []

    # RSS feeds
    try:
        rss = RSSFeedCollector()
        news_items = await rss.collect(hours_back=hours_back)
        intel_items.extend(news_items)
        sources_succeeded.append("RSS Feeds")
        logger.info("Collected %d news items from RSS feeds", len(news_items))
    except Exception as e:
        sources_failed["RSS Feeds"] = str(e)
        logger.error("RSS collection failed: %s", e)

    # World Bank
    try:
        wb = WorldBankClient()
        dfi = await wb.collect_opportunities(days_back=30)
        dfi_opportunities.extend(dfi)
        sources_succeeded.append("World Bank")
        logger.info("Collected %d World Bank opportunities", len(dfi))
    except Exception as e:
        sources_failed["World Bank"] = str(e)
        logger.error("World Bank collection failed: %s", e)

    # Verra Carbon Registry
    try:
        verra = VerraRegistryClient()
        verra_updates = await verra.collect_updates(days_back=30)
        carbon_updates.extend(verra_updates)
        sources_succeeded.append("Verra Registry")
        logger.info("Collected %d Verra carbon updates", len(verra_updates))
    except Exception as e:
        sources_failed["Verra Registry"] = str(e)
        logger.error("Verra collection failed: %s", e)

    # Gold Standard Registry
    try:
        gs = GoldStandardClient()
        gs_updates = await gs.collect_updates(days_back=30)
        carbon_updates.extend(gs_updates)
        sources_succeeded.append("Gold Standard")
        logger.info("Collected %d Gold Standard carbon updates", len(gs_updates))
    except Exception as e:
        sources_failed["Gold Standard"] = str(e)
        logger.error("Gold Standard collection failed: %s", e)

    # African Development Bank
    try:
        afdb = AfDBClient()
        afdb_opps = await afdb.collect_opportunities(days_back=30)
        dfi_opportunities.extend(afdb_opps)
        sources_succeeded.append("AfDB")
        logger.info("Collected %d AfDB opportunities", len(afdb_opps))
    except Exception as e:
        sources_failed["AfDB"] = str(e)
        logger.error("AfDB collection failed: %s", e)

    # Store collected intel
    if intel_items:
        try:
            store = MarketIntelStore()
            new_count = await store.save_intel(intel_items)
            logger.info("Saved %d new intel items to database", new_count)
        except Exception as e:
            logger.error("Failed to save intel to database: %s", e)

    return {
        "intel_items": intel_items,
        "dfi_opportunities": dfi_opportunities,
        "carbon_updates": carbon_updates,
        "sources_succeeded": sources_succeeded,
        "sources_failed": sources_failed,
    }


async def retrieve_intel(state: MarketScannerState) -> dict:
    """Retrieve relevant market intelligence from storage."""
    logger.info("Retrieving market intelligence from database...")

    try:
        store = MarketIntelStore()
        intel_items = await store.get_recent_intel(hours=24, min_relevance=0.3, limit=100)

        logger.info("Retrieved %d intel items from database", len(intel_items))

        return {"intel_items": intel_items}

    except Exception as e:
        logger.error("Failed to retrieve intel: %s", e)
        return {"error": f"Failed to retrieve intel: {e}"}


async def generate_brief(state: MarketScannerState) -> dict:
    """Generate morning brief from collected intelligence."""
    logger.info("Generating morning brief...")

    intel_data = {
        "news_items": state.get("intel_items", []),
        "dfi_opportunities": state.get("dfi_opportunities", []),
        "carbon_updates": state.get("carbon_updates", []),
    }

    # Check we have data
    total_items = (
        len(intel_data["news_items"]) +
        len(intel_data["dfi_opportunities"]) +
        len(intel_data["carbon_updates"])
    )

    if total_items == 0:
        logger.warning("No intelligence data available for brief generation")
        return {
            "brief": MorningBrief(
                brief_id=f"brief_{datetime.utcnow().strftime('%Y%m%d')}",
                intel_items_collected=0,
                generation_time=datetime.utcnow(),
            ),
            "report": {
                "status": "no_data",
                "message": "No intelligence data available",
            },
        }

    try:
        llm = get_default_llm(temperature=0.2)
        prompt = get_morning_brief_prompt(intel_data)

        response = await llm.ainvoke(prompt)
        response_text = response.content if hasattr(response, "content") else str(response)

        # Extract JSON from response
        brief_data = extract_json_from_llm_output(response_text)

        if not brief_data:
            logger.warning("Failed to extract JSON from LLM response, creating minimal brief")
            brief_data = {}

        # Create MorningBrief from parsed data
        brief = MorningBrief(
            brief_id=f"brief_{datetime.utcnow().strftime('%Y%m%d')}",
            market_moves=brief_data.get("market_moves", []),
            policy_updates=brief_data.get("policy_updates", []),
            funding_opportunities=brief_data.get("funding_opportunities", []),
            carbon_market_updates=intel_data.get("carbon_updates", []),
            competitive_intelligence=brief_data.get("competitive_intelligence", []),
            recommended_actions=brief_data.get("recommended_actions", []),
            sources_consulted=brief_data.get("sources_consulted", state.get("sources_succeeded", [])),
            intel_items_collected=total_items,
            generation_time=datetime.utcnow(),
        )

        logger.info(
            "Morning brief generated: %d market moves, %d policy updates, %d opportunities",
            len(brief.market_moves),
            len(brief.policy_updates),
            len(brief.funding_opportunities),
        )

        return {
            "brief": brief,
            "report": {
                "status": "success",
                "brief_id": brief.brief_id,
                "market_moves": len(brief.market_moves),
                "policy_updates": len(brief.policy_updates),
                "funding_opportunities": len(brief.funding_opportunities),
                "recommended_actions": len(brief.recommended_actions),
                "sources_succeeded": state.get("sources_succeeded", []),
                "sources_failed": state.get("sources_failed", {}),
            },
        }

    except Exception as e:
        logger.error("Failed to generate morning brief: %s", e)

        # Return error brief
        return {
            "brief": MorningBrief(
                brief_id=f"brief_{datetime.utcnow().strftime('%Y%m%d')}",
                intel_items_collected=total_items,
                generation_time=datetime.utcnow(),
            ),
            "error": f"Brief generation failed: {e}",
            "report": {
                "status": "error",
                "message": str(e),
            },
        }


async def enrich_intel(state: MarketScannerState) -> dict:
    """Enrich intel items with LLM-based categorization using INTELLIGENCE_ANALYSIS_PROMPT.

    Adds relevance scores, tags, region, sector, and organizations to items
    that don't already have them. Non-fatal on failure — items keep their
    keyword-based scores.
    """
    intel_items = state.get("intel_items", [])

    # Filter to items that need enrichment (no tags or sector)
    needs_enrichment = [
        item for item in intel_items
        if not item.tags and not item.sector
    ]

    if not needs_enrichment:
        logger.debug("No intel items need enrichment, skipping")
        return {}

    # Batch up to 20 items per LLM call to stay within token budget
    batch = needs_enrichment[:20]

    try:
        llm = get_default_llm(temperature=0.2)

        # Format items for the prompt
        items_text = []
        for i, item in enumerate(batch):
            items_text.append(
                f"[{i}] {item.title}: {item.summary[:200]}"
                f" (source: {item.source_name}, url: {item.url or 'N/A'})"
            )

        prompt = INTELLIGENCE_ANALYSIS_PROMPT.format(
            intel_items="\n".join(items_text)
        )

        response = await llm.ainvoke(prompt)
        response_text = response.content if hasattr(response, "content") else str(response)

        enrichments = extract_json_from_llm_output(response_text)

        if not enrichments:
            logger.warning("Failed to parse enrichment response, skipping")
            return {}

        # Handle both list and dict responses
        if isinstance(enrichments, dict):
            enrichment_list = enrichments.get("items", enrichments.get("results", [enrichments]))
        else:
            enrichment_list = enrichments

        if not isinstance(enrichment_list, list):
            enrichment_list = [enrichment_list]

        # Merge enrichments back into items
        for enrichment in enrichment_list:
            if not isinstance(enrichment, dict):
                continue

            # Match by item_id (index) or by title
            item_id = enrichment.get("item_id")
            target_item = None

            if item_id is not None:
                try:
                    idx = int(item_id) if not isinstance(item_id, int) else item_id
                    if 0 <= idx < len(batch):
                        target_item = batch[idx]
                except (ValueError, TypeError):
                    pass

            if target_item is None:
                continue

            # Merge enrichment data
            if score := enrichment.get("relevance_score"):
                try:
                    target_item.relevance_score = float(score)
                except (ValueError, TypeError):
                    pass
            if tags := enrichment.get("tags"):
                target_item.tags = tags if isinstance(tags, list) else [tags]
            if region := enrichment.get("region"):
                target_item.region = region
            if sector := enrichment.get("sector"):
                target_item.sector = sector
            if orgs := enrichment.get("organizations"):
                target_item.organizations = orgs if isinstance(orgs, list) else [orgs]

        logger.info("Enriched %d intel items via LLM", len(enrichment_list))

    except Exception as e:
        logger.warning("Intel enrichment failed (non-fatal): %s", e)

    return {"intel_items": intel_items}


async def save_brief(state: MarketScannerState) -> dict:
    """Save morning brief to database for delivery."""
    brief = state.get("brief")

    if not brief:
        return {"error": "No brief to save"}

    logger.info("Saving morning brief %s to database...", brief.brief_id)

    try:
        from src.memory.postgres_store import PostgresStore

        store = PostgresStore()

        # Serialize brief for storage
        brief_dict = {
            "brief_id": brief.brief_id,
            "brief_date": brief.brief_date,
            "market_moves": [m.model_dump() for m in brief.market_moves],
            "policy_updates": [p.model_dump() for p in brief.policy_updates],
            "funding_opportunities": [f.model_dump() for f in brief.funding_opportunities],
            "carbon_market_updates": [c.model_dump() for c in brief.carbon_market_updates],
            "competitive_intelligence": brief.competitive_intelligence,
            "recommended_actions": [a.model_dump() for a in brief.recommended_actions],
            "sources_consulted": brief.sources_consulted,
            "intel_items_collected": brief.intel_items_collected,
            "generation_time": brief.generation_time,
            "delivered": brief.delivered,
        }

        await store.save_report("morning_brief", brief_dict, notified=False)

        logger.info("Morning brief %s saved successfully", brief.brief_id)

        return {}

    except Exception as e:
        logger.error("Failed to save morning brief: %s", e)
        return {"error": f"Failed to save brief: {e}"}


async def notify_jarvis(state: MarketScannerState) -> dict:
    """Send morning brief to JARVIS via OpenClaw."""
    brief = state.get("brief")

    if not brief:
        return {}

    logger.info("Sending morning brief to JARVIS...")

    try:
        from src.integrations.openclaw_client import get_openclaw_client

        client = get_openclaw_client()
        if not client.is_connected:
            logger.debug("JARVIS not connected, skipping notification")
            return {}

        # Format brief for JARVIS
        message = f"""Good morning Joseph. Here is your Digital CTO Morning Brief for {brief.brief_date.strftime('%B %d, %Y')}.

## Market Moves ({len(brief.market_moves)})
"""
        for move in brief.market_moves[:5]:
            message += f"- {move['title']}: {move['description']}\n"

        if brief.policy_updates:
            message += f"\n## Policy Updates ({len(brief.policy_updates)})\n"
            for update in brief.policy_updates[:3]:
                message += f"- {update['title']}: {update['description']}\n"

        if brief.funding_opportunities:
            message += f"\n## Funding Opportunities ({len(brief.funding_opportunities)})\n"
            for opp in brief.funding_opportunities[:5]:
                message += f"- [{opp['source']}] {opp['title']}: {opp['description'][:100]}...\n"

        if brief.recommended_actions:
            message += "\n## Recommended Actions\n"
            for action in brief.recommended_actions[:5]:
                message += f"- [{action['priority'].upper()}] {action['title']}: {action['description']}\n"

        await client.send_agent_message(
            recipient="jarvis",
            message=message,
            context={
                "type": "morning_brief",
                "brief_id": brief.brief_id,
                "brief_date": brief.brief_date.isoformat(),
            },
        )

        logger.info("Morning brief sent to JARVIS")

        # Update delivered status
        brief.delivered = True
        brief.delivery_time = datetime.utcnow()
        return {"brief": brief}

    except Exception as e:
        logger.error("Failed to notify JARVIS: %s", e)
        return {"error": f"JARVIS notification failed: {e}"}


async def generate_status(state: MarketScannerState) -> dict:
    """Generate a status report for the market scanner."""
    query_type = state.get("query_type", MarketScannerQueryType.STATUS)

    try:
        store = MarketIntelStore()
        intel_items = await store.get_recent_intel(hours=24, min_relevance=0.0)

        report = {
            "status": "operational",
            "query_type": query_type,
            "intel_items_last_24h": len(intel_items),
            "high_relevance_count": sum(1 for i in intel_items if i.relevance_score >= 0.7),
            "sources_active": ["RSS Feeds", "World Bank", "Verra Registry", "Gold Standard", "AfDB"],
            "last_collection": datetime.utcnow().isoformat(),
            "briefs_generated_last_7_days": await store.get_briefs_count_last_7_days(),
        }

        return {"report": report}

    except Exception as e:
        logger.error("Failed to generate status: %s", e)
        return {"error": f"Status generation failed: {e}"}


async def handle_error(state: MarketScannerState) -> dict:
    """Handle errors in the market scanner workflow."""
    error = state.get("error", "Unknown error")
    logger.error("Market scanner error: %s", error)

    return {"report": {"status": "error", "message": error}}


# ── Routing Logic ──


def route_after_query_type(state: MarketScannerState) -> str:
    """Route to appropriate workflow based on query type."""
    query_type = state.get("query_type", MarketScannerQueryType.STATUS)

    if query_type == MarketScannerQueryType.COLLECT:
        return "collect_data"
    elif query_type == MarketScannerQueryType.BRIEF:
        return "retrieve_intel"
    elif query_type == MarketScannerQueryType.STATUS:
        return "generate_status"
    else:
        return "handle_error"


def route_after_retrieval(state: MarketScannerState) -> str:
    """Route after retrieving intel (brief generation path)."""
    if state.get("error"):
        return "handle_error"
    return "generate_brief"


def route_after_generation(state: MarketScannerState) -> str:
    """Route after brief generation."""
    if state.get("error"):
        return "handle_error"
    return "save_brief"


def route_after_save(state: MarketScannerState) -> str:
    """Route after saving brief."""
    # Try to notify JARVIS but don't fail if it's not available
    return "notify_jarvis"


# ── Build the Graph ──


def build_market_scanner_graph() -> StateGraph:
    """Construct the Market Scanner agent as a LangGraph StateGraph.

    Workflows:
    - COLLECT: collect_data → enrich_intel → END
    - BRIEF: retrieve_intel → generate_brief → save_brief → notify_jarvis → END
    - STATUS: generate_status → END
    """
    graph = StateGraph(MarketScannerState)

    # Add a router node that dispatches based on query_type
    graph.add_node("router", lambda state: state)

    # Add workflow nodes
    graph.add_node("collect_data", collect_data)
    graph.add_node("enrich_intel", enrich_intel)
    graph.add_node("retrieve_intel", retrieve_intel)
    graph.add_node("generate_brief", generate_brief)
    graph.add_node("save_brief", save_brief)
    graph.add_node("notify_jarvis", notify_jarvis)
    graph.add_node("generate_status", generate_status)
    graph.add_node("handle_error", handle_error)

    # Entry point
    graph.set_entry_point("router")

    # Conditional routing from router based on query_type
    graph.add_conditional_edges(
        "router",
        route_after_query_type,
        {
            "collect_data": "collect_data",
            "retrieve_intel": "retrieve_intel",
            "generate_status": "generate_status",
            "handle_error": "handle_error",
        },
    )

    # Brief workflow edges
    graph.add_conditional_edges("retrieve_intel", route_after_retrieval, {
        "generate_brief": "generate_brief",
        "handle_error": "handle_error",
    })

    graph.add_conditional_edges("generate_brief", route_after_generation, {
        "save_brief": "save_brief",
        "handle_error": "handle_error",
    })

    graph.add_conditional_edges("save_brief", route_after_save, {
        "notify_jarvis": "notify_jarvis",
    })

    # Collect workflow: collect_data → enrich_intel → END
    graph.add_edge("collect_data", "enrich_intel")

    # Terminal edges
    graph.add_edge("enrich_intel", END)
    graph.add_edge("notify_jarvis", END)
    graph.add_edge("generate_status", END)
    graph.add_edge("handle_error", END)

    return graph


# Compiled graph
market_scanner_graph = build_market_scanner_graph().compile()


# ── Convenience Functions ──


def _default_state(
    query_type: str = MarketScannerQueryType.STATUS.value,
    **kwargs,
) -> dict:
    """Create a default state for the market scanner."""
    return {
        "query_type": query_type,
        "query": kwargs.get("query", ""),
        "date_range": kwargs.get("date_range"),
        "intel_items": [],
        "dfi_opportunities": [],
        "carbon_updates": [],
        "brief": None,
        "report": None,
        "error": None,
        "sources_succeeded": [],
        "sources_failed": {},
    }


async def collect_market_data(hours_back: int = 24) -> dict:
    """Collect market data from all sources.

    Returns summary of what was collected.
    """
    return await collect_all_sources(hours_back=hours_back)


async def generate_morning_brief() -> MorningBrief | None:
    """Generate a morning brief from recent intelligence.

    This is the main entry point for scheduled morning brief generation.
    """
    state = _default_state(query_type=MarketScannerQueryType.BRIEF.value)

    try:
        result = await market_scanner_graph.ainvoke(state)
        return result.get("brief")

    except Exception as e:
        logger.error("Morning brief generation failed: %s", e)
        return None


async def get_market_scanner_status() -> dict | None:
    """Get the current status of market intelligence collection."""
    state = _default_state(query_type=MarketScannerQueryType.STATUS.value)

    try:
        result = await market_scanner_graph.ainvoke(state)
        return result.get("report")

    except Exception as e:
        logger.error("Status generation failed: %s", e)
        return None
