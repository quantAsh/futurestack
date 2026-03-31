"""
Crawler Router — API endpoints for NomadNest's Rust-powered OTA search engine.

Exposes the Rust crawler as a first-class API service:
    GET  /api/v1/crawler/search       — Real-time OTA search (Booking, Hostelworld, Airbnb)
    GET  /api/v1/crawler/status       — Engine health + security status
    POST /api/v1/crawler/enrich       — Scrape single URL for listing enrichment
    GET  /api/v1/crawler/providers    — Available OTA providers
"""
import structlog
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Query, HTTPException, Depends

from backend import models
from backend.utils import require_current_user, require_admin

logger = structlog.get_logger("nomadnest.router.crawler")

router = APIRouter()


@router.get("/search")
async def crawler_search(
    location: str = Query(..., description="Destination (e.g. 'Bali', 'Lisbon')"),
    checkin: str = Query(..., description="Check-in date (YYYY-MM-DD)"),
    checkout: str = Query(..., description="Check-out date (YYYY-MM-DD)"),
    guests: int = Query(1, ge=1, le=10, description="Number of guests"),
    currency: str = Query("USD", description="Currency code"),
    engine: str = Query("rust", description="Engine: 'rust' (OTA scraping) or 'python' (CSV/DB)"),
    current_user: models.User = Depends(require_current_user),
):
    """
    Search accommodations across multiple OTA providers.

    Uses the Rust crawler engine for real-time OTA scraping (Booking.com,
    Hostelworld, Airbnb) with built-in security (HTML sanitization +
    injection guard). Falls back to Python crawler for CSV/DB sources.
    """
    if engine == "rust":
        from backend.services.rust_crawler_bridge import rust_crawler
        results = await rust_crawler.search(
            location=location,
            checkin=checkin,
            checkout=checkout,
            guests=guests,
            currency=currency,
        )
        if results.error:
            return {
                "engine": "rust",
                "error": results.error,
                "results": [],
                "fallback": "Use engine=python for CSV/DB search while Rust binary is being built",
            }
        return results.to_dict()

    elif engine == "python":
        from backend.services.crawler import crawler_service
        listings = await crawler_service.search_combined(location, sort_by="price")
        return {
            "engine": "python",
            "total_found": len(listings),
            "listings": [
                {
                    "name": l.name,
                    "source": l.source,
                    "url": l.url,
                    "price_per_month": l.price_per_month,
                    "location": l.location,
                    "description": l.description[:200] if l.description else None,
                }
                for l in listings
            ],
        }

    raise HTTPException(status_code=400, detail=f"Unknown engine: {engine}. Use 'rust' or 'python'.")


@router.get("/status")
async def crawler_status(admin: models.User = Depends(require_admin)):
    """
    Get crawler engine status including security layer info.

    Returns:
        Engine availability, binary path, security module status,
        supported providers, scoring dimensions, and niche classifications.
    """
    from backend.services.rust_crawler_bridge import rust_crawler
    from backend.services.crawler import crawler_service

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "engines": {
            "rust": rust_crawler.get_status(),
            "python": {
                "available": True,
                "sources": ["enriched_csv", "database", "web"],
                "security": {
                    "html_sanitizer": True,
                    "injection_guard": True,
                    "quarantine_llm": True,
                },
            },
        },
    }


@router.post("/enrich")
async def crawler_enrich(
    url: str = Query(..., description="URL to scrape for listing enrichment"),
    current_user: models.User = Depends(require_current_user),
):
    """
    Scrape a single URL for listing enrichment data.

    Uses the Python LiveWebCrawler with defense-in-depth security
    (HTML sanitization → injection guard → optional quarantine LLM).
    """
    from backend.services.crawler import crawler_service

    result = await crawler_service.enrich_single(url)
    if not result:
        raise HTTPException(status_code=404, detail="Could not scrape listing from URL")

    return {
        "name": result.name,
        "source": result.source,
        "url": result.url,
        "description": result.description,
        "images": result.images,
        "booking_links": result.booking_links,
    }


@router.get("/providers")
async def crawler_providers(admin: models.User = Depends(require_admin)):
    """List all available OTA providers and their capabilities."""
    return {
        "providers": [
            {
                "name": "Booking.com",
                "engine": "rust",
                "strategies": ["Apollo GraphQL cache", "JSON-LD structured data", "Regex fallback"],
                "status": "active",
            },
            {
                "name": "Hostelworld",
                "engine": "rust",
                "strategies": ["__NEXT_DATA__", "JSON-LD"],
                "status": "active",
            },
            {
                "name": "Airbnb",
                "engine": "rust",
                "strategies": ["data-deferred-state-0 (niobeClientData)", "__NEXT_DATA__"],
                "status": "active",
            },
            {
                "name": "Enriched CSV",
                "engine": "python",
                "strategies": ["CSV parsing with AI enrichment"],
                "status": "active",
            },
            {
                "name": "Database",
                "engine": "python",
                "strategies": ["PostgreSQL + Alembic"],
                "status": "active",
            },
            {
                "name": "Live Web",
                "engine": "python",
                "strategies": ["BeautifulSoup + aiohttp with security hardening"],
                "status": "active",
            },
        ],
        "security": {
            "rust_engine": {
                "html_sanitizer": "security/sanitizer.rs — strips script, style, iframe, hidden CSS, event handlers",
                "injection_guard": "security/injection.rs — 22 compiled regex patterns, instruction density heuristic",
            },
            "python_engine": {
                "html_sanitizer": "crawler.py LiveWebCrawler._sanitize_html() — BS4-based structural sanitization",
                "injection_guard": "injection_guard.py — 30+ patterns, 3-layer detection (regex, heuristic, structural)",
                "quarantine_llm": "quarantine_llm.py — Split-Brain dual-LLM with SecureVault (UUID-referenced only)",
            },
        },
    }
