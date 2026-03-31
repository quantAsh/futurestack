"""
Tool Middleware — Production hardening layer for AI agent tool calls.

Provides:
- Rate limiting (per-user sliding window)
- Response caching (TTL-based in-memory cache)
- Input validation (Pydantic-based param checks)
- Metrics logging (structured logs for every tool call)
"""
try:
    import structlog
    logger = structlog.get_logger("nomadnest.tool_middleware")
    _HAS_STRUCTLOG = True
except ImportError:
    import logging
    logger = logging.getLogger("nomadnest.tool_middleware")
    _HAS_STRUCTLOG = False


def _log(level: str, msg: str, **kwargs):
    """Log that works with both structlog (kwargs) and stdlib (formatted string)."""
    log_fn = getattr(logger, level, logger.info)
    if _HAS_STRUCTLOG:
        log_fn(msg, **kwargs)
    else:
        extra = " ".join(f"{k}={v}" for k, v in kwargs.items())
        log_fn(f"{msg} {extra}".strip())

import time
from typing import Dict, Any, Optional, Callable
from collections import defaultdict


# --- Rate Limiting ---

RATE_LIMITS: Dict[str, Dict[str, int]] = {
    "default": {"calls": 30, "window_seconds": 60},
    "search_all_platforms": {"calls": 5, "window_seconds": 60},
    "create_booking": {"calls": 3, "window_seconds": 60},
    "escalate_to_human": {"calls": 2, "window_seconds": 60},
    "get_weather": {"calls": 10, "window_seconds": 60},
    "get_visa_requirements": {"calls": 10, "window_seconds": 60},
    "suggest_itinerary": {"calls": 5, "window_seconds": 60},
}

# Sliding window: {(user_id, tool_name): [timestamps]}
_rate_windows: Dict[tuple, list] = defaultdict(list)


def check_rate_limit(tool_name: str, user_id: str = "anonymous") -> Optional[Dict[str, Any]]:
    """
    Check if a tool call is within rate limits.
    Returns None if allowed, or an error dict if rate-limited.
    """
    limits = RATE_LIMITS.get(tool_name, RATE_LIMITS["default"])
    key = (user_id, tool_name)
    now = time.time()
    window = limits["window_seconds"]

    # Prune old entries
    _rate_windows[key] = [ts for ts in _rate_windows[key] if now - ts < window]

    if len(_rate_windows[key]) >= limits["calls"]:
        oldest = min(_rate_windows[key])
        retry_after = int(window - (now - oldest)) + 1
        _log("warning", "rate_limit_exceeded",
            tool=tool_name, user_id=user_id,
            limit=limits["calls"], window=window)
        return {
            "error": "rate_limit_exceeded",
            "message": f"Too many requests for {tool_name}. Try again in {retry_after} seconds.",
            "retry_after_seconds": retry_after,
        }

    # Record this call
    _rate_windows[key].append(now)
    return None


# --- Response Caching ---

CACHE_TTLS: Dict[str, int] = {
    "get_weather": 3600,            # 1 hour
    "get_safety_brief": 86400,      # 24 hours
    "emergency_contacts": 604800,   # 7 days
    "compare_cost_of_living": 3600, # 1 hour
    "get_destination_brief": 3600,  # 1 hour
    "scam_alerts": 86400,           # 24 hours
    "health_advisories": 86400,     # 24 hours
    "get_currency_tips": 86400,     # 24 hours
    "community_pulse": 1800,        # 30 min
    "curate_local_events": 1800,    # 30 min
}

# Cache: {cache_key: (timestamp, result)}
_response_cache: Dict[str, tuple] = {}
_MAX_CACHE_SIZE = 500


def _make_cache_key(tool_name: str, params: Dict) -> str:
    """Generate a deterministic cache key from tool name + sorted params."""
    import hashlib
    import json
    # Sort params for consistent keys
    param_str = json.dumps(params, sort_keys=True, default=str)
    return f"{tool_name}:{hashlib.md5(param_str.encode()).hexdigest()}"


