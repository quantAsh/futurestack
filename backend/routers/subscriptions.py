"""
Subscriptions Router - Subscription tiers and credit management.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
from uuid import uuid4

from backend import models
from backend.database import get_db

router = APIRouter()


def get_db_dep():
    yield from get_db()


# Tier definitions — Traveler plans
SUBSCRIPTION_TIERS = {
    "free": {
        "price_usd": 0,
        "credits": 10,
        "name": "Free",
        "token_limit": 2000,
        "features": ["basic_search", "safety_briefs", "cost_comparison"],
    },
    "nomad": {
        "price_usd": 9,
        "credits": 100,
        "name": "Nomad",
        "token_limit": 4000,
        "features": ["basic_search", "safety_briefs", "cost_comparison",
                     "trip_planning", "visa_wizard", "community_matching",
                     "destination_brief", "relocation"],
    },
    "pro": {
        "price_usd": 29,
        "credits": 999999,
        "name": "Pro",
        "token_limit": 8000,
        "features": ["basic_search", "safety_briefs", "cost_comparison",
                     "trip_planning", "visa_wizard", "community_matching",
                     "destination_brief", "relocation",
                     "voice_concierge", "do_it_for_me", "priority_support"],
    },
    "annual": {
        "price_usd": 199,
        "credits": 999999,
        "name": "Pro Annual",
        "token_limit": 8000,
        "features": ["basic_search", "safety_briefs", "cost_comparison",
                     "trip_planning", "visa_wizard", "community_matching",
                     "destination_brief", "relocation",
                     "voice_concierge", "do_it_for_me", "priority_support"],
    },
}

# Tier definitions — Host plans
HOST_TIERS = {
    "host_starter": {
        "price_usd": 0,
        "name": "Host Starter",
        "max_listings": 1,
        "features": ["basic_pricing", "manual_replies"],
    },
    "host_pro": {
        "price_usd": 19,
        "name": "Host Pro",
        "max_listings": 5,
        "features": ["basic_pricing", "manual_replies",
                     "smart_pricing", "auto_replies", "review_drafts",
                     "listing_optimization"],
    },
    "host_manager": {
        "price_usd": 49,
        "name": "Host Manager",
        "max_listings": 999,
        "features": ["basic_pricing", "manual_replies",
                     "smart_pricing", "auto_replies", "review_drafts",
                     "listing_optimization",
                     "occupancy_optimizer", "analytics_dashboard", "bulk_operations"],
    },
}

ALL_TIERS = {**SUBSCRIPTION_TIERS, **HOST_TIERS}


class SubscribeRequest(BaseModel):
    user_id: str
    tier: str  # free, pro, unlimited


# Using schemas.Subscription directly
from backend import schemas



class AllocateRequest(BaseModel):
    listing_id: str
    nights: int
    start_date: str


@router.get("/tiers")
def get_tiers():
    """Get available subscription tiers."""
    return SUBSCRIPTION_TIERS


@router.post("/subscribe", response_model=schemas.Subscription)
def subscribe(request: SubscribeRequest, db: Session = Depends(get_db_dep)):
    """Create or update subscription."""
    if request.tier not in SUBSCRIPTION_TIERS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid tier. Choose from: {list(SUBSCRIPTION_TIERS.keys())}",
        )

    tier_info = SUBSCRIPTION_TIERS[request.tier]

    # Check for existing subscription
    existing = (
        db.query(models.Subscription)
        .filter(models.Subscription.user_id == request.user_id)
        .first()
    )

    if existing:
        # Upgrade/downgrade
        existing.tier = request.tier
        existing.monthly_credits = tier_info["credits"]
        existing.status = "active"
        db.commit()
        db.refresh(existing)
        sub = existing
    else:
        # New subscription
        sub = models.Subscription(
            id=str(uuid4()),
            user_id=request.user_id,
            tier=request.tier,
            monthly_credits=tier_info["credits"],
            used_credits=0,
            status="active",
        )
        db.add(sub)
        db.commit()
        db.refresh(sub)

        db.refresh(sub)

    return sub


@router.get("/me")
def get_my_subscription(user_id: str, db: Session = Depends(get_db_dep)):
    """Get current user's subscription."""
    sub = (
        db.query(models.Subscription)
        .filter(models.Subscription.user_id == user_id)
        .first()
    )

    if not sub:
        return {"tier": "free", "credits": 0, "used": 0, "remaining": 0}

    return {
        "id": sub.id,
        "tier": sub.tier,
        "status": sub.status,
        "credits": sub.monthly_credits,
        "used": sub.used_credits,
        "remaining": sub.monthly_credits - sub.used_credits,
        "tier_name": SUBSCRIPTION_TIERS.get(sub.tier, {}).get("name", "Unknown"),
    }


@router.post("/allocate")
def allocate_stay(
    user_id: str, request: AllocateRequest, db: Session = Depends(get_db_dep)
):
    """Use subscription credits to book a stay."""
    sub = (
        db.query(models.Subscription)
        .filter(models.Subscription.user_id == user_id)
        .filter(models.Subscription.status == "active")
        .first()
    )

    if not sub:
        raise HTTPException(status_code=400, detail="No active subscription")

    remaining = sub.monthly_credits - sub.used_credits
    if request.nights > remaining:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient credits. Have {remaining}, need {request.nights}",
        )

    # Verify listing exists
    listing = (
        db.query(models.Listing).filter(models.Listing.id == request.listing_id).first()
    )
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    # Create booking
    start = datetime.fromisoformat(request.start_date)
    end = start + timedelta(days=request.nights)

    booking = models.Booking(
        id=str(uuid4()),
        listing_id=request.listing_id,
        user_id=user_id,
        start_date=start,
        end_date=end,
    )
    db.add(booking)

    # Deduct credits
    sub.used_credits += request.nights
    db.commit()

    return {
        "status": "allocated",
        "booking_id": booking.id,
        "nights_used": request.nights,
        "remaining_credits": sub.monthly_credits - sub.used_credits,
    }


