"""
Notification Preferences API - User notification settings management.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.utils import get_current_user
from backend import models
from backend.services import notification_preferences as prefs_service


router = APIRouter()


# ============================================================================
# SCHEMAS
# ============================================================================

class NotificationPreferencesResponse(BaseModel):
    """Response schema for notification preferences."""
    email_marketing: bool
    email_transactional: bool
    email_digest: bool
    push_bookings: bool
    push_messages: bool
    push_community: bool
    push_ai_insights: bool
    digest_frequency: str = Field(example="weekly")
    digest_day: int = Field(example=1, description="0=Sunday, 1=Monday, etc.")
    quiet_hours_enabled: bool
    quiet_hours_start: int = Field(example=22, description="Hour in local time")
    quiet_hours_end: int = Field(example=8, description="Hour in local time")
    timezone: str = Field(example="America/New_York")

    class Config:
        from_attributes = True


class NotificationPreferencesUpdate(BaseModel):
    """Request schema for updating notification preferences."""
    email_marketing: Optional[bool] = None
    email_transactional: Optional[bool] = None
    email_digest: Optional[bool] = None
    push_bookings: Optional[bool] = None
    push_messages: Optional[bool] = None
    push_community: Optional[bool] = None
    push_ai_insights: Optional[bool] = None
    digest_frequency: Optional[str] = Field(None, pattern="^(daily|weekly|never)$")
    quiet_hours_enabled: Optional[bool] = None
    quiet_hours_start: Optional[int] = Field(None, ge=0, le=23)
    quiet_hours_end: Optional[int] = Field(None, ge=0, le=23)
    timezone: Optional[str] = None


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get(
    "/",
    response_model=NotificationPreferencesResponse,
    summary="Get notification preferences",
    description="Returns the current user's notification preferences. Creates defaults if none exist.",
)
def get_preferences(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    prefs = prefs_service.get_preferences(current_user.id, db)
    return prefs


@router.patch(
    "/",
    response_model=NotificationPreferencesResponse,
    summary="Update notification preferences",
    description="Updates notification preferences. Only provided fields are updated.",
)
def update_preferences(
    updates: NotificationPreferencesUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    prefs = prefs_service.update_preferences(
        user_id=current_user.id,
        db=db,
        **updates.model_dump(exclude_unset=True),
    )
    return prefs


@router.post(
    "/unsubscribe-all-marketing",
    summary="Unsubscribe from all marketing",
    description="Quick action to disable all marketing notifications.",
)
def unsubscribe_marketing(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    prefs_service.update_preferences(
        user_id=current_user.id,
        db=db,
        email_marketing=False,
        push_ai_insights=False,
    )
    
    return {"message": "Successfully unsubscribed from marketing notifications"}


@router.post(
    "/enable-digest",
    summary="Enable digest mode",
    description="Switch to digest mode to receive a summary instead of immediate notifications.",
)
def enable_digest(
    frequency: str = "weekly",
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    if frequency not in ["daily", "weekly"]:
        raise HTTPException(status_code=400, detail="Frequency must be 'daily' or 'weekly'")
    
    prefs_service.update_preferences(
        user_id=current_user.id,
        db=db,
        email_digest=True,
        digest_frequency=frequency,
        # Reduce real-time notifications when digest is enabled
        push_community=False,
        push_ai_insights=False,
    )
    
    return {"message": f"Digest mode enabled ({frequency})"}
