"""Lock file management to prevent concurrent instances."""

import os
from pathlib import Path

from filelock import FileLock


class LockFile:
    """Cross-platform file lock to prevent concurrent instances.

    Uses the filelock library for robust, cross-platform file locking.
    Provides the same API as the previous custom implementation.
    """

    def __init__(self, lock_path: str | Path) -> None:
        self.lock_path = Path(lock_path)
        self._lock = FileLock(str(self.lock_path))
        self._acquired = False

    def acquire(self) -> tuple[bool, str]:
        """Attempt to acquire the lock atomically.

        Returns:
            Tuple of (success, message). If another process holds the lock,
            returns (False, error message).
        """
        try:
            # Ensure parent directory exists
            self.lock_path.parent.mkdir(parents=True, exist_ok=True)

            # Try to acquire exclusive lock (non-blocking)
            self._lock.acquire(blocking=False)
            self._acquired = True

            # Write PID to lock file for debugging/diagnostics
            try:
                self.lock_path.write_text(str(os.getpid()))
            except OSError:
                pass

            return True, ""
        except Exception as e:
            return False, f"Another instance is running: {e}"

    def release(self) -> bool:
        """Release the lock."""
        if not self._acquired:
            return False

        try:
            self._lock.release()
            self._acquired = False

            # Remove the lock file
            try:
                self.lock_path.unlink(missing_ok=True)
            except OSError:
                pass

            return True
        except Exception:
            return False

    def __enter__(self) -> "LockFile":
        success, msg = self.acquire()
        if not success:
            raise RuntimeError(msg)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()

    @property
    def is_acquired(self) -> bool:
        """Check if lock is currently held by this instance."""
        return self._acquired
