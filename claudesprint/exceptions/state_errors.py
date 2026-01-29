"""State management exceptions for ClaudeSprint.

These exceptions handle errors related to sprint and issue state,
including corruption detection, invalid transitions, and checkpoint failures.
"""

from typing import Any

from claudesprint.exceptions.base import ClaudeSprintError


class StateError(ClaudeSprintError):
    """Base class for state management errors."""

    pass


class StateCorruptionError(StateError):
    """State data is corrupted or inconsistent.

    Raised when:
    - Checksum verification fails
    - State files contain invalid data
    - Sprint and current_issue states are inconsistent
    """

    def __init__(
        self,
        message: str,
        expected_checksum: str | None = None,
        actual_checksum: str | None = None,
        **context: Any,
    ) -> None:
        """Initialize StateCorruptionError.

        Args:
            message: Human-readable error description.
            expected_checksum: Expected checksum value.
            actual_checksum: Actual checksum found.
            **context: Additional context.
        """
        if expected_checksum is not None:
            context["expected_checksum"] = expected_checksum
        if actual_checksum is not None:
            context["actual_checksum"] = actual_checksum
        super().__init__(message, **context)


class InvalidStateTransition(StateError):
    """Attempted invalid state transition.

    Raised when:
    - Issue transition violates workflow rules
    - Step transition is not allowed
    - State machine encounters invalid state
    """

    def __init__(
        self,
        message: str,
        from_state: str | None = None,
        to_state: str | None = None,
        allowed_transitions: list[str] | None = None,
        **context: Any,
    ) -> None:
        """Initialize InvalidStateTransition.

        Args:
            message: Human-readable error description.
            from_state: Current state.
            to_state: Attempted target state.
            allowed_transitions: List of valid target states.
            **context: Additional context.
        """
        if from_state is not None:
            context["from_state"] = from_state
        if to_state is not None:
            context["to_state"] = to_state
        if allowed_transitions is not None:
            context["allowed_transitions"] = allowed_transitions
        super().__init__(message, **context)


class CheckpointError(StateError):
    """Error creating or restoring a checkpoint.

    Raised when:
    - Checkpoint file cannot be written
    - Checkpoint file is corrupted
    - Checkpoint restore fails validation
    """

    def __init__(
        self,
        message: str,
        checkpoint_path: str | None = None,
        checkpoint_id: str | None = None,
        **context: Any,
    ) -> None:
        """Initialize CheckpointError.

        Args:
            message: Human-readable error description.
            checkpoint_path: Path to the checkpoint file.
            checkpoint_id: Identifier for the checkpoint.
            **context: Additional context.
        """
        if checkpoint_path is not None:
            context["checkpoint_path"] = checkpoint_path
        if checkpoint_id is not None:
            context["checkpoint_id"] = checkpoint_id
        super().__init__(message, **context)
