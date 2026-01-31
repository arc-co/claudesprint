"""Lock file management to prevent concurrent instances."""

import logging
import os
import signal
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# fcntl is Unix-only; use msvcrt on Windows
_IS_WINDOWS = sys.platform == "win32"

if _IS_WINDOWS:
    import msvcrt
else:
    import fcntl


class LockFile:
    """Atomic file lock to prevent TOCTOU races.

    On Unix, uses fcntl.flock for kernel-level file locking.
    On Windows, uses msvcrt.locking for file locking.
    Falls back to PID-based detection for stale lock identification.
    """

    def __init__(self, lock_path: str | Path) -> None:
        self.lock_path = Path(lock_path)
        self._acquired = False
        self._lock_fd: int | None = None

    def acquire(self) -> tuple[bool, str]:
        """Attempt to acquire the lock atomically.

        Uses platform-appropriate locking mechanism for atomic lock acquisition,
        eliminating TOCTOU race conditions.

        Returns:
            Tuple of (success, message). If another process holds the lock,
            returns (False, error message with PID).
        """
        try:
            # Ensure parent directory exists
            self.lock_path.parent.mkdir(parents=True, exist_ok=True)

            # Open file for writing (creates if doesn't exist)
            self._lock_fd = os.open(
                str(self.lock_path),
                os.O_RDWR | os.O_CREAT,
                0o644,
            )

            # Try to acquire exclusive lock (non-blocking)
            try:
                if _IS_WINDOWS:
                    # On Windows, use msvcrt.locking with LK_NBLCK (non-blocking)
                    msvcrt.locking(self._lock_fd, msvcrt.LK_NBLCK, 1)
                else:
                    fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                # Lock is held by another process
                # Try to read the PID for a better error message
                try:
                    os.lseek(self._lock_fd, 0, os.SEEK_SET)
                    content = os.read(self._lock_fd, 32).decode().strip()
                    pid = int(content) if content else "unknown"
                except (ValueError, OSError):
                    pid = "unknown"

                os.close(self._lock_fd)
                self._lock_fd = None
                return False, f"Another instance is running (PID: {pid})"

            # We have the lock - write our PID
            os.ftruncate(self._lock_fd, 0)
            os.lseek(self._lock_fd, 0, os.SEEK_SET)
            os.write(self._lock_fd, str(os.getpid()).encode())

            self._acquired = True
            return True, ""

        except OSError as e:
            if self._lock_fd is not None:
                try:
                    os.close(self._lock_fd)
                except OSError as close_err:
                    logger.debug("Failed to close file descriptor during lock acquisition error: %s", close_err)
                self._lock_fd = None
            return False, f"Failed to acquire lock: {e}"

    def release(self) -> bool:
        """Release the lock."""
        if not self._acquired or self._lock_fd is None:
            return False

        try:
            # Unlock and close the file descriptor
            if _IS_WINDOWS:
                # Seek to beginning and unlock the byte we locked
                os.lseek(self._lock_fd, 0, os.SEEK_SET)
                msvcrt.locking(self._lock_fd, msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
            os.close(self._lock_fd)
            self._lock_fd = None

            # Remove the lock file
            try:
                self.lock_path.unlink()
            except OSError as e:
                logger.debug("Failed to remove lock file during release: %s", e)

            self._acquired = False
            return True
        except OSError:
            return False

    def _is_process_running(self, pid: int) -> bool:
        """Check if a process with the given PID is running."""
        try:
            os.kill(pid, 0)
            return True
        except OSError:
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


class CleanupHandler:
    """Handler for graceful cleanup on signals."""

    def __init__(self, lock: LockFile, cleanup_files: list[Path] | None = None) -> None:
        self.lock = lock
        self.cleanup_files = cleanup_files or []
        self._original_handlers: dict[int, signal.Handlers] = {}

    def install(self) -> None:
        """Install signal handlers for graceful cleanup."""
        # SIGHUP doesn't exist on Windows
        signals = [signal.SIGINT, signal.SIGTERM]
        if not _IS_WINDOWS:
            signals.append(signal.SIGHUP)
        for sig in signals:
            self._original_handlers[sig] = signal.signal(sig, self._handle_signal)

    def uninstall(self) -> None:
        """Restore original signal handlers."""
        for sig, handler in self._original_handlers.items():
            signal.signal(sig, handler)
        self._original_handlers.clear()

    def _handle_signal(self, signum: int, frame) -> None:
        """Handle cleanup on signal."""
        self.cleanup()
        # Re-raise the signal to exit with proper code
        signal.signal(signum, signal.SIG_DFL)
        os.kill(os.getpid(), signum)

    def cleanup(self) -> None:
        """Perform cleanup operations."""
        # Release lock
        self.lock.release()

        # Remove cleanup files
        for path in self.cleanup_files:
            try:
                if path.exists():
                    path.unlink()
            except OSError as e:
                logger.debug("Failed to remove cleanup file %s: %s", path, e)
