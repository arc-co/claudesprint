"""Sprint engine - outer loop orchestration for sprint-based workflows.

The SprintEngine manages the outer loop:
1. Load sprint from sprint.json
2. Create/switch to sprint branch
3. Loop: Select issue -> Run issue engine -> Mark complete
4. Create PR when all issues complete
"""

import logging
import time
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Callable

import re

logger = logging.getLogger(__name__)

from claudesprint.core.claude_runner import ClaudeRunner, ClaudeResult
from claudesprint.core.issue_engine import IssueEngine, IssueResult, IssueExitReason
from claudesprint.core.issue_state_machine import IssueStateMachine, SprintAction
from claudesprint.core.iteration_tracker import IterationTracker, FailureCategory
from claudesprint.core.rate_limit_handler import RateLimitConfig, RateLimitHandler
from claudesprint.events.workflow_event_bus import (
    WorkflowEventBus,
    WorkflowEvent,
    SprintIterationPayload,
    SelectingIssuePayload,
    OutputPayload,
)
from claudesprint.exceptions import RateLimitExceeded, StateCorruptionError
from claudesprint.models.config import ClaudesprintConfig
from claudesprint.models.current_issue import CurrentIssue, ChunkType, IssueStep
from claudesprint.models.sprint import Sprint, Issue, IssueStatus, ResolvedConfig
from claudesprint.services.git_service import GitService
from claudesprint.services.issue_service import IssueService
from claudesprint.services.sprint_service import SprintService
from claudesprint.services.notification_service import NotificationService
from claudesprint.services.prompt_service import PromptService, PromptContext
from claudesprint.services.state_manager import StateManager
from claudesprint.utils.duration import format_duration
from claudesprint.utils.lock import LockFile


