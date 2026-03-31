"""
SBT Router - Soul-Bound Tokens (Achievement Badges).
"""
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend import models
from backend.database import get_db
from backend.middleware.auth import get_current_user

router = APIRouter(prefix="/sbts", tags=["sbts"])


class SBTOut(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    category: str
    awarded_at: datetime

    class Config:
        from_attributes = True


class SBTCreate(BaseModel):
    user_id: str
    name: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    category: str = "achievement"


# Default SBT definitions
DEFAULT_SBTS = [
    {"name": "First Booking", "description": "Completed your first booking", "category": "milestone"},
    {"name": "Explorer", "description": "Visited 5 different hubs", "category": "achievement"},
    {"name": "Community Builder", "description": "Helped 10 other members", "category": "achievement"},
    {"name": "Nomad Elite", "description": "100+ nights booked", "category": "milestone"},
    {"name": "Early Adopter", "description": "Joined during beta", "category": "special"},
]


@router.get("/", response_model=List[SBTOut])
def list_user_sbts(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """List current user's SBTs/badges."""
    sbts = db.query(models.SoulBoundToken).filter(
        models.SoulBoundToken.user_id == current_user.id
    ).order_by(models.SoulBoundToken.awarded_at.desc()).all()
    return [SBTOut.model_validate(s) for s in sbts]


@router.get("/available")
def list_available_sbts():
    """List all available SBT types."""
    return DEFAULT_SBTS


@router.post("/award", response_model=SBTOut, status_code=201)
def award_sbt(
    data: SBTCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Award an SBT to a user (admin only)."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    # Check if already awarded
    existing = db.query(models.SoulBoundToken).filter(
        models.SoulBoundToken.user_id == data.user_id,
        models.SoulBoundToken.name == data.name
    ).first()

    if existing:
        return SBTOut.model_validate(existing)

    sbt = models.SoulBoundToken(
        id=str(uuid.uuid4()),
        user_id=data.user_id,
        name=data.name,
        description=data.description,
        image_url=data.image_url,
        category=data.category,
    )
    db.add(sbt)
    db.commit()
    db.refresh(sbt)

    return SBTOut.model_validate(sbt)
