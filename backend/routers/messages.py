"""
Messages Router - Real-time messaging between users.
"""
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend import models
from backend.database import get_db
from backend.middleware.auth import get_current_user

router = APIRouter(prefix="/messages", tags=["messages"])


# --- Schemas ---

class MessageCreate(BaseModel):
    content: str


class MessageOut(BaseModel):
    id: str
    thread_id: str
    sender_id: str
    content: str
    read_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ThreadCreate(BaseModel):
    participant_id: str  # The other user to chat with
    listing_id: Optional[str] = None
    initial_message: Optional[str] = None


class ThreadOut(BaseModel):
    id: str
    participant_ids: List[str]
    listing_id: Optional[str] = None
    last_message_at: Optional[datetime] = None
    created_at: datetime
    unread_count: int = 0
    last_message_preview: Optional[str] = None

    class Config:
        from_attributes = True


# --- Endpoints ---

@router.get("/threads", response_model=List[ThreadOut])
def list_threads(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """List all chat threads for the current user."""
    threads = (
        db.query(models.ChatThread)
        .filter(models.ChatThread.participant_ids.contains([current_user.id]))
        .order_by(models.ChatThread.last_message_at.desc().nullslast())
        .all()
    )

    result = []
    for thread in threads:
        # Count unread messages
        unread = (
            db.query(models.ChatMessage)
            .filter(
                models.ChatMessage.thread_id == thread.id,
                models.ChatMessage.sender_id != current_user.id,
                models.ChatMessage.read_at.is_(None),
            )
            .count()
        )

        # Get last message preview
        last_msg = (
            db.query(models.ChatMessage)
            .filter(models.ChatMessage.thread_id == thread.id)
            .order_by(models.ChatMessage.created_at.desc())
            .first()
        )

        result.append(
            ThreadOut(
                id=thread.id,
                participant_ids=thread.participant_ids,
                listing_id=thread.listing_id,
                last_message_at=thread.last_message_at,
                created_at=thread.created_at,
                unread_count=unread,
                last_message_preview=last_msg.content[:50] if last_msg else None,
            )
        )

    return result


@router.post("/threads", response_model=ThreadOut, status_code=201)
def create_thread(
    data: ThreadCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Create a new chat thread with another user."""
    if data.participant_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot create thread with yourself")

    # Check if thread already exists between these users
    participant_ids = sorted([current_user.id, data.participant_id])
    existing = (
        db.query(models.ChatThread)
        .filter(models.ChatThread.participant_ids == participant_ids)
        .first()
    )

    if existing:
        # Return existing thread
        return ThreadOut(
            id=existing.id,
            participant_ids=existing.participant_ids,
            listing_id=existing.listing_id,
            last_message_at=existing.last_message_at,
            created_at=existing.created_at,
            unread_count=0,
        )

    # Create new thread
    thread = models.ChatThread(
        id=str(uuid.uuid4()),
        participant_ids=participant_ids,
        listing_id=data.listing_id,
    )
    db.add(thread)

    # Add initial message if provided
    if data.initial_message:
        msg = models.ChatMessage(
            id=str(uuid.uuid4()),
            thread_id=thread.id,
            sender_id=current_user.id,
            content=data.initial_message,
        )
        db.add(msg)
        thread.last_message_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(thread)

    return ThreadOut(
        id=thread.id,
        participant_ids=thread.participant_ids,
        listing_id=thread.listing_id,
        last_message_at=thread.last_message_at,
        created_at=thread.created_at,
        unread_count=0,
    )


@router.get("/threads/{thread_id}", response_model=List[MessageOut])
def get_thread_messages(
    thread_id: str,
    limit: int = Query(50, le=100),
    before: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Get messages in a thread."""
    thread = db.query(models.ChatThread).filter(models.ChatThread.id == thread_id).first()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    if current_user.id not in thread.participant_ids:
        raise HTTPException(status_code=403, detail="Not a participant in this thread")

    query = db.query(models.ChatMessage).filter(models.ChatMessage.thread_id == thread_id)

    if before:
        query = query.filter(models.ChatMessage.created_at < before)

    messages = query.order_by(models.ChatMessage.created_at.desc()).limit(limit).all()

    return [MessageOut.model_validate(m) for m in reversed(messages)]


@router.post("/threads/{thread_id}", response_model=MessageOut, status_code=201)
def send_message(
    thread_id: str,
    data: MessageCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Send a message to a thread."""
    thread = db.query(models.ChatThread).filter(models.ChatThread.id == thread_id).first()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    if current_user.id not in thread.participant_ids:
        raise HTTPException(status_code=403, detail="Not a participant in this thread")

    message = models.ChatMessage(
        id=str(uuid.uuid4()),
        thread_id=thread_id,
        sender_id=current_user.id,
        content=data.content,
    )
    db.add(message)

    thread.last_message_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(message)

    # TODO: Emit WebSocket event for real-time update
    # from backend.socket_server import sio
    # sio.emit("new_message", {...}, room=thread_id)

    return MessageOut.model_validate(message)


@router.patch("/{message_id}/read", status_code=204)
def mark_message_read(
    message_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Mark a message as read."""
    message = db.query(models.ChatMessage).filter(models.ChatMessage.id == message_id).first()

    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    # Verify user is recipient (not sender)
    thread = db.query(models.ChatThread).filter(models.ChatThread.id == message.thread_id).first()
    if current_user.id not in thread.participant_ids:
        raise HTTPException(status_code=403, detail="Not authorized")

    if message.sender_id == current_user.id:
        return  # Can't mark your own message as read

    if not message.read_at:
        message.read_at = datetime.now(timezone.utc)
        db.commit()
