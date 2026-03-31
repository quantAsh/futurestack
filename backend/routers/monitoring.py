from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime, timedelta
from prometheus_client import Counter, Gauge
from backend.database import get_db
from backend import models
from pydantic import BaseModel

router = APIRouter()

# Custom Business Metrics
BOOKING_COUNT = Counter(
    "nomadnest_bookings_total", 
    "Total number of bookings created",
    ["status"]
)
ACTIVE_USERS = Gauge(
    "nomadnest_active_users",
    "Estimated number of active users in the last 24h"
)
SIGNUP_COUNT = Counter(
    "nomadnest_signups_total",
    "Total number of new user registrations"
)


class HealthDashboard(BaseModel):
    status: str
    uptime_seconds: float
    total_bookings: int
    active_users: int
    system_load: List[float]
    ai_status: str

@router.get("/dashboard", response_model=HealthDashboard)
def get_health_dashboard(db: Session = Depends(get_db)):
    """Get aggregated health and performance metrics for the dashboard."""
    import os
    
    # Update active users gauge (last 24h)
    cutoff = datetime.utcnow() - timedelta(days=1)
    active_count = db.query(models.User).filter(models.User.created_at >= cutoff).count()
    ACTIVE_USERS.set(active_count)
    
    # Get total bookings
    total_bookings = db.query(models.Booking).count()
    
    # Placeholder for uptime (in production, use a persistent counter)
    uptime = 3600.0 
    
    # System load
    try:
        load = list(os.getloadavg())
    except:
        load = [0.0, 0.0, 0.0]
        
    return {
        "status": "healthy",
        "uptime_seconds": uptime,
        "total_bookings": total_bookings,
        "active_users": active_count,
        "system_load": load,
    }


class AIUsageStats(BaseModel):
    total_tokens: int
    total_cost_usd: float
    model_breakdown: List[dict]


class AIErrorStats(BaseModel):
    total_errors: int
    error_rate: float
    recent_errors: List[dict]


@router.get("/metrics", response_model=AIUsageStats)
def get_ai_metrics(days: int = 30, db: Session = Depends(get_db)):
    """Get aggregated AI usage statistics."""
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    # Base query
    query = db.query(models.AIMetric).filter(models.AIMetric.timestamp >= cutoff_date)

    # Totals
    total_requests = query.filter(models.AIMetric.metric_type == "completion").count()
    total_tokens = query.with_entities(func.sum(models.AIMetric.total_tokens)).scalar() or 0
    total_cost_usd = (
        query.with_entities(func.sum(models.AIMetric.estimated_cost_usd)).scalar() or 0.0
    )

    # Model breakdown
    breakdown_query = (
        db.query(
            models.AIMetric.model,
            func.count(models.AIMetric.id).label("count"),
            func.sum(models.AIMetric.estimated_cost_usd).label("cost"),
        )
        .filter(models.AIMetric.timestamp >= cutoff_date, models.AIMetric.metric_type == "completion")
        .group_by(models.AIMetric.model)
        .all()
    )

    model_breakdown = [
        {"model": b.model, "requests": b.count, "cost_usd": b.cost or 0.0}
        for b in breakdown_query
    ]

    return {
        "total_requests": total_requests,
        "total_tokens": int(total_tokens),
        "total_cost_usd": total_cost_usd,
        "model_breakdown": model_breakdown,
    }


@router.get("/errors", response_model=AIErrorStats)
def get_ai_errors(days: int = 7, db: Session = Depends(get_db)):
    """Get recent AI errors."""
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    total_ops = db.query(models.AIMetric).filter(models.AIMetric.timestamp >= cutoff_date).count()
    total_errors = (
        db.query(models.AIMetric)
        .filter(models.AIMetric.timestamp >= cutoff_date, models.AIMetric.metric_type == "error")
        .count()
    )

    error_rate = (total_errors / total_ops) * 100 if total_ops > 0 else 0

    recent_errors = (
        db.query(models.AIMetric)
        .filter(models.AIMetric.timestamp >= cutoff_date, models.AIMetric.metric_type == "error")
        .order_by(models.AIMetric.timestamp.desc())
        .limit(10)
        .all()
    )

    return {
        "total_errors": total_errors,
        "error_rate": error_rate,
        "recent_errors": [
            {"timestamp": e.timestamp, "model": e.model, "error": e.error_message}
            for e in recent_errors
        ],
    }


class AgentStepResponse(BaseModel):
    step: int
    action: str
    selector: Optional[str]
    reasoning: Optional[str]
    success: bool
    error: Optional[str]
    has_screenshot: bool
    timestamp: datetime


@router.get("/jobs/{job_id}/steps", response_model=List[AgentStepResponse])
def get_agent_steps(job_id: str, db: Session = Depends(get_db)):
    """Fetch the detailed thought log for a specific agent job."""
    steps = (
        db.query(models.AgentStep)
        .filter(models.AgentStep.job_id == job_id)
        .order_by(models.AgentStep.step_index)
        .all()
    )
    return [
        {
            "step": s.step_index,
            "action": s.action,
            "selector": s.selector,
            "reasoning": s.reasoning,
            "success": s.success,
            "error": s.error_message,
            "has_screenshot": bool(s.screenshot_path),
            "timestamp": s.created_at,
        }
        for s in steps
    ]


# --- PHASE 15: SLO Monitoring ---

from backend.services.slo_service import get_slo_service, SLOStatus


class SLOStatusResponse(BaseModel):
    name: str
    target: float
    current: float
    is_breached: bool
    error_budget_remaining: float
    window_seconds: int
    request_count: int
    error_count: int
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float


@router.get("/slos", response_model=List[SLOStatusResponse])
def get_slo_statuses():
    """Get current status for all defined SLOs."""
    slo_service = get_slo_service()
    statuses = slo_service.get_all_slo_statuses()
    return [
        SLOStatusResponse(
            name=s.name,
            target=s.target,
            current=round(s.current, 4) if s.current < 10 else round(s.current, 1),
            is_breached=s.is_breached,
            error_budget_remaining=round(s.error_budget_remaining, 4),
            window_seconds=s.window_seconds,
            request_count=s.request_count,
            error_count=s.error_count,
            p50_latency_ms=round(s.p50_latency_ms, 2),
            p95_latency_ms=round(s.p95_latency_ms, 2),
            p99_latency_ms=round(s.p99_latency_ms, 2),
        )
        for s in statuses if s
    ]


@router.get("/error-budget")
def get_error_budget():
    """Get error budget summary for all SLOs."""
    slo_service = get_slo_service()
    return slo_service.get_error_budget_summary()
