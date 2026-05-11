"""
Celery tasks – the bridge between async events and the ingestion pipeline.

Each task creates its own async event loop and DB session, keeping the
Celery worker fully decoupled from the FastAPI process.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """
    Helper to run an async coroutine inside a synchronous Celery task.

    Creates a fresh event loop per invocation to avoid conflicts with
    any existing loop in the worker process.
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _ingest_file(
    file_path: str,
    project_id: str | None,
    client_id: str | None,
) -> dict:
    """Async helper that wires up a session and runs the pipeline."""
    from app.db import async_session_factory
    from app.services.ingestion.pipeline import IngestionPipeline

    async with async_session_factory() as session:
        pipeline = IngestionPipeline(session)
        doc = await pipeline.ingest(
            file_path=Path(file_path),
            project_id=project_id,
            client_id=client_id,
        )
        return {
            "document_id": str(doc.id),
            "filename": doc.filename,
            "status": doc.processing_status.value,
            "document_type": doc.document_type.value,
            "processing_duration_ms": doc.processing_duration_ms,
        }


@celery_app.task(
    name="app.workers.tasks.process_document_task",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def process_document_task(
    self,
    file_path: str,
    project_id: str | None = None,
    client_id: str | None = None,
) -> dict:
    """
    Celery task: process a single document through the ingestion pipeline.

    Retries up to 3 times on transient failures (network, DB timeouts).
    """
    logger.info("Processing document: %s (task_id=%s)", file_path, self.request.id)

    try:
        return _run_async(_ingest_file(file_path, project_id, client_id))
    except FileNotFoundError:
        logger.error("File not found: %s – no retry.", file_path)
        return {"error": f"File not found: {file_path}"}
    except Exception as exc:
        logger.exception("Task failed for %s, retrying...", file_path)
        raise self.retry(exc=exc) from exc


async def _run_stale_detection() -> dict:
    """Async helper for stale lead detection."""
    from app.db import async_session_factory
    from app.services.intelligence.stale_detector import StaleLeadDetector

    async with async_session_factory() as session:
        detector = StaleLeadDetector(session)
        report = await detector.run(auto_flag=True)
        return {
            "threshold_days": report.threshold_days,
            "total_stale": report.total_stale,
            "generated_at": report.generated_at.isoformat(),
        }


@celery_app.task(name="app.workers.tasks.detect_stale_leads_task")
def detect_stale_leads_task() -> dict:
    """
    Scheduled task: scan for stale leads and auto-flag them.

    Runs daily via Celery Beat (configured in celery_app.py).
    """
    logger.info("Running scheduled stale-lead detection...")
    return _run_async(_run_stale_detection())


@celery_app.task(name="app.workers.tasks.bulk_index_task")
def bulk_index_task(
    directory_path: str,
    project_id: str | None = None,
    client_id: str | None = None,
) -> dict:
    """
    Celery task: scan a directory and dispatch individual document tasks.

    This is a fan-out pattern – one bulk task spawns N document tasks.
    """
    from app.services.indexing.engine import IndexingEngine

    engine = IndexingEngine()
    manifest = engine.scan_directory(Path(directory_path))
    task_ids = engine.dispatch_bulk_tasks(
        manifest,
        project_id=project_id,
        client_id=client_id,
    )

    return {
        "total_files": manifest.total_files,
        "unique_files": manifest.unique_files,
        "duplicates": manifest.duplicate_files,
        "unsupported": manifest.unsupported_files,
        "dispatched_tasks": len(task_ids),
        "task_ids": task_ids,
    }
