"""
Session Management Service.
Uses Redis when available, falls back to SQLite/DB for persistence.
SQLite fallback is the default for local development (no Redis required).
"""
import json
from datetime import datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel
import structlog

from backend.config import settings

logger = structlog.get_logger("nomadnest.session")

# Session TTL (matches refresh token expiry)
SESSION_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days


def _get_redis():
    """Lazy Redis import — returns None if unavailable."""
    try:
        from backend.utils.cache import redis_client
        return redis_client
    except Exception:
        return None


class SessionInfo(BaseModel):
    """Active session metadata."""
    session_id: str  # Same as refresh token JTI
    user_id: str
    device_info: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: str
    last_active: str
    is_current: bool = False


# ─── DB Fallback (SQLite/Postgres) ────────────────────────────────────────

def _db_create_session(
    user_id: str,
    token_jti: str,
    device_info: str = None,
    ip_address: str = None,
    user_agent: str = None,
    expires_at: datetime = None,
) -> str:
    from backend.database import get_db_context
    from backend.models import UserSession

    with get_db_context() as db:
        session = UserSession(
            id=token_jti,
            user_id=user_id,
            device_info=device_info,
            ip_address=ip_address,
            user_agent=user_agent,
            is_active=True,
            expires_at=expires_at or (datetime.utcnow() + timedelta(seconds=SESSION_TTL_SECONDS)),
        )
        db.merge(session)  # merge in case of retry/duplicate
        db.commit()
    logger.info("session_created", user_id=user_id, session_id=token_jti[:8], backend="db")
    return token_jti


def _db_get_active_sessions(user_id: str) -> List[SessionInfo]:
    from backend.database import get_db_context
    from backend.models import UserSession

    sessions = []
    with get_db_context() as db:
        records = (
            db.query(UserSession)
            .filter(
                UserSession.user_id == user_id,
                UserSession.is_active == True,
                UserSession.expires_at > datetime.utcnow(),
            )
            .order_by(UserSession.last_active.desc())
            .all()
        )
        for r in records:
            sessions.append(SessionInfo(
                session_id=r.id,
                user_id=r.user_id,
                device_info=r.device_info,
                ip_address=r.ip_address,
                user_agent=r.user_agent,
                created_at=r.created_at.isoformat() if r.created_at else "",
                last_active=r.last_active.isoformat() if r.last_active else "",
            ))
    return sessions


def _db_invalidate_session(user_id: str, token_jti: str) -> bool:
    from backend.database import get_db_context
    from backend.models import UserSession

    with get_db_context() as db:
        session = db.query(UserSession).filter(
            UserSession.id == token_jti,
            UserSession.user_id == user_id,
        ).first()
        if session:
            session.is_active = False
            db.commit()
            logger.info("session_invalidated", user_id=user_id, session_id=token_jti[:8], backend="db")
            return True
    return False


def _db_invalidate_all_sessions(user_id: str, except_session: str = None) -> int:
    from backend.database import get_db_context
    from backend.models import UserSession

    count = 0
    with get_db_context() as db:
        query = db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.is_active == True,
        )
        if except_session:
            query = query.filter(UserSession.id != except_session)

        records = query.all()
        for r in records:
            r.is_active = False
            count += 1
        db.commit()
    logger.info("sessions_invalidated_all", user_id=user_id, count=count, backend="db")
    return count


def _db_is_session_valid(user_id: str, token_jti: str) -> bool:
    from backend.database import get_db_context
    from backend.models import UserSession

    with get_db_context() as db:
        session = db.query(UserSession).filter(
            UserSession.id == token_jti,
            UserSession.user_id == user_id,
            UserSession.is_active == True,
            UserSession.expires_at > datetime.utcnow(),
        ).first()
        return session is not None


def _db_get_session_count(user_id: str) -> int:
    from backend.database import get_db_context
    from backend.models import UserSession

    with get_db_context() as db:
        return db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.is_active == True,
            UserSession.expires_at > datetime.utcnow(),
        ).count()


# ─── Public API (async wrappers — Redis first, DB fallback) ──────────────

