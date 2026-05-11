"""
Ingestion Pipeline – the core automation logic.

Orchestrates the full journey from raw file → database record:

  1. Compute file hash (SHA-256) for deduplication.
  2. Create a preliminary Document row (status=PENDING).
  3. Dispatch structural extraction via the ExtractorRegistry.
  4. Enrich with LLM for soft data (sentiment, budget, deadlines).
  5. Update the Document row with extracted data (status=COMPLETED).
  6. Log an InteractionLog entry and refresh the client's last_activity_at.

This module is called by Celery tasks but is itself framework-agnostic –
it only depends on a DB session and the extraction services.
"""

from __future__ import annotations

import hashlib
import logging
import mimetypes
import time
from datetime import UTC
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Client,
    Document,
    DocumentType,
    InteractionLog,
    InteractionType,
    ProcessingStatus,
)
from app.services.extraction.llm_enricher import LLMEnricher
from app.services.extraction.registry import extractor_registry

logger = logging.getLogger(__name__)


def compute_file_hash(file_path: Path, algorithm: str = "sha256") -> str:
    """Compute a hex-digest hash of a file for deduplication."""
    h = hashlib.new(algorithm)
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def detect_mime_type(file_path: Path) -> str:
    """Guess MIME type from extension; fall back to octet-stream."""
    mime, _ = mimetypes.guess_type(str(file_path))
    return mime or "application/octet-stream"


class IngestionPipeline:
    """
    Stateless pipeline – each call to ``ingest()`` processes one file.

    The pipeline is designed to be idempotent: re-ingesting the same
    file (by hash) is a no-op that returns the existing Document.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._llm = LLMEnricher()

    async def ingest(
        self,
        file_path: Path,
        project_id: str | None = None,
        client_id: str | None = None,
    ) -> Document:
        """
        Full ingestion cycle for a single file.

        Args:
            file_path: Absolute path to the file on disk.
            project_id: Optional UUID to associate the document with a project.
            client_id: Optional UUID – if provided, updates the client's
                       last_activity_at and creates an interaction log.

        Returns:
            The created (or existing) Document ORM instance.
        """
        start = time.perf_counter()
        file_path = Path(file_path).resolve()

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # ── Step 1: Deduplication ──────────────────────────────────
        file_hash = compute_file_hash(file_path)
        existing = await self._session.execute(
            select(Document).where(Document.file_hash == file_hash)
        )
        existing_doc = existing.scalar_one_or_none()
        if existing_doc:
            logger.info("Duplicate detected (hash=%s), skipping.", file_hash[:12])
            return existing_doc

        # ── Step 2: Create preliminary Document ────────────────────
        doc = Document(
            filename=file_path.name,
            file_path=str(file_path),
            file_hash=file_hash,
            file_size_bytes=file_path.stat().st_size,
            mime_type=detect_mime_type(file_path),
            processing_status=ProcessingStatus.PROCESSING,
            project_id=project_id,
        )
        self._session.add(doc)
        await self._session.flush()  # Get the ID without committing

        try:
            # ── Step 3: Structural extraction ──────────────────────
            extraction = await extractor_registry.extract(file_path)

            if not extraction.is_successful:
                doc.processing_status = ProcessingStatus.FAILED
                doc.error_message = "; ".join(extraction.errors)
                await self._session.commit()
                return doc

            doc.raw_text = extraction.raw_text
            doc.extracted_title = extraction.title
            doc.extracted_date = extraction.date
            doc.extracted_case_number = extraction.case_number
            doc.page_count = extraction.page_count

            # ── Step 4: LLM enrichment ─────────────────────────────
            llm_result = await self._llm.enrich(extraction.raw_text)

            if llm_result.success:
                doc.document_type = self._map_document_type(
                    llm_result.document_type,
                )
                doc.llm_metadata = {
                    "sentiment": llm_result.sentiment,
                    "total_budget": llm_result.total_budget,
                    "currency": llm_result.currency,
                    "deadlines": llm_result.deadlines,
                    "key_parties": llm_result.key_parties,
                    "summary": llm_result.summary,
                    "next_steps": llm_result.next_steps,
                }
            else:
                doc.llm_metadata = {"error": llm_result.error}

            # ── Step 5: Finalize ───────────────────────────────────
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            doc.processing_duration_ms = elapsed_ms
            doc.processing_status = ProcessingStatus.COMPLETED

            # ── Step 6: Client activity tracking ───────────────────
            if client_id:
                await self._update_client_activity(client_id, doc)

            await self._session.commit()
            logger.info(
                "Ingested %s in %dms (type=%s)",
                file_path.name,
                elapsed_ms,
                doc.document_type.value,
            )
            return doc

        except Exception as exc:
            doc.processing_status = ProcessingStatus.FAILED
            doc.error_message = str(exc)
            doc.processing_duration_ms = int(
                (time.perf_counter() - start) * 1000
            )
            await self._session.commit()
            logger.exception("Ingestion failed for %s", file_path.name)
            raise

    async def _update_client_activity(
        self,
        client_id: str,
        doc: Document,
    ) -> None:
        """Touch client's last_activity_at and log the interaction."""
        from datetime import datetime

        result = await self._session.execute(
            select(Client).where(Client.id == client_id)
        )
        client = result.scalar_one_or_none()
        if not client:
            logger.warning("Client %s not found, skipping activity update.", client_id)
            return

        client.last_activity_at = datetime.now(UTC)

        log = InteractionLog(
            interaction_type=InteractionType.DOCUMENT_INGESTED,
            summary=f"Document ingested: {doc.filename}",
            details=f"Type: {doc.document_type.value}, Pages: {doc.page_count}",
            client_id=client_id,
            document_id=doc.id,
        )
        self._session.add(log)

    @staticmethod
    def _map_document_type(llm_type: str) -> DocumentType:
        """Map LLM string output to the DocumentType enum."""
        mapping = {
            "proposal": DocumentType.PROPOSAL,
            "contract": DocumentType.CONTRACT,
            "invoice": DocumentType.INVOICE,
            "case_file": DocumentType.CASE_FILE,
            "correspondence": DocumentType.CORRESPONDENCE,
        }
        return mapping.get(llm_type, DocumentType.OTHER)
