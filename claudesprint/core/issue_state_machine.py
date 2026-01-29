"""Issue state machine for sprint engine result handling.

Maps IssueExitReason to SprintAction to determine what the sprint
engine should do after an issue completes.
"""

from dataclasses import dataclass
from enum import Enum, auto

from claudesprint.core.issue_engine import IssueExitReason


class SprintAction(Enum):
    """Actions the sprint engine should take based on issue result."""

    CONTINUE_NEXT_ISSUE = auto()  # Mark complete/blocked, move to next issue
    RETRY_SAME_ISSUE = auto()  # Rate limited, retry after backoff
    EXIT_SPRINT_SUCCESS = auto()  # All done successfully
    EXIT_SPRINT_FAILURE = auto()  # Fatal error, stop sprint


@dataclass
class ExitReasonMapping:
    """Mapping from IssueExitReason to sprint behavior."""

    exit_reason: IssueExitReason
    action: SprintAction
    is_fatal: bool
    requires_status_update: bool


class IssueStateMachine:
    """State machine for handling issue exit reasons.

    Maps IssueExitReason values to SprintAction decisions,
    replacing the match-case block in SprintEngine.run().

    Example:
        machine = IssueStateMachine()
        action = machine.get_action(IssueExitReason.COMPLETED)
        if action == SprintAction.CONTINUE_NEXT_ISSUE:
            # mark complete and move on
    """

    # Static mapping of exit reasons to their behaviors
    MAPPINGS: dict[IssueExitReason, ExitReasonMapping] = {
        IssueExitReason.COMPLETED: ExitReasonMapping(
            exit_reason=IssueExitReason.COMPLETED,
            action=SprintAction.CONTINUE_NEXT_ISSUE,
            is_fatal=False,
            requires_status_update=True,  # Mark as completed
        ),
        IssueExitReason.RATE_LIMITED: ExitReasonMapping(
            exit_reason=IssueExitReason.RATE_LIMITED,
            action=SprintAction.RETRY_SAME_ISSUE,
            is_fatal=False,
            requires_status_update=False,  # Keep as in_progress
        ),
        IssueExitReason.MAX_RETRY: ExitReasonMapping(
            exit_reason=IssueExitReason.MAX_RETRY,
            action=SprintAction.EXIT_SPRINT_FAILURE,
            is_fatal=True,
            requires_status_update=False,  # Leave as in_progress for investigation
        ),
        IssueExitReason.MAX_ITERATIONS: ExitReasonMapping(
            exit_reason=IssueExitReason.MAX_ITERATIONS,
            action=SprintAction.CONTINUE_NEXT_ISSUE,
            is_fatal=False,
            requires_status_update=True,  # Mark as blocked
        ),
        IssueExitReason.CRASHED: ExitReasonMapping(
            exit_reason=IssueExitReason.CRASHED,
            action=SprintAction.EXIT_SPRINT_FAILURE,
            is_fatal=True,
            requires_status_update=False,
        ),
        IssueExitReason.BLOCKED: ExitReasonMapping(
            exit_reason=IssueExitReason.BLOCKED,
            action=SprintAction.CONTINUE_NEXT_ISSUE,
            is_fatal=False,
            requires_status_update=True,  # Mark as blocked
        ),
        IssueExitReason.ERROR: ExitReasonMapping(
            exit_reason=IssueExitReason.ERROR,
            action=SprintAction.EXIT_SPRINT_FAILURE,
            is_fatal=True,
            requires_status_update=False,
        ),
    }

    def get_action(self, exit_reason: IssueExitReason) -> SprintAction:
        """Get the sprint action for an exit reason.

        Args:
            exit_reason: The issue exit reason to look up.

        Returns:
            The SprintAction to take.

        Raises:
            KeyError: If exit_reason is not mapped (should never happen
                      if all IssueExitReason values are in MAPPINGS).
        """
        mapping = self.MAPPINGS.get(exit_reason)
        if mapping is None:
            raise KeyError(f"No mapping for exit reason: {exit_reason}")
        return mapping.action

    def is_fatal(self, exit_reason: IssueExitReason) -> bool:
        """Check if an exit reason is fatal (should stop the sprint).

        Args:
            exit_reason: The issue exit reason to check.

        Returns:
            True if the exit reason should stop the sprint.

        Raises:
            KeyError: If exit_reason is not mapped.
        """
        mapping = self.MAPPINGS.get(exit_reason)
        if mapping is None:
            raise KeyError(f"No mapping for exit reason: {exit_reason}")
        return mapping.is_fatal

    def should_update_status(self, exit_reason: IssueExitReason) -> bool:
        """Check if the issue status should be updated for this exit reason.

        Args:
            exit_reason: The issue exit reason to check.

        Returns:
            True if the issue status should be updated in sprint.json.

        Raises:
            KeyError: If exit_reason is not mapped.
        """
        mapping = self.MAPPINGS.get(exit_reason)
        if mapping is None:
            raise KeyError(f"No mapping for exit reason: {exit_reason}")
        return mapping.requires_status_update

    def get_mapping(self, exit_reason: IssueExitReason) -> ExitReasonMapping:
        """Get the full mapping for an exit reason.

        Args:
            exit_reason: The issue exit reason to look up.

        Returns:
            The ExitReasonMapping with all behavior details.

        Raises:
            KeyError: If exit_reason is not mapped.
        """
        mapping = self.MAPPINGS.get(exit_reason)
        if mapping is None:
            raise KeyError(f"No mapping for exit reason: {exit_reason}")
        return mapping

    @classmethod
    def validate_completeness(cls) -> bool:
        """Validate that all IssueExitReason values have mappings.

        Returns:
            True if all exit reasons are mapped.

        Raises:
            ValueError: If any exit reason is missing from MAPPINGS.
        """
        missing = []
        for reason in IssueExitReason:
            if reason not in cls.MAPPINGS:
                missing.append(reason)

        if missing:
            raise ValueError(f"Missing mappings for exit reasons: {missing}")

        return True