def get_cached(tool_name: str, params: Dict) -> Optional[Dict]:
    """
    Check if a cached response exists and is still valid.
    Returns the cached result or None.
    """
    ttl = CACHE_TTLS.get(tool_name)
    if not ttl:
        return None

    key = _make_cache_key(tool_name, params)
    if key in _response_cache:
        ts, result = _response_cache[key]
        if time.time() - ts < ttl:
            _log("debug", "cache_hit", tool=tool_name)
            return result
        else:
            del _response_cache[key]  # Expired
    return None


def set_cached(tool_name: str, params: Dict, result: Dict) -> None:
    """Store a tool result in the cache."""
    if tool_name not in CACHE_TTLS:
        return

    # Evict oldest entries if cache is full
    if len(_response_cache) >= _MAX_CACHE_SIZE:
        oldest_key = min(_response_cache, key=lambda k: _response_cache[k][0])
        del _response_cache[oldest_key]

    key = _make_cache_key(tool_name, params)
    _response_cache[key] = (time.time(), result)
    _log("debug", "cache_set", tool=tool_name)


def clear_cache(tool_name: Optional[str] = None) -> int:
    """Clear cache entries. If tool_name given, clear only that tool's cache."""
    global _response_cache
    if tool_name:
        keys = [k for k in _response_cache if k.startswith(f"{tool_name}:")]
        for k in keys:
            del _response_cache[k]
        return len(keys)
    else:
        count = len(_response_cache)
        _response_cache = {}
        return count


# --- Input Validation ---

# Validation rules per tool parameter
VALIDATION_RULES: Dict[str, Dict[str, dict]] = {
    "get_weather": {
        "location": {"type": str, "min_len": 1, "max_len": 100},
    },
    "get_safety_brief": {
        "city": {"type": str, "min_len": 1, "max_len": 100},
    },
    "get_visa_requirements": {
        "destination": {"type": str, "min_len": 1, "max_len": 100},
        "nationality": {"type": str, "min_len": 1, "max_len": 100},
        "stay_duration": {"type": int, "min_val": 1, "max_val": 3650, "optional": True},
    },
    "get_smart_pricing": {
        "current_price": {"type": float, "min_val": 0, "max_val": 100000},
        "city": {"type": str, "min_len": 1, "max_len": 100},
        "occupancy_rate": {"type": float, "min_val": 0, "max_val": 1},
    },
    "draft_review_response": {
        "rating": {"type": int, "min_val": 1, "max_val": 5},
    },
    "estimate_trip_budget": {
        "total_days": {"type": int, "min_val": 1, "max_val": 365},
        "budget_tier": {"type": str, "enum": ["budget", "moderate", "luxury"]},
    },
}


def validate_params(tool_name: str, params: Dict) -> Optional[Dict[str, Any]]:
    """
    Validate tool parameters against rules.
    Returns None if valid, or error dict if invalid.
    """
    rules = VALIDATION_RULES.get(tool_name, {})
    if not rules:
        return None

    errors = []
    for param_name, rule in rules.items():
        value = params.get(param_name)

        # Skip optional params that are None
        if value is None and rule.get("optional"):
            continue

        # Required param missing
        if value is None:
            errors.append(f"Missing required parameter: {param_name}")
            continue

        # Type check
        expected_type = rule.get("type")
        if expected_type and not isinstance(value, expected_type):
            # Allow int for float params
            if expected_type == float and isinstance(value, int):
                pass
            else:
                errors.append(f"{param_name}: expected {expected_type.__name__}, got {type(value).__name__}")
                continue

        # String length
        if isinstance(value, str):
            if rule.get("min_len") and len(value) < rule["min_len"]:
                errors.append(f"{param_name}: too short (min {rule['min_len']} chars)")
            if rule.get("max_len") and len(value) > rule["max_len"]:
                errors.append(f"{param_name}: too long (max {rule['max_len']} chars)")

        # Numeric range
        if isinstance(value, (int, float)):
            if rule.get("min_val") is not None and value < rule["min_val"]:
                errors.append(f"{param_name}: value {value} below minimum {rule['min_val']}")
            if rule.get("max_val") is not None and value > rule["max_val"]:
                errors.append(f"{param_name}: value {value} above maximum {rule['max_val']}")

        # Enum check
        if rule.get("enum") and value not in rule["enum"]:
            errors.append(f"{param_name}: must be one of {rule['enum']}")

    if errors:
        _log("warning", "param_validation_failed", tool=tool_name, errors=errors)
        return {
            "error": "invalid_parameters",
            "message": "; ".join(errors),
            "errors": errors,
        }

    return None


