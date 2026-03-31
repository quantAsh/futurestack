from celery import shared_task
from backend.scripts.ingest_csv import ingest_csv
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

@shared_task(name="ingest_csv_task")
def ingest_csv_task():
    """
    Celery task to run the CSV ingestion process.
    """
    logger.info("Starting scheduled CSV ingestion...")
    try:
        ingest_csv()
        logger.info("CSV ingestion completed successfully.")
        return "Ingestion successful"
    except Exception as e:
        logger.error(f"CSV ingestion failed: {e}")
        raise e
