"""
Crawler Service for NomadNest AI.

Architecture:
    ┌─────────────────────────────────────────┐
    │           CrawlerService                │
    ├─────────────────────────────────────────┤
    │  Rust OTA Engine (subprocess bridge)    │
    │  ├── Booking.com Agent                  │
    │  ├── Hostelworld Agent                  │
    │  └── Airbnb Agent                       │
    │  └── Security: sanitizer + injection    │
    ├─────────────────────────────────────────┤
    │  EnrichedCSVCrawler (internal data)     │
    │  └── enriched_retreats.csv              │
    ├─────────────────────────────────────────┤
    │  DatabaseCrawler (internal data)        │
    │  └── PostgreSQL listings table          │
    └─────────────────────────────────────────┘

The LiveWebCrawler has been deprecated — its functionality is superseded
by the Rust OTA agents which provide: multi-strategy extraction, 5-dim scoring,
niche classification, and compiled security (sanitizer + injection guard).
"""
import csv
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
import structlog

logger = structlog.get_logger("nomadnest.crawler")


@dataclass
class CrawledListing:
    """Normalized listing data from crawled source."""
    source: str
    source_id: str
    name: str
    url: str
    price_per_night: Optional[float] = None
    price_per_month: Optional[float] = None
    currency: str = "USD"
    location: str = ""
    description: str = ""
    amenities: List[str] = field(default_factory=list)
    images: List[str] = field(default_factory=list)
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    host_name: Optional[str] = None
    wifi_speed: Optional[int] = None
    booking_links: List[str] = field(default_factory=list)
    programs: List[str] = field(default_factory=list)
    upcoming_dates: List[str] = field(default_factory=list)
    crawled_at: datetime = None

    def __post_init__(self):
        if self.crawled_at is None:
            self.crawled_at = datetime.utcnow()

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "source": self.source,
            "source_id": self.source_id,
            "name": self.name,
            "url": self.url,
            "price_per_night": self.price_per_night,
            "price_per_month": self.price_per_month,
            "currency": self.currency,
            "location": self.location,
            "description": self.description,
            "amenities": self.amenities,
            "images": self.images,
            "rating": self.rating,
            "reviews_count": self.reviews_count,
            "host_name": self.host_name,
            "wifi_speed": self.wifi_speed,
            "booking_links": self.booking_links,
            "programs": self.programs,
            "upcoming_dates": self.upcoming_dates,
            "crawled_at": self.crawled_at.isoformat() if self.crawled_at else None,
        }


def _parse_csv_list(value: str) -> List[str]:
    """Parse a stringified list field from CSV."""
    if not value or value.strip() == "":
        return []
    try:
        import json
        return json.loads(value.replace("'", '"'))
    except Exception:
        return [v.strip() for v in value.split(",") if v.strip()]


def _parse_price(price_str: str) -> Optional[float]:
    """Extract a numeric price from a string like '$1,200' or '1200.00'."""
    if not price_str:
        return None
    numbers = re.findall(r'[\d,]+\.?\d*', price_str.replace(",", ""))
    if numbers:
        try:
            return float(numbers[0])
        except ValueError:
            return None
    return None