@router.post("/reset-credits")
def reset_monthly_credits(db: Session = Depends(get_db_dep)):
    """Admin: Reset all subscription credits (run monthly via cron)."""
    subs = (
        db.query(models.Subscription)
        .filter(models.Subscription.status == "active")
        .all()
    )

    count = 0
    for sub in subs:
        sub.used_credits = 0
        count += 1

    db.commit()
    return {"status": "reset", "subscriptions_updated": count}

# --- PHASE 14: Stripe Integration ---

from fastapi import Request, Header
from backend.config import settings
from backend.services import stripe_service


class CheckoutRequest(BaseModel):
    tier: str  # pro or unlimited
    success_url: str
    cancel_url: str


@router.post("/checkout")
def create_checkout(
    request: CheckoutRequest,
    user_id: str,
    db: Session = Depends(get_db_dep),
):
    """Create a Stripe Checkout session for subscription."""
    if request.tier not in ["pro", "enterprise"]:
        raise HTTPException(status_code=400, detail="Invalid tier for checkout")

    # Get user
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get existing subscription for Stripe customer ID
    existing = (
        db.query(models.Subscription)
        .filter(models.Subscription.user_id == user_id)
        .first()
    )

    try:
        result = stripe_service.create_checkout_session(
            user_id=user_id,
            user_email=user.email or f"{user_id}@placeholder.com",
            tier=request.tier,
            success_url=request.success_url,
            cancel_url=request.cancel_url,
            stripe_customer_id=existing.stripe_customer_id if existing else None,
        )
        
        # Store customer ID if new
        if existing and not existing.stripe_customer_id:
            existing.stripe_customer_id = result["customer_id"]
            db.commit()

        return {"checkout_url": result["url"], "session_id": result["session_id"]}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="Stripe-Signature"),
):
    """Handle Stripe webhook events."""
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing signature")

    payload = await request.body()

    try:
        result = stripe_service.handle_webhook(payload, stripe_signature)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Process the event
    if result.get("processed"):
        from backend.database import SessionLocal
        db = SessionLocal()
        try:
            if result.get("event_type") == "checkout.session.completed":
                # Activate subscription
                user_id = result.get("user_id")
                tier = result.get("tier")
                tier_info = SUBSCRIPTION_TIERS.get(tier, {})

                existing = (
                    db.query(models.Subscription)
                    .filter(models.Subscription.user_id == user_id)
                    .first()
                )

                if existing:
                    existing.tier = tier
                    existing.status = "active"
                    existing.monthly_credits = tier_info.get("credits", 0)
                    sub.stripe_customer_id = result.get("customer_id")
                    sub.stripe_subscription_id = result.get("subscription_id")
                    
                    # Update period end if available (depends on stripe_service return)
                    # Assuming result might have it, else default
                    
                else:
                    sub = models.Subscription(
                        id=str(uuid4()),
                        user_id=user_id,
                        tier=tier,
                        status="active",
                        monthly_credits=tier_info.get("credits", 0),
                        stripe_customer_id=result.get("customer_id"),
                        stripe_subscription_id=result.get("subscription_id"),
                    )
                    db.add(sub)

                db.commit()

            elif result.get("event_type") == "customer.subscription.updated":
                # Handle updates (renewals, tier changes)
                subscription_id = result.get("subscription_id")
                sub = db.query(models.Subscription).filter(models.Subscription.stripe_subscription_id == subscription_id).first()
                if sub:
                    sub.status = result.get("status", sub.status)
                    # Update tier if changed? logic depends on stripe metadata or product mapping
                    # For now, just trust status. 
                    if sub.status == "active":
                         # Reset credits on renewal? Or monthly logic separately?
                         # Usually handled by a separate cron or checking period_end
                         pass
                    db.commit()
            
            elif result.get("event_type") == "customer.subscription.deleted" or result.get("cancelled"):
                # Handle cancellation
                subscription_id = result.get("subscription_id")
                sub = (
                    db.query(models.Subscription)
                    .filter(
                        models.Subscription.stripe_subscription_id
                        == subscription_id
                    )
                    .first()
                )
                if sub:
                    sub.status = "cancelled"
                    sub.tier = "free"
                    sub.monthly_credits = 0
                    db.commit()

            elif result.get("event_type") == "invoice.payment_failed":
                 subscription_id = result.get("subscription_id")
                 sub = db.query(models.Subscription).filter(models.Subscription.stripe_subscription_id == subscription_id).first()
                 if sub:
                     sub.status = "past_due"
                     db.commit()

        finally:
            db.close()

    return {"received": True}


@router.post("/portal")
def create_portal_session(
    user_id: str,
    return_url: str,
    db: Session = Depends(get_db_dep),
):
    """Create a Stripe Customer Portal session."""
    sub = (
        db.query(models.Subscription)
        .filter(models.Subscription.user_id == user_id)
        .first()
    )

    if not sub or not sub.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No Stripe customer found")

    try:
        url = stripe_service.create_portal_session(sub.stripe_customer_id, return_url)
        return {"portal_url": url}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/cancel")
def cancel_subscription(
    user_id: str,
    db: Session = Depends(get_db_dep),
):
    """Cancel subscription at period end."""
    sub = (
        db.query(models.Subscription)
        .filter(models.Subscription.user_id == user_id)
        .first()
    )

    if not sub or not sub.stripe_subscription_id:
        raise HTTPException(status_code=400, detail="No active subscription found")

    try:
        result = stripe_service.cancel_subscription(sub.stripe_subscription_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
