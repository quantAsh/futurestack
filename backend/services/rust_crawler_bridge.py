"""
Rust Crawler Bridge — Python service that invokes the Rust crawler binary.

Provides the Python backend with access to the high-performance Rust
OTA scraping engine as a first-class service. The bridge:

    1. Calls the compiled `nomadnest-crawler` or `ota_search` binary
    2. Passes search params as CLI args
    3. Captures JSON output
    4. Returns typed Python results

Architecture:
    ┌──────────────────┐     ┌───────────────────────┐     ┌──────────────┐
    │  FastAPI Router  │────▶│  RustCrawlerBridge     │────▶│ Rust Binary  │
    │  /api/crawler/*  │     │  (subprocess + JSON)   │     │ nomadnest-   │
    │                  │◀────│  parse_results()       │◀────│ crawler      │
    └──────────────────┘     └───────────────────────┘     └──────────────┘

The Rust binary is expected at:
    rust-crawler/target/release/nomadnest-crawler   (production)
    rust-crawler/target/debug/nomadnest-crawler     (development)
"""
import asyncio
import json
import os
import shutil
import structlog
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = structlog.get_logger("nomadnest.rust_crawler")

# ═══════════════════════════════════════════════════════════════
# BINARY RESOLUTION
# ═══════════════════════════════════════════════════════════════

PROJECT_ROOT = Path(__file__).parent.parent.parent
RUST_CRAWLER_DIR = PROJECT_ROOT / "rust-crawler"

BINARY_SEARCH_PATHS = [
    RUST_CRAWLER_DIR / "target" / "release" / "nomadnest-crawler",
    RUST_CRAWLER_DIR / "target" / "debug" / "nomadnest-crawler",
    RUST_CRAWLER_DIR / "target" / "release" / "ota_search",
    RUST_CRAWLER_DIR / "target" / "debug" / "ota_search",
]


def find_rust_binary() -> Optional[str]:
    """Locate the compiled Rust crawler binary."""
    for path in BINARY_SEARCH_PATHS:
        if path.exists() and os.access(str(path), os.X_OK):
            return str(path)

    # Try PATH
    which = shutil.which("nomadnest-crawler")
    if which:
        return which

    return None


# ═══════════════════════════════════════════════════════════════
# RESULT TYPES
# ═══════════════════════════════════════════════════════════════

@dataclass
class CrawledAccommodation:
    """A single accommodation listing from the Rust crawler."""
    id: str = ""
    source: str = ""
    name: str = ""
    url: str = ""
    price_per_night: Optional[float] = None
    total_price: Optional[float] = None
    currency: str = "USD"
    location: str = ""
    image_url: str = ""
    rating: Optional[float] = None
    reviews_count: int = 0
    property_type: str = ""
    amenities: List[str] = field(default_factory=list)
    nomad_friendly: bool = False
    free_cancellation: bool = False
    breakfast_included: bool = False
    overall_score: Optional[float] = None
    rank: Optional[int] = None

    @classmethod
    def from_rust_json(cls, data: Dict[str, Any]) -> "CrawledAccommodation":
        """Parse from the Rust crawler's JSON output."""
        location = data.get("location", {})
        prop = data.get("property", {})
        return cls(
            id=data.get("id", ""),
            source=data.get("source", ""),
            name=data.get("name", ""),
            url=data.get("url", ""),
            price_per_night=data.get("price_per_night"),
            total_price=data.get("total_price"),
            currency=data.get("currency", "USD"),
            location=location.get("address", "") if isinstance(location, dict) else str(location),
            image_url=data.get("image_url", ""),
            rating=data.get("rating"),
            reviews_count=data.get("reviews_count", 0),
            property_type=prop.get("property_type", "") if isinstance(prop, dict) else "",
            amenities=prop.get("amenities", []) if isinstance(prop, dict) else [],
            nomad_friendly=prop.get("nomad_friendly", False) if isinstance(prop, dict) else False,
            free_cancellation=data.get("free_cancellation", False),
            breakfast_included=data.get("breakfast_included", False),
        )


