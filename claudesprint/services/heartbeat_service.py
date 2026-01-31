"""Heartbeat service for detecting hung processes."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Callable

from claudesprint.events.workflow_event_bus import WorkflowEvent

if TYPE_CHECKING:
    from claudesprint.events.workflow_event_bus import WorkflowEventBus
    from claudesprint.models.current_issue import IssueStep as WorkflowStep

logger = logging.getLogger(__name__)


class HeartbeatService:
    """Service for monitoring workflow activity and detecting hung processes.

    Runs a background thread that monitors for inactivity and triggers
    a callback when no activity is detected for a configured timeout period.
    """

    # Default check interval (can be overridden via config)
    DEFAULT_CHECK_INTERVAL = 10.0

    def __init__(
        self,
        timeout_seconds: int = 600,
        enabled: bool = True,
        on_hung: Callable[[str, int], None] | None = None,
        check_interval: float | None = None,
        event_bus: WorkflowEventBus | None = None,
    ) -> None:
        """Initialize the heartbeat service.

        Args:
            timeout_seconds: Seconds of inactivity before triggering hung detection.
            enabled: Whether heartbeat monitoring is enabled.
            on_hung: Callback when hung process detected (step_name, seconds_inactive).
            check_interval: How often to check for inactivity (from config).
            event_bus: Optional event bus for emitting PROCESS_HUNG events.
        """
        self._timeout_seconds = timeout_seconds
        self._enabled = enabled
        self._on_hung = on_hung
        self._check_interval = check_interval if check_interval is not None else self.DEFAULT_CHECK_INTERVAL
        self._event_bus = event_bus

        self._last_pulse: float = 0
        self._current_step: str = ""
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()

        # Track if we've already notified for current hung state
        self._hung_notified = False

    def pulse(self, step: "WorkflowStep | str") -> None:
        """Record activity pulse, resetting the inactivity timer.

        Args:
            step: The current workflow step.
        """
        with self._lock:
            self._last_pulse = time.time()
            step_name = step.value if hasattr(step, 'value') else str(step)
            if step_name != self._current_step:
                self._current_step = step_name
                self._hung_notified = False  # Reset notification flag on step change

    def start(self) -> None:
        """Start the heartbeat monitoring thread."""
        if not self._enabled:
            return

        with self._lock:
            if self._running:
                return
            self._running = True
            self._last_pulse = time.time()
            self._stop_event.clear()

        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the heartbeat monitoring thread."""
        with self._lock:
            if not self._running:
                return
            self._running = False
            self._stop_event.set()

        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _monitor_loop(self) -> None:
        """Background thread loop that checks for inactivity."""
        while not self._stop_event.is_set():
            # Check at configured interval
            self._stop_event.wait(self._check_interval)

            if self._stop_event.is_set():
                break

            with self._lock:
                if not self._running:
                    break

                if self._last_pulse == 0:
                    continue

                elapsed = time.time() - self._last_pulse
                should_notify = elapsed >= self._timeout_seconds and not self._hung_notified
                if should_notify:
                    step = self._current_step
                    self._hung_notified = True

            # Call callback and emit event outside of lock (only once per hung state)
            if should_notify:
                # Emit PROCESS_HUNG event
                if self._event_bus:
                    try:
                        self._event_bus.emit(WorkflowEvent.PROCESS_HUNG, {
                            "step_name": step,
                            "seconds_inactive": int(elapsed),
                            "timestamp": datetime.now(UTC).isoformat(),
                        })
                    except Exception as e:
                        logger.warning(f"Failed to emit PROCESS_HUNG event: {e}")

                # Call callback
                if self._on_hung:
                    try:
                        self._on_hung(step, int(elapsed))
                    except Exception as e:
                        logger.warning(f"Heartbeat callback failed: {e}")

    @property
    def is_running(self) -> bool:
        """Check if heartbeat monitoring is running."""
        with self._lock:
            return self._running

    @property
    def seconds_since_pulse(self) -> int:
        """Get seconds since last pulse."""
        with self._lock:
            if self._last_pulse == 0:
                return 0
            return int(time.time() - self._last_pulse)

    def reset(self) -> None:
        """Reset the service state (for testing)."""
        self.stop()
        with self._lock:
            self._last_pulse = 0
            self._current_step = ""
            self._hung_notified = False


