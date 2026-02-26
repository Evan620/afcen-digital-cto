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


# ── Verra Carbon Registry ──


class VerraRegistryClient:
    """Collect carbon credit project data from the Verra VCS registry.

    Targets the public search at https://registry.verra.org/app/search/VCS
    """

    BASE_URL = "https://registry.verra.org/app/search/VCS"

    # East African countries relevant to AfCEN
    COUNTRIES = ["Kenya", "Ethiopia", "Tanzania", "Uganda", "Rwanda", "Burundi"]

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=45.0)  # Verra can be slow
        self._seen_ids: set[str] = set()

    async def collect_updates(self, days_back: int = 30) -> list[CarbonMarketUpdate]:
        """Collect recent carbon project updates from Verra registry.

        Args:
            days_back: Look for projects updated in last N days
        """
        updates: list[CarbonMarketUpdate] = []

        for country in self.COUNTRIES:
            try:
                params = {
                    "q": "",
                    "country": country,
                    "format": "json",
                    "limit": 50,
                }

                response = await self.client.get(self.BASE_URL, params=params)
                response.raise_for_status()

                # Try JSON first, fall back to HTML parsing
                projects = self._parse_response(response, country)
                updates.extend(projects)

                logger.info("Collected %d Verra projects for %s", len(projects), country)

            except Exception as e:
                logger.error("Failed to collect Verra projects for %s: %s", country, e)

        await self.client.aclose()
        return updates

    def _parse_response(self, response: httpx.Response, country: str) -> list[CarbonMarketUpdate]:
        """Parse Verra response, trying JSON first then HTML fallback."""
        projects: list[CarbonMarketUpdate] = []

        # Try JSON parsing
        try:
            data = response.json()
            records = data if isinstance(data, list) else data.get("records", data.get("results", []))
            for record in records:
                update = self._parse_project(record, country)
                if update:
                    projects.append(update)
            return projects
        except Exception:
            pass

        # HTML fallback — extract project info from table rows
        try:
            import re
            from html import unescape

            text = unescape(response.text)
            # Look for project IDs in the HTML
            project_ids = re.findall(r"VCS-?(\d+)", text)
            for pid in project_ids[:20]:  # Limit
                project_id = f"VCS-{pid}"
                if project_id not in self._seen_ids:
                    self._seen_ids.add(project_id)
                    projects.append(
                        CarbonMarketUpdate(
                            registry="Verra",
                            project_id=project_id,
                            project_name=f"VCS Project {pid}",
                            project_type="VCS",
                            country=country,
                            update_type="Listed",
                        )
                    )
        except Exception as e:
            logger.debug("Verra HTML parsing failed for %s: %s", country, e)

        return projects

    def _parse_project(self, record: dict[str, Any], country: str) -> CarbonMarketUpdate | None:
        """Parse a single Verra project record into a CarbonMarketUpdate."""
        try:
            project_id = str(record.get("resourceIdentifier", record.get("id", "")))
            if not project_id or project_id in self._seen_ids:
                return None
            self._seen_ids.add(project_id)

            # Parse announcement/issuance date
            date_str = record.get("creditingPeriodStartDate") or record.get("createdAt")
            announcement_date = None
            if date_str:
                try:
                    announcement_date = datetime.fromisoformat(str(date_str).replace("Z", "+00:00").replace("T", " ").split("+")[0])
                except Exception:
                    pass

            return CarbonMarketUpdate(
                registry="Verra",
                project_id=project_id,
                project_name=record.get("resourceName", record.get("name", f"VCS Project {project_id}")),
                project_type=record.get("methodology", record.get("type", "VCS")),
                country=country,
                update_type=record.get("status", "Listed"),
                credits_issued=record.get("estimatedAnnualReduction") or record.get("creditsIssued"),
                vintage_year=record.get("vintageYear"),
                announcement_date=announcement_date,
                url=f"https://registry.verra.org/app/projectDetail/VCS/{project_id}",
            )

        except Exception as e:
            logger.debug("Failed to parse Verra project: %s", e)
            return None


# ── Gold Standard Registry ──


