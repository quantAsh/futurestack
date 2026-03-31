"""
Stuck Job Reaper — Background task that recovers agent jobs
stuck in 'running' or 'queued' state past the global timeout.

Can be triggered by:
  - Celery Beat (periodic schedule)
  - FastAPI startup event (asyncio.create_task)
  - Manual admin endpoint (/api/v1/agent-jobs/recover-stuck)
"""
import asyncio
from datetime import datetime, timedelta
import structlog

from backend.database import SessionLocal
from backend.models import AgentJob

logger = structlog.get_logger("nomadnest.reaper")

# Jobs older than this are considered stuck
STUCK_THRESHOLD_MINUTES = 10

# How often the reaper runs (seconds)
REAPER_INTERVAL_SECONDS = 300  # 5 minutes


def reap_stuck_jobs(max_age_minutes: int = STUCK_THRESHOLD_MINUTES) -> int:
    """
    Synchronous reaper: find and fail stuck jobs.
    Returns count of recovered jobs.
    """
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(minutes=max_age_minutes)
        stuck_jobs = db.query(AgentJob).filter(
            AgentJob.status.in_(["running", "queued"]),
            AgentJob.updated_at < cutoff,
        ).all()

        count = 0
        for job in stuck_jobs:
            old_status = job.status
            job.status = "failed"
            job.error = (
                f"Auto-recovered: stuck in '{old_status}' for >{max_age_minutes} minutes. "
                f"Original task may have crashed or timed out."
            )
            count += 1
            logger.warning(
                "stuck_job_reaped",
                job_id=job.id,
                old_status=old_status,
                age_minutes=max_age_minutes,
            )

        if count > 0:
            db.commit()
            logger.info("reaper_cycle_complete", recovered=count)
        return count
    except Exception as e:
        logger.error("reaper_error", error=str(e))
        db.rollback()
        return 0
    finally:
        db.close()


async def reaper_loop():
    """
    Async background loop — call once at app startup.
    Runs every REAPER_INTERVAL_SECONDS and cleans up stuck jobs.
    """
    logger.info("stuck_job_reaper_started", interval_seconds=REAPER_INTERVAL_SECONDS)
    while True:
        try:
            await asyncio.sleep(REAPER_INTERVAL_SECONDS)
            count = reap_stuck_jobs()
            if count > 0:
                logger.info("reaper_recovered", count=count)
        except asyncio.CancelledError:
            logger.info("stuck_job_reaper_stopped")
            break
        except Exception as e:
            logger.error("reaper_loop_error", error=str(e))
            await asyncio.sleep(60)  # Back off on errors
