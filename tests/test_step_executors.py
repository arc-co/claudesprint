"""Tests for step executors in claudesprint.core.step_executors."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from claudesprint.core.claude_runner import ClaudeResult, FailureCategory
from claudesprint.core.issue_engine import ParseResult, StepResult
from claudesprint.core.step_executors import (
    CompletionStepExecutor,
    LlmStepExecutor,
    StepExecutor,
)
from claudesprint.models.current_issue import ChunkType, CurrentIssue, IssueStep
from claudesprint.models.sprint import IssueStatus


# --- Fixtures ---


@pytest.fixture
def sample_current_issue() -> CurrentIssue:
    """Create a sample CurrentIssue for testing."""
    return CurrentIssue(
        schema_version="2.0",
        session_id="2026-01-28T12:00:00Z/implement",
        timestamp="2026-01-28T12:00:00Z",
        sprint_path="./sprints/test/sprint.json",
        issue_id="test-issue-001",
        issue_title="Test issue for step executors",
        chunk_type=ChunkType.IMPLEMENT,
        step=IssueStep.IMPLEMENT,
        goal="Test goal",
        next_action="Test action",
        total_iterations=0,
    )


@pytest.fixture
def mock_prompt_service() -> MagicMock:
    """Create a mock prompt service."""
    from claudesprint.services.prompt_service import PromptContext
    mock = MagicMock()
    mock.get_prompt_content.return_value = "Test prompt content for step"
    mock.get_common_prompt_content.return_value = "Common prompt prefix"
    # For XML templates, provide a context property
    mock.context = PromptContext()
    return mock


@pytest.fixture
def mock_claude_runner() -> MagicMock:
    """Create a mock ClaudeRunner."""
    mock = MagicMock()
    mock.run_with_content.return_value = ClaudeResult(
        exit_code=0,
        duration_seconds=10,
        timed_out=False,
        rate_limited=False,
        failure_category=FailureCategory.NONE,
        output="Successful execution output\n<routing_signal>pass</routing_signal>",
        error_type=None,
    )
    return mock


@pytest.fixture
def mock_issue_service() -> MagicMock:
    """Create a mock issue service."""
    mock = MagicMock()
    mock.read_full_log.return_value = ""
    mock.read_log_tail.return_value = ""
    mock.read_current_issue.return_value = None
    mock.log_issue_completion.return_value = True
    return mock


@pytest.fixture
def mock_models_service() -> MagicMock:
    """Create a mock models service."""
    mock = MagicMock()
    mock.get_model_for_step.return_value = "sonnet"
    return mock


@pytest.fixture
def mock_sprint_service() -> MagicMock:
    """Create a mock sprint service."""
    mock = MagicMock()
    mock.mark_issue_status.return_value = True
    return mock


@pytest.fixture
def default_parse_step_output():
    """Create a default parse_step_output function that returns success routing."""
    def parse_fn(step: IssueStep, output: str) -> ParseResult:
        # Default behavior: return next step based on routing
        if "<routing_signal>pass</routing_signal>" in output.lower():
            return ParseResult(next_step=IssueStep.CODE_REVIEW, matched_signal="pass")
        if "<routing_signal>fail" in output.lower():
            return ParseResult(next_step=IssueStep.IMPLEMENT, matched_signal="fail")
        # Default routing
        return ParseResult(next_step=IssueStep.WRITE_TESTS, matched_signal=None)
    return parse_fn


@pytest.fixture
def llm_executor(
    mock_prompt_service: MagicMock,
    mock_claude_runner: MagicMock,
    mock_issue_service: MagicMock,
    mock_models_service: MagicMock,
    default_parse_step_output,
) -> LlmStepExecutor:
    """Create an LlmStepExecutor with mocked dependencies."""
    return LlmStepExecutor(
        prompt_service=mock_prompt_service,
        claude_runner=mock_claude_runner,
        issue_service=mock_issue_service,
        models_service=mock_models_service,
        parse_step_output=default_parse_step_output,
        requires_explicit_signal={
            IssueStep.RUN_TESTS,
            IssueStep.FIX_TESTS,
            IssueStep.BROWSER_VALIDATION,
            IssueStep.CODE_REVIEW,
        },
        output_patterns={
            IssueStep.RUN_TESTS: {
                "pass": [r"<routing_signal>\s*pass\s*</routing_signal>"],
                "fail_code": [r"<routing_signal>\s*fail_code\s*</routing_signal>"],
                "fail_test": [r"<routing_signal>\s*fail_test\s*</routing_signal>"],
            },
            IssueStep.FIX_TESTS: {
                "code_wrong": [r"<routing_signal>\s*code_wrong\s*</routing_signal>"],
                "test_fixed": [r"<routing_signal>\s*test_fixed\s*</routing_signal>"],
            },
            IssueStep.BROWSER_VALIDATION: {
                "skip": [r"<routing_signal>\s*skip\s*</routing_signal>"],
                "fail": [r"<routing_signal>\s*fail\s*</routing_signal>"],
                "pass": [r"<routing_signal>\s*pass\s*</routing_signal>"],
            },
            IssueStep.CODE_REVIEW: {
                "issues": [r"<routing_signal>\s*issues\s*</routing_signal>"],
                "pass": [r"<routing_signal>\s*pass\s*</routing_signal>"],
            },
        },
    )


@pytest.fixture
def completion_executor(
    mock_sprint_service: MagicMock,
    mock_issue_service: MagicMock,
) -> CompletionStepExecutor:
    """Create a CompletionStepExecutor with mocked dependencies."""
    return CompletionStepExecutor(
        sprint_service=mock_sprint_service,
        issue_service=mock_issue_service,
    )


# --- LlmStepExecutor Tests ---


class TestLlmStepExecutor:
    """Tests for LlmStepExecutor."""

    def test_successful_execution(
        self,
        llm_executor: LlmStepExecutor,
        sample_current_issue: CurrentIssue,
        mock_claude_runner: MagicMock,
        mock_prompt_service: MagicMock,
        mock_issue_service: MagicMock,
    ) -> None:
        """Test successful step execution with mocked claude_runner."""
        # Execute the step
        result = llm_executor.execute(sample_current_issue)

        # Verify success
        assert result.success is True
        assert result.rate_limited is False
        assert result.crashed is False
        assert result.error is None

        # Verify claude_runner was called
        mock_claude_runner.run_with_content.assert_called_once()
        call_args = mock_claude_runner.run_with_content.call_args

        # Verify prompt content was fetched
        mock_prompt_service.get_prompt_content.assert_called_once_with("implement")

        # Verify model was fetched
        llm_executor.models_service.get_model_for_step.assert_called_once_with(
            IssueStep.IMPLEMENT
        )

    def test_handling_rate_limiting(
        self,
        llm_executor: LlmStepExecutor,
        sample_current_issue: CurrentIssue,
        mock_claude_runner: MagicMock,
    ) -> None:
        """Test handling of rate limiting (result.rate_limited = True)."""
        # Configure mock to return rate limited result
        mock_claude_runner.run_with_content.return_value = ClaudeResult(
            exit_code=1,
            duration_seconds=5,
            timed_out=False,
            rate_limited=True,
            failure_category=FailureCategory.RATE_LIMITED,
            output="You've hit your limit. Please try again later.",
            error_type=None,
        )

        # Execute the step
        result = llm_executor.execute(sample_current_issue)

        # Verify rate limiting is propagated
        assert result.success is False
        assert result.rate_limited is True
        assert result.crashed is False
        assert result.next_step is None

    def test_handling_crash(
        self,
        llm_executor: LlmStepExecutor,
        sample_current_issue: CurrentIssue,
        mock_claude_runner: MagicMock,
    ) -> None:
        """Test handling of crash (result.crashed = True via SYSTEM_ERROR)."""
        # Configure mock to return crashed result (SYSTEM_ERROR category)
        mock_claude_runner.run_with_content.return_value = ClaudeResult(
            exit_code=137,  # SIGKILL (128 + 9)
            duration_seconds=2,
            timed_out=False,
            rate_limited=False,
            failure_category=FailureCategory.SYSTEM_ERROR,
            output="No messages returned",
            error_type="signal_9",
        )

        # Execute the step
        result = llm_executor.execute(sample_current_issue)

        # Verify crash is propagated
        assert result.success is False
        assert result.crashed is True
        assert result.rate_limited is False
        assert result.next_step is None
        assert result.error == "signal_9"

    def test_prompt_not_found_error(
        self,
        llm_executor: LlmStepExecutor,
        sample_current_issue: CurrentIssue,
        mock_prompt_service: MagicMock,
    ) -> None:
        """Test prompt not found error handling."""
        # Configure mock to raise FileNotFoundError
        mock_prompt_service.get_prompt_content.side_effect = FileNotFoundError(
            "Prompt file not found"
        )

        # Execute the step
        result = llm_executor.execute(sample_current_issue)

        # Verify error handling
        assert result.success is False
        assert result.next_step is None
        assert "Prompt not found" in result.error
        assert "PROMPT_implement.xml.j2" in result.error

    def test_explicit_signal_requirement_failure(
        self,
        mock_prompt_service: MagicMock,
        mock_claude_runner: MagicMock,
        mock_issue_service: MagicMock,
        mock_models_service: MagicMock,
    ) -> None:
        """Test explicit signal requirement failure for steps like RUN_TESTS."""
        # Create parse function that returns no matched signal (uses default routing)
        def parse_no_signal(step: IssueStep, output: str) -> ParseResult:
            return ParseResult(next_step=IssueStep.BROWSER_VALIDATION, matched_signal=None)

        # Create executor with RUN_TESTS requiring explicit signal
        executor = LlmStepExecutor(
            prompt_service=mock_prompt_service,
            claude_runner=mock_claude_runner,
            issue_service=mock_issue_service,
            models_service=mock_models_service,
            parse_step_output=parse_no_signal,
            requires_explicit_signal={IssueStep.RUN_TESTS},
            output_patterns={
                IssueStep.RUN_TESTS: {
                    "pass": [r"<routing_signal>\s*pass\s*</routing_signal>"],
                    "fail_code": [r"<routing_signal>\s*fail_code\s*</routing_signal>"],
                    "fail_test": [r"<routing_signal>\s*fail_test\s*</routing_signal>"],
                },
            },
        )

        # Create issue at RUN_TESTS step
        current_issue = CurrentIssue(
            schema_version="2.0",
            session_id="2026-01-28T12:00:00Z/run-tests",
            timestamp="2026-01-28T12:00:00Z",
            sprint_path="./sprints/test/sprint.json",
            issue_id="test-issue-001",
            issue_title="Test issue",
            chunk_type=ChunkType.TEST,
            step=IssueStep.RUN_TESTS,
            goal="Run tests",
            next_action="Run tests",
        )

        # Configure mock to return output without status signal
        mock_claude_runner.run_with_content.return_value = ClaudeResult(
            exit_code=0,
            duration_seconds=10,
            timed_out=False,
            rate_limited=False,
            failure_category=FailureCategory.NONE,
            output="Tests completed but no status tag provided",
            error_type=None,
        )

        # Execute the step
        result = executor.execute(current_issue)

        # Verify explicit signal requirement failure
        assert result.success is False
        assert result.next_step is None
        assert "requires explicit STATUS terminator" in result.error
        assert "run-tests" in result.error

    def test_on_output_callback_called(
        self,
        llm_executor: LlmStepExecutor,
        sample_current_issue: CurrentIssue,
    ) -> None:
        """Test that on_output callback is called when provided."""
        output_lines = []

        def capture_output(line: str) -> None:
            output_lines.append(line)

        # Execute with callback
        llm_executor.execute(sample_current_issue, on_output=capture_output)

        # Verify callback was called (at least for step announcement)
        assert len(output_lines) > 0
        assert any("Running step" in line for line in output_lines)

    def test_step_to_prompt_name_mapping(
        self,
        llm_executor: LlmStepExecutor,
    ) -> None:
        """Test that step names are correctly mapped to prompt names."""
        # Verify all step mappings
        assert llm_executor._get_prompt_name(IssueStep.SELECT_ISSUE) == "select-issue"
        assert llm_executor._get_prompt_name(IssueStep.READ_DOCS) == "read-docs"
        assert llm_executor._get_prompt_name(IssueStep.IMPLEMENT) == "implement"
        assert llm_executor._get_prompt_name(IssueStep.WRITE_TESTS) == "write-tests"
        assert llm_executor._get_prompt_name(IssueStep.RUN_TESTS) == "run-tests"
        assert llm_executor._get_prompt_name(IssueStep.FIX_TESTS) == "fix-tests"
        assert llm_executor._get_prompt_name(IssueStep.BROWSER_VALIDATION) == "browser-validation"
        assert llm_executor._get_prompt_name(IssueStep.CODE_REVIEW) == "code-review"
        assert llm_executor._get_prompt_name(IssueStep.FIX_CODE_REVIEW_ISSUES) == "fix-code-review-issues"
        assert llm_executor._get_prompt_name(IssueStep.UPDATE_DOCS) == "update-docs"
        assert llm_executor._get_prompt_name(IssueStep.STAGE_CHANGES) == "stage-changes"
        assert llm_executor._get_prompt_name(IssueStep.COMMIT_CHANGES) == "commit-changes"
        assert llm_executor._get_prompt_name(IssueStep.COMPLETE_ISSUE) == "complete-issue"

    def test_common_prompt_included_via_template(
        self,
        llm_executor: LlmStepExecutor,
        sample_current_issue: CurrentIssue,
        mock_prompt_service: MagicMock,
        mock_claude_runner: MagicMock,
    ) -> None:
        """Test that common prompt is included via XML template inheritance.

        For XML templates, common content is included via {% include '_common.xml.j2' %}
        in the _base.xml.j2 template, so get_common_prompt_content is not called separately.
        """
        # Execute the step
        llm_executor.execute(sample_current_issue)

        # Verify get_prompt_content was called (which renders the template with includes)
        mock_prompt_service.get_prompt_content.assert_called_once()

        # Verify the prompt was passed to claude_runner
        call_args = mock_claude_runner.run_with_content.call_args
        prompt_content = call_args.args[0]

        # The prompt content is rendered from the XML template
        assert "Test prompt content" in prompt_content

    def test_common_prompt_optional(
        self,
        llm_executor: LlmStepExecutor,
        sample_current_issue: CurrentIssue,
        mock_prompt_service: MagicMock,
        mock_claude_runner: MagicMock,
    ) -> None:
        """Test that missing common prompt doesn't cause failure."""
        # Configure mock to raise FileNotFoundError for common prompt
        mock_prompt_service.get_common_prompt_content.side_effect = FileNotFoundError(
            "Common prompt not found"
        )

        # Execute the step - should not raise
        result = llm_executor.execute(sample_current_issue)

        # Step should still succeed
        assert result.success is True

    def test_session_log_embedded_in_template(
        self,
        llm_executor: LlmStepExecutor,
        sample_current_issue: CurrentIssue,
        mock_issue_service: MagicMock,
        mock_claude_runner: MagicMock,
        mock_prompt_service: MagicMock,
    ) -> None:
        """Test that session log is embedded in the XML template context.

        For XML templates, context is embedded via <artifact> tags in the template
        rather than passed as a separate context string to claude_runner.
        """
        # Configure mock to return session log tail
        mock_issue_service.read_log_tail.return_value = "Previous step completed successfully"

        # Execute the step
        llm_executor.execute(sample_current_issue)

        # Verify context was passed as None (context is in template)
        call_args = mock_claude_runner.run_with_content.call_args
        context = call_args.kwargs.get("context")
        assert context is None

        # Verify set_context was called on prompt_service
        mock_prompt_service.set_context.assert_called_once()

    def test_updated_issue_step_ignored(
        self,
        llm_executor: LlmStepExecutor,
        sample_current_issue: CurrentIssue,
        mock_issue_service: MagicMock,
    ) -> None:
        """Test that if Claude updates the step field, it's ignored.

        Step transitions must go through the routing table to ensure valid
        transitions and proper skip logic for disabled gates.
        """
        # Configure mock to return updated issue with different step
        # (simulating Claude writing to current_issue.json directly)
        updated_issue = CurrentIssue(
            schema_version="2.0",
            session_id="2026-01-28T12:00:00Z/write-tests",
            timestamp="2026-01-28T12:00:00Z",
            sprint_path="./sprints/test/sprint.json",
            issue_id="test-issue-001",
            issue_title="Test issue",
            chunk_type=ChunkType.TEST,
            step=IssueStep.WRITE_TESTS,  # Claude tried to change the step
            goal="Write tests",
            next_action="Write tests",
        )
        mock_issue_service.read_current_issue.return_value = updated_issue

        # Execute the step
        result = llm_executor.execute(sample_current_issue)

        # Verify Claude's override is IGNORED and routing table is used
        # The mock claude_runner returns <routing_signal>pass</routing_signal>
        # which maps to CODE_REVIEW in default_parse_step_output
        assert result.next_step == IssueStep.CODE_REVIEW

    def test_non_zero_exit_code_without_next_step_fails(
        self,
        mock_prompt_service: MagicMock,
        mock_claude_runner: MagicMock,
        mock_issue_service: MagicMock,
        mock_models_service: MagicMock,
    ) -> None:
        """Test that non-zero exit code without next_step is a failure."""
        # Create parse function that returns no next step
        def parse_no_next(step: IssueStep, output: str) -> ParseResult:
            return ParseResult(next_step=None, matched_signal=None)

        executor = LlmStepExecutor(
            prompt_service=mock_prompt_service,
            claude_runner=mock_claude_runner,
            issue_service=mock_issue_service,
            models_service=mock_models_service,
            parse_step_output=parse_no_next,
            requires_explicit_signal=set(),  # No explicit signal required
            output_patterns={},
        )

        # Configure mock to return non-zero exit code (REJECTED category)
        mock_claude_runner.run_with_content.return_value = ClaudeResult(
            exit_code=1,
            duration_seconds=10,
            timed_out=False,
            rate_limited=False,
            failure_category=FailureCategory.REJECTED,
            output="Command failed with error",
            error_type="exit_1",
        )

        current_issue = CurrentIssue(
            schema_version="2.0",
            session_id="2026-01-28T12:00:00Z/implement",
            timestamp="2026-01-28T12:00:00Z",
            sprint_path="./sprints/test/sprint.json",
            issue_id="test-issue-001",
            issue_title="Test issue",
            chunk_type=ChunkType.IMPLEMENT,
            step=IssueStep.IMPLEMENT,
            goal="Implement",
            next_action="Implement",
        )

        # Execute the step
        result = executor.execute(current_issue)

        # Verify failure
        assert result.success is False
        assert "exited with code 1" in result.error


