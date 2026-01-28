"""Issue tools for CLI - operates on current_issue.json.

Replaces the old handoff_tools module.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Module-level configuration
_project_dir: Path | None = None


def configure(project_dir: Path) -> None:
    """Configure the issue tools with project directory."""
    global _project_dir
    _project_dir = project_dir


def _get_issue_path() -> Path:
    """Get path to current_issue.json."""
    if _project_dir is None:
        raise RuntimeError("issue_tools not configured. Call configure() first.")
    return _project_dir / "current_issue.json"


def _load_issue() -> dict[str, Any]:
    """Load current_issue.json."""
    path = _get_issue_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _save_issue(data: dict[str, Any]) -> None:
    """Save current_issue.json."""
    path = _get_issue_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


@dataclass
class ToolResult:
    """Result from a tool operation."""

    success: bool
    message: str
    data: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON output."""
        result: dict[str, Any] = {"success": self.success, "message": self.message}
        if self.data is not None:
            result["data"] = self.data
        return result


def get_issue() -> ToolResult:
    """Get current issue state."""
    try:
        data = _load_issue()
        if not data:
            return ToolResult(
                success=False,
                message="No current_issue.json found",
            )
        return ToolResult(
            success=True,
            message="Current issue loaded",
            data=data,
        )
    except Exception as e:
        return ToolResult(success=False, message=f"Failed to load issue: {e}")


def update_issue(
    goal: str | None = None,
    next_action: str | None = None,
) -> ToolResult:
    """Update current issue fields."""
    try:
        data = _load_issue()
        if not data:
            return ToolResult(success=False, message="No current_issue.json found")

        if goal is not None:
            data["goal"] = goal
        if next_action is not None:
            data["next_action"] = next_action

        _save_issue(data)
        return ToolResult(
            success=True,
            message="Issue updated",
            data={"updated_fields": [k for k, v in [("goal", goal), ("next_action", next_action)] if v is not None]},
        )
    except Exception as e:
        return ToolResult(success=False, message=f"Failed to update issue: {e}")


def set_next_step(
    step: str,
    goal: str | None = None,
    next_action: str | None = None,
    clear_failures: bool = False,
) -> ToolResult:
    """Set the next workflow step."""
    try:
        data = _load_issue()
        if not data:
            return ToolResult(success=False, message="No current_issue.json found")

        old_step = data.get("step", "")
        data["step"] = step

        if goal is not None:
            data["goal"] = goal
        if next_action is not None:
            data["next_action"] = next_action
        if clear_failures:
            data["current_failures"] = ""
            data["retry_count"] = 0

        _save_issue(data)
        return ToolResult(
            success=True,
            message=f"Step changed: {old_step} -> {step}",
            data={"old_step": old_step, "new_step": step},
        )
    except Exception as e:
        return ToolResult(success=False, message=f"Failed to set step: {e}")


def record_change(path: str, summary: str) -> ToolResult:
    """Record a file change."""
    try:
        data = _load_issue()
        if not data:
            return ToolResult(success=False, message="No current_issue.json found")

        changes = data.get("changes", [])
        changes.append({"path": path, "summary": summary})
        data["changes"] = changes

        _save_issue(data)
        return ToolResult(
            success=True,
            message=f"Recorded change: {path}",
            data={"path": path, "summary": summary},
        )
    except Exception as e:
        return ToolResult(success=False, message=f"Failed to record change: {e}")


def record_failure(failure_message: str, increment_retry: bool = True) -> ToolResult:
    """Record a failure."""
    try:
        data = _load_issue()
        if not data:
            return ToolResult(success=False, message="No current_issue.json found")

        data["current_failures"] = failure_message
        if increment_retry:
            data["retry_count"] = data.get("retry_count", 0) + 1

        _save_issue(data)
        return ToolResult(
            success=True,
            message="Failure recorded",
            data={"retry_count": data.get("retry_count", 0)},
        )
    except Exception as e:
        return ToolResult(success=False, message=f"Failed to record failure: {e}")


def clear_failures() -> ToolResult:
    """Clear failures and reset retry count."""
    try:
        data = _load_issue()
        if not data:
            return ToolResult(success=False, message="No current_issue.json found")

        data["current_failures"] = ""
        data["retry_count"] = 0

        _save_issue(data)
        return ToolResult(
            success=True,
            message="Failures cleared",
        )
    except Exception as e:
        return ToolResult(success=False, message=f"Failed to clear failures: {e}")


def init_issue(
    issue_id: str,
    step: str = "read-docs",
    goal: str | None = None,
    sprint_path: str | None = None,
) -> ToolResult:
    """Initialize current_issue.json for a selected issue.

    This creates or overwrites current_issue.json with fresh state for the selected issue.
    Used by select-issue step to persist the issue selection.

    Args:
        issue_id: ID of the selected issue
        step: Initial step (default: read-docs)
        goal: Optional goal description
        sprint_path: Optional path to sprint.json (will try to discover if not provided)

    Returns:
        ToolResult with success status
    """
    from datetime import datetime, UTC

    try:
        # Try to load existing issue to get sprint_path if not provided
        if sprint_path is None:
            existing = _load_issue()
            if existing and "sprint_path" in existing:
                sprint_path = existing["sprint_path"]
            else:
                # Try to find sprint.json in standard locations
                if _project_dir is None:
                    return ToolResult(
                        success=False,
                        message="Cannot init: no sprint_path provided and no existing issue to get it from",
                    )
                # Walk up to find .claudesprint/sprints/
                project_root = _project_dir.parent.parent  # .claudesprint/project -> .claudesprint -> project_root
                sprints_dir = project_root / ".claudesprint" / "sprints"
                if sprints_dir.exists():
                    # Find first sprint.json
                    for sprint_dir in sprints_dir.iterdir():
                        if sprint_dir.is_dir():
                            sprint_json = sprint_dir / "sprint.json"
                            if sprint_json.exists():
                                sprint_path = str(sprint_json)
                                break

        if sprint_path is None:
            return ToolResult(
                success=False,
                message="Cannot init: could not determine sprint_path",
            )

        # Create fresh current_issue data
        timestamp = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        session_id = f"{timestamp}/{step}"

        data = {
            "schema_version": "2.0",
            "sprint_path": sprint_path,
            "issue_id": issue_id,
            "issue_title": "",  # Will be populated by engine or agent
            "step": step,
            "chunk_type": "IMPLEMENT",
            "goal": goal or f"Begin work on issue {issue_id}",
            "next_action": f"Read documentation and understand requirements",
            "context": {},
            "changes": [],
            "current_failures": "",
            "retry_count": 0,
            "total_iterations": 0,
            "session_id": session_id,
            "repo_state": {"head_sha": "", "is_dirty": False},
            "log_tail": "",
        }

        _save_issue(data)

        return ToolResult(
            success=True,
            message=f"Initialized current_issue.json for {issue_id} at step {step}",
            data={"issue_id": issue_id, "step": step, "sprint_path": sprint_path},
        )
    except Exception as e:
        return ToolResult(success=False, message=f"Failed to init issue: {e}")
