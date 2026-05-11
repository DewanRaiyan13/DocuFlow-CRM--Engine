"""
Bulk Indexing Engine.

Handles mass-upload scenarios (100+ documents) by:
  1. Scanning a directory for supported files.
  2. Computing hashes in parallel to identify duplicates.
  3. Dispatching individual Celery tasks for each unique file.
  4. Generating a structured index manifest (JSON) for the batch.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from app.config import get_settings
from app.services.ingestion.pipeline import compute_file_hash, detect_mime_type

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class IndexEntry:
    """One row in the generated index."""
    filename: str
    file_path: str
    file_hash: str
    file_size_bytes: int
    mime_type: str
    extension: str


@dataclass
class IndexManifest:
    """Result of a bulk indexing scan."""
    total_files: int = 0
    unique_files: int = 0
    duplicate_files: int = 0
    unsupported_files: int = 0
    entries: list[IndexEntry] = field(default_factory=list)
    duplicates: list[str] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)


class IndexingEngine:
    """
    Scan a directory, deduplicate, and produce a structured manifest.

    The engine does NOT perform extraction – it only builds the index
    and can dispatch Celery tasks for actual processing.
    """

    def __init__(self, supported_extensions: list[str] | None = None):
        self._extensions = set(
            supported_extensions or settings.SUPPORTED_EXTENSIONS
        )

    def scan_directory(self, directory: Path) -> IndexManifest:
        """
        Walk the directory tree and build an index manifest.

        Returns:
            IndexManifest with unique entries and dedup stats.
        """
        directory = Path(directory).resolve()
        if not directory.is_dir():
            raise NotADirectoryError(f"Not a directory: {directory}")

        manifest = IndexManifest()
        seen_hashes: set[str] = set()

        for file_path in sorted(directory.rglob("*")):
            if not file_path.is_file():
                continue

            manifest.total_files += 1

            if file_path.suffix.lower() not in self._extensions:
                manifest.unsupported_files += 1
                manifest.unsupported.append(str(file_path))
                continue

            file_hash = compute_file_hash(file_path)

            if file_hash in seen_hashes:
                manifest.duplicate_files += 1
                manifest.duplicates.append(str(file_path))
                continue

            seen_hashes.add(file_hash)

            entry = IndexEntry(
                filename=file_path.name,
                file_path=str(file_path),
                file_hash=file_hash,
                file_size_bytes=file_path.stat().st_size,
                mime_type=detect_mime_type(file_path),
                extension=file_path.suffix.lower(),
            )
            manifest.entries.append(entry)

        manifest.unique_files = len(manifest.entries)
        logger.info(
            "Index scan complete: %d total, %d unique, %d duplicates, %d unsupported",
            manifest.total_files,
            manifest.unique_files,
            manifest.duplicate_files,
            manifest.unsupported_files,
        )
        return manifest

    def dispatch_bulk_tasks(
        self,
        manifest: IndexManifest,
        project_id: str | None = None,
        client_id: str | None = None,
    ) -> list[str]:
        """
        Fire a Celery task for each unique file in the manifest.

        Returns:
            List of Celery task IDs.
        """
        from app.workers.tasks import process_document_task

        task_ids: list[str] = []
        for entry in manifest.entries:
            result = process_document_task.delay(
                file_path=entry.file_path,
                project_id=project_id,
                client_id=client_id,
            )
            task_ids.append(result.id)

        logger.info("Dispatched %d Celery tasks for bulk indexing.", len(task_ids))
        return task_ids
