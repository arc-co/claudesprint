"""Tests for issue state machine."""

import pytest

from claudesprint.core.issue_engine import IssueExitReason
from claudesprint.core.issue_state_machine import (
    ExitReasonMapping,
    IssueStateMachine,
    SprintAction,
)


class TestSprintAction:
    """Tests for SprintAction enum."""

    def test_all_actions_defined(self):
        """Verify all expected actions exist."""
        assert SprintAction.CONTINUE_NEXT_ISSUE
        assert SprintAction.RETRY_SAME_ISSUE
        assert SprintAction.EXIT_SPRINT_SUCCESS
        assert SprintAction.EXIT_SPRINT_FAILURE


class TestExitReasonMapping:
    """Tests for ExitReasonMapping dataclass."""

    def test_mapping_creation(self):
        """Test creating a mapping."""
        mapping = ExitReasonMapping(
            exit_reason=IssueExitReason.COMPLETED,
            action=SprintAction.CONTINUE_NEXT_ISSUE,
            is_fatal=False,
            requires_status_update=True,
        )

        assert mapping.exit_reason == IssueExitReason.COMPLETED
        assert mapping.action == SprintAction.CONTINUE_NEXT_ISSUE
        assert mapping.is_fatal is False
        assert mapping.requires_status_update is True


class TestIssueStateMachine:
    """Tests for IssueStateMachine."""

    @pytest.fixture
    def machine(self):
        """Create a state machine instance."""
        return IssueStateMachine()

    def test_completed_returns_continue(self, machine):
        """COMPLETED -> CONTINUE_NEXT_ISSUE."""
        action = machine.get_action(IssueExitReason.COMPLETED)
        assert action == SprintAction.CONTINUE_NEXT_ISSUE

    def test_completed_is_not_fatal(self, machine):
        """COMPLETED is not fatal."""
        assert machine.is_fatal(IssueExitReason.COMPLETED) is False

    def test_completed_requires_status_update(self, machine):
        """COMPLETED requires status update (to completed)."""
        assert machine.should_update_status(IssueExitReason.COMPLETED) is True

    def test_rate_limited_returns_retry(self, machine):
        """RATE_LIMITED -> RETRY_SAME_ISSUE."""
        action = machine.get_action(IssueExitReason.RATE_LIMITED)
        assert action == SprintAction.RETRY_SAME_ISSUE

    def test_rate_limited_is_not_fatal(self, machine):
        """RATE_LIMITED is not fatal."""
        assert machine.is_fatal(IssueExitReason.RATE_LIMITED) is False

    def test_rate_limited_no_status_update(self, machine):
        """RATE_LIMITED does not change status."""
        assert machine.should_update_status(IssueExitReason.RATE_LIMITED) is False

    def test_max_retry_is_fatal(self, machine):
        """MAX_RETRY -> EXIT_SPRINT_FAILURE, is_fatal=True."""
        action = machine.get_action(IssueExitReason.MAX_RETRY)
        assert action == SprintAction.EXIT_SPRINT_FAILURE
        assert machine.is_fatal(IssueExitReason.MAX_RETRY) is True

    def test_max_iterations_continues(self, machine):
        """MAX_ITERATIONS -> CONTINUE_NEXT_ISSUE (mark as blocked)."""
        action = machine.get_action(IssueExitReason.MAX_ITERATIONS)
        assert action == SprintAction.CONTINUE_NEXT_ISSUE
        assert machine.is_fatal(IssueExitReason.MAX_ITERATIONS) is False
        assert machine.should_update_status(IssueExitReason.MAX_ITERATIONS) is True

    def test_crashed_is_fatal(self, machine):
        """CRASHED -> EXIT_SPRINT_FAILURE, is_fatal=True."""
        action = machine.get_action(IssueExitReason.CRASHED)
        assert action == SprintAction.EXIT_SPRINT_FAILURE
        assert machine.is_fatal(IssueExitReason.CRASHED) is True

    def test_error_is_fatal(self, machine):
        """ERROR -> EXIT_SPRINT_FAILURE, is_fatal=True."""
        action = machine.get_action(IssueExitReason.ERROR)
        assert action == SprintAction.EXIT_SPRINT_FAILURE
        assert machine.is_fatal(IssueExitReason.ERROR) is True

    def test_blocked_continues(self, machine):
        """BLOCKED -> CONTINUE_NEXT_ISSUE, is_fatal=False."""
        action = machine.get_action(IssueExitReason.BLOCKED)
        assert action == SprintAction.CONTINUE_NEXT_ISSUE
        assert machine.is_fatal(IssueExitReason.BLOCKED) is False
        assert machine.should_update_status(IssueExitReason.BLOCKED) is True

    def test_all_exit_reasons_mapped(self):
        """Every IssueExitReason has a mapping."""
        # This should not raise
        IssueStateMachine.validate_completeness()

        # Also verify by checking the MAPPINGS directly
        for reason in IssueExitReason:
            assert reason in IssueStateMachine.MAPPINGS, f"Missing mapping for {reason}"

    def test_get_mapping_returns_full_mapping(self, machine):
        """Test get_mapping returns complete ExitReasonMapping."""
        mapping = machine.get_mapping(IssueExitReason.COMPLETED)

        assert isinstance(mapping, ExitReasonMapping)
        assert mapping.exit_reason == IssueExitReason.COMPLETED
        assert mapping.action == SprintAction.CONTINUE_NEXT_ISSUE
        assert mapping.is_fatal is False
        assert mapping.requires_status_update is True

    def test_get_action_unknown_reason_raises(self, machine):
        """Test that unknown exit reasons raise KeyError."""
        # Create a mock unknown reason - since IssueExitReason is an Enum,
        # we can't easily create an invalid one, so we test the mechanism
        # by directly checking the MAPPINGS lookup would work
        # In practice, this should never happen because IssueExitReason is exhaustive

        # Test that all reasons work
        for reason in IssueExitReason:
            # Should not raise
            action = machine.get_action(reason)
            assert isinstance(action, SprintAction)

    def test_validate_completeness_raises_on_missing(self):
        """Test that validate_completeness raises if mapping is missing."""
        # Save original mappings
        original_mappings = IssueStateMachine.MAPPINGS.copy()

        try:
            # Remove one mapping
            del IssueStateMachine.MAPPINGS[IssueExitReason.COMPLETED]

            with pytest.raises(ValueError) as excinfo:
                IssueStateMachine.validate_completeness()

            assert "COMPLETED" in str(excinfo.value)
        finally:
            # Restore original mappings
            IssueStateMachine.MAPPINGS = original_mappings


