"""Sync-to-async event bridge for dashboard."""

from __future__ import annotations

import asyncio
import json
import logging
import queue
import threading
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, cast

from claudesprint.dashboard.state import DashboardState
from claudesprint.events.workflow_event_bus import (
    EventPayload,
    WorkflowEvent,
    WorkflowEventBus,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def _get_str(payload: EventPayload, key: str, default: str = "") -> str:
    """Safely get a string value from payload."""
    # Cast to dict[str, Any] for .get() - payloads are TypedDict union
    value = cast(dict[str, Any], payload).get(key, default)
    return str(value) if value is not None else default


def _get_int(payload: EventPayload, key: str, default: int = 0) -> int:
    """Safely get an int value from payload."""
    value = cast(dict[str, Any], payload).get(key, default)
    if isinstance(value, int):
        return value
    return default


def _get_optional_int(payload: EventPayload, key: str) -> int | None:
    """Safely get an optional int value from payload."""
    value = cast(dict[str, Any], payload).get(key)
    if isinstance(value, int):
        return value
    return None


class DashboardEventBridge:
    """Bridges sync WorkflowEventBus to async SSE stream.

    Subscribes to workflow events, updates DashboardState, and queues
    events for async consumption by the SSE endpoint.
    """

    def __init__(self, event_bus: WorkflowEventBus) -> None:
        """Initialize the bridge.

        Args:
            event_bus: The workflow event bus to subscribe to.
        """
        self._event_bus = event_bus
        self._state = DashboardState()
        self._event_queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=1000)
        self._connected = False
        self._lock = threading.Lock()

    @property
    def state(self) -> DashboardState:
        """Get the current dashboard state."""
        return self._state

    def connect(self) -> None:
        """Subscribe to all relevant workflow events."""
        if self._connected:
            return

        # Sprint events
        self._event_bus.subscribe(WorkflowEvent.SPRINT_STARTED, self._on_sprint_started)
        self._event_bus.subscribe(WorkflowEvent.SPRINT_COMPLETED, self._on_sprint_completed)
        self._event_bus.subscribe(WorkflowEvent.SPRINT_ITERATION, self._on_sprint_iteration)
        self._event_bus.subscribe(WorkflowEvent.SELECTING_ISSUE, self._on_selecting_issue)

        # Issue events
        self._event_bus.subscribe(WorkflowEvent.ISSUE_STARTED, self._on_issue_started)
        self._event_bus.subscribe(WorkflowEvent.ISSUE_COMPLETED, self._on_issue_completed)
        self._event_bus.subscribe(WorkflowEvent.ISSUE_FAILED, self._on_issue_failed)
        self._event_bus.subscribe(WorkflowEvent.ISSUE_ITERATION, self._on_issue_iteration)

        # Step events
        self._event_bus.subscribe(WorkflowEvent.STEP_STARTED, self._on_step_started)
        self._event_bus.subscribe(WorkflowEvent.STEP_COMPLETED, self._on_step_completed)
        self._event_bus.subscribe(WorkflowEvent.STEP_FAILED, self._on_step_failed)
        self._event_bus.subscribe(WorkflowEvent.STEP_SKIPPED, self._on_step_skipped)

        # Subprocess events
        self._event_bus.subscribe(WorkflowEvent.SUBPROCESS_STARTED, self._on_subprocess_started)
        self._event_bus.subscribe(WorkflowEvent.SUBPROCESS_OUTPUT, self._on_subprocess_output)
        self._event_bus.subscribe(WorkflowEvent.SUBPROCESS_ENDED, self._on_subprocess_ended)

        # Other events
        self._event_bus.subscribe(WorkflowEvent.RATE_LIMITED, self._on_rate_limited)
        self._event_bus.subscribe(WorkflowEvent.PROCESS_HUNG, self._on_process_hung)
        self._event_bus.subscribe(WorkflowEvent.ROUTING_SIGNAL, self._on_routing_signal)
        self._event_bus.subscribe(WorkflowEvent.OUTPUT, self._on_output)

        self._connected = True
        logger.debug("Dashboard event bridge connected")

    def disconnect(self) -> None:
        """Unsubscribe from all workflow events."""
        if not self._connected:
            return

        # Sprint events
        self._event_bus.unsubscribe(WorkflowEvent.SPRINT_STARTED, self._on_sprint_started)
        self._event_bus.unsubscribe(WorkflowEvent.SPRINT_COMPLETED, self._on_sprint_completed)
        self._event_bus.unsubscribe(WorkflowEvent.SPRINT_ITERATION, self._on_sprint_iteration)
        self._event_bus.unsubscribe(WorkflowEvent.SELECTING_ISSUE, self._on_selecting_issue)

        # Issue events
        self._event_bus.unsubscribe(WorkflowEvent.ISSUE_STARTED, self._on_issue_started)
        self._event_bus.unsubscribe(WorkflowEvent.ISSUE_COMPLETED, self._on_issue_completed)
        self._event_bus.unsubscribe(WorkflowEvent.ISSUE_FAILED, self._on_issue_failed)
        self._event_bus.unsubscribe(WorkflowEvent.ISSUE_ITERATION, self._on_issue_iteration)

        # Step events
        self._event_bus.unsubscribe(WorkflowEvent.STEP_STARTED, self._on_step_started)
        self._event_bus.unsubscribe(WorkflowEvent.STEP_COMPLETED, self._on_step_completed)
        self._event_bus.unsubscribe(WorkflowEvent.STEP_FAILED, self._on_step_failed)
        self._event_bus.unsubscribe(WorkflowEvent.STEP_SKIPPED, self._on_step_skipped)

        # Subprocess events
        self._event_bus.unsubscribe(WorkflowEvent.SUBPROCESS_STARTED, self._on_subprocess_started)
        self._event_bus.unsubscribe(WorkflowEvent.SUBPROCESS_OUTPUT, self._on_subprocess_output)
        self._event_bus.unsubscribe(WorkflowEvent.SUBPROCESS_ENDED, self._on_subprocess_ended)

        # Other events
        self._event_bus.unsubscribe(WorkflowEvent.RATE_LIMITED, self._on_rate_limited)
        self._event_bus.unsubscribe(WorkflowEvent.PROCESS_HUNG, self._on_process_hung)
        self._event_bus.unsubscribe(WorkflowEvent.ROUTING_SIGNAL, self._on_routing_signal)
        self._event_bus.unsubscribe(WorkflowEvent.OUTPUT, self._on_output)

        self._connected = False
        logger.debug("Dashboard event bridge disconnected")

    def _queue_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Queue an event for SSE streaming."""
        event = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        try:
            self._event_queue.put_nowait(event)
        except queue.Full:
            # Drop oldest event if queue is full, log warning
            try:
                dropped = self._event_queue.get_nowait()
                logger.warning(f"Dashboard event queue full, dropped event: {dropped.get('type')}")
                self._event_queue.put_nowait(event)
            except queue.Empty:
                pass

    async def get_events_async(self) -> AsyncGenerator[str, None]:
        """Async generator yielding SSE-formatted events.

        Yields:
            SSE-formatted event strings (data: {...}\n\n)
        """
        while True:
            try:
                # Poll the queue with a timeout to allow cancellation
                event = await asyncio.to_thread(self._event_queue.get, timeout=0.5)
                yield f"data: {json.dumps(event)}\n\n"
            except queue.Empty:
                # Send keepalive comment every 0.5s
                yield ": keepalive\n\n"
            except Exception:
                break

    # Event handlers

    def _on_sprint_started(self, payload: EventPayload) -> None:
        """Handle SPRINT_STARTED event."""
        with self._lock:
            self._state.sprint_id = _get_str(payload, "sprint_id")
            self._state.total_issues = _get_int(payload, "total_count")
            self._state.completed_issues = _get_int(payload, "completed_count")
            self._state.clear_output()
        self._queue_event("sprint_started", dict(cast(dict[str, Any], payload)))

    def _on_sprint_completed(self, payload: EventPayload) -> None:
        """Handle SPRINT_COMPLETED event."""
        with self._lock:
            self._state.completed_issues = _get_int(payload, "completed_count")
        self._queue_event("sprint_completed", dict(cast(dict[str, Any], payload)))

    def _on_sprint_iteration(self, payload: EventPayload) -> None:
        """Handle SPRINT_ITERATION event."""
        with self._lock:
            self._state.current_iteration = _get_int(payload, "iteration")
            self._state.completed_issues = _get_int(payload, "completed_count")
        self._queue_event("sprint_iteration", dict(cast(dict[str, Any], payload)))

    def _on_selecting_issue(self, payload: EventPayload) -> None:
        """Handle SELECTING_ISSUE event."""
        with self._lock:
            self._state.current_step = "selecting-issue"
            self._state.step_start_time = datetime.now(timezone.utc)
        self._queue_event("selecting_issue", dict(cast(dict[str, Any], payload)))

    def _on_issue_started(self, payload: EventPayload) -> None:
        """Handle ISSUE_STARTED event."""
        with self._lock:
            self._state.current_issue_id = _get_str(payload, "issue_id")
            self._state.current_issue_name = _get_str(payload, "issue_name")
            self._state.retry_count = 0
            self._state.total_iterations = 0
            self._state.clear_output()
        self._queue_event("issue_started", dict(cast(dict[str, Any], payload)))

    def _on_issue_completed(self, payload: EventPayload) -> None:
        """Handle ISSUE_COMPLETED event."""
        with self._lock:
            self._state.completed_issues += 1
            old_issue = self._state.current_issue_id
            self._state.current_issue_id = ""
            self._state.current_issue_name = ""
            self._state.current_step = ""
        self._queue_event(
            "issue_completed", {**dict(cast(dict[str, Any], payload)), "issue_id": old_issue}
        )

    def _on_issue_failed(self, payload: EventPayload) -> None:
        """Handle ISSUE_FAILED event."""
        self._queue_event("issue_failed", dict(cast(dict[str, Any], payload)))

    def _on_issue_iteration(self, payload: EventPayload) -> None:
        """Handle ISSUE_ITERATION event."""
        with self._lock:
            self._state.total_iterations = _get_int(payload, "total_iterations")
            self._state.max_iterations = _get_int(payload, "max_iterations", 50)
            self._state.retry_count = _get_int(payload, "retry_count")
            self._state.max_retry = _get_int(payload, "max_retry", 5)
        self._queue_event("issue_iteration", dict(cast(dict[str, Any], payload)))

    def _on_step_started(self, payload: EventPayload) -> None:
        """Handle STEP_STARTED event."""
        with self._lock:
            self._state.current_step = _get_str(payload, "step_name")
            self._state.step_start_time = datetime.now(timezone.utc)
        self._queue_event("step_started", dict(cast(dict[str, Any], payload)))

    def _on_step_completed(self, payload: EventPayload) -> None:
        """Handle STEP_COMPLETED event."""
        self._queue_event("step_completed", dict(cast(dict[str, Any], payload)))

    def _on_step_failed(self, payload: EventPayload) -> None:
        """Handle STEP_FAILED event."""
        with self._lock:
            self._state.retry_count = _get_int(payload, "retry_count")
        self._queue_event("step_failed", dict(cast(dict[str, Any], payload)))

    def _on_step_skipped(self, payload: EventPayload) -> None:
        """Handle STEP_SKIPPED event."""
        self._queue_event("step_skipped", dict(cast(dict[str, Any], payload)))

    def _on_subprocess_started(self, payload: EventPayload) -> None:
        """Handle SUBPROCESS_STARTED event."""
        with self._lock:
            self._state.subprocess_pid = _get_optional_int(payload, "pid")
            self._state.subprocess_command = _get_str(payload, "command")
            self._state.add_output(f"> {self._state.subprocess_command}")
        self._queue_event("subprocess_started", dict(cast(dict[str, Any], payload)))

    def _on_subprocess_output(self, payload: EventPayload) -> None:
        """Handle SUBPROCESS_OUTPUT event."""
        line = _get_str(payload, "line")
        with self._lock:
            self._state.add_output(line)
        self._queue_event("subprocess_output", dict(cast(dict[str, Any], payload)))

    def _on_subprocess_ended(self, payload: EventPayload) -> None:
        """Handle SUBPROCESS_ENDED event."""
        with self._lock:
            self._state.subprocess_pid = None
            self._state.subprocess_command = ""
        self._queue_event("subprocess_ended", dict(cast(dict[str, Any], payload)))

    def _on_rate_limited(self, payload: EventPayload) -> None:
        """Handle RATE_LIMITED event."""
        self._queue_event("rate_limited", dict(cast(dict[str, Any], payload)))

    def _on_process_hung(self, payload: EventPayload) -> None:
        """Handle PROCESS_HUNG event."""
        self._queue_event("process_hung", dict(cast(dict[str, Any], payload)))

    def _on_routing_signal(self, payload: EventPayload) -> None:
        """Handle ROUTING_SIGNAL event."""
        self._queue_event("routing_signal", dict(cast(dict[str, Any], payload)))

    def _on_output(self, payload: EventPayload) -> None:
        """Handle OUTPUT event."""
        text = _get_str(payload, "text")
        with self._lock:
            self._state.add_output(text)
        self._queue_event("output", dict(cast(dict[str, Any], payload)))
