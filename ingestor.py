"""
ingestor.py — CLI entry point for the DocuFlow-CRM ingestion engine.

This script demonstrates the full pipeline:
  1. Watch mode:  Monitor a directory for new files (Watchdog).
  2. Single mode: Process a specific file immediately.
  3. Bulk mode:   Scan a directory and dispatch all files.

Usage:
  # Watch a directory (blocks, processes files as they appear)
  python ingestor.py watch --directory ./watch_directory

  # Process a single file
  python ingestor.py process --file ./contracts/agreement.pdf

  # Bulk-index an entire folder
  python ingestor.py bulk --directory ./case_files --project-id <uuid>
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-25s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("docuflow.ingestor")


def cmd_watch(args: argparse.Namespace) -> None:
    """Start the file watcher daemon."""
    from app.watcher.file_watcher import FileWatcher

    directory = Path(args.directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("  DocuFlow-CRM — File Watcher")
    logger.info("  Monitoring: %s", directory)
    logger.info("  Supported:  .pdf, .docx")
    logger.info("=" * 60)

    watcher = FileWatcher(watch_path=directory)
    watcher.start()

    try:
        # Keep the main thread alive
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down watcher...")
        watcher.stop()


def cmd_process(args: argparse.Namespace) -> None:
    """Process a single file through the full pipeline."""
    file_path = Path(args.file).resolve()

    if not file_path.exists():
        logger.error("File not found: %s", file_path)
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("  DocuFlow-CRM — Single File Processing")
    logger.info("  File: %s", file_path.name)
    logger.info("  Size: %s bytes", file_path.stat().st_size)
    logger.info("=" * 60)

    async def _run():
        from app.db import async_session_factory
        from app.services.ingestion.pipeline import IngestionPipeline

        async with async_session_factory() as session:
            pipeline = IngestionPipeline(session)
            doc = await pipeline.ingest(
                file_path=file_path,
                project_id=args.project_id,
                client_id=args.client_id,
            )

            logger.info("─" * 60)
            logger.info("  ✅ Processing Complete")
            logger.info("  Document ID:   %s", doc.id)
            logger.info("  Title:         %s", doc.extracted_title or "N/A")
            logger.info("  Type:          %s", doc.document_type.value)
            logger.info("  Pages:         %s", doc.page_count)
            logger.info("  Case Number:   %s", doc.extracted_case_number or "N/A")
            logger.info("  Status:        %s", doc.processing_status.value)
            logger.info("  Duration:      %dms", doc.processing_duration_ms or 0)

            if doc.llm_metadata:
                logger.info("  LLM Sentiment: %s", doc.llm_metadata.get("sentiment", "N/A"))
                logger.info("  LLM Budget:    %s", doc.llm_metadata.get("total_budget", "N/A"))
                logger.info("  LLM Summary:   %s", doc.llm_metadata.get("summary", "N/A")[:100])
            logger.info("─" * 60)

    asyncio.run(_run())


def cmd_bulk(args: argparse.Namespace) -> None:
    """Bulk-index a directory by dispatching Celery tasks."""
    directory = Path(args.directory).resolve()

    if not directory.is_dir():
        logger.error("Not a directory: %s", directory)
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("  DocuFlow-CRM — Bulk Indexing")
    logger.info("  Directory: %s", directory)
    logger.info("=" * 60)

    from app.services.indexing.engine import IndexingEngine

    engine = IndexingEngine()
    manifest = engine.scan_directory(directory)

    logger.info("─" * 60)
    logger.info("  Scan Results:")
    logger.info("    Total files:       %d", manifest.total_files)
    logger.info("    Unique files:      %d", manifest.unique_files)
    logger.info("    Duplicates:        %d", manifest.duplicate_files)
    logger.info("    Unsupported:       %d", manifest.unsupported_files)
    logger.info("─" * 60)

    if manifest.unique_files == 0:
        logger.warning("No processable files found.")
        return

    if args.dispatch:
        task_ids = engine.dispatch_bulk_tasks(
            manifest,
            project_id=args.project_id,
            client_id=args.client_id,
        )
        logger.info("  Dispatched %d Celery tasks.", len(task_ids))
        for tid in task_ids[:5]:
            logger.info("    Task: %s", tid)
        if len(task_ids) > 5:
            logger.info("    ... and %d more.", len(task_ids) - 5)
    else:
        logger.info("  Dry run – use --dispatch to send tasks to Celery.")
        for entry in manifest.entries[:10]:
            logger.info("    📄 %s (%s, %d bytes)", entry.filename, entry.extension, entry.file_size_bytes)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ingestor",
        description="DocuFlow-CRM Document Ingestion Engine",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ── Watch command ──────────────────────────────────────────────
    watch_parser = subparsers.add_parser(
        "watch", help="Monitor a directory for new files.",
    )
    watch_parser.add_argument(
        "--directory", "-d", default="./watch_directory",
        help="Directory to watch (default: ./watch_directory)",
    )
    watch_parser.set_defaults(func=cmd_watch)

    # ── Process command ────────────────────────────────────────────
    process_parser = subparsers.add_parser(
        "process", help="Process a single file.",
    )
    process_parser.add_argument(
        "--file", "-f", required=True, help="Path to the file.",
    )
    process_parser.add_argument("--project-id", default=None)
    process_parser.add_argument("--client-id", default=None)
    process_parser.set_defaults(func=cmd_process)

    # ── Bulk command ───────────────────────────────────────────────
    bulk_parser = subparsers.add_parser(
        "bulk", help="Bulk-index a directory.",
    )
    bulk_parser.add_argument(
        "--directory", "-d", required=True,
        help="Directory to scan.",
    )
    bulk_parser.add_argument("--project-id", default=None)
    bulk_parser.add_argument("--client-id", default=None)
    bulk_parser.add_argument(
        "--dispatch", action="store_true",
        help="Actually dispatch Celery tasks (default: dry run).",
    )
    bulk_parser.set_defaults(func=cmd_bulk)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
