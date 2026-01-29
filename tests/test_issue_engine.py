"""Tests for IssueEngine - specifically max_total_iterations feature."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from claudesprint.core.issue_engine import IssueEngine, IssueExitReason, StepResult
from claudesprint.models.config import ClaudesprintConfig
from claudesprint.models.current_issue import CurrentIssue, ChunkType, IssueStep
from claudesprint.models.sprint import ResolvedConfig


@pytest.fixture
def mock_config(tmp_path: Path) -> ClaudesprintConfig:
    """Create a minimal config for testing."""
    return ClaudesprintConfig(
        project_dir=str(tmp_path),
        max_retry=3,
        max_total_iterations=5,  # Low limit for testing
        claude_timeout=60,
    )


@pytest.fixture
def mock_execution_config() -> ResolvedConfig:
    """Create a minimal execution config."""
    return ResolvedConfig(
        require_testing=False,
        require_browser_qa=False,
    )


@pytest.fixture
def sample_current_issue() -> CurrentIssue:
    """Create a sample CurrentIssue for testing."""
    return CurrentIssue(
        schema_version="2.0",
        session_id="2026-01-28T12:00:00Z/implement",
        timestamp="2026-01-28T12:00:00Z",
        sprint_path="./sprints/test/sprint.json",
        issue_id="test-issue-001",
        issue_title="Test issue",
        chunk_type=ChunkType.IMPLEMENT,
        step=IssueStep.IMPLEMENT,
        goal="Test goal",
        next_action="Test action",
        total_iterations=0,
    )


class TestMaxTotalIterations:
    """Tests for the max_total_iterations infinite loop prevention feature."""

    def test_max_iterations_exit_when_limit_reached(
        self, tmp_path: Path, mock_config: ClaudesprintConfig, mock_execution_config: ResolvedConfig
    ) -> None:
        """Engine exits with MAX_ITERATIONS when total_iterations reaches limit."""
        # Create issue that's already at the limit
        current_issue = CurrentIssue(
            schema_version="2.0",
            session_id="2026-01-28T12:00:00Z/implement",
            timestamp="2026-01-28T12:00:00Z",
            sprint_path="./sprints/test/sprint.json",
            issue_id="test-issue-001",
            issue_title="Test issue",
            chunk_type=ChunkType.IMPLEMENT,
            step=IssueStep.IMPLEMENT,
            goal="Test goal",
            next_action="Test action",
            total_iterations=5,  # Already at limit (max_total_iterations=5)
        )

        with patch.object(IssueEngine, "__init__", lambda self, *args, **kwargs: None):
            engine = IssueEngine.__new__(IssueEngine)
            engine.config = mock_config
            engine.notification_service = MagicMock()

            result = engine.run(current_issue)

        assert result.exit_reason == IssueExitReason.MAX_ITERATIONS
        assert result.issue_id == "test-issue-001"
        assert "max total iterations" in result.message.lower()
        assert "infinite loop" in result.error.lower()
        engine.notification_service.notify_failure.assert_called_once()

    def test_total_iterations_increments_after_step_execution(
        self, tmp_path: Path, mock_config: ClaudesprintConfig, mock_execution_config: ResolvedConfig
    ) -> None:
        """total_iterations is incremented after each step execution."""
        current_issue = CurrentIssue(
            schema_version="2.0",
            session_id="2026-01-28T12:00:00Z/implement",
            timestamp="2026-01-28T12:00:00Z",
            sprint_path="./sprints/test/sprint.json",
            issue_id="test-issue-001",
            issue_title="Test issue",
            chunk_type=ChunkType.IMPLEMENT,
            step=IssueStep.COMPLETE_ISSUE,  # Final step - will exit after one iteration
            goal="Test goal",
            next_action="Test action",
            total_iterations=0,
        )

        with patch.object(IssueEngine, "__init__", lambda self, *args, **kwargs: None):
            engine = IssueEngine.__new__(IssueEngine)
            engine.config = mock_config
            engine.notification_service = MagicMock()
            engine.issue_service = MagicMock()
            engine.event_bus = None

            # Mock _execute_step to return success with no next step (complete)
            engine._execute_step = MagicMock(
                return_value=StepResult(
                    success=True,
                    next_step=None,  # Signals completion
                    output="Done",
                )
            )
            # Mock _should_skip_step to return False
            engine._should_skip_step = MagicMock(return_value=False)
            # Mock _transition_step
            engine._transition_step = MagicMock()

            result = engine.run(current_issue)

        assert result.exit_reason == IssueExitReason.COMPLETED
        assert current_issue.total_iterations == 1
        # Verify it was persisted
        engine.issue_service.write_current_issue.assert_called()

    def test_total_iterations_persisted_immediately(
        self, tmp_path: Path, mock_config: ClaudesprintConfig, mock_execution_config: ResolvedConfig
    ) -> None:
        """total_iterations is persisted immediately after incrementing."""
        current_issue = CurrentIssue(
            schema_version="2.0",
            session_id="2026-01-28T12:00:00Z/implement",
            timestamp="2026-01-28T12:00:00Z",
            sprint_path="./sprints/test/sprint.json",
            issue_id="test-issue-001",
            issue_title="Test issue",
            chunk_type=ChunkType.IMPLEMENT,
            step=IssueStep.COMPLETE_ISSUE,
            goal="Test goal",
            next_action="Test action",
            total_iterations=0,
        )

        persisted_iterations = []

        def capture_write(issue: CurrentIssue) -> bool:
            persisted_iterations.append(issue.total_iterations)
            return True

        with patch.object(IssueEngine, "__init__", lambda self, *args, **kwargs: None):
            engine = IssueEngine.__new__(IssueEngine)
            engine.config = mock_config
            engine.notification_service = MagicMock()
            engine.issue_service = MagicMock()
            engine.issue_service.write_current_issue = capture_write
            engine.event_bus = None

            engine._execute_step = MagicMock(
                return_value=StepResult(success=True, next_step=None, output="Done")
            )
            engine._should_skip_step = MagicMock(return_value=False)
            engine._transition_step = MagicMock()

            engine.run(current_issue)

        # Verify the incremented value was persisted
        assert 1 in persisted_iterations

    def test_iterations_accumulate_across_multiple_steps(
        self, tmp_path: Path, mock_config: ClaudesprintConfig, mock_execution_config: ResolvedConfig
    ) -> None:
        """total_iterations accumulates across multiple step executions."""
        current_issue = CurrentIssue(
            schema_version="2.0",
            session_id="2026-01-28T12:00:00Z/implement",
            timestamp="2026-01-28T12:00:00Z",
            sprint_path="./sprints/test/sprint.json",
            issue_id="test-issue-001",
            issue_title="Test issue",
            chunk_type=ChunkType.IMPLEMENT,
            step=IssueStep.IMPLEMENT,
            goal="Test goal",
            next_action="Test action",
            total_iterations=2,  # Start with 2 already done
        )

        step_count = [0]

        def mock_execute_step(issue: CurrentIssue) -> StepResult:
            step_count[0] += 1
            if step_count[0] >= 2:
                return StepResult(success=True, next_step=None, output="Done")
            return StepResult(success=True, next_step=IssueStep.COMPLETE_ISSUE, output="Continue")

        with patch.object(IssueEngine, "__init__", lambda self, *args, **kwargs: None):
            engine = IssueEngine.__new__(IssueEngine)
            engine.config = mock_config
            engine.notification_service = MagicMock()
            engine.issue_service = MagicMock()
            engine.issue_service.write_current_issue = MagicMock(return_value=True)
            engine.event_bus = None

            engine._execute_step = mock_execute_step
            engine._should_skip_step = MagicMock(return_value=False)
            engine._transition_step = MagicMock()

            result = engine.run(current_issue)

        assert result.exit_reason == IssueExitReason.COMPLETED
        # Started at 2, ran 2 more steps = 4
        assert current_issue.total_iterations == 4

    def test_max_iterations_prevents_infinite_loop(
        self, tmp_path: Path, mock_config: ClaudesprintConfig, mock_execution_config: ResolvedConfig
    ) -> None:
        """max_total_iterations prevents infinite loops between steps."""
        current_issue = CurrentIssue(
            schema_version="2.0",
            session_id="2026-01-28T12:00:00Z/implement",
            timestamp="2026-01-28T12:00:00Z",
            sprint_path="./sprints/test/sprint.json",
            issue_id="test-issue-001",
            issue_title="Test issue",
            chunk_type=ChunkType.IMPLEMENT,
            step=IssueStep.RUN_TESTS,
            goal="Test goal",
            next_action="Test action",
            total_iterations=0,
        )

        # Simulate infinite loop: RUN_TESTS -> FIX_TESTS -> RUN_TESTS -> ...
        def mock_execute_step(issue: CurrentIssue) -> StepResult:
            if issue.step == IssueStep.RUN_TESTS:
                return StepResult(success=True, next_step=IssueStep.FIX_TESTS, output="fail_test")
            else:  # FIX_TESTS
                return StepResult(success=True, next_step=IssueStep.RUN_TESTS, output="test_fixed")

        with patch.object(IssueEngine, "__init__", lambda self, *args, **kwargs: None):
            engine = IssueEngine.__new__(IssueEngine)
            engine.config = mock_config
            engine.notification_service = MagicMock()
            engine.issue_service = MagicMock()
            engine.issue_service.write_current_issue = MagicMock(return_value=True)
            engine.event_bus = None

            engine._execute_step = mock_execute_step
            engine._should_skip_step = MagicMock(return_value=False)
            engine._transition_step = MagicMock()

            result = engine.run(current_issue)

        # Should exit with MAX_ITERATIONS, not run forever
        assert result.exit_reason == IssueExitReason.MAX_ITERATIONS
        assert current_issue.total_iterations == 5  # Reached the limit


class TestTotalIterationsModel:
    """Tests for total_iterations field in CurrentIssue model."""

    def test_total_iterations_default_is_zero(self) -> None:
        """total_iterations defaults to 0."""
        issue = CurrentIssue(
            schema_version="2.0",
            session_id="2026-01-28T12:00:00Z/implement",
            timestamp="2026-01-28T12:00:00Z",
            sprint_path="./sprint.json",
            issue_id="test-001",
            issue_title="Test",
            chunk_type=ChunkType.IMPLEMENT,
            step=IssueStep.IMPLEMENT,
            goal="Goal",
            next_action="Action",
        )
        assert issue.total_iterations == 0

    def test_total_iterations_reset_on_create_initial(self) -> None:
        """total_iterations is reset to 0 when creating via create_initial()."""
        issue = CurrentIssue.create_initial(sprint_path="./sprint.json")
        assert issue.total_iterations == 0


class TestMaxTotalIterationsConfig:
    """Tests for max_total_iterations configuration."""

    def test_max_total_iterations_default(self) -> None:
        """max_total_iterations defaults to 50."""
        config = ClaudesprintConfig()
        assert config.max_total_iterations == 50

    def test_max_total_iterations_custom_value(self) -> None:
        """max_total_iterations can be set to a custom value."""
        config = ClaudesprintConfig(max_total_iterations=100)
        assert config.max_total_iterations == 100

    def test_max_total_iterations_minimum_is_one(self) -> None:
        """max_total_iterations must be at least 1."""
        with pytest.raises(ValueError):
            ClaudesprintConfig(max_total_iterations=0)

    def test_max_total_iterations_from_env(self, monkeypatch) -> None:
        """max_total_iterations can be set via environment variable."""
        monkeypatch.setenv("CLAUDESPRINT_MAX_TOTAL_ITERATIONS", "75")
        config = ClaudesprintConfig()
        assert config.max_total_iterations == 75
