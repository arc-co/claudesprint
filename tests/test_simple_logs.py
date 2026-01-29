"""Tests for the simple logs output module."""

import io
from unittest.mock import patch

import pytest
from rich.console import Console

from claudesprint.models.current_issue import IssueStep
from claudesprint.simple_logs import SimpleLogsOutput


@pytest.fixture
def output():
    """Create a SimpleLogsOutput instance with a string buffer console."""
    string_buffer = io.StringIO()
    console = Console(file=string_buffer, force_terminal=False, no_color=True)
    return SimpleLogsOutput(console), string_buffer


class TestSimpleLogsOutputInit:
    """Tests for SimpleLogsOutput initialization."""

    def test_default_console(self):
        """Test that default console is created if not provided."""
        output = SimpleLogsOutput()
        assert output.console is not None

    def test_custom_console(self, output):
        """Test that custom console is used when provided."""
        logs, _ = output
        assert logs.console is not None

    def test_initial_state(self, output):
        """Test initial state values."""
        logs, _ = output
        assert logs.current_issue is None
        assert logs.current_step is None
        assert logs.step_start_time is None
        assert logs.sprint_total == 0
        assert logs.sprint_completed == 0


class TestSprintEvents:
    """Tests for sprint-level events."""

    def test_set_sprint_info(self, output):
        """Test setting sprint info logs correctly."""
        logs, buffer = output
        logs.set_sprint_info("SPEC_01", 10, 3)

        content = buffer.getvalue()
        assert "SPRINT" in content
        assert "SPEC_01" in content
        assert "3/10 issues complete" in content
        assert logs.sprint_total == 10
        assert logs.sprint_completed == 3

    def test_on_sprint_iteration(self, output):
        """Test sprint iteration callback logs correctly."""
        logs, buffer = output
        logs.sprint_total = 10
        logs.sprint_completed = 3
        logs.on_sprint_iteration(1, 7)

        content = buffer.getvalue()
        assert "ITERATION" in content
        assert "1" in content
        assert "7 issues available" in content

    def test_on_selecting_issue(self, output):
        """Test selecting issue callback logs correctly."""
        logs, buffer = output
        logs.on_selecting_issue()

        content = buffer.getvalue()
        assert "Selecting next issue" in content


class TestIssueEvents:
    """Tests for issue-level events."""

    def test_set_issue(self, output):
        """Test setting issue logs correctly."""
        logs, buffer = output
        logs.set_issue("feat-001", "Add login feature")

        content = buffer.getvalue()
        assert "ISSUE" in content
        assert "feat-001" in content
        assert "Add login feature" in content
        assert logs.current_issue == "feat-001"

    def test_on_issue_complete(self, output):
        """Test issue completion logs correctly."""
        logs, buffer = output
        logs.sprint_total = 5
        logs.sprint_completed = 1

        logs.on_issue_complete("feat-001")

        content = buffer.getvalue()
        assert "ISSUE" in content
        assert "feat-001" in content
        assert "Complete" in content
        assert "2/5" in content
        assert logs.sprint_completed == 2

    def test_clear_issue(self, output):
        """Test clearing issue clears state."""
        logs, _ = output
        logs.current_issue = "feat-001"

        logs.clear_issue()

        assert logs.current_issue is None


class TestStepEvents:
    """Tests for step-level events."""

    def test_on_step_start(self, output):
        """Test step start logs correctly."""
        logs, buffer = output
        logs.on_step_start(IssueStep.IMPLEMENT, "opus")

        content = buffer.getvalue()
        assert "STEP" in content
        assert "implement" in content
        assert "Starting" in content
        assert "opus" in content
        assert logs.current_step == "implement"
        assert logs.step_start_time is not None

    @patch("claudesprint.simple_logs.time.time")
    def test_on_step_complete(self, mock_time, output):
        """Test step completion logs correctly with timing."""
        logs, buffer = output
        mock_time.return_value = 100.0
        logs.step_start_time = 85.0  # 15 seconds ago

        logs.on_step_complete(IssueStep.IMPLEMENT, IssueStep.WRITE_TESTS)

        content = buffer.getvalue()
        assert "STEP" in content
        assert "implement" in content
        assert "Complete" in content
        assert "15s" in content
        assert logs.step_start_time is None
        assert logs.current_step is None

    def test_on_step_skip(self, output):
        """Test step skip logs correctly."""
        logs, buffer = output
        logs.on_step_skip(IssueStep.BROWSER_VALIDATION, IssueStep.CODE_REVIEW)

        content = buffer.getvalue()
        assert "STEP" in content
        assert "browser-validation" in content
        assert "Skipped" in content

    def test_on_step_failure(self, output):
        """Test step failure logs correctly."""
        logs, buffer = output
        logs.on_step_failure(IssueStep.RUN_TESTS, 2)

        content = buffer.getvalue()
        assert "STEP" in content
        assert "run-tests" in content
        assert "Failed" in content
        assert "retry 2" in content


