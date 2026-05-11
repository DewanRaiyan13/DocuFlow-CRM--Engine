"""
Celery application configuration.

Separate from FastAPI so workers can import this module without
bootstrapping the full web application.
"""

from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "docuflow",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue="docuflow",
    task_routes={
        "app.workers.tasks.process_document_task": {"queue": "documents"},
        "app.workers.tasks.detect_stale_leads_task": {"queue": "intelligence"},
        "app.workers.tasks.bulk_index_task": {"queue": "indexing"},
    },
    beat_schedule={
        "detect-stale-leads-daily": {
            "task": "app.workers.tasks.detect_stale_leads_task",
            "schedule": crontab(hour=9, minute=0),  # Every day at 9 AM UTC
        },
    },
)

celery_app.autodiscover_tasks(["app.workers"])
