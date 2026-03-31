"""
Virtual Co-Working Service - Video rooms with Pomodoro sync for focused work.
"""
import structlog
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from uuid import uuid4

from backend import models

logger = structlog.get_logger(__name__)


# Room themes with descriptions
ROOM_THEMES = {
    "focus": {"name": "Deep Focus", "emoji": "🎯", "color": "#667eea", "ambient": "lofi"},
    "creative": {"name": "Creative Flow", "emoji": "🎨", "color": "#f59e0b", "ambient": "cafe"},
    "social": {"name": "Social Cowork", "emoji": "💬", "color": "#10b981", "ambient": None},
    "quiet": {"name": "Silent Library", "emoji": "🤫", "color": "#64748b", "ambient": "nature"},
    "accountability": {"name": "Accountability", "emoji": "📋", "color": "#ef4444", "ambient": None},
}


class VirtualCoWorkingService:
    """
    Virtual co-working room management.
    
    Features:
    - Room creation and management
    - Pomodoro timer synchronization
    - Participant tracking
    - Focus statistics
    """
    
    def create_room(
        self,
        db: Session,
        host_id: str,
        name: str,
        description: Optional[str] = None,
        theme: str = "focus",
        max_participants: int = 10,
        is_public: bool = True,
        work_minutes: int = 25,
        break_minutes: int = 5,
        ambient_sound: Optional[str] = None,
    ) -> models.CoWorkingRoom:
        """Create a new co-working room."""
        room_id = str(uuid4())
        
        # Generate video room URL (mock - in production, integrate with Daily.co/Jitsi)
        video_room_url = f"https://nomadnest.daily.co/{room_id[:8]}"
        
        room = models.CoWorkingRoom(
            id=room_id,
            name=name,
            description=description,
            theme=theme,
            host_id=host_id,
            max_participants=max_participants,
            is_public=is_public,
            video_provider="daily",
            video_room_url=video_room_url,
            video_room_id=room_id[:8],
            pomodoro_enabled=True,
            work_minutes=work_minutes,
            break_minutes=break_minutes,
            ambient_sound=ambient_sound or ROOM_THEMES.get(theme, {}).get("ambient"),
        )
        db.add(room)
        db.commit()
        db.refresh(room)
        
        logger.info("cowork_room_created", room_id=room_id, host_id=host_id, name=name)
        return room
    
    def get_room(
        self,
        db: Session,
        room_id: str,
    ) -> Optional[models.CoWorkingRoom]:
        """Get a room by ID."""
        return db.query(models.CoWorkingRoom).filter(
            models.CoWorkingRoom.id == room_id
        ).first()
    
    def list_active_rooms(
        self,
        db: Session,
        theme: Optional[str] = None,
        include_private: bool = False,
    ) -> List[Dict[str, Any]]:
        """List all active co-working rooms."""
        query = db.query(models.CoWorkingRoom).filter(
            models.CoWorkingRoom.is_active == True
        )
        
        if not include_private:
            query = query.filter(models.CoWorkingRoom.is_public == True)
        
        if theme:
            query = query.filter(models.CoWorkingRoom.theme == theme)
        
        rooms = query.all()
        
        result = []
        for room in rooms:
            # Count active participants
            active_sessions = db.query(models.CoWorkingSession).filter(
                models.CoWorkingSession.room_id == room.id,
                models.CoWorkingSession.left_at == None,
            ).count()
            
            # Get host info
            host = db.query(models.User).filter(
                models.User.id == room.host_id
            ).first()
            
            theme_info = ROOM_THEMES.get(room.theme, ROOM_THEMES["focus"])
            
            result.append({
                "id": room.id,
                "name": room.name,
                "description": room.description,
                "theme": room.theme,
                "theme_emoji": theme_info["emoji"],
                "theme_color": theme_info["color"],
                "host": {
                    "id": host.id if host else None,
                    "name": host.name if host else "Unknown",
                },
                "participants": active_sessions,
                "max_participants": room.max_participants,
                "pomodoro": {
                    "enabled": room.pomodoro_enabled,
                    "work_minutes": room.work_minutes,
                    "break_minutes": room.break_minutes,
                    "state": room.current_pomodoro_state,
                    "cycle": room.current_pomodoro_cycle,
                },
                "ambient_sound": room.ambient_sound,
                "is_full": active_sessions >= room.max_participants,
            })
        
        return result
    
    def join_room(
        self,
        db: Session,
        room_id: str,
        user_id: str,
        current_task: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Join a co-working room."""
        room = self.get_room(db, room_id)
        if not room:
            raise ValueError("Room not found")
        
        if not room.is_active:
            raise ValueError("Room is no longer active")
        
        # Check capacity
        active_count = db.query(models.CoWorkingSession).filter(
            models.CoWorkingSession.room_id == room_id,
            models.CoWorkingSession.left_at == None,
        ).count()
        
        if active_count >= room.max_participants:
            raise ValueError("Room is full")
        
        # Check if already in room
        existing = db.query(models.CoWorkingSession).filter(
            models.CoWorkingSession.room_id == room_id,
            models.CoWorkingSession.user_id == user_id,
            models.CoWorkingSession.left_at == None,
        ).first()
        
        if existing:
            return {
                "session_id": existing.id,
                "already_joined": True,
                "video_url": room.video_room_url,
            }
        
        # Create session
        session = models.CoWorkingSession(
            id=str(uuid4()),
            room_id=room_id,
            user_id=user_id,
            current_task=current_task,
        )
        db.add(session)
        db.commit()
        
        logger.info("user_joined_cowork", room_id=room_id, user_id=user_id)
        
        return {
            "session_id": session.id,
            "video_url": room.video_room_url,
            "pomodoro_state": room.current_pomodoro_state,
            "ambient_sound": room.ambient_sound,
        }
    
    def leave_room(
        self,
        db: Session,
        room_id: str,
        user_id: str,
    ) -> bool:
        """Leave a co-working room."""
        session = db.query(models.CoWorkingSession).filter(
            models.CoWorkingSession.room_id == room_id,
            models.CoWorkingSession.user_id == user_id,
            models.CoWorkingSession.left_at == None,
        ).first()
        
        if not session:
            return False
        
        session.left_at = datetime.utcnow()
        
        # Calculate total focus time
        if session.joined_at:
            duration = (session.left_at - session.joined_at).total_seconds() / 60
            session.total_focus_minutes = int(duration)
        
        db.commit()
        
        logger.info("user_left_cowork", room_id=room_id, user_id=user_id)
        return True
    
    def update_pomodoro_state(
        self,
        db: Session,
        room_id: str,
        host_id: str,
        state: str,  # work, break, long_break, idle
    ) -> bool:
        """Update room's Pomodoro state (host only)."""
        room = db.query(models.CoWorkingRoom).filter(
            models.CoWorkingRoom.id == room_id,
            models.CoWorkingRoom.host_id == host_id,
        ).first()
        
        if not room:
            return False
        
        room.current_pomodoro_state = state
        
        if state == "work":
            room.current_session_start = datetime.utcnow()
        elif state == "break":
            room.current_pomodoro_cycle += 1
            # Increment pomodoros for all active participants
            db.query(models.CoWorkingSession).filter(
                models.CoWorkingSession.room_id == room_id,
                models.CoWorkingSession.left_at == None,
            ).update({"pomodoros_completed": models.CoWorkingSession.pomodoros_completed + 1})
        elif state == "idle":
            room.current_session_start = None
        
        db.commit()
        
        logger.info("pomodoro_state_changed", room_id=room_id, state=state)
        return True
    
    def get_room_participants(
        self,
        db: Session,
        room_id: str,
    ) -> List[Dict[str, Any]]:
        """Get all active participants in a room."""
        sessions = db.query(models.CoWorkingSession).filter(
            models.CoWorkingSession.room_id == room_id,
            models.CoWorkingSession.left_at == None,
        ).all()
        
        result = []
        for session in sessions:
            user = db.query(models.User).filter(
                models.User.id == session.user_id
            ).first()
            
            result.append({
                "user_id": session.user_id,
                "name": user.name if user else "Anonymous",
                "avatar": user.avatar if user else None,
                "status": session.status,
                "current_task": session.current_task,
                "pomodoros_completed": session.pomodoros_completed,
                "joined_at": session.joined_at.isoformat() if session.joined_at else None,
                "mic_enabled": session.mic_enabled,
                "camera_enabled": session.camera_enabled,
            })
        
        return result
    
    def update_user_status(
        self,
        db: Session,
        room_id: str,
        user_id: str,
        status: Optional[str] = None,
        current_task: Optional[str] = None,
        mic_enabled: Optional[bool] = None,
        camera_enabled: Optional[bool] = None,
    ) -> bool:
        """Update user's status in the room."""
        session = db.query(models.CoWorkingSession).filter(
            models.CoWorkingSession.room_id == room_id,
            models.CoWorkingSession.user_id == user_id,
            models.CoWorkingSession.left_at == None,
        ).first()
        
        if not session:
            return False
        
        if status is not None:
            session.status = status
        if current_task is not None:
            session.current_task = current_task
        if mic_enabled is not None:
            session.mic_enabled = mic_enabled
        if camera_enabled is not None:
            session.camera_enabled = camera_enabled
        
        db.commit()
        return True
    
    def get_user_stats(
        self,
        db: Session,
        user_id: str,
    ) -> Dict[str, Any]:
        """Get user's co-working statistics."""
        sessions = db.query(models.CoWorkingSession).filter(
            models.CoWorkingSession.user_id == user_id,
        ).all()
        
        total_pomodoros = sum(s.pomodoros_completed for s in sessions)
        total_minutes = sum(s.total_focus_minutes for s in sessions)
        sessions_count = len(sessions)
        
        # This week's stats
        week_start = datetime.utcnow() - timedelta(days=7)
        this_week = [s for s in sessions if s.joined_at and s.joined_at >= week_start]
        week_pomodoros = sum(s.pomodoros_completed for s in this_week)
        week_minutes = sum(s.total_focus_minutes for s in this_week)
        
        return {
            "total_sessions": sessions_count,
            "total_pomodoros": total_pomodoros,
            "total_focus_hours": round(total_minutes / 60, 1),
            "this_week": {
                "sessions": len(this_week),
                "pomodoros": week_pomodoros,
                "focus_hours": round(week_minutes / 60, 1),
            }
        }
    
    def close_room(
        self,
        db: Session,
        room_id: str,
        host_id: str,
    ) -> bool:
        """Close a room (host only)."""
        room = db.query(models.CoWorkingRoom).filter(
            models.CoWorkingRoom.id == room_id,
            models.CoWorkingRoom.host_id == host_id,
        ).first()
        
        if not room:
            return False
        
        room.is_active = False
        
        # End all active sessions
        now = datetime.utcnow()
        sessions = db.query(models.CoWorkingSession).filter(
            models.CoWorkingSession.room_id == room_id,
            models.CoWorkingSession.left_at == None,
        ).all()
        
        for session in sessions:
            session.left_at = now
            if session.joined_at:
                session.total_focus_minutes = int((now - session.joined_at).total_seconds() / 60)
        
        db.commit()
        
        logger.info("cowork_room_closed", room_id=room_id)
        return True


# Singleton
coworking_service = VirtualCoWorkingService()
