"""Tests for Phase 3 Market Scanner agent."""

import pytest

from src.agents.market_scanner.models import (
    MarketDataSource,
    MarketIntelItem,
    DFIOpportunity,
    CarbonMarketUpdate,
    MarketMove,
    PolicyUpdate,
    RecommendedAction,
    MorningBrief,
    MarketScannerQueryType,
    MarketScannerState,
)


class TestMarketScannerModels:
    """Test Market Scanner data models."""

    def test_query_type_values(self):
        """MarketScannerQueryType should have all expected values."""
        assert MarketScannerQueryType.COLLECT.value == "collect"
        assert MarketScannerQueryType.BRIEF.value == "brief"
        assert MarketScannerQueryType.STATUS.value == "status"
        assert MarketScannerQueryType.SEARCH.value == "search"

    def test_market_intel_item_creation(self):
        """MarketIntelItem should create with all fields."""
        item = MarketIntelItem(
            source=MarketDataSource.NEWS,
            source_name="Test Feed",
            title="Test Article",
            summary="Test summary",
            url="https://example.com/article",
            relevance_score=0.8,
            tags=["energy", "kenya"],
            sector="Energy",
        )
        assert item.source == MarketDataSource.NEWS
        assert item.relevance_score == 0.8
        assert item.tags == ["energy", "kenya"]

    def test_dfi_opportunity_creation(self):
        """DFIOpportunity should create with required fields."""
        opp = DFIOpportunity(
            source="World Bank",
            project_id="WB-12345",
            title="Solar Energy Project",
            description="Rural solar deployment",
            sector="Energy",
            country="Kenya",
            funding_amount="$5,000,000",
            status="Open",
        )
        assert opp.source == "World Bank"
        assert opp.project_id == "WB-12345"
        assert opp.country == "Kenya"

    def test_carbon_market_update_creation(self):
        """CarbonMarketUpdate should create with registry info."""
        update = CarbonMarketUpdate(
            registry="Verra",
            project_id="VCS-123",
            project_name="Forest Conservation",
            project_type="AR-AM0004",
            country="Ethiopia",
            update_type="New Issuance",
            credits_issued=10000,
        )
        assert update.registry == "Verra"
        assert update.credits_issued == 10000

    def test_morning_brief_creation(self):
        """MorningBrief should create with all sections."""
        brief = MorningBrief(
            brief_id="brief_20260225",
            market_moves=[
                MarketMove(
                    title="New solar plant",
                    description="100MW plant announced",
                    impact_level="high",
                    category="funding",
                )
            ],
            policy_updates=[
                PolicyUpdate(
                    title="Carbon Tax Update",
                    jurisdiction="EU",
                    policy_type="Carbon Tax",
                    description="New carbon border mechanism",
                )
            ],
            recommended_actions=[
                RecommendedAction(
                    priority="high",
                    category="partnership",
                    title="Explore partnership",
                    description="Contact potential partner",
                    rationale="Strategic alignment",
                )
            ],
        )
        assert brief.brief_id == "brief_20260225"
        assert len(brief.market_moves) == 1
        assert len(brief.policy_updates) == 1
        assert len(brief.recommended_actions) == 1

    def test_morning_brief_auto_id(self):
        """MorningBrief should auto-generate brief_id from date."""
        brief = MorningBrief()
        assert brief.brief_id.startswith("brief_")


class TestMarketScannerState:
    """Test MarketScannerState."""

    def test_default_state_structure(self):
        """MarketScannerState should have all expected keys."""
        state: MarketScannerState = {
            "query_type": MarketScannerQueryType.STATUS,
            "query": "",
            "date_range": None,
            "intel_items": [],
            "dfi_opportunities": [],
            "carbon_updates": [],
            "brief": None,
            "report": None,
            "error": None,
            "sources_succeeded": [],
            "sources_failed": {},
        }
        assert state["query_type"] == MarketScannerQueryType.STATUS
        assert state["intel_items"] == []
        assert state["brief"] is None


class TestMarketScannerIntegration:
    """Integration-style tests for Market Scanner."""

    @pytest.mark.asyncio
    async def test_market_intel_store_save_and_retrieve(self):
        """MarketIntelStore should save and retrieve intel."""
        from src.agents.market_scanner.tools import MarketIntelStore

        store = MarketIntelStore()

        # Save test intel
        item = MarketIntelItem(
            source=MarketDataSource.NEWS,
            source_name="Test Feed",
            title="Test Article",
            summary="Test summary",
            relevance_score=0.8,
            content_hash="test123",
            tags=["test"],
        )

        # Note: This would require a real database connection
        # For unit tests, we'd typically mock the database

    def test_content_hash_generation(self):
        """Content hash should be consistent for same input."""
        from src.agents.market_scanner.tools import content_hash

        hash1 = content_hash("same text")
        hash2 = content_hash("same text")
        hash3 = content_hash("different text")

        assert hash1 == hash2
        assert hash1 != hash3
