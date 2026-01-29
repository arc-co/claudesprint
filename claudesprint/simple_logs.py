"""Simple line-by-line log output for sprint execution.

This module provides a SimpleLogsOutput class that prints each event as it happens
with timestamps, providing a scrollable history of the entire execution.
"""

import time
from datetime import datetime
from typing import TYPE_CHECKING

from rich.console import Console

if TYPE_CHECKING:
    from claudesprint.core.issue_engine import IssueStep


class SimpleLogsOutput:
    """Simple line-by-line log output for sprint execution.

    Prints each event as it happens with timestamps, providing a scrollable
    history of the entire execution.

    Example output:
        [14:23:01] SPRINT SPEC_01 | 3/7 issues complete
        [14:23:01] ISSUE feat-002 | Fix authentication bug
        [14:23:02] STEP read-docs | Starting... (model: opus)
        [14:23:15] STEP read-docs | Complete (13s)
        [14:23:15] STEP implement | Starting... (model: opus)
        [14:23:16]   > Reading src/auth.py...
        [14:25:30] STEP implement | Complete (2m 15s)
    """

    def __init__(self, console: Console | None = None) -> None:
        """Initialize the simple logs output.

        Args:
            console: Rich console for output. If None, creates a new one.
        """
        self.console = console or Console()
        self.current_issue: str | None = None
        self.current_step: str | None = None
        self.step_start_time: float | None = None
        self.sprint_total: int = 0
        self.sprint_completed: int = 0

    def _timestamp(self) -> str:
        """Get current timestamp in HH:MM:SS format."""
        return datetime.now().strftime("%H:%M:%S")

    def _log(self, message: str, indent: int = 0) -> None:
        """Print a log line with timestamp.

        Args:
            message: The message to print (can contain Rich markup).
            indent: Number of indent levels (each level is 2 spaces).
        """
        prefix = "  " * indent
        self.console.print(f"[dim][{self._timestamp()}][/dim] {prefix}{message}")

    def _format_elapsed(self, start_time: float | None) -> str:
        """Format elapsed time since start_time.

        Args:
            start_time: Start time from time.time(), or None.

        Returns:
            Formatted elapsed time string (e.g., "13s" or "2m 15s").
        """
        if start_time is None:
            return "?"
        elapsed = time.time() - start_time
        if elapsed < 60:
            return f"{elapsed:.0f}s"
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        return f"{minutes}m {seconds}s"

    # Sprint events

    def set_sprint_info(self, spec_id: str, total: int, completed: int) -> None:
        """Log sprint info at start of execution.

        Args:
            spec_id: The sprint spec ID.
            total: Total number of issues in the sprint.
            completed: Number of already completed issues.
        """
        self.sprint_total = total
        self.sprint_completed = completed
        self._log(f"[bold]SPRINT[/bold] {spec_id} | {completed}/{total} issues complete")

    def on_sprint_iteration(self, iteration: int, available_issues: int) -> None:
        """Log a new sprint iteration.

        Args:
            iteration: The iteration number (1-based).
            available_issues: Number of issues available to work on.
        """
        self._log(
            f"[bold]ITERATION[/bold] {iteration} | "
            f"{available_issues} issues available, "
            f"{self.sprint_completed}/{self.sprint_total} complete"
        )

    def on_selecting_issue(self) -> None:
        """Log that issue selection is starting."""
        self._log("[dim]Selecting next issue...[/dim]")

    # Issue events

    def set_issue(self, issue_id: str, title: str) -> None:
        """Log starting work on an issue.

        Args:
            issue_id: The issue ID.
            title: The issue title.
        """
        self.current_issue = issue_id
        self._log(f"[cyan]ISSUE[/cyan] {issue_id} | {title}")

    def on_issue_complete(self, issue_id: str) -> None:
        """Log issue completion.

        Args:
            issue_id: The completed issue ID.
        """
        self.sprint_completed += 1
        self._log(
            f"[green]ISSUE[/green] {issue_id} | "
            f"Complete ({self.sprint_completed}/{self.sprint_total})"
        )

    def clear_issue(self) -> None:
        """Clear current issue tracking."""
        self.current_issue = None

    # Step events

    def on_step_start(self, step: "IssueStep", model: str) -> None:
        """Log step start.

        Args:
            step: The step being started.
            model: The model being used for this step.
        """
        self.current_step = step.value
        self.step_start_time = time.time()
        self._log(f"[yellow]STEP[/yellow] {step.value} | Starting... (model: {model})")

    def on_step_complete(self, step: "IssueStep", next_step: "IssueStep | None") -> None:
        """Log step completion.

        Args:
            step: The completed step.
            next_step: The next step to execute, or None if done.
        """
        elapsed = self._format_elapsed(self.step_start_time)
        self._log(f"[green]STEP[/green] {step.value} | Complete ({elapsed})")
        self.step_start_time = None
        self.current_step = None

    def on_step_skip(self, step: "IssueStep", next_step: "IssueStep | None") -> None:
        """Log step skip.

        Args:
            step: The skipped step.
            next_step: The next step to execute, or None if done.
        """
        self._log(f"[dim]STEP[/dim] {step.value} | Skipped")

    def on_step_failure(self, step: "IssueStep", retry_count: int) -> None:
        """Log step failure.

        Args:
            step: The failed step.
            retry_count: Number of retries attempted.
        """
        self._log(f"[red]STEP[/red] {step.value} | Failed (retry {retry_count})")

    # Subprocess/agent output

    def on_subprocess_start(self, pid: int, command: str) -> None:
        """Log subprocess start (no-op for simple logs).

        Args:
            pid: Process ID.
            command: Command being run.
        """
        # Don't need to log subprocess start for simple logs
        pass

    def on_subprocess_output(self, line: str) -> None:
        """Log subprocess output line.

        Args:
            line: Output line from the subprocess.
        """
        # Print agent output with indent
        # Strip any trailing whitespace but preserve content
        line = line.rstrip()
        if line:
            self._log(f"[dim]>[/dim] {line}", indent=1)

    def on_subprocess_end(self) -> None:
        """Log subprocess end (no-op for simple logs)."""
        # Don't need to log subprocess end for simple logs
        pass

    # General output

    def on_output(self, text: str) -> None:
        """Log general output from the sprint engine.

        Args:
            text: Output text to log.
        """
        # Split multi-line output and log each line
        for line in text.strip().split("\n"):
            if line.strip():
                self._log(f"[dim]{line}[/dim]")

    def add_log_line(self, line: str) -> None:
        """Add a log line.

        Args:
            line: Log line to add.
        """
        self._log(line)

    # Issue board (compatibility methods - no-op for simple logs)

    def set_issues(self, issues: list[tuple[str, str, str]]) -> None:
        """Set issues board (no-op for simple logs).

        Args:
            issues: List of (id, title, status) tuples.
        """
        pass

    def increment_completed(self) -> None:
        """Increment completed count (tracked via on_issue_complete)."""
        # This is handled by on_issue_complete for simple logs
        pass

    # Context manager (no-op for simple logger)

    def __enter__(self) -> "SimpleLogsOutput":
        """Enter context manager."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Exit context manager."""
        pass