class AsyncHeartbeatService:
    """Async heartbeat service using asyncio instead of threads.

    This service monitors workflow activity and detects hung processes
    using an asyncio task instead of a background thread.
    """

    # Default check interval (can be overridden via config)
    DEFAULT_CHECK_INTERVAL = 10.0

    def __init__(
        self,
        timeout_seconds: int = 600,
        enabled: bool = True,
        on_hung: Callable[[str, int], None] | None = None,
        check_interval: float | None = None,
        event_bus: "WorkflowEventBus | None" = None,
    ) -> None:
        """Initialize the async heartbeat service.

        Args:
            timeout_seconds: Seconds of inactivity before triggering hung detection.
            enabled: Whether heartbeat monitoring is enabled.
            on_hung: Callback when hung process detected (step_name, seconds_inactive).
            check_interval: How often to check for inactivity (from config).
            event_bus: Optional event bus for emitting PROCESS_HUNG events.
        """
        self._timeout_seconds = timeout_seconds
        self._enabled = enabled
        self._on_hung = on_hung
        self._check_interval = check_interval if check_interval is not None else self.DEFAULT_CHECK_INTERVAL
        self._event_bus = event_bus

        self._last_pulse: float = 0
        self._current_step: str = ""
        self._running = False
        self._monitor_task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

        # Track if we've already notified for current hung state
        self._hung_notified = False

        # Use threading.Lock for pulse() since it's called from sync code paths
        # (e.g., output handlers). This provides cross-thread safety.
        self._lock = threading.Lock()

    def pulse(self, step: "WorkflowStep | str") -> None:
        """Record activity pulse, resetting the inactivity timer.

        This method is synchronous to allow calling from sync code paths
        (e.g., output handlers in ClaudeRunner callbacks).

        Args:
            step: The current workflow step.
        """
        with self._lock:
            self._last_pulse = time.time()
            step_name = step.value if hasattr(step, 'value') else str(step)
            if step_name != self._current_step:
                self._current_step = step_name
                self._hung_notified = False  # Reset notification flag on step change

    async def start(self) -> None:
        """Start the async heartbeat monitoring task."""
        if not self._enabled:
            return

        with self._lock:
            if self._running:
                return
            self._running = True
            self._last_pulse = time.time()

        self._stop_event.clear()
        self._monitor_task = asyncio.create_task(self._monitor_loop())

    async def stop(self) -> None:
        """Stop the async heartbeat monitoring task."""
        with self._lock:
            if not self._running:
                return
            self._running = False

        self._stop_event.set()

        if self._monitor_task:
            try:
                # Give the task a moment to notice the stop event
                await asyncio.wait_for(self._monitor_task, timeout=2.0)
            except asyncio.TimeoutError:
                logger.warning("Heartbeat monitor task did not stop in time, cancelling")
                self._monitor_task.cancel()
                try:
                    await self._monitor_task
                except asyncio.CancelledError:
                    pass
            self._monitor_task = None

    async def _monitor_loop(self) -> None:
        """Async monitor loop that checks for inactivity."""
        while True:
            try:
                # Wait for either the stop event or timeout
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self._check_interval
                )
                # Stop event was set
                break
            except asyncio.TimeoutError:
                # Timeout expired - check for inactivity
                pass

            # Check inactivity under lock
            with self._lock:
                if not self._running:
                    break

                if self._last_pulse == 0:
                    continue

                elapsed = time.time() - self._last_pulse
                should_notify = elapsed >= self._timeout_seconds and not self._hung_notified
                if should_notify:
                    step = self._current_step
                    self._hung_notified = True

            # Call callback and emit event outside of lock (only once per hung state)
            if should_notify:
                # Emit PROCESS_HUNG event
                if self._event_bus:
                    try:
                        self._event_bus.emit(WorkflowEvent.PROCESS_HUNG, {
                            "step_name": step,
                            "seconds_inactive": int(elapsed),
                            "timestamp": datetime.now(UTC).isoformat(),
                        })
                    except Exception as e:
                        logger.warning(f"Failed to emit PROCESS_HUNG event: {e}")

                # Call callback
                if self._on_hung:
                    try:
                        self._on_hung(step, int(elapsed))
                    except Exception as e:
                        logger.warning(f"Heartbeat callback failed: {e}")

    @property
    def is_running(self) -> bool:
        """Check if heartbeat monitoring is running."""
        with self._lock:
            return self._running

    @property
    def seconds_since_pulse(self) -> int:
        """Get seconds since last pulse."""
        with self._lock:
            if self._last_pulse == 0:
                return 0
            return int(time.time() - self._last_pulse)

    async def reset(self) -> None:
        """Reset the service state (for testing)."""
        await self.stop()
        with self._lock:
            self._last_pulse = 0
            self._current_step = ""
            self._hung_notified = False

    async def __aenter__(self) -> "AsyncHeartbeatService":
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.stop()