# --- CompletionStepExecutor Tests ---


class TestCompletionStepExecutor:
    """Tests for CompletionStepExecutor."""

    def test_successful_completion(
        self,
        completion_executor: CompletionStepExecutor,
        mock_sprint_service: MagicMock,
        mock_issue_service: MagicMock,
    ) -> None:
        """Test successful completion logs and returns next_step=None.

        Note: Sprint status update is now handled by SprintEngine, not the executor.
        """
        # Create issue at COMPLETE_ISSUE step
        current_issue = CurrentIssue(
            schema_version="2.0",
            session_id="2026-01-28T12:00:00Z/complete-issue",
            timestamp="2026-01-28T12:00:00Z",
            sprint_path="./sprints/test/sprint.json",
            issue_id="test-issue-001",
            issue_title="Test issue completed",
            chunk_type=ChunkType.COMPLETE,
            step=IssueStep.COMPLETE_ISSUE,
            goal="Complete the issue",
            next_action="Mark issue as complete",
            current_failures="",  # No failures
        )

        # Execute the completion step
        result = completion_executor.execute(current_issue)

        # Verify success
        assert result.success is True
        assert result.next_step is None  # Signals loop exit
        assert "test-issue-001" in result.output
        assert "COMPLETED" in result.output

        # Sprint status update is handled by SprintEngine, not executor
        mock_sprint_service.mark_issue_status.assert_not_called()

        # Verify completion was logged
        mock_issue_service.log_issue_completion.assert_called_once_with(
            "test-issue-001",
            "Test issue completed",
        )

    def test_failure_when_current_failures_set(
        self,
        completion_executor: CompletionStepExecutor,
        mock_sprint_service: MagicMock,
    ) -> None:
        """Test failure when current_failures is set (should return FIX_CODE_REVIEW_ISSUES)."""
        # Create issue with outstanding failures
        current_issue = CurrentIssue(
            schema_version="2.0",
            session_id="2026-01-28T12:00:00Z/complete-issue",
            timestamp="2026-01-28T12:00:00Z",
            sprint_path="./sprints/test/sprint.json",
            issue_id="test-issue-001",
            issue_title="Test issue with failures",
            chunk_type=ChunkType.COMPLETE,
            step=IssueStep.COMPLETE_ISSUE,
            goal="Complete the issue",
            next_action="Mark issue as complete",
            current_failures="Code review found issues: missing error handling",
        )

        # Execute the completion step
        result = completion_executor.execute(current_issue)

        # Verify failure with redirect to fix issues
        assert result.success is False
        assert result.next_step == IssueStep.FIX_CODE_REVIEW_ISSUES
        assert "Outstanding failures" in result.error
        assert "Cannot complete issue" in result.output

        # Sprint service should NOT be called
        mock_sprint_service.mark_issue_status.assert_not_called()

    def test_on_output_callback_called(
        self,
        completion_executor: CompletionStepExecutor,
    ) -> None:
        """Test that on_output callback is called when provided."""
        output_lines = []

        def capture_output(line: str) -> None:
            output_lines.append(line)

        # Create issue at COMPLETE_ISSUE step
        current_issue = CurrentIssue(
            schema_version="2.0",
            session_id="2026-01-28T12:00:00Z/complete-issue",
            timestamp="2026-01-28T12:00:00Z",
            sprint_path="./sprints/test/sprint.json",
            issue_id="test-issue-001",
            issue_title="Test issue",
            chunk_type=ChunkType.COMPLETE,
            step=IssueStep.COMPLETE_ISSUE,
            goal="Complete the issue",
            next_action="Mark issue as complete",
            current_failures="",
        )

        # Execute with callback
        completion_executor.execute(current_issue, on_output=capture_output)

        # Verify callback was called
        assert len(output_lines) >= 2  # At least step announcement and completion message
        assert any("Running step" in line for line in output_lines)
        assert any("Issue Complete" in line for line in output_lines)

    def test_output_includes_issue_details(
        self,
        completion_executor: CompletionStepExecutor,
    ) -> None:
        """Test that completion output includes issue ID and title."""
        current_issue = CurrentIssue(
            schema_version="2.0",
            session_id="2026-01-28T12:00:00Z/complete-issue",
            timestamp="2026-01-28T12:00:00Z",
            sprint_path="./sprints/test/sprint.json",
            issue_id="PROJ-123",
            issue_title="Implement user authentication",
            chunk_type=ChunkType.COMPLETE,
            step=IssueStep.COMPLETE_ISSUE,
            goal="Complete the issue",
            next_action="Mark issue as complete",
            current_failures="",
        )

        result = completion_executor.execute(current_issue)

        assert result.success is True
        assert "PROJ-123" in result.output
        assert "Implement user authentication" in result.output
        assert "COMPLETED" in result.output


