"""Dashboard state management."""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class DashboardState:
    """Observable state for the NiceGUI dashboard.

    All state updates trigger UI refreshes via NiceGUI's reactivity.
    """

    # Sprint info
    sprint_id: str = ""
    total_issues: int = 0
    completed_issues: int = 0

    # Current issue
    current_issue_id: str = ""
    current_issue_name: str = ""
    current_step: str = ""
    step_start_time: datetime | None = None

    # Retry tracking
    retry_count: int = 0
    max_retry: int = 5

    # Output buffer (ring buffer)
    output_lines: deque[str] = field(default_factory=lambda: deque(maxlen=500))

    # Task board: issues indexed by ID
    issues: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def step_elapsed(self) -> str:
        """Calculate elapsed time for current step."""
        if self.step_start_time is None:
            return "-"
        delta = datetime.now(timezone.utc) - self.step_start_time
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return f"{seconds}s"
        mins = seconds // 60
        secs = seconds % 60
        return f"{mins}m{secs}s"

    def add_output(self, line: str) -> None:
        """Add a line to the output buffer."""
        self.output_lines.append(line)

    def clear_output(self) -> None:
        """Clear the output buffer."""
        self.output_lines.clear()

    def set_issues(self, issues: list[dict[str, Any]]) -> None:
        """Load issues from sprint data."""
        self.issues.clear()
        for issue in issues:
            issue_id = issue.get("id", "")
            self.issues[issue_id] = {
                "id": issue_id,
                "title": issue.get("title", ""),
                "status": issue.get("status", "pending"),
                "priority": issue.get("priority", "medium"),
                "category": issue.get("category"),
            }

    def update_issue_status(self, issue_id: str, status: str) -> None:
        """Update the status of a specific issue."""
        if issue_id in self.issues:
            self.issues[issue_id]["status"] = status