# Type alias for the IssueEngine factory
IssueEngineFactory = Callable[[ResolvedConfig], IssueEngine]


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
        sprint_path: Path,
        config: ClaudesprintConfig,
        # Injected Services
        git_service: GitService,
        sprint_service: SprintService,
        issue_service: IssueService,
        notification_service: NotificationService,
        prompt_service: PromptService,
        claude_runner: ClaudeRunner,
        # Injected Factory
        issue_engine_factory: IssueEngineFactory,
        # Optional integrations
        event_bus: WorkflowEventBus | None = None,
        state_manager: StateManager | None = None,
    ) -> None:
        """Initialize SprintEngine.

        Args:
            sprint_path: Path to the sprint.json file
            config: ClaudesprintConfig for the project
            git_service: Injected GitService instance
            sprint_service: Injected SprintService instance
            issue_service: Injected IssueService instance
            notification_service: Injected NotificationService instance
            prompt_service: Injected PromptService instance
            claude_runner: Injected ClaudeRunner instance
            issue_engine_factory: Factory function to create IssueEngine instances
            event_bus: Optional WorkflowEventBus for event emission
            state_manager: Optional StateManager for safe state operations
        """
        self.sprint_path = sprint_path
        self.config = config
        self.project_root = Path(config.project_dir)

        # Injected services
        self.git_service = git_service
        self.sprint_service = sprint_service
        self.issue_service = issue_service
        self.notification_service = notification_service
        self.prompt_service = prompt_service
        self.claude_runner = claude_runner

        # Injected factory
        self.issue_engine_factory = issue_engine_factory

        # Optional integrations
        self.event_bus = event_bus
        self.state_manager = state_manager

        # Iteration tracker for categorized failure handling
        self._iteration_tracker = IterationTracker(
            max_iterations=config.max_total_iterations,
            max_logic_errors=3,
            max_infra_errors=10,
            max_consecutive_failures=5,
        )

        # Rate limit handler (replaces self._rate_limit_retries)
        self._rate_limit_handler = RateLimitHandler(
            RateLimitConfig(
                max_retries=config.rate_limit_retries,
                base_delay_seconds=float(config.rate_limit_base_wait),
                max_delay_seconds=float(config.rate_limit_max_wait),
            )
        )

        # Issue state machine for result handling
        self._state_machine = IssueStateMachine()

    def _emit_event(self, event: WorkflowEvent, payload: dict) -> None:
        """Emit an event to the event bus if configured.

        Args:
            event: The WorkflowEvent type to emit
            payload: Event payload dictionary
        """
        if self.event_bus:
            from datetime import datetime, UTC
            payload.setdefault("timestamp", datetime.now(UTC).isoformat())
            self.event_bus.emit(event, payload)

    def _emit_output(self, text: str, source: str = "sprint_engine") -> None:
        """Emit an OUTPUT event for general text output.

        Args:
            text: The output text
            source: Source identifier for the output
        """
        self._emit_event(WorkflowEvent.OUTPUT, {
            "text": text,
            "source": source,
        })

    def _emit_subprocess_output(self, line: str, step_name: str = "select-issue") -> None:
        """Emit a SUBPROCESS_OUTPUT event for subprocess output lines.

        Args:
            line: The output line from the subprocess
            step_name: The step name for context
        """
        self._emit_event(WorkflowEvent.SUBPROCESS_OUTPUT, {
            "line": line,
            "issue_id": "selecting",
            "step_name": step_name,
        })

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

        This runs PROMPT_select-issue.xml.j2 to have the agent choose
        the next issue based on priority, dependencies, and context.

        If there's already an in_progress issue (from a previous interrupted
        session), that issue is resumed directly without running selection.

        If current_issue.json exists with a pending issue, that issue
        is used directly.

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

        # Check if current_issue.json already has a valid pending issue
        existing_current = self.issue_service.read_current_issue()
        if existing_current and existing_current.issue_id:
            # Find this issue in the sprint
            for issue in sprint.issues:
                if issue.id == existing_current.issue_id and issue.status == IssueStatus.PENDING:
                    # Valid pending issue already selected - use it
                    self.issue_service.log_issue_selection(
                        issue.id, issue.title, "Continuing from select-issue step"
                    )
                    return IssueSelectionResult(
                        success=True,
                        issue_id=issue.id,
                        issue_title=issue.title,
                        rationale="Continuing from select-issue step",
                    )

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
        """Run agent-driven issue selection using PROMPT_select-issue.xml.j2.

        Args:
            sprint: Sprint model
            available: List of available issues

        Returns:
            IssueSelectionResult with selected issue or error
        """
        import json

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

        # Build template context for select-issue prompt
        # For select-issue, we need full sprint data (all issues)
        sprint_json = ""
        if self.sprint_path.exists():
            try:
                sprint_data = json.loads(self.sprint_path.read_text())
                sprint_json = json.dumps(sprint_data, indent=2)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load sprint.json for agent selection context: %s", e)

        current_issue_json = current_issue.model_dump_json(indent=2)
        log_tail = self.issue_service.read_log_tail(num_lines=50)

        # Get base context and build full context
        base_context = self.prompt_service.context
        template_context = PromptContext(
            browser_validation_enabled=base_context.browser_validation_enabled,
            context7_available=base_context.context7_available,
            custom_vars=base_context.custom_vars,
            step_name="select-issue",
            step_goal="Select next issue from sprint",
            sprint_json=sprint_json,
            current_issue_json=current_issue_json,
            log_tail=log_tail,
            current_failures="",
        )
        self.prompt_service.set_context(template_context)

        # Get prompt content using PromptService (handles .xml.j2 templates)
        try:
            prompt_content = self.prompt_service.get_prompt_content("select-issue")
        except FileNotFoundError:
            return IssueSelectionResult(
                success=False,
                issue_id=None,
                issue_title=None,
                rationale="",
                error="Prompt not found: PROMPT_select-issue.xml.j2",
            )

        # Run Claude with the selection prompt
        self._emit_output(
            f"\n{'=' * 60}\n"
            f"SPRINT LOOP: Selecting next issue\n"
            f"{'=' * 60}\n"
        )

        result: ClaudeResult = self.claude_runner.run_with_content(
            prompt_content,
            source_name="PROMPT_select-issue.xml.j2",
            on_output=self._emit_subprocess_output,
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
        # Note: Selection rationale is logged to current_issue.log, not stored in JSON
        updated_issue = self.issue_service.read_current_issue()
        if updated_issue and updated_issue.issue_id:
            issue = sprint.get_issue(updated_issue.issue_id)
            if issue:
                rationale = "Agent selected"
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
        self._emit_output(
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

    def _prepare_sprint(self) -> tuple[Sprint | None, SprintResult | None]:
        """Prepare sprint for execution.

        Runs preflight checks, loads sprint, and sets up the branch.

        Returns:
            Tuple of (sprint, error_result). If sprint is None, error_result
            contains the failure result. If sprint is valid, error_result is None.
        """
        # Pre-flight checks
        valid, errors = self.preflight_check()
        if not valid:
            return None, SprintResult(
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
            return None, SprintResult(
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
            return None, SprintResult(
                exit_reason=SprintExitReason.ERROR,
                issues_completed=0,
                iterations=0,
                elapsed_seconds=0,
                message="Failed to setup sprint branch",
                error=branch_msg,
            )

        return sprint, None

    def _should_stop(
        self,
        iteration: int,
        max_iterations: int,
        start_time: float,
        issues_completed: int,
    ) -> SprintResult | None:
        """Check if the sprint loop should stop.

        Args:
            iteration: Current iteration number
            max_iterations: Maximum iterations allowed (0 = unlimited)
            start_time: Start time of the sprint run
            issues_completed: Number of issues completed so far

        Returns:
            SprintResult if should stop, None if should continue.
        """
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
        return None

    def _handle_issue_result(
        self,
        issue_result: IssueResult,
        issue: Issue,
        start_time: float,
        iteration: int,
        issues_completed: int,
    ) -> tuple[SprintResult | None, int, bool]:
        """Handle the result of an issue execution using the state machine.

        Args:
            issue_result: Result from running the issue engine
            issue: The issue that was executed
            start_time: Start time of the sprint run
            iteration: Current iteration number
            issues_completed: Number of issues completed so far

        Returns:
            Tuple of (exit_result, updated_issues_completed, should_retry_same_issue).
            exit_result is None if sprint should continue, otherwise contains the
            final SprintResult. should_retry_same_issue is True for rate limiting.
        """
        action = self._state_machine.get_action(issue_result.exit_reason)

        if action == SprintAction.CONTINUE_NEXT_ISSUE:
            return self._handle_continue_action(
                issue_result, issue, issues_completed
            )

        elif action == SprintAction.RETRY_SAME_ISSUE:
            return self._handle_retry_action(
                issue_result, issue, start_time, iteration, issues_completed
            )

        elif action == SprintAction.EXIT_SPRINT_FAILURE:
            return self._handle_exit_failure_action(
                issue_result, issue, start_time, iteration, issues_completed
            )

        # Shouldn't reach here if state machine is complete
        return None, issues_completed, False

    def _handle_continue_action(
        self,
        issue_result: IssueResult,
        issue: Issue,
        issues_completed: int,
    ) -> tuple[SprintResult | None, int, bool]:
        """Handle CONTINUE_NEXT_ISSUE action."""
        if issue_result.exit_reason == IssueExitReason.COMPLETED:
            # Mark issue complete in sprint
            self._mark_issue_complete(issue.id)
            issues_completed += 1

            # Clear current_issue artifacts
            self.issue_service.clear_current_issue()

            # Emit issue completed event
            self._emit_event(WorkflowEvent.ISSUE_COMPLETED, {
                "issue_id": issue.id,
                "issue_name": issue.title,
                "exit_reason": "completed",
            })

            # Reset rate limit handler and iteration tracker on successful completion
            self._rate_limit_handler.reset()
            self._iteration_tracker.record_success()

        elif issue_result.exit_reason == IssueExitReason.MAX_ITERATIONS:
            # Mark as blocked (likely infinite loop between steps)
            self.sprint_service.mark_issue_status(
                self.sprint_path,
                issue.id,
                IssueStatus.BLOCKED,
            )
            self.notification_service.notify_failure(
                f"Issue {issue.id} hit max iterations (possible infinite loop)"
            )
            self._emit_output(
                f"\nIssue {issue.id} exceeded max iterations limit "
                f"({self.config.max_total_iterations}), marking as blocked\n"
            )

            # Emit issue failed event
            self._emit_event(WorkflowEvent.ISSUE_FAILED, {
                "issue_id": issue.id,
                "issue_name": issue.title,
                "exit_reason": "max_iterations",
            })

            # Record as logic error (infinite loop is a logic bug)
            self._iteration_tracker.record_failure(
                FailureCategory.LOGIC_ERROR,
                f"Issue {issue.id} exceeded max iterations",
            )

        elif issue_result.exit_reason == IssueExitReason.BLOCKED:
            # Mark issue as blocked and continue to next
            self.sprint_service.mark_issue_status(
                self.sprint_path,
                issue.id,
                IssueStatus.BLOCKED,
            )
            self._emit_output(f"\nIssue {issue.id} is blocked, moving to next\n")

            # Emit issue failed event
            self._emit_event(WorkflowEvent.ISSUE_FAILED, {
                "issue_id": issue.id,
                "issue_name": issue.title,
                "exit_reason": "blocked",
            })

        return None, issues_completed, False

    def _handle_retry_action(
        self,
        issue_result: IssueResult,
        issue: Issue,
        start_time: float,
        iteration: int,
        issues_completed: int,
    ) -> tuple[SprintResult | None, int, bool]:
        """Handle RETRY_SAME_ISSUE action (rate limiting)."""
        self._rate_limit_handler.record_rate_limit()

        # Emit rate limited event
        self._emit_event(WorkflowEvent.RATE_LIMITED, {
            "sprint_id": str(self.sprint_path.parent.name),
            "completed_count": issues_completed,
            "total_count": 0,  # Will be populated by caller
        })

        # Record as rate limit in iteration tracker (doesn't count toward limits)
        self._iteration_tracker.record_failure(
            FailureCategory.RATE_LIMIT,
            "Claude API rate limited",
        )

        if not self._rate_limit_handler.should_retry():
            elapsed = int(time.time() - start_time)
            self.notification_service.notify_rate_limit(
                f"Max rate limit retries ({self._rate_limit_handler.config.max_retries}) exceeded"
            )
            return SprintResult(
                exit_reason=SprintExitReason.RATE_LIMITED,
                issues_completed=issues_completed,
                iterations=iteration,
                elapsed_seconds=elapsed,
                message="Rate limit retries exceeded",
                error="Claude API rate limited",
            ), issues_completed, False

        # Calculate backoff and wait
        backoff = self._rate_limit_handler.get_backoff_seconds()
        self.notification_service.notify_rate_limit(
            f"Rate limited, waiting {backoff}s (retry {self._rate_limit_handler.retry_count})"
        )
        self._emit_output(f"\nRate limited, waiting {backoff} seconds...\n")
        time.sleep(backoff)

        # Signal to retry same issue
        return None, issues_completed, True

    def _handle_exit_failure_action(
        self,
        issue_result: IssueResult,
        issue: Issue,
        start_time: float,
        iteration: int,
        issues_completed: int,
    ) -> tuple[SprintResult | None, int, bool]:
        """Handle EXIT_SPRINT_FAILURE action."""
        elapsed = int(time.time() - start_time)

        if issue_result.exit_reason == IssueExitReason.MAX_RETRY:
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
            ), issues_completed, False

        # CRASHED or ERROR
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
        ), issues_completed, False

    def _finalize_sprint(
        self,
        sprint: Sprint,
        start_time: float,
        iteration: int,
        issues_completed: int,
    ) -> SprintResult:
        """Finalize a completed sprint.

        Args:
            sprint: The sprint that completed
            start_time: Start time of the sprint run
            iteration: Final iteration count
            issues_completed: Total issues completed

        Returns:
            SprintResult for completed sprint.
        """
        elapsed = int(time.time() - start_time)
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

        # Emit sprint completed event
        self._emit_event(WorkflowEvent.SPRINT_COMPLETED, {
            "sprint_id": sprint.spec_id,
            "completed_count": issues_completed,
            "total_count": len(sprint.issues),
        })

        return result

    def _execute_iteration(
        self,
        sprint: Sprint,
        iteration: int,
        start_time: float,
        issues_completed: int,
    ) -> tuple[IssueResult | None, Issue | None, CurrentIssue | None, SprintResult | None]:
        """Execute a single sprint iteration.

        Handles issue selection, context setup, and issue engine execution.

        Args:
            sprint: Current sprint state
            iteration: Current iteration number
            start_time: Start time of the sprint run
            issues_completed: Issues completed so far

        Returns:
            Tuple of (issue_result, issue, current_issue, error_result).
            If error_result is not None, the sprint should exit with that result.
        """
        # Emit SPRINT_ITERATION event
        available_count = len(sprint.get_available_issues())
        stats = sprint.get_stats()
        self._emit_event(WorkflowEvent.SPRINT_ITERATION, {
            "iteration": iteration,
            "available_issues": available_count,
            "completed_count": stats["completed"],
            "total_count": stats["total"],
            "sprint_id": sprint.spec_id,
        })

        # Get bearings - output sprint status between issue cycles
        bearings = self.get_bearings(sprint)
        self._emit_output(bearings)

        # Emit SELECTING_ISSUE event
        self._emit_event(WorkflowEvent.SELECTING_ISSUE, {
            "sprint_id": sprint.spec_id,
        })
        selection = self.select_issue(sprint)
        if not selection.success:
            elapsed = int(time.time() - start_time)
            return None, None, None, SprintResult(
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
            return None, None, None, SprintResult(
                exit_reason=SprintExitReason.ERROR,
                issues_completed=issues_completed,
                iterations=iteration,
                elapsed_seconds=int(time.time() - start_time),
                message="Selected issue not found",
                error=f"Issue {selection.issue_id} not found in sprint",
            )

        # Setup current_issue context
        current_issue, error_result = self._setup_issue_context(
            issue, sprint, iteration, start_time, issues_completed
        )
        if error_result:
            return None, issue, None, error_result

        # Emit issue started event
        self._emit_event(WorkflowEvent.ISSUE_STARTED, {
            "issue_id": issue.id,
            "issue_name": issue.title,
            "exit_reason": None,
        })

        # Record iteration
        self._iteration_tracker.record_iteration()

        # Notify issue selection
        self.notification_service.notify_step(
            f"Selected issue: {issue.id} - {issue.title}"
        )

        # Run issue engine
        issue_result = self._run_issue_engine(issue, current_issue, sprint)

        return issue_result, issue, current_issue, None

    def _setup_issue_context(
        self,
        issue: Issue,
        sprint: Sprint,
        iteration: int,
        start_time: float,
        issues_completed: int,
    ) -> tuple[CurrentIssue | None, SprintResult | None]:
        """Set up the current_issue context for an issue.

        Args:
            issue: The selected issue
            sprint: Current sprint state
            iteration: Current iteration number
            start_time: Start time of the sprint run
            issues_completed: Issues completed so far

        Returns:
            Tuple of (current_issue, error_result). If error_result is not None,
            context setup failed.
        """
        is_resuming = issue.status == IssueStatus.IN_PROGRESS
        existing_current_issue = self.issue_service.read_current_issue()
        has_valid_context = (
            existing_current_issue
            and existing_current_issue.issue_id == issue.id
        )

        if has_valid_context:
            current_issue = existing_current_issue
            if not is_resuming:
                self.sprint_service.mark_issue_status(
                    self.sprint_path,
                    issue.id,
                    IssueStatus.IN_PROGRESS,
                )
            self._emit_output(
                f"\nResuming issue {issue.id} at step: {current_issue.step.value}\n"
            )
        else:
            # Warn about state mismatch
            if is_resuming:
                mismatched_id = (
                    existing_current_issue.issue_id
                    if existing_current_issue
                    else "missing"
                )
                self._emit_output(
                    f"\nWarning: State mismatch detected. "
                    f"Sprint has {issue.id} in_progress but current_issue.json "
                    f"has {mismatched_id}. Creating fresh context.\n"
                )
                self.issue_service.log_step_transition(
                    "resume",
                    "fresh-context",
                    f"State mismatch: sprint={issue.id}, current_issue={mismatched_id}",
                )

            if not is_resuming:
                self.sprint_service.mark_issue_status(
                    self.sprint_path,
                    issue.id,
                    IssueStatus.IN_PROGRESS,
                )

            current_issue = self._create_current_issue(issue, sprint)
            if not self.issue_service.write_current_issue(current_issue):
                return None, SprintResult(
                    exit_reason=SprintExitReason.ERROR,
                    issues_completed=issues_completed,
                    iterations=iteration,
                    elapsed_seconds=int(time.time() - start_time),
                    message="Failed to write current_issue.json",
                    error="Failed to write current_issue.json after issue selection",
                )

            self.issue_service.log_step_transition(
                "select-issue",
                current_issue.step.value,
                f"Selected: {issue.id}",
            )

        return current_issue, None

    def _run_issue_engine(
        self,
        issue: Issue,
        current_issue: CurrentIssue,
        sprint: Sprint,
    ) -> IssueResult:
        """Run the issue engine for an issue.

        Args:
            issue: The issue to run
            current_issue: The current issue context
            sprint: Current sprint state

        Returns:
            IssueResult from the issue engine.
        """
        resolved_config = self._resolve_issue_config(sprint, issue)
        issue_engine = self.issue_engine_factory(resolved_config)

        self._emit_output(
            f"\n{'=' * 60}\n"
            f"ENTERING ISSUE LOOP: {issue.id}\n"
            f"  Title: {issue.title}\n"
            f"  Starting step: {current_issue.step.value}\n"
            f"{'=' * 60}\n"
        )

        issue_result = issue_engine.run(current_issue)

        self._emit_output(
            f"\n{'-' * 60}\n"
            f"EXITING ISSUE LOOP: {issue.id}\n"
            f"  Exit reason: {issue_result.exit_reason.value}\n"
            f"  Steps completed: {issue_result.steps_completed}\n"
            f"  Final step: {issue_result.final_step.value if issue_result.final_step else 'N/A'}\n"
            f"{'-' * 60}\n"
        )

        return issue_result

    def run(
        self,
        max_iterations: int = 0,
    ) -> SprintResult:
        """Run the sprint loop.

        This is the main entry point for sprint execution. It orchestrates:
        1. Sprint preparation (preflight, load, branch setup)
        2. Main iteration loop with issue selection and execution
        3. Result handling via state machine
        4. Sprint finalization

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
            # Prepare sprint
            sprint, error_result = self._prepare_sprint()
            if error_result:
                return error_result

            # Emit sprint started event with full issue list for task board
            self._emit_event(WorkflowEvent.SPRINT_STARTED, {
                "sprint_id": sprint.spec_id,
                "completed_count": 0,
                "total_count": len(sprint.issues),
                "issues": [
                    {
                        "id": issue.id,
                        "title": issue.title,
                        "status": issue.status.value,
                        "priority": issue.priority.value,
                        "category": issue.category.value if issue.category else None,
                    }
                    for issue in sprint.issues
                ],
            })

            # Reset iteration tracker for this sprint run
            self._iteration_tracker.reset()

            # Main sprint loop
            while True:
                iteration += 1

                # Check if should stop
                stop_result = self._should_stop(
                    iteration, max_iterations, start_time, issues_completed
                )
                if stop_result:
                    return stop_result

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

                # Check if sprint is complete
                if sprint.is_complete():
                    return self._finalize_sprint(
                        sprint, start_time, iteration, issues_completed
                    )

                # Execute iteration
                issue_result, issue, current_issue, error_result = self._execute_iteration(
                    sprint, iteration, start_time, issues_completed
                )
                if error_result:
                    return error_result

                # Handle issue result
                exit_result, issues_completed, should_retry = self._handle_issue_result(
                    issue_result, issue, start_time, iteration, issues_completed
                )

                if exit_result:
                    return exit_result

                if should_retry:
                    # Don't increment iteration for rate limit retry
                    iteration -= 1

                # Small delay between issues
                time.sleep(self.config.issue_delay)

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
