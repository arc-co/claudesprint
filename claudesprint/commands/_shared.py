"""Shared utilities for CLI commands.

This module provides common utilities used across all command modules.
Heavy imports should be done inside functions to keep startup time fast.
"""

from pathlib import Path

from rich.console import Console

# Singleton console instance
console = Console()


def get_project_root() -> Path:
    """Get the project root directory.

    Returns:
        Project root path, or current working directory if not in a project.
    """
    # Lazy import to avoid loading configuration at module level
    from claudesprint.services.configuration_manager import ConfigurationManager

    discovered = ConfigurationManager.discover_project_root()
    return discovered or Path.cwd()


def get_config():
    """Get configuration for current project.

    Returns:
        ClaudesprintConfig instance for the current project.
    """
    # Lazy import to avoid loading configuration at module level
    from claudesprint.models.config import ClaudesprintConfig

    return ClaudesprintConfig.from_project_root(str(get_project_root()))


# Re-export all style utilities for convenience
from claudesprint.utils.styles import (
    COLORS,
    STYLES,
    SYMBOLS,
    ConsoleThrobber,
    success,
    error,
    warning,
    running,
    subprocess_line,
    status_badge,
    model_badge,
    muted,
    info,
    success_icon,
    error_icon,
    warning_icon,
)

__all__ = [
    # Core utilities
    "console",
    "get_project_root",
    "get_config",
    # Style constants
    "COLORS",
    "STYLES",
    "SYMBOLS",
    # Style helpers
    "ConsoleThrobber",
    "success",
    "error",
    "warning",
    "running",
    "subprocess_line",
    "status_badge",
    "model_badge",
    "muted",
    "info",
    "success_icon",
    "error_icon",
    "warning_icon",
]
