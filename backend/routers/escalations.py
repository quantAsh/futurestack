"""
Escalation Request Router.
Provides admin endpoints for managing human-in-the-loop escalations.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import uuid4

from backend.database import get_db
from backend import models
from backend.routers.auth import get_current_user

router = APIRouter(prefix="/escalations", tags=["escalations"])


# --- Schemas ---

class EscalationCreate(BaseModel):
    user_id: str
    session_id: str
    query: str
    reason: str
    priority: str = "medium"
    ai_context: Optional[dict] = None


class EscalationResponse(BaseModel):
    id: str
    user_id: str
    session_id: str
    query: str
    reason: str
    priority: str
    status: str
    assigned_to: Optional[str] = None
    resolution_notes: Optional[str] = None
    created_at: datetime
    assigned_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    user_name: Optional[str] = None
    assignee_name: Optional[str] = None

    class Config:
        from_attributes = True


class EscalationAssign(BaseModel):
    admin_id: str


class EscalationResolve(BaseModel):
    resolution_notes: str


class EscalationStats(BaseModel):
    total: int
    pending: int
    assigned: int
    resolved: int
    avg_resolution_hours: Optional[float] = None


# --- Helper Functions ---

async def create_escalation_request(
    db: Session,
    user_id: str,
    session_id: str,
    query: str,
    reason: str,
    priority: str = "medium",
    ai_context: dict = None
) -> models.EscalationRequest:
    """Create a new escalation request (called from AI concierge)."""
    escalation = models.EscalationRequest(
        id=str(uuid4()),
        user_id=user_id,
        session_id=session_id,
        query=query,
        reason=reason,
        priority=priority,
        ai_context=ai_context,
        status="pending"
    )
    db.add(escalation)
    db.commit()
    db.refresh(escalation)
    return escalation


# --- Admin Endpoints ---

@router.get("/", response_model=List[EscalationResponse])
def list_escalations(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """List escalation requests (admin only)."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    query = db.query(models.EscalationRequest)
    
    if status:
        query = query.filter(models.EscalationRequest.status == status)
    if priority:
        query = query.filter(models.EscalationRequest.priority == priority)
    
    query = query.order_by(
        # Priority order: high > medium > low
        func.case(
            (models.EscalationRequest.priority == "high", 1),
            (models.EscalationRequest.priority == "medium", 2),
            else_=3
        ),
        models.EscalationRequest.created_at.desc()
    )
    
    escalations = query.offset(offset).limit(limit).all()
    
    # Enrich with user names
    result = []
    for esc in escalations:
        response = EscalationResponse.model_validate(esc)
        if esc.user:
            response.user_name = esc.user.name
        if esc.assignee:
            response.assignee_name = esc.assignee.name
        result.append(response)
    
    return result


@router.get("/stats", response_model=EscalationStats)
def get_escalation_stats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get escalation statistics (admin only)."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    total = db.query(models.EscalationRequest).count()
    pending = db.query(models.EscalationRequest).filter(
        models.EscalationRequest.status == "pending"
    ).count()
    assigned = db.query(models.EscalationRequest).filter(
        models.EscalationRequest.status == "assigned"
    ).count()
    resolved = db.query(models.EscalationRequest).filter(
        models.EscalationRequest.status == "resolved"
    ).count()
    
    # Calculate average resolution time for resolved escalations
    avg_resolution = None
    resolved_with_times = db.query(models.EscalationRequest).filter(
        models.EscalationRequest.status == "resolved",
        models.EscalationRequest.resolved_at.isnot(None)
    ).all()
    
    if resolved_with_times:
        total_hours = 0
        for esc in resolved_with_times:
            if esc.resolved_at and esc.created_at:
                delta = esc.resolved_at - esc.created_at
                total_hours += delta.total_seconds() / 3600
        avg_resolution = round(total_hours / len(resolved_with_times), 1)
    
    return EscalationStats(
        total=total,
        pending=pending,
        assigned=assigned,
        resolved=resolved,
        avg_resolution_hours=avg_resolution
    )


@router.get("/{escalation_id}", response_model=EscalationResponse)
def get_escalation(
    escalation_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get a specific escalation (admin only)."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    escalation = db.query(models.EscalationRequest).filter(
        models.EscalationRequest.id == escalation_id
    ).first()
    
    if not escalation:
        raise HTTPException(status_code=404, detail="Escalation not found")
    
    response = EscalationResponse.model_validate(escalation)
    if escalation.user:
        response.user_name = escalation.user.name
    if escalation.assignee:
        response.assignee_name = escalation.assignee.name
    
    return response


@router.post("/{escalation_id}/assign")
def assign_escalation(
    escalation_id: str,
    payload: EscalationAssign,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Assign an escalation to an admin (admin only)."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    escalation = db.query(models.EscalationRequest).filter(
        models.EscalationRequest.id == escalation_id
    ).first()
    
    if not escalation:
        raise HTTPException(status_code=404, detail="Escalation not found")
    
    # Verify assignee exists and is admin
    assignee = db.query(models.User).filter(
        models.User.id == payload.admin_id
    ).first()
    
    if not assignee or not assignee.is_admin:
        raise HTTPException(status_code=400, detail="Invalid admin user")
    
    escalation.assigned_to = payload.admin_id
    escalation.assigned_at = datetime.utcnow()
    escalation.status = "assigned"
    db.commit()
    
    return {"status": "assigned", "assigned_to": assignee.name}


@router.post("/{escalation_id}/resolve")
def resolve_escalation(
    escalation_id: str,
    payload: EscalationResolve,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Mark an escalation as resolved (admin only)."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    escalation = db.query(models.EscalationRequest).filter(
        models.EscalationRequest.id == escalation_id
    ).first()
    
    if not escalation:
        raise HTTPException(status_code=404, detail="Escalation not found")
    
    escalation.status = "resolved"
    escalation.resolved_at = datetime.utcnow()
    escalation.resolution_notes = payload.resolution_notes
    
    # If not already assigned, assign to current user
    if not escalation.assigned_to:
        escalation.assigned_to = current_user.id
        escalation.assigned_at = datetime.utcnow()
    
    db.commit()
    
    return {"status": "resolved", "escalation_id": escalation_id}