class EnrichedCSVCrawler:
    """
    Production crawler that reads from enriched_retreats.csv.
    This CSV contains real scraped data from wellness retreat websites:
    booking links, amenities, prices, dates, images, social links.
    """
    source_name = "enriched_csv"

    def __init__(self):
        self._data: Optional[List[Dict]] = None

    def _load_data(self) -> List[Dict]:
        """Load and cache CSV data."""
        if self._data is not None:
            return self._data

        csv_path = Path(__file__).resolve().parents[2] / "data" / "enriched_retreats.csv"
        if not csv_path.exists():
            logger.warning("enriched_retreats.csv not found", path=str(csv_path))
            self._data = []
            return self._data

        retreats = []
        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    retreats.append(row)
            logger.info("loaded_enriched_csv", count=len(retreats))
        except Exception as e:
            logger.error("csv_load_failed", error=str(e))

        self._data = retreats
        return self._data

    async def search(self, location: str, **kwargs) -> List[CrawledListing]:
        """Search enriched CSV data by location."""
        data = self._load_data()
        location_lower = location.lower()
        results = []

        for row in data:
            # Search across multiple fields
            searchable = " ".join([
                row.get("place_name", ""),
                row.get("address", ""),
                row.get("description_long", ""),
                row.get("page_summary", ""),
            ]).lower()

            if location_lower in searchable:
                booking_links = _parse_csv_list(row.get("booking_links", ""))
                images = _parse_csv_list(row.get("image_urls", ""))
                amenities = _parse_csv_list(row.get("amenities", ""))
                programs = _parse_csv_list(row.get("program_names", ""))
                prices = _parse_csv_list(row.get("program_prices", ""))
                dates = _parse_csv_list(row.get("upcoming_dates", ""))

                listing = CrawledListing(
                    source=self.source_name,
                    source_id=re.sub(r'\W+', '-', row.get("place_name", "unknown")).lower()[:40],
                    name=row.get("place_name", "Unknown Retreat"),
                    url=row.get("source_url", ""),
                    description=row.get("description_long", row.get("page_summary", ""))[:500],
                    amenities=amenities,
                    images=images[:6],
                    booking_links=booking_links,
                    programs=programs[:5],
                    upcoming_dates=dates[:10],
                    price_per_month=_parse_price(prices[0]) if prices else None,
                    location=row.get("address", ""),
                )
                results.append(listing)

        logger.info("csv_search_complete", location=location, results=len(results))
        return results


class DatabaseCrawler:
    """
    Production crawler that queries the live database for listings.
    Returns enriched listings with real data.
    """
    source_name = "database"

    async def search(self, location: str, **kwargs) -> List[CrawledListing]:
        """Search database listings by location."""
        try:
            from backend.database import SessionLocal
            from backend import models

            db = SessionLocal()
            try:
                query = db.query(models.Listing).filter(
                    (models.Listing.city.ilike(f"%{location}%")) |
                    (models.Listing.country.ilike(f"%{location}%")) |
                    (models.Listing.name.ilike(f"%{location}%")) |
                    (models.Listing.description.ilike(f"%{location}%"))
                ).limit(20)

                results = []
                for listing in query.all():
                    results.append(CrawledListing(
                        source=self.source_name,
                        source_id=listing.id,
                        name=listing.name,
                        url=listing.booking_url or "",
                        price_per_month=listing.price_usd,
                        description=(listing.description or "")[:500],
                        amenities=listing.scraped_amenities or listing.features or [],
                        images=listing.images or [],
                        location=f"{listing.city}, {listing.country}".strip(", "),
                        booking_links=[listing.booking_url] if listing.booking_url else [],
                        programs=listing.program_names or [],
                        upcoming_dates=listing.upcoming_dates or [],
                    ))

                logger.info("db_search_complete", location=location, results=len(results))
                return results
            finally:
                db.close()
        except Exception as e:
            logger.error("db_search_failed", error=str(e))
            return []


# ═══════════════════════════════════════════════════════════════
# CRAWLER SERVICE — Orchestrates all engines
# ═══════════════════════════════════════════════════════════════

