from pathlib import Path
import asyncio
from typing import Optional
import logging
import threading

from watchdog.observers import Observer
from watchdog.events import (
    FileSystemEventHandler,
    FileModifiedEvent,
    FileCreatedEvent,
    FileDeletedEvent,
)
import httpx

logger = logging.getLogger(__name__)

class CodeFileWatcher(FileSystemEventHandler):
    def __init__(
            self,
            base_url: str,
            watch_path: Path,
            file_patterns: list[str] = ["*.py"],
            debounce_seconds: float = 0.5,
    ) -> None:
        """
        Initialize the file watcher.

        Args:
            base_url: Base URL of the API server
            watch_path: Directory path to watch
            file_patterns: List of file patterns to watch (glob syntax)
            debounce_seconds: Time to wait for file to stabilize before processing
        """
        self.base_url = base_url.rstrip("/")
        # Ensure we have absolute paths
        self.watch_path = Path(watch_path).resolve()
        self.file_patterns = file_patterns
        self.debounce_seconds = debounce_seconds

        # Keep track of pending updates to implement debouncing
        self._pending_updates: dict[Path, asyncio.Task[None]] = {}
        # Client for making API requests
        self._client = httpx.AsyncClient()

        # Store the event loop from the main thread
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        # Lock for thread-safe operations
        self._lock = threading.Lock()

        logger.info(f"Watching directory: {self.watch_path}")

    async def start(self) -> None:
        """Start watching the directory"""
        # Store the event loop from the main thread
        self._loop = asyncio.get_running_loop()

        self._observer = Observer()
        self._observer.schedule(self, str(self.watch_path), recursive=True)
        self._observer.start()
        logger.info(f"Started watching {self.watch_path}")

    async def stop(self) -> None:
        """Stop watching and cleanup"""
        if hasattr(self, '_observer'):
            self._observer.stop()
            self._observer.join()
        await self._client.aclose()
        logger.info("Stopped watching")

    def _should_process_file(self, path: Path) -> bool:
        """Check if file should be processed based on patterns"""
        if path.is_dir():
            return False

        return any(path.match(pattern) for pattern in self.file_patterns)

    def _get_relative_path(self, path: Path) -> Path:
        """Get path relative to watch directory, handling absolute/relative paths correctly"""
        try:
            # Ensure we're working with absolute paths
            abs_path = Path(path).resolve()
            return abs_path.relative_to(self.watch_path)
        except ValueError:
            logger.error(f"Path error: {path} is not within {self.watch_path}")
            raise

    async def _process_file_change(self, path: Path) -> None:
        """Process a file change after debounce period"""
        try:
            # Wait for file to stabilize
            await asyncio.sleep(self.debounce_seconds)

            # Resolve to absolute path
            abs_path = Path(path).resolve()

            if not abs_path.exists():
                # File was deleted
                await self._handle_delete(abs_path)
                return

            # Get relative path and read contents
            relative_path = self._get_relative_path(abs_path)
            contents = abs_path.read_text()

            # Send to API
            response = await self._client.post(
                f"{self.base_url}/files",
                json={
                    "file_name": str(relative_path),
                    "contents": contents,
                },
            )
            response.raise_for_status()
            logger.info(f"Successfully processed changes to {relative_path}")

        except ValueError as e:
            logger.error(f"Path error processing {path}: {e}")
        except Exception as e:
            logger.error(f"Error processing {path}: {e}")
        finally:
            # Thread-safe removal from pending updates
            with self._lock:
                self._pending_updates.pop(path, None)

    async def _handle_delete(self, path: Path) -> None:
        """Handle file deletion"""
        try:
            relative_path = self._get_relative_path(path)
            response = await self._client.delete(
                f"{self.base_url}/files/{relative_path}"
            )
            response.raise_for_status()
            logger.info(f"Successfully processed deletion of {relative_path}")
        except ValueError as e:
            logger.error(f"Path error processing deletion {path}: {e}")
        except Exception as e:
            logger.error(f"Error processing deletion of {path}: {e}")

    def _queue_update(self, path: Path) -> None:
        """Queue a file update with debouncing"""
        if self._loop is None:
            logger.error("No event loop available")
            return

        # Thread-safe task management
        with self._lock:
            # Cancel any pending update for this file
            if path in self._pending_updates:
                self._pending_updates[path].cancel()

            # Create new task for this update
            task = self._loop.create_task(
                self._process_file_change(path)
            )
            self._pending_updates[path] = task

    def on_modified(self, event: FileModifiedEvent) -> None:
        if not isinstance(event.src_path, str):
            return

        path = Path(event.src_path)
        if self._should_process_file(path):
            self._queue_update(path)

    def on_created(self, event: FileCreatedEvent) -> None:
        if not isinstance(event.src_path, str):
            return

        path = Path(event.src_path)
        if self._should_process_file(path):
            self._queue_update(path)

    def on_deleted(self, event: FileDeletedEvent) -> None:
        if not isinstance(event.src_path, str):
            return

        path = Path(event.src_path)
        if self._should_process_file(path):
            self._queue_update(path)

async def watch_directory(
        base_url: str,
        path: str | Path,
        patterns: list[str] = ["*.py"],
        debounce_seconds: float = 0.5
) -> CodeFileWatcher:
    """
    Watch a directory for code file changes.

    Args:
        base_url: Base URL of the API server
        path: Directory path to watch
        patterns: List of file patterns to watch (glob syntax)
        debounce_seconds: Time to wait for file to stabilize before processing

    Returns:
        CodeFileWatcher instance that has been started
    """
    watcher = CodeFileWatcher(
        base_url=base_url,
        watch_path=Path(path),
        file_patterns=patterns,
        debounce_seconds=debounce_seconds,
    )
    await watcher.start()
    return watcher