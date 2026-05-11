"""
Standalone file watcher entry point.

Run with: python -m app.watcher.run

This keeps the watcher alive as its own process, suitable for
running as a Docker container or systemd service.
"""

import logging
import signal
import sys
import time

from app.watcher.file_watcher import FileWatcher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    watcher = FileWatcher()
    watcher.start()

    # Graceful shutdown on SIGINT / SIGTERM
    def _shutdown(signum, _frame):
        logger.info("Received signal %s – shutting down watcher.", signum)
        watcher.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    logger.info("File watcher is running. Press Ctrl+C to stop.")

    # Block forever (cross-platform alternative to signal.pause())
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        watcher.stop()


if __name__ == "__main__":
    main()
