"""Tests for workflow event bus."""

import threading

from claudesprint.events.workflow_event_bus import (
    IssueEventPayload,
    IssueIterationPayload,
    OutputPayload,
    ProcessHungPayload,
    RoutingSignalPayload,
    SelectingIssuePayload,
    SprintEventPayload,
    SprintIterationPayload,
    StepEventPayload,
    StepSkippedPayload,
    SubprocessOutputPayload,
    SubprocessStartedPayload,
    WorkflowEvent,
    WorkflowEventBus,
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

        def failing_handler(_payload) -> None:
            raise ValueError("Intentional test error")

        def working_handler(payload) -> None:
            calls.append(payload)

        bus.subscribe(WorkflowEvent.SPRINT_STARTED, failing_handler)
        bus.subscribe(WorkflowEvent.SPRINT_STARTED, working_handler)

        payload: SprintEventPayload = {
            "sprint_id": "sprint-1",
            "completed_count": 5,
            "total_count": 10,
            "timestamp": "2024-01-01T00:00:00Z",
        }

        # Should not raise
        bus.emit(WorkflowEvent.SPRINT_STARTED, payload)

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
            def handler(_payload) -> None:
                with lock:
                    handlers_called.append(n)
            return handler

        threads = []
        for i in range(10):
            t = threading.Thread(
                target=lambda n=i: bus.subscribe(WorkflowEvent.OUTPUT, create_handler(n))
            )
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Emit and check all handlers were registered
        payload: OutputPayload = {
            "text": "test output",
            "source": "test",
            "timestamp": "2024-01-01T00:00:00Z",
        }
        bus.emit(WorkflowEvent.OUTPUT, payload)

        assert len(handlers_called) == 10

    def test_all_event_types_can_be_used(self) -> None:
        """All WorkflowEvent types should be usable."""
        bus = WorkflowEventBus()
        called = []

        for event in WorkflowEvent:
            bus.subscribe(event, lambda _p, e=event: called.append(e))

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

    def test_step_skipped_event(self) -> None:
        """STEP_SKIPPED event should be emitted with correct payload."""
        bus = WorkflowEventBus()
        received: list[StepSkippedPayload] = []

        def handler(payload: StepSkippedPayload) -> None:
            received.append(payload)

        bus.subscribe(WorkflowEvent.STEP_SKIPPED, handler)

        payload: StepSkippedPayload = {
            "issue_id": "issue-1",
            "step_name": "write-tests",
            "next_step": "browser-validation",
            "timestamp": "2024-01-01T00:00:00Z",
        }
        bus.emit(WorkflowEvent.STEP_SKIPPED, payload)

        assert len(received) == 1
        assert received[0]["issue_id"] == "issue-1"
        assert received[0]["step_name"] == "write-tests"
        assert received[0]["next_step"] == "browser-validation"

    def test_process_hung_event(self) -> None:
        """PROCESS_HUNG event should be emitted with correct payload."""
        bus = WorkflowEventBus()
        received: list[ProcessHungPayload] = []

        def handler(payload: ProcessHungPayload) -> None:
            received.append(payload)

        bus.subscribe(WorkflowEvent.PROCESS_HUNG, handler)

        payload: ProcessHungPayload = {
            "step_name": "implement",
            "seconds_inactive": 600,
            "timestamp": "2024-01-01T00:00:00Z",
        }
        bus.emit(WorkflowEvent.PROCESS_HUNG, payload)

        assert len(received) == 1
        assert received[0]["step_name"] == "implement"
        assert received[0]["seconds_inactive"] == 600

    def test_step_skipped_with_none_next_step(self) -> None:
        """STEP_SKIPPED event should handle None next_step."""
        bus = WorkflowEventBus()
        received: list[StepSkippedPayload] = []

        bus.subscribe(WorkflowEvent.STEP_SKIPPED, lambda p: received.append(p))

        payload: StepSkippedPayload = {
            "issue_id": "issue-1",
            "step_name": "complete-issue",
            "next_step": None,
            "timestamp": "2024-01-01T00:00:00Z",
        }
        bus.emit(WorkflowEvent.STEP_SKIPPED, payload)

        assert len(received) == 1
        assert received[0]["next_step"] is None

    def test_subprocess_started_event(self) -> None:
        """SUBPROCESS_STARTED event should be emitted with correct payload."""
        bus = WorkflowEventBus()
        received: list[SubprocessStartedPayload] = []

        bus.subscribe(WorkflowEvent.SUBPROCESS_STARTED, lambda p: received.append(p))

        payload: SubprocessStartedPayload = {
            "pid": 12345,
            "command": "claude --version",
            "issue_id": "issue-1",
            "step_name": "implement",
            "timestamp": "2024-01-01T00:00:00Z",
        }
        bus.emit(WorkflowEvent.SUBPROCESS_STARTED, payload)

        assert len(received) == 1
        assert received[0]["pid"] == 12345
        assert received[0]["command"] == "claude --version"

    def test_subprocess_output_event(self) -> None:
        """SUBPROCESS_OUTPUT event should be emitted with correct payload."""
        bus = WorkflowEventBus()
        received: list[SubprocessOutputPayload] = []

        bus.subscribe(WorkflowEvent.SUBPROCESS_OUTPUT, lambda p: received.append(p))

        payload: SubprocessOutputPayload = {
            "line": "Processing file...",
            "issue_id": "issue-1",
            "step_name": "implement",
            "timestamp": "2024-01-01T00:00:00Z",
        }
        bus.emit(WorkflowEvent.SUBPROCESS_OUTPUT, payload)

        assert len(received) == 1
        assert received[0]["line"] == "Processing file..."

    def test_issue_iteration_event(self) -> None:
        """ISSUE_ITERATION event should be emitted with correct payload."""
        bus = WorkflowEventBus()
        received: list[IssueIterationPayload] = []

        bus.subscribe(WorkflowEvent.ISSUE_ITERATION, lambda p: received.append(p))

        payload: IssueIterationPayload = {
            "total_iterations": 5,
            "max_iterations": 50,
            "retry_count": 1,
            "max_retry": 3,
            "issue_id": "issue-1",
            "timestamp": "2024-01-01T00:00:00Z",
        }
        bus.emit(WorkflowEvent.ISSUE_ITERATION, payload)

        assert len(received) == 1
        assert received[0]["total_iterations"] == 5
        assert received[0]["max_iterations"] == 50

    def test_routing_signal_event(self) -> None:
        """ROUTING_SIGNAL event should be emitted with correct payload."""
        bus = WorkflowEventBus()
        received: list[RoutingSignalPayload] = []

        bus.subscribe(WorkflowEvent.ROUTING_SIGNAL, lambda p: received.append(p))

        payload: RoutingSignalPayload = {
            "step_name": "run-tests",
            "signal": "pass",
            "next_step": "browser-validation",
            "issue_id": "issue-1",
            "timestamp": "2024-01-01T00:00:00Z",
        }
        bus.emit(WorkflowEvent.ROUTING_SIGNAL, payload)

        assert len(received) == 1
        assert received[0]["signal"] == "pass"
        assert received[0]["next_step"] == "browser-validation"

    def test_sprint_iteration_event(self) -> None:
        """SPRINT_ITERATION event should be emitted with correct payload."""
        bus = WorkflowEventBus()
        received: list[SprintIterationPayload] = []

        bus.subscribe(WorkflowEvent.SPRINT_ITERATION, lambda p: received.append(p))

        payload: SprintIterationPayload = {
            "iteration": 3,
            "available_issues": 5,
            "completed_count": 2,
            "total_count": 7,
            "sprint_id": "SPEC_01",
            "timestamp": "2024-01-01T00:00:00Z",
        }
        bus.emit(WorkflowEvent.SPRINT_ITERATION, payload)

        assert len(received) == 1
        assert received[0]["iteration"] == 3
        assert received[0]["available_issues"] == 5

    def test_selecting_issue_event(self) -> None:
        """SELECTING_ISSUE event should be emitted with correct payload."""
        bus = WorkflowEventBus()
        received: list[SelectingIssuePayload] = []

        bus.subscribe(WorkflowEvent.SELECTING_ISSUE, lambda p: received.append(p))

        payload: SelectingIssuePayload = {
            "sprint_id": "SPEC_01",
            "timestamp": "2024-01-01T00:00:00Z",
        }
        bus.emit(WorkflowEvent.SELECTING_ISSUE, payload)

        assert len(received) == 1
        assert received[0]["sprint_id"] == "SPEC_01"

    def test_output_event(self) -> None:
        """OUTPUT event should be emitted with correct payload."""
        bus = WorkflowEventBus()
        received: list[OutputPayload] = []

        bus.subscribe(WorkflowEvent.OUTPUT, lambda p: received.append(p))

        payload: OutputPayload = {
            "text": "Starting sprint execution...",
            "source": "sprint_engine",
            "timestamp": "2024-01-01T00:00:00Z",
        }
        bus.emit(WorkflowEvent.OUTPUT, payload)

        assert len(received) == 1
        assert received[0]["text"] == "Starting sprint execution..."
        assert received[0]["source"] == "sprint_engine"
