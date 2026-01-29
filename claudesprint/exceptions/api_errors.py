"""API and model interaction exceptions for ClaudeSprint.

These exceptions handle errors from external API calls,
including rate limiting, authentication, and model errors.
"""

from typing import Any

from claudesprint.exceptions.base import ClaudeSprintError


class ApiError(ClaudeSprintError):
    """Base class for API-related errors."""

    pass


class RateLimitExceeded(ApiError):
    """API rate limit has been exceeded.

    Raised when:
    - Claude API returns 429 status
    - Too many requests in a time window
    - Token quota exceeded

    This error typically requires waiting before retrying.
    """

    def __init__(
        self,
        message: str,
        retry_after: float | None = None,
        limit_type: str | None = None,
        **context: Any,
    ) -> None:
        """Initialize RateLimitExceeded.

        Args:
            message: Human-readable error description.
            retry_after: Seconds to wait before retrying.
            limit_type: Type of limit exceeded (requests, tokens, etc.)
            **context: Additional context.
        """
        if retry_after is not None:
            context["retry_after"] = retry_after
        if limit_type is not None:
            context["limit_type"] = limit_type
        super().__init__(message, **context)


class AuthenticationError(ApiError):
    """API authentication failed.

    Raised when:
    - API key is invalid or expired
    - Authentication token is missing
    - Insufficient permissions
    """

    def __init__(
        self,
        message: str,
        api_name: str | None = None,
        **context: Any,
    ) -> None:
        """Initialize AuthenticationError.

        Args:
            message: Human-readable error description.
            api_name: Name of the API that rejected authentication.
            **context: Additional context.
        """
        if api_name is not None:
            context["api_name"] = api_name
        super().__init__(message, **context)


class ModelError(ApiError):
    """Error from the AI model.

    Raised when:
    - Model returns an error response
    - Model output is malformed
    - Model refuses to complete the request
    - Context length exceeded
    """

    def __init__(
        self,
        message: str,
        model: str | None = None,
        error_code: str | None = None,
        **context: Any,
    ) -> None:
        """Initialize ModelError.

        Args:
            message: Human-readable error description.
            model: Model identifier that caused the error.
            error_code: API error code if available.
            **context: Additional context.
        """
        if model is not None:
            context["model"] = model
        if error_code is not None:
            context["error_code"] = error_code
        super().__init__(message, **context)
