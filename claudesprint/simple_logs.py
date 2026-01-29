"""Simple line-by-line log output for sprint execution.

This module provides a SimpleLogsOutput class that prints each event as it happens
with timestamps, providing a scrollable history of the entire execution.
"""

import time
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from rich.console import Console

if TYPE_CHECKING:
    from claudesprint.core.issue_engine import IssueStep


class LogVerbosity(StrEnum):
    """Verbosity levels for log output."""

    QUIET = "quiet"  # Errors/warnings only
    NORMAL = "normal"  # Default: key events
    VERBOSE = "verbose"  # All events + routing signals + iterations
    DEBUG = "debug"  # Everything + internal state


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

    def __init__(
        self,
        console: Console | None = None,
        verbosity: LogVerbosity = LogVerbosity.NORMAL,
    ) -> None:
        """Initialize the simple logs output.

        Args:
            console: Rich console for output. If None, creates a new one.
            verbosity: Log verbosity level controlling output detail.
        """
        self.console = console or Console()
        self.verbosity = verbosity
        self.current_issue: str | None = None
        self.current_step: str | None = None
        self.step_start_time: float | None = None
        self.sprint_total: int = 0
        self.sprint_completed: int = 0
        # Track iteration state for warnings
        self.issue_iterations: int = 0
        self.max_iterations: int = 50
        self.retry_count: int = 0
        self.max_retry: int = 5

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

    def _log_if(self, level: LogVerbosity, message: str, indent: int = 0) -> None:
        """Log only if verbosity >= level.

        Args:
            level: Minimum verbosity level required for this message.
            message: The message to print (can contain Rich markup).
            indent: Number of indent levels (each level is 2 spaces).
        """
        levels = {
            LogVerbosity.QUIET: 0,
            LogVerbosity.NORMAL: 1,
            LogVerbosity.VERBOSE: 2,
            LogVerbosity.DEBUG: 3,
        }
        if levels[self.verbosity] >= levels[level]:
            self._log(message, indent)

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

    def on_sprint_entered(self, spec_id: str, total: int, completed: int) -> None:
        """Log entering sprint loop with visual marker.

        Args:
            spec_id: The sprint spec ID.
            total: Total number of issues in the sprint.
            completed: Number of already completed issues.
        """
        self.sprint_total = total
        self.sprint_completed = completed
        self._log("")
        self._log("[bold blue]" + "=" * 50 + "[/bold blue]")
        self._log("[bold blue]>>> ENTERING SPRINT LOOP[/bold blue]")
        self._log(f"[bold blue]    Sprint: {spec_id}[/bold blue]")
        self._log(f"[bold blue]    Issues: {completed}/{total} complete[/bold blue]")
        self._log("[bold blue]" + "=" * 50 + "[/bold blue]")

    def on_sprint_exited(self, spec_id: str, total: int, completed: int) -> None:
        """Log exiting sprint loop with visual marker.

        Args:
            spec_id: The sprint spec ID.
            total: Total number of issues in the sprint.
            completed: Number of completed issues.
        """
        self._log("")
        self._log("[bold green]" + "=" * 50 + "[/bold green]")
        self._log("[bold green]<<< EXITING SPRINT LOOP[/bold green]")
        self._log(f"[bold green]    Sprint: {spec_id}[/bold green]")
        self._log(f"[bold green]    Completed: {completed}/{total} issues[/bold green]")
        self._log("[bold green]" + "=" * 50 + "[/bold green]")

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

    def on_issue_entered(self, issue_id: str, title: str) -> None:
        """Log entering issue loop with visual marker.

        Args:
            issue_id: The issue ID.
            title: The issue title.
        """
        self._log("")
        self._log("[bold cyan]" + "-" * 40 + "[/bold cyan]")
        self._log("[bold cyan]  >> ENTERING ISSUE LOOP[/bold cyan]")
        self._log(f"[bold cyan]     Issue: {issue_id}[/bold cyan]")
        self._log(f"[bold cyan]     Title: {title}[/bold cyan]")
        self._log("[bold cyan]" + "-" * 40 + "[/bold cyan]")

    def on_issue_exited(self, issue_id: str, exit_reason: str) -> None:
        """Log exiting issue loop with visual marker.

        Args:
            issue_id: The issue ID.
            exit_reason: The reason for exiting (e.g., "completed", "failed").
        """
        color = "green" if exit_reason == "completed" else "yellow"
        self._log("")
        self._log(f"[bold {color}]" + "-" * 40 + f"[/bold {color}]")
        self._log(f"[bold {color}]  << EXITING ISSUE LOOP[/bold {color}]")
        self._log(f"[bold {color}]     Issue: {issue_id}[/bold {color}]")
        self._log(f"[bold {color}]     Reason: {exit_reason}[/bold {color}]")
        self._log(f"[bold {color}]" + "-" * 40 + f"[/bold {color}]")

    def set_issue(self, issue_id: str, title: str) -> None:
        """Log starting work on an issue.

        Args:
            issue_id: The issue ID.
            title: The issue title.
        """
        self.current_issue = issue_id
        self._log(f"[cyan]ISSUE[/cyan] {issue_id} | {title}", indent=1)

    def on_issue_complete(self, issue_id: str) -> None:
        """Log issue completion.

        Args:
            issue_id: The completed issue ID.
        """
        self.sprint_completed += 1
        self._log(
            f"[green]ISSUE[/green] {issue_id} | "
            f"Complete ({self.sprint_completed}/{self.sprint_total})",
            indent=1,
        )

    def clear_issue(self) -> None:
        """Clear current issue tracking."""
        self.current_issue = None

    # Step events

    def on_issue_iteration(
        self,
        total_iterations: int,
        max_iterations: int,
        retry_count: int,
        max_retry: int,
    ) -> None:
        """Log iteration with early warnings at 70% threshold.

        Args:
            total_iterations: Current iteration count.
            max_iterations: Maximum allowed iterations.
            retry_count: Current retry count for the step.
            max_retry: Maximum allowed retries.
        """
        self.issue_iterations = total_iterations
        self.max_iterations = max_iterations
        self.retry_count = retry_count
        self.max_retry = max_retry

        # Always log in VERBOSE mode
        self._log_if(
            LogVerbosity.VERBOSE,
            f"[dim]ITER[/dim] {total_iterations}/{max_iterations} | retry {retry_count}/{max_retry}",
        )

        # Warn at 70% of limits (always visible)
        iter_pct = total_iterations / max_iterations if max_iterations > 0 else 0
        if 0.7 <= iter_pct < 1.0:
            self._log(
                f"[yellow]WARNING[/yellow] Approaching iteration limit: "
                f"{total_iterations}/{max_iterations} ({iter_pct:.0%})"
            )

        retry_pct = retry_count / max_retry if max_retry > 0 else 0
        if 0.6 <= retry_pct < 1.0:
            self._log(f"[yellow]WARNING[/yellow] High retry count: {retry_count}/{max_retry}")

    def on_routing_signal(
        self,
        step: "IssueStep",
        signal: str | None,
        next_step: "IssueStep | None",
    ) -> None:
        """Log routing decision (VERBOSE mode).

        Args:
            step: The current step.
            signal: The matched routing signal, or None for default.
            next_step: The next step to transition to.
        """
        next_name = next_step.value if next_step else "COMPLETE"
        if signal:
            self._log_if(
                LogVerbosity.VERBOSE,
                f"[dim]ROUTE[/dim] {step.value} --[cyan]{signal}[/cyan]--> {next_name}",
            )
        else:
            self._log_if(
                LogVerbosity.DEBUG,
                f"[dim]ROUTE[/dim] {step.value} --[dim]default[/dim]--> {next_name}",
            )

    def on_step_start(self, step: "IssueStep", model: str) -> None:
        """Log step start.

        Args:
            step: The step being started.
            model: The model being used for this step.
        """
        self.current_step = step.value
        self.step_start_time = time.time()

        iter_info = ""
        if self.verbosity in (LogVerbosity.VERBOSE, LogVerbosity.DEBUG) and self.issue_iterations > 0:
            iter_info = f" [dim](iter {self.issue_iterations}/{self.max_iterations})[/dim]"

        self._log(f"[yellow]STEP[/yellow] {step.value} | Starting... (model: {model}){iter_info}", indent=2)

    def on_step_complete(self, step: "IssueStep", next_step: "IssueStep | None") -> None:
        """Log step completion.

        Args:
            step: The completed step.
            next_step: The next step to execute, or None if done.
        """
        elapsed = self._format_elapsed(self.step_start_time)
        self._log(f"[green]STEP[/green] {step.value} | Complete ({elapsed})", indent=2)
        self.step_start_time = None
        self.current_step = None

    def on_step_skip(self, step: "IssueStep", next_step: "IssueStep | None") -> None:
        """Log step skip.

        Args:
            step: The skipped step.
            next_step: The next step to execute, or None if done.
        """
        self._log(f"[dim]STEP[/dim] {step.value} | Skipped", indent=2)

    def on_step_failure(self, step: "IssueStep", retry_count: int, max_retry: int = 5) -> None:
        """Log step failure.

        Args:
            step: The failed step.
            retry_count: Number of retries attempted.
            max_retry: Maximum retry limit for context.
        """
        color = "red" if retry_count >= max_retry * 0.6 else "yellow"
        self._log(f"[{color}]STEP[/{color}] {step.value} | Failed (retry {retry_count}/{max_retry})", indent=2)

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
        # Print agent output with indent (3 levels - under step)
        # Strip any trailing whitespace but preserve content
        line = line.rstrip()
        if line:
            self._log(f"[dim]>[/dim] {line}", indent=3)

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
