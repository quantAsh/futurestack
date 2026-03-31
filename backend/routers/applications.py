"""
Applications Router - Host application workflow.
"""
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend import models
from backend.database import get_db
from backend.middleware.auth import get_current_user

router = APIRouter(prefix="/applications", tags=["applications"])


# --- Schemas ---

class ApplicationCreate(BaseModel):
    hub_id: Optional[str] = None
    answers: dict  # e.g., {"why_host": "...", "experience": "..."}


class ApplicationUpdate(BaseModel):
    status: str  # "approved" or "rejected"
    rejection_reason: Optional[str] = None


class ApplicationOut(BaseModel):
    id: str
    user_id: str
    hub_id: Optional[str] = None
    status: str
    answers: Optional[dict] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    created_at: datetime

    # Populated fields
    applicant_name: Optional[str] = None
    applicant_email: Optional[str] = None
    hub_name: Optional[str] = None

    class Config:
        from_attributes = True


# --- Endpoints ---

@router.post("/", response_model=ApplicationOut, status_code=201)
def submit_application(
    data: ApplicationCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Submit a new host application."""
    # Check for existing pending application
    existing = (
        db.query(models.HostApplication)
        .filter(
            models.HostApplication.user_id == current_user.id,
            models.HostApplication.status == "pending",
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=400,
            detail="You already have a pending application",
        )

    application = models.HostApplication(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        hub_id=data.hub_id,
        answers=data.answers,
        status="pending",
    )
    db.add(application)
    db.commit()
    db.refresh(application)

    return ApplicationOut(
        id=application.id,
        user_id=application.user_id,
        hub_id=application.hub_id,
        status=application.status,
        answers=application.answers,
        created_at=application.created_at,
        applicant_name=current_user.name,
        applicant_email=current_user.email,
    )


@router.get("/", response_model=List[ApplicationOut])
def list_applications(
    status: Optional[str] = Query(None, description="Filter by status"),
    hub_id: Optional[str] = Query(None, description="Filter by hub"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    List applications.
    - Admins see all applications
    - Hub managers see applications for their hub
    - Regular users see only their own
    """
    query = db.query(models.HostApplication)

    # Access control
    if current_user.is_admin:
        pass  # See all
    elif getattr(current_user, 'is_hub_manager', False):
        # Filter to hubs they manage (simplified: assume hub_id matches)
        query = query.filter(
            (models.HostApplication.hub_id == hub_id) | (models.HostApplication.user_id == current_user.id)
        )
    else:
        # Regular users see only their own
        query = query.filter(models.HostApplication.user_id == current_user.id)

    if status:
        query = query.filter(models.HostApplication.status == status)

    if hub_id:
        query = query.filter(models.HostApplication.hub_id == hub_id)

    applications = query.order_by(models.HostApplication.created_at.desc()).all()

    result = []
    for app in applications:
        applicant = db.query(models.User).filter(models.User.id == app.user_id).first()
        hub = db.query(models.Hub).filter(models.Hub.id == app.hub_id).first() if app.hub_id else None

        result.append(
            ApplicationOut(
                id=app.id,
                user_id=app.user_id,
                hub_id=app.hub_id,
                status=app.status,
                answers=app.answers,
                reviewed_by=app.reviewed_by,
                reviewed_at=app.reviewed_at,
                rejection_reason=app.rejection_reason,
                created_at=app.created_at,
                applicant_name=applicant.name if applicant else None,
                applicant_email=applicant.email if applicant else None,
                hub_name=hub.name if hub else None,
            )
        )

    return result


@router.get("/{application_id}", response_model=ApplicationOut)
def get_application(
    application_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Get a specific application."""
    application = (
        db.query(models.HostApplication)
        .filter(models.HostApplication.id == application_id)
        .first()
    )

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    # Access control
    if not current_user.is_admin and application.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this application")

    applicant = db.query(models.User).filter(models.User.id == application.user_id).first()
    hub = db.query(models.Hub).filter(models.Hub.id == application.hub_id).first() if application.hub_id else None

    return ApplicationOut(
        id=application.id,
        user_id=application.user_id,
        hub_id=application.hub_id,
        status=application.status,
        answers=application.answers,
        reviewed_by=application.reviewed_by,
        reviewed_at=application.reviewed_at,
        rejection_reason=application.rejection_reason,
        created_at=application.created_at,
        applicant_name=applicant.name if applicant else None,
        applicant_email=applicant.email if applicant else None,
        hub_name=hub.name if hub else None,
    )


@router.patch("/{application_id}", response_model=ApplicationOut)
def review_application(
    application_id: str,
    data: ApplicationUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Approve or reject an application (admin/hub manager only)."""
    if not current_user.is_admin and not getattr(current_user, 'is_hub_manager', False):
        raise HTTPException(status_code=403, detail="Only admins can review applications")

    application = (
        db.query(models.HostApplication)
        .filter(models.HostApplication.id == application_id)
        .first()
    )

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    if application.status != "pending":
        raise HTTPException(status_code=400, detail="Application already reviewed")

    if data.status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="Status must be 'approved' or 'rejected'")

    application.status = data.status
    application.reviewed_by = current_user.id
    application.reviewed_at = datetime.now(timezone.utc)

    if data.status == "rejected" and data.rejection_reason:
        application.rejection_reason = data.rejection_reason

    # If approved, update user role
    if data.status == "approved":
        applicant = db.query(models.User).filter(models.User.id == application.user_id).first()
        if applicant:
            applicant.is_host = True

    db.commit()
    db.refresh(application)

    applicant = db.query(models.User).filter(models.User.id == application.user_id).first()
    hub = db.query(models.Hub).filter(models.Hub.id == application.hub_id).first() if application.hub_id else None

    return ApplicationOut(
        id=application.id,
        user_id=application.user_id,
        hub_id=application.hub_id,
        status=application.status,
        answers=application.answers,
        reviewed_by=application.reviewed_by,
        reviewed_at=application.reviewed_at,
        rejection_reason=application.rejection_reason,
        created_at=application.created_at,
        applicant_name=applicant.name if applicant else None,
        applicant_email=applicant.email if applicant else None,
        hub_name=hub.name if hub else None,
    )
