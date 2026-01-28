"""Step executors for the IssueEngine.

The StepExecutor pattern separates step execution strategies from the
engine's orchestration logic. Each executor handles a specific type of step:

- LlmStepExecutor: Runs steps via LLM prompts (the default)
- CompletionStepExecutor: Runs the COMPLETE_ISSUE step via Python logic
"""

from abc import ABC, abstractmethod
from collections.abc import Callable

from claudesprint.core.claude_runner import ClaudeResult, ClaudeRunner
from claudesprint.core.step_types import ParseResult, StepResult
from claudesprint.models.current_issue import CurrentIssue, IssueStep
from claudesprint.models.sprint import IssueStatus
from claudesprint.services.issue_service import IssueService
from claudesprint.services.models_service import ModelsService
from claudesprint.services.prompt_service import PromptService
from claudesprint.services.sprint_service import SprintService


class StepExecutor(ABC):
    """Abstract base class for step executors.

    Each executor handles the execution of one or more workflow steps.
    The IssueEngine looks up the appropriate executor for each step
    and delegates execution to it.
    """

    @abstractmethod
    def execute(
        self,
        current_issue: CurrentIssue,
        on_output: Callable[[str], None] | None = None,
    ) -> StepResult:
        """Execute the step.

        Args:
            current_issue: CurrentIssue context
            on_output: Optional callback for output streaming

        Returns:
            StepResult with outcome and next step
        """
        ...


class LlmStepExecutor(StepExecutor):
    """Default executor that runs steps via LLM prompts."""

    def __init__(
        self,
        prompt_service: PromptService,
        claude_runner: ClaudeRunner,
        issue_service: IssueService,
        models_service: ModelsService,
        parse_step_output: Callable[[IssueStep, str], ParseResult],
        requires_explicit_signal: set[IssueStep],
        output_patterns: dict[IssueStep, dict[str, list[str]]],
        on_step_start: Callable[[IssueStep, str], None] | None = None,
        on_subprocess_start: Callable[[int, str], None] | None = None,
        on_subprocess_end: Callable[[], None] | None = None,
        on_subprocess_output: Callable[[str], None] | None = None,
    ) -> None:
        """Initialize LlmStepExecutor.

        Args:
            prompt_service: Service for loading prompt templates
            claude_runner: Runner for executing Claude commands
            issue_service: Service for managing current issue state
            models_service: Service for model configuration
            parse_step_output: Function to parse step output for routing
            requires_explicit_signal: Steps that require explicit signal matching
            output_patterns: Patterns for parsing step output
            on_step_start: Callback when step starts
            on_subprocess_start: Callback when subprocess starts
            on_subprocess_end: Callback when subprocess ends
            on_subprocess_output: Callback for subprocess output
        """
        self.prompt_service = prompt_service
        self.claude_runner = claude_runner
        self.issue_service = issue_service
        self.models_service = models_service
        self.parse_step_output = parse_step_output
        self.requires_explicit_signal = requires_explicit_signal
        self.output_patterns = output_patterns
        self.on_step_start = on_step_start
        self.on_subprocess_start = on_subprocess_start
        self.on_subprocess_end = on_subprocess_end
        self.on_subprocess_output = on_subprocess_output

    def execute(
        self,
        current_issue: CurrentIssue,
        on_output: Callable[[str], None] | None = None,
    ) -> StepResult:
        """Execute step via LLM prompt.

        Args:
            current_issue: CurrentIssue context
            on_output: Optional callback for output streaming

        Returns:
            StepResult with outcome and next step
        """
        step = current_issue.step

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
        model = self.models_service.get_model_for_step(step)

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
        if on_output:
            on_output(f"\n=== Running step: {step} ===\n")

        # Wire up subprocess callbacks
        self.claude_runner.on_subprocess_start = self.on_subprocess_start
        self.claude_runner.on_subprocess_end = self.on_subprocess_end

        # Create combined output handler that notifies both on_output and on_subprocess_output
        def combined_output_handler(line: str) -> None:
            if on_output:
                on_output(line)
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
        parse_result = self.parse_step_output(step, result.output)
        next_step = parse_result.next_step

        # Check if this step requires explicit signal matching
        # If so, using default routing is a failure (prevents infinite loops)
        if step in self.requires_explicit_signal and parse_result.matched_signal is None:
            expected_patterns = list(self.output_patterns.get(step, {}).keys())
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
        # Claude may have updated the step field directly
        if updated_issue and updated_issue.step != current_issue.step:
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

    def _get_prompt_name(self, step: IssueStep) -> str:
        """Get the prompt name for a workflow step.

        Args:
            step: Workflow step

        Returns:
            Prompt name (e.g., "implement", "run-tests")
        """
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


class CompletionStepExecutor(StepExecutor):
    """Executor for the COMPLETE_ISSUE step.

    This executor runs Python logic instead of an LLM prompt to:
    - Update sprint.json status to 'completed'
    - Log completion
    - Signal the workflow to exit
    """

    def __init__(
        self,
        sprint_service: SprintService,
        issue_service: IssueService,
    ) -> None:
        """Initialize CompletionStepExecutor.

        Args:
            sprint_service: Service for managing sprint data
            issue_service: Service for managing current issue state
        """
        self.sprint_service = sprint_service
        self.issue_service = issue_service

    def execute(
        self,
        current_issue: CurrentIssue,
        on_output: Callable[[str], None] | None = None,
    ) -> StepResult:
        """Execute the COMPLETE_ISSUE step via Python logic.

        Args:
            current_issue: CurrentIssue context
            on_output: Optional callback for output streaming

        Returns:
            StepResult with outcome (next_step=None signals loop exit)
        """
        if on_output:
            on_output(f"\n=== Running step: {current_issue.step} ===\n")

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

        if on_output:
            on_output(output_msg)

        return StepResult(
            success=True,
            next_step=None,  # This triggers IssueExitReason.COMPLETED in run()
            output=output_msg,
        )
