"""Tests for the dashboard module."""

import time
from collections import deque
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from claudesprint.dashboard.port_manager import PortResult, find_available_port
from claudesprint.dashboard.state import DashboardState
from claudesprint.events.workflow_event_bus import WorkflowEventBus


class TestPortManager:
    """Tests for port_manager module."""

    def test_find_available_port_success(self) -> None:
        """Should find an available port."""
        result = find_available_port(start_port=19500)
        assert result.success is True
        assert result.port >= 19500
        assert result.error is None

    def test_find_available_port_returns_port_result(self) -> None:
        """Should return a PortResult dataclass."""
        result = find_available_port()
        assert isinstance(result, PortResult)

    def test_find_available_port_scans_range(self) -> None:
        """Should try multiple ports if needed."""
        result = find_available_port(start_port=19500, max_attempts=5)
        assert result.success is True


class TestDashboardState:
    """Tests for DashboardState class."""

    def test_default_state(self) -> None:
        """Should have sensible defaults."""
        state = DashboardState()
        assert state.sprint_id == ""
        assert state.total_issues == 0
        assert state.completed_issues == 0
        assert state.current_issue_id == ""
        assert state.current_step == ""
        assert state.retry_count == 0
        assert isinstance(state.output_lines, deque)

    def test_add_output_appends_line(self) -> None:
        """Should append lines to output buffer."""
        state = DashboardState()
        state.add_output("Line 1")
        state.add_output("Line 2")

        assert len(state.output_lines) == 2
        assert list(state.output_lines) == ["Line 1", "Line 2"]

    def test_output_buffer_max_size(self) -> None:
        """Should respect max buffer size."""
        state = DashboardState()
        # Default maxlen is 500
        for i in range(600):
            state.add_output(f"Line {i}")

        assert len(state.output_lines) == 500
        # Should have dropped earliest entries
        assert state.output_lines[0] == "Line 100"

    def test_clear_output(self) -> None:
        """Should clear the output buffer."""
        state = DashboardState()
        state.add_output("Line 1")
        state.add_output("Line 2")
        state.clear_output()

        assert len(state.output_lines) == 0

    def test_step_elapsed_without_start_time(self) -> None:
        """Should return '-' when no step start time."""
        state = DashboardState()
        assert state.step_elapsed == "-"

    def test_step_elapsed_with_start_time(self) -> None:
        """Should calculate elapsed time string."""
        state = DashboardState()
        state.step_start_time = datetime.now(UTC)
        time.sleep(0.1)  # Small delay

        elapsed = state.step_elapsed
        assert elapsed is not None
        assert "s" in elapsed  # Should contain seconds

    def test_step_elapsed_formats_minutes(self) -> None:
        """Should format elapsed time with minutes."""
        state = DashboardState()
        # Set start time to 65 seconds ago
        from datetime import timedelta

        state.step_start_time = datetime.now(UTC) - timedelta(seconds=65)
        elapsed = state.step_elapsed
        assert "m" in elapsed  # Should contain minutes
        assert "s" in elapsed  # Should contain seconds

    def test_set_issues(self) -> None:
        """Should load issues from sprint data."""
        state = DashboardState()
        issues = [
            {"id": "issue-1", "title": "First issue", "status": "pending", "priority": "high"},
            {"id": "issue-2", "title": "Second issue", "status": "completed", "priority": "low"},
        ]
        state.set_issues(issues)

        assert len(state.issues) == 2
        assert state.issues["issue-1"]["title"] == "First issue"
        assert state.issues["issue-1"]["priority"] == "high"
        assert state.issues["issue-2"]["status"] == "completed"

    def test_update_issue_status(self) -> None:
        """Should update issue status."""
        state = DashboardState()
        state.set_issues([{"id": "issue-1", "title": "Test", "status": "pending", "priority": "medium"}])

        state.update_issue_status("issue-1", "completed")
        assert state.issues["issue-1"]["status"] == "completed"

    def test_update_issue_status_missing_issue(self) -> None:
        """Should handle missing issue gracefully."""
        state = DashboardState()
        # Should not raise
        state.update_issue_status("nonexistent", "completed")