@dataclass
class CrawlResults:
    """Results from a Rust crawler search."""
    listings: List[CrawledAccommodation] = field(default_factory=list)
    ranked: List[CrawledAccommodation] = field(default_factory=list)
    providers_queried: List[str] = field(default_factory=list)
    providers_succeeded: List[str] = field(default_factory=list)
    total_found: int = 0
    timestamp: str = ""
    engine: str = "rust-crawler"
    error: Optional[str] = None

    @classmethod
    def from_rust_json(cls, data: Dict[str, Any]) -> "CrawlResults":
        """Parse the full JSON output from the Rust binary."""
        listings = [
            CrawledAccommodation.from_rust_json(l)
            for l in data.get("listings", [])
        ]
        ranked_data = data.get("ranked", [])
        ranked = []
        for r in ranked_data:
            listing_data = r.get("listing", r)
            acc = CrawledAccommodation.from_rust_json(listing_data)
            acc.overall_score = r.get("overall_score")
            acc.rank = r.get("rank")
            ranked.append(acc)

        return cls(
            listings=listings,
            ranked=ranked,
            providers_queried=data.get("providers_queried", []),
            providers_succeeded=data.get("providers_succeeded", []),
            total_found=data.get("total_found", 0),
            timestamp=data.get("timestamp", ""),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to API-friendly dict."""
        return {
            "engine": self.engine,
            "total_found": self.total_found,
            "providers_queried": self.providers_queried,
            "providers_succeeded": self.providers_succeeded,
            "timestamp": self.timestamp,
            "error": self.error,
            "ranked": [
                {
                    "rank": r.rank,
                    "overall_score": r.overall_score,
                    "id": r.id,
                    "source": r.source,
                    "name": r.name,
                    "url": r.url,
                    "price_per_night": r.price_per_night,
                    "total_price": r.total_price,
                    "currency": r.currency,
                    "location": r.location,
                    "image_url": r.image_url,
                    "rating": r.rating,
                    "reviews_count": r.reviews_count,
                    "property_type": r.property_type,
                    "amenities": r.amenities,
                    "nomad_friendly": r.nomad_friendly,
                }
                for r in self.ranked
            ],
            "listings": [
                {
                    "id": l.id,
                    "source": l.source,
                    "name": l.name,
                    "url": l.url,
                    "price_per_night": l.price_per_night,
                    "currency": l.currency,
                    "location": l.location,
                    "rating": l.rating,
                    "image_url": l.image_url,
                }
                for l in self.listings
            ],
        }


# ═══════════════════════════════════════════════════════════════
# BRIDGE SERVICE
# ═══════════════════════════════════════════════════════════════

class RustCrawlerBridge:
    """
    Invokes the Rust crawler binary as a subprocess and parses the JSON output.

    The Rust crawler provides:
    - 3 OTA agents: Booking.com, Hostelworld, Airbnb
    - Built-in injection guard (security/injection.rs)
    - HTML sanitization (security/sanitizer.rs)
    - 5-dimension scoring: amenity, space, review, value, location
    - NomadNest niche classification
    """

    def __init__(self):
        self.binary = find_rust_binary()
        self.available = self.binary is not None
        if self.available:
            logger.info("rust_crawler_found", binary=self.binary)
        else:
            logger.warning("rust_crawler_not_found", search_paths=[str(p) for p in BINARY_SEARCH_PATHS])

    async def search(
        self,
        location: str,
        checkin: str,
        checkout: str,
        guests: int = 1,
        currency: str = "USD",
        timeout: int = 30,
    ) -> CrawlResults:
        """
        Execute a full OTA search via the Rust crawler.

        Args:
            location: Destination (e.g. "Bali", "Lisbon")
            checkin: Check-in date (YYYY-MM-DD)
            checkout: Check-out date (YYYY-MM-DD)
            guests: Number of guests
            currency: Currency code
            timeout: Max seconds to wait

        Returns:
            CrawlResults with ranked accommodations from all 3 OTA providers
        """
        if not self.available:
            return CrawlResults(error="Rust crawler binary not found. Run: cd rust-crawler && cargo build --release")

        cmd = [
            self.binary,
            "--location", location,
            "--checkin", checkin,
            "--checkout", checkout,
            "--guests", str(guests),
            "--currency", currency,
            "--json",
        ]

        logger.info("rust_crawler_search", location=location, checkin=checkin, checkout=checkout)

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(RUST_CRAWLER_DIR),
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )

            if process.returncode != 0:
                error_msg = stderr.decode("utf-8", errors="replace").strip()
                logger.error("rust_crawler_failed", returncode=process.returncode, stderr=error_msg)
                return CrawlResults(error=f"Rust crawler exited with code {process.returncode}: {error_msg[:200]}")

            output = stdout.decode("utf-8", errors="replace").strip()
            if not output:
                return CrawlResults(error="Rust crawler returned empty output")

            data = json.loads(output)
            results = CrawlResults.from_rust_json(data)

            logger.info(
                "rust_crawler_complete",
                total=results.total_found,
                ranked=len(results.ranked),
                providers=results.providers_succeeded,
            )
            return results

        except asyncio.TimeoutError:
            logger.error("rust_crawler_timeout", timeout=timeout)
            return CrawlResults(error=f"Rust crawler timed out after {timeout}s")
        except json.JSONDecodeError as e:
            logger.error("rust_crawler_json_error", error=str(e))
            return CrawlResults(error=f"Failed to parse Rust crawler output: {e}")
        except Exception as e:
            logger.error("rust_crawler_error", error=str(e))
            return CrawlResults(error=str(e))

    def get_status(self) -> Dict[str, Any]:
        """Get Rust crawler status for admin panel."""
        return {
            "available": self.available,
            "binary_path": self.binary,
            "engine": "rust-crawler v0.2.0",
            "agents": ["Booking.com", "Hostelworld", "Airbnb"],
            "security": {
                "html_sanitizer": True,
                "injection_guard": True,
                "patterns": 22,
            },
            "scoring_dimensions": [
                "amenity", "space", "review", "value", "location",
            ],
            "niche_classification": [
                "CoLiving", "RemoteWork", "LongStay",
                "BudgetNomad", "DigitalRetreat", "UniqueStay",
            ],
        }


# Singleton
rust_crawler = RustCrawlerBridge()
