"""Issue tools for CLI - operates on current_issue.json.

Replaces the old handoff_tools module.

This module provides atomic writes and file locking to prevent race conditions
when multiple processes access current_issue.json concurrently.
"""

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from claudesprint.utils.issue_lock import IssueLock, get_issue_lock

# Module-level configuration
_project_dir: Path | None = None
_issue_lock: IssueLock | None = None


def configure(project_dir: Path) -> None:
    """Configure the issue tools with project directory and lock."""
    global _project_dir, _issue_lock
    _project_dir = project_dir
    _issue_lock = get_issue_lock(project_dir)


def _get_issue_path() -> Path:
    """Get path to current_issue.json."""
    if _project_dir is None:
        raise RuntimeError("issue_tools not configured. Call configure() first.")
    return _project_dir / "current_issue.json"


def _get_lock() -> IssueLock:
    """Get the issue lock instance."""
    if _issue_lock is None:
        raise RuntimeError("issue_tools not configured. Call configure() first.")
    return _issue_lock


def _load_issue() -> dict[str, Any]:
    """Load current_issue.json (caller must hold lock)."""
    path = _get_issue_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _save_issue_atomic(data: dict[str, Any]) -> None:
    """Save current_issue.json atomically using temp file + rename.

    Uses a temporary file in the same directory then renames to ensure
    the write is atomic and won't leave corrupted JSON on crash.

    Caller must hold the lock.
    """
    path = _get_issue_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    # Write to temp file in same directory (ensures same filesystem for rename)
    fd, temp_path = tempfile.mkstemp(
        suffix=".tmp.json",
        dir=path.parent,
        prefix=".current_issue_"
    )
    temp_file = Path(temp_path)
    try:
        # Write content
        content = json.dumps(data, indent=2) + "\n"
        os.write(fd, content.encode())
        os.close(fd)
        fd = -1  # Mark as closed

        # Atomic rename
        temp_file.rename(path)
    finally:
        # Clean up on failure
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass
        if temp_file.exists():
            try:
                temp_file.unlink()
            except OSError:
                pass


def _save_issue(data: dict[str, Any]) -> None:
    """Save current_issue.json atomically (caller must hold lock)."""
    _save_issue_atomic(data)


def _get_log_path() -> Path:
    """Get path to current_issue.log."""
    if _project_dir is None:
        raise RuntimeError("issue_tools not configured. Call configure() first.")
    return _project_dir / "current_issue.log"


def _clear_log() -> bool:
    """Clear current_issue.log.

    Returns:
        True if successful, False otherwise
    """
    try:
        log_path = _get_log_path()
        if log_path.exists():
            log_path.unlink()
        return True
    except Exception:
        return False


def _load_sprint(sprint_path: str) -> dict[str, Any] | None:
    """Load sprint.json file.

    Args:
        sprint_path: Path to sprint.json

    Returns:
        Sprint data dict or None if file doesn't exist
    """
    path = Path(sprint_path)
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _validate_issue_in_sprint(
    sprint_path: str, issue_id: str
) -> tuple[bool, str, str | None]:
    """Validate that an issue exists in the sprint and is selectable.

    Args:
        sprint_path: Path to sprint.json
        issue_id: Issue ID to validate

    Returns:
        Tuple of (is_valid, error_message, issue_title)
    """
    sprint_data = _load_sprint(sprint_path)
    if sprint_data is None:
        return False, f"Sprint file not found: {sprint_path}", None

    issues = sprint_data.get("issues", [])
    for issue in issues:
        if issue.get("id") == issue_id:
            status = issue.get("status", "pending")
            if status == "pending":
                return True, "", issue.get("title", "")
            elif status == "completed":
                return False, f"Issue {issue_id} is already completed", None
            elif status == "in_progress":
                return False, f"Issue {issue_id} is already in progress", None
            elif status == "blocked":
                return False, f"Issue {issue_id} is blocked", None
            else:
                return False, f"Issue {issue_id} has invalid status: {status}", None

    return False, f"Issue {issue_id} not found in sprint", None


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
    """Get current issue state with locking."""
    try:
        with _get_lock().locked():
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
    """Update current issue fields with locking."""
    try:
        with _get_lock().locked():
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
    """Set the next workflow step with locking."""
    try:
        with _get_lock().locked():
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
    """Record a file change with locking."""
    try:
        with _get_lock().locked():
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
    """Record a failure with locking."""
    try:
        with _get_lock().locked():
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
    """Clear failures and reset retry count with locking."""
    try:
        with _get_lock().locked():
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
    """Initialize current_issue.json for a selected issue with locking.

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
        with _get_lock().locked():
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

            # Validate issue exists in sprint and is selectable
            is_valid, error_msg, issue_title = _validate_issue_in_sprint(sprint_path, issue_id)
            if not is_valid:
                return ToolResult(
                    success=False,
                    message=f"Cannot init issue: {error_msg}",
                )

            # Create fresh current_issue data
            timestamp = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            session_id = f"{timestamp}/{step}"

            data = {
                "schema_version": "2.0",
                "sprint_path": sprint_path,
                "issue_id": issue_id,
                "issue_title": issue_title or "",  # From sprint validation
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

            # Clear the log file when initializing a new issue to avoid mixing
            # log entries from different issues
            _clear_log()

            _save_issue(data)

            return ToolResult(
                success=True,
                message=f"Initialized current_issue.json for {issue_id} at step {step}",
                data={"issue_id": issue_id, "step": step, "sprint_path": sprint_path},
            )
    except Exception as e:
        return ToolResult(success=False, message=f"Failed to init issue: {e}")
