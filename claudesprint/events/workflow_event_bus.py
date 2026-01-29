"""Thread-safe pub/sub event bus for workflow events."""

import logging
import threading
from collections import defaultdict
from enum import Enum, auto
from typing import Callable, TypedDict

logger = logging.getLogger(__name__)


class WorkflowEvent(Enum):
    """Workflow event types."""

    STEP_STARTED = auto()
    STEP_COMPLETED = auto()
    STEP_FAILED = auto()
    ISSUE_STARTED = auto()
    ISSUE_COMPLETED = auto()
    ISSUE_FAILED = auto()
    SPRINT_STARTED = auto()
    SPRINT_PROGRESS = auto()
    SPRINT_COMPLETED = auto()
    RATE_LIMITED = auto()
    STATE_PERSISTED = auto()


class StepEventPayload(TypedDict):
    """Payload for step-related events."""

    issue_id: str
    step_name: str
    step_index: int
    timestamp: str


class IssueEventPayload(TypedDict):
    """Payload for issue-related events."""

    issue_id: str
    issue_name: str
    exit_reason: str | None
    timestamp: str


class SprintEventPayload(TypedDict):
    """Payload for sprint-related events."""

    sprint_id: str
    completed_count: int
    total_count: int
    timestamp: str


EventPayload = StepEventPayload | IssueEventPayload | SprintEventPayload


class WorkflowEventBus:
    """Thread-safe pub/sub event bus for workflow events.

    Allows components to subscribe to workflow events and receive notifications
    when those events occur. Handler exceptions are logged but don't prevent
    other handlers from being called.

    Example:
        bus = WorkflowEventBus()

        def on_step_started(payload: EventPayload) -> None:
            print(f"Step started: {payload['step_name']}")

        bus.subscribe(WorkflowEvent.STEP_STARTED, on_step_started)
        bus.emit(WorkflowEvent.STEP_STARTED, {
            "issue_id": "issue-1",
            "step_name": "implement",
            "step_index": 0,
            "timestamp": "2024-01-01T00:00:00Z"
        })
    """

    def __init__(self) -> None:
        """Initialize the event bus."""
        self._subscribers: dict[WorkflowEvent, list[Callable[[EventPayload], None]]] = (
            defaultdict(list)
        )
        self._lock = threading.Lock()

    def subscribe(
        self,
        event: WorkflowEvent,
        handler: Callable[[EventPayload], None],
    ) -> None:
        """Register a handler for an event type.

        Args:
            event: The event type to subscribe to
            handler: Callback function that receives the event payload
        """
        with self._lock:
            self._subscribers[event].append(handler)

    def unsubscribe(
        self,
        event: WorkflowEvent,
        handler: Callable[[EventPayload], None],
    ) -> None:
        """Remove a handler registration.

        Args:
            event: The event type to unsubscribe from
            handler: The handler function to remove
        """
        with self._lock:
            if event in self._subscribers:
                try:
                    self._subscribers[event].remove(handler)
                except ValueError:
                    pass  # Handler not found, ignore

    def emit(self, event: WorkflowEvent, payload: EventPayload) -> None:
        """Emit an event to all subscribers.

        Handler exceptions are logged but don't stop other handlers from
        being called.

        Args:
            event: The event type to emit
            payload: The event payload data
        """
        with self._lock:
            handlers = list(self._subscribers.get(event, []))

        for handler in handlers:
            try:
                handler(payload)
            except Exception as e:
                logger.exception(
                    f"Handler {handler.__name__} raised exception for {event.name}: {e}"
                )
