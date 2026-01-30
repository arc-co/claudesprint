"""ClaudeSprint exception hierarchy.

This package provides a typed exception hierarchy for ClaudeSprint,
enabling specific error handling and better debugging.

Exception Hierarchy:
    ClaudeSprintError (base)
    ├── FileOperationError
    │   ├── FileReadError
    │   ├── FileWriteError
    │   └── FileLockError
    ├── StateError
    │   ├── StateCorruptionError
    │   ├── InvalidStateTransition
    │   └── CheckpointError
    ├── ApiError
    │   ├── RateLimitExceeded
    │   ├── AuthenticationError
    │   └── ModelError
    └── ValidationError
        ├── ConfigValidationError
        ├── IssueValidationError
        └── SprintValidationError

Usage:
    from claudesprint.exceptions import FileReadError, FileWriteError

    try:
        data = load_sprint(path)
    except FileReadError as e:
        logger.error(f"Failed to read sprint: {e.context}")
"""

# Base exception
from claudesprint.exceptions.base import ClaudeSprintError

# File errors
from claudesprint.exceptions.file_errors import (
    FileOperationError,
    FileReadError,
    FileWriteError,
    FileLockError,
)

# State errors
from claudesprint.exceptions.state_errors import (
    StateError,
    StateCorruptionError,
    InvalidStateTransition,
    CheckpointError,
)

# API errors
from claudesprint.exceptions.api_errors import (
    ApiError,
    RateLimitExceeded,
    RateLimitDetected,
    AuthenticationError,
    ModelError,
)

# Validation errors
from claudesprint.exceptions.validation_errors import (
    ValidationError,
    ConfigValidationError,
    IssueValidationError,
    SprintValidationError,
)

# Decorators
from claudesprint.exceptions.decorators import (
    handle_file_errors,
    log_exceptions,
)

__all__ = [
    # Base
    "ClaudeSprintError",
    # File errors
    "FileOperationError",
    "FileReadError",
    "FileWriteError",
    "FileLockError",
    # State errors
    "StateError",
    "StateCorruptionError",
    "InvalidStateTransition",
    "CheckpointError",
    # API errors
    "ApiError",
    "RateLimitExceeded",
    "RateLimitDetected",
    "AuthenticationError",
    "ModelError",
    # Validation errors
    "ValidationError",
    "ConfigValidationError",
    "IssueValidationError",
    "SprintValidationError",
    # Decorators
    "handle_file_errors",
    "log_exceptions",
]
