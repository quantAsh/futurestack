from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from backend import models, schemas
from backend.database import get_db

router = APIRouter()

@router.get("/", response_model=schemas.PaginatedResponse[schemas.Notification])
def get_notifications(
    user_id: str, page: int = 1, size: int = 20, db: Session = Depends(get_db)
):
    """Get notifications for a user with pagination."""
    query = (
        db.query(models.Notification)
        .filter(models.Notification.user_id == user_id)
        .order_by(models.Notification.created_at.desc())
    )
    
    offset = (page - 1) * size
    total = query.count()
    items = query.offset(offset).limit(size).all()
    pages = (total + size - 1) // size

    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": pages,
    }


@router.get("/unread-count")
def get_unread_count(user_id: str, db: Session = Depends(get_db)):
    """Get count of unread notifications."""
    count = (
        db.query(models.Notification)
        .filter(models.Notification.user_id == user_id)
        .filter(models.Notification.read == False)
        .count()
    )
    return {"count": count}


@router.post("/{notification_id}/mark-read")
def mark_notification_read(notification_id: str, db: Session = Depends(get_db)):
    """Mark a notification as read."""
    notification = (
        db.query(models.Notification)
        .filter(models.Notification.id == notification_id)
        .first()
    )
    if not notification:
        from backend.errors import ResourceNotFoundError
        raise ResourceNotFoundError(resource="Notification", identifier=notification_id)
        
    notification.read = True
    db.commit()
    return {"status": "marked_read"}


@router.post("/mark-all-read")
def mark_all_read(user_id: str, db: Session = Depends(get_db)):
    """Mark all notifications as read for a user."""
    db.query(models.Notification).filter(models.Notification.user_id == user_id).update(
        {"read": True}
    )
    db.commit()
    return {"status": "all_marked_read"}

# --- PHASE 14: Push Notification Registration ---

from pydantic import BaseModel
from uuid import uuid4
from backend.services import push_service


class PushSubscriptionRequest(BaseModel):
    endpoint: str
    p256dh_key: str
    auth_key: str
    user_agent: str | None = None


@router.post("/push/register")
def register_push_subscription(
    user_id: str,
    request: PushSubscriptionRequest,
    db: Session = Depends(get_db),
):
    """Register a device for push notifications."""
    # Check if endpoint already exists
    existing = (
        db.query(models.PushSubscription)
        .filter(models.PushSubscription.endpoint == request.endpoint)
        .first()
    )

    if existing:
        # Update user association if different
        if existing.user_id != user_id:
            existing.user_id = user_id
            db.commit()
        return {"status": "already_registered", "id": existing.id}

    # Create new subscription
    sub = models.PushSubscription(
        id=str(uuid4()),
        user_id=user_id,
        endpoint=request.endpoint,
        p256dh_key=request.p256dh_key,
        auth_key=request.auth_key,
        user_agent=request.user_agent,
    )
    db.add(sub)
    db.commit()

    return {"status": "registered", "id": sub.id}


@router.delete("/push/unregister")
def unregister_push_subscription(
    endpoint: str,
    db: Session = Depends(get_db),
):
    """Remove a push subscription."""
    result = (
        db.query(models.PushSubscription)
        .filter(models.PushSubscription.endpoint == endpoint)
        .delete()
    )
    db.commit()

    return {"status": "unregistered", "deleted": result}


@router.post("/push/test")
def send_test_notification(
    user_id: str,
    db: Session = Depends(get_db),
):
    """Send a test push notification (debug endpoint)."""
    try:
        result = push_service.send_notification_to_user(
            db=db,
            user_id=user_id,
            title="Test Notification",
            body="This is a test notification from NomadNest!",
            icon="/icons/logo.png",
            url="/dashboard",
        )
        return result
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(e))