class GoldStandardClient:
    """Collect carbon credit project data from the Gold Standard registry.

    Targets the public listing at https://registry.goldstandard.org/projects
    """

    BASE_URL = "https://registry.goldstandard.org/projects"

    COUNTRIES = ["Kenya", "Ethiopia", "Tanzania", "Uganda", "Rwanda"]

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=45.0)
        self._seen_ids: set[str] = set()

    async def collect_updates(self, days_back: int = 30) -> list[CarbonMarketUpdate]:
        """Collect recent carbon project updates from Gold Standard registry.

        Args:
            days_back: Look for projects updated in last N days
        """
        updates: list[CarbonMarketUpdate] = []

        for country in self.COUNTRIES:
            try:
                params = {
                    "q": country,
                    "limit": 50,
                }

                response = await self.client.get(self.BASE_URL, params=params)
                response.raise_for_status()

                projects = self._parse_response(response, country)
                updates.extend(projects)

                logger.info("Collected %d Gold Standard projects for %s", len(projects), country)

            except Exception as e:
                logger.error("Failed to collect Gold Standard projects for %s: %s", country, e)

        await self.client.aclose()
        return updates

    def _parse_response(self, response: httpx.Response, country: str) -> list[CarbonMarketUpdate]:
        """Parse Gold Standard response, trying JSON first then HTML fallback."""
        projects: list[CarbonMarketUpdate] = []

        # Try JSON parsing
        try:
            data = response.json()
            records = data if isinstance(data, list) else data.get("data", data.get("results", []))
            for record in records:
                update = self._parse_project(record, country)
                if update:
                    projects.append(update)
            return projects
        except Exception:
            pass

        # HTML fallback
        try:
            import re
            from html import unescape

            text = unescape(response.text)
            project_ids = re.findall(r"GS-?(\d+)", text)
            for pid in project_ids[:20]:
                project_id = f"GS-{pid}"
                if project_id not in self._seen_ids:
                    self._seen_ids.add(project_id)
                    projects.append(
                        CarbonMarketUpdate(
                            registry="Gold Standard",
                            project_id=project_id,
                            project_name=f"Gold Standard Project {pid}",
                            project_type="GS-VER",
                            country=country,
                            update_type="Listed",
                        )
                    )
        except Exception as e:
            logger.debug("Gold Standard HTML parsing failed for %s: %s", country, e)

        return projects

    def _parse_project(self, record: dict[str, Any], country: str) -> CarbonMarketUpdate | None:
        """Parse a single Gold Standard project record."""
        try:
            project_id = str(record.get("id", record.get("gsId", "")))
            if not project_id or project_id in self._seen_ids:
                return None
            self._seen_ids.add(project_id)

            date_str = record.get("registrationDate") or record.get("createdAt")
            announcement_date = None
            if date_str:
                try:
                    announcement_date = datetime.fromisoformat(str(date_str).replace("Z", "+00:00").replace("T", " ").split("+")[0])
                except Exception:
                    pass

            return CarbonMarketUpdate(
                registry="Gold Standard",
                project_id=project_id,
                project_name=record.get("name", record.get("title", f"GS Project {project_id}")),
                project_type=record.get("methodology", record.get("type", "GS-VER")),
                country=country,
                update_type=record.get("status", "Listed"),
                credits_issued=record.get("creditsIssued") or record.get("estimatedReduction"),
                vintage_year=record.get("vintageYear"),
                announcement_date=announcement_date,
                url=f"https://registry.goldstandard.org/projects/details/{project_id}",
            )

        except Exception as e:
            logger.debug("Failed to parse Gold Standard project: %s", e)
            return None


# ── African Development Bank Projects ──