# --- StepExecutor Abstract Base Class Tests ---


class TestStepExecutorInterface:
    """Tests for StepExecutor abstract base class interface."""

    def test_llm_executor_is_step_executor(
        self,
        llm_executor: LlmStepExecutor,
    ) -> None:
        """Test that LlmStepExecutor is a StepExecutor."""
        assert isinstance(llm_executor, StepExecutor)

    def test_completion_executor_is_step_executor(
        self,
        completion_executor: CompletionStepExecutor,
    ) -> None:
        """Test that CompletionStepExecutor is a StepExecutor."""
        assert isinstance(completion_executor, StepExecutor)

    def test_step_executor_has_execute_method(self) -> None:
        """Test that StepExecutor defines execute method signature."""
        import inspect
        from abc import ABC

        # Verify StepExecutor is abstract
        assert issubclass(StepExecutor, ABC)

        # Verify execute is an abstract method
        assert hasattr(StepExecutor, "execute")
        assert getattr(StepExecutor.execute, "__isabstractmethod__", False)


# --- Edge Cases and Error Handling ---


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_llm_executor_with_empty_output(
        self,
        llm_executor: LlmStepExecutor,
        sample_current_issue: CurrentIssue,
        mock_claude_runner: MagicMock,
    ) -> None:
        """Test handling of empty output from Claude."""
        mock_claude_runner.run_with_content.return_value = ClaudeResult(
            exit_code=0,
            duration_seconds=5,
            timed_out=False,
            rate_limited=False,
            failure_category=FailureCategory.NONE,
            output="",
            error_type=None,
        )

        result = llm_executor.execute(sample_current_issue)

        # Should still succeed with default routing
        assert result.success is True

    def test_llm_executor_subprocess_callbacks(
        self,
        mock_prompt_service: MagicMock,
        mock_claude_runner: MagicMock,
        mock_issue_service: MagicMock,
        mock_models_service: MagicMock,
        default_parse_step_output,
        sample_current_issue: CurrentIssue,
    ) -> None:
        """Test that subprocess callbacks are wired up correctly."""
        on_start_called = []
        on_end_called = []
        on_output_called = []

        executor = LlmStepExecutor(
            prompt_service=mock_prompt_service,
            claude_runner=mock_claude_runner,
            issue_service=mock_issue_service,
            models_service=mock_models_service,
            parse_step_output=default_parse_step_output,
            requires_explicit_signal=set(),
            output_patterns={},
            on_subprocess_start=lambda pid, cmd: on_start_called.append((pid, cmd)),
            on_subprocess_end=lambda: on_end_called.append(True),
            on_subprocess_output=lambda line: on_output_called.append(line),
        )

        # Execute - callbacks should be wired to claude_runner
        executor.execute(sample_current_issue)

        # Verify callbacks were wired (not necessarily called, as that depends on mock)
        assert mock_claude_runner.on_subprocess_start is not None
        assert mock_claude_runner.on_subprocess_end is not None

    def test_llm_executor_on_step_start_callback(
        self,
        mock_prompt_service: MagicMock,
        mock_claude_runner: MagicMock,
        mock_issue_service: MagicMock,
        mock_models_service: MagicMock,
        default_parse_step_output,
        sample_current_issue: CurrentIssue,
    ) -> None:
        """Test that on_step_start callback is called."""
        step_starts = []

        executor = LlmStepExecutor(
            prompt_service=mock_prompt_service,
            claude_runner=mock_claude_runner,
            issue_service=mock_issue_service,
            models_service=mock_models_service,
            parse_step_output=default_parse_step_output,
            requires_explicit_signal=set(),
            output_patterns={},
            on_step_start=lambda step, model: step_starts.append((step, model)),
        )

        executor.execute(sample_current_issue)

        # Verify on_step_start was called
        assert len(step_starts) == 1
        assert step_starts[0][0] == IssueStep.IMPLEMENT
        assert step_starts[0][1] == "sonnet"  # From mock_models_service


