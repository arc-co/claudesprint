"""Step executors for the IssueEngine.

The StepExecutor pattern separates step execution strategies from the
engine's orchestration logic. Each executor handles a specific type of step:

- LlmStepExecutor: Runs steps via LLM prompts (the default)
- CompletionStepExecutor: Runs the COMPLETE_ISSUE step via Python logic
"""

import json
import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)

from claudesprint.core.claude_runner import ClaudeResult, ClaudeRunner, FailureCategory
from claudesprint.core.step_types import ParseResult, StepResult
from claudesprint.models.current_issue import CurrentIssue, IssueStep
from claudesprint.models.sprint import IssueStatus
from claudesprint.services.issue_service import IssueService
from claudesprint.services.models_service import ModelsService
from claudesprint.services.prompt_service import PromptContext, PromptService
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
            on_step_start: Callback when step starts (emits STEP_STARTED event)
            on_subprocess_start: Callback when subprocess starts (emits SUBPROCESS_STARTED event)
            on_subprocess_end: Callback when subprocess ends (emits SUBPROCESS_ENDED event)
            on_subprocess_output: Callback for subprocess output (emits SUBPROCESS_OUTPUT event)
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

    def _build_template_context(self, current_issue: CurrentIssue) -> PromptContext:
        """Build rich context data for XML template injection.

        Args:
            current_issue: CurrentIssue context

        Returns:
            PromptContext with all fields populated for XML template rendering
        """
        step = current_issue.step
        prompt_name = self._get_prompt_name(step)

        # Get step goal from current_issue
        step_goal = current_issue.goal or f"Execute the {prompt_name} workflow step"

        # Load sprint.json content if available
        # Optimization: For select-issue, inject full sprint (needs all issues)
        # For other steps, inject minimal sprint with only current issue's data
        sprint_json = ""
        if current_issue.sprint_path:
            sprint_path = Path(current_issue.sprint_path)
            if sprint_path.exists():
                try:
                    sprint_data = json.loads(sprint_path.read_text())

                    # For non-select-issue steps, filter to only current issue
                    if step != IssueStep.SELECT_ISSUE and current_issue.issue_id:
                        # Find current issue in sprint
                        current_issue_data = None
                        for issue in sprint_data.get("issues", []):
                            if issue.get("id") == current_issue.issue_id:
                                current_issue_data = issue
                                break

                        # Create minimal sprint with only current issue
                        if current_issue_data:
                            sprint_data = {
                                "spec_id": sprint_data.get("spec_id", ""),
                                "spec_file": sprint_data.get("spec_file", ""),
                                "description": sprint_data.get("description", ""),
                                "config": sprint_data.get("config", {}),
                                "git_branch": sprint_data.get("git_branch"),
                                "issues": [current_issue_data],
                                "metadata": {
                                    "total_issues": sprint_data.get("metadata", {}).get(
                                        "total_issues", 0
                                    ),
                                    "note": "Filtered to current issue only",
                                },
                            }

                    sprint_json = json.dumps(sprint_data, indent=2)
                except (json.JSONDecodeError, OSError) as e:
                    logger.warning("Failed to load sprint.json for prompt context (step=%s): %s", step, e)

        # Serialize current_issue to JSON
        current_issue_json = current_issue.model_dump_json(indent=2)

        # Get log tail (last 50 lines) for context
        log_tail = self.issue_service.read_log_tail(num_lines=50)

        # Get current failures
        current_failures = current_issue.current_failures or ""

        # Create base context from prompt service
        base_context = self.prompt_service.context

        return PromptContext(
            browser_validation_enabled=base_context.browser_validation_enabled,
            context7_available=base_context.context7_available,
            custom_vars=base_context.custom_vars,
            step_name=prompt_name,
            step_goal=step_goal,
            sprint_json=sprint_json,
            current_issue_json=current_issue_json,
            log_tail=log_tail,
            current_failures=current_failures,
        )

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

        # Build rich context for XML template
        template_context = self._build_template_context(current_issue)
        self.prompt_service.set_context(template_context)

        # Get prompt content for this step using hierarchical loading
        # For XML templates, common content is included via {% include '_common.xml.j2' %}
        prompt_name = self._get_prompt_name(step)
        try:
            prompt_content = self.prompt_service.get_prompt_content(prompt_name)
        except FileNotFoundError:
            return StepResult(
                success=False,
                next_step=None,
                output="",
                error=f"Prompt not found: PROMPT_{prompt_name}.xml.j2",
            )

        # Get model for this step
        model = self.models_service.get_model_for_step(step)

        # Callback: step starting
        if self.on_step_start:
            self.on_step_start(step, model)

        # Run Claude with the prompt
        # Note: Context is now embedded in XML template via <artifact> tags
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
            source_name=f"PROMPT_{prompt_name}.xml.j2",
            on_output=combined_output_handler,
            model=model,
            context=None,  # Context is embedded in XML template
        )

        # Check for rate limiting
        if result.rate_limited:
            return StepResult(
                success=False,
                next_step=None,
                output=result.output,
                rate_limited=True,
            )

        # Check for system error (crash)
        if result.failure_category == FailureCategory.SYSTEM_ERROR:
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

        # NOTE: We intentionally do NOT allow Claude to override the step field
        # by writing to current_issue.json. Step transitions must go through
        # the routing table in IssueEngine to ensure valid transitions and
        # proper skip logic for disabled gates (require_testing, require_browser_qa).

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
            matched_signal=parse_result.matched_signal,
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
    - Validate issue can be completed (no outstanding failures)
    - Log completion
    - Signal the workflow to exit

    Note: Sprint status update is handled by SprintEngine when it receives
    the COMPLETED exit reason, to ensure single source of truth.
    """

    def __init__(
        self,
        sprint_service: SprintService,
        issue_service: IssueService,
    ) -> None:
        """Initialize CompletionStepExecutor.

        Args:
            sprint_service: Service for managing sprint data (kept for compatibility)
            issue_service: Service for managing current issue state
        """
        self.sprint_service = sprint_service  # Kept for potential future use
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

        # Log completion (sprint status update is handled by SprintEngine)
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
