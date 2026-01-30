"""Tests for the dashboard module."""

import asyncio
import json
import queue
import threading
import time
from collections import deque
from datetime import datetime, UTC
from unittest.mock import MagicMock, patch

import pytest

from claudesprint.dashboard.bridge import DashboardEventBridge
from claudesprint.dashboard.port_manager import PortResult, find_available_port
from claudesprint.dashboard.server import DashboardServer
from claudesprint.dashboard.state import DashboardState
from claudesprint.events.workflow_event_bus import WorkflowEvent, WorkflowEventBus


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
        # This test just verifies the function works correctly
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
        assert state.connected_clients == 0
        assert isinstance(state.output_buffer, deque)

    def test_to_dict_serialization(self) -> None:
        """Should serialize to JSON-compatible dict."""
        state = DashboardState(
            sprint_id="SPEC_01",
            total_issues=10,
            completed_issues=3,
            current_issue_id="issue-1",
            current_step="implement",
        )
        data = state.to_dict()

        assert data["sprint_id"] == "SPEC_01"
        assert data["total_issues"] == 10
        assert data["completed_issues"] == 3
        assert data["current_issue_id"] == "issue-1"
        assert data["current_step"] == "implement"
        assert "timestamp" in data
        assert isinstance(data["output_lines"], list)

    def test_add_output_appends_line(self) -> None:
        """Should append lines to output buffer."""
        state = DashboardState()
        state.add_output("Line 1")
        state.add_output("Line 2")

        assert len(state.output_buffer) == 2
        assert list(state.output_buffer) == ["Line 1", "Line 2"]

    def test_output_buffer_max_size(self) -> None:
        """Should respect max buffer size."""
        state = DashboardState()
        # Default maxlen is 500
        for i in range(600):
            state.add_output(f"Line {i}")

        assert len(state.output_buffer) == 500
        # Should have dropped earliest entries
        assert state.output_buffer[0] == "Line 100"

    def test_clear_output(self) -> None:
        """Should clear the output buffer."""
        state = DashboardState()
        state.add_output("Line 1")
        state.add_output("Line 2")
        state.clear_output()

        assert len(state.output_buffer) == 0

    def test_step_elapsed_without_start_time(self) -> None:
        """Should return None when no step start time."""
        state = DashboardState()
        data = state.to_dict()
        assert data["step_elapsed_seconds"] is None

    def test_step_elapsed_with_start_time(self) -> None:
        """Should calculate elapsed seconds."""
        state = DashboardState()
        state.step_start_time = datetime.now(UTC)
        time.sleep(0.1)  # Small delay
        data = state.to_dict()

        assert data["step_elapsed_seconds"] is not None
        assert data["step_elapsed_seconds"] >= 0.1


