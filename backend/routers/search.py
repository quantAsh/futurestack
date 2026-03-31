from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from backend.database import get_db
from backend.services.smart_search import smart_search_service

router = APIRouter()


class SmartSearchRequest(BaseModel):
    query: str


class SmartSearchResult(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    price_usd: Optional[float] = None
    # Add other needed fields for frontend


@router.post("/smart", response_model=List[SmartSearchResult])
async def smart_search(request: SmartSearchRequest, db: Session = Depends(get_db)):
    """
    Perform a natural language search for listings.
    """
    import structlog
    _logger = structlog.get_logger("nomadnest.search")
    try:
        listings = smart_search_service.search_listings(request.query, db)

        # Track analytics event (anonymous — no auth required for search)
        from backend.services.analytics_service import analytics_service
        analytics_service.track(
            event_name="search_performed",
            user_id="anonymous",
            properties={"query": request.query, "result_count": len(listings)},
        )

        return listings
    except Exception as e:
        _logger.error("smart_search_failed", query=request.query, error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Search service error")


# ============================================================================
# Cross-Provider Smart Search (NLP + OTA Aggregator)
# ============================================================================


class SmartOTARequest(BaseModel):
    query: str
    check_in: Optional[str] = None  # YYYY-MM-DD, extracted from query if missing
    check_out: Optional[str] = None
    guests: int = 1


@router.post("/smart-ota")
async def smart_ota_search(request: SmartOTARequest, db: Session = Depends(get_db)):
    """
    Natural language search across ALL providers.

    Combines Gemini NLP parsing with the OTA aggregator.
    Example: "cheap retreat in Bali under $500 with pool"
    """
    from backend.services.ota.aggregator import AggregatorService
    from datetime import date, timedelta

    # Step 1: Extract structured filters via LLM
    filters = smart_search_service._extract_filters(request.query)

    # Step 2: Determine location and dates
    location = filters.get("location") or "worldwide"
    max_price = filters.get("max_price")

    # Use provided dates or default to next month
    if request.check_in:
        check_in = date.fromisoformat(request.check_in)
    else:
        check_in = date.today() + timedelta(days=30)

    if request.check_out:
        check_out = date.fromisoformat(request.check_out)
    else:
        check_out = check_in + timedelta(days=7)

    # Step 3: Run OTA aggregator with extracted location
    aggregator = AggregatorService(db)
    ota_results = await aggregator.aggregate_search(
        location=location,
        check_in=check_in,
        check_out=check_out,
        guests=request.guests,
        max_price=max_price,
    )

    # Step 4: Also search native listings via SmartSearch for richer DB matches
    try:
        native_smart = smart_search_service.search_listings(request.query, db)
        native_results = [
            {
                "id": l.id,
                "provider_id": "smart_search",
                "name": l.name,
                "url": f"https://nomadnest.ai/listing/{l.id}",
                "price_per_night": l.price_usd / 30 if l.price_usd else None,
                "total_price": l.price_usd or 0,
                "currency": "USD",
                "location": f"{l.city}, {l.country}" if l.city else l.country,
                "amenities": l.features or [],
            }
            for l in native_smart[:5]
        ]
    except Exception:
        native_results = []

    # Merge and deduplicate (prefer OTA results, add unique native matches)
    ota_ids = {r.get("id") for r in ota_results.get("results", [])}
    unique_native = [n for n in native_results if n["id"] not in ota_ids]

    all_results = ota_results.get("results", []) + unique_native

    return {
        "query": request.query,
        "extracted_filters": filters,
        "results": all_results,
        "total_found": len(all_results),
        "providers_searched": ota_results.get("providers_searched", []) + ["smart_search"],
        "providers_succeeded": ota_results.get("providers_succeeded", []) + (["smart_search"] if native_results else []),
    }

