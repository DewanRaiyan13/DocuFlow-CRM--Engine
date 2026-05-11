"""
File Watcher – powered by Watchdog.

Monitors the configured ``WATCH_DIRECTORY`` for new PDF/DOCX files
and dispatches Celery tasks for each detected file. This is the
"zero-manual-entry" trigger – drop a file, get a CRM record.

Features:
  - Debouncing: waits for file writes to complete before dispatching.
  - Extension filtering: only reacts to supported file types.
  - Recursive: monitors subdirectories.
  - Thread-safe: runs in a daemon thread alongside FastAPI.
"""

from __future__ import annotations

import logging
import time
import threading
from pathlib import Path

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class DocumentEventHandler(FileSystemEventHandler):
    """
    React to new files in the watch directory.

    Uses a debounce mechanism to avoid processing partially-written
    files (e.g., during a slow copy or download).
    """

    DEBOUNCE_SECONDS = 2.0

    def __init__(
        self,
        supported_extensions: set[str] | None = None,
        project_id: str | None = None,
        client_id: str | None = None,
    ) -> None:
        super().__init__()
        self._extensions = supported_extensions or set(
            settings.SUPPORTED_EXTENSIONS
        )
        self._project_id = project_id
        self._client_id = client_id
        self._pending: dict[str, float] = {}
        self._lock = threading.Lock()

        # Start debounce checker thread
        self._checker = threading.Thread(
            target=self._debounce_loop,
            daemon=True,
        )
        self._checker.start()

    def on_created(self, event: FileCreatedEvent) -> None:
        """Called when a new file is created in the watch directory."""
        if event.is_directory:
            return

        file_path = Path(event.src_path)
        if file_path.suffix.lower() not in self._extensions:
            logger.debug("Ignoring unsupported file: %s", file_path.name)
            return

        with self._lock:
            self._pending[str(file_path)] = time.time()
            logger.info("Detected new file: %s (debouncing...)", file_path.name)

    def _debounce_loop(self) -> None:
        """
        Background loop that checks pending files and dispatches
        tasks once the debounce period has elapsed.
        """
        while True:
            time.sleep(1.0)
            now = time.time()
            ready: list[str] = []

            with self._lock:
                for path, timestamp in list(self._pending.items()):
                    if now - timestamp >= self.DEBOUNCE_SECONDS:
                        ready.append(path)

                for path in ready:
                    del self._pending[path]

            for path in ready:
                self._dispatch(path)

    def _dispatch(self, file_path: str) -> None:
        """Send the file to the Celery processing queue."""
        from app.workers.tasks import process_document_task

        logger.info("Dispatching to Celery: %s", Path(file_path).name)
        process_document_task.delay(
            file_path=file_path,
            project_id=self._project_id,
            client_id=self._client_id,
        )


class FileWatcher:
    """
    High-level wrapper around Watchdog's Observer.

    Usage::

        watcher = FileWatcher()
        watcher.start()       # Non-blocking (daemon thread)
        ...
        watcher.stop()
    """

    def __init__(
        self,
        watch_path: Path | None = None,
        recursive: bool = True,
    ) -> None:
        self._watch_path = watch_path or settings.watch_path
        self._recursive = recursive
        self._observer: Observer | None = None

    def start(self) -> None:
        """Start watching the directory in a background thread."""
        self._watch_path.mkdir(parents=True, exist_ok=True)

        handler = DocumentEventHandler()
        self._observer = Observer()
        self._observer.schedule(
            handler,
            str(self._watch_path),
            recursive=self._recursive,
        )
        self._observer.daemon = True
        self._observer.start()

        logger.info(
            "🔍 File watcher started on: %s (recursive=%s)",
            self._watch_path,
            self._recursive,
        )

    def stop(self) -> None:
        """Stop the watcher gracefully."""
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            logger.info("File watcher stopped.")

    @property
    def is_alive(self) -> bool:
        return self._observer is not None and self._observer.is_alive()
