"""NiceGUI-based dashboard server."""

from __future__ import annotations

import contextlib
import logging
import threading
from collections.abc import Callable
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, cast

from claudesprint.dashboard.components import create_dashboard
from claudesprint.dashboard.port_manager import find_available_port
from claudesprint.dashboard.state import DashboardState
from claudesprint.events.workflow_event_bus import EventPayload, WorkflowEvent

if TYPE_CHECKING:
    from claudesprint.events.workflow_event_bus import WorkflowEventBus

try:
    from nicegui import app, ui
except ImportError:
    app = None
    ui = None

logger = logging.getLogger(__name__)


def _get_str(payload: EventPayload, key: str, default: str = "") -> str:
    """Safely get a string value from payload."""
    value = cast(dict[str, Any], payload).get(key, default)
    return str(value) if value is not None else default


def _get_int(payload: EventPayload, key: str, default: int = 0) -> int:
    """Safely get an int value from payload."""
    value = cast(dict[str, Any], payload).get(key, default)
    return value if isinstance(value, int) else default


class DashboardServer:
    """NiceGUI-based dashboard server.

    Replaces the aiohttp/SSE implementation with NiceGUI's built-in
    WebSocket reactivity for simpler real-time updates.
    """

    def __init__(self, event_bus: WorkflowEventBus) -> None:
        """Initialize the dashboard server.

        Args:
            event_bus: The workflow event bus to subscribe to.
        """
        if ui is None:
            raise ImportError("nicegui is required for the dashboard. Install with: pip install nicegui")

        self._event_bus = event_bus
        self._state = DashboardState()
        self._refresh_callbacks: dict[str, Callable[[], None]] = {}
        self._port: int = 0
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self, start_port: int = 9500) -> str | None:
        """Start the dashboard server in a background thread.

        Args:
            start_port: Port to start scanning from.

        Returns:
            Dashboard URL if started successfully, None otherwise.
        """
        if self._running:
            return f"http://127.0.0.1:{self._port}"

        # Find available port
        port_result = find_available_port(start_port)
        if not port_result.success:
            logger.warning(f"Dashboard: {port_result.error}")
            return None

        self._port = port_result.port

        # Subscribe to events
        self._connect_events()

        # Create the UI page
        @ui.page("/")
        def dashboard_page() -> None:
            ui.page_title("ClaudeSprint")
            create_dashboard(self._state, self._refresh_callbacks)

        # Start server in background thread
        self._thread = threading.Thread(target=self._run_server, daemon=True)
        self._thread.start()

        self._running = True
        url = f"http://127.0.0.1:{self._port}"
        logger.info(f"Dashboard started at {url}")
        return url

    def stop(self) -> None:
        """Stop the dashboard server gracefully."""
        if not self._running:
            return

        self._running = False
        self._disconnect_events()

        # NiceGUI shutdown
        with contextlib.suppress(Exception):
            app.shutdown()

        logger.info("Dashboard stopped")

    def _run_server(self) -> None:
        """Run the NiceGUI server (called in background thread)."""
        try:
            ui.run(
                host="127.0.0.1",
                port=self._port,
                reload=False,
                show=False,
                title="ClaudeSprint",
            )
        except Exception as e:
            logger.exception(f"Dashboard server error: {e}")

    def _connect_events(self) -> None:
        """Subscribe to all relevant workflow events."""
        self._event_bus.subscribe(WorkflowEvent.SPRINT_STARTED, self._on_sprint_started)
        self._event_bus.subscribe(WorkflowEvent.SPRINT_COMPLETED, self._on_sprint_completed)
        self._event_bus.subscribe(WorkflowEvent.SPRINT_ITERATION, self._on_sprint_iteration)
        self._event_bus.subscribe(WorkflowEvent.SELECTING_ISSUE, self._on_selecting_issue)
        self._event_bus.subscribe(WorkflowEvent.ISSUE_STARTED, self._on_issue_started)
        self._event_bus.subscribe(WorkflowEvent.ISSUE_COMPLETED, self._on_issue_completed)
        self._event_bus.subscribe(WorkflowEvent.ISSUE_FAILED, self._on_issue_failed)
        self._event_bus.subscribe(WorkflowEvent.ISSUE_ITERATION, self._on_issue_iteration)
        self._event_bus.subscribe(WorkflowEvent.STEP_STARTED, self._on_step_started)
        self._event_bus.subscribe(WorkflowEvent.STEP_COMPLETED, self._on_step_completed)
        self._event_bus.subscribe(WorkflowEvent.STEP_FAILED, self._on_step_failed)
        self._event_bus.subscribe(WorkflowEvent.SUBPROCESS_STARTED, self._on_subprocess_started)
        self._event_bus.subscribe(WorkflowEvent.SUBPROCESS_OUTPUT, self._on_subprocess_output)
        self._event_bus.subscribe(WorkflowEvent.OUTPUT, self._on_output)
        logger.debug("Dashboard event handlers connected")

    def _disconnect_events(self) -> None:
        """Unsubscribe from all workflow events."""
        self._event_bus.unsubscribe(WorkflowEvent.SPRINT_STARTED, self._on_sprint_started)
        self._event_bus.unsubscribe(WorkflowEvent.SPRINT_COMPLETED, self._on_sprint_completed)
        self._event_bus.unsubscribe(WorkflowEvent.SPRINT_ITERATION, self._on_sprint_iteration)
        self._event_bus.unsubscribe(WorkflowEvent.SELECTING_ISSUE, self._on_selecting_issue)
        self._event_bus.unsubscribe(WorkflowEvent.ISSUE_STARTED, self._on_issue_started)
        self._event_bus.unsubscribe(WorkflowEvent.ISSUE_COMPLETED, self._on_issue_completed)
        self._event_bus.unsubscribe(WorkflowEvent.ISSUE_FAILED, self._on_issue_failed)
        self._event_bus.unsubscribe(WorkflowEvent.ISSUE_ITERATION, self._on_issue_iteration)
        self._event_bus.unsubscribe(WorkflowEvent.STEP_STARTED, self._on_step_started)
        self._event_bus.unsubscribe(WorkflowEvent.STEP_COMPLETED, self._on_step_completed)
        self._event_bus.unsubscribe(WorkflowEvent.STEP_FAILED, self._on_step_failed)
        self._event_bus.unsubscribe(WorkflowEvent.SUBPROCESS_STARTED, self._on_subprocess_started)
        self._event_bus.unsubscribe(WorkflowEvent.SUBPROCESS_OUTPUT, self._on_subprocess_output)
        self._event_bus.unsubscribe(WorkflowEvent.OUTPUT, self._on_output)
        logger.debug("Dashboard event handlers disconnected")

    def _refresh_ui(self, *sections: str) -> None:
        """Refresh specified UI sections."""
        for section in sections:
            if section in self._refresh_callbacks:
                with contextlib.suppress(Exception):
                    self._refresh_callbacks[section]()

    # Event handlers

    def _on_sprint_started(self, payload: EventPayload) -> None:
        self._state.sprint_id = _get_str(payload, "sprint_id")
        self._state.total_issues = _get_int(payload, "total_count")
        self._state.completed_issues = _get_int(payload, "completed_count")
        self._state.clear_output()
        issues_data = cast(dict[str, Any], payload).get("issues", [])
        if issues_data:
            self._state.set_issues(issues_data)
        self._refresh_ui("sprint", "task_board", "issue", "output")

    def _on_sprint_completed(self, payload: EventPayload) -> None:
        self._state.completed_issues = _get_int(payload, "completed_count")
        self._state.add_output("SPRINT DONE")
        self._refresh_ui("sprint", "task_board", "output")

    def _on_sprint_iteration(self, payload: EventPayload) -> None:
        self._state.completed_issues = _get_int(payload, "completed_count")
        self._refresh_ui("sprint", "task_board")

    def _on_selecting_issue(self, _payload: EventPayload) -> None:
        self._state.current_step = "selecting-issue"
        self._state.step_start_time = datetime.now(timezone.utc)
        self._refresh_ui("issue", "workflow")

    def _on_issue_started(self, payload: EventPayload) -> None:
        issue_id = _get_str(payload, "issue_id")
        self._state.current_issue_id = issue_id
        self._state.current_issue_name = _get_str(payload, "issue_name")
        self._state.retry_count = 0
        self._state.clear_output()
        self._state.update_issue_status(issue_id, "in_progress")
        self._refresh_ui("task_board", "issue", "output")

    def _on_issue_completed(self, _payload: EventPayload) -> None:
        old_issue = self._state.current_issue_id
        self._state.update_issue_status(old_issue, "completed")
        self._state.completed_issues += 1
        self._state.current_issue_id = ""
        self._state.current_issue_name = ""
        self._state.current_step = ""
        self._state.add_output(f"DONE: {old_issue}")
        self._refresh_ui("sprint", "task_board", "issue", "workflow", "output")

    def _on_issue_failed(self, payload: EventPayload) -> None:
        issue_id = _get_str(payload, "issue_id") or self._state.current_issue_id
        self._state.update_issue_status(issue_id, "pending")
        self._state.current_issue_id = ""
        self._state.current_issue_name = ""
        self._state.current_step = ""
        self._state.add_output(f"FAILED: {issue_id}")
        self._refresh_ui("task_board", "issue", "workflow", "output")

    def _on_issue_iteration(self, payload: EventPayload) -> None:
        self._state.retry_count = _get_int(payload, "retry_count")
        self._state.max_retry = _get_int(payload, "max_retry", 5)
        self._refresh_ui("issue")

    def _on_step_started(self, payload: EventPayload) -> None:
        self._state.current_step = _get_str(payload, "step_name")
        self._state.step_start_time = datetime.now(timezone.utc)
        self._refresh_ui("issue", "workflow")

    def _on_step_completed(self, _payload: EventPayload) -> None:
        self._refresh_ui("workflow")

    def _on_step_failed(self, payload: EventPayload) -> None:
        self._state.retry_count = _get_int(payload, "retry_count")
        self._refresh_ui("issue", "workflow")

    def _on_subprocess_started(self, payload: EventPayload) -> None:
        command = _get_str(payload, "command")
        self._state.add_output(f"> {command}")
        self._refresh_ui("output")

    def _on_subprocess_output(self, payload: EventPayload) -> None:
        line = _get_str(payload, "line")
        self._state.add_output(line)
        self._refresh_ui("output")

    def _on_output(self, payload: EventPayload) -> None:
        text = _get_str(payload, "text")
        self._state.add_output(text)
        self._refresh_ui("output")
