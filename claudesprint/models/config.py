"""Configuration models for ClaudeSprint."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

from pydantic import AliasChoices, BaseModel, Field, PrivateAttr
from pydantic_settings import BaseSettings

if TYPE_CHECKING:
    from claudesprint.services.global_config_service import GlobalConfigService
    from claudesprint.services.path_service import PathService


class BarkConfig(BaseModel):
    """Bark push notification configuration."""

    enabled: bool = False
    url: str = ""


class NotificationConfig(BaseModel):
    """Notification settings."""

    enabled: bool = True
    bark: BarkConfig = Field(default_factory=BarkConfig)


class ClaudesprintConfig(BaseSettings):
    """Main configuration for ClaudeSprint.

    Environment variables override defaults:
    - CLAUDESPRINT_MAX_RETRY: Maximum retry count (default: 5)
    - CLAUDESPRINT_CLAUDE_TIMEOUT: Timeout for Claude sessions in seconds (default: 1800 = 30 min)
    - CLAUDESPRINT_TOTAL_TIMEOUT: Total runtime limit in seconds (default: 28800 = 8 hours, 0 = unlimited)
    - CLAUDESPRINT_RATE_LIMIT_RETRIES: Max rate limit retries before exiting (default: 3, 0 = exit immediately)
    - CLAUDESPRINT_RATE_LIMIT_BASE_WAIT: Base wait time in seconds for rate limit backoff (default: 60)
    - CLAUDESPRINT_RATE_LIMIT_MAX_WAIT: Maximum wait time in seconds for rate limit backoff (default: 900 = 15 min)
    """

    max_retry: Annotated[int, Field(ge=1)] = Field(
        default=5,
        description="Maximum number of retries before giving up",
        validation_alias=AliasChoices("max_retry", "CLAUDESPRINT_MAX_RETRY"),
    )
    claude_timeout: Annotated[int, Field(ge=60)] = Field(
        default=1800,
        description="Timeout for individual Claude sessions in seconds",
        validation_alias=AliasChoices("claude_timeout", "CLAUDESPRINT_CLAUDE_TIMEOUT"),
    )
    total_timeout: Annotated[int, Field(ge=0)] = Field(
        default=28800,
        description="Total runtime limit in seconds (0 = unlimited)",
        validation_alias=AliasChoices("total_timeout", "CLAUDESPRINT_TOTAL_TIMEOUT"),
    )
    rate_limit_retries: Annotated[int, Field(ge=0)] = Field(
        default=3,
        description="Max rate limit retries before exiting (0 = exit immediately)",
        validation_alias=AliasChoices("rate_limit_retries", "CLAUDESPRINT_RATE_LIMIT_RETRIES"),
    )
    rate_limit_base_wait: Annotated[int, Field(ge=10)] = Field(
        default=60,
        description="Base wait time in seconds for rate limit exponential backoff",
        validation_alias=AliasChoices("rate_limit_base_wait", "CLAUDESPRINT_RATE_LIMIT_BASE_WAIT"),
    )
    rate_limit_max_wait: Annotated[int, Field(ge=60)] = Field(
        default=900,
        description="Maximum wait time in seconds for rate limit backoff (default 15 min)",
        validation_alias=AliasChoices("rate_limit_max_wait", "CLAUDESPRINT_RATE_LIMIT_MAX_WAIT"),
    )
    heartbeat_timeout: Annotated[int, Field(ge=60)] = Field(
        default=600,
        description="Seconds of inactivity before triggering hung process notification",
        validation_alias=AliasChoices("heartbeat_timeout", "CLAUDESPRINT_HEARTBEAT_TIMEOUT"),
    )
    heartbeat_enabled: bool = Field(
        default=True,
        description="Enable heartbeat monitoring for hung process detection",
        validation_alias=AliasChoices("heartbeat_enabled", "CLAUDESPRINT_HEARTBEAT_ENABLED"),
    )
    debug_conversations: bool = Field(
        default=False,
        description="Log full agent inputs and outputs to agent_conversations.log",
        validation_alias=AliasChoices("debug_conversations", "CLAUDESPRINT_DEBUG_CONVERSATIONS"),
    )

    # Paths (derived from script location) - kept for backward compatibility
    claude_dir: str = Field(default="", description="Path to .claude directory")
    project_dir: str = Field(default="", description="Path to .claudesprint/project directory")
    claudesprint_dir: str = Field(default="", description="Path to .claudesprint directory")
    prompts_dir: str = Field(default="", description="Path to prompts directory (inside claudesprint)")

    # Private attributes for services
    _path_service: "PathService | None" = PrivateAttr(default=None)
    _global_config_service: "GlobalConfigService | None" = PrivateAttr(default=None)
    _project_root: Path | None = PrivateAttr(default=None)

    model_config = {
        "env_file": ".claudesprint/.env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @staticmethod
    def _get_global_defaults() -> dict[str, Any]:
        """Load defaults from global config file.

        Only returns values for fields where no environment variable is set.
        This ensures env vars have highest precedence.

        Returns:
            Dict with global config values to use as defaults
        """
        # Lazy import to avoid circular dependency
        from claudesprint.services.global_config_service import GlobalConfigService

        service = GlobalConfigService()
        if not service.exists():
            return {}

        flat = service.get_flat_dict()

        # Map of field name -> env var name
        env_var_map = {
            "max_retry": "CLAUDESPRINT_MAX_RETRY",
            "claude_timeout": "CLAUDESPRINT_CLAUDE_TIMEOUT",
            "total_timeout": "CLAUDESPRINT_TOTAL_TIMEOUT",
            "rate_limit_retries": "CLAUDESPRINT_RATE_LIMIT_RETRIES",
            "rate_limit_base_wait": "CLAUDESPRINT_RATE_LIMIT_BASE_WAIT",
            "rate_limit_max_wait": "CLAUDESPRINT_RATE_LIMIT_MAX_WAIT",
            "heartbeat_enabled": "CLAUDESPRINT_HEARTBEAT_ENABLED",
            "heartbeat_timeout": "CLAUDESPRINT_HEARTBEAT_TIMEOUT",
            "debug_conversations": "CLAUDESPRINT_DEBUG_CONVERSATIONS",
        }

        # Only include values where env var is not set
        result: dict[str, Any] = {}
        for field_name, value in flat.items():
            env_var = env_var_map.get(field_name)
            if env_var and os.environ.get(env_var) is not None:
                # Env var is set, skip this field (let pydantic-settings handle it)
                continue
            result[field_name] = value

        return result

    @property
    def paths(self) -> "PathService":
        """Get PathService for centralized path resolution.

        Returns:
            PathService instance configured with the project root
        """
        if self._path_service is None:
            # Lazy import to avoid circular dependency
            from claudesprint.services.path_service import PathService

            self._path_service = PathService(project_root=self._project_root)
        return self._path_service

    @classmethod
    def from_project_root(cls, project_root: str) -> "ClaudesprintConfig":
        """Create config with paths derived from project root.

        Configuration precedence (highest to lowest):
        1. Environment variables (CLAUDESPRINT_*)
        2. Project config (.claudesprint/.env)
        3. Global config (~/.config/claudesprint/config.toml)
        4. Hardcoded defaults

        Args:
            project_root: Path to the project root directory

        Returns:
            ClaudesprintConfig instance configured for the project
        """
        # Lazy import to avoid circular dependency
        from claudesprint.services.global_config_service import GlobalConfigService
        from claudesprint.services.path_service import PathService

        claude_dir = os.path.join(project_root, ".claude")
        claudesprint_dir = os.path.join(project_root, ".claudesprint")

        # Load global config defaults first
        global_defaults = cls._get_global_defaults()

        # Build kwargs with global defaults (pydantic-settings will override with env vars)
        kwargs: dict[str, Any] = {
            "claude_dir": claude_dir,
            "project_dir": os.path.join(claudesprint_dir, "project"),
            "claudesprint_dir": claudesprint_dir,
            "prompts_dir": os.path.join(claudesprint_dir, "prompts"),
        }

        # Apply global config defaults for fields that have them
        # Only set if the global config has a value (not relying on Pydantic defaults)
        field_mapping = {
            "max_retry": "max_retry",
            "claude_timeout": "claude_timeout",
            "total_timeout": "total_timeout",
            "rate_limit_retries": "rate_limit_retries",
            "rate_limit_base_wait": "rate_limit_base_wait",
            "rate_limit_max_wait": "rate_limit_max_wait",
            "heartbeat_enabled": "heartbeat_enabled",
            "heartbeat_timeout": "heartbeat_timeout",
            "debug_conversations": "debug_conversations",
        }

        for field_name, global_key in field_mapping.items():
            if global_key in global_defaults:
                kwargs[field_name] = global_defaults[global_key]

        config = cls(**kwargs)
        config._project_root = Path(project_root)
        config._path_service = PathService(project_root=project_root)
        config._global_config_service = GlobalConfigService()
        return config

    @property
    def current_issue_file(self) -> str:
        """Path to current_issue.json."""
        return os.path.join(self.project_dir, "current_issue.json")

    @property
    def current_issue_log_file(self) -> str:
        """Path to current_issue.log."""
        return os.path.join(self.project_dir, "current_issue.log")

    @property
    def sprints_dir(self) -> str:
        """Path to sprints directory (inside claudesprint/)."""
        return os.path.join(self.claudesprint_dir, "sprints")

    @property
    def lock_file(self) -> str:
        """Path to loop lock file."""
        return os.path.join(self.project_dir, ".loop.lock")

    @property
    def log_file(self) -> str:
        """Path to loop log file."""
        return os.path.join(self.project_dir, "loop.log")

    @property
    def step_marker_file(self) -> str:
        """Path to current step marker file."""
        return os.path.join(self.project_dir, ".current_step")

    @property
    def claude_output_file(self) -> str:
        """Path to temp file for capturing Claude output."""
        return os.path.join(self.project_dir, ".claude_output.tmp")

    @property
    def notifications_file(self) -> str:
        """Path to notifications config file."""
        return os.path.join(self.claudesprint_dir, "config", "notifications.json")

    @property
    def models_file(self) -> str:
        """Path to models config file for per-step model selection."""
        return os.path.join(self.claudesprint_dir, "config", "models.json")

    def get_prompt_file(self, step: str) -> str:
        """Get path to prompt file for a step."""
        return os.path.join(self.prompts_dir, f"PROMPT_{step}.md")

    @property
    def common_prompt_file(self) -> str:
        """Path to common prompt patterns file (prepended to all prompts)."""
        return os.path.join(self.prompts_dir, "_common.md")

    @property
    def schemas_dir(self) -> str:
        """Path to JSON schemas directory."""
        return os.path.join(self.claudesprint_dir, "schemas")

    @property
    def specs_dir(self) -> str:
        """Path to specs directory (inside claudesprint/)."""
        return os.path.join(self.claudesprint_dir, "specs")

    @property
    def conversation_log_file(self) -> str:
        """Path to agent_conversations.log for debug mode."""
        return os.path.join(self.project_dir, "agent_conversations.log")
