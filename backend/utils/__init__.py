from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import uuid4
import structlog

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from backend import models
from backend.config import settings
from backend.database import get_db
from backend.utils.context import set_user_id

try:
    from backend.utils.cache import redis_client
except ImportError:
    redis_client = None

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(subject: str | Any, expires_delta: timedelta = None) -> str:
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode = {"exp": expire, "sub": str(subject), "type": "access"}
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def create_refresh_token(subject: str | Any) -> tuple[str, str, datetime]:
    """Create a refresh token with longer expiry."""
    token_id = uuid4().hex
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "type": "refresh",
        "jti": token_id,
    }
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt, token_id, expire


def verify_token(token: str, token_type: str = "access") -> Optional[str]:
    """Verify a JWT token and return the subject (user_id) if valid."""
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        if payload.get("type") != token_type:
            return None
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
        return user_id
    except JWTError:
        return None


def decode_token(token: str) -> dict:
    """Decode a JWT token and return the payload."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


async def blacklist_token(token: str):
    """Add a token to the blacklist."""
    if not redis_client:
        return

    try:
        payload = decode_token(token)
        jti = payload.get("jti")
        exp = payload.get("exp")

        if jti and exp:
            now = datetime.utcnow().timestamp()
            ttl = int(exp - now)
            if ttl > 0:
                await redis_client.setex(f"blacklist:{jti}", ttl, "true")
    except Exception as e:
        structlog.get_logger("nomadnest.auth").warning("token_blacklist_failed", error=str(e))


async def check_token_blacklist(token: str) -> bool:
    """Check if a token is blacklisted."""
    if not redis_client:
        return False

    try:
        payload = decode_token(token)
        # Note: redundant decode if called after verify,
        # but robust. Optimally extract jti from payload passed in.
        jti = payload.get("jti")
        if jti:
            is_blacklisted = await redis_client.exists(f"blacklist:{jti}")
            return bool(is_blacklisted)
    except:
        pass
    return False


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> Optional[models.User]:
    """
    Dependency to get the current authenticated user.
    Returns None if not authenticated (for optional auth routes).
    """
    if not token:
        return None

    # Check blacklist
    if await check_token_blacklist(token):
        return None

    user_id = verify_token(token, "access")
    if not user_id:
        return None

    set_user_id(user_id)

    user = db.query(models.User).filter(models.User.id == user_id).first()
    return user


async def require_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> models.User:
    """
    Dependency that requires authentication.
    Raises 401 if not authenticated.
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check blacklist
    if await check_token_blacklist(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = verify_token(token, "access")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    set_user_id(user_id)

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def require_host(user: models.User = Depends(require_current_user)) -> models.User:
    """Dependency that requires the user to be a host."""
    if not user.is_host:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Host access required"
        )
    return user


async def require_admin(
    user: models.User = Depends(require_current_user),
) -> models.User:
    """
    Centralized admin dependency — use for all admin-only endpoints.
    Raises 403 if authenticated user is not an admin.
    """
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return user

