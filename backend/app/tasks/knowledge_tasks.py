"""Celery ingestion task for knowledge documents.

The worker creates its own async engine (NullPool) because Celery runs tasks on a
fresh event loop per invocation. When `KNOWLEDGE_INGESTION_MODE=inline` (the
local/demo default), the API calls `ingest_document` directly instead.
"""
import asyncio
import logging

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.services.knowledge_service import ingest_document
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _ingest_in_new_engine(document_id: str, workspace_id: str) -> str:
    connect_args = {}
    if "sqlite" in settings.DATABASE_URL:
        connect_args["check_same_thread"] = False

    engine = create_async_engine(
        settings.DATABASE_URL,
        poolclass=NullPool,
        connect_args=connect_args,
        future=True,
    )
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            document = await ingest_document(session, workspace_id, document_id)
            return document.status
    finally:
        await engine.dispose()


@celery_app.task(bind=True, name="knowledge.ingest_document", max_retries=3)
def ingest_document_task(self, document_id: str, workspace_id: str) -> dict:
    try:
        final_status = asyncio.run(_ingest_in_new_engine(document_id, workspace_id))
    except Exception as exc:
        logger.exception("Celery ingestion failed for document %s", document_id)
        raise self.retry(exc=exc, countdown=min(60, 5 * (self.request.retries + 1)))

    return {"document_id": document_id, "workspace_id": workspace_id, "status": final_status}


def dispatch_ingestion(document_id: str, workspace_id: str) -> bool:
    """Queues ingestion when Celery mode is enabled. Returns False to index inline."""
    if (settings.KNOWLEDGE_INGESTION_MODE or "").strip().lower() != "celery":
        return False
    try:
        ingest_document_task.delay(document_id, workspace_id)
        return True
    except Exception:
        logger.warning(
            "Could not enqueue ingestion for document %s; falling back to inline indexing.",
            document_id,
            exc_info=True,
        )
        return False
