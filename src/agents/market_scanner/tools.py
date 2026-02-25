"""Market data collection tools for the Market Scanner agent.

Integrations with various data sources for market intelligence.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

import httpx
from pydantic import ValidationError

from src.agents.market_scanner.models import (
    CarbonMarketUpdate,
    DFIOpportunity,
    MarketIntelItem,
    MarketDataSource,
)
from src.config import settings

logger = logging.getLogger(__name__)


# ── Content Hashing for Deduplication ──


def content_hash(text: str) -> str:
    """Generate a content hash for deduplication."""
    return hashlib.sha256(text.encode()).hexdigest()[:16]


# ── RSS Feed Parser ──


class RSSFeedCollector:
    """Collect news from RSS feeds.

    Sources include:
    - ESI Africa (energy news)
    - Carbon Pulse (carbon markets)
    - Devex (development)
    - Reuters Africa
    """

    DEFAULT_FEEDS = {
        "ESI Africa": "https://www.esi-africa.com/feed/",
        "Carbon Pulse": "https://carbonpulse.com/feed/",
        "Reuters Africa": "https://www.reuters.com/arc/outboundfeeds/rss/category/Africa",
        "Renewables Now": "https://renewablesnow.com/rss/",
    }

    def __init__(self, feeds: dict[str, str] | None = None):
        self.feeds = feeds or self.DEFAULT_FEEDS
        self.client = httpx.AsyncClient(timeout=30.0)

    async def collect(
        self,
        hours_back: int = 24,
        relevance_keywords: list[str] | None = None,
    ) -> list[MarketIntelItem]:
        """Collect news items from RSS feeds.

        Args:
            hours_back: Only collect items from last N hours
            relevance_keywords: Keywords that indicate higher relevance
        """
        relevance_keywords = relevance_keywords or [
            "climate",
            "energy",
            "carbon",
            "renewable",
            "solar",
            "geothermal",
            "agriculture",
            "africa",
            "kenya",
            "ethiopia",
            "tanzania",
            "uganda",
            "dfi",
            "development finance",
            "afdb",
            "world bank",
            "verra",
            "gold standard",
        ]

        items = []
        cutoff = datetime.utcnow() - timedelta(hours=hours_back)

        for source_name, feed_url in self.feeds.items():
            try:
                response = await self.client.get(feed_url)
                response.raise_for_status()

                # Parse RSS XML
                import xml.etree.ElementTree as ET

                root = ET.fromstring(response.content)

                # RSS items are in <channel><item> or <entry> (Atom)
                # Handle both RSS and Atom formats
                channel = root.find("channel") or root
                entries = channel.findall("item") or channel.findall("{http://www.w3.org/2005/Atom}entry")

                for entry in entries:
                    item = self._parse_rss_item(entry, source_name, relevance_keywords, cutoff)
                    if item and item.published_at and item.published_at >= cutoff:
                        items.append(item)

                logger.info("Collected %d items from %s", len(entries), source_name)

            except Exception as e:
                logger.error("Failed to collect from %s: %s", source_name, e)

        await self.client.aclose()
        return items

    def _parse_rss_item(
        self,
        entry: Any,
        source_name: str,
        relevance_keywords: list[str],
        cutoff: datetime,
    ) -> MarketIntelItem | None:
        """Parse a single RSS/Atom entry into a MarketIntelItem."""
        try:
            # Handle different tag names for RSS vs Atom
            title = self._get_text(entry, "title") or ""
            description = self._get_text(entry, "description") or self._get_text(entry, "summary") or ""
            link = self._get_text(entry, "link") or self._get_attr(entry, "link", "href") or ""

            # Parse pubDate
            pub_date_str = self._get_text(entry, "pubDate") or self._get_text(entry, "published")
            published_at = self._parse_date(pub_date_str) if pub_date_str else datetime.utcnow()

            # Skip if too old
            if published_at < cutoff:
                return None

            # Calculate relevance score
            text = f"{title} {description}".lower()
            relevance_count = sum(1 for kw in relevance_keywords if kw.lower() in text)
            relevance_score = min(0.9, 0.3 + (relevance_count * 0.1))

            # Extract key points (first 2 sentences)
            sentences = [s.strip() for s in description.split(".") if s.strip()]
            key_points = sentences[:3] if sentences else []

            # Generate content hash
            content_hash_val = content_hash(f"{title}{description}")

            return MarketIntelItem(
                source=MarketDataSource.NEWS,
                source_name=source_name,
                title=title,
                summary=description,
                url=link,
                published_at=published_at,
                relevance_score=relevance_score,
                key_points=key_points,
                content_hash=content_hash_val,
            )

        except Exception as e:
            logger.debug("Failed to parse RSS item: %s", e)
            return None

    def _get_text(self, element: Any, tag: str) -> str | None:
        """Get text from an element, handling namespaces."""
        child = element.find(tag)
        if child is not None and child.text:
            return child.text.strip()
        # Try with namespace
        child = element.find(f"*//{tag}")
        if child is not None and child.text:
            return child.text.strip()
        return None

    def _get_attr(self, element: Any, tag: str, attr: str) -> str | None:
        """Get an attribute from an element."""
        child = element.find(tag)
        if child is not None:
            return child.get(attr)
        return None

    def _parse_date(self, date_str: str) -> datetime | None:
        """Parse various date formats."""
        if not date_str:
            return None

        formats = [
            "%a, %d %b %Y %H:%M:%S %z",  # RFC 2822
            "%a, %d %b %Y %H:%M:%S %Z",  # RFC 2822 without numeric timezone
            "%Y-%m-%dT%H:%M:%S%z",  # ISO 8601
            "%Y-%m-%dT%H:%M:%SZ",  # ISO 8601 UTC
            "%Y-%m-%d %H:%M:%S",  # Simple format
        ]

        for fmt in formats:
            try:
                from email.utils import parsedate_to_datetime

                # Try email.utils first (handles RSS dates well)
                return parsedate_to_datetime(date_str)
            except Exception:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue

        return None


# ── World Bank Projects API ──


class WorldBankClient:
    """Collect DFI opportunities from World Bank Projects API.

    API docs: https://projectsportal.worldbank.org/api/v2/docs
    """

    BASE_URL = "https://projectsportal.worldbank.org/api/v2"

    # Countries relevant to AfCEN
    COUNTRIES = ["KE", "ET", "TZ", "UG", "RW", "BI", "SO", "DJ"]  # East Africa focus

    # Sectors of interest
    SECTORS = [
        "Energy",
        "Agriculture",
        "Rural development",
        "Environment",
        "Climate change",
        "Water",
        "Transportation",
    ]

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)

    async def collect_opportunities(
        self,
        days_back: int = 30,
    ) -> list[DFIOpportunity]:
        """Collect recently updated or announced World Bank projects.

        Args:
            days_back: Look for projects updated in last N days
        """
        opportunities = []
        cutoff = datetime.utcnow() - timedelta(days=days_back)

        for country in self.COUNTRIES:
            try:
                # Query projects by country
                url = f"{self.BASE_URL}/country"
                params = {
                    "countrycode": country,
                    "format": "json",
                    "pagesize": 50,
                }

                response = await self.client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                # First element is metadata, rest are projects
                projects = data[1:] if isinstance(data, list) and len(data) > 1 else []

                for project in projects:
                    opp = self._parse_project(project, cutoff)
                    if opp:
                        opportunities.append(opp)

                logger.info("Found %d opportunities in %s", len(opportunities), country)

            except Exception as e:
                logger.error("Failed to collect World Bank projects for %s: %s", country, e)

        await self.client.aclose()
        return opportunities

    def _parse_project(self, project: dict[str, Any], cutoff: datetime) -> DFIOpportunity | None:
        """Parse a World Bank project into a DFIOpportunity."""
        try:
            # Check if recently updated
            approval_date = self._parse_wb_date(project.get("approvaldate"))
            if not approval_date:
                return None

            # Get project details
            project_id = project.get("project_id", "")
            title = project.get("project_name", "")
            description = project.get("projectdocs", [{}])[0].get("docdescription") if project.get("projectdocs") else ""
            sector = project.get("sector", [""])[0] if project.get("sector") else ""
            country_code = project.get("countrycode", "")
            status = project.get("status", "Unknown")
            url = project.get("url", "")

            # Extract funding amount if available
            lending = project.get("lendingprojectcost", "")
            funding_amount = f"${lending:,}" if lending else None

            # Skip if too old
            if approval_date < cutoff:
                return None

            # Basic relevance filtering
            if not any(s.lower() in sector.lower() for s in self.SECTORS):
                return None

            return DFIOpportunity(
                source="World Bank",
                project_id=project_id,
                title=title,
                description=description or title,
                sector=sector,
                country=country_code,
                funding_amount=funding_amount,
                status=status,
                approval_date=approval_date,
                url=url,
                relevance_score=0.7,  # World Bank projects are usually relevant
            )

        except Exception as e:
            logger.debug("Failed to parse World Bank project: %s", e)
            return None

    def _parse_wb_date(self, date_str: str | None) -> datetime | None:
        """Parse World Bank date format (YYYY-MM-DDTHH:MM:SS)."""
        if not date_str:
            return None
        try:
            # World Bank dates are like "2013-06-26T00:00:00"
            return datetime.fromisoformat(date_str.replace("T", " ").replace("Z", ""))
        except Exception:
            return None


# ── Generic HTTP Scraper for Additional Sources ──


class GenericNewsScraper:
    """Generic scraper for news sites without RSS feeds.

    Uses simple HTTP GET + HTML parsing fallback.
    """

    async def scrape(self, url: str) -> str | None:
        """Scrape text content from a URL."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                response.raise_for_status()

                # Very basic text extraction
                import re
                from html import unescape

                # Extract text from HTML
                text = re.sub(r"<[^>]+>", " ", response.text)
                text = unescape(text)
                text = " ".join(text.split())

                return text[:5000]  # Limit length

        except Exception as e:
            logger.error("Failed to scrape %s: %s", url, e)
            return None


