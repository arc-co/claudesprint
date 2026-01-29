"""Issue service for current issue session operations."""

import json
from datetime import datetime, UTC
from pathlib import Path

from claudesprint.models.current_issue import CurrentIssue


class IssueService:
    """Service for CurrentIssue file I/O and session management."""

    def __init__(self, project_dir: str | Path) -> None:
        """Initialize IssueService.

        Args:
            project_dir: Project directory (e.g., .claudesprint/project)
        """
        self.project_dir = Path(project_dir)
        self.current_issue_file = self.project_dir / "current_issue.json"
        self.current_issue_log = self.project_dir / "current_issue.log"

    def read_current_issue(self) -> CurrentIssue | None:
        """Read and parse current_issue.json.

        Returns:
            CurrentIssue model or None if not found/invalid
        """
        if not self.current_issue_file.exists():
            return None
        try:
            data = json.loads(self.current_issue_file.read_text())
            return CurrentIssue.model_validate(data)
        except (json.JSONDecodeError, Exception):
            return None

    def write_current_issue(self, issue: CurrentIssue) -> bool:
        """Write current_issue.json atomically.

        Args:
            issue: CurrentIssue model to write

        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure parent directory exists
            self.project_dir.mkdir(parents=True, exist_ok=True)

            # Update timestamp
            issue.update_timestamp()

            # Write to temp file first
            temp_file = self.project_dir / "current_issue.tmp.json"
            content = issue.model_dump_json(indent=2, by_alias=True)
            temp_file.write_text(content)

            # Atomic rename
            temp_file.rename(self.current_issue_file)
            return True
        except Exception:
            return False

    def is_current_issue_valid(self) -> bool:
        """Check if current_issue.json exists and is valid JSON.

        Returns:
            True if valid, False otherwise
        """
        if not self.current_issue_file.exists():
            return False
        try:
            data = json.loads(self.current_issue_file.read_text())
            # Basic structure check
            return (
                isinstance(data, dict)
                and "sprint_path" in data
                and "step" in data
            )
        except (json.JSONDecodeError, Exception):
            return False

    def clear_current_issue(self) -> bool:
        """Delete current_issue files (main, backup, log).

        Returns:
            True if successful, False otherwise
        """
        try:
            if self.current_issue_file.exists():
                self.current_issue_file.unlink()
            if self.current_issue_log.exists():
                self.current_issue_log.unlink()
            return True
        except Exception:
            return False

    def create_initial(self, sprint_path: str) -> CurrentIssue:
        """Create an initial CurrentIssue for a sprint.

        Args:
            sprint_path: Path to the sprint.json file

        Returns:
            Initial CurrentIssue model
        """
        return CurrentIssue.create_initial(sprint_path)

    def reset_current_issue(self, sprint_path: str) -> bool:
        """Reset current_issue.json to initial state for a sprint.

        Args:
            sprint_path: Path to the sprint.json file

        Returns:
            True if successful, False otherwise
        """
        current_issue = self.create_initial(sprint_path)
        return self.write_current_issue(current_issue)

    # Log operations

    def append_log(self, entry: str) -> bool:
        """Append an entry to current_issue.log.

        Args:
            entry: Log entry text

        Returns:
            True if successful, False otherwise
        """
        try:
            self.project_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            log_line = f"[{timestamp}] {entry}\n"
            with open(self.current_issue_log, "a") as f:
                f.write(log_line)
            return True
        except Exception:
            return False

    def read_log(self) -> list[str]:
        """Read all entries from current_issue.log.

        Returns:
            List of log entries
        """
        if not self.current_issue_log.exists():
            return []
        try:
            content = self.current_issue_log.read_text()
            return [line for line in content.splitlines() if line.strip()]
        except Exception:
            return []

    def read_log_tail(self, num_lines: int = 20) -> str:
        """Read the last N lines from current_issue.log.

        This is useful for injecting recent activity context into agent prompts
        without overwhelming token usage.

        Args:
            num_lines: Number of lines to return (default 20)

        Returns:
            String containing the last N log lines, or empty string if no log
        """
        lines = self.read_log()
        if not lines:
            return ""
        tail_lines = lines[-num_lines:]
        return "\n".join(tail_lines)

    def read_full_log(self) -> str:
        """Read the full current_issue.log content.

        This provides complete session history for context continuity between
        agent invocations. The full log is important for understanding the
        complete workflow progression.

        Returns:
            String containing all log lines, or empty string if no log
        """
        lines = self.read_log()
        if not lines:
            return ""
        return "\n".join(lines)

    def clear_log(self) -> bool:
        """Clear current_issue.log.

        Returns:
            True if successful, False otherwise
        """
        try:
            if self.current_issue_log.exists():
                self.current_issue_log.unlink()
            return True
        except Exception:
            return False

    def log_issue_selection(
        self,
        issue_id: str,
        issue_title: str,
        rationale: str,
    ) -> bool:
        """Log issue selection with rationale.

        Args:
            issue_id: Selected issue ID
            issue_title: Selected issue title
            rationale: Selection rationale

        Returns:
            True if successful, False otherwise
        """
        entry = f"SELECTED: {issue_id} - {issue_title}\n  Rationale: {rationale}"
        return self.append_log(entry)

    def log_step_transition(
        self,
        from_step: str,
        to_step: str,
        reason: str = "",
    ) -> bool:
        """Log step transition.

        Args:
            from_step: Previous step
            to_step: New step
            reason: Optional reason for transition

        Returns:
            True if successful, False otherwise
        """
        entry = f"STEP: {from_step} -> {to_step}"
        if reason:
            entry += f" ({reason})"
        return self.append_log(entry)

    def log_issue_completion(
        self,
        issue_id: str,
        issue_title: str,
    ) -> bool:
        """Log issue completion.

        Args:
            issue_id: Completed issue ID
            issue_title: Completed issue title

        Returns:
            True if successful, False otherwise
        """
        entry = f"COMPLETED: {issue_id} - {issue_title}"
        return self.append_log(entry)

    def has_active_issue(self) -> bool:
        """Check if there is an active issue being worked on.

        Returns:
            True if there is an active issue with issue_id set
        """
        current_issue = self.read_current_issue()
        if not current_issue:
            return False
        return bool(current_issue.issue_id)
