"""
AI Usage Service - Track token usage and costs per request.
"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
import structlog
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend import models
from backend.database import get_db_session

logger = structlog.get_logger("nomadnest.ai_usage")

# Model pricing (per 1K tokens, in USD)
MODEL_PRICING = {
    "gemini/gemini-2.0-flash": {"input": 0.0001, "output": 0.0004},
    "gemini/gemini-1.5-pro": {"input": 0.00125, "output": 0.005},
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "claude-3-sonnet": {"input": 0.003, "output": 0.015},
    "default": {"input": 0.001, "output": 0.002},
}


def calculate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate estimated cost for a request."""
    pricing = MODEL_PRICING.get(model, MODEL_PRICING["default"])
    input_cost = (prompt_tokens / 1000) * pricing["input"]
    output_cost = (completion_tokens / 1000) * pricing["output"]
    return round(input_cost + output_cost, 6)


def log_ai_usage(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    duration_ms: float = None,
    tool_calls: int = 0,
    cached: bool = False,
    user_id: str = None,
    session_id: str = None,
) -> Optional[str]:
    """
    Log AI usage to database.
    Returns the usage record ID.
    """
    try:
        with get_db_session() as db:
            total_tokens = prompt_tokens + completion_tokens
            cost_usd = calculate_cost(model, prompt_tokens, completion_tokens)

            usage = models.AIUsage(
                id=str(uuid.uuid4()),
                user_id=user_id,
                session_id=session_id,
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                cost_usd=cost_usd,
                duration_ms=duration_ms,
                tool_calls=tool_calls,
                cached=cached,
            )
            db.add(usage)
            db.commit()

            logger.info(
                "ai_usage_logged",
                model=model,
                tokens=total_tokens,
                cost_usd=cost_usd,
                cached=cached,
            )
            return usage.id

    except Exception as e:
        logger.warning("ai_usage_log_error", error=str(e))
        return None


def get_usage_stats(user_id: str = None, days: int = 30) -> dict:
    """Get AI usage statistics for dashboard."""
    try:
        with get_db_session() as db:
            since = datetime.now(timezone.utc) - timedelta(days=days)

            query = db.query(
                func.count(models.AIUsage.id).label("total_requests"),
                func.sum(models.AIUsage.total_tokens).label("total_tokens"),
                func.sum(models.AIUsage.cost_usd).label("total_cost"),
                func.avg(models.AIUsage.duration_ms).label("avg_latency"),
            ).filter(models.AIUsage.created_at >= since)

            if user_id:
                query = query.filter(models.AIUsage.user_id == user_id)

            result = query.first()

            # Model breakdown
            model_stats = db.query(
                models.AIUsage.model,
                func.count(models.AIUsage.id).label("requests"),
                func.sum(models.AIUsage.cost_usd).label("cost"),
            ).filter(
                models.AIUsage.created_at >= since
            ).group_by(models.AIUsage.model).all()

            return {
                "total_requests": result.total_requests or 0,
                "total_tokens": result.total_tokens or 0,
                "total_cost_usd": round(result.total_cost or 0, 4),
                "avg_latency_ms": round(result.avg_latency or 0, 2),
                "model_breakdown": [
                    {"model": m.model, "requests": m.requests, "cost_usd": round(m.cost or 0, 4)}
                    for m in model_stats
                ],
                "period_days": days,
            }

    except Exception as e:
        logger.warning("ai_usage_stats_error", error=str(e))
        return {
            "total_requests": 0,
            "total_tokens": 0,
            "total_cost_usd": 0,
            "avg_latency_ms": 0,
            "model_breakdown": [],
            "period_days": days,
        }
