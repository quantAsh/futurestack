from uuid import uuid4
from datetime import datetime
from collections import defaultdict
import time

from typing import Union
from fastapi import APIRouter, Depends, HTTPException, status, Response, Cookie, Body, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from backend import database, models, schemas, utils
from backend.utils import mfa, get_current_user, create_access_token
from backend.errors import AuthenticationError, ValidationError
from backend.services.token_service import (
    issue_tokens,
    revoke_refresh_token,
    rotate_refresh_token,
)

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

# ─── Login Rate Limiting (in-memory, per-IP) ─────────────────────────────
_login_attempts: dict[str, list[float]] = defaultdict(list)
_LOGIN_RATE_LIMIT = 5       # max attempts
_LOGIN_RATE_WINDOW = 60     # per 60 seconds


def _check_login_rate_limit(client_ip: str) -> None:
    """Raise 429 if IP exceeds login rate limit."""
    now = time.time()
    # Prune old entries
    _login_attempts[client_ip] = [
        t for t in _login_attempts[client_ip] if now - t < _LOGIN_RATE_WINDOW
    ]
    if len(_login_attempts[client_ip]) >= _LOGIN_RATE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again in a minute.",
        )
    _login_attempts[client_ip].append(now)


def _get_client_ip(request: Request) -> str:
    """Extract client IP from request, supporting reverse proxies."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def get_db():
    yield from database.get_db()


@router.post(
    "/register",
    response_model=schemas.User,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Creates a new user profile. Returns the user details if successful.",
    responses={
        400: {"description": "Email already registered or invalid input data"},
    },
)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise ValidationError(message="Email already registered")

    # Password policy validation
    from backend.services.password_policy import validate_password
    is_valid, violations = validate_password(user.password, email=user.email)
    if not is_valid:
        raise ValidationError(message=f"Password error: {violations[0]}")

    hashed_password = utils.get_password_hash(user.password)
    new_user = models.User(
        id=str(uuid4()),
        email=user.email,
        hashed_password=hashed_password,
        name=user.name,
        is_host=user.is_host,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Audit Log
    from backend.services.audit_logging import log_user_action, AuditAction
    log_user_action(
        action=AuditAction.USER_CREATE,
        actor_id=new_user.id,
        metadata={"email": new_user.email, "role": "host" if user.is_host else "nomad"},
        db=db
    )

    # Increment custom metric
    from backend.routers.monitoring import SIGNUP_COUNT
    SIGNUP_COUNT.inc()

    return new_user


@router.post(
    "/login",
    response_model=Union[schemas.Token, schemas.MFARequiredResponse],
    summary="Login for access token",
    description="Authenticates a user. If MFA is enabled, returns a pre-auth token and requires verification.",
    responses={
        401: {"description": "Incorrect email or password"},
        202: {"description": "MFA code required"},
    },
)
def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    # Rate limit by IP
    client_ip = _get_client_ip(request)
    _check_login_rate_limit(client_ip)

    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not utils.verify_password(form_data.password, user.hashed_password):
        raise AuthenticationError(message="Incorrect email or password")

    # MFA Check
    if user.mfa_enabled:
        # Issue temporary pre-auth token
        temp_token = create_access_token(
            subject=user.id,
            expires_delta=utils.timedelta(minutes=5),
            additional_claims={"type": "pre-auth"}
        )
        response.status_code = status.HTTP_202_ACCEPTED
        return {
            "mfa_required": True,
            "temp_token": temp_token,
            "message": "Two-factor authentication code required"
        }

    # Capture device info for session tracking
    user_agent = request.headers.get("User-Agent", "unknown")
    access_token, refresh_token = issue_tokens(
        user.id, db,
        ip_address=client_ip,
        user_agent=user_agent,
    )

    # Audit Log: Login Success
    from backend.services.audit_logging import log_user_action, AuditAction
    log_user_action(
        action=AuditAction.AUTH_LOGIN,
        actor_id=user.id,
        metadata={"ip": client_ip, "user_agent": user_agent[:100]},
        db=db
    )

    # Track analytics event
    from backend.services.analytics_service import analytics_service
    analytics_service.track(
        event_name="user_login",
        user_id=user.id,
        properties={"method": "password"},
    )

    # Set refresh token in HTTP-only cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,  # Should be True in production (HTTPS)
        samesite="lax",
        max_age=60 * 60 * 24 * 7,  # 7 days
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }


@router.post(
    "/change-password",
    status_code=status.HTTP_200_OK,
    summary="Change Password",
    description="Update user password with policy enforcement.",
)
def change_password(
    req: schemas.PasswordChangeRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Verify current password
    if not utils.verify_password(req.current_password, current_user.hashed_password):
        raise AuthenticationError(message="Incorrect current password")

    # Validate new password
    from backend.services.password_policy import validate_password
    is_valid, violations = validate_password(req.new_password, email=current_user.email)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Password error: {violations[0]}")

    # Update password
    current_user.hashed_password = utils.get_password_hash(req.new_password)
    
    # Audit Log
    from backend.services.audit_logging import log_user_action, AuditAction
    log_user_action(
        action=AuditAction.AUTH_PASSWORD_CHANGE,
        actor_id=current_user.id,
        db=db
    )
    
    # Revoke all other sessions for security (password change = force logout everywhere)
    db.query(models.RefreshToken).filter(
        models.RefreshToken.user_id == current_user.id,
        models.RefreshToken.revoked == False,
    ).update({"revoked": True, "revoked_at": datetime.utcnow()})
    
    # Also invalidate sessions in session store
    from backend.services import session_service
    import asyncio
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(session_service.invalidate_all_sessions(current_user.id))
    except RuntimeError:
        asyncio.run(session_service.invalidate_all_sessions(current_user.id))
    
    db.commit()
    return {"status": "password_updated", "sessions_revoked": True}


@router.post(
    "/mfa/verify-login",
    response_model=schemas.Token,
    summary="Verify MFA Login",
    description="Complete login by verifying TOTP code with pre-auth token."
)
def verify_mfa_login(
    payload: schemas.MFALoginVerifyRequest,
    response: Response,
    db: Session = Depends(get_db)
):
    # Verify pre-auth token
    claims = utils.decode_token(payload.temp_token)
    if not claims or claims.get("type") != "pre-auth":
        raise AuthenticationError(message="Invalid or expired pre-auth session")
    
    user_id = claims.get("sub")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise AuthenticationError(message="User not found")
        
    # Verify MFA Code
    if not mfa.verify_totp(user.mfa_secret, payload.code):
        raise AuthenticationError(message="Invalid MFA code")
        
    # Issue real tokens
    access_token, refresh_token = issue_tokens(user.id, db)

    # Set refresh token in HTTP-only cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }


@router.post(
    "/mfa/setup",
    response_model=schemas.MFASetupResponse,
    summary="Setup MFA",
    description="Generate a new MFA secret and QR code."
)
def setup_mfa(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.mfa_enabled:
         raise HTTPException(status_code=400, detail="MFA is already enabled")
         
    secret = mfa.generate_mfa_secret()
    
    # Store secret temporarily or permanently? 
    # Store it but don't enable it. Overwrite if exists and not enabled.
    current_user.mfa_secret = secret
    db.commit()
    
    uri = mfa.get_totp_uri(secret, current_user.email)
    qr_code = mfa.generate_qr_code(uri)
    
    return {"secret": secret, "qr_code": qr_code}


@router.post(
    "/mfa/enable",
    status_code=status.HTTP_200_OK,
    summary="Enable MFA",
    description="Verify code and enable MFA for the account. Returns one-time recovery codes."
)
def enable_mfa(
    req: schemas.MFAVerifyRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.mfa_secret:
        raise HTTPException(status_code=400, detail="MFA setup not initiated")
        
    if not mfa.verify_totp(current_user.mfa_secret, req.code):
        raise HTTPException(status_code=400, detail="Invalid MFA code")
    
    # Generate recovery codes
    plain_codes = mfa.generate_recovery_codes()
    hashed_codes = [mfa.hash_recovery_code(c) for c in plain_codes]
    
    current_user.mfa_enabled = True
    current_user.mfa_recovery_codes = hashed_codes
    db.commit()
    
    # Return plain codes to user (they should save these!)
    return {
        "status": "MFA enabled",
        "recovery_codes": plain_codes,
        "message": "Save these recovery codes securely. Each code can only be used once."
    }


@router.post(
    "/mfa/disable",
    status_code=status.HTTP_200_OK,
    summary="Disable MFA",
    description="Disable MFA for the account."
)
def disable_mfa(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    current_user.mfa_enabled = False
    current_user.mfa_secret = None
    current_user.mfa_recovery_codes = None
    db.commit()
    return {"status": "MFA disabled"}


@router.post(
    "/mfa/verify-recovery",
    response_model=schemas.Token,
    summary="Verify MFA with Recovery Code",
    description="Complete login using a one-time recovery code instead of TOTP."
)
def verify_recovery_login(
    payload: schemas.MFARecoveryRequest,
    response: Response,
    db: Session = Depends(get_db)
):
    # Verify pre-auth token
    claims = utils.decode_token(payload.temp_token)
    if not claims or claims.get("type") != "pre-auth":
        raise AuthenticationError(message="Invalid or expired pre-auth session")
    
    user_id = claims.get("sub")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise AuthenticationError(message="User not found")
    
    if not user.mfa_recovery_codes:
        raise AuthenticationError(message="No recovery codes available")
    
    # Verify recovery code
    match_idx = mfa.verify_recovery_code(payload.recovery_code, user.mfa_recovery_codes)
    if match_idx is None:
        raise AuthenticationError(message="Invalid recovery code")
    
    # Remove used recovery code (one-time use)
    remaining_codes = list(user.mfa_recovery_codes)
    remaining_codes.pop(match_idx)
    user.mfa_recovery_codes = remaining_codes if remaining_codes else None
    db.commit()
    
    # Issue real tokens
    access_token, refresh_token = issue_tokens(user.id, db)

    # Set refresh token in HTTP-only cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }


@router.post(
    "/refresh",
    response_model=schemas.Token,
    summary="Refresh access token",
    description="Rotate the refresh token and issue a new access token. Requires the refresh token cookie.",
    responses={
        401: {"description": "Refresh token missing or invalid"},
    },
)
def refresh_tokens(
    response: Response, refresh_token: str = Cookie(None), db: Session = Depends(get_db)
):
    if not refresh_token:
        raise AuthenticationError(message="Refresh token missing")

    access_token, new_refresh_token, _ = rotate_refresh_token(refresh_token, db)

    # Update refresh token cookie
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }


@router.post(
    "/logout",
    summary="Logout user",
    description="Revoke the refresh token, blacklist access token, and clear the authentication cookie.",
)
async def logout(
    response: Response, 
    refresh_token: str = Cookie(None), 
    access_token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    if refresh_token:
        revoke_refresh_token(refresh_token, db)
    
    # Blacklist access token
    from backend.utils import blacklist_token
    if access_token:
        await blacklist_token(access_token)

        # Audit Log: Logout
        # Need to decode token to get user_id if we want to log it?
        # Actually `logout` doesn't enforce `get_current_user` dependency in signature fully?
        # Wait, signature is `access_token: str = Depends(oauth2_scheme)`.
        # We can extract user_id if needed, but for now we might skip actor_id if not easily available.
        # But wait, audit logs are better with actor_id. 
        # Ideally we should depend on `get_current_user`.
        # But to avoid breaking changes, let's try to get it if possible.
        pass

    response.delete_cookie("refresh_token")
    return {"status": "logged_out"}


# --- Session Management Endpoints ---

@router.get(
    "/sessions",
    summary="List active sessions",
    description="Get all active sessions for the current user across devices.",
)
async def list_sessions(
    current_user: models.User = Depends(get_current_user),
):
    from backend.services import session_service
    
    sessions = await session_service.get_active_sessions(current_user.id)
    return {
        "sessions": [s.model_dump() for s in sessions],
        "count": len(sessions)
    }


@router.post(
    "/sessions/revoke-all",
    summary="Revoke all sessions",
    description="Logout from all devices except the current session (if specified).",
)
async def revoke_all_sessions(
    keep_current: bool = True,
    refresh_token: str = Cookie(None),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from backend.services import session_service
    from backend.services.token_service import _decode_refresh_token
    
    current_session_id = None
    if keep_current and refresh_token:
        try:
            _, current_session_id = _decode_refresh_token(refresh_token)
        except Exception:
            pass
    
    # Invalidate sessions in Redis
    count = await session_service.invalidate_all_sessions(
        current_user.id, 
        except_session=current_session_id
    )
    
    # Also revoke refresh tokens in DB
    tokens = db.query(models.RefreshToken).filter(
        models.RefreshToken.user_id == current_user.id,
        models.RefreshToken.revoked == False
    ).all()
    
    for token in tokens:
        if current_session_id and token.id == current_session_id:
            continue
        token.revoked = True
        token.revoked_at = datetime.utcnow()
    
    db.commit()
    
    return {
        "status": "sessions_revoked",
        "count": count,
        "kept_current": keep_current and current_session_id is not None
    }


@router.delete(
    "/sessions/{session_id}",
    summary="Revoke specific session",
    description="Logout from a specific device/session.",
)
async def revoke_session(
    session_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from backend.services import session_service
    
    # Invalidate in Redis
    await session_service.invalidate_session(current_user.id, session_id)
    
    # Also revoke in DB
    token = db.query(models.RefreshToken).filter(
        models.RefreshToken.id == session_id,
        models.RefreshToken.user_id == current_user.id
    ).first()
    
    if token:
        token.revoked = True
        token.revoked_at = datetime.utcnow()
        db.commit()
    
    return {"status": "session_revoked", "session_id": session_id}

