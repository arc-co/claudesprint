"""Rich terminal UI for ClaudeSprint workflow visualization.

Provides a clean terminal-native display with:
- Progress bar for sprint completion
- Live step status with animated spinner
- Rolling log for context (non-repetitive)
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.progress import Progress, BarColumn, TextColumn
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

from claudesprint.models.current_issue import IssueStep


class StepStatus(StrEnum):
    """Status of a workflow step."""

    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    SKIPPED = "skipped"
    FAILED = "failed"


class LiveSubprocessDisplay:
    """A renderable that recalculates elapsed time on each render.

    This is needed because Rich's Live widget caches the rendered output.
    By implementing __rich__, we force recalculation on each refresh.
    """

    def __init__(self, dashboard: "WorkflowDashboard") -> None:
        self._dashboard = dashboard

    def __rich__(self) -> RenderableType:
        """Called by Rich on each render - recalculates elapsed time."""
        return self._dashboard._build_subprocess_display_inner()


@dataclass
class SubprocessInfo:
    """Information about a running subprocess."""

    pid: int | None = None
    command: str = ""
    start_time: float = 0.0
    output_lines: int = 0
    last_output: str = ""


@dataclass
class SprintIssue:
    """Information about an issue in the sprint."""

    id: str
    title: str
    status: str  # "pending", "in_progress", "completed", "blocked"


@dataclass
class DashboardState:
    """Centralized mutable state for the dashboard."""

    # Sprint info
    spec_id: str = ""
    total_issues: int = 0
    completed_issues: int = 0

    # Sprint issues for board display
    issues: list[SprintIssue] = field(default_factory=list)

    # Current issue
    issue_id: str = ""
    issue_title: str = ""

    # Step statuses
    step_statuses: dict[IssueStep, StepStatus] = field(default_factory=dict)

    # Current execution state
    current_step: IssueStep | None = None
    current_model: str = ""
    retry_count: int = 0
    status_message: str = ""

    # Phase
    phase: str = "planning"  # "planning" or "executing"

    # Subprocess tracking
    subprocess: SubprocessInfo = field(default_factory=SubprocessInfo)

    # Rolling log buffer
    log_lines: list[str] = field(default_factory=list)

    # Track last logged step to avoid repetition
    last_logged_step: str = ""


class WorkflowDashboard:
    """Terminal-native workflow visualization.

    Usage:
        dashboard = WorkflowDashboard()
        dashboard.set_sprint_info("SPEC_01", 10, 3)
        with dashboard:
            # Run workflow
            dashboard.on_step_start(IssueStep.IMPLEMENT, "opus")
            ...
    """

    MAX_LOG_LINES = 8

    def __init__(self) -> None:
        """Initialize the dashboard."""
        self.state = DashboardState()
        self._console = Console()
        self._live: Live | None = None
        self._progress = Progress(
            TextColumn("[bold magenta]{task.description}"),
            BarColumn(bar_width=30, complete_style="green", finished_style="green"),
            TextColumn("[bold][{task.completed}/{task.total}][/bold]"),
            TextColumn("[dim]{task.fields[status]}"),
            console=self._console,
            expand=False,
        )
        self._task_id: Any = None

        # Initialize step statuses
        self._reset_step_statuses()

    def _reset_step_statuses(self) -> None:
        """Reset all step statuses to pending."""
        self.state.step_statuses = dict.fromkeys(
            IssueStep.ordered_steps(), StepStatus.PENDING
        )

    def set_sprint_info(
        self,
        spec_id: str,
        total_issues: int,
        completed_issues: int,
    ) -> None:
        """Update sprint information.

        Args:
            spec_id: Spec ID (e.g., "SPEC_01")
            total_issues: Total number of issues in the sprint
            completed_issues: Number of completed issues
        """
        self.state.spec_id = spec_id
        self.state.total_issues = total_issues
        self.state.completed_issues = completed_issues
        self._update_progress_bar()
        self._refresh()

    def set_issues(self, issues: list[tuple[str, str, str]]) -> None:
        """Set the list of issues for the sprint board.

        Args:
            issues: List of (id, title, status) tuples
        """
        self.state.issues = [
            SprintIssue(id=id, title=title, status=status)
            for id, title, status in issues
        ]
        self._refresh()

    def _update_progress_bar(self) -> None:
        """Update the progress bar task."""
        if self._task_id is not None:
            self._progress.update(
                self._task_id,
                completed=self.state.completed_issues,
                total=self.state.total_issues,
                status=self._get_progress_status(),
            )

    def _get_progress_status(self) -> str:
        """Get the status text for the progress bar."""
        if self.state.issue_id:
            return f"→ {self.state.issue_id}"
        return "selecting..."

    def set_issue(self, issue_id: str, issue_title: str) -> None:
        """Set the current issue being worked on.

        Args:
            issue_id: Issue ID
            issue_title: Issue title
        """
        self.state.issue_id = issue_id
        self.state.issue_title = issue_title
        self.state.phase = "executing"
        self._reset_step_statuses()
        self.state.retry_count = 0
        self.state.last_logged_step = ""
        # Clear activity log for new issue
        self.state.log_lines = []
        self._update_progress_bar()
        self._refresh()

    def clear_issue(self) -> None:
        """Clear the current issue (e.g., when completed)."""
        self.state.issue_id = ""
        self.state.issue_title = ""
        self.state.phase = "planning"
        self.state.current_step = None
        self.state.current_model = ""
        self.state.retry_count = 0
        self.state.status_message = ""
        self.state.last_logged_step = ""
        self._reset_step_statuses()
        self._update_progress_bar()
        self._refresh()

    def increment_completed(self) -> None:
        """Increment the completed issues count."""
        self.state.completed_issues += 1
        self._update_progress_bar()
        self._refresh()

    def on_step_start(self, step: IssueStep, model: str) -> None:
        """Handle step start event.

        Args:
            step: The step that is starting
            model: The model being used (e.g., "opus", "sonnet")
        """
        self.state.current_step = step
        self.state.current_model = model
        self.state.step_statuses[step] = StepStatus.RUNNING
        self.state.status_message = step.value
        self._refresh()

    def on_step_complete(self, step: IssueStep, next_step: IssueStep | None) -> None:
        """Handle step completion event.

        Args:
            step: The step that completed
            next_step: The next step (None if workflow complete)
        """
        self.state.step_statuses[step] = StepStatus.DONE
        self.state.retry_count = 0
        # Only log if different from last logged (avoid repetition)
        step_key = f"done:{step.value}"
        if self.state.last_logged_step != step_key:
            self._add_context_log(f"    [green]✓[/] {step.value}")
            self.state.last_logged_step = step_key
        self.state.status_message = next_step.value if next_step else ""
        self._refresh()

    def on_step_skip(self, step: IssueStep, next_step: IssueStep | None) -> None:
        """Handle step skip event.

        Args:
            step: The step that was skipped
            next_step: The next step (None if workflow complete)
        """
        self.state.step_statuses[step] = StepStatus.SKIPPED
        # Log skips with skip symbol
        step_key = f"skip:{step.value}"
        if self.state.last_logged_step != step_key:
            self._add_context_log(f"    [yellow]⏭[/] {step.value}")
            self.state.last_logged_step = step_key
        self.state.status_message = next_step.value if next_step else ""
        self._refresh()

    def on_step_failure(self, step: IssueStep, retry_count: int) -> None:
        """Handle step failure event.

        Args:
            step: The step that failed
            retry_count: Current retry count
        """
        self.state.step_statuses[step] = StepStatus.FAILED
        self.state.retry_count = retry_count
        self._add_context_log(f"    [red]✗[/] {step.value} [dim](retry {retry_count})[/]")
        self.state.status_message = f"{step.value} (retry {retry_count})"
        self._refresh()

    def on_subprocess_start(self, pid: int, command: str = "claude") -> None:
        """Handle subprocess start event.

        Args:
            pid: Process ID of the subprocess
            command: Command being run (default: "claude")
        """
        import time
        self.state.subprocess = SubprocessInfo(
            pid=pid,
            command=command,
            start_time=time.time(),
            output_lines=0,
            last_output="",
        )
        self._refresh()

    def on_subprocess_output(self, line: str) -> None:
        """Handle subprocess output line.

        Args:
            line: Output line from subprocess
        """
        self.state.subprocess.output_lines += 1
        # Keep last meaningful output (skip empty lines)
        stripped = line.strip()
        if stripped and not stripped.startswith("─"):
            # Truncate long lines for display
            self.state.subprocess.last_output = stripped[:60] + ("..." if len(stripped) > 60 else "")
        self._refresh()

    def on_subprocess_end(self) -> None:
        """Handle subprocess completion."""
        self.state.subprocess = SubprocessInfo()
        self._refresh()

    def _add_context_log(self, line: str) -> None:
        """Add a contextual log line (internal use).

        Args:
            line: Log line to add
        """
        self.state.log_lines.append(line)
        if len(self.state.log_lines) > self.MAX_LOG_LINES:
            self.state.log_lines = self.state.log_lines[-self.MAX_LOG_LINES:]

    def add_log_line(self, line: str) -> None:
        """Add a line to the rolling log buffer.

        Args:
            line: Log line to add
        """
        # Split on newlines and add each line
        for log_line in line.rstrip().split("\n"):
            if log_line.strip():
                self._add_context_log(log_line)
        self._refresh()

    def _format_elapsed(self, seconds: float) -> str:
        """Format elapsed time in a human-readable way.

        Args:
            seconds: Elapsed time in seconds

        Returns:
            Formatted string like "5s", "1m 23s", etc.
        """
        if seconds < 10:
            # Show one decimal for small values to appear more responsive
            return f"{seconds:.1f}s"
        if seconds < 60:
            return f"{int(seconds)}s"
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"

    def _build_active_step_display(self) -> RenderableType:
        """Build the current step indicator with spinner.

        Returns:
            Renderable showing current step or idle state
        """
        if not self.state.current_step:
            return Text("    waiting for next step...", style="dim italic")

        step = self.state.current_step
        status = self.state.step_statuses.get(step, StepStatus.PENDING)

        if status == StepStatus.RUNNING:
            model = self.state.current_model
            model_style = "bold magenta" if model == "opus" else "cyan"

            # Use a grid table to align spinner and text side-by-side
            grid = Table.grid(padding=(0, 1))
            grid.add_row(
                Text("   "),
                Spinner("dots", style="cyan"),
                Text.assemble(
                    (step.value, "bold white"),
                    ("   ", ""),
                    ("model: ", "dim"),
                    (model, model_style),
                ),
            )
            return grid
        elif status == StepStatus.FAILED:
            return Text(f"    ✗ {step.value} (retry {self.state.retry_count})", style="red")
        else:
            return Text(f"    {step.value}", style="dim")

    def _build_subprocess_display(self) -> RenderableType:
        """Build the subprocess status display.

        Returns a LiveSubprocessDisplay which recalculates elapsed time
        on each Rich render, ensuring the timer stays updated.
        """
        if not self.state.subprocess.pid:
            return Text("")
        return LiveSubprocessDisplay(self)

    def _build_subprocess_display_inner(self) -> RenderableType:
        """Build the actual subprocess status display content.

        Called by LiveSubprocessDisplay on each render.

        Returns:
            Renderable showing subprocess info or empty text
        """
        import time

        sub = self.state.subprocess
        if not sub.pid:
            return Text("")

        elapsed = time.time() - sub.start_time
        elapsed_str = self._format_elapsed(elapsed)

        # Extract process name from command (first word)
        process_name = sub.command.split()[0] if sub.command else "claude"

        elements: list[RenderableType] = []

        # Build subprocess info line with arc
        grid = Table.grid(padding=(0, 1))
        grid.add_row(
            Text("    ╰", style="dim"),
            Spinner("dots2", style="dim cyan"),
            Text.assemble(
                (process_name, "cyan"),
                (" ", ""),
                (f"pid:{sub.pid}", "dim"),
                ("  ", ""),
                (elapsed_str, ""),
            ),
        )
        elements.append(grid)

        # Show last output if available
        if sub.last_output:
            elements.append(
                Text(f"        {sub.last_output}", style="dim italic")
            )

        return Group(*elements)

    def _build_step_summary(self) -> Text:
        """Build a compact summary of completed/skipped steps.

        Returns:
            Text showing step completion status
        """
        done = sum(1 for s in self.state.step_statuses.values() if s == StepStatus.DONE)
        skipped = sum(1 for s in self.state.step_statuses.values() if s == StepStatus.SKIPPED)

        parts = []
        if done:
            step_word = "step" if done == 1 else "steps"
            parts.append(f"[green]✓[/] {done} {step_word} done")
        if skipped:
            parts.append(f"[yellow]⏭[/] {skipped} skipped")

        summary = "  ·  ".join(parts)
        return Text.from_markup(f"  [dim]{summary}[/]") if parts else Text("")

    def _build_log_display(self) -> RenderableType:
        """Build the rolling log display.

        Returns:
            Renderable showing recent log lines
        """
        if not self.state.log_lines:
            return Text("")

        lines = []
        for line in self.state.log_lines[-self.MAX_LOG_LINES:]:
            lines.append(Text.from_markup(line))

        return Group(*lines)

    def _build_box_header(self, title: str, description: str) -> RenderableType:
        """Build a boxed section header with description.

        Args:
            title: Section title
            description: Brief description of the section

        Returns:
            Formatted boxed header
        """
        width = 50
        title_line = f"┤ {title} ├"
        padding = width - len(title_line) - 2
        left_pad = padding // 2
        right_pad = padding - left_pad

        lines = [
            Text.from_markup(f"[dim]┌{'─' * left_pad}{title_line}{'─' * right_pad}┐[/]"),
            Text.from_markup(f"[dim]│[/] [italic dim]{description[:width-4]:<{width-4}}[/] [dim]│[/]"),
            Text.from_markup(f"[dim]└{'─' * (width - 2)}┘[/]"),
        ]
        return Group(*lines)

    def _build_sprint_board(self) -> RenderableType:
        """Build a visual task board showing issues with status.

        Returns:
            Renderable showing issues with checkboxes
        """
        if not self.state.issues:
            return Text("  No issues loaded", style="dim")

        lines: list[RenderableType] = []
        max_display = 8  # Show at most 8 issues to avoid clutter

        # Find current issue index
        current_idx = -1
        for i, issue in enumerate(self.state.issues):
            if issue.id == self.state.issue_id:
                current_idx = i
                break

        # Determine which issues to show (window around current)
        total = len(self.state.issues)
        if total <= max_display:
            start_idx = 0
            end_idx = total
        else:
            # Center window around current issue
            half = max_display // 2
            start_idx = max(0, current_idx - half)
            end_idx = min(total, start_idx + max_display)
            if end_idx - start_idx < max_display:
                start_idx = max(0, end_idx - max_display)

        # Show "..." if there are issues before
        if start_idx > 0:
            lines.append(Text(f"  [dim]··· {start_idx} more above[/]"))

        # Build issue list
        for i in range(start_idx, end_idx):
            issue = self.state.issues[i]

            # Determine icon and style based on status
            if issue.status == "completed":
                icon = "☑"
                icon_style = "green"
                text_style = "dim"
            elif issue.status == "in_progress":
                icon = "▶"
                icon_style = "bold cyan"
                text_style = "bold"
            elif issue.status == "blocked":
                icon = "⊘"
                icon_style = "red"
                text_style = "dim"
            else:  # pending
                icon = "☐"
                icon_style = "dim"
                text_style = "dim"

            # Truncate title
            max_title_len = 35
            title = issue.title[:max_title_len] + ("..." if len(issue.title) > max_title_len else "")

            line = Text("  ")
            line.append(icon, style=icon_style)
            line.append(" ", style="")
            line.append(f"{issue.id}", style=text_style)
            line.append("  ", style="")
            line.append(title, style=text_style if issue.status != "in_progress" else "")

            lines.append(line)

        # Show "..." if there are issues after
        if end_idx < total:
            lines.append(Text.from_markup(f"  [dim]··· {total - end_idx} more below[/]"))

        return Group(*lines)

    def _build_layout(self) -> RenderableType:
        """Build the complete display layout.

        Returns:
            Renderable for the terminal display
        """
        elements: list[RenderableType] = []

        # 1. Simple header
        elements.append(Text.from_markup("[bold]ClaudeSprint[/]"))
        elements.append(Text(""))

        # 2. Sprint progress board
        sprint_desc = f"Sprint: {self.state.spec_id or '...'} → Issue: {self.state.issue_id or 'selecting'}"
        elements.append(self._build_box_header("Sprint", sprint_desc))
        elements.append(self._build_sprint_board())

        # 3. Issue Activity (combines execution status + activity log)
        elements.append(Text(""))

        # Build activity description with current step
        if self.state.current_step:
            step_name = self.state.current_step.value
            activity_desc = f"{self.state.issue_id or 'issue'}  ·  step: {step_name}"
        else:
            activity_desc = f"{self.state.issue_id or 'issue'}  ·  idle"

        elements.append(self._build_box_header("Issue Activity", activity_desc))

        # Execution section
        elements.append(Text.from_markup("  [dim]Execution:[/]"))
        elements.append(self._build_active_step_display())

        # Subprocess info (when Claude is running)
        subprocess_display = self._build_subprocess_display()
        if self.state.subprocess.pid:
            elements.append(subprocess_display)

        # Step summary (compact)
        summary = self._build_step_summary()
        if summary.plain:
            elements.append(summary)

        # Log section
        if self.state.log_lines:
            elements.append(Text(""))
            elements.append(Text.from_markup("  [dim]Task Progress Log:[/]"))
            elements.append(self._build_log_display())

        return Group(*elements)

    def _refresh(self) -> None:
        """Refresh the display if live mode is active."""
        if self._live:
            self._live.update(self._build_layout())

    def __enter__(self) -> "WorkflowDashboard":
        """Enter context manager - start live display."""
        # Initialize progress bar task (don't call self._progress.start() since
        # we're embedding Progress in our own Live layout)
        self._task_id = self._progress.add_task(
            f"[bold]{self.state.spec_id or 'Sprint'}[/]",
            total=self.state.total_issues or 1,
            completed=self.state.completed_issues,
            status=self._get_progress_status(),
        )

        self._live = Live(
            self._build_layout(),
            console=self._console,
            refresh_per_second=4,
            transient=False,
        )
        self._live.__enter__()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager - stop live display."""
        if self._live:
            self._live.__exit__(exc_type, exc_val, exc_tb)
            self._live = None
        # Note: don't call self._progress.stop() since we never started it
        # (Progress is embedded in our Live layout which handles rendering)

    def print_static(self) -> None:
        """Print a static version of the dashboard (for non-live mode)."""
        self._console.print(self._build_layout())
