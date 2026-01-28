"""Issue engine - inner loop orchestration for single issue workflows.

The IssueEngine manages the inner loop:
1. Run workflow steps (read-docs -> implement -> write-tests -> etc.)
2. Handle conditional routing based on step output
3. Track retry counts and handle max retry limits
4. Respect execution gates (require_testing, require_browser_qa)
"""

import re
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Callable

from claudesprint.core.claude_runner import ClaudeRunner, ClaudeResult
from claudesprint.models.config import ClaudesprintConfig
from claudesprint.models.current_issue import CurrentIssue, IssueStep, ChunkType
from claudesprint.models.sprint import ResolvedConfig, IssueStatus
from claudesprint.services.issue_service import IssueService
from claudesprint.services.models_service import ModelsService
from claudesprint.services.prompt_service import PromptService
from claudesprint.services.sprint_service import SprintService
from claudesprint.services.notification_service import NotificationService


class IssueExitReason(StrEnum):
    """Reasons for issue loop exit."""

    COMPLETED = "completed"
    MAX_RETRY = "max_retry"
    MAX_ITERATIONS = "max_iterations"  # Total iteration limit (prevents infinite loops)
    RATE_LIMITED = "rate_limited"
    CRASHED = "crashed"
    BLOCKED = "blocked"
    ERROR = "error"


@dataclass
class IssueResult:
    """Result of running an issue through the workflow."""

    exit_reason: IssueExitReason
    issue_id: str
    steps_completed: int
    elapsed_seconds: int
    final_step: IssueStep
    message: str
    error: str | None = None


@dataclass
class StepResult:
    """Result of executing a single workflow step."""

    success: bool
    next_step: IssueStep | None
    output: str
    rate_limited: bool = False
    crashed: bool = False
    error: str | None = None


@dataclass
class ParseResult:
    """Result of parsing step output."""

    next_step: IssueStep | None
    matched_signal: str | None  # The signal that matched, or None if default