async def create_session(
    user_id: str,
    token_jti: str,
    device_info: str = None,
    ip_address: str = None,
    user_agent: str = None
) -> str:
    """Create a new session entry. Uses Redis if available, DB otherwise."""
    redis = _get_redis()
    if redis:
        try:
            session_key = f"session:{user_id}:{token_jti}"
            now = datetime.utcnow().isoformat()
            session_data = {
                "session_id": token_jti,
                "user_id": user_id,
                "device_info": device_info,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "created_at": now,
                "last_active": now,
            }
            await redis.setex(session_key, SESSION_TTL_SECONDS, json.dumps(session_data))
            user_sessions_key = f"user_sessions:{user_id}"
            await redis.sadd(user_sessions_key, token_jti)
            await redis.expire(user_sessions_key, SESSION_TTL_SECONDS)
            logger.info("session_created", user_id=user_id, session_id=token_jti[:8], backend="redis")
            return token_jti
        except Exception as e:
            logger.warning("redis_session_fallback", error=str(e))

    # DB fallback
    return _db_create_session(user_id, token_jti, device_info, ip_address, user_agent)


async def get_active_sessions(user_id: str) -> List[SessionInfo]:
    """Get all active sessions for a user."""
    redis = _get_redis()
    if redis:
        try:
            sessions = []
            user_sessions_key = f"user_sessions:{user_id}"
            session_ids = await redis.smembers(user_sessions_key)
            for session_id in session_ids:
                session_key = f"session:{user_id}:{session_id}"
                session_data = await redis.get(session_key)
                if session_data:
                    data = json.loads(session_data)
                    sessions.append(SessionInfo(**data))
                else:
                    await redis.srem(user_sessions_key, session_id)
            sessions.sort(key=lambda s: s.last_active, reverse=True)
            return sessions
        except Exception as e:
            logger.warning("redis_session_list_fallback", error=str(e))

    return _db_get_active_sessions(user_id)


async def update_session_activity(user_id: str, token_jti: str):
    """Update last_active timestamp for a session."""
    redis = _get_redis()
    if redis:
        try:
            session_key = f"session:{user_id}:{token_jti}"
            session_data = await redis.get(session_key)
            if session_data:
                data = json.loads(session_data)
                data["last_active"] = datetime.utcnow().isoformat()
                await redis.setex(session_key, SESSION_TTL_SECONDS, json.dumps(data))
                return
        except Exception as e:
            logger.warning("session_update_error", error=str(e))

    # DB fallback: last_active auto-updates via onupdate=func.now()


async def invalidate_session(user_id: str, token_jti: str) -> bool:
    """Invalidate a specific session."""
    redis = _get_redis()
    if redis:
        try:
            session_key = f"session:{user_id}:{token_jti}"
            user_sessions_key = f"user_sessions:{user_id}"
            await redis.delete(session_key)
            await redis.srem(user_sessions_key, token_jti)
            logger.info("session_invalidated", user_id=user_id, session_id=token_jti[:8], backend="redis")
            # Also invalidate in DB for consistency
        except Exception as e:
            logger.warning("redis_session_invalidate_fallback", error=str(e))

    return _db_invalidate_session(user_id, token_jti)


async def invalidate_all_sessions(user_id: str, except_session: str = None) -> int:
    """Invalidate all sessions for a user (except optionally the current one)."""
    redis = _get_redis()
    if redis:
        try:
            user_sessions_key = f"user_sessions:{user_id}"
            session_ids = await redis.smembers(user_sessions_key)
            for session_id in session_ids:
                if except_session and session_id == except_session:
                    continue
                session_key = f"session:{user_id}:{session_id}"
                await redis.delete(session_key)
                await redis.srem(user_sessions_key, session_id)
        except Exception as e:
            logger.warning("redis_session_invalidate_all_fallback", error=str(e))

    return _db_invalidate_all_sessions(user_id, except_session)


async def is_session_valid(user_id: str, token_jti: str) -> bool:
    """Check if a session is still valid. Fast O(1) check."""
    redis = _get_redis()
    if redis:
        try:
            session_key = f"session:{user_id}:{token_jti}"
            exists = await redis.exists(session_key)
            if exists:
                return True
            # If not in Redis, check DB (might have been created via fallback)
        except Exception as e:
            logger.warning("session_check_error", error=str(e))

    return _db_is_session_valid(user_id, token_jti)


async def get_session_count(user_id: str) -> int:
    """Get count of active sessions for a user."""
    redis = _get_redis()
    if redis:
        try:
            user_sessions_key = f"user_sessions:{user_id}"
            count = await redis.scard(user_sessions_key)
            if count > 0:
                return count
        except Exception as e:
            logger.warning("session_count_error", error=str(e))

    return _db_get_session_count(user_id)
