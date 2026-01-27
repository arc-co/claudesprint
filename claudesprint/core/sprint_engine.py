"""Sprint engine - outer loop orchestration for sprint-based workflows.

The SprintEngine manages the outer loop:
1. Load sprint from sprint.json
2. Create/switch to sprint branch
3. Loop: Select issue -> Run issue engine -> Mark complete
4. Create PR when all issues complete
"""

import time
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Callable

import re

from claudesprint.core.claude_runner import ClaudeRunner, ClaudeResult
from claudesprint.core.issue_engine import IssueEngine, IssueResult, IssueExitReason
from claudesprint.models.config import ClaudesprintConfig
from claudesprint.models.current_issue import CurrentIssue, ChunkType, IssueStep
from claudesprint.models.sprint import Sprint, Issue, IssueStatus, ResolvedConfig
from claudesprint.services.git_service import GitService
from claudesprint.services.issue_service import IssueService
from claudesprint.services.sprint_service import SprintService
from claudesprint.services.notification_service import NotificationService
from claudesprint.utils.duration import format_duration
from claudesprint.utils.lock import LockFile


class SprintExitReason(StrEnum):
    """Reasons for sprint loop exit."""

    COMPLETED = "completed"
    MAX_ITERATIONS = "max_iterations"
    TOTAL_TIMEOUT = "total_timeout"
    MAX_RETRY = "max_retry"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"
    USER_INTERRUPT = "user_interrupt"
    NO_ISSUES = "no_issues"


@dataclass
class SprintResult:
    """Result of a sprint run."""

    exit_reason: SprintExitReason
    issues_completed: int
    iterations: int
    elapsed_seconds: int
    message: str
    pr_url: str | None = None
    error: str | None = None


@dataclass
class IssueSelectionResult:
    """Result of agent-driven issue selection."""

    success: bool
    issue_id: str | None
    issue_title: str | None
    rationale: str
    error: str | None = None


