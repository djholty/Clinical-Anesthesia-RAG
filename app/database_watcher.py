"""
Database Watcher Service

Monitors the ingested_documents directory for new markdown files and automatically
rebuilds the Chroma vector database after a quiet period (default: 5 minutes).

Designed for Docker deployment with cloud-ready features:
- Environment-based configuration
- Graceful shutdown handling
- Error recovery and logging
"""
import os
import sys
import time
import signal
import threading
import logging
from pathlib import Path
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path to import app package
sys.path.insert(0, str(Path(__file__).parent.parent))
from app.rebuild_database import rebuild_database

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Configuration from environment variables
QUIET_PERIOD_SECONDS = int(os.getenv("QUIET_PERIOD_SECONDS", "300"))  # 5 minutes default
WATCH_DIRECTORY = os.getenv("WATCH_DIRECTORY", "./data/ingested_documents")
DB_DIR = os.getenv("DB_DIR", "./data/chroma_db")
MARKDOWN_DIR = os.getenv("MARKDOWN_DIR", "./data/ingested_documents")
REBUILD_ON_STARTUP = os.getenv("REBUILD_ON_STARTUP", "false").lower() == "true"

# Global state
rebuild_timer = None
timer_lock = threading.Lock()
is_rebuilding = False
rebuild_lock = threading.Lock()
shutdown_event = threading.Event()


class MarkdownFileHandler(FileSystemEventHandler):
    """
    Handles file system events for markdown files in the watched directory.
    """
    
    def __init__(self):
        self.known_files = set()
        self.last_change_time = None
        logger.info(f"MarkdownFileHandler initialized, watching: {WATCH_DIRECTORY}")
    
    def on_created(self, event):
        """Called when a file or directory is created."""
        if not event.is_directory and event.src_path.endswith('.md'):
            self._handle_markdown_change(event.src_path, "created")
    
    def on_modified(self, event):
        """Called when a file or directory is modified."""
        if not event.is_directory and event.src_path.endswith('.md'):
            self._handle_markdown_change(event.src_path, "modified")
    
    def _handle_markdown_change(self, file_path: str, event_type: str):
        """Handle a change to a markdown file."""
        global rebuild_timer, last_change_time
        
        file_name = Path(file_path).name
        
        with timer_lock:
            if file_path not in self.known_files:
                logger.info(f"📄 New markdown file detected: {file_name} (event: {event_type})")
                self.known_files.add(file_path)
            else:
                logger.info(f"📝 Markdown file modified: {file_name} (event: {event_type})")
            
            self.last_change_time = time.time()
            
            # Cancel existing timer if it exists
            if rebuild_timer is not None and rebuild_timer.is_alive():
                rebuild_timer.cancel()
                logger.info(f"⏸️  Quiet period timer reset due to new change")
            
            # Start new quiet period timer
            rebuild_timer = threading.Timer(QUIET_PERIOD_SECONDS, self._trigger_rebuild)
            rebuild_timer.daemon = True
            rebuild_timer.start()
            
            logger.info(f"⏳ Started quiet period timer ({QUIET_PERIOD_SECONDS}s) for rebuild")
            logger.info(f"   Timer will trigger rebuild at {datetime.fromtimestamp(time.time() + QUIET_PERIOD_SECONDS).strftime('%H:%M:%S')}")
    
    def _trigger_rebuild(self):
        """Trigger database rebuild after quiet period."""
        global is_rebuilding
        
        # Check if already rebuilding
        with rebuild_lock:
            if is_rebuilding:
                logger.warning("⚠️  Rebuild already in progress, skipping")
                return
            
            is_rebuilding = True
        
        try:
            logger.info("=" * 60)
            logger.info("🔄 Starting automatic database rebuild...")
            logger.info("=" * 60)
            
            # Count markdown files
            md_files = list(Path(MARKDOWN_DIR).glob("**/*.md"))
            logger.info(f"📊 Found {len(md_files)} markdown files to process")
            
            # Call rebuild function
            rebuild_database(markdown_dir=MARKDOWN_DIR, db_dir=DB_DIR)
            
            logger.info("=" * 60)
            logger.info("✅ Automatic database rebuild completed successfully")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"❌ Error during database rebuild: {e}", exc_info=True)
        finally:
            with rebuild_lock:
                is_rebuilding = False
    
    def scan_initial_state(self):
        """Scan directory on startup to establish baseline of existing files."""
        watch_path = Path(WATCH_DIRECTORY)
        if not watch_path.exists():
            logger.warning(f"⚠️  Watch directory does not exist: {WATCH_DIRECTORY}")
            return
        
        md_files = list(watch_path.glob("**/*.md"))
        self.known_files = {str(f) for f in md_files}
        logger.info(f"📂 Initial scan: Found {len(self.known_files)} existing markdown files")
        
        for file_path in sorted(self.known_files):
            logger.info(f"   - {Path(file_path).name}")


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"\n⚠️  Received signal {signum}, initiating graceful shutdown...")
    shutdown_event.set()
    
    global rebuild_timer
    with timer_lock:
        if rebuild_timer is not None and rebuild_timer.is_alive():
            rebuild_timer.cancel()
            logger.info("⏸️  Cancelled pending rebuild timer")


