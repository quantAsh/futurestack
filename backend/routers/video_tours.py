"""
Host Video Tours API Router.

Video tours for listings with live scheduling.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

from backend.database import get_db
from backend.routers.auth import get_current_user
from backend import models
from backend.services.video_tours import video_tour_service

router = APIRouter(prefix="/api/video-tours", tags=["video-tours"])


# ============================================================================
# Schemas
# ============================================================================

class RecordedTourCreate(BaseModel):
    listing_id: str
    title: str = Field(..., max_length=200)
    video_url: str
    thumbnail_url: Optional[str] = None
    duration_seconds: Optional[int] = None
    description: Optional[str] = Field(None, max_length=1000)


class LiveTourSchedule(BaseModel):
    listing_id: str
    title: str = Field(..., max_length=200)
    scheduled_at: str  # ISO format datetime
    meeting_url: str
    max_attendees: int = Field(default=10, ge=1, le=100)
    description: Optional[str] = Field(None, max_length=1000)


# ============================================================================
# Tour Endpoints
# ============================================================================

@router.get("/upcoming")
async def get_upcoming_tours(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Get upcoming live tours across all listings."""
    tours = video_tour_service.get_upcoming_live_tours(db, limit)
    return {"tours": tours, "total": len(tours)}


@router.get("/listing/{listing_id}")
async def get_tours_for_listing(
    listing_id: str,
    db: Session = Depends(get_db),
):
    """Get all tours for a specific listing."""
    tours = video_tour_service.list_tours_for_listing(db, listing_id)
    return {"tours": tours, "total": len(tours)}


@router.get("/{tour_id}")
async def get_tour(
    tour_id: str,
    db: Session = Depends(get_db),
):
    """Get tour details."""
    tour = video_tour_service.get_tour(db, tour_id)
    if not tour:
        raise HTTPException(status_code=404, detail="Tour not found")
    return tour


@router.post("/{tour_id}/view")
async def record_view(
    tour_id: str,
    db: Session = Depends(get_db),
):
    """Record a view for the tour."""
    video_tour_service.record_view(db, tour_id)
    return {"recorded": True}


# ============================================================================
# Host Endpoints (create tours)
# ============================================================================

@router.post("/recorded")
def create_recorded_tour(
    data: RecordedTourCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Upload a recorded video tour."""
    # Verify user owns the listing
    listing = db.query(models.Listing).filter(
        models.Listing.id == data.listing_id
    ).first()
    
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    if listing.host_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your listing")
    
    tour = video_tour_service.create_recorded_tour(
        db=db,
        host_id=current_user.id,
        listing_id=data.listing_id,
        title=data.title,
        video_url=data.video_url,
        thumbnail_url=data.thumbnail_url,
        duration_seconds=data.duration_seconds,
        description=data.description,
    )
    
    return {
        "tour_id": tour.id,
        "message": "📹 Video tour uploaded successfully!",
    }


@router.post("/live")
def schedule_live_tour(
    data: LiveTourSchedule,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Schedule a live video tour."""
    # Verify user owns the listing
    listing = db.query(models.Listing).filter(
        models.Listing.id == data.listing_id
    ).first()
    
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    if listing.host_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your listing")
    
    scheduled_at = datetime.fromisoformat(data.scheduled_at.replace('Z', '+00:00'))
    
    tour = video_tour_service.schedule_live_tour(
        db=db,
        host_id=current_user.id,
        listing_id=data.listing_id,
        title=data.title,
        scheduled_at=scheduled_at,
        meeting_url=data.meeting_url,
        max_attendees=data.max_attendees,
        description=data.description,
    )
    
    return {
        "tour_id": tour.id,
        "message": "🎥 Live tour scheduled!",
        "scheduled_at": scheduled_at.isoformat(),
    }


# ============================================================================
# Registration Endpoints
# ============================================================================

@router.post("/{tour_id}/register")
async def register_for_tour(
    tour_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Register for a live tour."""
    try:
        result = video_tour_service.register_for_tour(db, tour_id, current_user.id)
        return {
            "success": True,
            "message": "🎫 You're registered for this tour!",
            **result,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{tour_id}/register")
async def cancel_registration(
    tour_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Cancel tour registration."""
    success = video_tour_service.cancel_registration(db, tour_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Registration not found")
    return {"message": "Registration cancelled"}


@router.get("/my/registrations")
async def get_my_registrations(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Get all your tour registrations."""
    registrations = video_tour_service.get_user_registrations(db, current_user.id)
    return {"registrations": registrations, "total": len(registrations)}
