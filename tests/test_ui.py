"""Tests for the ClaudeSprint dashboard UI module."""

import pytest
from rich.console import Group

from claudesprint.models.current_issue import IssueStep
from claudesprint.ui import WorkflowDashboard, StepStatus, DashboardState, SubprocessInfo


@pytest.fixture
def dashboard():
    """Create a fresh dashboard instance."""
    return WorkflowDashboard()


class TestDashboardState:
    """Tests for DashboardState initialization and defaults."""

    def test_default_state(self):
        """Test default state values."""
        state = DashboardState()
        assert state.spec_id == ""
        assert state.total_issues == 0
        assert state.completed_issues == 0
        assert state.issue_id == ""
        assert state.phase == "planning"
        assert state.log_lines == []
        assert state.step_statuses == {}


class TestResetStepStatuses:
    """Tests for _reset_step_statuses method."""

    def test_reset_step_statuses(self, dashboard):
        """All steps should be reset to pending status."""
        dashboard._reset_step_statuses()

        for step in IssueStep.ordered_steps():
            assert dashboard.state.step_statuses[step] == StepStatus.PENDING

    def test_reset_clears_previous_statuses(self, dashboard):
        """Reset should clear any previous status values."""
        # Set some steps to non-pending
        dashboard.state.step_statuses[IssueStep.IMPLEMENT] = StepStatus.DONE
        dashboard.state.step_statuses[IssueStep.RUN_TESTS] = StepStatus.FAILED

        dashboard._reset_step_statuses()

        assert dashboard.state.step_statuses[IssueStep.IMPLEMENT] == StepStatus.PENDING
        assert dashboard.state.step_statuses[IssueStep.RUN_TESTS] == StepStatus.PENDING


class TestSetIssue:
    """Tests for set_issue method."""

    def test_set_issue_changes_phase(self, dashboard):
        """Setting an issue should change phase to executing."""
        assert dashboard.state.phase == "planning"

        dashboard.set_issue("issue-001", "Test issue")

        assert dashboard.state.phase == "executing"
        assert dashboard.state.issue_id == "issue-001"
        assert dashboard.state.issue_title == "Test issue"

    def test_set_issue_resets_steps(self, dashboard):
        """Setting a new issue should reset all step statuses."""
        # Mark some steps as done
        dashboard.state.step_statuses[IssueStep.IMPLEMENT] = StepStatus.DONE

        dashboard.set_issue("issue-002", "Another issue")

        assert dashboard.state.step_statuses[IssueStep.IMPLEMENT] == StepStatus.PENDING

    def test_set_issue_resets_retry_count(self, dashboard):
        """Setting a new issue should reset retry count."""
        dashboard.state.retry_count = 5

        dashboard.set_issue("issue-001", "Test issue")

        assert dashboard.state.retry_count == 0

    def test_set_issue_clears_activity_log(self, dashboard):
        """Setting a new issue should clear activity log from previous issue."""
        # Add some activity from a previous issue
        dashboard.add_log_line("Previous step completed")
        dashboard.add_log_line("Another step completed")
        assert len(dashboard.state.log_lines) == 2

        # Start a new issue
        dashboard.set_issue("issue-002", "New issue")

        # Activity log should be cleared for new issue
        assert len(dashboard.state.log_lines) == 0


class TestClearIssue:
    """Tests for clear_issue method."""

    def test_clear_issue_returns_to_planning(self, dashboard):
        """Clearing issue should return to planning phase."""
        dashboard.set_issue("issue-001", "Test issue")
        assert dashboard.state.phase == "executing"

        dashboard.clear_issue()

        assert dashboard.state.phase == "planning"
        assert dashboard.state.issue_id == ""
        assert dashboard.state.issue_title == ""

    def test_clear_issue_resets_current_step(self, dashboard):
        """Clearing issue should reset current step."""
        dashboard.set_issue("issue-001", "Test issue")
        dashboard.on_step_start(IssueStep.IMPLEMENT, "opus")

        dashboard.clear_issue()

        assert dashboard.state.current_step is None
        assert dashboard.state.current_model == ""


class TestOnStepStart:
    """Tests for on_step_start callback."""

    def test_on_step_start_updates_status(self, dashboard):
        """Starting a step should mark it as running."""
        dashboard.on_step_start(IssueStep.IMPLEMENT, "opus")

        assert dashboard.state.step_statuses[IssueStep.IMPLEMENT] == StepStatus.RUNNING
        assert dashboard.state.current_step == IssueStep.IMPLEMENT
        assert dashboard.state.current_model == "opus"

    def test_on_step_start_updates_message(self, dashboard):
        """Starting a step should update status message with step name."""
        dashboard.on_step_start(IssueStep.CODE_REVIEW, "sonnet")

        # New compact format just shows step name (model shown in spinner line)
        assert dashboard.state.status_message == "code-review"


