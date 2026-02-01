"""Pytest configuration and fixtures for ClaudeSprint."""

import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

# Import service and engine classes for Mock specs
from claudesprint.core.claude_runner import ClaudeRunner
from claudesprint.core.issue_engine import IssueEngine
from claudesprint.models.config import ClaudesprintConfig
from claudesprint.models.current_issue import ChunkType, CurrentIssue, IssueStep
from claudesprint.models.sprint import Issue, IssuePriority, IssueStatus, ResolvedConfig, Sprint
from claudesprint.services.git_service import GitService
from claudesprint.services.issue_service import IssueService
from claudesprint.services.notification_service import NotificationService
from claudesprint.services.prompt_service import PromptService
from claudesprint.services.sprint_service import SprintService


@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        project_root / ".claude"
        claudesprint_dir = project_root / ".claudesprint"
        project_dir = claudesprint_dir / "project"
        prompts_dir = claudesprint_dir / "prompts"
        schemas_dir = claudesprint_dir / "schemas"
        config_dir = claudesprint_dir / "config"
        sprints_dir = claudesprint_dir / "sprints"
        specs_dir = claudesprint_dir / "specs"

        # Create directories
        project_dir.mkdir(parents=True)
        prompts_dir.mkdir(parents=True)
        schemas_dir.mkdir(parents=True)
        config_dir.mkdir(parents=True)
        sprints_dir.mkdir(parents=True)
        specs_dir.mkdir(parents=True)

        yield project_root


@pytest.fixture
def sample_issue():
    """Create a sample Issue object."""
    return Issue(
        id="issue-001",
        title="Test issue",
        status=IssueStatus.PENDING,
        priority=IssuePriority.HIGH,
        acceptance_criteria=["Criterion 1", "Criterion 2"],
    )


@pytest.fixture
def sample_sprint(sample_issue):
    """Create a sample Sprint object."""
    return Sprint(
        schema_version="2.0",
        spec_id="SPEC_01",
        spec_file=".claudesprint/specs/SPEC_01.md",
        description="Test sprint",
        issues=[sample_issue],
    )


@pytest.fixture
def sample_sprint_dict():
    """Create a sample sprint dictionary."""
    return {
        "schema_version": "2.0",
        "spec_id": "SPEC_01",
        "spec_file": ".claudesprint/specs/SPEC_01.md",
        "description": "Test sprint",
        "issues": [
            {
                "id": "issue-001",
                "title": "Test issue",
                "status": "pending",
                "priority": "high",
                "acceptance_criteria": ["Criterion 1"],
            }
        ],
        "config": {
            "require_testing": True,
            "require_browser_qa": False,
        },
        "created_at": "2026-01-22T12:00:00Z",
        "metadata": {
            "total_issues": 1,
            "pending": 1,
            "in_progress": 0,
            "completed": 0,
            "blocked": 0,
        },
    }


@pytest.fixture
def sample_current_issue():
    """Create a sample CurrentIssue object."""
    return CurrentIssue(
        schema_version="2.0",
        session_id="2026-01-22T12:00:00Z/implement",
        timestamp="2026-01-22T12:00:00Z",
        sprint_path="./sprints/SPEC_01/sprint.json",
        issue_id="issue-001",
        issue_title="Test issue",
        chunk_type=ChunkType.IMPLEMENT,
        step=IssueStep.IMPLEMENT,
        goal="Implement the test issue",
        next_action="Write the implementation code",
    )


@pytest.fixture
def sample_current_issue_dict():
    """Create a sample current_issue dictionary."""
    return {
        "schema_version": "2.0",
        "session_id": "2026-01-22T12:00:00Z/implement",
        "timestamp": "2026-01-22T12:00:00Z",
        "sprint_path": "./sprints/SPEC_01/sprint.json",
        "issue_id": "issue-001",
        "issue_title": "Test issue",
        "chunk_type": "implement",
        "step": "implement",
        "goal": "Implement the test issue",
        "next_action": "Write the implementation code",
        "repo_state": {"git_head": "abc123", "dirty": False},
        "changes": [],
        "commands_run": [],
        "current_failures": "",
        "retry_count": 0,
    }


@pytest.fixture
def config(temp_project_dir):
    """Create a ClaudesprintConfig for testing."""
    return ClaudesprintConfig.from_project_root(str(temp_project_dir))


# =============================================================================
# Dependency Injection Mock Fixtures
# =============================================================================
# These fixtures provide mock objects for all services and engines, enabling
# isolated unit testing without file system, network, or subprocess operations.


