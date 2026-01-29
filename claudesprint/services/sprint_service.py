"""Sprint service for sprint file operations."""

import json
import logging
from pathlib import Path

from pydantic import ValidationError

from claudesprint.models.sprint import Sprint, Issue, IssueStatus

logger = logging.getLogger(__name__)


class SprintService:
    """Service for sprint file I/O and management operations."""

    def __init__(self, sprints_dir: str | Path = Path(".claudesprint/sprints")) -> None:
        """Initialize SprintService.

        Args:
            sprints_dir: Base directory for sprint files (default: .claudesprint/sprints)
        """
        self.sprints_dir = Path(sprints_dir)

    def get_sprint_path(self, spec_id: str) -> Path:
        """Get the path to a sprint.json file for a given spec_id.

        Args:
            spec_id: The spec identifier (e.g., SPEC_01)

        Returns:
            Path to the sprint.json file (e.g., .claudesprint/sprints/SPEC_01/sprint.json)
        """
        return self.sprints_dir / spec_id / "sprint.json"

    def get_sprint_dir(self, spec_id: str) -> Path:
        """Get the directory for a sprint.

        Args:
            spec_id: The spec identifier (e.g., SPEC_01)

        Returns:
            Path to the sprint directory (e.g., .claudesprint/sprints/SPEC_01)
        """
        return self.sprints_dir / spec_id

    def derive_spec_id(self, spec_file: str | Path) -> str:
        """Derive spec_id from a spec file path.

        Args:
            spec_file: Path to the spec file (e.g., .claudesprint/specs/SPEC_01.md)

        Returns:
            Derived spec_id (e.g., SPEC_01)
        """
        path = Path(spec_file)
        # Remove extension and use the stem
        return path.stem

    def read_sprint(self, path: str | Path) -> Sprint | None:
        """Read and parse a sprint.json file.

        Args:
            path: Path to the sprint.json file

        Returns:
            Sprint model or None if not found/invalid
        """
        file_path = Path(path)
        if not file_path.exists():
            return None
        try:
            data = json.loads(file_path.read_text())
            return Sprint.model_validate(data)
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in sprint file {file_path}: {e}")
            return None
        except ValidationError as e:
            logger.warning(f"Invalid sprint data in {file_path}: {e}")
            return None
        except OSError as e:
            logger.warning(f"Failed to read sprint file {file_path}: {e}")
            return None

    def write_sprint(self, sprint: Sprint, path: str | Path) -> bool:
        """Write a sprint to a sprint.json file atomically.

        Args:
            sprint: Sprint model to write
            path: Path to the sprint.json file

        Returns:
            True if successful, False otherwise
        """
        file_path = Path(path)
        try:
            # Ensure parent directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Update last_modified
            sprint.update_last_modified()

            # Write to temp file first
            temp_file = file_path.with_suffix(".tmp.json")
            content = sprint.model_dump_json(indent=2, by_alias=True)
            temp_file.write_text(content)

            # Atomic rename
            temp_file.rename(file_path)
            return True
        except OSError as e:
            logger.warning(f"Failed to write sprint file {file_path}: {e}")
            return False

    def is_sprint_valid(self, path: str | Path) -> bool:
        """Check if a sprint.json exists and is valid JSON with required structure.

        Args:
            path: Path to the sprint.json file

        Returns:
            True if valid, False otherwise
        """
        file_path = Path(path)
        if not file_path.exists():
            return False
        try:
            data = json.loads(file_path.read_text())
            # Basic structure check
            return (
                isinstance(data, dict)
                and "issues" in data
                and isinstance(data["issues"], list)
                and "spec_id" in data
            )
        except json.JSONDecodeError as e:
            logger.debug(f"Invalid JSON in sprint file {file_path}: {e}")
            return False
        except OSError as e:
            logger.debug(f"Failed to read sprint file {file_path}: {e}")
            return False

    def get_available_issues(self, sprint: Sprint) -> list[Issue]:
        """Get all pending issues that can be worked on.

        Args:
            sprint: Sprint model

        Returns:
            List of available issues (pending, not blocked)
        """
        return sprint.get_available_issues()

    def get_issue(self, sprint: Sprint, issue_id: str) -> Issue | None:
        """Get an issue by ID from a sprint.

        Args:
            sprint: Sprint model
            issue_id: Issue ID to find

        Returns:
            Issue or None if not found
        """
        return sprint.get_issue(issue_id)

    def mark_issue_status(
        self,
        path: str | Path,
        issue_id: str,
        status: IssueStatus,
        session_id: str | None = None,
    ) -> bool:
        """Mark an issue's status in a sprint.

        Args:
            path: Path to the sprint.json file
            issue_id: Issue ID to update
            status: New status to set
            session_id: Optional session ID for history

        Returns:
            True if successful, False otherwise
        """
        sprint = self.read_sprint(path)
        if not sprint:
            return False

        issue = sprint.get_issue(issue_id)
        if not issue:
            return False

        old_status = issue.status
        issue.status = status
        issue.add_history(
            f"Status changed: {old_status} -> {status}",
            session_id=session_id,
        )

        return self.write_sprint(sprint, path)

    def list_sprints(self) -> list[Path]:
        """List all sprint.json files in the sprints directory.

        Returns:
            List of paths to sprint.json files
        """
        if not self.sprints_dir.exists():
            return []

        sprints = []
        for sprint_dir in self.sprints_dir.iterdir():
            if sprint_dir.is_dir():
                sprint_file = sprint_dir / "sprint.json"
                if sprint_file.exists():
                    sprints.append(sprint_file)

        return sorted(sprints)

    def get_active_sprint(self) -> tuple[Path | None, Sprint | None]:
        """Find the first sprint with pending or in-progress issues.

        Returns:
            Tuple of (path, sprint) or (None, None) if no active sprint
        """
        for sprint_path in self.list_sprints():
            sprint = self.read_sprint(sprint_path)
            if sprint and not sprint.is_complete():
                return sprint_path, sprint
        return None, None

    def create_sprint_from_spec(
        self,
        spec_file: str | Path,
        description: str = "",
    ) -> tuple[Path, Sprint]:
        """Create a new sprint from a spec file.

        Args:
            spec_file: Path to the spec file
            description: Optional sprint description

        Returns:
            Tuple of (sprint_path, sprint)
        """
        spec_id = self.derive_spec_id(spec_file)
        sprint = Sprint.create_initial(
            spec_id=spec_id,
            spec_file=str(spec_file),
            description=description,
        )
        sprint_path = self.get_sprint_path(spec_id)
        return sprint_path, sprint
