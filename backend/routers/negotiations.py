"""
Negotiations Router - AI-powered price negotiation.
"""
import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from uuid import uuid4

from backend import models
from backend.database import get_db
from backend.middleware.auth import get_current_user

router = APIRouter()
logger = structlog.get_logger("nomadnest.negotiations")


def get_db_dep():
    yield from get_db()


class NegotiationRequest(BaseModel):
    listing_id: str
    offered_price: float
    message: Optional[str] = None
    stay_duration_days: Optional[int] = 30


from backend.services.negotiation_agent import negotiation_agent

@router.post("/start")
def start_negotiation(
    request: NegotiationRequest, 
    db: Session = Depends(get_db_dep),
    current_user: models.User = Depends(get_current_user)
):
    """Start a price negotiation for a listing."""
    # Get listing
    listing = (
        db.query(models.Listing).filter(models.Listing.id == request.listing_id).first()
    )

    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    original_price = listing.price_usd

    # Check for existing pending negotiation
    existing = (
        db.query(models.Negotiation)
        .filter(models.Negotiation.listing_id == request.listing_id)
        .filter(models.Negotiation.user_id == current_user.id)
        .filter(models.Negotiation.status == "pending")
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=400,
            detail="You already have a pending negotiation for this listing",
        )

    # Calculate AI response
    try:
        ai_response = negotiation_agent.negotiate_price(
            listing=listing, 
            user_offer=request.offered_price,
            stay_duration=request.stay_duration_days or 30,
            history=[]
        )
    except Exception as e:
        logger.error("negotiation_agent_failed", listing_id=request.listing_id, offer=request.offered_price, error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Negotiation agent unavailable.")

    # Create negotiation record
    negotiation = models.Negotiation(
        id=str(uuid4()),
        listing_id=request.listing_id,
        user_id=current_user.id,
        original_price=original_price,
        offered_price=request.offered_price,
        counter_price=ai_response.get("price") if ai_response.get("action") == "counter" else None,
        status="pending", # Temporary, will be set below
        message=request.message,
    )

    # Set status correctly
    action = ai_response.get("action", "counter")
    if action == "accept":
        negotiation.status = "accepted"
        negotiation.counter_price = request.offered_price
    elif action == "counter":
        negotiation.status = "countered"
    else:
        negotiation.status = "rejected"
    
    # Store the AI's message (optional: add a message column or send in response)
    # The models.Negotiation has a 'message' column, but that's usually the *user's* message.
    # We should return the AI message in the API response.

    db.add(negotiation)
    db.commit()
    db.refresh(negotiation)

    # Track analytics event
    from backend.services.analytics_service import analytics_service
    analytics_service.track(
        event_name="negotiation_started",
        user_id=current_user.id,
        properties={
            "listing_id": request.listing_id,
            "offered_price": request.offered_price,
            "original_price": original_price,
            "ai_action": action,
        },
    )

    return {
        "negotiation_id": negotiation.id,
        "listing_id": request.listing_id,
        "original_price": original_price,
        "your_offer": request.offered_price,
        "action": action,
        "counter_price": negotiation.counter_price,
        "message": ai_response.get("message", "Processed by Agent.")
    }


@router.post("/{negotiation_id}/accept")
def accept_counter(negotiation_id: str, db: Session = Depends(get_db_dep)):
    """Accept a counter-offer and proceed to booking."""
    negotiation = (
        db.query(models.Negotiation)
        .filter(models.Negotiation.id == negotiation_id)
        .first()
    )

    if not negotiation:
        raise HTTPException(status_code=404, detail="Negotiation not found")

    if negotiation.status != "countered":
        raise HTTPException(
            status_code=400, detail="This negotiation cannot be accepted"
        )

    negotiation.status = "accepted"
    db.commit()

    return {
        "status": "accepted",
        "negotiation_id": negotiation_id,
        "final_price": negotiation.counter_price,
        "message": "Great! You can now book at the agreed price.",
        "next_step": f"POST /api/v1/bookings with price_override={negotiation.counter_price}",
    }


@router.post("/{negotiation_id}/counter")
def user_counter(
    negotiation_id: str, new_offer: float, db: Session = Depends(get_db_dep)
):
    """Submit a counter-counter offer."""
    negotiation = (
        db.query(models.Negotiation)
        .filter(models.Negotiation.id == negotiation_id)
        .first()
    )

    if not negotiation:
        raise HTTPException(status_code=404, detail="Negotiation not found")

    if negotiation.status not in ["countered", "rejected"]:
        raise HTTPException(status_code=400, detail="Cannot counter this negotiation")

    # Recalculate with new offer using AI Agent
    try:
        # Fetch listing details for context
        listing = db.query(models.Listing).filter(models.Listing.id == negotiation.listing_id).first()
        
        ai_response = negotiation_agent.negotiate_price(
            listing=listing,
            user_offer=new_offer,
            stay_duration=30, # Should ideally come from booking context
            history=[{"role": "user", "price": negotiation.offered_price, "action": "offer"}] # Minimal history
        )
    except Exception as e:
        logger.error("counter_negotiation_failed", negotiation_id=negotiation_id, new_offer=new_offer, error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Negotiation agent unavailable.")

    negotiation.offered_price = new_offer
    
    action = ai_response.get("action", "counter")
    
    if action == "accept":
        negotiation.status = "accepted"
        negotiation.counter_price = new_offer
    elif action == "counter":
        negotiation.status = "countered"
        negotiation.counter_price = ai_response.get("price")
    else:
        # Even if rejected, we keep status as rejected or countered? 
        # Usually if rejected, negotiation might end.
        negotiation.status = "rejected"

    db.commit()

    return {
        "negotiation_id": negotiation_id,
        "your_new_offer": new_offer,
        "action": action,
        "counter_price": negotiation.counter_price,
        "message": ai_response.get("message", "Processed by Agent.")
    }


@router.get("/user/{user_id}")
def get_user_negotiations(user_id: str, db: Session = Depends(get_db_dep)):
    """Get all negotiations for a user."""
    negotiations = (
        db.query(models.Negotiation)
        .filter(models.Negotiation.user_id == user_id)
        .order_by(models.Negotiation.created_at.desc())
        .all()
    )

    return [
        {
            "id": n.id,
            "listing_id": n.listing_id,
            "original_price": n.original_price,
            "offered_price": n.offered_price,
            "counter_price": n.counter_price,
            "status": n.status,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in negotiations
    ]
