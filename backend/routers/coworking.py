"""
Virtual Co-Working API Router.

Video rooms with synchronized Pomodoro timers for focused work sessions.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

from backend.database import get_db
from backend.routers.auth import get_current_user
from backend import models
from backend.services.coworking import coworking_service, ROOM_THEMES

router = APIRouter(prefix="/api/coworking", tags=["coworking"])


# ============================================================================
# Schemas
# ============================================================================

class RoomCreate(BaseModel):
    name: str = Field(..., max_length=100, example="Morning Focus Session")
    description: Optional[str] = Field(None, max_length=500)
    theme: str = Field(default="focus", pattern="^(focus|creative|social|quiet|accountability)$")
    max_participants: int = Field(default=10, ge=2, le=50)
    is_public: bool = True
    work_minutes: int = Field(default=25, ge=5, le=90)
    break_minutes: int = Field(default=5, ge=1, le=30)
    ambient_sound: Optional[str] = None


class JoinRoom(BaseModel):
    current_task: Optional[str] = Field(None, max_length=200)


class UpdateStatus(BaseModel):
    status: Optional[str] = Field(None, pattern="^(active|away|do_not_disturb)$")
    current_task: Optional[str] = Field(None, max_length=200)
    mic_enabled: Optional[bool] = None
    camera_enabled: Optional[bool] = None


# ============================================================================
# Room Endpoints
# ============================================================================

@router.get("/rooms")
async def list_rooms(
    theme: Optional[str] = Query(None, description="Filter by theme"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """List all active co-working rooms."""
    rooms = coworking_service.list_active_rooms(db, theme=theme)
    
    return {
        "rooms": rooms,
        "total": len(rooms),
        "themes": [
            {"key": k, **v}
            for k, v in ROOM_THEMES.items()
        ]
    }


@router.post("/rooms")
async def create_room(
    data: RoomCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Create a new co-working room."""
    room = coworking_service.create_room(
        db=db,
        host_id=current_user.id,
        name=data.name,
        description=data.description,
        theme=data.theme,
        max_participants=data.max_participants,
        is_public=data.is_public,
        work_minutes=data.work_minutes,
        break_minutes=data.break_minutes,
        ambient_sound=data.ambient_sound,
    )
    
    return {
        "id": room.id,
        "name": room.name,
        "video_url": room.video_room_url,
        "message": "Room created! Share the link to invite others.",
    }


@router.get("/rooms/{room_id}")
async def get_room(
    room_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Get room details with participants."""
    room = coworking_service.get_room(db, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    participants = coworking_service.get_room_participants(db, room_id)
    theme_info = ROOM_THEMES.get(room.theme, ROOM_THEMES["focus"])
    
    return {
        "id": room.id,
        "name": room.name,
        "description": room.description,
        "theme": room.theme,
        "theme_emoji": theme_info["emoji"],
        "theme_color": theme_info["color"],
        "host_id": room.host_id,
        "is_host": room.host_id == current_user.id,
        "video_url": room.video_room_url,
        "participants": participants,
        "max_participants": room.max_participants,
        "pomodoro": {
            "enabled": room.pomodoro_enabled,
            "work_minutes": room.work_minutes,
            "break_minutes": room.break_minutes,
            "long_break_minutes": room.long_break_minutes,
            "state": room.current_pomodoro_state,
            "cycle": room.current_pomodoro_cycle,
            "session_start": room.current_session_start.isoformat() if room.current_session_start else None,
        },
        "ambient_sound": room.ambient_sound,
    }


@router.delete("/rooms/{room_id}")
async def close_room(
    room_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Close a room (host only)."""
    success = coworking_service.close_room(db, room_id, current_user.id)
    if not success:
        raise HTTPException(status_code=403, detail="Only the host can close this room")
    return {"message": "Room closed"}


# ============================================================================
# Session Endpoints
# ============================================================================

@router.post("/rooms/{room_id}/join")
async def join_room(
    room_id: str,
    data: JoinRoom = JoinRoom(),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Join a co-working room."""
    try:
        result = coworking_service.join_room(
            db=db,
            room_id=room_id,
            user_id=current_user.id,
            current_task=data.current_task,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/rooms/{room_id}/leave")
async def leave_room(
    room_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Leave a co-working room."""
    success = coworking_service.leave_room(db, room_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Not in this room")
    return {"message": "Left room"}


@router.patch("/rooms/{room_id}/status")
async def update_status(
    room_id: str,
    data: UpdateStatus,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Update your status in a room."""
    success = coworking_service.update_user_status(
        db=db,
        room_id=room_id,
        user_id=current_user.id,
        status=data.status,
        current_task=data.current_task,
        mic_enabled=data.mic_enabled,
        camera_enabled=data.camera_enabled,
    )
    if not success:
        raise HTTPException(status_code=404, detail="Not in this room")
    return {"message": "Status updated"}


# ============================================================================
# Pomodoro Endpoints
# ============================================================================

@router.post("/rooms/{room_id}/pomodoro/{action}")
async def control_pomodoro(
    room_id: str,
    action: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Control room's Pomodoro timer (host only)."""
    if action not in ["start_work", "start_break", "start_long_break", "reset"]:
        raise HTTPException(status_code=400, detail="Invalid action")
    
    state_map = {
        "start_work": "work",
        "start_break": "break",
        "start_long_break": "long_break",
        "reset": "idle",
    }
    
    success = coworking_service.update_pomodoro_state(
        db=db,
        room_id=room_id,
        host_id=current_user.id,
        state=state_map[action],
    )
    
    if not success:
        raise HTTPException(status_code=403, detail="Only the host can control the timer")
    
    return {"message": f"Pomodoro: {action}", "state": state_map[action]}


# ============================================================================
# Stats Endpoints
# ============================================================================

@router.get("/stats")
async def get_my_stats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Get your co-working statistics."""
    stats = coworking_service.get_user_stats(db, current_user.id)
    return stats


@router.get("/leaderboard")
def get_leaderboard(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Get weekly focus leaderboard."""
    from datetime import timedelta
    from sqlalchemy import func
    
    week_start = datetime.utcnow() - timedelta(days=7)
    
    # Aggregate by user
    results = db.query(
        models.CoWorkingSession.user_id,
        func.sum(models.CoWorkingSession.pomodoros_completed).label("pomodoros"),
        func.sum(models.CoWorkingSession.total_focus_minutes).label("minutes"),
    ).filter(
        models.CoWorkingSession.joined_at >= week_start,
    ).group_by(
        models.CoWorkingSession.user_id
    ).order_by(
        func.sum(models.CoWorkingSession.pomodoros_completed).desc()
    ).limit(10).all()
    
    leaderboard = []
    for i, row in enumerate(results):
        user = db.query(models.User).filter(
            models.User.id == row.user_id
        ).first()
        
        leaderboard.append({
            "rank": i + 1,
            "user_id": row.user_id,
            "name": user.name if user else "Anonymous",
            "pomodoros": row.pomodoros or 0,
            "focus_hours": round((row.minutes or 0) / 60, 1),
            "is_me": row.user_id == current_user.id,
        })
    
    return {
        "leaderboard": leaderboard,
        "period": "This week",
    }