class CrawlerService:
    """
    Main crawler service that orchestrates all data sources.

    - Rust OTA Engine: Booking.com, Hostelworld, Airbnb (with security hardening)
    - EnrichedCSVCrawler: curated seed data from enriched_retreats.csv
    - DatabaseCrawler: PostgreSQL listings table
    """

    def __init__(self):
        self.csv_crawler = EnrichedCSVCrawler()
        self.db_crawler = DatabaseCrawler()

        # Rust OTA engine (high-performance OTA agents)
        try:
            from backend.services.rust_crawler_bridge import rust_crawler
            self.rust_engine = rust_crawler
        except ImportError:
            self.rust_engine = None
            logger.warning("rust_crawler_bridge_unavailable")

    async def search_rust_ota(
        self,
        location: str,
        checkin: str,
        checkout: str,
        guests: int = 1,
        currency: str = "USD",
    ):
        """
        Search via the Rust OTA engine (Booking.com, Hostelworld, Airbnb).
        Returns scored, ranked, niche-classified results.
        """
        if not self.rust_engine or not self.rust_engine.available:
            return None
        return await self.rust_engine.search(
            location=location,
            checkin=checkin,
            checkout=checkout,
            guests=guests,
            currency=currency,
        )

    async def search_all(
        self,
        location: str,
        sources: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, List[CrawledListing]]:
        """
        Search across internal data sources (CSV + DB).
        Returns results grouped by source.
        """
        results = {}
        crawlers = {
            "enriched_csv": self.csv_crawler,
            "database": self.db_crawler,
        }

        if sources:
            crawlers = {k: v for k, v in crawlers.items() if k in sources}

        tasks = []
        for name, crawler in crawlers.items():
            tasks.append((name, crawler.search(location, **kwargs)))

        for name, task in tasks:
            try:
                results[name] = await task
            except Exception as e:
                logger.error("crawler_search_failed", source=name, error=str(e))
                results[name] = []

        return results

    async def search_combined(
        self,
        location: str,
        sources: Optional[List[str]] = None,
        sort_by: str = "price",
        **kwargs
    ) -> List[CrawledListing]:
        """
        Search all internal sources and return combined, deduplicated, sorted results.
        """
        all_results = await self.search_all(location, sources, **kwargs)

        # Combine and deduplicate by name
        combined = []
        seen_names = set()

        for source_results in all_results.values():
            for listing in source_results:
                name_key = listing.name.lower().strip()
                if name_key not in seen_names:
                    seen_names.add(name_key)
                    combined.append(listing)

        # Sort
        if sort_by == "price":
            combined.sort(key=lambda x: x.price_per_month or float("inf"))
        elif sort_by == "name":
            combined.sort(key=lambda x: x.name.lower())

        return combined

    async def enrich_single(self, url: str) -> Optional[CrawledListing]:
        """
        Enrich a single URL by looking up existing data.
        The Rust OTA engine handles live scraping; this checks internal sources.
        """
        try:
            from backend.database import SessionLocal
            from backend import models
            db = SessionLocal()
            try:
                existing = db.query(models.Listing).filter(
                    models.Listing.booking_url == url
                ).first()
                if existing:
                    return CrawledListing(
                        source="database",
                        source_id=existing.id,
                        name=existing.name,
                        url=existing.booking_url or url,
                        description=(existing.description or "")[:500],
                        amenities=existing.scraped_amenities or existing.features or [],
                        images=existing.images or [],
                        location=f"{existing.city}, {existing.country}".strip(", "),
                        booking_links=[existing.booking_url] if existing.booking_url else [],
                    )
            finally:
                db.close()
        except Exception as e:
            logger.warning("enrich_lookup_failed", error=str(e))
        return None

    def get_engine_status(self) -> Dict:
        """Engine status for admin panel."""
        status = {
            "python": {
                "csv_crawler": True,
                "db_crawler": True,
                "purpose": "Internal data (seed CSV + PostgreSQL listings)",
            },
        }
        if self.rust_engine:
            status["rust"] = self.rust_engine.get_status()
        return status


# Singleton instance
crawler_service = CrawlerService()


async def crawl_and_store(location: str, db_session=None) -> Dict[str, Any]:
    """
    Crawl listings from all sources and optionally store in database.
    Returns summary of crawled data.
    """
    results = await crawler_service.search_combined(location)

    summary = {
        "location": location,
        "total_found": len(results),
        "sources": {},
        "listings": [r.to_dict() for r in results[:20]],
    }

    # Count by source
    for r in results:
        summary["sources"][r.source] = summary["sources"].get(r.source, 0) + 1

    # Store in DB if session provided
    if db_session and results:
        try:
            from backend import models
            stored = 0
            for listing_data in results:
                existing = db_session.query(models.Listing).filter(
                    models.Listing.name.ilike(f"%{listing_data.name}%")
                ).first()
                if existing and not existing.booking_url and listing_data.url:
                    existing.booking_url = listing_data.url
                    stored += 1
            db_session.commit()
            summary["stored_count"] = stored
        except Exception as e:
            logger.error("crawl_store_failed", error=str(e))
            summary["store_error"] = str(e)

    return summary