# --- Metrics Logging ---

# In-memory metrics counters
_tool_metrics: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
    "call_count": 0,
    "error_count": 0,
    "total_duration_ms": 0,
    "cache_hits": 0,
    "rate_limits": 0,
})


def log_tool_call(
    tool_name: str,
    params: Dict,
    result: Optional[Dict],
    duration_ms: float,
    user_id: str = "anonymous",
    success: bool = True,
    error: Optional[str] = None,
    cache_hit: bool = False,
) -> None:
    """Log structured metrics for a tool call."""
    metrics = _tool_metrics[tool_name]
    metrics["call_count"] += 1
    metrics["total_duration_ms"] += duration_ms
    if not success:
        metrics["error_count"] += 1
    if cache_hit:
        metrics["cache_hits"] += 1

    _log("info", "tool_call",
        tool=tool_name, user_id=user_id,
        duration_ms=round(duration_ms, 1), success=success,
        cache_hit=cache_hit, error=error)


def get_metrics_summary() -> Dict[str, Any]:
    """Get aggregated metrics for all tools."""
    summary = {}
    for tool_name, m in _tool_metrics.items():
        avg_ms = m["total_duration_ms"] / m["call_count"] if m["call_count"] > 0 else 0
        error_rate = m["error_count"] / m["call_count"] if m["call_count"] > 0 else 0
        cache_rate = m["cache_hits"] / m["call_count"] if m["call_count"] > 0 else 0
        summary[tool_name] = {
            "calls": m["call_count"],
            "errors": m["error_count"],
            "error_rate": round(error_rate, 3),
            "avg_duration_ms": round(avg_ms, 1),
            "cache_hit_rate": round(cache_rate, 3),
        }
    return summary


# --- Middleware Wrapper ---

def with_middleware(
    tool_name: str,
    tool_fn: Callable,
    params: Dict,
    user_id: str = "anonymous",
) -> Dict[str, Any]:
    """
    Execute a tool call with all middleware applied:
    1. Input validation
    2. Rate limiting
    3. Cache check
    4. Execute tool
    5. Cache result
    6. Log metrics
    """
    start = time.time()

    # 1. Validate params
    validation_error = validate_params(tool_name, params)
    if validation_error:
        log_tool_call(tool_name, params, None, 0, user_id, success=False, error="validation")
        return validation_error

    # 2. Rate limit check
    rate_error = check_rate_limit(tool_name, user_id)
    if rate_error:
        _tool_metrics[tool_name]["rate_limits"] += 1
        log_tool_call(tool_name, params, None, 0, user_id, success=False, error="rate_limited")
        return rate_error

    # 3. Check cache
    cached = get_cached(tool_name, params)
    if cached is not None:
        duration = (time.time() - start) * 1000
        log_tool_call(tool_name, params, cached, duration, user_id, cache_hit=True)
        return cached

    # 4. Execute tool
    try:
        result = tool_fn(**params)
        duration = (time.time() - start) * 1000

        # 5. Cache result
        set_cached(tool_name, params, result)

        # 6. Log metrics
        log_tool_call(tool_name, params, result, duration, user_id)

        return result
    except Exception as e:
        duration = (time.time() - start) * 1000
        log_tool_call(tool_name, params, None, duration, user_id, success=False, error=str(e))
        _log("error", "tool_execution_error", tool=tool_name, error=str(e))
        return {
            "error": "tool_execution_error",
            "message": f"Error executing {tool_name}: {str(e)}",
        }
