"""
Journeys Router - Multi-city journey planning and booking.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime
from uuid import uuid4

from backend import models
from backend.database import get_db
from backend.services import journey_planner
from backend.middleware.auth import get_current_user

router = APIRouter()


def get_db_dep():
    yield from get_db()


class JourneyPlanRequest(BaseModel):
    duration_days: int
    budget_usd: float
    start_date: str  # ISO format
    preferences: Optional[Dict] = None


class JourneySaveRequest(BaseModel):
    name: str
    plan: Dict


@router.post("/plan")
def plan_journey(
    request: JourneyPlanRequest,
    current_user: models.User = Depends(get_current_user)
):
    """Generate an AI-powered journey plan."""
    try:
        start = datetime.fromisoformat(request.start_date)
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid date format. Use YYYY-MM-DD"
        )

    if request.duration_days < 7:
        raise HTTPException(
            status_code=400, detail="Minimum journey duration is 7 days"
        )

    if request.budget_usd < 500:
        raise HTTPException(status_code=400, detail="Minimum budget is $500")

    plan = journey_planner.generate_journey_plan(
        user_id=current_user.id,
        total_duration_days=request.duration_days,
        total_budget_usd=request.budget_usd,
        start_date=start,
        preferences=request.preferences,
    )

    return plan


@router.post("/save")
def save_journey(
    request: JourneySaveRequest,
    current_user: models.User = Depends(get_current_user)
):
    """Save a journey plan to the database."""
    journey_id = journey_planner.create_journey_from_plan(
        user_id=current_user.id, plan=request.plan, name=request.name
    )

    return {"status": "saved", "journey_id": journey_id}


@router.get("/")
def get_user_journeys(
    db: Session = Depends(get_db_dep),
    current_user: models.User = Depends(get_current_user)
):
    """Get all journeys for current user."""
    journeys = (
        db.query(models.Journey)
        .filter(models.Journey.user_id == current_user.id)
        .order_by(models.Journey.created_at.desc())
        .all()
    )

    result = []
    for journey in journeys:
        legs = (
            db.query(models.JourneyLeg)
            .filter(models.JourneyLeg.journey_id == journey.id)
            .order_by(models.JourneyLeg.order)
            .all()
        )

        result.append(
            {
                "id": journey.id,
                "name": journey.name,
                "status": journey.status,
                "total_budget_usd": journey.total_budget_usd,
                "start_date": journey.start_date.isoformat()
                if journey.start_date
                else None,
                "end_date": journey.end_date.isoformat() if journey.end_date else None,
                "num_cities": len(legs),
                "cities": [leg.city for leg in legs],
            }
        )

    return result


@router.get("/{journey_id}")
def get_journey(journey_id: str, db: Session = Depends(get_db_dep)):
    """Get a journey with all its legs."""
    journey = db.query(models.Journey).filter(models.Journey.id == journey_id).first()

    if not journey:
        raise HTTPException(status_code=404, detail="Journey not found")

    legs = (
        db.query(models.JourneyLeg)
        .filter(models.JourneyLeg.journey_id == journey_id)
        .order_by(models.JourneyLeg.order)
        .all()
    )

    return {
        "id": journey.id,
        "name": journey.name,
        "status": journey.status,
        "total_budget_usd": journey.total_budget_usd,
        "start_date": journey.start_date.isoformat() if journey.start_date else None,
        "end_date": journey.end_date.isoformat() if journey.end_date else None,
        "legs": [
            {
                "order": leg.order,
                "city": leg.city,
                "country": leg.country,
                "hub_id": leg.hub_id,
                "listing_id": leg.listing_id,
                "start_date": leg.start_date.isoformat() if leg.start_date else None,
                "end_date": leg.end_date.isoformat() if leg.end_date else None,
                "estimated_cost_usd": leg.estimated_cost_usd,
                "booking_id": leg.booking_id,
            }
            for leg in legs
        ],
    }


@router.post("/{journey_id}/book")
def book_journey(journey_id: str, db: Session = Depends(get_db_dep)):
    """Book all legs of a journey (creates bookings)."""
    journey = db.query(models.Journey).filter(models.Journey.id == journey_id).first()

    if not journey:
        raise HTTPException(status_code=404, detail="Journey not found")

    if journey.status == "booked":
        raise HTTPException(status_code=400, detail="Journey already booked")

    legs = (
        db.query(models.JourneyLeg)
        .filter(models.JourneyLeg.journey_id == journey_id)
        .all()
    )

    bookings_created = []
    for leg in legs:
        if leg.listing_id:
            booking = models.Booking(
                id=str(uuid4()),
                listing_id=leg.listing_id,
                user_id=journey.user_id,
                start_date=leg.start_date,
                end_date=leg.end_date,
            )
            db.add(booking)
            leg.booking_id = booking.id
            bookings_created.append(booking.id)

    journey.status = "booked"
    db.commit()

    return {
        "status": "booked",
        "journey_id": journey_id,
        "bookings_created": len(bookings_created),
    }