def main():
    """Main function to run the database watcher service."""
    logger.info("=" * 60)
    logger.info("   DATABASE WATCHER SERVICE")
    logger.info("=" * 60)
    logger.info(f"Configuration:")
    logger.info(f"   Watch Directory: {WATCH_DIRECTORY}")
    logger.info(f"   Markdown Directory: {MARKDOWN_DIR}")
    logger.info(f"   Database Directory: {DB_DIR}")
    logger.info(f"   Quiet Period: {QUIET_PERIOD_SECONDS} seconds ({QUIET_PERIOD_SECONDS/60:.1f} minutes)")
    logger.info(f"   Rebuild on Startup: {REBUILD_ON_STARTUP}")
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
    
    # Check if watch directory exists
    watch_path = Path(WATCH_DIRECTORY)
    if not watch_path.exists():
        logger.error(f"❌ Watch directory does not exist: {WATCH_DIRECTORY}")
        logger.error("   Please ensure the directory exists or set WATCH_DIRECTORY environment variable")
        sys.exit(1)
    
    # Create event handler
    event_handler = MarkdownFileHandler()
    
    # Perform initial scan
    event_handler.scan_initial_state()
    
    # Optional rebuild on startup
    if REBUILD_ON_STARTUP:
        logger.info("\n🔄 Performing initial database rebuild...")
        try:
            rebuild_database(markdown_dir=MARKDOWN_DIR, db_dir=DB_DIR)
            logger.info("✅ Initial rebuild completed")
        except Exception as e:
            logger.error(f"❌ Error during initial rebuild: {e}", exc_info=True)
    
    # Create and start observer
    observer = Observer()
    observer.schedule(event_handler, str(watch_path), recursive=False)
    observer.start()
    
    logger.info(f"\n👀 Watching directory: {WATCH_DIRECTORY}")
    logger.info(f"   Waiting for markdown file changes...")
    logger.info(f"   Press Ctrl+C to stop\n")
    
    try:
        # Keep the main thread alive until shutdown
        while not shutdown_event.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("\n⚠️  Keyboard interrupt received")
        shutdown_event.set()
    finally:
        logger.info("\n🛑 Stopping watcher...")
        observer.stop()
        observer.join(timeout=5)
        
        # Cancel any pending rebuild timer
        global rebuild_timer
        with timer_lock:
            if rebuild_timer is not None and rebuild_timer.is_alive():
                rebuild_timer.cancel()
        
        logger.info("✅ Watcher stopped gracefully")


if __name__ == "__main__":
    main()

