"""Tests for Phase 3 Market Scanner agent."""

import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
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
from src.agents.market_scanner.tools import (
    VerraRegistryClient,
    GoldStandardClient,
    AfDBClient,
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


class TestDFIOpportunityApprovalDate:
    """Test the new approval_date field on DFIOpportunity."""

    def test_approval_date_defaults_to_none(self):
        """approval_date should default to None."""
        opp = DFIOpportunity(
            source="World Bank",
            project_id="WB-99",
            title="Test Project",
            description="Test",
            sector="Energy",
            country="Kenya",
            status="Open",
        )
        assert opp.approval_date is None

    def test_approval_date_accepts_datetime(self):
        """approval_date should accept a datetime value."""
        dt = datetime(2026, 1, 15, 12, 0, 0)
        opp = DFIOpportunity(
            source="AfDB",
            project_id="AFDB-1",
            title="Solar Project",
            description="Solar deployment",
            sector="Energy",
            country="Ethiopia",
            status="Active",
            approval_date=dt,
        )
        assert opp.approval_date == dt

    def test_approval_date_serializes_in_model_dump(self):
        """approval_date should appear in model_dump output."""
        dt = datetime(2026, 2, 1)
        opp = DFIOpportunity(
            source="AfDB",
            project_id="AFDB-2",
            title="Wind Project",
            description="Wind farm",
            sector="Energy",
            country="Tanzania",
            status="Active",
            approval_date=dt,
        )
        dumped = opp.model_dump()
        assert "approval_date" in dumped
        assert dumped["approval_date"] == dt


class TestVerraRegistryClient:
    """Test VerraRegistryClient with mocked HTTP responses."""

    def test_country_config(self):
        """Verra client should target East African countries."""
        client = VerraRegistryClient()
        assert "Kenya" in client.COUNTRIES
        assert "Ethiopia" in client.COUNTRIES
        assert "Tanzania" in client.COUNTRIES
        assert "Uganda" in client.COUNTRIES
        assert "Rwanda" in client.COUNTRIES
        assert "Burundi" in client.COUNTRIES

    def test_timeout_is_45_seconds(self):
        """Verra client should use 45s timeout (Verra is slow)."""
        client = VerraRegistryClient()
        assert client.client.timeout.read == 45.0

    @pytest.mark.asyncio
    async def test_parse_json_response(self):
        """Should parse a JSON response with project records."""
        client = VerraRegistryClient()

        mock_data = [
            {
                "resourceIdentifier": "1234",
                "resourceName": "Kenya Cookstoves",
                "methodology": "AMS-II.G.",
                "status": "Registered",
                "estimatedAnnualReduction": 50000,
            },
            {
                "resourceIdentifier": "5678",
                "resourceName": "Tanzania REDD+",
                "methodology": "VM0015",
                "status": "Under Validation",
            },
        ]

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = mock_data
        mock_response.text = ""

        results = client._parse_response(mock_response, "Kenya")
        assert len(results) == 2
        assert results[0].project_id == "1234"
        assert results[0].project_name == "Kenya Cookstoves"
        assert results[0].registry == "Verra"
        assert results[1].project_id == "5678"

    @pytest.mark.asyncio
    async def test_parse_html_fallback(self):
        """Should fall back to HTML parsing when JSON fails."""
        client = VerraRegistryClient()

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.side_effect = Exception("Not JSON")
        mock_response.text = """
        <html><body>
        <tr><td>VCS-1001</td><td>Project A</td></tr>
        <tr><td>VCS-2002</td><td>Project B</td></tr>
        </body></html>
        """

        results = client._parse_response(mock_response, "Kenya")
        assert len(results) == 2
        assert results[0].project_id == "VCS-1001"
        assert results[1].project_id == "VCS-2002"

    @pytest.mark.asyncio
    async def test_deduplicates_by_project_id(self):
        """Should not return duplicate project IDs."""
        client = VerraRegistryClient()

        mock_data = [
            {"resourceIdentifier": "1234", "resourceName": "Project A"},
            {"resourceIdentifier": "1234", "resourceName": "Project A duplicate"},
        ]

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = mock_data

        results = client._parse_response(mock_response, "Kenya")
        assert len(results) == 1


class TestGoldStandardClient:
    """Test GoldStandardClient with mocked HTTP responses."""

    def test_country_config(self):
        """Gold Standard client should target East African countries."""
        client = GoldStandardClient()
        assert "Kenya" in client.COUNTRIES
        assert "Ethiopia" in client.COUNTRIES
        assert "Tanzania" in client.COUNTRIES
        assert "Uganda" in client.COUNTRIES
        assert "Rwanda" in client.COUNTRIES

    @pytest.mark.asyncio
    async def test_parse_json_response(self):
        """Should parse a JSON response with project data."""
        client = GoldStandardClient()

        mock_data = {
            "data": [
                {
                    "id": "GS-100",
                    "name": "Clean Cooking Kenya",
                    "methodology": "GS-TPDDTEC",
                    "status": "Certified",
                    "creditsIssued": 25000,
                },
            ]
        }

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = mock_data
        mock_response.text = ""

        results = client._parse_response(mock_response, "Kenya")
        assert len(results) == 1
        assert results[0].project_id == "GS-100"
        assert results[0].registry == "Gold Standard"
        assert results[0].project_name == "Clean Cooking Kenya"

    @pytest.mark.asyncio
    async def test_parse_html_fallback(self):
        """Should fall back to HTML parsing when JSON fails."""
        client = GoldStandardClient()

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.side_effect = Exception("Not JSON")
        mock_response.text = """
        <html><body>
        <div>GS-500</div>
        <div>GS-600</div>
        </body></html>
        """

        results = client._parse_response(mock_response, "Ethiopia")
        assert len(results) == 2
        assert results[0].project_id == "GS-500"
        assert results[0].country == "Ethiopia"


class TestAfDBClient:
    """Test AfDBClient with mocked HTTP responses."""

    def test_country_config(self):
        """AfDB client should target East African countries."""
        client = AfDBClient()
        assert "Kenya" in client.COUNTRIES
        assert "Ethiopia" in client.COUNTRIES
        assert "Burundi" in client.COUNTRIES

    def test_sector_config(self):
        """AfDB client should cover relevant sectors."""
        client = AfDBClient()
        assert "Energy" in client.SECTORS
        assert "Agriculture" in client.SECTORS
        assert "Environment" in client.SECTORS
        assert "Water" in client.SECTORS
        assert "Transport" in client.SECTORS
        assert "Multi-Sector" in client.SECTORS

    @pytest.mark.asyncio
    async def test_parse_json_response(self):
        """Should parse a JSON response with AfDB project data."""
        client = AfDBClient()
        cutoff = datetime.utcnow() - timedelta(days=30)

        mock_data = {
            "results": [
                {
                    "projectId": "P-KE-FA0-001",
                    "projectName": "Kenya Geothermal Expansion",
                    "description": "Expand geothermal capacity in Olkaria",
                    "sector": "Energy",
                    "country": "Kenya",
                    "approvedAmount": 50000000,
                    "status": "Approved",
                    "approvalDate": datetime.utcnow().isoformat(),
                },
            ]
        }

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = mock_data
        mock_response.text = ""

        results = client._parse_response(mock_response, "Kenya", cutoff)
        assert len(results) == 1
        assert results[0].source == "AfDB"
        assert results[0].project_id == "P-KE-FA0-001"
        assert results[0].sector == "Energy"
        assert results[0].funding_amount == "$50,000,000"

    @pytest.mark.asyncio
    async def test_filters_old_projects(self):
        """Should filter out projects older than cutoff."""
        client = AfDBClient()
        cutoff = datetime.utcnow() - timedelta(days=30)

        mock_data = {
            "results": [
                {
                    "projectId": "P-OLD-001",
                    "projectName": "Old Project",
                    "sector": "Energy",
                    "country": "Kenya",
                    "status": "Active",
                    "approvalDate": "2020-01-01T00:00:00",
                },
            ]
        }

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = mock_data
        mock_response.text = ""

        results = client._parse_response(mock_response, "Kenya", cutoff)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_filters_irrelevant_sectors(self):
        """Should filter out projects in irrelevant sectors."""
        client = AfDBClient()
        cutoff = datetime.utcnow() - timedelta(days=30)

        mock_data = {
            "results": [
                {
                    "projectId": "P-FIN-001",
                    "projectName": "Financial Sector Reform",
                    "sector": "Finance",
                    "country": "Kenya",
                    "status": "Active",
                    "approvalDate": datetime.utcnow().isoformat(),
                },
            ]
        }

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = mock_data
        mock_response.text = ""

        results = client._parse_response(mock_response, "Kenya", cutoff)
        assert len(results) == 0


class TestEnrichIntel:
    """Test the enrich_intel node function."""

    @pytest.mark.asyncio
    async def test_skips_when_no_items_need_enrichment(self):
        """Should return empty dict when all items already have tags/sector."""
        from src.agents.market_scanner.agent import enrich_intel

        item = MarketIntelItem(
            source=MarketDataSource.NEWS,
            source_name="Test",
            title="Test",
            summary="Test",
            tags=["energy"],
            sector="Energy",
        )

        state = {"intel_items": [item]}
        result = await enrich_intel(state)
        assert result == {}

    @pytest.mark.asyncio
    async def test_skips_when_no_items(self):
        """Should return empty dict when intel_items is empty."""
        from src.agents.market_scanner.agent import enrich_intel

        state = {"intel_items": []}
        result = await enrich_intel(state)
        assert result == {}

    @pytest.mark.asyncio
    async def test_handles_llm_failure_gracefully(self):
        """Should not raise on LLM failure — items keep keyword-based scores."""
        from src.agents.market_scanner.agent import enrich_intel

        item = MarketIntelItem(
            source=MarketDataSource.NEWS,
            source_name="Test",
            title="Kenya Solar News",
            summary="Solar deployment in Kenya",
            relevance_score=0.5,
        )

        state = {"intel_items": [item]}

        with patch("src.agents.market_scanner.agent.get_default_llm") as mock_llm:
            mock_llm.return_value.ainvoke = AsyncMock(side_effect=Exception("LLM unavailable"))
            result = await enrich_intel(state)

        # Should return items unchanged, not raise
        assert result.get("intel_items") is not None or result == {}
        # Original score should be preserved
        assert item.relevance_score == 0.5

    @pytest.mark.asyncio
    async def test_enriches_items_from_llm_response(self):
        """Should merge LLM enrichment data back into items."""
        from src.agents.market_scanner.agent import enrich_intel

        item = MarketIntelItem(
            source=MarketDataSource.NEWS,
            source_name="Test",
            title="Kenya Geothermal",
            summary="New geothermal plant in Kenya",
        )

        state = {"intel_items": [item]}

        mock_response = MagicMock()
        mock_response.content = json.dumps([
            {
                "item_id": 0,
                "relevance_score": 0.9,
                "tags": ["geothermal", "kenya"],
                "region": "East Africa",
                "sector": "Energy",
                "organizations": ["KenGen"],
            }
        ])

        with patch("src.agents.market_scanner.agent.get_default_llm") as mock_llm:
            mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)
            result = await enrich_intel(state)

        assert result["intel_items"][0].relevance_score == 0.9
        assert result["intel_items"][0].tags == ["geothermal", "kenya"]
        assert result["intel_items"][0].region == "East Africa"
        assert result["intel_items"][0].sector == "Energy"
        assert result["intel_items"][0].organizations == ["KenGen"]
