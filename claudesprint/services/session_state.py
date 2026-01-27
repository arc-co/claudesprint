"""Session state utilities for ClaudeSprint."""

from pathlib import Path


def is_session_active(project_root: Path | str | None = None) -> bool:
    """Check if a ClaudeSprint session is currently active.

    Returns True if sprint.lock exists (path determined by PathService).
    Returns False if project root cannot be determined, directory doesn't
    exist, or any filesystem error occurs.
    """
    from claudesprint.services.path_service import PathService

    try:
        if project_root is None:
            discovered = PathService.discover_project_root()
            if discovered is None:
                return False
            project_root = discovered

        path_service = PathService(project_root=project_root)
        return path_service.sprint_lock_file.exists()
    except (OSError, PermissionError):
        return False
