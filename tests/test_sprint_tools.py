"""Tests for sprint_tools module."""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from claudesprint.tools import sprint_tools
from claudesprint.models.sprint import Sprint, Issue, IssueStatus, IssuePriority


@pytest.fixture
def sprints_dir(tmp_path: Path) -> Path:
    """Create a temporary sprints directory."""
    sprints = tmp_path / "sprints"
    sprints.mkdir()
    return sprints


@pytest.fixture
def sample_sprint_data() -> dict:
    """Create sample sprint data."""
    return {
        "spec_id": "TEST_SPEC",
        "spec_file": "specs/TEST_SPEC.md",
        "description": "Test sprint",
        "issues": [
            {
                "id": "issue-1",
                "title": "First issue",
                "status": "pending",
                "priority": "high",
                "acceptance_criteria": ["AC1"],
                "dependencies": [],
            },
            {
                "id": "issue-2",
                "title": "Second issue",
                "status": "pending",
                "priority": "medium",
                "acceptance_criteria": ["AC2"],
                "dependencies": ["issue-1"],
            },
            {
                "id": "issue-3",
                "title": "Completed issue",
                "status": "completed",
                "priority": "low",
                "acceptance_criteria": ["AC3"],
                "dependencies": [],
            },
            {
                "id": "issue-4",
                "title": "In progress issue",
                "status": "in_progress",
                "priority": "high",
                "acceptance_criteria": ["AC4"],
                "dependencies": [],
            },
        ],
        "metadata": {"total_issues": 4, "completed": 1},
    }


@pytest.fixture
def setup_sprint(sprints_dir: Path, sample_sprint_data: dict) -> Path:
    """Set up a sprint directory with sprint.json."""
    spec_dir = sprints_dir / "TEST_SPEC"
    spec_dir.mkdir()
    sprint_path = spec_dir / "sprint.json"
    sprint_path.write_text(json.dumps(sample_sprint_data, indent=2))

    # Configure sprint_tools
    sprint_tools.configure(sprints_dir)
    return sprint_path


class TestStartIssue:
    """Tests for start_issue function."""

    def test_start_pending_issue_success(self, setup_sprint: Path) -> None:
        """Test successfully starting a pending issue."""
        result = sprint_tools.start_issue("issue-1", spec_id="TEST_SPEC")

        assert result.success is True
        assert "Started issue issue-1" in result.message
        assert result.data["issue_id"] == "issue-1"
        assert result.data["status"] == "in_progress"

    def test_start_issue_already_in_progress(self, setup_sprint: Path) -> None:
        """Test starting an issue that's already in progress."""
        result = sprint_tools.start_issue("issue-4", spec_id="TEST_SPEC")

        assert result.success is True
        assert "already in progress" in result.message
        assert result.data["issue_id"] == "issue-4"

    def test_start_completed_issue_fails(self, setup_sprint: Path) -> None:
        """Test that starting a completed issue fails."""
        result = sprint_tools.start_issue("issue-3", spec_id="TEST_SPEC")

        assert result.success is False
        assert "already completed" in result.message

    def test_start_issue_not_found(self, setup_sprint: Path) -> None:
        """Test starting a non-existent issue."""
        result = sprint_tools.start_issue("nonexistent", spec_id="TEST_SPEC")

        assert result.success is False
        assert "Issue not found" in result.message

    def test_start_issue_blocked_by_dependencies(self, setup_sprint: Path) -> None:
        """Test that starting an issue with unmet dependencies fails."""
        result = sprint_tools.start_issue("issue-2", spec_id="TEST_SPEC")

        assert result.success is False
        assert "blocked by incomplete dependencies" in result.message
        assert "issue-1" in result.message

    def test_start_issue_sprint_not_found(self, sprints_dir: Path) -> None:
        """Test starting an issue when sprint doesn't exist."""
        sprint_tools.configure(sprints_dir)
        result = sprint_tools.start_issue("issue-1", spec_id="NONEXISTENT")

        assert result.success is False
        assert "Sprint not found" in result.message

    def test_start_issue_no_active_sprint(self, sprints_dir: Path) -> None:
        """Test starting an issue when no active sprint exists."""
        sprint_tools.configure(sprints_dir)
        result = sprint_tools.start_issue("issue-1")  # No spec_id

        assert result.success is False
        assert "No active sprint" in result.message

    def test_start_issue_updates_sprint_file(self, setup_sprint: Path) -> None:
        """Test that starting an issue updates the sprint.json file."""
        sprint_tools.start_issue("issue-1", spec_id="TEST_SPEC")

        # Read the sprint file and verify status was updated
        sprint_data = json.loads(setup_sprint.read_text())
        issue = next(i for i in sprint_data["issues"] if i["id"] == "issue-1")
        assert issue["status"] == "in_progress"
