"""Session state utilities for ClaudeSprint."""

from pathlib import Path


def is_session_active(project_root: Path | str | None = None) -> bool:
    """Check if a ClaudeSprint session is currently active.

    Returns True if sprint.lock exists (path determined by ConfigurationManager).
    Returns False if project root cannot be determined, directory doesn't
    exist, or any filesystem error occurs.
    """
    from claudesprint.services.configuration_manager import ConfigurationManager

    try:
        if project_root is None:
            discovered = ConfigurationManager.discover_project_root()
            if discovered is None:
                return False
            project_root = discovered

        cm = ConfigurationManager(project_root=project_root)
        return cm.paths.sprint_lock_file.exists()
    except (OSError, PermissionError):
        return False
