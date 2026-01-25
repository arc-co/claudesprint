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
    add_rationale: str | None = None,
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
        if add_rationale is not None:
            rationale = data.get("rationale", [])
            rationale.append(add_rationale)
            data["rationale"] = rationale

        _save_issue(data)
        return ToolResult(
            success=True,
            message="Issue updated",
            data={"updated_fields": [k for k, v in [("goal", goal), ("next_action", next_action), ("rationale", add_rationale)] if v is not None]},
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
