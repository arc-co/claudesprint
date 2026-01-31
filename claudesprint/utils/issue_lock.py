"""Issue state locking to prevent concurrent access race conditions.

This module provides file locking for issue state files (current_issue.json)
to prevent race conditions between the Engine main loop and Agent subprocesses.

Uses the existing LockFile utility for cross-platform kernel-level locking.
"""

import logging
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from claudesprint.utils.lock import LockFile

logger = logging.getLogger(__name__)

# Default lock settings
DEFAULT_TIMEOUT = 10.0  # seconds
DEFAULT_RETRY_INTERVAL = 0.1  # seconds

# Singleton instances per project directory
_issue_locks: dict[str, "IssueLock"] = {}


class LockAcquisitionError(Exception):
    """Raised when lock cannot be acquired within timeout."""

    pass


class IssueLock:
    """Lock manager for issue state files.

    Provides thread-safe and process-safe locking for current_issue.json
    to prevent race conditions during concurrent access.

    Uses a separate lock file (issue.lock) from state.lock to avoid deadlocks.
    """

    def __init__(self, project_dir: Path) -> None:
        """Initialize IssueLock.

        Args:
            project_dir: Project directory (e.g., .claudesprint/project)
        """
        self.project_dir = Path(project_dir)
        self.lock_path = self.project_dir / "issue.lock"
        self._lock = LockFile(self.lock_path)

    @contextmanager
    def locked(
        self,
        timeout: float = DEFAULT_TIMEOUT,
        retry_interval: float = DEFAULT_RETRY_INTERVAL,
    ) -> Generator[None, None, None]:
        """Context manager for acquiring lock with timeout and retry.

        Args:
            timeout: Maximum time to wait for lock (seconds)
            retry_interval: Time between retry attempts (seconds)

        Yields:
            None while lock is held

        Raises:
            LockAcquisitionError: If lock cannot be acquired within timeout
        """
        start_time = time.monotonic()
        acquired = False

        while not acquired:
            success, message = self._lock.acquire()
            if success:
                acquired = True
                logger.debug(f"Acquired issue lock: {self.lock_path}")
                break

            elapsed = time.monotonic() - start_time
            if elapsed >= timeout:
                raise LockAcquisitionError(
                    f"Failed to acquire issue lock within {timeout}s: {message}"
                )

            logger.debug(f"Lock busy, retrying in {retry_interval}s ({elapsed:.1f}s elapsed)")
            time.sleep(retry_interval)

        try:
            yield
        finally:
            self._lock.release()
            logger.debug(f"Released issue lock: {self.lock_path}")

    def try_acquire(self) -> tuple[bool, str]:
        """Try to acquire lock without blocking.

        Returns:
            Tuple of (success, message)
        """
        return self._lock.acquire()

    def release(self) -> bool:
        """Release the lock if held.

        Returns:
            True if released, False if not held
        """
        return self._lock.release()

    @property
    def is_acquired(self) -> bool:
        """Check if lock is currently held by this instance."""
        return self._lock.is_acquired


def get_issue_lock(project_dir: Path | str) -> IssueLock:
    """Get or create IssueLock instance for a project directory.

    Uses singleton pattern to ensure only one lock instance per directory.

    Args:
        project_dir: Project directory path

    Returns:
        IssueLock instance for the directory
    """
    key = str(Path(project_dir).resolve())
    if key not in _issue_locks:
        _issue_locks[key] = IssueLock(Path(project_dir))
    return _issue_locks[key]


def clear_lock_cache() -> None:
    """Clear the lock singleton cache.

    Primarily for testing purposes.
    """
    _issue_locks.clear()
