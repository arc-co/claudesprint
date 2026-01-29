"""Decorators for exception handling in ClaudeSprint.

These decorators convert standard Python exceptions to typed ClaudeSprint
exceptions, providing consistent error handling across the codebase.
"""

import functools
import logging
from pathlib import Path
from typing import Any, Callable, ParamSpec, TypeVar

from claudesprint.exceptions.file_errors import (
    FileReadError,
    FileWriteError,
    FileOperationError,
)

P = ParamSpec("P")
R = TypeVar("R")

logger = logging.getLogger(__name__)


def handle_file_errors(
    operation: str = "file operation",
    path_arg: str | int | None = None,
    reraise: bool = True,
    default: R | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to convert standard file exceptions to ClaudeSprint exceptions.

    Converts:
    - FileNotFoundError -> FileReadError
    - PermissionError -> FileReadError or FileWriteError (based on operation)
    - IsADirectoryError -> FileReadError
    - NotADirectoryError -> FileWriteError
    - OSError -> FileOperationError

    Args:
        operation: Description of the operation ("read", "write", or custom).
        path_arg: Name or index of the path argument for context.
            If string, looks for keyword arg with that name.
            If int, uses positional arg at that index.
            If None, tries to find 'path' or 'file_path' in kwargs.
        reraise: If True, re-raises as typed exception. If False, returns default.
        default: Value to return if reraise is False and an error occurs.

    Returns:
        Decorated function that handles file exceptions.

    Example:
        @handle_file_errors(operation="read", path_arg="path")
        def read_config(path: Path) -> dict:
            return json.loads(path.read_text())
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            # Extract path for error context
            file_path: str | None = None

            if path_arg is not None:
                if isinstance(path_arg, int) and len(args) > path_arg:
                    file_path = str(args[path_arg])
                elif isinstance(path_arg, str) and path_arg in kwargs:
                    file_path = str(kwargs[path_arg])

            # Try common path argument names if not specified
            if file_path is None:
                for name in ("path", "file_path", "filepath"):
                    if name in kwargs:
                        file_path = str(kwargs[name])
                        break

            try:
                return func(*args, **kwargs)

            except FileNotFoundError as e:
                msg = f"File not found: {file_path or e.filename or 'unknown'}"
                logger.warning(msg)
                if reraise:
                    raise FileReadError(msg, path=file_path or e.filename) from e
                return default  # type: ignore[return-value]

            except PermissionError as e:
                is_write = operation.lower() in ("write", "create", "delete", "remove")
                msg = f"Permission denied: {file_path or e.filename or 'unknown'}"
                logger.warning(msg)
                if reraise:
                    if is_write:
                        raise FileWriteError(msg, path=file_path or e.filename) from e
                    raise FileReadError(msg, path=file_path or e.filename) from e
                return default  # type: ignore[return-value]

            except IsADirectoryError as e:
                msg = f"Expected file, got directory: {file_path or 'unknown'}"
                logger.warning(msg)
                if reraise:
                    raise FileReadError(msg, path=file_path) from e
                return default  # type: ignore[return-value]

            except NotADirectoryError as e:
                msg = f"Parent is not a directory: {file_path or 'unknown'}"
                logger.warning(msg)
                if reraise:
                    raise FileWriteError(msg, path=file_path) from e
                return default  # type: ignore[return-value]

            except OSError as e:
                msg = f"File operation failed: {e}"
                logger.warning(f"{msg} (path={file_path})")
                if reraise:
                    raise FileOperationError(
                        msg, path=file_path, operation=operation
                    ) from e
                return default  # type: ignore[return-value]

        return wrapper

    return decorator


def log_exceptions(
    logger_name: str | None = None,
    level: int = logging.WARNING,
    message: str | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to log exceptions without modifying them.

    Logs the exception and re-raises it unchanged. Useful for adding
    visibility to exception handling without changing behavior.

    Args:
        logger_name: Name for the logger. If None, uses module name.
        level: Logging level for the exception message.
        message: Custom message prefix. If None, uses function name.

    Returns:
        Decorated function that logs exceptions.
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        log = logging.getLogger(logger_name or func.__module__)

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                prefix = message or f"{func.__name__} failed"
                log.log(level, f"{prefix}: {e}")
                raise

        return wrapper

    return decorator
