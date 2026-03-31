from celery import Celery

from backend.config import settings

broker_url = settings.REDIS_URL or "redis://localhost:6379/0"

celery_app = Celery(
    "nomadnest", 
    broker=broker_url, 
    backend=broker_url,
    include=["backend.tasks.data_tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
    timezone="UTC",
    enable_utc=True,
)

from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    "nightly-csv-ingestion": {
        "task": "ingest_csv_task",
        "schedule": crontab(hour=2, minute=0),  # Run at 2:00 AM UTC
    },
    "check-price-alerts": {
        "task": "check_price_alerts_task",
        "schedule": crontab(minute=0),  # Run every hour
    },
}


# Define the price alert task
@celery_app.task(name="check_price_alerts_task")
def check_price_alerts_task():
    """Check all active price alerts and send notifications for drops."""
    import asyncio
    from backend.database import SessionLocal
    from backend.services.price_alerts import price_alert_service
    
    db = SessionLocal()
    try:
        # Run the async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        notifications = loop.run_until_complete(
            price_alert_service.check_price_drops(db)
        )
        loop.close()
        
        return {
            "status": "success",
            "notifications_sent": len(notifications),
        }
    finally:
        db.close()

