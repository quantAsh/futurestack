import json
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, Response
import re
import structlog

logger = structlog.get_logger("nomadnest.xss")

# XSS patterns to detect in user input
XSS_PATTERNS = [
    re.compile(r"<script", re.IGNORECASE),
    re.compile(r"javascript:", re.IGNORECASE),
    re.compile(r"on(load|error|click|mouseover|focus|blur|submit|change|input|keyup|keydown)\s*=", re.IGNORECASE),
    re.compile(r"eval\s*\(", re.IGNORECASE),
    re.compile(r"alert\s*\(", re.IGNORECASE),
    re.compile(r"document\.(cookie|location|write)", re.IGNORECASE),
    re.compile(r"<iframe", re.IGNORECASE),
    re.compile(r"<object", re.IGNORECASE),
    re.compile(r"<embed", re.IGNORECASE),
    re.compile(r"<svg[^>]+on\w+\s*=", re.IGNORECASE),
    re.compile(r"data:\s*text/html", re.IGNORECASE),
    re.compile(r"expression\s*\(", re.IGNORECASE),  # CSS expression injection
    re.compile(r"url\s*\(\s*['\"]?javascript:", re.IGNORECASE),  # CSS url() injection
]

# Max body size to scan (skip large uploads)
MAX_SCAN_BODY_SIZE = 64 * 1024  # 64 KB


def _scan_value(value: str) -> str | None:
    """Scan a single string value for XSS patterns. Returns matched pattern or None."""
    for pattern in XSS_PATTERNS:
        if pattern.search(value):
            return pattern.pattern
    return None


def _scan_recursive(data, path: str = "") -> str | None:
    """Recursively scan JSON data for XSS patterns. Returns path:pattern or None."""
    if isinstance(data, str):
        match = _scan_value(data)
        if match:
            return f"{path}: {match}"
    elif isinstance(data, dict):
        for key, val in data.items():
            # Also scan keys
            key_match = _scan_value(str(key))
            if key_match:
                return f"{path}.key({key}): {key_match}"
            result = _scan_recursive(val, f"{path}.{key}")
            if result:
                return result
    elif isinstance(data, list):
        for i, item in enumerate(data):
            result = _scan_recursive(item, f"{path}[{i}]")
            if result:
                return result
    return None


class XSSMiddleware(BaseHTTPMiddleware):
    """
    Middleware to detect and block XSS attempts in:
    1. Query parameters
    2. JSON POST/PUT/PATCH request bodies
    3. Request headers (Referer, etc.)
    """

    async def dispatch(self, request: Request, call_next):
        # === Layer 1: Query parameters ===
        for key, value in request.query_params.items():
            match = _scan_value(value)
            if match:
                logger.warning("xss_blocked_query", path=request.url.path, param=key, pattern=match)
                return Response(
                    content=json.dumps({"error": "Malicious input detected in query parameters"}),
                    media_type="application/json",
                    status_code=400,
                )

        # === Layer 2: JSON body (POST, PUT, PATCH) ===
        if request.method in ("POST", "PUT", "PATCH"):
            content_type = request.headers.get("content-type", "")
            content_length = int(request.headers.get("content-length", "0") or "0")

            if "application/json" in content_type and 0 < content_length <= MAX_SCAN_BODY_SIZE:
                try:
                    body_bytes = await request.body()
                    body_data = json.loads(body_bytes)

                    xss_hit = _scan_recursive(body_data)
                    if xss_hit:
                        logger.warning("xss_blocked_body", path=request.url.path, match=xss_hit[:200])
                        return Response(
                            content=json.dumps({"error": "Malicious input detected in request body"}),
                            media_type="application/json",
                            status_code=400,
                        )
                except (json.JSONDecodeError, UnicodeDecodeError):
                    pass  # Not valid JSON — let downstream handlers deal with it

        # === Layer 3: Suspicious headers ===
        referer = request.headers.get("referer", "")
        if referer:
            match = _scan_value(referer)
            if match:
                logger.warning("xss_blocked_header", path=request.url.path, header="referer", pattern=match)
                return Response(
                    content=json.dumps({"error": "Malicious input detected in request headers"}),
                    media_type="application/json",
                    status_code=400,
                )

        return await call_next(request)
