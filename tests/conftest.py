"""Pytest configuration and fixtures for ClaudeSprint."""

import json
import tempfile
from pathlib import Path

import pytest

from claudesprint.models.config import ClaudesprintConfig
from claudesprint.models.sprint import Sprint, Issue, IssueStatus, IssuePriority
from claudesprint.models.current_issue import CurrentIssue, ChunkType, IssueStep


@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        claude_dir = project_root / ".claude"
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
        "rationale": [],
        "retry_count": 0,
    }


@pytest.fixture
def config(temp_project_dir):
    """Create a ClaudesprintConfig for testing."""
    return ClaudesprintConfig.from_project_root(str(temp_project_dir))
