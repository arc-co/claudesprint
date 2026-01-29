"""Tests for workflow event bus."""

import threading
import pytest

from claudesprint.events.workflow_event_bus import (
    WorkflowEvent,
    WorkflowEventBus,
    StepEventPayload,
    IssueEventPayload,
    SprintEventPayload,
)


class TestWorkflowEventBus:
    """Tests for WorkflowEventBus."""

    def test_subscribe_then_emit_calls_handler(self) -> None:
        """Subscribe then emit should call the handler."""
        bus = WorkflowEventBus()
        called = []

        def handler(payload: StepEventPayload) -> None:
            called.append(payload)

        bus.subscribe(WorkflowEvent.STEP_STARTED, handler)
        payload: StepEventPayload = {
            "issue_id": "issue-1",
            "step_name": "implement",
            "step_index": 0,
            "timestamp": "2024-01-01T00:00:00Z",
        }
        bus.emit(WorkflowEvent.STEP_STARTED, payload)

        assert len(called) == 1
        assert called[0]["issue_id"] == "issue-1"
        assert called[0]["step_name"] == "implement"

    def test_multiple_subscribers_all_called(self) -> None:
        """Multiple subscribers for same event should all be called."""
        bus = WorkflowEventBus()
        calls_1 = []
        calls_2 = []
        calls_3 = []

        bus.subscribe(WorkflowEvent.ISSUE_COMPLETED, lambda p: calls_1.append(p))
        bus.subscribe(WorkflowEvent.ISSUE_COMPLETED, lambda p: calls_2.append(p))
        bus.subscribe(WorkflowEvent.ISSUE_COMPLETED, lambda p: calls_3.append(p))

        payload: IssueEventPayload = {
            "issue_id": "issue-1",
            "issue_name": "Test Issue",
            "exit_reason": None,
            "timestamp": "2024-01-01T00:00:00Z",
        }
        bus.emit(WorkflowEvent.ISSUE_COMPLETED, payload)

        assert len(calls_1) == 1
        assert len(calls_2) == 1
        assert len(calls_3) == 1

    def test_unsubscribe_removes_handler(self) -> None:
        """Unsubscribe should prevent handler from being called."""
        bus = WorkflowEventBus()
        called = []

        def handler(payload) -> None:
            called.append(payload)

        bus.subscribe(WorkflowEvent.STEP_COMPLETED, handler)
        bus.unsubscribe(WorkflowEvent.STEP_COMPLETED, handler)

        payload: StepEventPayload = {
            "issue_id": "issue-1",
            "step_name": "implement",
            "step_index": 0,
            "timestamp": "2024-01-01T00:00:00Z",
        }
        bus.emit(WorkflowEvent.STEP_COMPLETED, payload)

        assert len(called) == 0

    def test_handler_exception_does_not_break_others(self) -> None:
        """Handler exception should not prevent other handlers from running."""
        bus = WorkflowEventBus()
        calls = []

        def failing_handler(payload) -> None:
            raise ValueError("Intentional test error")

        def working_handler(payload) -> None:
            calls.append(payload)

        bus.subscribe(WorkflowEvent.SPRINT_PROGRESS, failing_handler)
        bus.subscribe(WorkflowEvent.SPRINT_PROGRESS, working_handler)

        payload: SprintEventPayload = {
            "sprint_id": "sprint-1",
            "completed_count": 5,
            "total_count": 10,
            "timestamp": "2024-01-01T00:00:00Z",
        }

        # Should not raise
        bus.emit(WorkflowEvent.SPRINT_PROGRESS, payload)

        # Working handler should still be called
        assert len(calls) == 1
        assert calls[0]["sprint_id"] == "sprint-1"

    def test_emit_with_no_subscribers_is_noop(self) -> None:
        """Emitting with no subscribers should not raise."""
        bus = WorkflowEventBus()
        payload: StepEventPayload = {
            "issue_id": "issue-1",
            "step_name": "implement",
            "step_index": 0,
            "timestamp": "2024-01-01T00:00:00Z",
        }

        # Should not raise
        bus.emit(WorkflowEvent.STEP_STARTED, payload)

    def test_different_events_are_independent(self) -> None:
        """Subscribers to different events should be independent."""
        bus = WorkflowEventBus()
        step_calls = []
        issue_calls = []

        bus.subscribe(WorkflowEvent.STEP_STARTED, lambda p: step_calls.append(p))
        bus.subscribe(WorkflowEvent.ISSUE_STARTED, lambda p: issue_calls.append(p))

        step_payload: StepEventPayload = {
            "issue_id": "issue-1",
            "step_name": "implement",
            "step_index": 0,
            "timestamp": "2024-01-01T00:00:00Z",
        }
        bus.emit(WorkflowEvent.STEP_STARTED, step_payload)

        assert len(step_calls) == 1
        assert len(issue_calls) == 0

    def test_unsubscribe_nonexistent_handler_is_noop(self) -> None:
        """Unsubscribing a handler that was never subscribed should not raise."""
        bus = WorkflowEventBus()

        def handler(payload) -> None:
            pass

        # Should not raise
        bus.unsubscribe(WorkflowEvent.STEP_STARTED, handler)

    def test_thread_safety_subscribe(self) -> None:
        """Subscribing from multiple threads should be safe."""
        bus = WorkflowEventBus()
        handlers_called = []
        lock = threading.Lock()

        def create_handler(n: int):
            def handler(payload) -> None:
                with lock:
                    handlers_called.append(n)
            return handler

        threads = []
        for i in range(10):
            t = threading.Thread(
                target=lambda n=i: bus.subscribe(WorkflowEvent.STATE_PERSISTED, create_handler(n))
            )
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Emit and check all handlers were registered
        payload: StepEventPayload = {
            "issue_id": "issue-1",
            "step_name": "implement",
            "step_index": 0,
            "timestamp": "2024-01-01T00:00:00Z",
        }
        bus.emit(WorkflowEvent.STATE_PERSISTED, payload)

        assert len(handlers_called) == 10

    def test_all_event_types_can_be_used(self) -> None:
        """All WorkflowEvent types should be usable."""
        bus = WorkflowEventBus()
        called = []

        for event in WorkflowEvent:
            bus.subscribe(event, lambda p, e=event: called.append(e))

        # Emit each event type
        step_payload: StepEventPayload = {
            "issue_id": "issue-1",
            "step_name": "test",
            "step_index": 0,
            "timestamp": "2024-01-01T00:00:00Z",
        }
        for event in WorkflowEvent:
            bus.emit(event, step_payload)

        assert len(called) == len(WorkflowEvent)
