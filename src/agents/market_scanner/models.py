"""Data models for the Market Scanner agent.

Models for market intelligence, news aggregation, and morning briefs.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class MarketDataSource(str, Enum):
    """Sources for market intelligence data."""

    NEWS = "news"
    DFI_OPPORTUNITY = "dfi_opportunity"
    CARBON_MARKET = "carbon_market"
    POLICY_UPDATE = "policy_update"
    RESEARCH_PAPER = "research_paper"
    SOCIAL_MENTION = "social_mention"


class MarketIntelItem(BaseModel):
    """A single piece of market intelligence.

    Collected from various sources and stored for brief generation.
    """

    source: MarketDataSource
    source_name: str  # e.g., "Feedly", "World Bank API", "Verra Registry"
    title: str
    summary: str
    url: Optional[str] = None
    published_at: Optional[datetime] = None
    collected_at: datetime = Field(default_factory=datetime.utcnow)
    relevance_score: float = Field(default=0.5, ge=0.0, le=1.0)

    # Categorization
    tags: list[str] = Field(default_factory=list)
    region: Optional[str] = None  # e.g., "East Africa", "Kenya", "Pan-African"
    sector: Optional[str] = None  # e.g., "Energy", "Agribusiness", "Carbon Markets"

    # Content extraction
    key_points: list[str] = Field(default_factory=list)
    organizations: list[str] = Field(default_factory=list)
    mentioned_technologies: list[str] = Field(default_factory=list)

    # Raw data for reference
    raw_data: dict[str, Any] = Field(default_factory=dict)

    # Unique identifier for deduplication
    content_hash: Optional[str] = None


class DFIOpportunity(BaseModel):
    """Development Finance Institution funding opportunity."""

    source: str  # e.g., "World Bank", "AfDB", "IFC"
    project_id: str
    title: str
    description: str
    sector: str  # e.g., "Renewable Energy", "Agriculture"
    country: str
    funding_amount: Optional[str] = None
    status: str  # e.g., "Open", "Closing Soon", "Closed"
    deadline: Optional[datetime] = None
    url: Optional[str] = None
    relevance_score: float = Field(default=0.5, ge=0.0, le=1.0)

    # Extracted details
    eligibility_criteria: list[str] = Field(default_factory=list)
    key_requirements: list[str] = Field(default_factory=list)
    contact_info: Optional[str] = None


class CarbonMarketUpdate(BaseModel):
    """Update from carbon credit registries."""

    registry: str  # e.g., "Verra", "Gold Standard"
    project_id: str
    project_name: str
    project_type: str  # e.g., "AR-AM0004", "AMS-III.G."
    country: str
    update_type: str  # e.g., "New Issuance", "Methodology Change", "Verification"
    credits_issued: Optional[int] = None
    vintage_year: Optional[int] = None
    announcement_date: Optional[datetime] = None
    url: Optional[str] = None


class MarketMove(BaseModel):
    """Notable market movement or development."""

    title: str
    description: str
    impact_level: str = Field(default="medium")  # "low", "medium", "high"
    category: str  # e.g., "partnership", "funding", "regulation", "competition"
    organizations: list[str] = Field(default_factory=list)
    url: Optional[str] = None
    published_at: Optional[datetime] = None


class PolicyUpdate(BaseModel):
    """Regulatory or policy change relevant to AfCEN."""

    title: str
    jurisdiction: str  # e.g., "EU", "Kenya", "EAC"
    policy_type: str  # e.g., "EUDR", "Carbon Tax", "Feed-in Tariff"
    description: str
    implications: list[str] = Field(default_factory=list)
    effective_date: Optional[datetime] = None
    url: Optional[str] = None


class RecommendedAction(BaseModel):
    """Action recommended to the CEO based on market intelligence."""

    priority: str = Field(default="medium")  # "low", "medium", "high", "urgent"
    category: str  # e.g., "partnership", "funding", "compliance", "competitive"
    title: str
    description: str
    rationale: str
    suggested_deadline: Optional[datetime] = None
    estimated_effort: Optional[str] = None  # e.g., "2 hours", "1 week"
    related_intel: list[str] = Field(default_factory=list)  # IDs of related items


class MorningBrief(BaseModel):
    """Daily morning briefing for the CEO.

    Generated overnight and delivered by 6 AM EAT.
    """

    brief_date: datetime = Field(default_factory=datetime.utcnow)
    brief_id: str = Field(default="")

    # Sections
    market_moves: list[MarketMove] = Field(default_factory=list)
    policy_updates: list[PolicyUpdate] = Field(default_factory=list)
    funding_opportunities: list[DFIOpportunity] = Field(default_factory=list)
    carbon_market_updates: list[CarbonMarketUpdate] = Field(default_factory=list)
    competitive_intelligence: list[str] = Field(default_factory=list)

    # Meeting follow-ups
    meeting_follow_ups: list[str] = Field(default_factory=list)

    # Recommended actions
    recommended_actions: list[RecommendedAction] = Field(default_factory=list)

    # Metadata
    sources_consulted: list[str] = Field(default_factory=list)
    intel_items_collected: int = 0
    generation_time: Optional[datetime] = None
    delivered: bool = False
    delivery_time: Optional[datetime] = None

    def model_post_init(self, __context: Any) -> None:
        """Generate brief_id from date if not provided."""
        if not self.brief_id:
            self.brief_id = f"brief_{self.brief_date.strftime('%Y%m%d')}"


class MarketScannerQueryType(str, Enum):
    """Types of queries the Market Scanner agent can handle."""

    COLLECT = "collect"  # Collect data from all sources
    BRIEF = "brief"  # Generate morning brief
    STATUS = "status"  # Status of recent collections
    SEARCH = "search"  # Search collected intel


class MarketScannerState(BaseModel):
    """State for the Market Scanner agent workflow."""

    query_type: MarketScannerQueryType = MarketScannerQueryType.STATUS
    query: str = ""
    date_range: Optional[tuple[datetime, datetime]] = None

    # Collected data
    intel_items: list[MarketIntelItem] = Field(default_factory=list)
    dfi_opportunities: list[DFIOpportunity] = Field(default_factory=list)
    carbon_updates: list[CarbonMarketUpdate] = Field(default_factory=list)

    # Output
    brief: Optional[MorningBrief] = None
    report: Optional[dict[str, Any]] = None

    # Error handling
    error: Optional[str] = None
    sources_succeeded: list[str] = Field(default_factory=list)
    sources_failed: dict[str, str] = Field(default_factory=dict)
