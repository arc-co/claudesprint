"""Dashboard state aggregation."""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class DashboardState:
    """Aggregated state for the dashboard UI.

    Tracks sprint progress, current issue, workflow step, and output buffer.
    """

    # Sprint info
    sprint_id: str = ""
    total_issues: int = 0
    completed_issues: int = 0
    current_iteration: int = 0

    # Issue info
    current_issue_id: str = ""
    current_issue_name: str = ""
    current_step: str = ""
    step_start_time: datetime | None = None

    # Metrics
    retry_count: int = 0
    max_retry: int = 5
    total_iterations: int = 0
    max_iterations: int = 50

    # Subprocess info
    subprocess_pid: int | None = None
    subprocess_command: str = ""

    # Connection tracking
    connected_clients: int = 0

    # Output buffer (ring buffer to prevent memory issues)
    output_buffer: deque[str] = field(default_factory=lambda: deque(maxlen=500))

    def to_dict(self) -> dict[str, Any]:
        """Serialize state to JSON-compatible dictionary."""
        return {
            "sprint_id": self.sprint_id,
            "total_issues": self.total_issues,
            "completed_issues": self.completed_issues,
            "current_iteration": self.current_iteration,
            "current_issue_id": self.current_issue_id,
            "current_issue_name": self.current_issue_name,
            "current_step": self.current_step,
            "step_start_time": self.step_start_time.isoformat() if self.step_start_time else None,
            "step_elapsed_seconds": self._get_step_elapsed(),
            "retry_count": self.retry_count,
            "max_retry": self.max_retry,
            "total_iterations": self.total_iterations,
            "max_iterations": self.max_iterations,
            "subprocess_pid": self.subprocess_pid,
            "subprocess_command": self.subprocess_command,
            "connected_clients": self.connected_clients,
            "output_lines": list(self.output_buffer),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _get_step_elapsed(self) -> float | None:
        """Get elapsed seconds for current step."""
        if self.step_start_time is None:
            return None
        delta = datetime.now(timezone.utc) - self.step_start_time
        return delta.total_seconds()

    def add_output(self, line: str) -> None:
        """Add a line to the output buffer."""
        self.output_buffer.append(line)

    def clear_output(self) -> None:
        """Clear the output buffer."""
        self.output_buffer.clear()
