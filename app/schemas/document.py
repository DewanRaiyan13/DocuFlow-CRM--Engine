"""Document schemas for API serialization."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.document import DocumentType, ProcessingStatus


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    file_path: str
    file_hash: str
    file_size_bytes: int
    mime_type: str
    document_type: DocumentType
    processing_status: ProcessingStatus
    extracted_title: str | None
    extracted_date: datetime | None
    extracted_case_number: str | None
    page_count: int | None
    llm_metadata: dict | None
    processing_duration_ms: int | None
    error_message: str | None
    project_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class DocumentUploadResponse(BaseModel):
    document_id: uuid.UUID
    filename: str
    status: str = "queued"
    message: str = "Document queued for processing."


class BulkUploadResponse(BaseModel):
    total_queued: int
    documents: list[DocumentUploadResponse]
    skipped_duplicates: int = 0
