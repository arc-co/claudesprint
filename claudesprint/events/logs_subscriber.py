"""Event subscriber that connects workflow events to SimpleLogsOutput.

This module provides a LogsEventSubscriber class that bridges the event bus
to the SimpleLogsOutput logging system, converting event payloads to method calls.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from claudesprint.events.workflow_event_bus import (
    EventPayload,
    WorkflowEvent,
    WorkflowEventBus,
)
from claudesprint.models.current_issue import IssueStep

if TYPE_CHECKING:
    from claudesprint.simple_logs import SimpleLogsOutput


class LogsEventSubscriber:
    """Subscribes to workflow events and forwards them to SimpleLogsOutput.

    This adapter converts event payloads from the event bus into method calls
    on SimpleLogsOutput, enabling event-driven logging without direct callbacks.

    Example:
        output = SimpleLogsOutput(console)
        event_bus = WorkflowEventBus()

        subscriber = LogsEventSubscriber(output, event_bus)
        subscriber.connect()

        # Events emitted on event_bus will now appear in output
        event_bus.emit(WorkflowEvent.STEP_STARTED, {...})

        subscriber.disconnect()
    """

    def __init__(
        self,
        output: SimpleLogsOutput,
        event_bus: WorkflowEventBus,
    ) -> None:
        """Initialize the subscriber.

        Args:
            output: SimpleLogsOutput instance to forward events to.
            event_bus: WorkflowEventBus to subscribe to.
        """
        self._output = output
        self._event_bus = event_bus
        self._connected = False

    def connect(self) -> None:
        """Subscribe to all relevant workflow events."""
        if self._connected:
            return

        # Step events
        self._event_bus.subscribe(WorkflowEvent.STEP_STARTED, self._on_step_started)
        self._event_bus.subscribe(WorkflowEvent.STEP_COMPLETED, self._on_step_completed)
        self._event_bus.subscribe(WorkflowEvent.STEP_SKIPPED, self._on_step_skipped)
        self._event_bus.subscribe(WorkflowEvent.STEP_FAILED, self._on_step_failed)

        # Issue events
        self._event_bus.subscribe(WorkflowEvent.ISSUE_STARTED, self._on_issue_started)
        self._event_bus.subscribe(WorkflowEvent.ISSUE_COMPLETED, self._on_issue_completed)
        self._event_bus.subscribe(WorkflowEvent.ISSUE_ITERATION, self._on_issue_iteration)
        self._event_bus.subscribe(WorkflowEvent.ROUTING_SIGNAL, self._on_routing_signal)

        # Sprint events
        self._event_bus.subscribe(WorkflowEvent.SPRINT_STARTED, self._on_sprint_started)
        self._event_bus.subscribe(WorkflowEvent.SPRINT_COMPLETED, self._on_sprint_completed)
        self._event_bus.subscribe(WorkflowEvent.SPRINT_ITERATION, self._on_sprint_iteration)
        self._event_bus.subscribe(WorkflowEvent.SELECTING_ISSUE, self._on_selecting_issue)

        # Subprocess events
        self._event_bus.subscribe(WorkflowEvent.SUBPROCESS_STARTED, self._on_subprocess_started)
        self._event_bus.subscribe(WorkflowEvent.SUBPROCESS_OUTPUT, self._on_subprocess_output)
        self._event_bus.subscribe(WorkflowEvent.SUBPROCESS_ENDED, self._on_subprocess_ended)

        # General output
        self._event_bus.subscribe(WorkflowEvent.OUTPUT, self._on_output)

        self._connected = True

    def disconnect(self) -> None:
        """Unsubscribe from all workflow events."""
        if not self._connected:
            return

        # Step events
        self._event_bus.unsubscribe(WorkflowEvent.STEP_STARTED, self._on_step_started)
        self._event_bus.unsubscribe(WorkflowEvent.STEP_COMPLETED, self._on_step_completed)
        self._event_bus.unsubscribe(WorkflowEvent.STEP_SKIPPED, self._on_step_skipped)
        self._event_bus.unsubscribe(WorkflowEvent.STEP_FAILED, self._on_step_failed)

        # Issue events
        self._event_bus.unsubscribe(WorkflowEvent.ISSUE_STARTED, self._on_issue_started)
        self._event_bus.unsubscribe(WorkflowEvent.ISSUE_COMPLETED, self._on_issue_completed)
        self._event_bus.unsubscribe(WorkflowEvent.ISSUE_ITERATION, self._on_issue_iteration)
        self._event_bus.unsubscribe(WorkflowEvent.ROUTING_SIGNAL, self._on_routing_signal)

        # Sprint events
        self._event_bus.unsubscribe(WorkflowEvent.SPRINT_STARTED, self._on_sprint_started)
        self._event_bus.unsubscribe(WorkflowEvent.SPRINT_COMPLETED, self._on_sprint_completed)
        self._event_bus.unsubscribe(WorkflowEvent.SPRINT_ITERATION, self._on_sprint_iteration)
        self._event_bus.unsubscribe(WorkflowEvent.SELECTING_ISSUE, self._on_selecting_issue)

        # Subprocess events
        self._event_bus.unsubscribe(WorkflowEvent.SUBPROCESS_STARTED, self._on_subprocess_started)
        self._event_bus.unsubscribe(WorkflowEvent.SUBPROCESS_OUTPUT, self._on_subprocess_output)
        self._event_bus.unsubscribe(WorkflowEvent.SUBPROCESS_ENDED, self._on_subprocess_ended)

        # General output
        self._event_bus.unsubscribe(WorkflowEvent.OUTPUT, self._on_output)

        self._connected = False

    def _step_from_name(self, step_name: str) -> IssueStep | None:
        """Convert a step name string to IssueStep enum.

        Args:
            step_name: Step name string (e.g., "implement", "run-tests").

        Returns:
            IssueStep enum value, or None if not found.
        """
        try:
            return IssueStep(step_name)
        except ValueError:
            return None

    # Event handlers

    def _on_step_started(self, payload: EventPayload) -> None:
        """Handle STEP_STARTED event."""
        step = self._step_from_name(payload.get("step_name", ""))
        model = payload.get("model", "opus")
        if step:
            self._output.on_step_start(step, model)

    def _on_step_completed(self, payload: EventPayload) -> None:
        """Handle STEP_COMPLETED event."""
        step = self._step_from_name(payload.get("step_name", ""))
        next_step_name = payload.get("next_step")
        next_step = self._step_from_name(next_step_name) if next_step_name else None
        if step:
            self._output.on_step_complete(step, next_step)

    def _on_step_skipped(self, payload: EventPayload) -> None:
        """Handle STEP_SKIPPED event."""
        step = self._step_from_name(payload.get("step_name", ""))
        next_step_name = payload.get("next_step")
        next_step = self._step_from_name(next_step_name) if next_step_name else None
        if step:
            self._output.on_step_skip(step, next_step)

    def _on_step_failed(self, payload: EventPayload) -> None:
        """Handle STEP_FAILED event."""
        step = self._step_from_name(payload.get("step_name", ""))
        retry_count = payload.get("retry_count", payload.get("step_index", 0))
        max_retry = payload.get("max_retry", 5)
        if step:
            self._output.on_step_failure(step, retry_count, max_retry)

    def _on_issue_started(self, payload: EventPayload) -> None:
        """Handle ISSUE_STARTED event."""
        issue_id = payload.get("issue_id", "")
        issue_name = payload.get("issue_name", "")
        self._output.on_issue_entered(issue_id, issue_name)
        self._output.set_issue(issue_id, issue_name)

    def _on_issue_completed(self, payload: EventPayload) -> None:
        """Handle ISSUE_COMPLETED event."""
        issue_id = payload.get("issue_id", "")
        exit_reason = payload.get("exit_reason", "completed")
        self._output.on_issue_complete(issue_id)
        self._output.on_issue_exited(issue_id, exit_reason)

    def _on_issue_iteration(self, payload: EventPayload) -> None:
        """Handle ISSUE_ITERATION event."""
        self._output.on_issue_iteration(
            payload.get("total_iterations", 0),
            payload.get("max_iterations", 50),
            payload.get("retry_count", 0),
            payload.get("max_retry", 5),
        )

    def _on_routing_signal(self, payload: EventPayload) -> None:
        """Handle ROUTING_SIGNAL event."""
        step = self._step_from_name(payload.get("step_name", ""))
        signal = payload.get("signal")
        next_step_name = payload.get("next_step")
        next_step = self._step_from_name(next_step_name) if next_step_name else None
        if step:
            self._output.on_routing_signal(step, signal, next_step)

    def _on_sprint_started(self, payload: EventPayload) -> None:
        """Handle SPRINT_STARTED event."""
        spec_id = payload.get("sprint_id", "")
        total = payload.get("total_count", 0)
        completed = payload.get("completed_count", 0)
        self._output.on_sprint_entered(spec_id, total, completed)

    def _on_sprint_completed(self, payload: EventPayload) -> None:
        """Handle SPRINT_COMPLETED event."""
        spec_id = payload.get("sprint_id", "")
        total = payload.get("total_count", 0)
        completed = payload.get("completed_count", 0)
        self._output.on_sprint_exited(spec_id, total, completed)

    def _on_sprint_iteration(self, payload: EventPayload) -> None:
        """Handle SPRINT_ITERATION event."""
        iteration = payload.get("iteration", 0)
        available_issues = payload.get("available_issues", 0)
        self._output.on_sprint_iteration(iteration, available_issues)

    def _on_selecting_issue(self, payload: EventPayload) -> None:  # noqa: ARG002
        """Handle SELECTING_ISSUE event."""
        self._output.on_selecting_issue()

    def _on_subprocess_started(self, payload: EventPayload) -> None:
        """Handle SUBPROCESS_STARTED event."""
        pid = payload.get("pid", 0)
        command = payload.get("command", "")
        self._output.on_subprocess_start(pid, command)

    def _on_subprocess_output(self, payload: EventPayload) -> None:
        """Handle SUBPROCESS_OUTPUT event."""
        line = payload.get("line", "")
        self._output.on_subprocess_output(line)

    def _on_subprocess_ended(self, payload: EventPayload) -> None:  # noqa: ARG002
        """Handle SUBPROCESS_ENDED event."""
        self._output.on_subprocess_end()

    def _on_output(self, payload: EventPayload) -> None:
        """Handle OUTPUT event."""
        text = payload.get("text", "")
        self._output.on_output(text)
