from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime

from backend import database, models, schemas
from backend.utils import get_current_user
from backend.services.audit_logging import audit_logger

router = APIRouter()

def get_db():
    yield from database.get_db()

def get_current_admin(current_user: models.User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Admin privileges required"
        )
    return current_user

@router.get("/audit-logs", summary="Get audit logs")
def read_audit_logs(
    actor_id: Optional[str] = None,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin)
):
    """
    Retrieve audit logs with optional filtering.
    Only accessible by admins.
    """
    logs = audit_logger.query(
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        limit=limit,
        db=db
    )
    return logs
