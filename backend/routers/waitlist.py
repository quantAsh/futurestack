"""
Waitlist Router - Launch waitlists for new features/hubs.
"""
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend import models
from backend.database import get_db
from backend.middleware.auth import get_current_user

router = APIRouter(prefix="/waitlist", tags=["waitlist"])


class WaitlistJoin(BaseModel):
    email: str
    waitlist_type: str = "general"


class WaitlistOut(BaseModel):
    id: str
    email: str
    waitlist_type: str
    position: Optional[int] = None
    invited: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


@router.post("/join", response_model=WaitlistOut, status_code=201)
def join_waitlist(
    data: WaitlistJoin,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Join a waitlist."""
    # Check if already on waitlist
    existing = db.query(models.WaitlistEntry).filter(
        models.WaitlistEntry.email == data.email,
        models.WaitlistEntry.waitlist_type == data.waitlist_type
    ).first()

    if existing:
        return WaitlistOut.model_validate(existing)

    # Get position
    count = db.query(func.count(models.WaitlistEntry.id)).filter(
        models.WaitlistEntry.waitlist_type == data.waitlist_type
    ).scalar()

    entry = models.WaitlistEntry(
        id=str(uuid.uuid4()),
        email=data.email,
        user_id=current_user.id if current_user else None,
        waitlist_type=data.waitlist_type,
        position=count + 1,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    return WaitlistOut.model_validate(entry)


@router.get("/status")
def check_status(
    email: str,
    waitlist_type: str = "general",
    db: Session = Depends(get_db),
):
    """Check waitlist status by email."""
    entry = db.query(models.WaitlistEntry).filter(
        models.WaitlistEntry.email == email,
        models.WaitlistEntry.waitlist_type == waitlist_type
    ).first()

    if not entry:
        return {"on_waitlist": False}

    return {
        "on_waitlist": True,
        "position": entry.position,
        "invited": entry.invited,
    }


@router.get("/", response_model=List[WaitlistOut])
def list_waitlist(
    waitlist_type: str = Query(None),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """List waitlist entries (admin only)."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    query = db.query(models.WaitlistEntry)
    if waitlist_type:
        query = query.filter(models.WaitlistEntry.waitlist_type == waitlist_type)

    entries = query.order_by(models.WaitlistEntry.position).limit(limit).all()
    return [WaitlistOut.model_validate(e) for e in entries]