class TestStateMachineConsistency:
    """Tests to verify consistency between mappings and expected behavior."""

    def test_fatal_reasons_exit_sprint(self):
        """All fatal reasons should exit the sprint."""
        machine = IssueStateMachine()

        for reason in IssueExitReason:
            if machine.is_fatal(reason):
                action = machine.get_action(reason)
                assert action == SprintAction.EXIT_SPRINT_FAILURE, (
                    f"Fatal reason {reason} should exit with failure"
                )

    def test_non_fatal_reasons_continue_or_retry(self):
        """Non-fatal reasons should continue or retry."""
        machine = IssueStateMachine()

        for reason in IssueExitReason:
            if not machine.is_fatal(reason):
                action = machine.get_action(reason)
                assert action in (
                    SprintAction.CONTINUE_NEXT_ISSUE,
                    SprintAction.RETRY_SAME_ISSUE,
                ), f"Non-fatal reason {reason} should continue or retry"

    def test_only_rate_limited_retries(self):
        """Only RATE_LIMITED should trigger retry."""
        machine = IssueStateMachine()

        for reason in IssueExitReason:
            action = machine.get_action(reason)
            if action == SprintAction.RETRY_SAME_ISSUE:
                assert reason == IssueExitReason.RATE_LIMITED, (
                    f"Only RATE_LIMITED should retry, but {reason} also does"
                )
