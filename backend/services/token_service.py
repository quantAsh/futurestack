from datetime import datetime
import asyncio
import structlog

from jose import JWTError, jwt
from sqlalchemy.orm import Session

from backend.config import settings
from backend.errors import AuthenticationError
from backend.models import RefreshToken
from backend.utils import create_access_token, create_refresh_token

logger = structlog.get_logger("nomadnest.tokens")


def _run_async_safe(coro):
    """Run an async coroutine from sync code without leaking event loops."""
    try:
        loop = asyncio.get_running_loop()
        # We're inside an existing loop — schedule as a task (fire-and-forget)
        loop.create_task(coro)
    except RuntimeError:
        # No running loop — create one, run, and close
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(coro)
        finally:
            loop.close()


def issue_tokens(
    user_id: str,
    db: Session,
    device_info: str = None,
    ip_address: str = None,
    user_agent: str = None
) -> tuple[str, str]:
    access_token = create_access_token(user_id)
    refresh_token, token_id, expires_at = create_refresh_token(user_id)
    db.add(
        RefreshToken(
            id=token_id,
            user_id=user_id,
            expires_at=expires_at,
            revoked=False,
        )
    )
    db.commit()
    
    # Create session in Redis for tracking (non-critical)
    try:
        from backend.services import session_service
        _run_async_safe(
            session_service.create_session(
                user_id=user_id,
                token_jti=token_id,
                device_info=device_info,
                ip_address=ip_address,
                user_agent=user_agent
            )
        )
    except Exception as e:
        logger.debug("session_create_skipped", error=str(e))
    
    return access_token, refresh_token


def rotate_refresh_token(refresh_token: str, db: Session) -> tuple[str, str, str]:
    user_id, token_id = _decode_refresh_token(refresh_token)
    token_record = (
        db.query(RefreshToken)
        .filter(RefreshToken.id == token_id, RefreshToken.user_id == user_id)
        .first()
    )
    if not token_record:
        raise AuthenticationError("Refresh token not recognized")
    if token_record.revoked:
        raise AuthenticationError("Refresh token has been revoked")
    if token_record.expires_at and token_record.expires_at < datetime.utcnow():
        raise AuthenticationError("Refresh token expired")

    token_record.revoked = True
    token_record.revoked_at = datetime.utcnow()
    
    # Invalidate old session in Redis (non-critical)
    try:
        from backend.services import session_service
        _run_async_safe(session_service.invalidate_session(user_id, token_id))
    except Exception as e:
        logger.debug("session_invalidate_skipped", error=str(e))

    access_token, new_refresh_token = issue_tokens(user_id, db)
    return access_token, new_refresh_token, user_id


def revoke_refresh_token(refresh_token: str, db: Session) -> None:
    user_id, token_id = _decode_refresh_token(refresh_token)
    token_record = (
        db.query(RefreshToken)
        .filter(RefreshToken.id == token_id, RefreshToken.user_id == user_id)
        .first()
    )
    if not token_record:
        return
    token_record.revoked = True
    token_record.revoked_at = datetime.utcnow()
    db.commit()
    
    # Invalidate session in Redis (non-critical)
    try:
        from backend.services import session_service
        _run_async_safe(session_service.invalidate_session(user_id, token_id))
    except Exception as e:
        logger.debug("session_invalidate_skipped", error=str(e))


def _decode_refresh_token(token: str) -> tuple[str, str]:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
    except JWTError as exc:
        raise AuthenticationError("Invalid or expired refresh token") from exc

    if payload.get("type") != "refresh":
        raise AuthenticationError("Invalid token type")
    user_id = payload.get("sub")
    token_id = payload.get("jti")
    if not user_id or not token_id:
        raise AuthenticationError("Invalid refresh token payload")
    return user_id, token_id

