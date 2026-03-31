"""
Rate Limiting Middleware - Token bucket algorithm for API protection.
"""
import time
import structlog
from collections import defaultdict
from typing import Dict, Tuple, Optional
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from backend.config import settings

try:
    import redis

    redis_client = redis.from_url(settings.REDIS_URL)
    REDIS_AVAILABLE = True
except (ImportError, Exception):
    redis_client = None
    REDIS_AVAILABLE = False

logger = structlog.get_logger("nomadnest.rate_limit")


class RateLimiter:
    """Token bucket rate limiter with Redis backend and in-memory fallback."""

    def __init__(self, requests_per_minute: int = 60, burst_size: int = 10):
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size

        # In-memory fallback
        self._tokens: Dict[str, float] = defaultdict(lambda: float(burst_size))
        self._last_update: Dict[str, float] = defaultdict(time.time)

    def _get_client_id(self, request: Request) -> str:
        """Get client identifier from request (prioritizing user ID)."""
        # Try to get user_id from token
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            from backend.utils import verify_token
            user_id = verify_token(token, "access")
            if user_id:
                return f"user:{user_id}"

        # Fallback to IP address
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _refill_tokens_redis(self, client_id: str) -> Tuple[float, int]:
        """Redis-based rate limiting logic using a Lua script for atomicity."""
        if not REDIS_AVAILABLE or not redis_client:
            return self._refill_tokens_memory(client_id)

        key = f"rate_limit:{client_id}"
        now = time.time()

        # Lua script for atomic token bucket
        # ARGV[1] = now, ARGV[2] = capacity, ARGV[3] = fill_rate (tokens/sec)
        lua_script = """
        local key = KEYS[1]
        local now = tonumber(ARGV[1])
        local capacity = tonumber(ARGV[2])
        local fill_rate = tonumber(ARGV[3])
        
        local bucket = redis.call('HMGET', key, 'tokens', 'last_update')
        local tokens = tonumber(bucket[1]) or capacity
        local last_update = tonumber(bucket[2]) or now
        
        local elapsed = math.max(0, now - last_update)
        tokens = math.min(capacity, tokens + (elapsed * fill_rate))
        
        local allowed = 0
        if tokens >= 1 then
            tokens = tokens - 1
            allowed = 1
        end
        
        redis.call('HMSET', key, 'tokens', tokens, 'last_update', now)
        redis.call('EXPIRE', key, 60)
        
        return {allowed, tokens}
        """

        try:
            fill_rate = self.requests_per_minute / 60.0
            allowed, remaining = redis_client.eval(
                lua_script, 1, key, now, self.burst_size, fill_rate
            )
            return float(remaining), int(allowed)
        except Exception as e:
            logger.error("redis_rate_limit_error", error=str(e))
            return self._refill_tokens_memory(client_id)

    def _refill_tokens_memory(self, client_id: str) -> Tuple[float, int]:
        """In-memory fallback logic."""
        now = time.time()
        elapsed = now - self._last_update[client_id]

        tokens_to_add = elapsed * (self.requests_per_minute / 60.0)
        self._tokens[client_id] = min(
            self.burst_size, self._tokens[client_id] + tokens_to_add
        )
        self._last_update[client_id] = now

        if self._tokens[client_id] >= 1:
            self._tokens[client_id] -= 1
            return self._tokens[client_id], 1
        return self._tokens[client_id], 0

    def is_allowed(self, request: Request) -> Tuple[bool, Dict]:
        """Check if request is allowed."""
        client_id = self._get_client_id(request)

        if REDIS_AVAILABLE:
            remaining, allowed = self._refill_tokens_redis(client_id)
        else:
            remaining, allowed = self._refill_tokens_memory(client_id)

        reset_time = 60  # Default reset window

        return bool(allowed), {
            "remaining": int(remaining),
            "limit": self.requests_per_minute,
            "reset": reset_time,
        }


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to apply rate limiting to all requests."""

    def __init__(self, app, requests_per_minute: int = 60, burst_size: int = 10):
        super().__init__(app)
        self.limiter = RateLimiter(requests_per_minute, burst_size)
        # Paths to exclude from rate limiting
        self.excluded_paths = {
            "/health",
            "/health/ready",
            "/health/db",
            "/",
            "/docs",
            "/openapi.json",
            "/redoc",
        }
        # Specialized limits for sensitive paths
        self.path_overrides = {
            "/api/v1/bookings": (10, 2),  # 10 req/min, burst 2
            "/api/v1/auth/register": (5, 1),  # 5 req/min, burst 1
            "/api/v1/auth/login": (10, 5),
        }
        self._limiters: Dict[str, RateLimiter] = {}

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for excluded paths
        if request.url.path in self.excluded_paths:
            return await call_next(request)

        # Check for path overrides
        limiter = self.limiter
        for prefix, (rpm, burst) in self.path_overrides.items():
            if request.url.path.startswith(prefix):
                key = f"{prefix}:{rpm}:{burst}"
                if key not in self._limiters:
                    self._limiters[key] = RateLimiter(requests_per_minute=rpm, burst_size=burst)
                limiter = self._limiters[key]
                break

        allowed, info = limiter.is_allowed(request)

        if not allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Too many requests. Please slow down.",
                    "retry_after": info["reset"],
                },
                headers={
                    "X-RateLimit-Limit": str(info["limit"]),
                    "X-RateLimit-Remaining": str(info["remaining"]),
                    "X-RateLimit-Reset": str(info["reset"]),
                    "Retry-After": str(info["reset"]),
                },
            )

        response = await call_next(request)

        # Add rate limit headers to response
        response.headers["X-RateLimit-Limit"] = str(info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
        response.headers["X-RateLimit-Reset"] = str(info["reset"])

        return response
