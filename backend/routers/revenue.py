"""
Revenue Dashboard API — Aggregates all 7 revenue streams for admin dashboard.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import date, datetime, timedelta
from typing import Dict, Any

from backend import models
from backend.database import get_db

router = APIRouter()


def get_db_dep():
    yield from get_db()


@router.get("/dashboard")
def revenue_dashboard(db: Session = Depends(get_db_dep)) -> Dict[str, Any]:
    """
    Get unified revenue dashboard data across all 7 streams.
    Returns KPIs, per-stream breakdown, and trend data.
    """
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    prev_month_start = (month_start - timedelta(days=1)).replace(day=1)

    # ── Stream 1: AI Subscriptions (Traveler) ──────────────────
    traveler_subs = (
        db.query(models.Subscription)
        .filter(
            models.Subscription.status == "active",
            models.Subscription.tier.in_(["nomad", "pro", "annual"]),
        )
        .all()
    )
    from backend.routers.subscriptions import SUBSCRIPTION_TIERS
    traveler_mrr = sum(
        SUBSCRIPTION_TIERS.get(s.tier, {}).get("price_usd", 0)
        for s in traveler_subs
    )
    # Annual pays $199/yr = $16.58/mo
    traveler_mrr_adj = sum(
        (199 / 12) if s.tier == "annual" else SUBSCRIPTION_TIERS.get(s.tier, {}).get("price_usd", 0)
        for s in traveler_subs
    )

    # ── Stream 2: Booking Commissions ──────────────────────────
    bookings_this_month = (
        db.query(models.Booking)
        .filter(models.Booking.start_date >= month_start)
        .all()
    )
    total_gmv = sum(getattr(b, "total_price", 0) or 0 for b in bookings_this_month)
    total_platform_fee = sum(getattr(b, "platform_fee", 0) or 0 for b in bookings_this_month)

    # ── Stream 3: Affiliate Revenue ────────────────────────────
    try:
        from backend.services.affiliate_service import get_affiliate_report
        affiliate_report = get_affiliate_report()
    except Exception:
        affiliate_report = {"summary": {"total_clicks": 0, "total_conversions": 0, "total_revenue": 0}}

    # ── Stream 4: Host Copilot SaaS ────────────────────────────
    host_subs = (
        db.query(models.Subscription)
        .filter(
            models.Subscription.status == "active",
            models.Subscription.tier.in_(["host_pro", "host_manager"]),
        )
        .all()
    )
    from backend.routers.subscriptions import HOST_TIERS
    host_mrr = sum(
        HOST_TIERS.get(s.tier, {}).get("price_usd", 0)
        for s in host_subs
    )

    # ── Stream 5: Promoted Listings ────────────────────────────
    # Placeholder — promoted listing model TBD
    promoted_count = 0
    promoted_revenue = 0

    # ── Stream 6: Smart Pricing Pro ────────────────────────────
    # Placeholder — add-on model TBD
    smart_pricing_subs = 0
    smart_pricing_mrr = 0

    # ── Stream 7: Enterprise / API ─────────────────────────────
    # Placeholder — contracts TBD
    enterprise_contracts = 0
    enterprise_mrr = 0

    # ── KPIs ───────────────────────────────────────────────────
    total_mrr = round(traveler_mrr_adj + total_platform_fee + host_mrr + smart_pricing_mrr + enterprise_mrr, 2)
    total_subscribers = len(traveler_subs) + len(host_subs) + smart_pricing_subs

    return {
        "kpis": {
            "mrr": total_mrr,
            "total_gmv": round(total_gmv, 2),
            "platform_revenue_mtd": round(total_platform_fee + traveler_mrr_adj + host_mrr, 2),
            "active_subscribers": total_subscribers,
            "month": month_start.strftime("%B %Y"),
        },
        "streams": {
            "ai_subscriptions": {
                "name": "AI Subscriptions",
                "tier": "traveler",
                "icon": "🧠",
                "subscribers": len(traveler_subs),
                "mrr": round(traveler_mrr_adj, 2),
                "breakdown": {
                    "nomad": len([s for s in traveler_subs if s.tier == "nomad"]),
                    "pro": len([s for s in traveler_subs if s.tier == "pro"]),
                    "annual": len([s for s in traveler_subs if s.tier == "annual"]),
                },
            },
            "booking_commissions": {
                "name": "Booking Commissions",
                "tier": "traveler",
                "icon": "🏨",
                "bookings_mtd": len(bookings_this_month),
                "gmv": round(total_gmv, 2),
                "platform_revenue": round(total_platform_fee, 2),
                "avg_commission_rate": round(total_platform_fee / total_gmv * 100, 1) if total_gmv > 0 else 0,
            },
            "affiliates": {
                "name": "Affiliate Revenue",
                "tier": "traveler",
                "icon": "🤝",
                "clicks": affiliate_report["summary"]["total_clicks"],
                "conversions": affiliate_report["summary"]["total_conversions"],
                "revenue": affiliate_report["summary"]["total_revenue"],
                "partners": affiliate_report.get("partners", {}),
            },
            "host_copilot": {
                "name": "Host Copilot SaaS",
                "tier": "host",
                "icon": "🏠",
                "subscribers": len(host_subs),
                "mrr": round(host_mrr, 2),
                "breakdown": {
                    "host_pro": len([s for s in host_subs if s.tier == "host_pro"]),
                    "host_manager": len([s for s in host_subs if s.tier == "host_manager"]),
                },
            },
            "promoted_listings": {
                "name": "Promoted Listings",
                "tier": "host",
                "icon": "📢",
                "active_boosts": promoted_count,
                "revenue": promoted_revenue,
                "status": "coming_soon",
            },
            "smart_pricing_pro": {
                "name": "Smart Pricing Pro",
                "tier": "host",
                "icon": "📊",
                "subscribers": smart_pricing_subs,
                "mrr": smart_pricing_mrr,
                "status": "coming_soon",
            },
            "enterprise": {
                "name": "Enterprise / API",
                "tier": "enterprise",
                "icon": "🏢",
                "contracts": enterprise_contracts,
                "mrr": enterprise_mrr,
                "status": "coming_soon",
            },
        },
    }


@router.get("/streams")
def revenue_streams() -> Dict[str, Any]:
    """Get static configuration of all 7 revenue streams."""
    return {
        "traveler": [
            {"id": "ai_subscriptions", "name": "AI Subscriptions", "icon": "🧠", "model": "SaaS", "prices": ["$9/mo", "$29/mo", "$199/yr"]},
            {"id": "booking_commissions", "name": "Booking Commissions", "icon": "🏨", "model": "Commission", "rates": ["5% guest", "3% host"]},
            {"id": "affiliates", "name": "Affiliate Revenue", "icon": "🤝", "model": "Per-action", "partners": ["SafetyWing", "Airalo", "Kiwi.com", "NordVPN", "Wise"]},
        ],
        "host": [
            {"id": "host_copilot", "name": "Host Copilot SaaS", "icon": "🏠", "model": "SaaS", "prices": ["$19/mo", "$49/mo"]},
            {"id": "promoted_listings", "name": "Promoted Listings", "icon": "📢", "model": "Per-day", "prices": ["$5-15/day"]},
            {"id": "smart_pricing_pro", "name": "Smart Pricing Pro", "icon": "📊", "model": "Add-on", "prices": ["$9/mo"]},
        ],
        "enterprise": [
            {"id": "enterprise", "name": "White-Label AI & API", "icon": "🏢", "model": "Contract", "prices": ["$500-2000/mo"]},
        ],
    }
