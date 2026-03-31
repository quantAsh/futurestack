import asyncio
import json
import structlog

from backend.database import SessionLocal
from backend.models import AgentJob
from backend.tasks.celery_app import celery_app
import sys
import os

try:
    _project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)
    from core.agent_engine import AgentWorker
except ImportError:
    AgentWorker = None  # Stub: core agent engine not available in FutureStack fork

logger = structlog.get_logger("nomadnest.agent_jobs")


@celery_app.task(
    name="agent_jobs.run",
    bind=True,
    autoretry_for=(ConnectionError, TimeoutError, OSError),
    retry_backoff=True,          # Exponential backoff: 1s, 2s, 4s...
    retry_backoff_max=60,        # Cap at 60 seconds
    retry_kwargs={"max_retries": 2},
    acks_late=True,              # Re-deliver if worker crashes mid-task
    reject_on_worker_lost=True,  # Reject instead of ack if worker dies
)
def run_agent_job(self, job_id: str, url: str, goal: str) -> dict:
    db = SessionLocal()
    try:
        job = db.query(AgentJob).filter(AgentJob.id == job_id).first()
        if job:
            job.status = "running"
            db.commit()

        worker = AgentWorker()
        asyncio.run(worker.execute_task(url=url, goal=goal, job_id=job_id, db=db))

        job = db.query(AgentJob).filter(AgentJob.id == job_id).first()
        if job:
            job.status = "completed"
            job.result = json.dumps({"success": True, "message": "Task completed"})
            db.commit()
    except Exception as exc:
        logger.exception("Agent job %s failed", job_id)
        job = db.query(AgentJob).filter(AgentJob.id == job_id).first()
        if job:
            job.status = "failed"
            job.error = str(exc)
            db.commit()
        raise
    finally:
        db.close()

    return {"job_id": job_id, "status": "completed"}