class TestOnStepComplete:
    """Tests for on_step_complete callback."""

    def test_on_step_complete_marks_done(self, dashboard):
        """Completing a step should mark it as done."""
        dashboard.on_step_start(IssueStep.IMPLEMENT, "opus")
        dashboard.on_step_complete(IssueStep.IMPLEMENT, IssueStep.WRITE_TESTS)

        assert dashboard.state.step_statuses[IssueStep.IMPLEMENT] == StepStatus.DONE

    def test_on_step_complete_resets_retry_count(self, dashboard):
        """Completing a step should reset retry count."""
        dashboard.state.retry_count = 3

        dashboard.on_step_complete(IssueStep.IMPLEMENT, IssueStep.WRITE_TESTS)

        assert dashboard.state.retry_count == 0

    def test_on_step_complete_updates_message(self, dashboard):
        """Completing a step should update status message with next step."""
        dashboard.on_step_complete(IssueStep.IMPLEMENT, IssueStep.WRITE_TESTS)

        # New compact format just shows the next step
        assert dashboard.state.status_message == "write-tests"


class TestOnStepSkip:
    """Tests for on_step_skip callback."""

    def test_on_step_skip_marks_skipped(self, dashboard):
        """Skipping a step should mark it as skipped."""
        dashboard.on_step_skip(IssueStep.WRITE_TESTS, IssueStep.CODE_REVIEW)

        assert dashboard.state.step_statuses[IssueStep.WRITE_TESTS] == StepStatus.SKIPPED

    def test_on_step_skip_updates_message(self, dashboard):
        """Skipping a step should update status message with next step."""
        dashboard.on_step_skip(IssueStep.BROWSER_VALIDATION, IssueStep.CODE_REVIEW)

        # New compact format just shows the next step (skips are noted in log)
        assert dashboard.state.status_message == "code-review"

    def test_on_step_skip_logs_with_skip_symbol(self, dashboard):
        """Skipping a step should log with skip symbol (⏭)."""
        dashboard.on_step_skip(IssueStep.BROWSER_VALIDATION, IssueStep.CODE_REVIEW)

        # Should have logged the skip with ⏭ symbol
        assert len(dashboard.state.log_lines) == 1
        assert "⏭" in dashboard.state.log_lines[0]
        assert "browser-validation" in dashboard.state.log_lines[0]


class TestOnStepFailure:
    """Tests for on_step_failure callback."""

    def test_on_step_failure_marks_failed(self, dashboard):
        """Failing a step should mark it as failed."""
        dashboard.on_step_failure(IssueStep.RUN_TESTS, 1)

        assert dashboard.state.step_statuses[IssueStep.RUN_TESTS] == StepStatus.FAILED

    def test_on_step_failure_updates_retry_count(self, dashboard):
        """Failing a step should update retry count."""
        dashboard.on_step_failure(IssueStep.RUN_TESTS, 3)

        assert dashboard.state.retry_count == 3

    def test_on_step_failure_updates_message(self, dashboard):
        """Failing a step should update status message with retry count."""
        dashboard.on_step_failure(IssueStep.IMPLEMENT, 2)

        # New format shows step and retry count
        assert "implement" in dashboard.state.status_message
        assert "retry 2" in dashboard.state.status_message


class TestAddLogLine:
    """Tests for add_log_line method."""

    def test_add_log_line_limits_buffer(self, dashboard):
        """Log buffer should be limited to MAX_LOG_LINES."""
        max_lines = dashboard.MAX_LOG_LINES

        # Add more lines than the limit
        for i in range(max_lines + 10):
            dashboard.add_log_line(f"Line {i}")

        assert len(dashboard.state.log_lines) == max_lines

    def test_add_log_line_keeps_newest(self, dashboard):
        """Buffer should keep the newest lines when trimming."""
        max_lines = dashboard.MAX_LOG_LINES

        for i in range(max_lines + 5):
            dashboard.add_log_line(f"Line {i}")

        # The oldest lines should be removed
        assert "Line 5" in dashboard.state.log_lines[0]
        assert f"Line {max_lines + 4}" in dashboard.state.log_lines[-1]

    def test_add_log_line_handles_multiline(self, dashboard):
        """Multi-line strings should be split into separate entries."""
        dashboard.add_log_line("Line 1\nLine 2\nLine 3")

        assert "Line 1" in dashboard.state.log_lines
        assert "Line 2" in dashboard.state.log_lines
        assert "Line 3" in dashboard.state.log_lines


class TestSprintInfo:
    """Tests for set_sprint_info method."""

    def test_set_sprint_info(self, dashboard):
        """Setting sprint info should update state."""
        dashboard.set_sprint_info("SPEC_01", 10, 3)

        assert dashboard.state.spec_id == "SPEC_01"
        assert dashboard.state.total_issues == 10
        assert dashboard.state.completed_issues == 3

    def test_increment_completed(self, dashboard):
        """Incrementing completed should update count."""
        dashboard.set_sprint_info("SPEC_01", 10, 3)
        dashboard.increment_completed()

        assert dashboard.state.completed_issues == 4


