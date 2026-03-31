"""
Agent Jobs Router - Trigger AgentWorker tasks via API.
Connects the core.agent_engine to user-facing features.
Requires authentication — users can only access their own jobs.
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from uuid import uuid4
from datetime import datetime
import asyncio
import structlog
import json
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import AgentJob
from backend import models
from backend.utils import get_current_user
from backend.tasks.agent_jobs import run_agent_job

# Import the modular agent engine from project root
import sys
import os

try:
    _project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)
    from core.agent_engine import AgentWorker
except ImportError:
    AgentWorker = None

router = APIRouter()
logger = structlog.get_logger("nomadnest.agent_jobs")

# Per-user concurrency limit
_MAX_CONCURRENT_JOBS_PER_USER = 3


def _check_user_concurrency(user_id: str, db: Session) -> None:
    """Raise 429 if user has too many running/queued jobs."""
    active_count = db.query(AgentJob).filter(
        AgentJob.user_id == user_id,
        AgentJob.status.in_(["queued", "running"]),
    ).count()
    if active_count >= _MAX_CONCURRENT_JOBS_PER_USER:
        raise HTTPException(
            status_code=429,
            detail=f"Maximum {_MAX_CONCURRENT_JOBS_PER_USER} concurrent agent jobs allowed. "
                   f"Wait for existing jobs to complete.",
        )


class NegotiateRequest(BaseModel):
    external_url: str
    target_price: float
    listing_id: Optional[str] = None


class AvailabilityRequest(BaseModel):
    external_url: str
    check_in_date: Optional[str] = None
    check_out_date: Optional[str] = None


async def run_agent_task(job_id: str, url: str, goal: str):
    """Background task that runs the AgentWorker and updates DB status."""
    from backend.database import SessionLocal

    db = SessionLocal()
    try:
        job = db.query(AgentJob).filter(AgentJob.id == job_id).first()
        if job:
            job.status = "running"
            db.commit()

        worker = AgentWorker()
        await worker.execute_task(
            url=url,
            goal=goal,
            job_id=job_id,
            db=db,
            max_steps=10,
        )

        # Worker updates job status internally, but set completed as fallback
        job = db.query(AgentJob).filter(AgentJob.id == job_id).first()
        if job and job.status == "running":
            job.status = "completed"
            job.result = json.dumps({"success": True, "message": "Task completed"})
            db.commit()
    except Exception as e:
        logger.error("agent_job_failed", job_id=job_id, error=str(e), exc_info=True)
        job = db.query(AgentJob).filter(AgentJob.id == job_id).first()
        if job:
            job.status = "failed"
            job.error = str(e)
            db.commit()
    finally:
        db.close()


def enqueue_agent_job(
    job_id: str, url: str, goal: str, background_tasks: BackgroundTasks
) -> str:
    try:
        run_agent_job.delay(job_id, url, goal)
        return "celery"
    except Exception as exc:
        logger.warning("celery_enqueue_fallback", error=str(exc))
        background_tasks.add_task(run_agent_task, job_id, url, goal)
        return "background"


@router.post("/negotiate")
async def start_negotiation(
    request: NegotiateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Spawn an AI agent to negotiate on an external booking site.
    Returns a job_id to poll for status.
    """
    job_id = str(uuid4())
    goal = f"Navigate to the booking page and attempt to negotiate the price to ${request.target_price}. Look for contact forms, chat widgets, or special offer requests."

    # Enforce concurrency limit
    _check_user_concurrency(current_user.id, db)

    new_job = AgentJob(
        id=job_id,
        type="negotiate",
        url=request.external_url,
        goal=goal,
        status="queued",
        user_id=current_user.id,
    )
    db.add(new_job)
    db.commit()

    queue = enqueue_agent_job(job_id, request.external_url, goal, background_tasks)
    logger.info("negotiation_started", job_id=job_id, user_id=current_user.id)

    return {
        "job_id": job_id,
        "status": "queued",
        "queue": queue,
        "message": "Negotiation agent started. Poll /api/v1/agent-jobs/{job_id}/status for updates.",
    }


@router.post("/check-availability")
async def check_availability(
    request: AvailabilityRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Spawn an AI agent to verify availability on an external booking site.
    """
    job_id = str(uuid4())
    goal = f"Check if this property is available. Look for availability calendars, booking forms, or 'Book Now' buttons."

    if request.check_in_date:
        goal += f" Target dates: {request.check_in_date} to {request.check_out_date}."

    # Enforce concurrency limit
    _check_user_concurrency(current_user.id, db)

    new_job = AgentJob(
        id=job_id,
        type="availability",
        url=request.external_url,
        goal=goal,
        status="queued",
        user_id=current_user.id,
    )
    db.add(new_job)
    db.commit()

    queue = enqueue_agent_job(job_id, request.external_url, goal, background_tasks)

    return {
        "job_id": job_id,
        "status": "queued",
        "queue": queue,
        "message": "Availability check started.",
    }


@router.get("/{job_id}/status")
def get_job_status(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Get the status of an agent job (own jobs only)."""
    job = db.query(AgentJob).filter(
        AgentJob.id == job_id,
        AgentJob.user_id == current_user.id,
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "id": job.id,
        "type": job.type,
        "url": job.url,
        "goal": job.goal,
        "status": job.status,
        "result": json.loads(job.result) if job.result else None,
        "error": job.error,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


@router.get("/")
def list_jobs(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """List agent jobs for the authenticated user."""
    jobs = db.query(AgentJob).filter(
        AgentJob.user_id == current_user.id,
    ).order_by(AgentJob.created_at.desc()).all()
    return jobs


@router.post("/recover-stuck")
def recover_stuck_jobs(
    max_age_minutes: int = 10,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Admin endpoint: Recover jobs stuck in 'running' or 'queued' state
    for longer than max_age_minutes. Marks them as 'failed'.
    """
    from backend.utils import require_admin
    from datetime import timedelta
    
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    cutoff = datetime.utcnow() - timedelta(minutes=max_age_minutes)
    stuck_jobs = db.query(AgentJob).filter(
        AgentJob.status.in_(["running", "queued"]),
        AgentJob.updated_at < cutoff,
    ).all()
    
    recovered = []
    for job in stuck_jobs:
        job.status = "failed"
        job.error = f"Recovered: stuck in '{job.status}' for >{max_age_minutes} minutes"
        recovered.append(job.id)
    
    db.commit()
    logger.info("stuck_jobs_recovered", count=len(recovered), max_age_minutes=max_age_minutes)
    
    return {
        "recovered": len(recovered),
        "job_ids": recovered,
        "max_age_minutes": max_age_minutes,
    }