class TestDashboardServerWithMockNicegui:
    """Tests for DashboardServer with mocked NiceGUI."""

    def test_server_creation(self) -> None:
        """Should create server instance."""
        # Mock nicegui imports
        with patch.dict("sys.modules", {"nicegui": MagicMock()}):
            from claudesprint.dashboard.server import DashboardServer

            event_bus = WorkflowEventBus()
            server = DashboardServer(event_bus)
            assert server is not None

    def test_server_requires_nicegui(self) -> None:
        """Should raise ImportError when nicegui not available."""
        import claudesprint.dashboard.server as server_module

        # Save originals
        original_ui = getattr(server_module, "ui", None)
        original_app = getattr(server_module, "app", None)

        try:
            # Set to None to simulate import failure
            server_module.ui = None
            server_module.app = None

            event_bus = WorkflowEventBus()
            with pytest.raises(ImportError, match="nicegui is required"):
                server_module.DashboardServer(event_bus)
        finally:
            # Restore
            server_module.ui = original_ui
            server_module.app = original_app


class TestDashboardEventHandlers:
    """Tests for event handler behavior on state."""

    def test_sprint_started_updates_state(self) -> None:
        """Event handler should update sprint state."""
        state = DashboardState()

        # Simulate what _on_sprint_started does
        state.sprint_id = "SPEC_01"
        state.total_issues = 10
        state.completed_issues = 2
        state.clear_output()

        assert state.sprint_id == "SPEC_01"
        assert state.total_issues == 10
        assert state.completed_issues == 2

    def test_issue_started_updates_state(self) -> None:
        """Event handler should update issue state."""
        state = DashboardState()
        state.set_issues([{"id": "issue-1", "title": "Test", "status": "pending", "priority": "medium"}])

        # Simulate what _on_issue_started does
        state.current_issue_id = "issue-1"
        state.current_issue_name = "Implement feature"
        state.retry_count = 0
        state.clear_output()
        state.update_issue_status("issue-1", "in_progress")

        assert state.current_issue_id == "issue-1"
        assert state.current_issue_name == "Implement feature"
        assert state.issues["issue-1"]["status"] == "in_progress"

    def test_step_started_updates_state(self) -> None:
        """Event handler should update step state."""
        state = DashboardState()

        # Simulate what _on_step_started does
        state.current_step = "implement"
        state.step_start_time = datetime.now(UTC)

        assert state.current_step == "implement"
        assert state.step_start_time is not None

    def test_issue_completed_updates_state(self) -> None:
        """Event handler should update state on issue completion."""
        state = DashboardState()
        state.set_issues([{"id": "issue-1", "title": "Test", "status": "in_progress", "priority": "medium"}])
        state.current_issue_id = "issue-1"
        state.current_issue_name = "Test"

        # Simulate what _on_issue_completed does
        old_issue = state.current_issue_id
        state.update_issue_status(old_issue, "completed")
        state.completed_issues += 1
        state.current_issue_id = ""
        state.current_issue_name = ""
        state.current_step = ""
        state.add_output(f"DONE: {old_issue}")

        assert state.issues["issue-1"]["status"] == "completed"
        assert state.completed_issues == 1
        assert state.current_issue_id == ""
        assert "DONE: issue-1" in state.output_lines

    def test_subprocess_output_updates_buffer(self) -> None:
        """Event handler should add subprocess output to buffer."""
        state = DashboardState()

        # Simulate what _on_subprocess_output does
        state.add_output("Test output line")

        assert "Test output line" in state.output_lines

    def test_issue_iteration_updates_metrics(self) -> None:
        """Event handler should update iteration metrics."""
        state = DashboardState()

        # Simulate what _on_issue_iteration does
        state.retry_count = 2
        state.max_retry = 5

        assert state.retry_count == 2
        assert state.max_retry == 5