class TestBuildLayout:
    """Tests for layout building methods."""

    def test_build_layout_returns_group(self, dashboard):
        """_build_layout should return a Group (no panels)."""
        layout = dashboard._build_layout()
        assert isinstance(layout, Group)



class TestContextManager:
    """Tests for context manager functionality."""

    def test_context_manager_starts_live(self, dashboard):
        """Entering context should start live mode."""
        assert dashboard._live is None

        with dashboard:
            assert dashboard._live is not None

    def test_context_manager_stops_live(self, dashboard):
        """Exiting context should stop live mode."""
        with dashboard:
            pass

        assert dashboard._live is None

    def test_print_static_works(self, dashboard):
        """print_static should work without raising."""
        # This just verifies no exceptions are raised
        dashboard.print_static()


class TestSubprocessTracking:
    """Tests for subprocess tracking functionality."""

    def test_subprocess_info_default(self):
        """SubprocessInfo should have sensible defaults."""
        info = SubprocessInfo()
        assert info.pid is None
        assert info.command == ""
        assert info.start_time == 0.0
        assert info.output_lines == 0
        assert info.last_output == ""

    def test_on_subprocess_start(self, dashboard):
        """Starting a subprocess should track its info."""
        dashboard.on_subprocess_start(12345, "claude -p --verbose")

        assert dashboard.state.subprocess.pid == 12345
        assert dashboard.state.subprocess.command == "claude -p --verbose"
        assert dashboard.state.subprocess.start_time > 0
        assert dashboard.state.subprocess.output_lines == 0

    def test_on_subprocess_output(self, dashboard):
        """Subprocess output should update tracking."""
        dashboard.on_subprocess_start(12345, "claude")

        dashboard.on_subprocess_output("Reading file...")
        assert dashboard.state.subprocess.output_lines == 1
        assert dashboard.state.subprocess.last_output == "Reading file..."

        dashboard.on_subprocess_output("Processing...")
        assert dashboard.state.subprocess.output_lines == 2
        assert dashboard.state.subprocess.last_output == "Processing..."

    def test_on_subprocess_output_truncates_long_lines(self, dashboard):
        """Long output lines should be truncated for display."""
        dashboard.on_subprocess_start(12345, "claude")

        long_line = "A" * 100
        dashboard.on_subprocess_output(long_line)

        # Should truncate to 60 chars + "..."
        assert len(dashboard.state.subprocess.last_output) == 63
        assert dashboard.state.subprocess.last_output.endswith("...")

    def test_on_subprocess_output_ignores_empty_lines(self, dashboard):
        """Empty lines should not update last_output."""
        dashboard.on_subprocess_start(12345, "claude")

        dashboard.on_subprocess_output("Initial output")
        dashboard.on_subprocess_output("")
        dashboard.on_subprocess_output("   ")

        # last_output should still be the first non-empty line
        assert dashboard.state.subprocess.last_output == "Initial output"
        # But line count should still increase
        assert dashboard.state.subprocess.output_lines == 3

    def test_on_subprocess_end(self, dashboard):
        """Ending subprocess should clear tracking."""
        dashboard.on_subprocess_start(12345, "claude")
        dashboard.on_subprocess_output("Some output")

        dashboard.on_subprocess_end()

        assert dashboard.state.subprocess.pid is None
        assert dashboard.state.subprocess.command == ""
        assert dashboard.state.subprocess.output_lines == 0

    def test_format_elapsed(self, dashboard):
        """Test elapsed time formatting."""
        # Small values show decimal for responsiveness
        assert dashboard._format_elapsed(0.5) == "0.5s"
        assert dashboard._format_elapsed(5.3) == "5.3s"
        assert dashboard._format_elapsed(9.9) == "9.9s"
        # Values >= 10s show whole seconds
        assert dashboard._format_elapsed(10) == "10s"
        assert dashboard._format_elapsed(59) == "59s"
        assert dashboard._format_elapsed(60) == "1m 0s"
        assert dashboard._format_elapsed(90) == "1m 30s"
        assert dashboard._format_elapsed(3661) == "61m 1s"

    def test_subprocess_display_empty_when_not_running(self, dashboard):
        """Subprocess display should be empty text when no subprocess."""
        from rich.text import Text
        display = dashboard._build_subprocess_display()
        assert isinstance(display, Text)
        assert display.plain == ""

    def test_subprocess_display_shows_info_when_running(self, dashboard):
        """Subprocess display should show info when subprocess is running."""
        dashboard.on_subprocess_start(12345, "claude")
        dashboard.on_subprocess_output("Working...")

        display = dashboard._build_subprocess_display()
        # Should return a LiveSubprocessDisplay that recalculates on each render
        from claudesprint.ui import LiveSubprocessDisplay
        assert isinstance(display, LiveSubprocessDisplay)
        # The inner display should be a Group
        from rich.console import Group
        inner = dashboard._build_subprocess_display_inner()
        assert isinstance(inner, Group)
