"""Issue engine - inner loop orchestration for single issue workflows.

The IssueEngine manages the inner loop:
1. Run workflow steps (read-docs -> implement -> write-tests -> etc.)
2. Handle conditional routing based on step output
3. Track retry counts and handle max retry limits
4. Respect execution gates (require_testing, require_browser_qa)
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from claudesprint.core.claude_runner import ClaudeRunner

if TYPE_CHECKING:
    from claudesprint.events.workflow_event_bus import WorkflowEventBus

from claudesprint.events.workflow_event_bus import WorkflowEvent, IssueIterationPayload, RoutingSignalPayload
from claudesprint.core.step_executors import (
    CompletionStepExecutor,
    LlmStepExecutor,
    StepExecutor,
)
from claudesprint.core.step_types import ParseResult, StepResult
from claudesprint.models.config import ClaudesprintConfig
from claudesprint.models.current_issue import CurrentIssue, IssueStep
from claudesprint.models.sprint import ResolvedConfig
from claudesprint.services.issue_service import IssueService
from claudesprint.services.models_service import ModelsService
from claudesprint.services.notification_service import NotificationService
from claudesprint.services.prompt_service import PromptService
from claudesprint.services.sprint_service import SprintService

# Re-export for backward compatibility
__all__ = ["IssueEngine", "IssueExitReason", "IssueResult", "ParseResult", "StepResult"]


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


class IssueEngine:
    """Inner loop engine - runs 13 workflow steps for one issue.

    Manages the step-by-step execution of a single issue through
    the workflow, handling conditional routing and error recovery.
    """

    # Step routing table - maps step to possible next steps based on output signals
    STEP_ROUTING: dict[IssueStep, dict[str, IssueStep | None]] = {
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

    # Steps that use non-default executors (default is LlmStepExecutor)
    STEP_EXECUTOR_OVERRIDES: dict[IssueStep, type] = {
        IssueStep.COMPLETE_ISSUE: CompletionStepExecutor,
    }

    # Patterns for parsing step output to determine routing
    # These patterns match <routing_signal>...</routing_signal> XML tags that signal routing decisions.
    # The distinct tag name avoids false matches with code snippets in verbose Claude output.
    OUTPUT_PATTERNS = {
        IssueStep.RUN_TESTS: {
            "pass": [
                r"<routing_signal>\s*pass\s*</routing_signal>",
            ],
            "fail_code": [
                r"<routing_signal>\s*fail_code\s*</routing_signal>",
            ],
            "fail_test": [
                r"<routing_signal>\s*fail_test\s*</routing_signal>",
            ],
        },
        IssueStep.FIX_TESTS: {
            "code_wrong": [
                r"<routing_signal>\s*code_wrong\s*</routing_signal>",
            ],
            "test_fixed": [
                r"<routing_signal>\s*test_fixed\s*</routing_signal>",
            ],
        },
        IssueStep.BROWSER_VALIDATION: {
            "skip": [
                r"<routing_signal>\s*skip\s*</routing_signal>",
            ],
            "fail": [
                r"<routing_signal>\s*fail\s*</routing_signal>",
            ],
            "pass": [
                r"<routing_signal>\s*pass\s*</routing_signal>",
            ],
        },
        IssueStep.CODE_REVIEW: {
            "issues": [
                r"<routing_signal>\s*issues\s*</routing_signal>",
            ],
            "pass": [
                r"<routing_signal>\s*pass\s*</routing_signal>",
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
        event_bus: WorkflowEventBus | None = None,
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
            event_bus: Optional event bus for emitting workflow events
        """
        self.config = config
        self.execution_config = execution_config
        self.issue_service = issue_service
        self.sprint_service = sprint_service
        self.notification_service = notification_service
        self.prompt_service = prompt_service
        self.claude_runner = claude_runner
        self.event_bus = event_bus

        # Step executors registry
        self._step_executors: dict[IssueStep, StepExecutor] = {}
        self._init_step_executors()

    def _init_step_executors(self) -> None:
        """Initialize and register step executors.

        Uses STEP_EXECUTOR_OVERRIDES to determine executor types.
        Default executor is LlmStepExecutor for steps not in the overrides.
        """
        models_service = ModelsService(self.config.models_file)

        # Create executor instances
        # Event-driven: callbacks emit events via the event bus
        executor_instances: dict[type, StepExecutor] = {
            LlmStepExecutor: LlmStepExecutor(
                prompt_service=self.prompt_service,
                claude_runner=self.claude_runner,
                issue_service=self.issue_service,
                models_service=models_service,
                parse_step_output=self._parse_step_output,
                requires_explicit_signal=self.REQUIRES_EXPLICIT_SIGNAL,
                output_patterns=self.OUTPUT_PATTERNS,
                on_step_start=lambda s, m: self._emit_step_started(s, m),
                on_subprocess_start=lambda p, c: self._emit_subprocess_started(p, c),
                on_subprocess_end=lambda: self._emit_subprocess_ended(),
                on_subprocess_output=lambda ln: self._emit_subprocess_output(ln),
            ),
            CompletionStepExecutor: CompletionStepExecutor(
                sprint_service=self.sprint_service,
                issue_service=self.issue_service,
            ),
        }

        # Register executors for each step using the declarative mapping
        for step in IssueStep:
            executor_type = self.STEP_EXECUTOR_OVERRIDES.get(step, LlmStepExecutor)
            self._step_executors[step] = executor_instances[executor_type]

        # Verify all steps have executors (fail fast on misconfiguration)
        missing_steps = set(IssueStep) - set(self._step_executors.keys())
        if missing_steps:
            raise RuntimeError(f"No executor registered for steps: {missing_steps}")

    def _emit_event(self, event: WorkflowEvent, payload: dict) -> None:
        """Emit an event to the event bus if configured.

        Args:
            event: The workflow event type to emit
            payload: Event payload dict (timestamp will be added if missing)
        """
        if self.event_bus:
            payload.setdefault("timestamp", datetime.now(UTC).isoformat())
            self.event_bus.emit(event, payload)

    def _emit_step_started(self, step: IssueStep, model: str) -> None:
        """Emit STEP_STARTED event.

        Args:
            step: The step that is starting
            model: The model being used for the step
        """
        current_issue = self.issue_service.read_current_issue()
        issue_id = current_issue.issue_id if current_issue else "unknown"
        self._emit_event(WorkflowEvent.STEP_STARTED, {
            "issue_id": issue_id,
            "step_name": step.value,
            "step_index": 0,
            "model": model,
        })

    def _emit_subprocess_started(self, pid: int, command: str) -> None:
        """Emit SUBPROCESS_STARTED event.

        Args:
            pid: Process ID
            command: Command being run
        """
        current_issue = self.issue_service.read_current_issue()
        issue_id = current_issue.issue_id if current_issue else "unknown"
        step_name = current_issue.step.value if current_issue else "unknown"
        self._emit_event(WorkflowEvent.SUBPROCESS_STARTED, {
            "pid": pid,
            "command": command,
            "issue_id": issue_id,
            "step_name": step_name,
        })

    def _emit_subprocess_output(self, line: str) -> None:
        """Emit SUBPROCESS_OUTPUT event.

        Args:
            line: Output line from the subprocess
        """
        current_issue = self.issue_service.read_current_issue()
        issue_id = current_issue.issue_id if current_issue else "unknown"
        step_name = current_issue.step.value if current_issue else "unknown"
        self._emit_event(WorkflowEvent.SUBPROCESS_OUTPUT, {
            "line": line,
            "issue_id": issue_id,
            "step_name": step_name,
        })

    def _emit_subprocess_ended(self) -> None:
        """Emit SUBPROCESS_ENDED event."""
        current_issue = self.issue_service.read_current_issue()
        issue_id = current_issue.issue_id if current_issue else "unknown"
        step_name = current_issue.step.value if current_issue else "unknown"
        self._emit_event(WorkflowEvent.SUBPROCESS_ENDED, {
            "issue_id": issue_id,
            "step_name": step_name,
        })

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

            # Emit ISSUE_ITERATION event for logging/tracking
            self._emit_event(WorkflowEvent.ISSUE_ITERATION, {
                "total_iterations": current_issue.total_iterations,
                "max_iterations": self.config.max_total_iterations,
                "retry_count": current_issue.retry_count,
                "max_retry": self.config.max_retry,
                "issue_id": issue_id,
            })

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

                # Emit STEP_SKIPPED event
                self._emit_event(WorkflowEvent.STEP_SKIPPED, {
                    "issue_id": issue_id,
                    "step_name": current_issue.step.value,
                    "next_step": skip_result.next_step.value if skip_result.next_step else None,
                })

                if skip_result.next_step:
                    if not self._transition_step(current_issue, skip_result.next_step, skipped=True):
                        return IssueResult(
                            exit_reason=IssueExitReason.ERROR,
                            issue_id=issue_id,
                            steps_completed=steps_completed,
                            elapsed_seconds=int(time.time() - start_time),
                            final_step=current_issue.step,
                            message=f"Failed to transition from {current_issue.step} to {skip_result.next_step}",
                            error="Step transition failed",
                        )
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

                # Emit STEP_FAILED event
                self._emit_event(WorkflowEvent.STEP_FAILED, {
                    "issue_id": issue_id,
                    "step_name": current_issue.step.value,
                    "step_index": current_issue.retry_count,
                    "retry_count": current_issue.retry_count,
                    "max_retry": self.config.max_retry,
                    "error": step_result.error,
                })

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

            # Emit ROUTING_SIGNAL event
            self._emit_event(WorkflowEvent.ROUTING_SIGNAL, {
                "step_name": current_issue.step.value,
                "signal": step_result.matched_signal,
                "next_step": next_step.value if next_step else None,
                "issue_id": issue_id,
            })

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
            if not self._transition_step(current_issue, next_step):
                return IssueResult(
                    exit_reason=IssueExitReason.ERROR,
                    issue_id=issue_id,
                    steps_completed=steps_completed,
                    elapsed_seconds=int(time.time() - start_time),
                    final_step=completed_step,
                    message=f"Failed to transition from {completed_step} to {next_step}",
                    error="Step transition failed",
                )

            # Notify step completion with rich context
            self.notification_service.notify_step_with_context(
                step=completed_step.value,
                next_step=next_step.value,
                task_id=issue_id,
                task_title=current_issue.issue_title,
                status="DONE ✅",
            )

            # Emit STEP_COMPLETED event
            self._emit_event(WorkflowEvent.STEP_COMPLETED, {
                "issue_id": issue_id,
                "step_name": completed_step.value,
                "step_index": steps_completed,
                "next_step": next_step.value,
            })

            # Small delay between steps to avoid hammering API
            time.sleep(1)

    def _execute_step(self, current_issue: CurrentIssue) -> StepResult:
        """Execute a single workflow step.

        Delegates to the registered StepExecutor for the current step.

        Args:
            current_issue: CurrentIssue context

        Returns:
            StepResult with outcome and next step
        """
        step = current_issue.step

        # Look up the executor for this step
        executor = self._step_executors.get(step)
        if executor is None:
            return StepResult(
                success=False,
                next_step=None,
                output="",
                error=f"No executor registered for step: {step}",
            )

        # Delegate execution to the executor
        # Note: on_output is None - output is streamed via SUBPROCESS_OUTPUT events
        return executor.execute(current_issue, on_output=None)

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
                if re.search(pattern, output_lower, re.IGNORECASE) and signal in routing:
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
    ) -> bool:
        """Transition to the next step with validate-before-mutate pattern.

        Creates a backup of mutable state before mutation. If the write fails,
        the state is rolled back to prevent corruption.

        Args:
            current_issue: CurrentIssue to update
            next_step: New step to transition to
            skipped: If True, the step was skipped (for logging purposes)

        Returns:
            True if transition succeeded, False if it failed (state is unchanged).
        """
        from_step = current_issue.step

        # 1. Pre-validation: Check if transition is valid
        if not self._validate_step_transition(from_step, next_step):
            self._log_invalid_transition(from_step, next_step)
            return False

        # 2. Create backup of mutable fields before any changes
        backup = {
            "step": current_issue.step,
            "chunk_type": current_issue.chunk_type,
            "session_id": current_issue.session_id,
            "next_action": current_issue.next_action,
        }

        # 3. Mutate state
        try:
            current_issue.step = next_step
            current_issue.chunk_type = next_step.to_chunk_type()
            current_issue.session_id = current_issue.generate_session_id()
            current_issue.next_action = self._get_next_action(next_step, current_issue)

            # Prune arrays to prevent unbounded growth
            current_issue.prune_arrays()

            # 4. Write and validate
            if not self.issue_service.write_current_issue(current_issue):
                raise RuntimeError("Write failed")

            # 5. Success - log transition
            self.issue_service.log_step_transition(
                from_step.value,
                next_step.value,
            )

            return True

        except Exception as e:
            # 6. Rollback on failure
            current_issue.step = backup["step"]
            current_issue.chunk_type = backup["chunk_type"]
            current_issue.session_id = backup["session_id"]
            current_issue.next_action = backup["next_action"]
            self._log_rollback(current_issue, next_step, e)
            return False

    def _validate_step_transition(
        self,
        from_step: IssueStep,
        to_step: IssueStep,
    ) -> bool:
        """Validate that a step transition is allowed.

        Checks against the STEP_ROUTING table to ensure the transition
        is a valid path in the workflow.

        Args:
            from_step: Current step
            to_step: Target step

        Returns:
            True if the transition is valid.
        """
        routing = self.STEP_ROUTING.get(from_step, {})

        # Check if to_step is reachable from from_step
        valid_targets = set(routing.values())
        return to_step in valid_targets

    def _log_invalid_transition(
        self,
        from_step: IssueStep,
        to_step: IssueStep,
    ) -> None:
        """Log an invalid step transition attempt.

        Args:
            from_step: Current step
            to_step: Attempted target step
        """
        self.issue_service.log_step_transition(
            from_step.value,
            to_step.value,
            f"INVALID TRANSITION: {from_step.value} -> {to_step.value} not allowed",
        )

    def _log_rollback(
        self,
        current_issue: CurrentIssue,
        target_step: IssueStep,
        error: Exception,
    ) -> None:
        """Log a rollback after a failed transition.

        Args:
            current_issue: The issue whose state was rolled back
            target_step: The step we were trying to transition to
            error: The exception that caused the rollback
        """
        self.issue_service.log_step_transition(
            current_issue.step.value,
            target_step.value,
            f"ROLLBACK: Transition failed, state restored. Error: {error}",
        )

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

