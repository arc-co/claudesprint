"""Heartbeat service for detecting hung processes."""

import logging
import threading
import time
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
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
    ) -> None:
        """Initialize the heartbeat service.

        Args:
            timeout_seconds: Seconds of inactivity before triggering hung detection.
            enabled: Whether heartbeat monitoring is enabled.
            on_hung: Callback when hung process detected (step_name, seconds_inactive).
            check_interval: How often to check for inactivity (from config).
        """
        self._timeout_seconds = timeout_seconds
        self._enabled = enabled
        self._on_hung = on_hung
        self._check_interval = check_interval if check_interval is not None else self.DEFAULT_CHECK_INTERVAL

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
                if elapsed >= self._timeout_seconds and not self._hung_notified:
                    step = self._current_step
                    self._hung_notified = True

            # Call callback outside of lock
            if elapsed >= self._timeout_seconds and self._on_hung:
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


# Global instance
_heartbeat_service: HeartbeatService | None = None


def get_heartbeat_service(
    timeout_seconds: int = 600,
    enabled: bool = True,
    on_hung: Callable[[str, int], None] | None = None,
    check_interval: float | None = None,
) -> HeartbeatService:
    """Get or create the global heartbeat service instance.

    Args:
        timeout_seconds: Seconds of inactivity before triggering hung detection.
        enabled: Whether heartbeat monitoring is enabled.
        on_hung: Callback when hung process detected.
        check_interval: How often to check for inactivity (from config).

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
        )
    return _heartbeat_service


def reset_heartbeat_service() -> None:
    """Reset the global heartbeat service (for testing)."""
    global _heartbeat_service
    if _heartbeat_service:
        _heartbeat_service.reset()
    _heartbeat_service = None
