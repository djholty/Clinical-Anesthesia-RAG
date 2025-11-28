"""
PDF Watcher Service

Watches the data/pdfs directory for new/updated PDFs. After a quiet period
(no further changes), it converts any PDFs without corresponding .md files
into Markdown in data/ingested_documents using the existing converter.

Intended to chain with the database watcher (which watches the markdown
folder). This creates the sequence:

  Upload PDF -> (quiet period A) -> Convert to .md -> (quiet period B via DB watcher) -> Rebuild DB

Environment variables:
  - PDF_WATCH_DIRECTORY: directory to watch for PDFs (default: ./data/pdfs)
  - MD_OUTPUT_DIR: markdown output directory (default: ./data/ingested_documents)
  - PDF_QUIET_PERIOD_SECONDS: quiet period before converting (default: 120)

Requires: watchdog, python-dotenv (optional if you set envs via container)
"""

import os
import sys
import time
import signal
import threading
import logging
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from dotenv import load_dotenv

# Load env vars if present
load_dotenv()

# Ensure project root is on sys.path so `app.*` imports work when run as a script
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Configuration
PDF_WATCH_DIRECTORY = os.getenv("PDF_WATCH_DIRECTORY", "./data/pdfs")
MD_OUTPUT_DIR = os.getenv("MD_OUTPUT_DIR", "./data/ingested_documents")
PDF_QUIET_PERIOD_SECONDS = int(os.getenv("PDF_QUIET_PERIOD_SECONDS", "120"))
PDF_CONVERT_ON_STARTUP = os.getenv("PDF_CONVERT_ON_STARTUP", "true").lower() == "true"

# Global state
convert_timer = None
timer_lock = threading.Lock()
shutdown_event = threading.Event()


class PdfFileHandler(FileSystemEventHandler):
    """Handles file system events for PDFs in the watched directory."""

    def __init__(self):
        self.known_pdfs = set()
        logger.info(f"PDF handler initialized, watching: {PDF_WATCH_DIRECTORY}")

    def on_created(self, event):
        if not event.is_directory and event.src_path.lower().endswith('.pdf'):
            self._handle_pdf_change(event.src_path, "created")

    def on_modified(self, event):
        if not event.is_directory and event.src_path.lower().endswith('.pdf'):
            self._handle_pdf_change(event.src_path, "modified")

    def _handle_pdf_change(self, file_path: str, event_type: str):
        global convert_timer
        file_name = Path(file_path).name

        with timer_lock:
            if file_path not in self.known_pdfs:
                logger.info(f"📄 New PDF detected: {file_name} (event: {event_type})")
                self.known_pdfs.add(file_path)
            else:
                logger.info(f"📝 PDF modified: {file_name} (event: {event_type})")

            # Reset quiet period timer
            if convert_timer is not None and convert_timer.is_alive():
                convert_timer.cancel()
                logger.info("⏸️  Conversion quiet period timer reset due to new change")

            convert_timer = threading.Timer(PDF_QUIET_PERIOD_SECONDS, self._trigger_conversion)
            convert_timer.daemon = True
            convert_timer.start()

            target_time = time.time() + PDF_QUIET_PERIOD_SECONDS
            logger.info(f"⏳ Started conversion quiet period ({PDF_QUIET_PERIOD_SECONDS}s). Will run at {time.strftime('%H:%M:%S', time.localtime(target_time))}")

    def _trigger_conversion(self):
        logger.info("=" * 60)
        logger.info("🔄 Starting PDF → Markdown conversion after quiet period...")
        logger.info("=" * 60)
        try:
            # Import here to avoid hard dependency during container startup
            from app.extract_pdf_to_markdown import process_pdfs_from_folder
            process_pdfs_from_folder()
            logger.info("✅ PDF → Markdown conversion completed")
        except Exception as e:
            logger.error(f"❌ Error during conversion: {e}", exc_info=True)

    def scan_initial_state(self):
        watch_path = Path(PDF_WATCH_DIRECTORY)
        if not watch_path.exists():
            logger.warning(f"⚠️  Watch directory does not exist: {PDF_WATCH_DIRECTORY}")
            return
        pdfs = list(watch_path.glob("**/*.pdf"))
        self.known_pdfs = {str(p) for p in pdfs}
        logger.info(f"📂 Initial scan: Found {len(self.known_pdfs)} existing PDFs")
        for p in sorted(self.known_pdfs):
            logger.info(f"   - {Path(p).name}")


def signal_handler(signum, frame):
    logger.info(f"\n⚠️  Received signal {signum}, shutting down PDF watcher...")
    shutdown_event.set()
    global convert_timer
    with timer_lock:
        if convert_timer is not None and convert_timer.is_alive():
            convert_timer.cancel()
            logger.info("⏸️  Cancelled pending conversion timer")


def main():
    logger.info("=" * 60)
    logger.info("   PDF WATCHER SERVICE")
    logger.info("=" * 60)
    logger.info(f"   Watch Directory: {PDF_WATCH_DIRECTORY}")
    logger.info(f"   Markdown Output: {MD_OUTPUT_DIR}")
    logger.info(f"   Quiet Period: {PDF_QUIET_PERIOD_SECONDS} seconds")
    logger.info("=" * 60)

    # Register signal handlers for graceful shutdown (only in main thread)
    # When running as a background thread, signals are handled by the main process
    try:
        if threading.current_thread() is threading.main_thread():
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
        else:
            logger.info("Running as background thread - signal handlers will be managed by main process")
    except (ValueError, AttributeError):
        # Signal registration failed (not main thread) - this is expected when running as a thread
        logger.info("Running as background thread - shutdown will be handled via shutdown_event")

    watch_path = Path(PDF_WATCH_DIRECTORY)
    if not watch_path.exists():
        logger.error(f"❌ Watch directory does not exist: {PDF_WATCH_DIRECTORY}")
        logger.error("   Ensure the directory exists or set PDF_WATCH_DIRECTORY")
        raise SystemExit(1)

    handler = PdfFileHandler()
    handler.scan_initial_state()

    # Optional: convert any PDFs missing markdown on startup
    if PDF_CONVERT_ON_STARTUP:
        try:
            from app.extract_pdf_to_markdown import process_pdfs_from_folder
            logger.info("\n🔍 Startup scan: converting any PDFs missing corresponding .md files...")
            process_pdfs_from_folder()
            logger.info("✅ Startup conversion scan complete")
        except Exception as e:
            logger.error(f"❌ Startup conversion failed: {e}", exc_info=True)

    observer = Observer()
    observer.schedule(handler, str(watch_path), recursive=False)
    observer.start()

    logger.info(f"\n👀 Watching directory: {PDF_WATCH_DIRECTORY}")
    logger.info("   Waiting for PDF changes...")
    logger.info("   Press Ctrl+C to stop\n")

    try:
        while not shutdown_event.is_set():
            time.sleep(1)
    finally:
        observer.stop()
        observer.join(timeout=5)
        with timer_lock:
            if convert_timer is not None and convert_timer.is_alive():
                convert_timer.cancel()
        logger.info("✅ PDF watcher stopped")


if __name__ == "__main__":
    main()