# ── Market Intel Storage ──


class MarketIntelStore:
    """Store and retrieve market intelligence from PostgreSQL."""

    def __init__(self):
        from src.memory.postgres_store import PostgresStore

        self.store = PostgresStore()

    async def save_intel(self, items: list[MarketIntelItem]) -> int:
        """Save market intelligence items to database.

        Returns count of new (non-duplicate) items saved.
        """
        new_count = 0

        for item in items:
            try:
                # Check for duplicates by content_hash
                existing = await self._find_by_hash(item.content_hash)
                if existing:
                    logger.debug("Duplicate intel item: %s", item.title)
                    continue

                # Insert new item
                await self.store.execute(
                    """
                    INSERT INTO market_intel
                    (source, source_name, title, summary, url, published_at,
                     relevance_score, tags, region, sector, key_points,
                     organizations, content_hash, raw_data)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                    """,
                    item.source,
                    item.source_name,
                    item.title,
                    item.summary,
                    item.url,
                    item.published_at,
                    item.relevance_score,
                    item.tags,
                    item.region,
                    item.sector,
                    item.key_points,
                    item.organizations,
                    item.content_hash,
                    item.raw_data,
                )
                new_count += 1

            except Exception as e:
                logger.error("Failed to save intel item: %s", e)

        return new_count

    async def _find_by_hash(self, content_hash: str) -> bool:
        """Check if item with this hash already exists."""
        try:
            result = await self.store.fetch_one(
                "SELECT 1 FROM market_intel WHERE content_hash = $1 LIMIT 1",
                content_hash,
            )
            return result is not None
        except Exception:
            return False

    async def get_recent_intel(
        self,
        hours: int = 24,
        min_relevance: float = 0.3,
        limit: int = 100,
    ) -> list[MarketIntelItem]:
        """Retrieve recent market intelligence above relevance threshold."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        try:
            rows = await self.store.fetch_all(
                """
                SELECT source, source_name, title, summary, url, published_at,
                       relevance_score, tags, region, sector, key_points,
                       organizations, mentioned_technologies, content_hash, raw_data
                FROM market_intel
                WHERE collected_at > $1 AND relevance_score >= $2
                ORDER BY relevance_score DESC, published_at DESC
                LIMIT $3
                """,
                cutoff,
                min_relevance,
                limit,
            )

            items = []
            for row in rows:
                items.append(
                    MarketIntelItem(
                        source=row["source"],
                        source_name=row["source_name"],
                        title=row["title"],
                        summary=row["summary"],
                        url=row["url"],
                        published_at=row["published_at"],
                        relevance_score=row["relevance_score"],
                        tags=row["tags"] or [],
                        region=row["region"],
                        sector=row["sector"],
                        key_points=row["key_points"] or [],
                        organizations=row["organizations"] or [],
                        mentioned_technologies=row.get("mentioned_technologies") or [],
                        raw_data=row.get("raw_data") or {},
                        content_hash=row["content_hash"],
                    )
                )

            return items

        except Exception as e:
            logger.error("Failed to retrieve recent intel: %s", e)
            return []

    async def get_briefs_count_last_7_days(self) -> int:
        """Count morning briefs generated in the last 7 days."""
        from datetime import timedelta
        from sqlalchemy import func, select
        from src.memory.postgres_store import MorningBriefRecord

        cutoff = datetime.utcnow() - timedelta(days=7)

        try:
            async with self.store.session() as session:
                stmt = select(func.count()).select_from(
                    MorningBriefRecord
                ).where(
                    MorningBriefRecord.generated_at > cutoff
                )
                result = await session.execute(stmt)
                count = result.scalar()
                return count or 0
        except Exception as e:
            logger.error("Failed to count briefs: %s", e)
            return 0


# ── All-in-One Collection Function ──


async def collect_all_sources(hours_back: int = 24) -> dict[str, Any]:
    """Collect data from all enabled sources.

    Returns a summary of what was collected.
    """
    results = {
        "news_items": [],
        "dfi_opportunities": [],
        "carbon_updates": [],
        "sources_succeeded": [],
        "sources_failed": {},
    }

    # RSS feeds
    try:
        rss_collector = RSSFeedCollector()
        news_items = await rss_collector.collect(hours_back=hours_back)
        results["news_items"] = news_items
        results["sources_succeeded"].append("RSS Feeds")
        logger.info("Collected %d news items from RSS", len(news_items))
    except Exception as e:
        results["sources_failed"]["RSS Feeds"] = str(e)
        logger.error("RSS collection failed: %s", e)

    # World Bank
    try:
        wb_client = WorldBankClient()
        dfi_opps = await wb_client.collect_opportunities(days_back=30)  # Look back 30 days for DFI
        results["dfi_opportunities"] = dfi_opps
        results["sources_succeeded"].append("World Bank")
        logger.info("Collected %d World Bank opportunities", len(dfi_opps))
    except Exception as e:
        results["sources_failed"]["World Bank"] = str(e)
        logger.error("World Bank collection failed: %s", e)

    # TODO: Add more sources (Verra, Gold Standard, Twitter, etc.)

    return results
