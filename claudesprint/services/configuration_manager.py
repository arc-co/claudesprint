"""Unified configuration manager for ClaudeSprint.

Consolidates configuration loading from:
- Project config (.claudesprint/config.toml)
- Global config (~/.config/claudesprint/config.toml)
- Path resolution for project directories and files
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from claudesprint.services.global_config_service import GlobalConfig
    from claudesprint.services.project_config_service import (
        ModelName,
        ProjectConfig,
    )

# TOML parsing: use tomllib (3.11+) or tomli (backport for 3.10)
if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[import-not-found]

import tomli_w

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResolvedPaths:
    """All resolved paths for a project, frozen for immutability."""

    project_root: Path
    claude_dir: Path
    config_dir: Path
    project_dir: Path
    sprints_dir: Path
    specs_dir: Path
    config_files_dir: Path
    current_issue_file: Path
    current_issue_log_file: Path
    lock_file: Path
    log_file: Path
    step_marker_file: Path
    claude_output_file: Path
    notifications_file: Path
    models_file: Path
    project_config_file: Path
    sprint_lock_file: Path
    conversation_log_file: Path

    @classmethod
    def from_project_root(cls, project_root: Path) -> ResolvedPaths:
        """Create ResolvedPaths from a project root directory."""
        config_dir = project_root / ".claudesprint"
        project_dir = config_dir / "project"
        config_files_dir = config_dir / "config"

        return cls(
            project_root=project_root,
            claude_dir=project_root / ".claude",
            config_dir=config_dir,
            project_dir=project_dir,
            sprints_dir=config_dir / "sprints",
            specs_dir=config_dir / "specs",
            config_files_dir=config_files_dir,
            current_issue_file=project_dir / "current_issue.json",
            current_issue_log_file=project_dir / "current_issue.log",
            lock_file=project_dir / ".loop.lock",
            log_file=project_dir / "loop.log",
            step_marker_file=project_dir / ".current_step",
            claude_output_file=project_dir / ".claude_output.tmp",
            notifications_file=config_files_dir / "notifications.json",
            models_file=config_files_dir / "models.json",
            project_config_file=config_dir / "config.toml",
            sprint_lock_file=config_dir / "state" / "sprint.lock",
            conversation_log_file=project_dir / "agent_conversations.log",
        )


class ConfigurationManager:
    """Unified configuration manager for ClaudeSprint.

    Consolidates:
    - Project config loading/saving (from .claudesprint/config.toml)
    - Global config loading (from ~/.config/claudesprint/config.toml)
    - Path resolution for all project directories and files

    Example:
        >>> cm = ConfigurationManager()
        >>> print(cm.project.models.default_model)
        >>> print(cm.paths.project_root)
    """

    CONFIG_FILENAME = "config.toml"

    def __init__(self, project_root: Path | str | None = None) -> None:
        """Initialize the configuration manager.

        Args:
            project_root: Project root directory containing .claudesprint/.
                         If None, attempts to discover by walking up from cwd.
        """
        if project_root is None:
            discovered = self.discover_project_root()
            self._project_root = discovered or Path.cwd()
        else:
            self._project_root = Path(project_root)

        self._project_config: ProjectConfig | None = None
        self._global_config: GlobalConfig | None = None
        self._paths: ResolvedPaths | None = None

    # === Properties ===

    @property
    def project_root(self) -> Path:
        """Get the project root directory."""
        return self._project_root

    @cached_property
    def paths(self) -> ResolvedPaths:
        """Get all resolved paths for this project."""
        return ResolvedPaths.from_project_root(self._project_root)

    @property
    def project(self) -> ProjectConfig:
        """Get the project configuration (lazy-loaded and cached)."""
        if self._project_config is None:
            self._project_config = self._load_project_config()
        return self._project_config

    @property
    def global_config(self) -> GlobalConfig:
        """Get the global configuration (lazy-loaded and cached)."""
        if self._global_config is None:
            self._global_config = self._load_global_config()
        return self._global_config

    @property
    def config_path(self) -> Path:
        """Get the project config file path."""
        return self.paths.project_config_file

    # === Config Loading ===

    def _load_project_config(self) -> ProjectConfig:
        """Load project configuration from TOML file."""
        from claudesprint.services.project_config_service import ProjectConfig

        config_path = self.paths.project_config_file
        if not config_path.exists():
            return ProjectConfig()

        try:
            with open(config_path, "rb") as f:
                data = tomllib.load(f)
            return ProjectConfig(**data)
        except (OSError, tomllib.TOMLDecodeError) as e:
            logger.warning(
                "Failed to load project config from %s: %s. Using defaults.",
                config_path,
                e,
            )
            return ProjectConfig()

    def _load_global_config(self) -> GlobalConfig:
        """Load global configuration from TOML file."""
        from claudesprint.services.global_config_service import GlobalConfig

        config_path = self.get_default_global_config_path()
        if not config_path.exists():
            return GlobalConfig()

        try:
            with open(config_path, "rb") as f:
                data = tomllib.load(f)
            return GlobalConfig(**data)
        except (OSError, tomllib.TOMLDecodeError):
            return GlobalConfig()

    # === Explicit Loaders ===

    def load_project(self) -> ProjectConfig:
        """Explicitly load project configuration.

        Returns:
            ProjectConfig instance
        """
        self._project_config = self._load_project_config()
        return self._project_config

    def load_global(self) -> GlobalConfig:
        """Explicitly load global configuration.

        Returns:
            GlobalConfig instance
        """
        self._global_config = self._load_global_config()
        return self._global_config

    # === Config Saving ===

    def save_project(self, config: ProjectConfig | None = None) -> bool:
        """Save project configuration to TOML file.

        Args:
            config: Configuration to save. If None, saves current config.

        Returns:
            True if save was successful
        """
        if config is None:
            config = self.project

        try:
            # Ensure directory exists
            self.paths.project_config_file.parent.mkdir(parents=True, exist_ok=True)

            # Convert to dict for TOML serialization
            # Use by_alias=True to get hyphenated keys like "read-docs"
            data = config.model_dump(by_alias=True, exclude_none=True)

            with open(self.paths.project_config_file, "wb") as f:
                tomli_w.dump(data, f)

            self._project_config = config
            return True
        except OSError as e:
            logger.warning(
                "Failed to save config to %s: %s", self.paths.project_config_file, e
            )
            return False

    # === Config Initialization ===

    def init_config(self, overwrite: bool = False) -> bool:
        """Initialize project config file with default template.

        Args:
            overwrite: If True, overwrite existing file

        Returns:
            True if file was created/written
        """
        from claudesprint.services.project_config_service import (
            DEFAULT_PROJECT_CONFIG_TOML,
        )

        config_path = self.paths.project_config_file
        if config_path.exists() and not overwrite:
            return False

        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(DEFAULT_PROJECT_CONFIG_TOML)
            self._project_config = None  # Clear cache
            return True
        except OSError as e:
            logger.warning("Failed to initialize config at %s: %s", config_path, e)
            return False

    # === Reload ===

    def reload(self) -> None:
        """Clear all caches and force reload on next access."""
        self._project_config = None
        self._global_config = None
        # Clear cached_property
        if "paths" in self.__dict__:
            del self.__dict__["paths"]

    # === Existence Checks ===

    def exists(self) -> bool:
        """Check if project config file exists."""
        return self.paths.project_config_file.exists()

    # === Convenience Methods ===

    def get_model_for_step(self, step_name: str) -> ModelName:
        """Get the model to use for a workflow step.

        Args:
            step_name: Step name (e.g., "implement", "code-review")

        Returns:
            Model name
        """
        config = self.project

        # Check for override
        if config.models.model_override:
            return config.models.model_override

        # Normalize step name to use underscores for attribute access
        attr_name = step_name.replace("-", "_")

        # Check step-specific config
        step_model: ModelName | None = getattr(config.models.steps, attr_name, None)
        if step_model:
            return step_model

        # Fall back to default
        return config.models.default_model

    def get_model_for_special_step(self, step_name: str) -> ModelName:
        """Get the model for a special step (init, plan).

        Args:
            step_name: Special step name (init, plan)

        Returns:
            Model name
        """
        config = self.project

        # Check for override
        if config.models.model_override:
            return config.models.model_override

        # Check special config
        special_model: ModelName | None = getattr(config.models.special, step_name, None)
        if special_model:
            return special_model

        # Fall back to default
        return config.models.default_model

    # === Directory Management ===

    def ensure_directories(self) -> None:
        """Create all required directories if they don't exist."""
        self.paths.project_dir.mkdir(parents=True, exist_ok=True)
        self.paths.sprints_dir.mkdir(parents=True, exist_ok=True)
        self.paths.specs_dir.mkdir(parents=True, exist_ok=True)
        self.paths.config_files_dir.mkdir(parents=True, exist_ok=True)

    # === Sprint-specific ===

    def get_sprint_dir(self, spec_id: str) -> Path:
        """Get the directory for a specific sprint.

        Args:
            spec_id: The spec identifier (e.g., "SPEC_01")

        Returns:
            Path to the sprint directory
        """
        return self.paths.sprints_dir / spec_id

    def get_sprint_path(self, spec_id: str) -> Path:
        """Get the path to a sprint.json file.

        Args:
            spec_id: The spec identifier (e.g., "SPEC_01")

        Returns:
            Path to sprint.json
        """
        return self.get_sprint_dir(spec_id) / "sprint.json"

    # === Discovery ===

    @classmethod
    def discover_project_root(cls, start: Path | None = None) -> Path | None:
        """Walk up from start (or cwd) looking for .claude directory.

        Args:
            start: Starting directory for search. Defaults to cwd.

        Returns:
            Path to project root if .claude found, None otherwise
        """
        cwd = start or Path.cwd()
        for parent in [cwd] + list(cwd.parents):
            if (parent / ".claude").exists():
                return parent
        return None

    # === Static Methods ===

    @staticmethod
    def get_default_global_config_path() -> Path:
        """Get the default global config file path for the current platform.

        Returns:
            Path to config.toml
        """
        # Check for environment variable override first
        env_home = os.environ.get("CLAUDESPRINT_CONFIG_HOME")
        if env_home:
            return Path(env_home) / "config.toml"

        # Platform-specific paths
        if sys.platform == "win32":
            # Windows: %APPDATA%/claudesprint
            appdata = os.environ.get("APPDATA")
            if appdata:
                return Path(appdata) / "claudesprint" / "config.toml"
            # Fallback to user home
            return Path.home() / "AppData" / "Roaming" / "claudesprint" / "config.toml"
        else:
            # Linux/macOS: XDG_CONFIG_HOME or ~/.config
            xdg_config = os.environ.get("XDG_CONFIG_HOME")
            if xdg_config:
                return Path(xdg_config) / "claudesprint" / "config.toml"
            return Path.home() / ".config" / "claudesprint" / "config.toml"

    # === Global Config Helpers (for backward compatibility with models/config.py) ===

    def get_global_flat_dict(self) -> dict[str, Any]:
        """Get global configuration as a flat dictionary for easy access.

        Returns:
            Dict with keys like 'max_retry', 'rate_limit_retries', etc.
        """
        config = self.global_config
        result: dict[str, Any] = {}

        # Flatten defaults section
        result["model"] = config.defaults.model
        result["max_retry"] = config.defaults.max_retry
        result["claude_timeout"] = config.defaults.claude_timeout
        result["total_timeout"] = config.defaults.total_timeout

        # Flatten rate_limiting section
        result["rate_limit_retries"] = config.rate_limiting.retries
        result["rate_limit_base_wait"] = config.rate_limiting.base_wait
        result["rate_limit_max_wait"] = config.rate_limiting.max_wait

        # Flatten heartbeat section
        result["heartbeat_enabled"] = config.heartbeat.enabled
        result["heartbeat_timeout"] = config.heartbeat.timeout

        # Flatten debug section
        result["debug_conversations"] = config.debug.conversations

        return result
