"""
Analytics Router - Nomad spending and travel insights.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
from uuid import uuid4

from backend import models
from backend.database import get_db
from backend.utils import get_current_user, require_current_user, require_admin

router = APIRouter()


def get_db_dep():
    yield from get_db()


SPENDING_CATEGORIES = [
    "accommodation",
    "food",
    "transport",
    "coworking",
    "entertainment",
    "other",
]


class SpendingCreate(BaseModel):
    user_id: str
    category: str
    amount_usd: float
    city: Optional[str] = None
    country: Optional[str] = None
    date: str  # YYYY-MM-DD
    notes: Optional[str] = None


@router.post("/spending")
def add_spending(
    record: SpendingCreate,
    db: Session = Depends(get_db_dep),
    current_user: models.User = Depends(require_current_user),
):
    """Log a spending record. User can only add records for themselves."""
    if record.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot add spending for another user")
    if record.category not in SPENDING_CATEGORIES:
        raise HTTPException(
            status_code=400, detail=f"Invalid category. Choose: {SPENDING_CATEGORIES}"
        )

    db_record = models.SpendingRecord(
        id=str(uuid4()),
        user_id=record.user_id,
        category=record.category,
        amount_usd=record.amount_usd,
        city=record.city,
        country=record.country,
        date=datetime.fromisoformat(record.date),
        notes=record.notes,
    )
    db.add(db_record)
    db.commit()
    return {"id": db_record.id, "status": "recorded"}


@router.get("/spending")
def get_spending(
    months: int = 3,
    db: Session = Depends(get_db_dep),
    current_user: models.User = Depends(require_current_user),
):
    """Get spending breakdown by category for the authenticated user."""
    user_id = current_user.id
    cutoff = datetime.now() - timedelta(days=months * 30)

    records = (
        db.query(models.SpendingRecord)
        .filter(models.SpendingRecord.user_id == user_id)
        .filter(models.SpendingRecord.date >= cutoff)
        .all()
    )

    # Aggregate by category
    by_category = {}
    total = 0
    for r in records:
        cat = r.category
        if cat not in by_category:
            by_category[cat] = 0
        by_category[cat] += r.amount_usd
        total += r.amount_usd

    return {
        "user_id": user_id,
        "period_months": months,
        "total_usd": round(total, 2),
        "by_category": {k: round(v, 2) for k, v in by_category.items()},
        "avg_monthly": round(total / months, 2) if months > 0 else 0,
    }


@router.get("/locations")
def get_locations(
    db: Session = Depends(get_db_dep),
    current_user: models.User = Depends(require_current_user),
):
    """Get cities visited and time spent for the authenticated user."""
    user_id = current_user.id
    # Get bookings with listings in a single query (eliminates N+1)
    bookings = db.query(models.Booking).filter(models.Booking.user_id == user_id).all()

    if not bookings:
        return {"user_id": user_id, "cities": []}

    # Bulk-fetch all associated listings in one query
    listing_ids = list(set(b.listing_id for b in bookings if b.listing_id))
    listings_map = {}
    if listing_ids:
        listings = db.query(models.Listing).filter(models.Listing.id.in_(listing_ids)).all()
        listings_map = {l.id: l for l in listings}

    cities = {}
    for b in bookings:
        listing = listings_map.get(b.listing_id)
        if listing:
            key = f"{listing.city}, {listing.country}"
            if key not in cities:
                cities[key] = {
                    "city": listing.city,
                    "country": listing.country,
                    "nights": 0,
                    "visits": 0,
                }

            nights = (
                (b.end_date - b.start_date).days if b.end_date and b.start_date else 0
            )
            cities[key]["nights"] += nights
            cities[key]["visits"] += 1

    # Sort by nights
    sorted_cities = sorted(cities.values(), key=lambda x: x["nights"], reverse=True)

    return {
        "user_id": user_id,
        "total_cities": len(cities),
        "total_nights": sum(c["nights"] for c in sorted_cities),
        "cities": sorted_cities[:10],  # Top 10
    }


@router.get("/summary")
def get_summary(
    db: Session = Depends(get_db_dep),
    current_user: models.User = Depends(require_current_user),
):
    """Get overall nomad statistics for the authenticated user."""
    user_id = current_user.id
    # Bookings count
    bookings = db.query(models.Booking).filter(models.Booking.user_id == user_id).all()

    total_nights = sum(
        (b.end_date - b.start_date).days
        for b in bookings
        if b.end_date and b.start_date
    )

    # Spending (last 12 months)
    cutoff = datetime.now() - timedelta(days=365)
    spending = (
        db.query(func.sum(models.SpendingRecord.amount_usd))
        .filter(models.SpendingRecord.user_id == user_id)
        .filter(models.SpendingRecord.date >= cutoff)
        .scalar()
        or 0
    )

    # Unique locations
    unique_cities = set()
    for b in bookings:
        listing = (
            db.query(models.Listing).filter(models.Listing.id == b.listing_id).first()
        )
        if listing:
            unique_cities.add(listing.city)

    # Subscription status
    sub = (
        db.query(models.Subscription)
        .filter(models.Subscription.user_id == user_id)
        .first()
    )

    return {
        "user_id": user_id,
        "total_bookings": len(bookings),
        "total_nights_traveled": total_nights,
        "unique_cities_visited": len(unique_cities),
        "spending_last_12mo_usd": round(spending, 2),
        "avg_cost_per_night": round(spending / total_nights, 2)
        if total_nights > 0
        else 0,
        "subscription_tier": sub.tier if sub else "free",
        "nomad_level": "Explorer"
        if total_nights < 30
        else "Traveler"
        if total_nights < 90
        else "Nomad"
        if total_nights < 180
        else "Global Citizen",
    }


@router.get("/monthly-trend")
def get_monthly_trend(
    months: int = 6,
    db: Session = Depends(get_db_dep),
    current_user: models.User = Depends(require_current_user),
):
    """Get spending trend by month for the authenticated user."""
    user_id = current_user.id
    cutoff = datetime.now() - timedelta(days=months * 30)

    records = (
        db.query(models.SpendingRecord)
        .filter(models.SpendingRecord.user_id == user_id)
        .filter(models.SpendingRecord.date >= cutoff)
        .all()
    )

    by_month = {}
    for r in records:
        key = r.date.strftime("%Y-%m")
        if key not in by_month:
            by_month[key] = 0
        by_month[key] += r.amount_usd

    return {
        "user_id": user_id,
        "trend": [
            {"month": k, "amount_usd": round(v, 2)} for k, v in sorted(by_month.items())
        ],
    }


# ============================================
# AI USAGE ANALYTICS
# ============================================

@router.get("/ai-usage")
def get_ai_usage(
    db: Session = Depends(get_db_dep),
    current_user: models.User = Depends(require_current_user),
):
    """Get AI usage summary for the authenticated user."""
    from backend.services.ai_metering import get_user_usage_summary
    return get_user_usage_summary(current_user.id, db)


@router.get("/ai-usage/daily")
def get_ai_usage_daily(
    db: Session = Depends(get_db_dep),
    admin: models.User = Depends(require_admin),
):
    """Get daily AI usage aggregates (admin only)."""
    from backend.services.ai_metering import get_daily_usage_summary
    return {"daily_usage": get_daily_usage_summary(db)}


@router.get("/ai-usage/by-endpoint")
def get_ai_usage_by_endpoint(
    db: Session = Depends(get_db_dep),
    admin: models.User = Depends(require_admin),
):
    """Get AI usage breakdown by endpoint (admin only)."""
    results = db.query(
        models.AIUsageMetrics.endpoint,
        func.count(models.AIUsageMetrics.id).label("request_count"),
        func.sum(models.AIUsageMetrics.total_tokens).label("total_tokens"),
        func.sum(models.AIUsageMetrics.cost_cents).label("total_cost_cents"),
    ).group_by(
        models.AIUsageMetrics.endpoint
    ).all()
    
    return {
        "by_endpoint": [
            {
                "endpoint": r.endpoint,
                "request_count": r.request_count,
                "total_tokens": r.total_tokens or 0,
                "total_cost_usd": (r.total_cost_cents or 0) / 100,
            }
            for r in results
        ]
    }


@router.get("/ai-usage/by-model")
def get_ai_usage_by_model(
    db: Session = Depends(get_db_dep),
    admin: models.User = Depends(require_admin),
):
    """Get AI usage breakdown by model (admin only)."""
    results = db.query(
        models.AIUsageMetrics.model,
        models.AIUsageMetrics.provider,
        func.count(models.AIUsageMetrics.id).label("request_count"),
        func.sum(models.AIUsageMetrics.total_tokens).label("total_tokens"),
        func.sum(models.AIUsageMetrics.cost_cents).label("total_cost_cents"),
        func.avg(models.AIUsageMetrics.latency_ms).label("avg_latency_ms"),
    ).group_by(
        models.AIUsageMetrics.model,
        models.AIUsageMetrics.provider,
    ).all()
    
    return {
        "by_model": [
            {
                "model": r.model,
                "provider": r.provider,
                "request_count": r.request_count,
                "total_tokens": r.total_tokens or 0,
                "total_cost_usd": (r.total_cost_cents or 0) / 100,
                "avg_latency_ms": int(r.avg_latency_ms) if r.avg_latency_ms else 0,
            }
            for r in results
        ]
    }

# ============================================
# USER JOURNEY EVENTS
# ============================================

class AnalyticsEvent(BaseModel):
    name: str
    properties: Optional[dict] = {}
    context: Optional[dict] = {}

@router.post("/events", status_code=202)
def track_event(
    event: AnalyticsEvent,
    current_user: models.User = Depends(get_current_user), 
    # Note: We use get_current_user from utils, imported below or at top
):
    """Track a frontend user journey event."""
    from backend.services.analytics_service import analytics_service
    analytics_service.track(
        event_name=event.name,
        user_id=current_user.id,
        properties=event.properties,
        context=event.context
    )
    return {"status": "tracked"}


# ============================================
# ADMIN: AGENT & SYSTEMS ANALYTICS
# ============================================

@router.get("/admin/agents/fleet")
def agent_fleet(admin: models.User = Depends(require_admin)):
    """Get status of all AI agents in the fleet (admin only)."""
    from backend.services.agent_analytics import get_agent_fleet_status
    return get_agent_fleet_status()


@router.get("/admin/system/health")
def system_health(admin: models.User = Depends(require_admin)):
    """Get health status of system services (admin only)."""
    from backend.services.agent_analytics import get_system_health
    return get_system_health()


@router.get("/admin/system/circuits")
def circuit_status(admin: models.User = Depends(require_admin)):
    """Get circuit breaker states (admin only)."""
    from backend.services.agent_analytics import get_circuit_breaker_status
    return get_circuit_breaker_status()


@router.get("/admin/ai/costs")
def ai_costs(admin: models.User = Depends(require_admin)):
    """Get AI token usage and cost summary (admin only)."""
    from backend.services.agent_analytics import get_ai_cost_summary
    return get_ai_cost_summary()


# ============================================
# ADMIN: SAFETY & ESCALATIONS
# ============================================

@router.get("/admin/safety/escalations")
def safety_escalations(admin: models.User = Depends(require_admin)):
    """Get escalation queue with SLA tracking (admin only)."""
    from backend.services.safety_ops import get_escalation_dashboard
    return get_escalation_dashboard()


@router.get("/admin/safety/map")
def safety_map(admin: models.User = Depends(require_admin)):
    """Get traveler safety map (admin only)."""
    from backend.services.safety_ops import get_safety_map
    return get_safety_map()


@router.get("/admin/safety/timeline")
def safety_timeline(admin: models.User = Depends(require_admin)):
    """Get incident timeline (admin only)."""
    from backend.services.safety_ops import get_incident_timeline
    return get_incident_timeline()


@router.get("/admin/safety/stats")
def safety_stats(admin: models.User = Depends(require_admin)):
    """Get safety coverage and response stats (admin only)."""
    from backend.services.safety_ops import get_safety_stats
    return get_safety_stats()


# ============================================
# ADMIN: BOOKING OPERATIONS
# ============================================

@router.get("/admin/bookings/pipeline")
def booking_pipeline(admin: models.User = Depends(require_admin)):
    """Get booking job pipeline status (admin only)."""
    from backend.services.booking_ops import get_booking_pipeline
    return get_booking_pipeline()


@router.get("/admin/bookings/payments")
def booking_payments(admin: models.User = Depends(require_admin)):
    """Get payment authorization and settlement status (admin only)."""
    from backend.services.booking_ops import get_payment_gates
    return get_payment_gates()


@router.get("/admin/bookings/funnel")
def booking_funnel(admin: models.User = Depends(require_admin)):
    """Get booking funnel drop-off analysis (admin only)."""
    from backend.services.booking_ops import get_booking_funnel
    return get_booking_funnel()


@router.get("/admin/bookings/agents")
def booking_agents(admin: models.User = Depends(require_admin)):
    """Get browser agent job history (admin only)."""
    from backend.services.booking_ops import get_agent_jobs
    return get_agent_jobs()


