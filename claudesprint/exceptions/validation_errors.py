"""Validation exceptions for ClaudeSprint.

These exceptions handle validation failures for configuration,
issues, sprints, and other data structures.
"""

from typing import Any

from claudesprint.exceptions.base import ClaudeSprintError


class ValidationError(ClaudeSprintError):
    """Base class for validation errors."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        value: Any = None,
        **context: Any,
    ) -> None:
        """Initialize ValidationError.

        Args:
            message: Human-readable error description.
            field: Name of the field that failed validation.
            value: The invalid value (may be truncated for large values).
            **context: Additional context.
        """
        if field is not None:
            context["field"] = field
        if value is not None:
            # Truncate large values for readability
            str_value = str(value)
            if len(str_value) > 100:
                str_value = str_value[:100] + "..."
            context["value"] = str_value
        super().__init__(message, **context)


class ConfigValidationError(ValidationError):
    """Configuration validation failed.

    Raised when:
    - Required config field is missing
    - Config value is invalid type
    - Config value is out of range
    """

    def __init__(
        self,
        message: str,
        config_file: str | None = None,
        **context: Any,
    ) -> None:
        """Initialize ConfigValidationError.

        Args:
            message: Human-readable error description.
            config_file: Path to the configuration file.
            **context: Additional context including field and value.
        """
        if config_file is not None:
            context["config_file"] = config_file
        super().__init__(message, **context)


class IssueValidationError(ValidationError):
    """Issue data validation failed.

    Raised when:
    - Required issue field is missing
    - Issue ID format is invalid
    - Issue status is invalid
    - Issue references non-existent dependency
    """

    def __init__(
        self,
        message: str,
        issue_id: str | None = None,
        **context: Any,
    ) -> None:
        """Initialize IssueValidationError.

        Args:
            message: Human-readable error description.
            issue_id: ID of the issue that failed validation.
            **context: Additional context including field and value.
        """
        if issue_id is not None:
            context["issue_id"] = issue_id
        super().__init__(message, **context)


class SprintValidationError(ValidationError):
    """Sprint data validation failed.

    Raised when:
    - Required sprint field is missing
    - Sprint structure is invalid
    - Sprint references invalid spec file
    - Sprint issues are malformed
    """

    def __init__(
        self,
        message: str,
        sprint_path: str | None = None,
        spec_id: str | None = None,
        **context: Any,
    ) -> None:
        """Initialize SprintValidationError.

        Args:
            message: Human-readable error description.
            sprint_path: Path to the sprint file.
            spec_id: Spec ID for the sprint.
            **context: Additional context including field and value.
        """
        if sprint_path is not None:
            context["sprint_path"] = sprint_path
        if spec_id is not None:
            context["spec_id"] = spec_id
        super().__init__(message, **context)