# Global instances
_heartbeat_service: HeartbeatService | None = None
_async_heartbeat_service: AsyncHeartbeatService | None = None


def get_heartbeat_service(
    timeout_seconds: int = 600,
    enabled: bool = True,
    on_hung: Callable[[str, int], None] | None = None,
    check_interval: float | None = None,
    event_bus: "WorkflowEventBus | None" = None,
) -> HeartbeatService:
    """Get or create the global heartbeat service instance (thread-based).

    Args:
        timeout_seconds: Seconds of inactivity before triggering hung detection.
        enabled: Whether heartbeat monitoring is enabled.
        on_hung: Callback when hung process detected.
        check_interval: How often to check for inactivity (from config).
        event_bus: Optional event bus for emitting PROCESS_HUNG events.

    Returns:
        The global HeartbeatService instance.
    """
    global _heartbeat_service
    if _heartbeat_service is None:
        _heartbeat_service = HeartbeatService(
            timeout_seconds=timeout_seconds,
            enabled=enabled,
            on_hung=on_hung,
            check_interval=check_interval,
            event_bus=event_bus,
        )
    return _heartbeat_service


def get_async_heartbeat_service(
    timeout_seconds: int = 600,
    enabled: bool = True,
    on_hung: Callable[[str, int], None] | None = None,
    check_interval: float | None = None,
    event_bus: "WorkflowEventBus | None" = None,
) -> AsyncHeartbeatService:
    """Get or create the global async heartbeat service instance.

    Args:
        timeout_seconds: Seconds of inactivity before triggering hung detection.
        enabled: Whether heartbeat monitoring is enabled.
        on_hung: Callback when hung process detected.
        check_interval: How often to check for inactivity (from config).
        event_bus: Optional event bus for emitting PROCESS_HUNG events.

    Returns:
        The global AsyncHeartbeatService instance.
    """
    global _async_heartbeat_service
    if _async_heartbeat_service is None:
        _async_heartbeat_service = AsyncHeartbeatService(
            timeout_seconds=timeout_seconds,
            enabled=enabled,
            on_hung=on_hung,
            check_interval=check_interval,
            event_bus=event_bus,
        )
    return _async_heartbeat_service


def reset_heartbeat_service() -> None:
    """Reset the global heartbeat service (for testing)."""
    global _heartbeat_service
    if _heartbeat_service:
        _heartbeat_service.reset()
    _heartbeat_service = None


async def reset_async_heartbeat_service() -> None:
    """Reset the global async heartbeat service (for testing)."""
    global _async_heartbeat_service
    if _async_heartbeat_service:
        await _async_heartbeat_service.reset()
    _async_heartbeat_service = None
