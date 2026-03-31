"""
Auth middleware - re-exports authentication utilities.
"""
from typing import Optional
from fastapi import Depends, HTTPException, status
from backend.utils import get_current_user as _get_current_user_optional
from backend import models


async def get_current_user(
    user: Optional[models.User] = Depends(_get_current_user_optional)
) -> models.User:
    """
    Dependency that requires authentication.
    Raises 401 if not authenticated.
    """
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_optional_user(
    user: Optional[models.User] = Depends(_get_current_user_optional)
) -> Optional[models.User]:
    """
    Dependency for optional authentication.
    Returns None if not authenticated.
    """
    return user


__all__ = ["get_current_user", "get_optional_user"]