# --- Sprint Filtering Tests ---


class TestSprintFiltering:
    """Tests for sprint.json filtering optimization.

    For select-issue step: full sprint is injected (needs all issues).
    For other steps: minimal sprint with only current issue's data.
    """

    def test_full_sprint_injected_for_select_issue(
        self,
        mock_prompt_service: MagicMock,
        mock_claude_runner: MagicMock,
        mock_issue_service: MagicMock,
        mock_models_service: MagicMock,
        default_parse_step_output,
        tmp_path: Path,
    ) -> None:
        """Test that full sprint.json is injected for select-issue step."""
        import json

        # Create a sprint with multiple issues
        sprint_data = {
            "spec_id": "TEST_01",
            "spec_file": ".claudesprint/specs/TEST_01.md",
            "description": "Test sprint",
            "config": {"require_testing": True},
            "git_branch": "sprint/TEST_01",
            "issues": [
                {"id": "issue-1", "title": "First issue", "acceptance_criteria": ["AC1"]},
                {"id": "issue-2", "title": "Second issue", "acceptance_criteria": ["AC2"]},
                {"id": "issue-3", "title": "Third issue", "acceptance_criteria": ["AC3"]},
            ],
            "metadata": {"total_issues": 3},
        }
        sprint_path = tmp_path / "sprint.json"
        sprint_path.write_text(json.dumps(sprint_data))

        # Create CurrentIssue for select-issue step (no issue_id yet)
        current_issue = CurrentIssue(
            schema_version="2.0",
            session_id="2026-01-28T12:00:00Z/select-issue",
            timestamp="2026-01-28T12:00:00Z",
            sprint_path=str(sprint_path),
            issue_id="",  # No issue selected yet
            issue_title="",
            step=IssueStep.SELECT_ISSUE,
            goal="Select next issue",
            next_action="Review issues",
        )

        executor = LlmStepExecutor(
            prompt_service=mock_prompt_service,
            claude_runner=mock_claude_runner,
            issue_service=mock_issue_service,
            models_service=mock_models_service,
            parse_step_output=default_parse_step_output,
            requires_explicit_signal=set(),
            output_patterns={},
        )

        # Build template context
        context = executor._build_template_context(current_issue)

        # Verify full sprint is injected (all 3 issues)
        sprint_json = json.loads(context.sprint_json)
        assert len(sprint_json["issues"]) == 3
        assert sprint_json["issues"][0]["id"] == "issue-1"
        assert sprint_json["issues"][1]["id"] == "issue-2"
        assert sprint_json["issues"][2]["id"] == "issue-3"

    def test_minimal_sprint_injected_for_implement_step(
        self,
        mock_prompt_service: MagicMock,
        mock_claude_runner: MagicMock,
        mock_issue_service: MagicMock,
        mock_models_service: MagicMock,
        default_parse_step_output,
        tmp_path: Path,
    ) -> None:
        """Test that minimal sprint (only current issue) is injected for implement step."""
        import json

        # Create a sprint with multiple issues
        sprint_data = {
            "spec_id": "TEST_01",
            "spec_file": ".claudesprint/specs/TEST_01.md",
            "description": "Test sprint",
            "config": {"require_testing": True, "require_browser_qa": False},
            "git_branch": "sprint/TEST_01",
            "issues": [
                {
                    "id": "issue-1",
                    "title": "First issue",
                    "acceptance_criteria": ["AC1"],
                    "priority": "high",
                },
                {
                    "id": "issue-2",
                    "title": "Second issue",
                    "acceptance_criteria": ["AC2", "AC2b"],
                    "priority": "medium",
                },
                {
                    "id": "issue-3",
                    "title": "Third issue",
                    "acceptance_criteria": ["AC3"],
                    "priority": "low",
                },
            ],
            "metadata": {"total_issues": 3, "pending": 2, "in_progress": 1},
        }
        sprint_path = tmp_path / "sprint.json"
        sprint_path.write_text(json.dumps(sprint_data))

        # Create CurrentIssue for implement step (issue-2 selected)
        current_issue = CurrentIssue(
            schema_version="2.0",
            session_id="2026-01-28T12:00:00Z/implement",
            timestamp="2026-01-28T12:00:00Z",
            sprint_path=str(sprint_path),
            issue_id="issue-2",
            issue_title="Second issue",
            step=IssueStep.IMPLEMENT,
            goal="Implement the feature",
            next_action="Write code",
        )

        executor = LlmStepExecutor(
            prompt_service=mock_prompt_service,
            claude_runner=mock_claude_runner,
            issue_service=mock_issue_service,
            models_service=mock_models_service,
            parse_step_output=default_parse_step_output,
            requires_explicit_signal=set(),
            output_patterns={},
        )

        # Build template context
        context = executor._build_template_context(current_issue)

        # Verify minimal sprint is injected (only current issue)
        sprint_json = json.loads(context.sprint_json)
        assert len(sprint_json["issues"]) == 1
        assert sprint_json["issues"][0]["id"] == "issue-2"
        assert sprint_json["issues"][0]["title"] == "Second issue"
        assert sprint_json["issues"][0]["acceptance_criteria"] == ["AC2", "AC2b"]

        # Verify sprint-level metadata is preserved
        assert sprint_json["spec_id"] == "TEST_01"
        assert sprint_json["config"]["require_testing"] is True
        assert sprint_json["git_branch"] == "sprint/TEST_01"
        assert sprint_json["metadata"]["total_issues"] == 3
        assert sprint_json["metadata"]["note"] == "Filtered to current issue only"

    def test_minimal_sprint_for_all_non_select_steps(
        self,
        mock_prompt_service: MagicMock,
        mock_claude_runner: MagicMock,
        mock_issue_service: MagicMock,
        mock_models_service: MagicMock,
        default_parse_step_output,
        tmp_path: Path,
    ) -> None:
        """Test that minimal sprint is used for various non-select-issue steps."""
        import json

        sprint_data = {
            "spec_id": "TEST_01",
            "spec_file": ".claudesprint/specs/TEST_01.md",
            "description": "Test sprint",
            "config": {},
            "issues": [
                {"id": "issue-1", "title": "First", "acceptance_criteria": ["AC1"]},
                {"id": "issue-2", "title": "Second", "acceptance_criteria": ["AC2"]},
            ],
            "metadata": {"total_issues": 2},
        }
        sprint_path = tmp_path / "sprint.json"
        sprint_path.write_text(json.dumps(sprint_data))

        executor = LlmStepExecutor(
            prompt_service=mock_prompt_service,
            claude_runner=mock_claude_runner,
            issue_service=mock_issue_service,
            models_service=mock_models_service,
            parse_step_output=default_parse_step_output,
            requires_explicit_signal=set(),
            output_patterns={},
        )

        # Test various non-select-issue steps
        steps_to_test = [
            IssueStep.IMPLEMENT,
            IssueStep.WRITE_TESTS,
            IssueStep.RUN_TESTS,
            IssueStep.FIX_TESTS,
            IssueStep.CODE_REVIEW,
            IssueStep.COMMIT_CHANGES,
        ]

        for step in steps_to_test:
            current_issue = CurrentIssue(
                schema_version="2.0",
                session_id=f"2026-01-28T12:00:00Z/{step.value}",
                timestamp="2026-01-28T12:00:00Z",
                sprint_path=str(sprint_path),
                issue_id="issue-1",
                issue_title="First",
                step=step,
                goal="Test goal",
                next_action="Test action",
            )

            context = executor._build_template_context(current_issue)
            sprint_json = json.loads(context.sprint_json)

            assert len(sprint_json["issues"]) == 1, f"Step {step} should have 1 issue"
            assert sprint_json["issues"][0]["id"] == "issue-1"

    def test_fallback_to_full_sprint_if_issue_not_found(
        self,
        mock_prompt_service: MagicMock,
        mock_claude_runner: MagicMock,
        mock_issue_service: MagicMock,
        mock_models_service: MagicMock,
        default_parse_step_output,
        tmp_path: Path,
    ) -> None:
        """Test that full sprint is used if current issue_id is not found in sprint."""
        import json

        sprint_data = {
            "spec_id": "TEST_01",
            "spec_file": ".claudesprint/specs/TEST_01.md",
            "description": "Test sprint",
            "config": {},
            "issues": [
                {"id": "issue-1", "title": "First", "acceptance_criteria": ["AC1"]},
                {"id": "issue-2", "title": "Second", "acceptance_criteria": ["AC2"]},
            ],
            "metadata": {"total_issues": 2},
        }
        sprint_path = tmp_path / "sprint.json"
        sprint_path.write_text(json.dumps(sprint_data))

        # Create CurrentIssue with an issue_id that doesn't exist in sprint
        current_issue = CurrentIssue(
            schema_version="2.0",
            session_id="2026-01-28T12:00:00Z/implement",
            timestamp="2026-01-28T12:00:00Z",
            sprint_path=str(sprint_path),
            issue_id="nonexistent-issue",
            issue_title="Nonexistent",
            step=IssueStep.IMPLEMENT,
            goal="Test goal",
            next_action="Test action",
        )

        executor = LlmStepExecutor(
            prompt_service=mock_prompt_service,
            claude_runner=mock_claude_runner,
            issue_service=mock_issue_service,
            models_service=mock_models_service,
            parse_step_output=default_parse_step_output,
            requires_explicit_signal=set(),
            output_patterns={},
        )

        context = executor._build_template_context(current_issue)
        sprint_json = json.loads(context.sprint_json)

        # Should fall back to full sprint since issue wasn't found
        assert len(sprint_json["issues"]) == 2