class AfDBClient:
    """Collect DFI opportunities from the African Development Bank projects portal.

    Targets: https://projectsportal.afdb.org/dataportal/VProject/ongoingProjects
    """

    BASE_URL = "https://projectsportal.afdb.org/dataportal/VProject/ongoingProjects"

    COUNTRIES = ["Kenya", "Ethiopia", "Tanzania", "Uganda", "Rwanda", "Burundi"]

    SECTORS = [
        "Energy",
        "Agriculture",
        "Environment",
        "Water",
        "Transport",
        "Multi-Sector",
    ]

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=45.0)

    async def collect_opportunities(self, days_back: int = 30) -> list[DFIOpportunity]:
        """Collect recently updated AfDB project opportunities.

        Args:
            days_back: Look for projects updated in last N days
        """
        opportunities: list[DFIOpportunity] = []
        cutoff = datetime.utcnow() - timedelta(days=days_back)

        for country in self.COUNTRIES:
            try:
                params = {
                    "country": country,
                    "format": "json",
                    "limit": 50,
                }

                response = await self.client.get(self.BASE_URL, params=params)
                response.raise_for_status()

                projects = self._parse_response(response, country, cutoff)
                opportunities.extend(projects)

                logger.info("Collected %d AfDB opportunities for %s", len(projects), country)

            except Exception as e:
                logger.error("Failed to collect AfDB projects for %s: %s", country, e)

        await self.client.aclose()
        return opportunities

    def _parse_response(
        self, response: httpx.Response, country: str, cutoff: datetime
    ) -> list[DFIOpportunity]:
        """Parse AfDB response, trying JSON first then HTML fallback."""
        projects: list[DFIOpportunity] = []

        # Try JSON parsing
        try:
            data = response.json()
            records = data if isinstance(data, list) else data.get("results", data.get("projects", []))
            for record in records:
                opp = self._parse_project(record, country, cutoff)
                if opp:
                    projects.append(opp)
            return projects
        except Exception:
            pass

        # HTML fallback — extract project info
        try:
            import re
            from html import unescape

            text = unescape(response.text)
            # Look for project identifiers
            project_ids = re.findall(r"P-([A-Z]{2}-\w+-\d+)", text)
            for pid in project_ids[:20]:
                projects.append(
                    DFIOpportunity(
                        source="AfDB",
                        project_id=f"P-{pid}",
                        title=f"AfDB Project {pid}",
                        description=f"African Development Bank project in {country}",
                        sector="Multi-Sector",
                        country=country,
                        status="Active",
                        relevance_score=0.6,
                    )
                )
        except Exception as e:
            logger.debug("AfDB HTML parsing failed for %s: %s", country, e)

        return projects

    def _parse_project(
        self, record: dict[str, Any], country: str, cutoff: datetime
    ) -> DFIOpportunity | None:
        """Parse a single AfDB project record into a DFIOpportunity."""
        try:
            project_id = str(record.get("projectId", record.get("id", "")))
            if not project_id:
                return None

            # Parse approval date
            date_str = record.get("approvalDate") or record.get("boardApprovalDate")
            approval_date = None
            if date_str:
                try:
                    approval_date = datetime.fromisoformat(str(date_str).replace("Z", "+00:00").replace("T", " ").split("+")[0])
                except Exception:
                    pass

            # Filter by date if we have one
            if approval_date and approval_date < cutoff:
                return None

            # Filter by sector
            sector = record.get("sector", record.get("sectorName", ""))
            if sector and not any(s.lower() in sector.lower() for s in self.SECTORS):
                return None

            # Filter by country
            project_country = record.get("country", record.get("countryName", country))
            if not any(c.lower() in str(project_country).lower() for c in self.COUNTRIES):
                return None

            funding = record.get("approvedAmount") or record.get("totalCost")
            funding_amount = f"${funding:,.0f}" if isinstance(funding, (int, float)) else str(funding) if funding else None

            return DFIOpportunity(
                source="AfDB",
                project_id=project_id,
                title=record.get("projectName", record.get("title", f"AfDB Project {project_id}")),
                description=record.get("description", record.get("objective", f"AfDB project in {country}")),
                sector=sector or "Multi-Sector",
                country=project_country if isinstance(project_country, str) else country,
                funding_amount=funding_amount,
                status=record.get("status", "Active"),
                approval_date=approval_date,
                url=record.get("url", f"https://projectsportal.afdb.org/dataportal/VProject/show/{project_id}"),
                relevance_score=0.7,
            )

        except Exception as e:
            logger.debug("Failed to parse AfDB project: %s", e)
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

    # Verra Carbon Registry
    try:
        verra_client = VerraRegistryClient()
        verra_updates = await verra_client.collect_updates(days_back=30)
        results["carbon_updates"].extend(verra_updates)
        results["sources_succeeded"].append("Verra Registry")
        logger.info("Collected %d Verra carbon updates", len(verra_updates))
    except Exception as e:
        results["sources_failed"]["Verra Registry"] = str(e)
        logger.error("Verra collection failed: %s", e)

    # Gold Standard Registry
    try:
        gs_client = GoldStandardClient()
        gs_updates = await gs_client.collect_updates(days_back=30)
        results["carbon_updates"].extend(gs_updates)
        results["sources_succeeded"].append("Gold Standard")
        logger.info("Collected %d Gold Standard carbon updates", len(gs_updates))
    except Exception as e:
        results["sources_failed"]["Gold Standard"] = str(e)
        logger.error("Gold Standard collection failed: %s", e)

    # African Development Bank
    try:
        afdb_client = AfDBClient()
        afdb_opps = await afdb_client.collect_opportunities(days_back=30)
        results["dfi_opportunities"].extend(afdb_opps)
        results["sources_succeeded"].append("AfDB")
        logger.info("Collected %d AfDB opportunities", len(afdb_opps))
    except Exception as e:
        results["sources_failed"]["AfDB"] = str(e)
        logger.error("AfDB collection failed: %s", e)

    return results
