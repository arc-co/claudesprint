"""File operation exceptions for ClaudeSprint.

These exceptions wrap standard file I/O errors to provide consistent
error handling and additional context about failed operations.
"""

from pathlib import Path
from typing import Any

from claudesprint.exceptions.base import ClaudeSprintError


class FileOperationError(ClaudeSprintError):
    """Base class for file operation errors."""

    def __init__(
        self,
        message: str,
        path: str | Path | None = None,
        operation: str | None = None,
        **context: Any,
    ) -> None:
        """Initialize FileOperationError.

        Args:
            message: Human-readable error description.
            path: File path involved in the error.
            operation: Operation that failed (read, write, delete, etc.)
            **context: Additional context.
        """
        if path is not None:
            context["path"] = str(path)
        if operation is not None:
            context["operation"] = operation
        super().__init__(message, **context)


class FileReadError(FileOperationError):
    """Error reading a file.

    Raised when a file cannot be read due to:
    - File not found
    - Permission denied
    - Encoding issues
    - Corrupted content
    """

    def __init__(
        self,
        message: str,
        path: str | Path | None = None,
        **context: Any,
    ) -> None:
        """Initialize FileReadError.

        Args:
            message: Human-readable error description.
            path: File path that could not be read.
            **context: Additional context.
        """
        super().__init__(message, path=path, operation="read", **context)


class FileWriteError(FileOperationError):
    """Error writing a file.

    Raised when a file cannot be written due to:
    - Permission denied
    - Disk full
    - Parent directory doesn't exist
    - Atomic rename failure
    """

    def __init__(
        self,
        message: str,
        path: str | Path | None = None,
        **context: Any,
    ) -> None:
        """Initialize FileWriteError.

        Args:
            message: Human-readable error description.
            path: File path that could not be written.
            **context: Additional context.
        """
        super().__init__(message, path=path, operation="write", **context)


class FileLockError(FileOperationError):
    """Error acquiring or releasing a file lock.

    Raised when:
    - Lock acquisition times out
    - Another process holds the lock
    - Lock file cannot be created
    """

    def __init__(
        self,
        message: str,
        path: str | Path | None = None,
        holder_pid: int | None = None,
        **context: Any,
    ) -> None:
        """Initialize FileLockError.

        Args:
            message: Human-readable error description.
            path: Lock file path.
            holder_pid: PID of the process holding the lock, if known.
            **context: Additional context.
        """
        if holder_pid is not None:
            context["holder_pid"] = holder_pid
        super().__init__(message, path=path, operation="lock", **context)
