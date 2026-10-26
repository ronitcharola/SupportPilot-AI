"""
Celery application shared by the worker container and background tasks.

The knowledge-base ingestion task lives in `app.tasks.knowledge_tasks` and is
declared via `include` so `celery -A app.tasks.celery_app:celery_app worker`
discovers it. Ingestion runs inline by default; set
`KNOWLEDGE_INGESTION_MODE=celery` (as docker-compose does) to use the worker.
"""
from celery import Celery

from app.config import settings

celery_app = Celery(
    "supportpilot",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    include=["app.tasks.knowledge_tasks"],
)
