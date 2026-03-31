"""
"Do It For Me" Autonomous Booking API Router.

End-to-end automated booking with progress tracking.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

from backend.database import get_db
from backend.routers.auth import get_current_user
from backend import models
from backend.services.autonomous_booking import autonomous_booking_service

router = APIRouter(prefix="/api/do-it-for-me", tags=["autonomous"])


# ============================================================================
# Schemas
# ============================================================================

class BookingRequestCreate(BaseModel):
    request_type: str = Field(..., pattern="^(accommodation|flight|full_trip)$")
    destination: str = Field(..., max_length=100)
    check_in: str = Field(..., description="YYYY-MM-DD format")
    check_out: str = Field(..., description="YYYY-MM-DD format")
    max_budget_usd: float = Field(..., ge=50)
    authorize_payment: bool = Field(default=False, description="Pre-authorize payment up to max budget")
    requirements: Optional[List[str]] = None  # ["wifi", "kitchen", "quiet"]
    flexibility_days: int = Field(default=0, ge=0, le=7)
    notes: Optional[str] = Field(None, max_length=500)


class ApproveBooking(BaseModel):
    option_id: Optional[str] = None  # If choosing different from recommended


# ============================================================================
# Request Endpoints
# ============================================================================

@router.post("/requests")
async def create_booking_request(
    data: BookingRequestCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Create a new autonomous booking request."""
    preferences = {
        "destination": data.destination,
        "check_in": data.check_in,
        "check_out": data.check_out,
        "requirements": data.requirements or [],
        "flexibility_days": data.flexibility_days,
        "notes": data.notes,
        "payment_authorized": data.authorize_payment,
    }
    
    request = autonomous_booking_service.create_request(
        db=db,
        user_id=current_user.id,
        request_type=data.request_type,
        preferences=preferences,
        max_budget_usd=data.max_budget_usd,
        authorized_payment_usd=data.max_budget_usd if data.authorize_payment else None,
    )
    
    # Start the booking process in background
    background_tasks.add_task(
        autonomous_booking_service.simulate_booking_process,
        db,
        request.id,
    )
    
    return {
        "request_id": request.id,
        "status": "pending",
        "message": "🤖 I'm on it! Starting your search now...",
    }


@router.get("/requests")
async def list_requests(
    status: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """List your autonomous booking requests."""
    requests = autonomous_booking_service.list_user_requests(db, current_user.id, status)
    
    return {
        "requests": [
            {
                "id": r.id,
                "request_type": r.request_type,
                "destination": r.preferences.get("destination"),
                "dates": f"{r.preferences.get('check_in')} → {r.preferences.get('check_out')}",
                "max_budget_usd": r.max_budget_usd,
                "status": r.status,
                "current_step": r.current_step,
                "progress_percent": r.progress_percent,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in requests
        ],
        "total": len(requests),
    }


@router.get("/requests/{request_id}")
async def get_request(
    request_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Get full request details with all steps."""
    result = autonomous_booking_service.get_request_with_steps(db, request_id, current_user.id)
    if not result:
        raise HTTPException(status_code=404, detail="Request not found")
    return result


@router.post("/requests/{request_id}/approve")
async def approve_booking(
    request_id: str,
    data: ApproveBooking = ApproveBooking(),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Approve and proceed with booking."""
    result = autonomous_booking_service.approve_and_book(
        db=db,
        request_id=request_id,
        user_id=current_user.id,
        option_id=data.option_id,
    )
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.post("/requests/{request_id}/cancel")
async def cancel_request(
    request_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Cancel a booking request."""
    success = autonomous_booking_service.cancel_request(db, request_id, current_user.id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot cancel this request")
    return {"message": "Request cancelled"}


# ============================================================================
# Status Polling (for real-time updates simulation)
# ============================================================================

@router.get("/requests/{request_id}/status")
async def poll_status(
    request_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Poll for current status (lightweight endpoint for frequent calls)."""
    request = autonomous_booking_service.get_request(db, request_id, current_user.id)
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    return {
        "status": request.status,
        "current_step": request.current_step,
        "progress_percent": request.progress_percent,
        "options_count": len(request.found_options) if request.found_options else 0,
        "has_confirmation": request.booking_confirmation is not None,
    }