class IssueEngine:
    """Inner loop engine - runs 13 workflow steps for one issue.

    Manages the step-by-step execution of a single issue through
    the workflow, handling conditional routing and error recovery.
    """

    # Step routing table - maps step to possible next steps based on output signals
    STEP_ROUTING: dict[IssueStep, dict[str, IssueStep | None]] = {
        IssueStep.SELECT_ISSUE: {"default": IssueStep.READ_DOCS},
        IssueStep.READ_DOCS: {"default": IssueStep.IMPLEMENT},
        IssueStep.IMPLEMENT: {"default": IssueStep.WRITE_TESTS},
        IssueStep.WRITE_TESTS: {"default": IssueStep.RUN_TESTS},
        IssueStep.RUN_TESTS: {
            "pass": IssueStep.BROWSER_VALIDATION,
            "fail_code": IssueStep.IMPLEMENT,
            "fail_test": IssueStep.FIX_TESTS,
            "default": IssueStep.BROWSER_VALIDATION,
        },
        IssueStep.FIX_TESTS: {
            "test_fixed": IssueStep.RUN_TESTS,
            "code_wrong": IssueStep.IMPLEMENT,
            "default": IssueStep.RUN_TESTS,
        },
        IssueStep.BROWSER_VALIDATION: {
            "pass": IssueStep.CODE_REVIEW,
            "fail": IssueStep.IMPLEMENT,
            "skip": IssueStep.CODE_REVIEW,
            "default": IssueStep.CODE_REVIEW,
        },
        IssueStep.CODE_REVIEW: {
            "pass": IssueStep.UPDATE_DOCS,
            "issues": IssueStep.FIX_CODE_REVIEW_ISSUES,
            "default": IssueStep.UPDATE_DOCS,
        },
        IssueStep.FIX_CODE_REVIEW_ISSUES: {"default": IssueStep.RUN_TESTS},
        IssueStep.UPDATE_DOCS: {"default": IssueStep.STAGE_CHANGES},
        IssueStep.STAGE_CHANGES: {"default": IssueStep.COMMIT_CHANGES},
        IssueStep.COMMIT_CHANGES: {"default": IssueStep.COMPLETE_ISSUE},
        IssueStep.COMPLETE_ISSUE: {"default": None},  # Exit loop
    }

    # Steps that MUST have an explicit signal match - default routing is not allowed
    # because it can create infinite loops (e.g., FIX_TESTS -> RUN_TESTS -> FIX_TESTS)
    REQUIRES_EXPLICIT_SIGNAL: set[IssueStep] = {
        IssueStep.RUN_TESTS,
        IssueStep.FIX_TESTS,
    }

    # Patterns for parsing step output to determine routing
    # These patterns match <status>...</status> XML tags that signal routing decisions.
    # XML tags are preferred over plain text markers for more robust LLM output parsing.
    OUTPUT_PATTERNS = {
        IssueStep.RUN_TESTS: {
            "pass": [
                r"<status>\s*pass\s*</status>",
            ],
            "fail_code": [
                r"<status>\s*fail_code\s*</status>",
            ],
            "fail_test": [
                r"<status>\s*fail_test\s*</status>",
            ],
        },
        IssueStep.FIX_TESTS: {
            "code_wrong": [
                r"<status>\s*code_wrong\s*</status>",
            ],
            "test_fixed": [
                r"<status>\s*test_fixed\s*</status>",
            ],
        },
        IssueStep.BROWSER_VALIDATION: {
            "skip": [
                r"<status>\s*skip\s*</status>",
            ],
            "fail": [
                r"<status>\s*fail\s*</status>",
            ],
            "pass": [
                r"<status>\s*pass\s*</status>",
            ],
        },
        IssueStep.CODE_REVIEW: {
            "issues": [
                r"<status>\s*issues\s*</status>",
            ],
            "pass": [
                r"<status>\s*pass\s*</status>",
            ],
        },
    }

    def __init__(
        self,
        config: ClaudesprintConfig,
        execution_config: ResolvedConfig,
        # Injected Dependencies:
        issue_service: IssueService,
        sprint_service: SprintService,
        notification_service: NotificationService,
        prompt_service: PromptService,
        claude_runner: ClaudeRunner,
    ) -> None:
        """Initialize IssueEngine.

        Args:
            config: ClaudesprintConfig with timeout and retry settings
            execution_config: ResolvedConfig with resolved execution gates for this issue
            issue_service: Service for managing current issue state
            sprint_service: Service for managing sprint data
            notification_service: Service for sending notifications
            prompt_service: Service for loading prompt templates
            claude_runner: Runner for executing Claude commands
        """
        self.config = config
        self.execution_config = execution_config
        self.issue_service = issue_service
        self.sprint_service = sprint_service
        self.notification_service = notification_service
        self.prompt_service = prompt_service
        self.claude_runner = claude_runner

        # Callbacks
        self.on_output: Callable[[str], None] | None = None
        self.on_step_complete: Callable[[IssueStep, IssueStep | None], None] | None = None
        self.on_step_start: Callable[[IssueStep, str], None] | None = None  # (step, model)
        self.on_step_skip: Callable[[IssueStep, IssueStep | None], None] | None = None
        self.on_step_failure: Callable[[IssueStep, int], None] | None = None  # (step, retry_count)
        self.on_subprocess_start: Callable[[int, str], None] | None = None  # (pid, command)
        self.on_subprocess_output: Callable[[str], None] | None = None  # (line)
        self.on_subprocess_end: Callable[[], None] | None = None

    def run(self, current_issue: CurrentIssue) -> IssueResult:
        """Run the issue through the workflow until completion or exit.

        Args:
            current_issue: CurrentIssue context with initial step

        Returns:
            IssueResult with final outcome
        """
        start_time = time.time()
        steps_completed = 0
        issue_id = current_issue.issue_id

        while True:
            # Check total iteration limit (prevents infinite loops between steps)
            if current_issue.total_iterations >= self.config.max_total_iterations:
                self.notification_service.notify_failure(
                    f"Max total iterations reached ({self.config.max_total_iterations}) for: {issue_id}"
                )
                return IssueResult(
                    exit_reason=IssueExitReason.MAX_ITERATIONS,
                    issue_id=issue_id,
                    steps_completed=steps_completed,
                    elapsed_seconds=int(time.time() - start_time),
                    final_step=current_issue.step,
                    message=f"Max total iterations limit ({self.config.max_total_iterations}) reached - possible infinite loop",
                    error="Total iteration limit exceeded. This usually indicates an infinite loop between steps like FIX_TESTS <-> RUN_TESTS.",
                )

            # Increment total iterations before any step processing (including skips)
            current_issue.total_iterations += 1
            self.issue_service.write_current_issue(current_issue)

            # Check if we should skip the current step
            if self._should_skip_step(current_issue.step):
                skip_result = self._get_skip_result(current_issue.step)

                # Notify about the skip so the user knows what happened
                self.notification_service.notify_step_with_context(
                    step=current_issue.step.value,
                    next_step=skip_result.next_step.value if skip_result.next_step else "complete",
                    task_id=issue_id,
                    task_title=current_issue.issue_title,
                    status="SKIPPED ⏭️",
                )

                # Callback: step skipped
                if self.on_step_skip:
                    self.on_step_skip(current_issue.step, skip_result.next_step)

                if skip_result.next_step:
                    self._transition_step(current_issue, skip_result.next_step, skipped=True)
                    steps_completed += 1
                    continue
                else:
                    # Completed
                    return IssueResult(
                        exit_reason=IssueExitReason.COMPLETED,
                        issue_id=issue_id,
                        steps_completed=steps_completed,
                        elapsed_seconds=int(time.time() - start_time),
                        final_step=current_issue.step,
                        message="Issue completed successfully",
                    )

            # Execute the step
            step_result = self._execute_step(current_issue)

            # Handle rate limiting
            if step_result.rate_limited:
                return IssueResult(
                    exit_reason=IssueExitReason.RATE_LIMITED,
                    issue_id=issue_id,
                    steps_completed=steps_completed,
                    elapsed_seconds=int(time.time() - start_time),
                    final_step=current_issue.step,
                    message="Rate limited by Claude API",
                )

            # Handle crash
            if step_result.crashed:
                return IssueResult(
                    exit_reason=IssueExitReason.CRASHED,
                    issue_id=issue_id,
                    steps_completed=steps_completed,
                    elapsed_seconds=int(time.time() - start_time),
                    final_step=current_issue.step,
                    message="Claude session crashed",
                    error=step_result.error,
                )

            # Handle step failure (retry logic)
            if not step_result.success:
                current_issue.retry_count += 1
                current_issue.current_failures = step_result.error or "Step failed"
                if not self.issue_service.write_current_issue(current_issue):
                    raise RuntimeError("Failed to write current_issue.json after step failure")

                # Callback: step failure
                if self.on_step_failure:
                    self.on_step_failure(current_issue.step, current_issue.retry_count)

                if current_issue.retry_count >= self.config.max_retry:
                    self.notification_service.notify_failure(
                        f"Max retry reached on {current_issue.step}: {issue_id}"
                    )
                    return IssueResult(
                        exit_reason=IssueExitReason.MAX_RETRY,
                        issue_id=issue_id,
                        steps_completed=steps_completed,
                        elapsed_seconds=int(time.time() - start_time),
                        final_step=current_issue.step,
                        message=f"Max retry limit ({self.config.max_retry}) reached",
                        error=step_result.error,
                    )

                # Retry the same step
                continue

            # Step succeeded
            steps_completed += 1
            current_issue.retry_count = 0
            current_issue.current_failures = ""

            # Determine next step
            next_step = step_result.next_step

            # Check if we're done
            if next_step is None:
                elapsed = int(time.time() - start_time)
                self.notification_service.notify_step(
                    f"Issue complete: {issue_id} ({steps_completed} steps)"
                )
                return IssueResult(
                    exit_reason=IssueExitReason.COMPLETED,
                    issue_id=issue_id,
                    steps_completed=steps_completed,
                    elapsed_seconds=elapsed,
                    final_step=current_issue.step,
                    message="Issue completed successfully",
                )

            # Capture the current step before transition
            completed_step = current_issue.step

            # Transition to next step
            self._transition_step(current_issue, next_step)

            # Notify step completion with rich context
            self.notification_service.notify_step_with_context(
                step=completed_step.value,
                next_step=next_step.value,
                task_id=issue_id,
                task_title=current_issue.issue_title,
                status="DONE ✅",
            )

            # Small delay between steps to avoid hammering API
            time.sleep(1)

    def _execute_step(self, current_issue: CurrentIssue) -> StepResult:
        """Execute a single workflow step.

        Args:
            current_issue: CurrentIssue context

        Returns:
            StepResult with outcome and next step
        """
        step = current_issue.step

        # Intercept complete-issue step - execute via Python, not LLM
        if step == IssueStep.COMPLETE_ISSUE:
            return self._execute_complete_issue(current_issue)

        # Get prompt content for this step using hierarchical loading
        prompt_name = self._get_prompt_name(step)
        try:
            prompt_content = self.prompt_service.get_prompt_content(prompt_name)
            # Prepend common prompt content if available
            try:
                common_content = self.prompt_service.get_common_prompt_content()
                prompt_content = common_content + "\n\n---\n\n" + prompt_content
            except FileNotFoundError:
                pass  # Common prompt is optional
        except FileNotFoundError:
            return StepResult(
                success=False,
                next_step=None,
                output="",
                error=f"Prompt not found: PROMPT_{prompt_name}.md",
            )

        # Backup current_issue before running
        self.issue_service.backup_current_issue()

        # Get model for this step
        models_service = ModelsService(self.config.models_file)
        model = models_service.get_model_for_step(step)

        # Callback: step starting
        if self.on_step_start:
            self.on_step_start(step, model)

        # Build context from full session log for agent awareness
        session_log = self.issue_service.read_full_log()
        context_str: str | None = None
        if session_log:
            context_str = (
                "## Session Activity Log\n"
                "The following log shows the complete workflow activity for this session. "
                "Use this to understand the full progression, including any failures or decisions made.\n\n"
                f"```\n{session_log}\n```\n"
            )

        # Run Claude with the prompt
        if self.on_output:
            self.on_output(f"\n=== Running step: {step} ===\n")

        # Wire up subprocess callbacks
        self.claude_runner.on_subprocess_start = self.on_subprocess_start
        self.claude_runner.on_subprocess_end = self.on_subprocess_end

        # Create combined output handler that notifies both on_output and on_subprocess_output
        def combined_output_handler(line: str) -> None:
            if self.on_output:
                self.on_output(line)
            if self.on_subprocess_output:
                self.on_subprocess_output(line)

        result: ClaudeResult = self.claude_runner.run_with_content(
            prompt_content,
            source_name=f"PROMPT_{prompt_name}.md",
            on_output=combined_output_handler,
            model=model,
            context=context_str,
        )

        # Check for rate limiting
        if result.rate_limited:
            return StepResult(
                success=False,
                next_step=None,
                output=result.output,
                rate_limited=True,
            )

        # Check for crash
        if result.crashed:
            return StepResult(
                success=False,
                next_step=None,
                output=result.output,
                crashed=True,
                error=result.error_type or "Claude crashed",
            )

        # Parse output to determine routing
        parse_result = self._parse_step_output(step, result.output)
        next_step = parse_result.next_step

        # Check if this step requires explicit signal matching
        # If so, using default routing is a failure (prevents infinite loops)
        if step in self.REQUIRES_EXPLICIT_SIGNAL and parse_result.matched_signal is None:
            expected_patterns = list(self.OUTPUT_PATTERNS.get(step, {}).keys())
            return StepResult(
                success=False,
                next_step=None,
                output=result.output,
                error=(
                    f"Step {step} requires explicit STATUS terminator but none found. "
                    f"Expected one of: {', '.join(expected_patterns)}. "
                    "Check that the prompt ends with a STATUS line."
                ),
            )

        # Reload current_issue to get any updates made by Claude
        updated_issue = self.issue_service.read_current_issue()
        if updated_issue:
            # Claude may have updated the step field directly
            if updated_issue.step != current_issue.step:
                next_step = updated_issue.step

        # Check exit code
        if result.exit_code != 0 and not next_step:
            return StepResult(
                success=False,
                next_step=None,
                output=result.output,
                error=f"Claude exited with code {result.exit_code}",
            )

        return StepResult(
            success=True,
            next_step=next_step,
            output=result.output,
        )

    def _execute_complete_issue(self, current_issue: CurrentIssue) -> StepResult:
        """Pure Python implementation of complete-issue step.

        Updates sprint.json status to 'completed', logs completion,
        and signals the workflow to exit.

        Args:
            current_issue: CurrentIssue context

        Returns:
            StepResult with outcome (next_step=None signals loop exit)
        """
        # Safety check: do not complete if there are known failures
        if current_issue.current_failures:
            return StepResult(
                success=False,
                next_step=IssueStep.FIX_CODE_REVIEW_ISSUES,
                output="Cannot complete issue: Outstanding failures detected.",
                error="Outstanding failures present in current_issue context",
            )

        # Update sprint file (mark as completed)
        success = self.sprint_service.mark_issue_status(
            path=current_issue.sprint_path,
            issue_id=current_issue.issue_id,
            status=IssueStatus.COMPLETED,
            session_id=current_issue.session_id,
        )

        if not success:
            return StepResult(
                success=False,
                next_step=None,
                output="Failed to update sprint.json",
                error=f"Could not find issue {current_issue.issue_id} in {current_issue.sprint_path}",
            )

        # Log completion
        self.issue_service.log_issue_completion(
            current_issue.issue_id,
            current_issue.issue_title,
        )

        # Return success with next_step=None (signals loop exit)
        output_msg = (
            f"=== Issue Complete ===\n"
            f"Issue: {current_issue.issue_id}\n"
            f"Title: {current_issue.issue_title}\n"
            f"Status: COMPLETED\n"
        )

        return StepResult(
            success=True,
            next_step=None,  # This triggers IssueExitReason.COMPLETED in run()
            output=output_msg,
        )

    def _parse_step_output(self, step: IssueStep, output: str) -> ParseResult:
        """Parse step output to determine next step based on signals.

        Args:
            step: Current step
            output: Claude output text

        Returns:
            ParseResult with next step and whether a signal matched
        """
        routing = self.STEP_ROUTING.get(step, {})
        patterns = self.OUTPUT_PATTERNS.get(step, {})

        # Strip trailing whitespace/newlines to handle Claude adding extra newlines
        # while still requiring STATUS token to be at end of meaningful content
        output_lower = output.lower().strip()

        # Try to match patterns for conditional routing
        for signal, signal_patterns in patterns.items():
            for pattern in signal_patterns:
                if re.search(pattern, output_lower, re.IGNORECASE):
                    if signal in routing:
                        return ParseResult(
                            next_step=routing[signal],
                            matched_signal=signal,
                        )

        # Fall back to default routing
        return ParseResult(
            next_step=routing.get("default"),
            matched_signal=None,
        )

    def _should_skip_step(self, step: IssueStep) -> bool:
        """Check if a step should be skipped based on execution gates.

        Args:
            step: Step to check

        Returns:
            True if step should be skipped
        """
        # Skip testing steps if testing not required
        if step in IssueStep.testing_steps():
            return not self.execution_config.require_testing

        # Skip browser validation if not required
        if step in IssueStep.browser_qa_steps():
            return not self.execution_config.require_browser_qa

        return False

    def _get_skip_result(self, step: IssueStep) -> StepResult:
        """Get the result for a skipped step.

        Args:
            step: Skipped step

        Returns:
            StepResult with next step after skip
        """
        # Log the skip
        self.issue_service.log_step_transition(
            step.value,
            "SKIPPED",
            f"Gate disabled: testing={self.execution_config.require_testing}, "
            f"browser_qa={self.execution_config.require_browser_qa}",
        )

        # Map skipped step to appropriate next step
        if step == IssueStep.WRITE_TESTS:
            # Skip write-tests -> go to browser validation or code review
            if self.execution_config.require_browser_qa:
                return StepResult(
                    success=True,
                    next_step=IssueStep.BROWSER_VALIDATION,
                    output="Skipped: testing not required",
                )
            return StepResult(
                success=True,
                next_step=IssueStep.CODE_REVIEW,
                output="Skipped: testing not required",
            )

        if step == IssueStep.RUN_TESTS:
            # Skip run-tests -> go to browser validation or code review
            if self.execution_config.require_browser_qa:
                return StepResult(
                    success=True,
                    next_step=IssueStep.BROWSER_VALIDATION,
                    output="Skipped: testing not required",
                )
            return StepResult(
                success=True,
                next_step=IssueStep.CODE_REVIEW,
                output="Skipped: testing not required",
            )

        if step == IssueStep.FIX_TESTS:
            # This shouldn't happen if testing is disabled, but handle it
            return StepResult(
                success=True,
                next_step=IssueStep.CODE_REVIEW,
                output="Skipped: testing not required",
            )

        if step == IssueStep.BROWSER_VALIDATION:
            return StepResult(
                success=True,
                next_step=IssueStep.CODE_REVIEW,
                output="Skipped: browser QA not required",
            )

        # Default: use routing table
        routing = self.STEP_ROUTING.get(step, {})
        return StepResult(
            success=True,
            next_step=routing.get("default"),
            output="Skipped",
        )

    def _transition_step(
        self,
        current_issue: CurrentIssue,
        next_step: IssueStep,
        *,
        skipped: bool = False,
    ) -> None:
        """Transition to the next step.

        Args:
            current_issue: CurrentIssue to update
            next_step: New step to transition to
            skipped: If True, the step was skipped (don't fire on_step_complete)
        """
        from_step = current_issue.step

        # Update current_issue
        current_issue.step = next_step
        current_issue.chunk_type = next_step.to_chunk_type()
        current_issue.session_id = current_issue.generate_session_id()
        current_issue.next_action = self._get_next_action(next_step, current_issue)

        # Prune arrays to prevent unbounded growth
        current_issue.prune_arrays()

        # Write updated state
        if not self.issue_service.write_current_issue(current_issue):
            raise RuntimeError(
                f"Failed to write current_issue.json during transition to {next_step}"
            )

        # Log transition
        self.issue_service.log_step_transition(
            from_step.value,
            next_step.value,
        )

        # Callback (only for completed steps, not skipped ones)
        if self.on_step_complete and not skipped:
            self.on_step_complete(from_step, next_step)

    def _get_next_action(self, step: IssueStep, current_issue: CurrentIssue) -> str:
        """Get the next_action description for a step.

        Args:
            step: Step to get action for
            current_issue: Current issue context

        Returns:
            Next action description string
        """
        issue_title = current_issue.issue_title or current_issue.issue_id

        actions = {
            IssueStep.SELECT_ISSUE: "Review sprint and select next issue to work on",
            IssueStep.READ_DOCS: f"Read documentation for: {issue_title}",
            IssueStep.IMPLEMENT: f"Implement changes for: {issue_title}",
            IssueStep.WRITE_TESTS: f"Write tests for: {issue_title}",
            IssueStep.RUN_TESTS: "Run test suite and verify all tests pass",
            IssueStep.FIX_TESTS: "Analyze test failures and fix issues",
            IssueStep.BROWSER_VALIDATION: f"Validate UI changes for: {issue_title}",
            IssueStep.CODE_REVIEW: f"Review code changes for: {issue_title}",
            IssueStep.FIX_CODE_REVIEW_ISSUES: "Fix issues identified in code review",
            IssueStep.UPDATE_DOCS: f"Update documentation for: {issue_title}",
            IssueStep.STAGE_CHANGES: "Stage changes for commit",
            IssueStep.COMMIT_CHANGES: "Create commit with staged changes",
            IssueStep.COMPLETE_ISSUE: f"Mark issue complete: {issue_title}",
        }

        return actions.get(step, f"Execute step: {step}")

    def _get_prompt_name(self, step: IssueStep) -> str:
        """Get the prompt name for a workflow step.

        Args:
            step: Workflow step

        Returns:
            Prompt name (e.g., "implement", "run-tests")
        """
        # Map IssueStep to prompt file name
        step_to_prompt = {
            IssueStep.SELECT_ISSUE: "select-issue",
            IssueStep.READ_DOCS: "read-docs",
            IssueStep.IMPLEMENT: "implement",
            IssueStep.WRITE_TESTS: "write-tests",
            IssueStep.RUN_TESTS: "run-tests",
            IssueStep.FIX_TESTS: "fix-tests",
            IssueStep.BROWSER_VALIDATION: "browser-validation",
            IssueStep.CODE_REVIEW: "code-review",
            IssueStep.FIX_CODE_REVIEW_ISSUES: "fix-code-review-issues",
            IssueStep.UPDATE_DOCS: "update-docs",
            IssueStep.STAGE_CHANGES: "stage-changes",
            IssueStep.COMMIT_CHANGES: "commit-changes",
            IssueStep.COMPLETE_ISSUE: "complete-issue",
        }

        return step_to_prompt.get(step, step.value)
