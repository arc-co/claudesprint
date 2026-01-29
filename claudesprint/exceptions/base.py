"""Base exception class for ClaudeSprint.

All ClaudeSprint exceptions inherit from ClaudeSprintError, which carries
context information for debugging and error reporting.
"""

from typing import Any


class ClaudeSprintError(Exception):
    """Base exception for all ClaudeSprint errors.

    Carries context information about the error for debugging and logging.

    Attributes:
        message: Human-readable error message.
        context: Dictionary of contextual information (file path, operation, etc.)
    """

    def __init__(self, message: str, **context: Any) -> None:
        """Initialize ClaudeSprintError.

        Args:
            message: Human-readable error description.
            **context: Additional context (path, operation, etc.)
        """
        self.message = message
        self.context = context
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format the full error message including context."""
        if not self.context:
            return self.message
        context_str = ", ".join(f"{k}={v!r}" for k, v in self.context.items())
        return f"{self.message} [{context_str}]"

    def __repr__(self) -> str:
        """Return detailed representation for debugging."""
        context_args = ", ".join(f"{k}={v!r}" for k, v in self.context.items())
        if context_args:
            return f"{self.__class__.__name__}({self.message!r}, {context_args})"
        return f"{self.__class__.__name__}({self.message!r})"
