"""
Document endpoints – upload (single + bulk) and retrieval.

File uploads are saved to disk and immediately dispatched to
the Celery queue for background processing.
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.config import get_settings
from app.models import Document, ProcessingStatus
from app.schemas.document import (
    BulkUploadResponse,
    DocumentRead,
    DocumentUploadResponse,
)
from app.services.ingestion.pipeline import compute_file_hash
from app.workers.tasks import process_document_task

router = APIRouter()
settings = get_settings()


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=202,
    summary="Upload a single document",
)
async def upload_document(
    file: UploadFile = File(...),
    project_id: uuid.UUID | None = None,
    client_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_session),
):
    """
    Accept a file upload, save to disk, and queue for processing.

    Returns immediately with a 202 Accepted – the actual processing
    happens asynchronously in a Celery worker.
    """
    # Validate extension
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in settings.SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type: {suffix}."
                f" Supported: {settings.SUPPORTED_EXTENSIONS}"
            ),
        )

    # Save to watch directory
    dest = settings.watch_path / (file.filename or "unnamed")
    dest.parent.mkdir(parents=True, exist_ok=True)

    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Check for duplicates
    file_hash = compute_file_hash(dest)
    existing = await db.execute(
        select(Document).where(Document.file_hash == file_hash)
    )
    if existing.scalar_one_or_none():
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=409, detail="Duplicate document detected.")

    # Create preliminary record
    doc = Document(
        filename=dest.name,
        file_path=str(dest),
        file_hash=file_hash,
        file_size_bytes=dest.stat().st_size,
        mime_type=file.content_type or "application/octet-stream",
        processing_status=ProcessingStatus.PENDING,
        project_id=str(project_id) if project_id else None,
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)

    # Dispatch Celery task
    process_document_task.delay(
        file_path=str(dest),
        project_id=str(project_id) if project_id else None,
        client_id=str(client_id) if client_id else None,
    )

    return DocumentUploadResponse(
        document_id=doc.id,
        filename=doc.filename,
    )


@router.post(
    "/upload/bulk",
    response_model=BulkUploadResponse,
    status_code=202,
    summary="Upload multiple documents",
)
async def bulk_upload(
    files: list[UploadFile] = File(...),
    project_id: uuid.UUID | None = None,
    client_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_session),
):
    """
    Accept multiple file uploads. Each file is saved and queued
    independently – partial failures don't block other files.
    """
    responses: list[DocumentUploadResponse] = []
    skipped = 0

    for file in files:
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in settings.SUPPORTED_EXTENSIONS:
            skipped += 1
            continue

        fallback_name = f"unnamed_{uuid.uuid4().hex[:8]}"
        dest = settings.watch_path / (file.filename or fallback_name)
        with open(dest, "wb") as f:
            shutil.copyfileobj(file.file, f)

        file_hash = compute_file_hash(dest)
        existing = await db.execute(
            select(Document).where(Document.file_hash == file_hash)
        )
        if existing.scalar_one_or_none():
            dest.unlink(missing_ok=True)
            skipped += 1
            continue

        doc = Document(
            filename=dest.name,
            file_path=str(dest),
            file_hash=file_hash,
            file_size_bytes=dest.stat().st_size,
            mime_type=file.content_type or "application/octet-stream",
            processing_status=ProcessingStatus.PENDING,
            project_id=str(project_id) if project_id else None,
        )
        db.add(doc)
        await db.flush()
        await db.refresh(doc)

        process_document_task.delay(
            file_path=str(dest),
            project_id=str(project_id) if project_id else None,
            client_id=str(client_id) if client_id else None,
        )

        responses.append(
            DocumentUploadResponse(
                document_id=doc.id,
                filename=doc.filename,
            )
        )

    return BulkUploadResponse(
        total_queued=len(responses),
        documents=responses,
        skipped_duplicates=skipped,
    )


@router.get("/", response_model=list[DocumentRead], summary="List documents")
async def list_documents(
    project_id: uuid.UUID | None = None,
    status: ProcessingStatus | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
):
    query = select(Document)
    if project_id:
        query = query.where(Document.project_id == project_id)
    if status:
        query = query.where(Document.processing_status == status)

    query = query.offset(skip).limit(limit).order_by(Document.created_at.desc())
    result = await db.execute(query)
    return [DocumentRead.model_validate(d) for d in result.scalars().all()]


@router.get("/{document_id}", response_model=DocumentRead, summary="Get a document")
async def get_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
):
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentRead.model_validate(doc)
