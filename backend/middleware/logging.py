"""
Request Logging Middleware - Log all API requests for monitoring.
"""
import time
import structlog
from typing import Dict, Any
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from backend.config import settings
from backend.utils.context import get_request_id, get_user_id

# Attempt to import Sentry
try:
    import sentry_sdk
    from sentry_sdk import set_context
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False

# Note: structlog is configured once in config/observability.py via setup_logging()
logger = structlog.get_logger("nomadnest.api")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all incoming requests in JSON format using structlog."""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        request_id = get_request_id()
        user_id = get_user_id()

        # Get client info
        client_ip = request.headers.get(
            "x-forwarded-for", request.client.host if request.client else "unknown"
        )
        user_agent = request.headers.get("user-agent", "unknown")[:100]

        # Prepare context for Sentry
        if SENTRY_AVAILABLE:
            set_context(
                "request",
                {
                    "method": request.method,
                    "url": str(request.url),
                    "client_ip": client_ip,
                    "user_agent": user_agent,
                    "request_id": request_id,
                },
            )

        # Process request
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            if SENTRY_AVAILABLE:
                sentry_sdk.capture_exception(e)
            
            # Log error before re-raising
            logger.error(
                "request_failed",
                method=request.method,
                path=request.url.path,
                error=str(e),
                request_id=request_id,
                user_id=user_id,
                client_ip=client_ip
            )
            raise e

        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000

        # Log request with structlog
        log_kwargs = {
            "method": request.method,
            "path": request.url.path,
            "status": status_code,
            "duration_ms": round(duration_ms, 2),
            "client_ip": client_ip,
            "user_agent": user_agent,
            "request_id": request_id,
            "user_id": user_id,
        }

        if status_code >= 500:
            logger.error("request_error", **log_kwargs)
        elif status_code >= 400:
            logger.warning("request_warning", **log_kwargs)
        else:
            logger.info("request_handled", **log_kwargs)

        # Add timing header
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"

        return response