class TestSubprocessOutput:
    """Tests for subprocess/agent output."""

    def test_on_subprocess_start_is_noop(self, output):
        """Test subprocess start is a no-op for simple logs."""
        logs, buffer = output
        logs.on_subprocess_start(12345, "claude --print")

        # Should not log anything
        assert buffer.getvalue() == ""

    def test_on_subprocess_output(self, output):
        """Test subprocess output logs with indent."""
        logs, buffer = output
        logs.on_subprocess_output("Reading src/auth.py...")

        content = buffer.getvalue()
        assert ">" in content
        assert "Reading src/auth.py" in content

    def test_on_subprocess_output_strips_whitespace(self, output):
        """Test subprocess output strips trailing whitespace."""
        logs, buffer = output
        logs.on_subprocess_output("Some output   \n  ")

        content = buffer.getvalue()
        assert "Some output" in content

    def test_on_subprocess_output_ignores_empty(self, output):
        """Test empty output lines are ignored."""
        logs, buffer = output
        logs.on_subprocess_output("")
        logs.on_subprocess_output("   ")

        # Should not log empty lines
        assert buffer.getvalue() == ""

    def test_on_subprocess_end_is_noop(self, output):
        """Test subprocess end is a no-op for simple logs."""
        logs, buffer = output
        logs.on_subprocess_end()

        # Should not log anything
        assert buffer.getvalue() == ""


class TestGeneralOutput:
    """Tests for general output methods."""

    def test_on_output(self, output):
        """Test general output logging."""
        logs, buffer = output
        logs.on_output("Some status message")

        content = buffer.getvalue()
        assert "Some status message" in content

    def test_on_output_multiline(self, output):
        """Test multiline output is split correctly."""
        logs, buffer = output
        logs.on_output("Line 1\nLine 2\nLine 3")

        content = buffer.getvalue()
        assert "Line 1" in content
        assert "Line 2" in content
        assert "Line 3" in content

    def test_on_output_strips_empty_lines(self, output):
        """Test empty lines in output are skipped."""
        logs, buffer = output
        logs.on_output("Line 1\n\nLine 2")

        content = buffer.getvalue()
        # Count non-timestamp parts
        lines = [l for l in content.split("\n") if l.strip()]
        # Should have 2 lines (Line 1 and Line 2, not an empty line)
        assert len(lines) == 2

    def test_add_log_line(self, output):
        """Test add_log_line for compatibility."""
        logs, buffer = output
        logs.add_log_line("Some log message")

        content = buffer.getvalue()
        assert "Some log message" in content


class TestCompatibilityMethods:
    """Tests for optional compatibility methods."""

    def test_set_issues_is_noop(self, output):
        """Test set_issues is a no-op for simple logs."""
        logs, buffer = output
        logs.set_issues([("id1", "title1", "pending"), ("id2", "title2", "done")])

        # Should not log anything
        assert buffer.getvalue() == ""

    def test_increment_completed_is_noop(self, output):
        """Test increment_completed is a no-op for simple logs."""
        logs, buffer = output
        logs.sprint_completed = 5
        logs.increment_completed()

        # Should not change state (handled by on_issue_complete instead)
        assert logs.sprint_completed == 5


class TestContextManager:
    """Tests for context manager functionality."""

    def test_context_manager_enter(self, output):
        """Test entering context returns self."""
        logs, _ = output
        with logs as result:
            assert result is logs

    def test_context_manager_exit(self, output):
        """Test exiting context does not raise."""
        logs, _ = output
        # Should not raise
        with logs:
            pass


class TestFormatElapsed:
    """Tests for elapsed time formatting."""

    def test_format_elapsed_none(self, output):
        """Test formatting with no start time returns ?."""
        logs, _ = output
        assert logs._format_elapsed(None) == "?"

    @patch("claudesprint.simple_logs.time.time")
    def test_format_elapsed_seconds(self, mock_time, output):
        """Test formatting seconds."""
        logs, _ = output
        mock_time.return_value = 30.0
        assert logs._format_elapsed(15.0) == "15s"

    @patch("claudesprint.simple_logs.time.time")
    def test_format_elapsed_minutes(self, mock_time, output):
        """Test formatting minutes."""
        logs, _ = output
        mock_time.return_value = 200.0
        # 135 seconds = 2m 15s
        assert logs._format_elapsed(65.0) == "2m 15s"


class TestTimestamp:
    """Tests for timestamp formatting."""

    def test_timestamp_format(self, output):
        """Test timestamp is in HH:MM:SS format."""
        logs, _ = output
        timestamp = logs._timestamp()

        # Should be 8 characters: HH:MM:SS
        assert len(timestamp) == 8
        assert timestamp[2] == ":"
        assert timestamp[5] == ":"
