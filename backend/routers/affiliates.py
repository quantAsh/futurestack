"""
Affiliates Router — API endpoints for affiliate link tracking.
"""
from fastapi import APIRouter
from typing import Optional, Dict, Any

from backend.services.affiliate_service import (
    generate_affiliate_link,
    generate_all_links,
    track_click,
    track_conversion,
    get_affiliate_report,
    get_contextual_recommendations,
)

router = APIRouter()


@router.get("/links")
def get_affiliate_links(
    destination: Optional[str] = None,
) -> Dict[str, Any]:
    """Get all affiliate links, optionally contextualized by destination."""
    context = {"destination": destination} if destination else None
    return {"links": generate_all_links(context)}


@router.get("/links/{partner}")
def get_partner_link(
    partner: str,
    destination: Optional[str] = None,
) -> Dict[str, Any]:
    """Get a specific partner's affiliate link."""
    context = {"destination": destination} if destination else None
    return generate_affiliate_link(partner, context)


@router.post("/click")
def record_click(
    partner: str,
    user_id: Optional[str] = None,
    source: str = "web",
) -> Dict[str, Any]:
    """Record an affiliate link click for tracking."""
    return track_click(partner, user_id, source)


@router.post("/conversion")
def record_conversion(
    partner: str,
    user_id: Optional[str] = None,
    amount: float = 0.0,
) -> Dict[str, Any]:
    """Record an affiliate conversion (admin/webhook)."""
    return track_conversion(partner, user_id, amount)


@router.get("/report")
def affiliate_revenue_report() -> Dict[str, Any]:
    """Get affiliate revenue report with per-partner breakdown."""
    return get_affiliate_report()


@router.get("/recommendations")
def get_recommendations(
    destination: Optional[str] = None,
    features: Optional[str] = None,
) -> Dict[str, Any]:
    """Get contextual affiliate recommendations for a destination.
    
    Features is a comma-separated string: 'insurance,esim,flights'
    """
    feature_list = features.split(",") if features else None
    recs = get_contextual_recommendations(destination, feature_list)
    return {"recommendations": recs}
