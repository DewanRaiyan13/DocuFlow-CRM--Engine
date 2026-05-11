"""
Document model – individual file records created by the ingestion pipeline.

Each row captures both the raw file metadata (path, hash, size) and
the structured data extracted by the parsing + LLM enrichment stages.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    ForeignKey, String, Text, Integer, DateTime,
    Enum as SAEnum, BigInteger,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

import enum


class DocumentType(str, enum.Enum):
    PROPOSAL = "proposal"
    CONTRACT = "contract"
    INVOICE = "invoice"
    CASE_FILE = "case_file"
    CORRESPONDENCE = "correspondence"
    OTHER = "other"


class ProcessingStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Document(TimestampMixin, Base):
    __tablename__ = "documents"

    # ── File metadata ──────────────────────────────────────────────
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_hash: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True,
        comment="SHA-256 hash for deduplication",
    )
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)

    # ── Classification ─────────────────────────────────────────────
    document_type: Mapped[DocumentType] = mapped_column(
        SAEnum(DocumentType, name="document_type", create_constraint=True),
        default=DocumentType.OTHER,
        index=True,
    )
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        SAEnum(ProcessingStatus, name="processing_status", create_constraint=True),
        default=ProcessingStatus.PENDING,
        index=True,
    )

    # ── Extracted content ──────────────────────────────────────────
    extracted_title: Mapped[str | None] = mapped_column(String(500))
    extracted_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    extracted_case_number: Mapped[str | None] = mapped_column(String(100), index=True)
    raw_text: Mapped[str | None] = mapped_column(Text)
    page_count: Mapped[int | None] = mapped_column(Integer)

    # ── LLM-enriched metadata (stored as flexible JSON) ────────────
    llm_metadata: Mapped[dict | None] = mapped_column(
        JSONB,
        default=dict,
        comment="Flexible store for LLM-extracted fields: budget, sentiment, etc.",
    )

    # ── Processing telemetry ───────────────────────────────────────
    processing_duration_ms: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)

    # ── Foreign keys ───────────────────────────────────────────────
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        index=True,
    )

    # ── Relationships ──────────────────────────────────────────────
    project: Mapped["Project | None"] = relationship(  # noqa: F821
        back_populates="documents",
    )

    def __repr__(self) -> str:
        return f"<Document {self.filename} ({self.processing_status.value})>"
