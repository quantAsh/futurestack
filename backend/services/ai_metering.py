"""
AI Usage Metering Service - Tracks token usage and costs.
"""
import time
from uuid import uuid4
from typing import Optional
from sqlalchemy.orm import Session

from backend import models
from backend.database import SessionLocal

# Cost per 1K tokens in USD cents (as of 2024)
COST_PER_1K_TOKENS = {
    "gpt-4o": {"prompt": 0.25, "completion": 1.0},  # $0.0025 / $0.01
    "gpt-4o-mini": {"prompt": 0.015, "completion": 0.06},
    "gpt-4-turbo": {"prompt": 1.0, "completion": 3.0},
    "gpt-3.5-turbo": {"prompt": 0.05, "completion": 0.15},
    "gemini-pro": {"prompt": 0.0, "completion": 0.0},  # Free tier
    "gemini-1.5-pro": {"prompt": 0.125, "completion": 0.375},
    "claude-3-opus": {"prompt": 1.5, "completion": 7.5},
    "claude-3-sonnet": {"prompt": 0.3, "completion": 1.5},
    "claude-3-haiku": {"prompt": 0.025, "completion": 0.125},
}


def calculate_cost_cents(
    model: str, prompt_tokens: int, completion_tokens: int
) -> int:
    """Calculate cost in cents for a given model and token counts."""
    costs = COST_PER_1K_TOKENS.get(model, {"prompt": 0.1, "completion": 0.3})
    prompt_cost = (prompt_tokens / 1000) * costs["prompt"]
    completion_cost = (completion_tokens / 1000) * costs["completion"]
    return int((prompt_cost + completion_cost) * 100)  # Convert to cents


def log_ai_usage(
    endpoint: str,
    model: str,
    provider: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: int,
    user_id: Optional[str] = None,
    success: bool = True,
    error_message: Optional[str] = None,
    db: Optional[Session] = None,
) -> str:
    """
    Log an AI API usage record.
    
    Args:
        endpoint: The API endpoint that made the request (e.g., "concierge")
        model: The AI model used (e.g., "gpt-4o")
        provider: The AI provider (e.g., "openai")
        prompt_tokens: Number of tokens in the prompt
        completion_tokens: Number of tokens in the completion
        latency_ms: Request latency in milliseconds
        user_id: Optional user ID who made the request
        success: Whether the request succeeded
        error_message: Error message if failed
        db: Database session (creates one if not provided)
    
    Returns:
        The ID of the created usage record
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    
    try:
        total_tokens = prompt_tokens + completion_tokens
        cost_cents = calculate_cost_cents(model, prompt_tokens, completion_tokens)
        
        usage = models.AIUsageMetrics(
            id=str(uuid4()),
            user_id=user_id,
            endpoint=endpoint,
            model=model,
            provider=provider,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_cents=cost_cents,
            latency_ms=latency_ms,
            success=success,
            error_message=error_message,
        )
        
        db.add(usage)
        db.commit()
        
        return usage.id
    
    finally:
        if close_db:
            db.close()


def get_user_usage_summary(user_id: str, db: Session) -> dict:
    """Get usage summary for a user."""
    from sqlalchemy import func
    
    result = db.query(
        func.count(models.AIUsageMetrics.id).label("request_count"),
        func.sum(models.AIUsageMetrics.total_tokens).label("total_tokens"),
        func.sum(models.AIUsageMetrics.cost_cents).label("total_cost_cents"),
    ).filter(
        models.AIUsageMetrics.user_id == user_id
    ).first()
    
    return {
        "user_id": user_id,
        "request_count": result.request_count or 0,
        "total_tokens": result.total_tokens or 0,
        "total_cost_usd": (result.total_cost_cents or 0) / 100,
    }


def get_daily_usage_summary(db: Session) -> list:
    """Get daily usage aggregates for the past 30 days."""
    from sqlalchemy import func, cast, Date
    from datetime import datetime, timedelta
    
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    results = db.query(
        cast(models.AIUsageMetrics.created_at, Date).label("date"),
        func.count(models.AIUsageMetrics.id).label("request_count"),
        func.sum(models.AIUsageMetrics.total_tokens).label("total_tokens"),
        func.sum(models.AIUsageMetrics.cost_cents).label("total_cost_cents"),
    ).filter(
        models.AIUsageMetrics.created_at >= thirty_days_ago
    ).group_by(
        cast(models.AIUsageMetrics.created_at, Date)
    ).order_by(
        cast(models.AIUsageMetrics.created_at, Date).desc()
    ).all()
    
    return [
        {
            "date": str(r.date),
            "request_count": r.request_count,
            "total_tokens": r.total_tokens or 0,
            "total_cost_usd": (r.total_cost_cents or 0) / 100,
        }
        for r in results
    ]


class AIUsageTimer:
    """Context manager for timing AI requests."""
    
    def __init__(self):
        self.start_time = None
        self.latency_ms = 0
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.latency_ms = int((time.time() - self.start_time) * 1000)
        return False
