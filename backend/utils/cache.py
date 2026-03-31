import json
from functools import wraps
from typing import Any, Callable, Optional
import redis.asyncio as redis
from backend.config import settings
import structlog

logger = structlog.get_logger("nomadnest.cache")

# Initialize Redis client
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)


def serialize_for_cache(data: Any) -> Any:
    """
    Recursively convert Pydantic models to dicts for JSON serialization.
    Handles nested structures like lists and dicts containing Pydantic models.
    """
    from pydantic import BaseModel
    
    if isinstance(data, BaseModel):
        return data.model_dump(mode='json')
    elif isinstance(data, dict):
        return {k: serialize_for_cache(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [serialize_for_cache(item) for item in data]
    return data

def cached(ttl: int = 300, prefix: str = "cache"):
    """
    Decorator to cache FastAPI endpoint responses in Redis.
    
    Args:
        ttl: Time-to-live in seconds (default 5 minutes)
        prefix: Prefix for the cache key
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Skip cache in development if needed, or if no redis_client
            if not redis_client:
                return await func(*args, **kwargs)

            # Generate cache key based on function name and arguments
            # We filter out specific arguments like 'db' or 'current_user' 
            # as they are dependencies and not part of the unique request state
            filterable_keys = ["db", "current_user", "session"]
            cache_kwargs = {k: v for k, v in kwargs.items() if k not in filterable_keys}
            
            key_parts = [prefix, func.__name__]
            if args:
                key_parts.append(str(args))
            if cache_kwargs:
                key_parts.append(str(sorted(cache_kwargs.items())))
            
            cache_key = ":".join(key_parts)

            try:
                # Check cache
                cached_data = await redis_client.get(cache_key)
                if cached_data:
                    logger.debug("cache_hit", key=cache_key)
                    return json.loads(cached_data)
            except Exception as e:
                logger.warning("cache_error", action="read", error=str(e))

            # Cache miss - execute function
            result = await func(*args, **kwargs)

            try:
                # Store in cache
                # Convert Pydantic models to JSON-serializable dicts
                serializable_result = serialize_for_cache(result)
                await redis_client.setex(
                    cache_key,
                    ttl,
                    json.dumps(serializable_result, default=str)
                )
                logger.debug("cache_miss", key=cache_key)
            except Exception as e:
                logger.warning("cache_error", action="write", error=str(e))

            return result
        return wrapper
    return decorator

async def invalidate_cache(pattern: str):
    """Invalidate all cache keys matching a pattern."""
    try:
        keys = await redis_client.keys(f"{pattern}*")
        if keys:
            await redis_client.delete(*keys)
            logger.info("cache_invalidated", pattern=pattern, count=len(keys))
    except Exception as e:
        logger.warning("cache_invalidation_error", pattern=pattern, error=str(e))
