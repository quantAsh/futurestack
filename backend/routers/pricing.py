"""
Pricing Router - Dynamic pricing endpoints for hosts.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date

from backend import models
from backend.database import get_db
from backend.services import pricing_engine

router = APIRouter()


def get_db_dep():
    yield from get_db()


@router.get("/{listing_id}/suggest")
def get_price_suggestion(
    listing_id: str,
    target_date: Optional[str] = None,
    db: Session = Depends(get_db_dep),
):
    """
    Get dynamic price suggestion for a listing.

    - If target_date provided (YYYY-MM-DD), returns suggestion for that date
    - Otherwise returns AI recommendation for current month
    """
    # Verify listing exists
    listing = db.query(models.Listing).filter(models.Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    if target_date:
        try:
            target = date.fromisoformat(target_date)
            return pricing_engine.calculate_dynamic_price(listing_id, target)
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid date format. Use YYYY-MM-DD"
            )
    else:
        return pricing_engine.get_ai_pricing_recommendation(listing_id)


@router.get("/{listing_id}/month/{year}/{month}")
def get_monthly_pricing(
    listing_id: str, year: int, month: int, db: Session = Depends(get_db_dep)
):
    """Get price suggestions for each day in a month."""
    # Verify listing exists
    listing = db.query(models.Listing).filter(models.Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="Month must be 1-12")

    suggestions = pricing_engine.get_price_suggestions_for_month(
        listing_id, year, month
    )

    # Calculate summary stats
    if suggestions:
        prices = [s["suggested_price"] for s in suggestions]
        summary = {
            "avg_price": round(sum(prices) / len(prices), 2),
            "min_price": min(prices),
            "max_price": max(prices),
            "base_price": suggestions[0]["base_price"],
            "total_days": len(suggestions),
        }
    else:
        summary = {}

    return {
        "listing_id": listing_id,
        "year": year,
        "month": month,
        "summary": summary,
        "daily_prices": suggestions,
    }


@router.get("/{listing_id}/factors")
def get_pricing_factors(listing_id: str, db: Session = Depends(get_db_dep)):
    """Get the pricing factors used for a listing."""
    listing = db.query(models.Listing).filter(models.Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    return {
        "listing_id": listing_id,
        "base_price": listing.price_usd,
        "seasonality_factors": pricing_engine.SEASONALITY,
        "day_of_week_factors": pricing_engine.DAY_OF_WEEK,
        "note": "Final price = base_price * seasonality * day_of_week * demand",
    }


# ============================================================================
# ML-Powered Dynamic Pricing (event-aware, demand curves)
# ============================================================================

from backend.services.ml_pricing import get_enhanced_dynamic_price


@router.get("/ml/{listing_id}/dynamic-price")
def get_ml_dynamic_price(
    listing_id: str,
    check_in: str,
    check_out: str,
    db: Session = Depends(get_db_dep),
):
    """
    Get ML-powered dynamic price for a listing with event-aware adjustments.

    Uses demand curves, local event detection, and seasonality modeling
    for more accurate pricing than static multipliers.
    """
    from datetime import datetime

    listing = db.query(models.Listing).filter(models.Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    try:
        ci = datetime.fromisoformat(check_in)
        co = datetime.fromisoformat(check_out)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    nights = (co - ci).days
    if nights <= 0:
        raise HTTPException(status_code=400, detail="check_out must be after check_in")

    location = listing.city or listing.country or "unknown"

    result = get_enhanced_dynamic_price(
        base_price=listing.price_usd,
        check_in_date=ci,
        stay_nights=nights,
        location=location,
    )

    return {
        "listing_id": listing_id,
        "listing_name": listing.name,
        "location": location,
        "check_in": check_in,
        "check_out": check_out,
        "nights": nights,
        **result,
    }

