"""Sprint tools for CLI - provides token-efficient sprint views.

This module creates "views" that filter out noise (completed task history,
metadata overhead) and presents only decision-relevant data to the LLM.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from claudesprint.models.sprint import IssuePriority, IssueStatus
from claudesprint.services.sprint_service import SprintService

# Module-level configuration
_sprints_dir: Path | None = None


def configure(sprints_dir: Path) -> None:
    """Configure the sprint tools with sprints directory."""
    global _sprints_dir
    _sprints_dir = sprints_dir


def _get_service() -> SprintService:
    """Get configured SprintService."""
    if _sprints_dir is None:
        raise RuntimeError("sprint_tools not configured. Call configure() first.")
    return SprintService(_sprints_dir)


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


def list_available_issues(spec_id: str | None = None) -> ToolResult:
    """Get a token-optimized list of available issues.

    Filters out completed issues and heavy history.
    Checks dependencies to mark availability.

    Args:
        spec_id: Optional spec ID to query. If None, uses active sprint.

    Returns:
        ToolResult with available issues view.
    """
    try:
        service = _get_service()

        # Determine sprint path
        if spec_id:
            path = service.get_sprint_path(spec_id)
            if not path.exists():
                return ToolResult(
                    success=False,
                    message=f"Sprint not found for spec: {spec_id}",
                )
        else:
            path, _ = service.get_active_sprint()
            if not path:
                return ToolResult(
                    success=False,
                    message="No active sprint found",
                )

        sprint = service.read_sprint(path)
        if not sprint:
            return ToolResult(
                success=False,
                message="Failed to parse sprint.json",
            )

        # Build efficient view - filter out completed issues and heavy history
        available_view: list[dict[str, Any]] = []
        blocked_view: list[dict[str, Any]] = []
        in_progress_view: list[dict[str, Any]] = []

        # Pre-calculate completed IDs for dependency checking
        completed_ids = {i.id for i in sprint.issues if i.status == IssueStatus.COMPLETED}

        # Priority order for sorting
        priority_order = {
            IssuePriority.CRITICAL: 0,
            IssuePriority.HIGH: 1,
            IssuePriority.MEDIUM: 2,
            IssuePriority.LOW: 3,
        }

        for issue in sprint.issues:
            if issue.status == IssueStatus.COMPLETED:
                continue

            # Check dependencies
            missing_deps = []
            for dep in issue.dependencies:
                if dep not in completed_ids:
                    missing_deps.append(dep)

            # Build compact issue summary (no history, no acceptance_criteria)
            issue_summary: dict[str, Any] = {
                "id": issue.id,
                "title": issue.title,
                "priority": issue.priority.value,
                "category": issue.category.value if issue.category else None,
            }

            # Include dependencies only if they exist
            if issue.dependencies:
                issue_summary["dependencies"] = issue.dependencies

            if issue.status == IssueStatus.IN_PROGRESS:
                # In-progress issues should be resumed
                issue_summary["status"] = "IN_PROGRESS"
                issue_summary["action"] = "RESUME THIS"
                in_progress_view.append(issue_summary)
            elif missing_deps:
                # Blocked by incomplete dependencies
                issue_summary["status"] = "blocked"
                issue_summary["blocked_by"] = missing_deps
                blocked_view.append(issue_summary)
            else:
                # Available for selection
                issue_summary["status"] = "pending"
                available_view.append(issue_summary)

        # Sort available by priority
        available_view.sort(key=lambda x: priority_order.get(IssuePriority(x["priority"]), 99))

        # Build response
        response_data: dict[str, Any] = {
            "spec_id": sprint.spec_id,
            "sprint_path": str(path),
            "summary": {
                "in_progress": len(in_progress_view),
                "available": len(available_view),
                "blocked": len(blocked_view),
                "completed": sprint.metadata.completed,
                "total": sprint.metadata.total_issues,
            },
        }

        # In-progress issues go first (should resume)
        if in_progress_view:
            response_data["in_progress_issues"] = in_progress_view

        # Available issues (sorted by priority)
        if available_view:
            response_data["available_issues"] = available_view

        # Only show blocked if nothing else is available (saves tokens)
        if not in_progress_view and not available_view:
            if blocked_view:
                response_data["blocked_issues"] = blocked_view
                response_data["message"] = "All remaining issues are blocked by dependencies"
            else:
                response_data["message"] = "SPRINT_COMPLETE: All issues are done"

        return ToolResult(
            success=True,
            message="Sprint view generated",
            data=response_data,
        )

    except Exception as e:
        return ToolResult(
            success=False,
            message=f"Failed to query sprint: {e}",
        )


def start_issue(issue_id: str, spec_id: str | None = None) -> ToolResult:
    """Mark an issue as in_progress in the sprint.

    This should be called when selecting an issue to work on.
    Updates the sprint.json status and adds history entry.

    Args:
        issue_id: The issue ID to start.
        spec_id: Optional spec ID. If None, uses active sprint.

    Returns:
        ToolResult indicating success or failure.
    """
    try:
        service = _get_service()

        # Determine sprint path
        if spec_id:
            path = service.get_sprint_path(spec_id)
            if not path.exists():
                return ToolResult(
                    success=False,
                    message=f"Sprint not found for spec: {spec_id}",
                )
        else:
            path, _ = service.get_active_sprint()
            if not path:
                return ToolResult(
                    success=False,
                    message="No active sprint found",
                )

        sprint = service.read_sprint(path)
        if not sprint:
            return ToolResult(
                success=False,
                message="Failed to parse sprint.json",
            )

        issue = sprint.get_issue(issue_id)
        if not issue:
            return ToolResult(
                success=False,
                message=f"Issue not found: {issue_id}",
            )

        # Check if issue can be started (not already completed)
        if issue.status == IssueStatus.COMPLETED:
            return ToolResult(
                success=False,
                message=f"Issue {issue_id} is already completed",
            )

        # Check if issue is already in progress
        if issue.status == IssueStatus.IN_PROGRESS:
            return ToolResult(
                success=True,
                message=f"Issue {issue_id} is already in progress",
                data={"issue_id": issue_id, "status": "in_progress", "sprint_path": str(path)},
            )

        # Check dependencies
        completed_ids = {i.id for i in sprint.issues if i.status == IssueStatus.COMPLETED}
        missing_deps = [dep for dep in issue.dependencies if dep not in completed_ids]
        if missing_deps:
            return ToolResult(
                success=False,
                message=f"Issue {issue_id} is blocked by incomplete dependencies: {missing_deps}",
            )

        # Mark as in_progress
        success = service.mark_issue_status(path, issue_id, IssueStatus.IN_PROGRESS)
        if not success:
            return ToolResult(
                success=False,
                message=f"Failed to update issue status for {issue_id}",
            )

        return ToolResult(
            success=True,
            message=f"Started issue {issue_id}",
            data={"issue_id": issue_id, "status": "in_progress", "sprint_path": str(path)},
        )

    except Exception as e:
        return ToolResult(
            success=False,
            message=f"Failed to start issue: {e}",
        )


def get_issue_details(issue_id: str, spec_id: str | None = None) -> ToolResult:
    """Get full details for a specific issue (including acceptance criteria).

    Use this after selection to get the full context needed for implementation.

    Args:
        issue_id: The issue ID to retrieve.
        spec_id: Optional spec ID. If None, uses active sprint.

    Returns:
        ToolResult with full issue details.
    """
    try:
        service = _get_service()

        # Determine sprint path
        if spec_id:
            path = service.get_sprint_path(spec_id)
            if not path.exists():
                return ToolResult(
                    success=False,
                    message=f"Sprint not found for spec: {spec_id}",
                )
        else:
            path, _ = service.get_active_sprint()
            if not path:
                return ToolResult(
                    success=False,
                    message="No active sprint found",
                )

        sprint = service.read_sprint(path)
        if not sprint:
            return ToolResult(
                success=False,
                message="Failed to parse sprint.json",
            )

        issue = sprint.get_issue(issue_id)
        if not issue:
            return ToolResult(
                success=False,
                message=f"Issue not found: {issue_id}",
            )

        # Full issue details for implementation context
        issue_data: dict[str, Any] = {
            "id": issue.id,
            "title": issue.title,
            "status": issue.status.value,
            "priority": issue.priority.value,
            "category": issue.category.value if issue.category else None,
            "acceptance_criteria": issue.acceptance_criteria,
            "dependencies": issue.dependencies,
        }

        if issue.notes:
            issue_data["notes"] = issue.notes

        return ToolResult(
            success=True,
            message=f"Issue details for {issue_id}",
            data={
                "sprint_path": str(path),
                "issue": issue_data,
            },
        )

    except Exception as e:
        return ToolResult(
            success=False,
            message=f"Failed to get issue details: {e}",
        )