@pytest.fixture
def mock_claude_runner():
    """Mock ClaudeRunner for testing without running actual Claude CLI.

    The mock has the same interface as ClaudeRunner, allowing tests to
    control responses and verify method calls without subprocess execution.

    Example:
        def test_something(mock_claude_runner):
            from claudesprint.core.claude_runner import ClaudeResult, FailureCategory
            mock_claude_runner.run_prompt.return_value = ClaudeResult(
                exit_code=0,
                duration_seconds=10,
                timed_out=False,
                rate_limited=False,
                output="Test output",
                failure_category=FailureCategory.NONE,
            )
    """
    return Mock(spec=ClaudeRunner)


@pytest.fixture
def mock_issue_service():
    """Mock IssueService for testing without file system operations.

    Provides isolated testing of components that depend on IssueService
    without actually reading/writing current_issue.json or logs.

    Example:
        def test_something(mock_issue_service):
            mock_issue_service.read_current_issue.return_value = sample_current_issue
            mock_issue_service.write_current_issue.return_value = True
    """
    return Mock(spec=IssueService)


@pytest.fixture
def mock_sprint_service():
    """Mock SprintService for testing without file system operations.

    Enables testing sprint-related operations without reading/writing
    sprint.json files.

    Example:
        def test_something(mock_sprint_service, sample_sprint):
            mock_sprint_service.read_sprint.return_value = sample_sprint
            mock_sprint_service.write_sprint.return_value = True
    """
    return Mock(spec=SprintService)


@pytest.fixture
def mock_notification_service():
    """Mock NotificationService for testing without network calls.

    Allows testing notification triggers without actual HTTP requests
    to the Bark notification service.

    Example:
        def test_something(mock_notification_service):
            # Run code that should trigger notifications
            mock_notification_service.notify_step.assert_called_once()
    """
    return Mock(spec=NotificationService)


@pytest.fixture
def mock_git_service():
    """Mock GitService for testing without actual git operations.

    Provides controlled git behavior for tests without requiring
    a real git repository or executing git commands.

    Example:
        def test_something(mock_git_service):
            mock_git_service.is_repo.return_value = True
            mock_git_service.get_current_branch.return_value = "feature/test"
            mock_git_service.create_branch.return_value = (True, "Created branch")
    """
    return Mock(spec=GitService)


@pytest.fixture
def mock_prompt_service():
    """Mock PromptService for testing without loading prompt files.

    Enables testing prompt-dependent code without file system access
    or Jinja2 template rendering.

    Example:
        def test_something(mock_prompt_service):
            mock_prompt_service.get_prompt_content.return_value = "Test prompt content"
            mock_prompt_service.prompt_exists.return_value = True
    """
    return Mock(spec=PromptService)


@pytest.fixture
def mock_issue_engine():
    """Mock IssueEngine for testing without running the inner loop.

    Useful for testing SprintEngine or other components that use IssueEngine
    without executing the actual workflow steps.

    Example:
        def test_something(mock_issue_engine):
            from claudesprint.core.issue_engine import IssueResult, IssueExitReason
            mock_issue_engine.run.return_value = IssueResult(
                exit_reason=IssueExitReason.COMPLETED,
                issue_id="issue-001",
                steps_completed=5,
                elapsed_seconds=120,
                final_step=IssueStep.COMPLETE_ISSUE,
                message="Issue completed successfully",
            )
    """
    return Mock(spec=IssueEngine)


@pytest.fixture
def mock_issue_engine_factory(mock_issue_engine):
    """Mock factory that returns mock IssueEngine instances.

    This fixture is used by SprintEngine to create IssueEngine instances
    for each issue. The factory pattern allows SprintEngine to create
    engines with issue-specific ResolvedConfig.

    Example:
        def test_sprint_engine(mock_issue_engine_factory, mock_issue_engine):
            # The factory returns the same mock for all calls
            engine = mock_issue_engine_factory(some_resolved_config)
            assert engine is mock_issue_engine

    Args:
        mock_issue_engine: The mock IssueEngine to return (auto-injected)

    Returns:
        A factory function that takes ResolvedConfig and returns a mock IssueEngine
    """
    def factory(resolved_config: ResolvedConfig) -> Mock:  # noqa: ARG001
        return mock_issue_engine
    return factory


@pytest.fixture
def sample_resolved_config():
    """Create a sample ResolvedConfig for testing.

    ResolvedConfig contains the resolved execution gates for a specific issue,
    merging sprint-level defaults with issue-level overrides.

    Example:
        def test_something(sample_resolved_config):
            # Use in IssueEngine or SprintEngine tests
            engine = IssueEngine(
                config=config,
                execution_config=sample_resolved_config,
                ...
            )
    """
    return ResolvedConfig(
        require_testing=True,
        require_browser_qa=False,
    )
