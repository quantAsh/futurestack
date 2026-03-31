"""
AI Response Caching Service.
Caches frequent AI queries to reduce LLM costs and latency.
Uses Redis when available, falls back to SQLite/DB for persistence.
"""
import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional
import structlog

logger = structlog.get_logger("nomadnest.ai_cache")

# Cache TTL settings
DEFAULT_TTL = 3600  # 1 hour for AI responses
FAQ_TTL = 86400  # 24 hours for FAQ-like responses

# Simple query patterns that are safe to cache
CACHEABLE_PATTERNS = [
    "what is",
    "how do i",
    "tell me about",
    "explain",
    "where can i",
    "recommend",
    "suggest",
    "what are the",
    "list",
    "show me",
]

# Queries that should NOT be cached (dynamic/personal)
NON_CACHEABLE_PATTERNS = [
    "my booking",
    "my reservation",
    "my account",
    "cancel",
    "refund",
    "payment",
    "price for",
    "available on",
    "book now",
]


def _get_redis():
    """Lazy Redis import — returns None if unavailable."""
    try:
        from backend.utils.cache import redis_client
        return redis_client
    except Exception:
        return None


def compute_query_hash(query: str) -> str:
    """
    Compute a normalized hash of the query for cache key.
    Normalizes by lowercasing and removing extra whitespace.
    """
    normalized = " ".join(query.lower().strip().split())
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def is_cacheable_query(query: str) -> bool:
    """
    Determine if a query should be cached.
    Returns False for personal/dynamic queries, True for general knowledge queries.
    """
    query_lower = query.lower()
    
    # Check for non-cacheable patterns first
    for pattern in NON_CACHEABLE_PATTERNS:
        if pattern in query_lower:
            return False
    
    # Check if it matches cacheable patterns
    for pattern in CACHEABLE_PATTERNS:
        if query_lower.startswith(pattern) or pattern in query_lower:
            return True
    
    # Default: don't cache if unsure
    return False


# ─── DB Fallback ──────────────────────────────────────────────────────────

def _db_get_cached(query_hash: str) -> Optional[dict]:
    """Get cached response from SQLite/DB."""
    try:
        from backend.database import get_db_context
        from backend.models import AICacheEntry
        
        with get_db_context() as db:
            entry = db.query(AICacheEntry).filter(
                AICacheEntry.query_hash == query_hash,
                AICacheEntry.expires_at > datetime.utcnow(),
            ).first()
            
            if entry:
                return json.loads(entry.response_json)
    except Exception as e:
        logger.warning("db_cache_read_error", error=str(e))
    return None


def _db_set_cached(query_hash: str, data: dict, query: str, ttl: int) -> bool:
    """Store cached response in SQLite/DB."""
    try:
        from backend.database import get_db_context
        from backend.models import AICacheEntry
        
        with get_db_context() as db:
            # Upsert: delete old entry if exists, insert new
            db.query(AICacheEntry).filter(
                AICacheEntry.query_hash == query_hash
            ).delete()
            
            entry = AICacheEntry(
                query_hash=query_hash,
                query_preview=query[:100],
                response_json=json.dumps(data),
                expires_at=datetime.utcnow() + timedelta(seconds=ttl),
            )
            db.add(entry)
            db.commit()
        return True
    except Exception as e:
        logger.warning("db_cache_write_error", error=str(e))
        return False


def _db_cleanup_expired():
    """Remove expired cache entries from DB."""
    try:
        from backend.database import get_db_context
        from backend.models import AICacheEntry
        
        with get_db_context() as db:
            count = db.query(AICacheEntry).filter(
                AICacheEntry.expires_at <= datetime.utcnow()
            ).delete()
            if count > 0:
                db.commit()
                logger.debug("db_cache_cleanup", expired=count)
    except Exception as e:
        logger.warning("db_cache_cleanup_error", error=str(e))


# ─── Public API (async — Redis first, DB fallback) ───────────────────────

async def get_cached_response(query: str) -> Optional[dict]:
    """
    Check if we have a cached response for this query.
    Returns cached response dict or None.
    """
    if not is_cacheable_query(query):
        return None
    
    query_hash = compute_query_hash(query)
    cache_key = f"ai_response:{query_hash}"
    
    # Try Redis first
    redis = _get_redis()
    if redis:
        try:
            cached_data = await redis.get(cache_key)
            if cached_data:
                logger.info("ai_cache_hit", query_preview=query[:50], backend="redis")
                return json.loads(cached_data)
        except Exception as e:
            logger.warning("ai_cache_redis_read_error", error=str(e))
    
    # Fall back to DB
    result = _db_get_cached(query_hash)
    if result:
        logger.info("ai_cache_hit", query_preview=query[:50], backend="db")
        return result
    
    return None


async def cache_response(query: str, response: str, tool_calls: list = None, ttl: int = None) -> bool:
    """
    Cache an AI response for a query.
    Only caches if the query is cacheable and there were no tool calls.
    """
    # Don't cache if there were tool calls (dynamic actions)
    if tool_calls:
        return False
    
    if not is_cacheable_query(query):
        return False
    
    query_hash = compute_query_hash(query)
    cache_key = f"ai_response:{query_hash}"
    cache_ttl = ttl or DEFAULT_TTL
    
    cache_data = {
        "response": response,
        "cached": True,
        "tool_calls": [],
    }
    
    # Try Redis first
    redis = _get_redis()
    if redis:
        try:
            await redis.setex(cache_key, cache_ttl, json.dumps(cache_data))
            logger.info("ai_cache_stored", query_preview=query[:50], backend="redis", ttl=cache_ttl)
            return True
        except Exception as e:
            logger.warning("ai_cache_redis_write_error", error=str(e))
    
    # Fall back to DB
    stored = _db_set_cached(query_hash, cache_data, query, cache_ttl)
    if stored:
        logger.info("ai_cache_stored", query_preview=query[:50], backend="db", ttl=cache_ttl)
    return stored


async def invalidate_ai_cache():
    """Invalidate all AI response cache entries."""
    # Redis
    redis = _get_redis()
    if redis:
        try:
            keys = await redis.keys("ai_response:*")
            if keys:
                await redis.delete(*keys)
                logger.info("ai_cache_invalidated", count=len(keys), backend="redis")
        except Exception as e:
            logger.warning("ai_cache_invalidation_error", error=str(e))
    
    # DB: delete all
    try:
        from backend.database import get_db_context
        from backend.models import AICacheEntry
        
        with get_db_context() as db:
            count = db.query(AICacheEntry).delete()
            db.commit()
            if count > 0:
                logger.info("ai_cache_invalidated", count=count, backend="db")
    except Exception as e:
        logger.warning("db_cache_invalidation_error", error=str(e))


async def get_cache_stats() -> dict:
    """Get AI cache statistics."""
    stats = {"enabled": True, "redis_entries": 0, "db_entries": 0}
    
    redis = _get_redis()
    if redis:
        try:
            keys = await redis.keys("ai_response:*")
            stats["redis_entries"] = len(keys)
        except Exception:
            pass
    
    try:
        from backend.database import get_db_context
        from backend.models import AICacheEntry
        
        with get_db_context() as db:
            stats["db_entries"] = db.query(AICacheEntry).filter(
                AICacheEntry.expires_at > datetime.utcnow()
            ).count()
    except Exception:
        pass
    
    stats["total_entries"] = stats["redis_entries"] + stats["db_entries"]
    return stats