class SprintEngine:
    """Sprint-level orchestration engine (outer loop).

    Manages the sprint lifecycle:
    - Loads sprint from sprint.json
    - Creates/switches to sprint branch
    - Agent-driven issue selection
    - Runs IssueEngine for each selected issue
    - Creates PR when sprint is complete
    """

    def __init__(
        self,
        project_root: str | Path,
        sprint_path: str | Path,
        config: ClaudesprintConfig | None = None,
    ) -> None:
        """Initialize SprintEngine.

        Args:
            project_root: Root directory of the project
            sprint_path: Path to the sprint.json file
            config: Optional ClaudesprintConfig (uses defaults if not provided)
        """
        self.project_root = Path(project_root)
        self.sprint_path = Path(sprint_path)
        self.config = config or ClaudesprintConfig.from_project_root(str(project_root))

        # Initialize services
        self.git_service = GitService(project_root)
        self.sprint_service = SprintService(self.sprint_path.parent.parent)  # sprints dir
        self.issue_service = IssueService(self.config.project_dir)
        self.notification_service = NotificationService(self.config.notifications_file)
        self.claude_runner = ClaudeRunner(
            project_root,
            self.config.claude_timeout,
            common_prompt_file=self.config.common_prompt_file,
            conversation_log_file=(
                self.config.conversation_log_file if self.config.debug_conversations else None
            ),
        )

        # Rate limit tracking
        self._rate_limit_retries = 0

        # Callbacks
        self.on_issue_start: Callable[[Issue], None] | None = None
        self.on_issue_complete: Callable[[Issue], None] | None = None
        self.on_output: Callable[[str], None] | None = None
        self.on_sprint_complete: Callable[[SprintResult], None] | None = None
        self.issue_engine_configurator: Callable[[IssueEngine], None] | None = None

    def preflight_check(self) -> tuple[bool, list[str]]:
        """Run pre-flight checks before starting sprint.

        Returns:
            Tuple of (success, list of error messages)
        """
        errors = []

        # Check sprint.json exists and is valid
        if not self.sprint_service.is_sprint_valid(self.sprint_path):
            errors.append(f"Invalid or missing sprint.json at {self.sprint_path}")

        # Load and validate sprint
        if not errors:
            sprint = self.sprint_service.read_sprint(self.sprint_path)
            if not sprint:
                errors.append("Failed to parse sprint.json")
            elif not sprint.issues:
                errors.append("Sprint has no issues")

        return len(errors) == 0, errors

    def _setup_sprint_branch(self, sprint: Sprint) -> tuple[bool, str]:
        """Set up the sprint branch.

        Args:
            sprint: Sprint model

        Returns:
            Tuple of (success, message)
        """
        if not self.git_service.is_repo():
            return True, "Not a git repository, skipping branch setup"

        branch_name = sprint.git_branch or f"sprint/{sprint.spec_id}"

        # Check if we're already on the sprint branch
        current_branch = self.git_service.get_current_branch()
        if current_branch == branch_name:
            return True, f"Already on branch {branch_name}"

        # Create or checkout the branch
        success, message = self.git_service.create_branch(branch_name, checkout=True)
        if success:
            # Update sprint with branch name
            sprint.git_branch = branch_name
            self.sprint_service.write_sprint(sprint, self.sprint_path)
            return True, f"Switched to branch {branch_name}"

        return False, f"Failed to create/checkout branch: {message}"

    def _get_in_progress_issue(self, sprint: Sprint) -> Issue | None:
        """Get an issue that is already in_progress.

        If there's a current_issue.json with an issue_id that matches an
        in_progress issue, prefer that one. Otherwise return the first
        in_progress issue found.

        Args:
            sprint: Sprint model

        Returns:
            In_progress issue to resume, or None if none found
        """
        # First check if current_issue.json points to an in_progress issue
        existing_current_issue = self.issue_service.read_current_issue()
        if existing_current_issue and existing_current_issue.issue_id:
            issue = sprint.get_issue(existing_current_issue.issue_id)
            if issue and issue.status == IssueStatus.IN_PROGRESS:
                return issue

        # Fallback to first in_progress issue
        for issue in sprint.issues:
            if issue.status == IssueStatus.IN_PROGRESS:
                return issue
        return None

    def _resume_in_progress_issue(
        self,
        issue: Issue,
        current_issue: CurrentIssue | None,
    ) -> IssueSelectionResult:
        """Resume an in_progress issue.

        Args:
            issue: The in_progress issue to resume
            current_issue: Existing current_issue context if any

        Returns:
            IssueSelectionResult for the resumed issue
        """
        rationale = f"Resuming in_progress issue from previous session"
        self.issue_service.log_issue_selection(issue.id, issue.title, rationale)
        return IssueSelectionResult(
            success=True,
            issue_id=issue.id,
            issue_title=issue.title,
            rationale=rationale,
        )

    def select_issue(self, sprint: Sprint) -> IssueSelectionResult:
        """Select next issue using agent-driven selection.

        This runs PROMPT_select-issue.md to have the agent choose
        the next issue based on priority, dependencies, and context.

        If there's already an in_progress issue (from a previous interrupted
        session), that issue is resumed directly without running selection.

        Args:
            sprint: Sprint model

        Returns:
            IssueSelectionResult with selected issue or error
        """
        # First check for existing in_progress issue to resume
        in_progress_issue = self._get_in_progress_issue(sprint)
        if in_progress_issue:
            current_issue = self.issue_service.read_current_issue()
            return self._resume_in_progress_issue(in_progress_issue, current_issue)

        # Get available issues
        available = self.sprint_service.get_available_issues(sprint)
        if not available:
            return IssueSelectionResult(
                success=False,
                issue_id=None,
                issue_title=None,
                rationale="No available issues",
                error="All issues are completed, blocked, or in progress",
            )

        # If only one issue available, select it directly (optimization)
        if len(available) == 1:
            issue = available[0]
            rationale = "Only one available issue"
            self.issue_service.log_issue_selection(
                issue.id, issue.title, rationale
            )
            return IssueSelectionResult(
                success=True,
                issue_id=issue.id,
                issue_title=issue.title,
                rationale=rationale,
            )

        # Multiple issues - use agent-driven selection
        result = self._run_agent_selection(sprint, available)

        # Fallback to priority-based if agent fails
        if not result.success:
            return self._fallback_priority_selection(available, result.error)

        return result

    def _run_agent_selection(
        self,
        sprint: Sprint,
        available: list[Issue],
    ) -> IssueSelectionResult:
        """Run agent-driven issue selection using PROMPT_select-issue.md.

        Args:
            sprint: Sprint model
            available: List of available issues

        Returns:
            IssueSelectionResult with selected issue or error
        """
        # Prepare current_issue.json for the agent with sprint context
        current_issue = CurrentIssue.create_initial(str(self.sprint_path))
        current_issue.step = IssueStep.SELECT_ISSUE
        current_issue.goal = "Select next issue from sprint"
        current_issue.next_action = "Review sprint and select next issue to work on"
        if not self.issue_service.write_current_issue(current_issue):
            return IssueSelectionResult(
                success=False,
                issue_id=None,
                issue_title=None,
                rationale="",
                error="Failed to write current_issue.json for issue selection",
            )

        # Get prompt file for selection
        prompt_file = self.config.get_prompt_file("select-issue")
        if not Path(prompt_file).exists():
            return IssueSelectionResult(
                success=False,
                issue_id=None,
                issue_title=None,
                rationale="",
                error=f"Prompt file not found: {prompt_file}",
            )

        # Run Claude with the selection prompt
        if self.on_output:
            self.on_output("\n=== Running agent-driven issue selection ===\n")

        result: ClaudeResult = self.claude_runner.run_prompt(
            prompt_file,
            on_output=self.on_output,
        )

        # Handle rate limiting
        if result.rate_limited:
            return IssueSelectionResult(
                success=False,
                issue_id=None,
                issue_title=None,
                rationale="",
                error="Rate limited during issue selection",
            )

        # Handle crash
        if result.crashed:
            return IssueSelectionResult(
                success=False,
                issue_id=None,
                issue_title=None,
                rationale="",
                error=f"Claude crashed during selection: {result.error_type}",
            )

        # Parse the result
        return self._parse_selection_result(result.output, sprint)

    def _parse_selection_result(
        self,
        output: str,
        sprint: Sprint,
    ) -> IssueSelectionResult:
        """Parse agent selection output to get selected issue.

        The agent may:
        1. Write to current_issue.json with issue_id set
        2. Output "ID: <issue-id>" in the text
        3. Output "SPRINT_COMPLETE" if no more work
        4. Output "BLOCKED" if all issues are blocked

        Args:
            output: Claude output text
            sprint: Sprint model

        Returns:
            IssueSelectionResult with selected issue
        """
        import re

        # Check for SPRINT_COMPLETE signal
        if "SPRINT_COMPLETE" in output:
            return IssueSelectionResult(
                success=False,
                issue_id=None,
                issue_title=None,
                rationale="Sprint complete - all issues done",
                error=None,
            )

        # Check for BLOCKED signal
        if "BLOCKED" in output and "circular" in output.lower():
            return IssueSelectionResult(
                success=False,
                issue_id=None,
                issue_title=None,
                rationale="Blocked by circular dependencies",
                error="Circular dependency detected",
            )

        # Check current_issue.json first (Claude may have written it)
        updated_issue = self.issue_service.read_current_issue()
        if updated_issue and updated_issue.issue_id:
            issue = sprint.get_issue(updated_issue.issue_id)
            if issue:
                rationale = (
                    updated_issue.rationale[0]
                    if updated_issue.rationale
                    else "Agent selected"
                )
                self.issue_service.log_issue_selection(
                    issue.id, issue.title, rationale
                )
                return IssueSelectionResult(
                    success=True,
                    issue_id=issue.id,
                    issue_title=issue.title,
                    rationale=rationale,
                )

        # Fallback: parse "ID: <issue-id>" from output
        id_match = re.search(r"ID:\s*([a-z0-9-]+)", output, re.IGNORECASE)
        if id_match:
            issue_id = id_match.group(1)
            issue = sprint.get_issue(issue_id)
            if issue:
                # Try to extract rationale from output
                rationale_match = re.search(
                    r"Selection Rationale:\s*(.+?)(?:\n\n|\nNext step:|$)",
                    output,
                    re.DOTALL | re.IGNORECASE,
                )
                rationale = (
                    rationale_match.group(1).strip()
                    if rationale_match
                    else "Agent selected from output"
                )
                self.issue_service.log_issue_selection(
                    issue.id, issue.title, rationale
                )
                return IssueSelectionResult(
                    success=True,
                    issue_id=issue.id,
                    issue_title=issue.title,
                    rationale=rationale,
                )

        # Could not parse selection
        return IssueSelectionResult(
            success=False,
            issue_id=None,
            issue_title=None,
            rationale="",
            error="Could not parse issue selection from agent output",
        )

    def _fallback_priority_selection(
        self,
        available: list[Issue],
        error: str | None,
    ) -> IssueSelectionResult:
        """Fallback to priority-based selection when agent fails.

        Args:
            available: List of available issues
            error: Error message from agent selection

        Returns:
            IssueSelectionResult with selected issue
        """
        if self.on_output:
            self.on_output(
                f"\nAgent selection failed ({error}), using priority-based fallback\n"
            )

        priority_order = ["critical", "high", "medium", "low"]
        for priority in priority_order:
            for issue in available:
                if issue.priority == priority:
                    rationale = f"Fallback: Highest priority available ({priority})"
                    self.issue_service.log_issue_selection(
                        issue.id, issue.title, rationale
                    )
                    return IssueSelectionResult(
                        success=True,
                        issue_id=issue.id,
                        issue_title=issue.title,
                        rationale=rationale,
                    )

        # Fallback to first available
        issue = available[0]
        rationale = "Fallback: First available issue"
        self.issue_service.log_issue_selection(issue.id, issue.title, rationale)
        return IssueSelectionResult(
            success=True,
            issue_id=issue.id,
            issue_title=issue.title,
            rationale=rationale,
        )

    def get_bearings(self, sprint: Sprint) -> str:
        """Generate sprint status summary for logging between issue cycles.

        This provides context about the sprint progress at the start
        of each issue selection cycle.

        Args:
            sprint: Sprint model

        Returns:
            Formatted status summary string
        """
        stats = sprint.get_stats()
        available = self.sprint_service.get_available_issues(sprint)

        lines = [
            "",
            "=" * 50,
            "GET BEARINGS - Sprint Status Summary",
            "=" * 50,
            f"Spec: {sprint.spec_id}",
            f"Branch: {sprint.git_branch or 'N/A'}",
            "",
            "Issue Stats:",
            f"  Total:       {stats['total']}",
            f"  Completed:   {stats['completed']}",
            f"  In Progress: {stats['in_progress']}",
            f"  Pending:     {stats['pending']}",
            f"  Blocked:     {stats['blocked']}",
            "",
            f"Available to work on: {len(available)}",
        ]

        if available:
            lines.append("")
            lines.append("Available issues:")
            for issue in available[:5]:  # Show first 5
                lines.append(f"  - [{issue.priority}] {issue.id}: {issue.title}")
            if len(available) > 5:
                lines.append(f"  ... and {len(available) - 5} more")

        lines.extend(["", "=" * 50, ""])

        summary = "\n".join(lines)

        # Log to current_issue.log
        self.issue_service.append_log(f"GET BEARINGS\n{summary}")

        return summary

    def _resolve_issue_config(self, sprint: Sprint, issue: Issue) -> ResolvedConfig:
        """Resolve execution configuration for a specific issue.

        Merges issue-specific overrides with sprint-level defaults.

        Args:
            sprint: Sprint model with default configuration
            issue: Issue that may have overrides

        Returns:
            ResolvedConfig with all fields resolved to concrete values
        """
        return ResolvedConfig.from_sprint_and_issue(sprint.config, issue.config)

    def _create_current_issue(
        self,
        issue: Issue,
        sprint: Sprint,
    ) -> CurrentIssue:
        """Create CurrentIssue context for the selected issue.

        Args:
            issue: Selected issue
            sprint: Sprint model

        Returns:
            CurrentIssue model
        """
        current_issue = CurrentIssue.create_initial(str(self.sprint_path))
        current_issue.issue_id = issue.id
        current_issue.issue_title = issue.title
        current_issue.chunk_type = ChunkType.IMPLEMENT
        current_issue.step = IssueStep.READ_DOCS
        current_issue.goal = f"Implement: {issue.title}"
        current_issue.next_action = f"Read documentation and understand requirements for: {issue.title}"

        # Store acceptance criteria in context
        current_issue.context["acceptance_criteria"] = "\n".join(
            f"- {ac}" for ac in issue.acceptance_criteria
        )

        return current_issue

    def _mark_issue_complete(
        self,
        issue_id: str,
        session_id: str | None = None,
    ) -> bool:
        """Mark an issue as completed in the sprint.

        Args:
            issue_id: Issue ID to mark complete
            session_id: Optional session ID for history

        Returns:
            True if successful
        """
        success = self.sprint_service.mark_issue_status(
            self.sprint_path,
            issue_id,
            IssueStatus.COMPLETED,
            session_id=session_id,
        )

        if success:
            # Log completion
            sprint = self.sprint_service.read_sprint(self.sprint_path)
            if sprint:
                issue = sprint.get_issue(issue_id)
                if issue:
                    self.issue_service.log_issue_completion(issue.id, issue.title)

        return success

    def _calculate_rate_limit_backoff(self) -> int:
        """Calculate exponential backoff wait time for rate limiting.

        Uses exponential backoff: base * 2^(retries-1), capped at max_wait.

        Returns:
            Wait time in seconds
        """
        base = self.config.rate_limit_base_wait
        max_wait = self.config.rate_limit_max_wait

        # Exponential backoff: base * 2^(retries-1)
        # First retry: base, second: base*2, third: base*4, etc.
        exponent = max(0, self._rate_limit_retries - 1)
        wait = base * (2 ** exponent)

        # Cap at max_wait
        return min(wait, max_wait)

    def _get_pr_instructions(self, sprint: Sprint) -> str:
        """Get instructions for manually creating a PR.

        Args:
            sprint: Sprint model

        Returns:
            Instructions string for the user
        """
        if not self.git_service.is_repo():
            return ""

        branch = self.git_service.get_current_branch()
        completed_issues = [i for i in sprint.issues if i.status == IssueStatus.COMPLETED]

        lines = [
            "",
            "=" * 60,
            "SPRINT COMPLETE - Manual PR submission required",
            "=" * 60,
            "",
            f"Branch: {branch}",
            f"Spec: {sprint.spec_id}",
            "",
            "Completed issues:",
        ]
        for issue in completed_issues:
            lines.append(f"  - {issue.id}: {issue.title}")

        lines.extend([
            "",
            "Next steps:",
            f"  1. Push your branch:  git push -u origin {branch}",
            "  2. Create a PR on your Git hosting platform",
            "  3. Request review and merge",
            "",
            "=" * 60,
        ])

        return "\n".join(lines)

    def run(
        self,
        max_iterations: int = 0,
    ) -> SprintResult:
        """Run the sprint loop.

        Args:
            max_iterations: Maximum iterations (0 = unlimited)

        Returns:
            SprintResult with final outcome
        """
        start_time = time.time()
        iteration = 0
        issues_completed = 0

        # Acquire lock
        lock = LockFile(self.config.lock_file)
        success, error = lock.acquire()
        if not success:
            return SprintResult(
                exit_reason=SprintExitReason.ERROR,
                issues_completed=0,
                iterations=0,
                elapsed_seconds=0,
                message="Failed to acquire lock",
                error=error,
            )

        try:
            # Pre-flight checks
            valid, errors = self.preflight_check()
            if not valid:
                return SprintResult(
                    exit_reason=SprintExitReason.ERROR,
                    issues_completed=0,
                    iterations=0,
                    elapsed_seconds=0,
                    message="Pre-flight checks failed",
                    error="; ".join(errors),
                )

            # Load sprint
            sprint = self.sprint_service.read_sprint(self.sprint_path)
            if not sprint:
                return SprintResult(
                    exit_reason=SprintExitReason.ERROR,
                    issues_completed=0,
                    iterations=0,
                    elapsed_seconds=0,
                    message="Failed to load sprint",
                    error="Could not parse sprint.json",
                )

            # Setup sprint branch
            branch_success, branch_msg = self._setup_sprint_branch(sprint)
            if not branch_success:
                return SprintResult(
                    exit_reason=SprintExitReason.ERROR,
                    issues_completed=0,
                    iterations=0,
                    elapsed_seconds=0,
                    message="Failed to setup sprint branch",
                    error=branch_msg,
                )

            # Main sprint loop
            while True:
                iteration += 1

                # Check iteration limit
                if max_iterations > 0 and iteration > max_iterations:
                    elapsed = int(time.time() - start_time)
                    self.notification_service.notify_exit(
                        f"Max iterations ({max_iterations}) reached"
                    )
                    return SprintResult(
                        exit_reason=SprintExitReason.MAX_ITERATIONS,
                        issues_completed=issues_completed,
                        iterations=iteration - 1,
                        elapsed_seconds=elapsed,
                        message=f"Max iterations ({max_iterations}) reached",
                    )

                # Reload sprint to get current state
                sprint = self.sprint_service.read_sprint(self.sprint_path)
                if not sprint:
                    return SprintResult(
                        exit_reason=SprintExitReason.ERROR,
                        issues_completed=issues_completed,
                        iterations=iteration - 1,
                        elapsed_seconds=int(time.time() - start_time),
                        message="Failed to reload sprint",
                        error="Could not parse sprint.json",
                    )

                # Get bearings - output sprint status between issue cycles
                bearings = self.get_bearings(sprint)
                if self.on_output:
                    self.on_output(bearings)

                # Check if sprint is complete
                if sprint.is_complete():
                    elapsed = int(time.time() - start_time)

                    # Get PR instructions for manual submission
                    pr_instructions = self._get_pr_instructions(sprint)

                    self.notification_service.notify_exit(
                        f"Sprint complete: {issues_completed} issues in {format_duration(elapsed)}"
                    )

                    result = SprintResult(
                        exit_reason=SprintExitReason.COMPLETED,
                        issues_completed=issues_completed,
                        iterations=iteration,
                        elapsed_seconds=elapsed,
                        message=pr_instructions if pr_instructions else f"All {len(sprint.issues)} issues completed",
                        pr_url=None,
                    )

                    if self.on_sprint_complete:
                        self.on_sprint_complete(result)

                    return result

                # Select next issue
                selection = self.select_issue(sprint)
                if not selection.success:
                    elapsed = int(time.time() - start_time)
                    return SprintResult(
                        exit_reason=SprintExitReason.NO_ISSUES,
                        issues_completed=issues_completed,
                        iterations=iteration,
                        elapsed_seconds=elapsed,
                        message="No issues available to work on",
                        error=selection.error,
                    )

                # Get the selected issue
                issue = sprint.get_issue(selection.issue_id)
                if not issue:
                    return SprintResult(
                        exit_reason=SprintExitReason.ERROR,
                        issues_completed=issues_completed,
                        iterations=iteration,
                        elapsed_seconds=int(time.time() - start_time),
                        message="Selected issue not found",
                        error=f"Issue {selection.issue_id} not found in sprint",
                    )

                # Check if this is a resumed in_progress issue
                is_resuming = issue.status == IssueStatus.IN_PROGRESS
                existing_current_issue = self.issue_service.read_current_issue()
                has_valid_context = (
                    existing_current_issue
                    and existing_current_issue.issue_id == issue.id
                )

                if is_resuming and has_valid_context:
                    # Resuming: use existing current_issue context
                    current_issue = existing_current_issue
                    if self.on_output:
                        self.on_output(
                            f"\nResuming issue {issue.id} at step: {current_issue.step.value}\n"
                        )
                else:
                    # New issue or no valid context: mark in_progress and create fresh context
                    if not is_resuming:
                        self.sprint_service.mark_issue_status(
                            self.sprint_path,
                            issue.id,
                            IssueStatus.IN_PROGRESS,
                        )

                    # Create current_issue context
                    current_issue = self._create_current_issue(issue, sprint)
                    if not self.issue_service.write_current_issue(current_issue):
                        return SprintResult(
                            exit_reason=SprintExitReason.ERROR,
                            issues_completed=issues_completed,
                            iterations=iteration,
                            elapsed_seconds=int(time.time() - start_time),
                            message="Failed to write current_issue.json",
                            error="Failed to write current_issue.json after issue selection",
                        )

                    # Log step transition
                    self.issue_service.log_step_transition(
                        "select-issue",
                        current_issue.step.value,
                        f"Selected: {issue.id}",
                    )

                # Callback: issue start
                if self.on_issue_start:
                    self.on_issue_start(issue)

                # Notify issue selection
                self.notification_service.notify_step(
                    f"Selected issue: {issue.id} - {issue.title}"
                )

                # Resolve execution configuration for this issue
                resolved_config = self._resolve_issue_config(sprint, issue)

                # Create and run issue engine
                issue_engine = IssueEngine(
                    self.project_root,
                    self.config,
                    resolved_config,
                )
                issue_engine.on_output = self.on_output

                # Allow external configuration of the issue engine (e.g., for dashboard callbacks)
                if self.issue_engine_configurator:
                    self.issue_engine_configurator(issue_engine)

                issue_result = issue_engine.run(current_issue)

                # Handle issue result
                match issue_result.exit_reason:
                    case IssueExitReason.COMPLETED:
                        # Mark issue complete in sprint
                        self._mark_issue_complete(issue.id)
                        issues_completed += 1

                        # Clear current_issue artifacts
                        self.issue_service.clear_current_issue()

                        # Callback: issue complete
                        if self.on_issue_complete:
                            self.on_issue_complete(issue)

                    case IssueExitReason.RATE_LIMITED:
                        # Handle rate limiting with backoff
                        self._rate_limit_retries += 1

                        if self._rate_limit_retries > self.config.rate_limit_retries:
                            elapsed = int(time.time() - start_time)
                            self.notification_service.notify_rate_limit(
                                f"Max rate limit retries ({self.config.rate_limit_retries}) exceeded"
                            )
                            return SprintResult(
                                exit_reason=SprintExitReason.RATE_LIMITED,
                                issues_completed=issues_completed,
                                iterations=iteration,
                                elapsed_seconds=elapsed,
                                message="Rate limit retries exceeded",
                                error="Claude API rate limited",
                            )

                        # Calculate backoff and wait
                        backoff = self._calculate_rate_limit_backoff()
                        self.notification_service.notify_rate_limit(
                            f"Rate limited, waiting {backoff}s (retry {self._rate_limit_retries})"
                        )
                        if self.on_output:
                            self.on_output(f"\nRate limited, waiting {backoff} seconds...\n")
                        time.sleep(backoff)
                        # Don't increment iteration, retry same issue
                        iteration -= 1

                    case IssueExitReason.MAX_RETRY:
                        elapsed = int(time.time() - start_time)
                        self.notification_service.notify_failure(
                            f"Max retry limit reached on {issue.id}"
                        )
                        return SprintResult(
                            exit_reason=SprintExitReason.MAX_RETRY,
                            issues_completed=issues_completed,
                            iterations=iteration,
                            elapsed_seconds=elapsed,
                            message=f"Max retry limit reached on issue {issue.id}",
                            error=issue_result.error,
                        )

                    case IssueExitReason.CRASHED | IssueExitReason.ERROR:
                        elapsed = int(time.time() - start_time)
                        self.notification_service.notify_failure(
                            f"Issue {issue.id} failed: {issue_result.message}"
                        )
                        return SprintResult(
                            exit_reason=SprintExitReason.ERROR,
                            issues_completed=issues_completed,
                            iterations=iteration,
                            elapsed_seconds=elapsed,
                            message=issue_result.message,
                            error=issue_result.error,
                        )

                    case IssueExitReason.BLOCKED:
                        # Mark issue as blocked and continue to next
                        self.sprint_service.mark_issue_status(
                            self.sprint_path,
                            issue.id,
                            IssueStatus.BLOCKED,
                        )
                        if self.on_output:
                            self.on_output(f"\nIssue {issue.id} is blocked, moving to next\n")

                # Reset rate limit counter on successful completion
                if issue_result.exit_reason == IssueExitReason.COMPLETED:
                    self._rate_limit_retries = 0

                # Small delay between issues
                time.sleep(2)

        finally:
            lock.release()

    def get_sprint_status(self) -> dict:
        """Get current sprint status.

        Returns:
            Dict with sprint status information
        """
        sprint = self.sprint_service.read_sprint(self.sprint_path)
        if not sprint:
            return {"error": "Sprint not found"}

        stats = sprint.get_stats()
        current_issue = self.issue_service.read_current_issue()

        return {
            "spec_id": sprint.spec_id,
            "spec_file": sprint.spec_file,
            "description": sprint.description,
            "git_branch": sprint.git_branch,
            "is_complete": sprint.is_complete(),
            "stats": stats,
            "current_issue": {
                "id": current_issue.issue_id if current_issue else None,
                "step": current_issue.step.value if current_issue else None,
            } if current_issue else None,
            "available_issues": [
                {"id": i.id, "title": i.title, "priority": i.priority}
                for i in sprint.get_available_issues()
            ],
        }
