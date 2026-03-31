"""
Events Router - Community events and local happenings.
Includes festivals, conferences, and meetups for pricing integration.
"""
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend import models
from backend.middleware.auth import get_current_user

router = APIRouter()


# ============================================
# SCHEMAS
# ============================================

class EventCreate(BaseModel):
    name: str
    description: Optional[str] = None
    event_type: str = "conference"  # conference, festival, meetup, holiday
    location: str
    start_date: datetime
    end_date: Optional[datetime] = None
    price_impact_percent: float = 0.0  # How much it affects local pricing
    tags: Optional[List[str]] = None
    source_url: Optional[str] = None


class EventResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    event_type: str
    location: str
    start_date: datetime
    end_date: Optional[datetime]
    price_impact_percent: float
    tags: List[str]
    source_url: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================
# ENDPOINTS
# ============================================

@router.get("/events", response_model=List[EventResponse])
def list_events(
    location: Optional[str] = None,
    event_type: Optional[str] = None,
    start_after: Optional[datetime] = None,
    start_before: Optional[datetime] = None,
    limit: int = Query(default=50, le=100),
    db: Session = Depends(get_db),
):
    """List events with optional filters."""
    query = db.query(models.Event)
    
    if location:
        query = query.filter(models.Event.location.ilike(f"%{location}%"))
    if event_type:
        query = query.filter(models.Event.event_type == event_type)
    if start_after:
        query = query.filter(models.Event.start_date >= start_after)
    if start_before:
        query = query.filter(models.Event.start_date <= start_before)
    
    events = query.order_by(models.Event.start_date).limit(limit).all()
    return events


@router.get("/events/upcoming")
def get_upcoming_events(
    location: Optional[str] = None,
    days: int = Query(default=30, le=90),
    db: Session = Depends(get_db),
):
    """Get upcoming events for the next N days."""
    now = datetime.utcnow()
    end_date = now + timedelta(days=days)
    
    query = db.query(models.Event).filter(
        models.Event.start_date >= now,
        models.Event.start_date <= end_date,
    )
    
    if location:
        query = query.filter(models.Event.location.ilike(f"%{location}%"))
    
    events = query.order_by(models.Event.start_date).all()
    
    return {
        "events": events,
        "count": len(events),
        "date_range": {"start": now.isoformat(), "end": end_date.isoformat()},
    }


@router.get("/events/{event_id}", response_model=EventResponse)
def get_event(event_id: str, db: Session = Depends(get_db)):
    """Get a specific event by ID."""
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.post("/events", response_model=EventResponse)
def create_event(
    event: EventCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Create a new event (admin only)."""
    if current_user.role not in ("admin", "host"):
        raise HTTPException(status_code=403, detail="Not authorized")
    
    db_event = models.Event(
        id=str(uuid4()),
        name=event.name,
        description=event.description,
        event_type=event.event_type,
        location=event.location,
        start_date=event.start_date,
        end_date=event.end_date,
        price_impact_percent=event.price_impact_percent,
        tags=event.tags or [],
        source_url=event.source_url,
    )
    
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    
    return db_event


@router.get("/events/pricing-impact")
def get_pricing_impact(
    location: str,
    check_in: datetime,
    check_out: datetime,
    db: Session = Depends(get_db),
):
    """
    Get pricing impact from events during a stay.
    Used by ML pricing engine for dynamic adjustments.
    """
    events = db.query(models.Event).filter(
        models.Event.location.ilike(f"%{location}%"),
        models.Event.start_date <= check_out,
        models.Event.end_date >= check_in if models.Event.end_date else models.Event.start_date >= check_in,
    ).all()
    
    if not events:
        return {"impact_percent": 0, "events": [], "reason": "No events during stay"}
    
    # Calculate cumulative impact
    total_impact = sum(e.price_impact_percent for e in events)
    max_impact = 50.0  # Cap at 50% increase
    
    return {
        "impact_percent": min(total_impact, max_impact),
        "events": [
            {
                "name": e.name,
                "type": e.event_type,
                "impact": e.price_impact_percent,
                "date": e.start_date.isoformat(),
            }
            for e in events
        ],
        "reason": f"{len(events)} event(s) during your stay",
    }