class TestDashboardEventBridge:
    """Tests for DashboardEventBridge class."""

    def test_connect_subscribes_to_events(self) -> None:
        """Should subscribe to workflow events on connect."""
        event_bus = WorkflowEventBus()
        bridge = DashboardEventBridge(event_bus)

        bridge.connect()

        # Verify subscribers were added
        assert len(event_bus._subscribers[WorkflowEvent.SPRINT_STARTED]) > 0
        assert len(event_bus._subscribers[WorkflowEvent.STEP_STARTED]) > 0
        assert len(event_bus._subscribers[WorkflowEvent.SUBPROCESS_OUTPUT]) > 0

        bridge.disconnect()

    def test_disconnect_unsubscribes(self) -> None:
        """Should unsubscribe from events on disconnect."""
        event_bus = WorkflowEventBus()
        bridge = DashboardEventBridge(event_bus)

        bridge.connect()
        bridge.disconnect()

        # Verify subscribers were removed
        assert len(event_bus._subscribers.get(WorkflowEvent.SPRINT_STARTED, [])) == 0

    def test_double_connect_is_safe(self) -> None:
        """Should handle multiple connect calls safely."""
        event_bus = WorkflowEventBus()
        bridge = DashboardEventBridge(event_bus)

        bridge.connect()
        bridge.connect()  # Should not double-subscribe

        # Should only have one subscriber
        assert len(event_bus._subscribers[WorkflowEvent.SPRINT_STARTED]) == 1

        bridge.disconnect()

    def test_double_disconnect_is_safe(self) -> None:
        """Should handle multiple disconnect calls safely."""
        event_bus = WorkflowEventBus()
        bridge = DashboardEventBridge(event_bus)

        bridge.connect()
        bridge.disconnect()
        bridge.disconnect()  # Should not error

    def test_sprint_started_updates_state(self) -> None:
        """Should update state on SPRINT_STARTED event."""
        event_bus = WorkflowEventBus()
        bridge = DashboardEventBridge(event_bus)
        bridge.connect()

        event_bus.emit(
            WorkflowEvent.SPRINT_STARTED,
            {
                "sprint_id": "SPEC_01",
                "total_count": 10,
                "completed_count": 2,
                "timestamp": "2024-01-01T00:00:00Z",
            },
        )

        assert bridge.state.sprint_id == "SPEC_01"
        assert bridge.state.total_issues == 10
        assert bridge.state.completed_issues == 2

        bridge.disconnect()

    def test_issue_started_updates_state(self) -> None:
        """Should update state on ISSUE_STARTED event."""
        event_bus = WorkflowEventBus()
        bridge = DashboardEventBridge(event_bus)
        bridge.connect()

        event_bus.emit(
            WorkflowEvent.ISSUE_STARTED,
            {
                "issue_id": "issue-1",
                "issue_name": "Implement feature",
                "exit_reason": None,
                "timestamp": "2024-01-01T00:00:00Z",
            },
        )

        assert bridge.state.current_issue_id == "issue-1"
        assert bridge.state.current_issue_name == "Implement feature"

        bridge.disconnect()

    def test_step_started_updates_state(self) -> None:
        """Should update state on STEP_STARTED event."""
        event_bus = WorkflowEventBus()
        bridge = DashboardEventBridge(event_bus)
        bridge.connect()

        event_bus.emit(
            WorkflowEvent.STEP_STARTED,
            {
                "issue_id": "issue-1",
                "step_name": "implement",
                "step_index": 1,
                "timestamp": "2024-01-01T00:00:00Z",
            },
        )

        assert bridge.state.current_step == "implement"
        assert bridge.state.step_start_time is not None

        bridge.disconnect()

    def test_subprocess_output_updates_buffer(self) -> None:
        """Should add subprocess output to buffer."""
        event_bus = WorkflowEventBus()
        bridge = DashboardEventBridge(event_bus)
        bridge.connect()

        event_bus.emit(
            WorkflowEvent.SUBPROCESS_OUTPUT,
            {
                "line": "Test output line",
                "issue_id": "issue-1",
                "step_name": "run-tests",
                "timestamp": "2024-01-01T00:00:00Z",
            },
        )

        assert "Test output line" in bridge.state.output_buffer

        bridge.disconnect()

    def test_events_queued_for_sse(self) -> None:
        """Should queue events for SSE streaming."""
        event_bus = WorkflowEventBus()
        bridge = DashboardEventBridge(event_bus)
        bridge.connect()

        event_bus.emit(
            WorkflowEvent.STEP_STARTED,
            {
                "issue_id": "issue-1",
                "step_name": "implement",
                "step_index": 1,
                "timestamp": "2024-01-01T00:00:00Z",
            },
        )

        # Should have queued the event
        event = bridge._event_queue.get_nowait()
        assert event["type"] == "step_started"
        assert "data" in event
        assert "timestamp" in event

        bridge.disconnect()

    def test_issue_iteration_updates_metrics(self) -> None:
        """Should update iteration metrics on ISSUE_ITERATION."""
        event_bus = WorkflowEventBus()
        bridge = DashboardEventBridge(event_bus)
        bridge.connect()

        event_bus.emit(
            WorkflowEvent.ISSUE_ITERATION,
            {
                "total_iterations": 5,
                "max_iterations": 50,
                "retry_count": 2,
                "max_retry": 5,
                "issue_id": "issue-1",
                "timestamp": "2024-01-01T00:00:00Z",
            },
        )

        assert bridge.state.total_iterations == 5
        assert bridge.state.max_iterations == 50
        assert bridge.state.retry_count == 2
        assert bridge.state.max_retry == 5

        bridge.disconnect()


class TestDashboardServer:
    """Tests for DashboardServer class."""

    def test_server_creation(self) -> None:
        """Should create server instance."""
        event_bus = WorkflowEventBus()
        server = DashboardServer(event_bus)
        assert server is not None

    def test_server_start_and_stop(self) -> None:
        """Should start and stop server cleanly."""
        event_bus = WorkflowEventBus()
        server = DashboardServer(event_bus)

        url = server.start(start_port=19600)
        assert url is not None
        assert "http://127.0.0.1:" in url

        server.stop()

    def test_server_returns_url_on_start(self) -> None:
        """Should return dashboard URL on successful start."""
        event_bus = WorkflowEventBus()
        server = DashboardServer(event_bus)

        url = server.start(start_port=19700)
        try:
            assert url is not None
            assert url.startswith("http://127.0.0.1:")
        finally:
            server.stop()

    def test_server_double_start_returns_same_url(self) -> None:
        """Should return same URL if already running."""
        event_bus = WorkflowEventBus()
        server = DashboardServer(event_bus)

        url1 = server.start(start_port=19800)
        url2 = server.start(start_port=19800)

        try:
            assert url1 == url2
        finally:
            server.stop()

    def test_server_double_stop_is_safe(self) -> None:
        """Should handle multiple stop calls safely."""
        event_bus = WorkflowEventBus()
        server = DashboardServer(event_bus)

        server.start(start_port=19900)
        server.stop()
        server.stop()  # Should not error


class TestDashboardIntegration:
    """Integration tests for dashboard with event bus."""

    def test_events_flow_through_system(self) -> None:
        """Events should flow from event bus to dashboard state."""
        event_bus = WorkflowEventBus()
        server = DashboardServer(event_bus)

        url = server.start(start_port=20000)
        try:
            # Emit events through the event bus
            event_bus.emit(
                WorkflowEvent.SPRINT_STARTED,
                {
                    "sprint_id": "TEST_SPRINT",
                    "total_count": 5,
                    "completed_count": 0,
                    "timestamp": "2024-01-01T00:00:00Z",
                },
            )

            event_bus.emit(
                WorkflowEvent.ISSUE_STARTED,
                {
                    "issue_id": "test-issue",
                    "issue_name": "Test Issue",
                    "exit_reason": None,
                    "timestamp": "2024-01-01T00:00:00Z",
                },
            )

            # Verify state was updated
            state = server._bridge.state
            assert state.sprint_id == "TEST_SPRINT"
            assert state.total_issues == 5
            assert state.current_issue_id == "test-issue"
        finally:
            server.stop()
