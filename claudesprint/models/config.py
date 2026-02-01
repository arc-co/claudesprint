"""Configuration models for ClaudeSprint."""

from __future__ import annotations

import os
from typing import Annotated, Any

from pydantic import AliasChoices, BaseModel, Field
from pydantic_settings import BaseSettings


# Map of config field name -> environment variable name (module-level constant)
_ENV_VAR_MAP: dict[str, str] = {
    "max_retry": "CLAUDESPRINT_MAX_RETRY",
    "max_total_iterations": "CLAUDESPRINT_MAX_TOTAL_ITERATIONS",
    "claude_timeout": "CLAUDESPRINT_CLAUDE_TIMEOUT",
    "total_timeout": "CLAUDESPRINT_TOTAL_TIMEOUT",
    "rate_limit_retries": "CLAUDESPRINT_RATE_LIMIT_RETRIES",
    "rate_limit_base_wait": "CLAUDESPRINT_RATE_LIMIT_BASE_WAIT",
    "rate_limit_max_wait": "CLAUDESPRINT_RATE_LIMIT_MAX_WAIT",
    "heartbeat_enabled": "CLAUDESPRINT_HEARTBEAT_ENABLED",
    "heartbeat_timeout": "CLAUDESPRINT_HEARTBEAT_TIMEOUT",
    "heartbeat_check_interval": "CLAUDESPRINT_HEARTBEAT_CHECK_INTERVAL",
    "debug_conversations": "CLAUDESPRINT_DEBUG_CONVERSATIONS",
    "kill_timeout": "CLAUDESPRINT_KILL_TIMEOUT",
    "git_timeout": "CLAUDESPRINT_GIT_TIMEOUT",
    "http_timeout": "CLAUDESPRINT_HTTP_TIMEOUT",
    "issue_delay": "CLAUDESPRINT_ISSUE_DELAY",
    "min_output_length": "CLAUDESPRINT_MIN_OUTPUT_LENGTH",
    "version_check_timeout": "CLAUDESPRINT_VERSION_CHECK_TIMEOUT",
    "install_timeout": "CLAUDESPRINT_INSTALL_TIMEOUT",
    "notifications_enabled": "CLAUDESPRINT_NOTIFICATIONS_ENABLED",
    "bark_enabled": "CLAUDESPRINT_BARK_ENABLED",
    "bark_url": "CLAUDESPRINT_BARK_URL",
    "webhook_enabled": "CLAUDESPRINT_WEBHOOK_ENABLED",
    "webhook_url": "CLAUDESPRINT_WEBHOOK_URL",
    "webhook_timeout": "CLAUDESPRINT_WEBHOOK_TIMEOUT",
    "webhook_retry_count": "CLAUDESPRINT_WEBHOOK_RETRY_COUNT",
}


class ClaudesprintConfig(BaseSettings):
    """Main configuration for ClaudeSprint.

    Configuration precedence (highest to lowest):
    1. Environment variables (CLAUDESPRINT_*)
    2. Project config (.claudesprint/config.toml) - per-project settings
    3. Global config (~/.config/claudesprint/config.toml) - shared defaults
    4. Hardcoded defaults

    Environment variables:
    - CLAUDESPRINT_MAX_RETRY: Maximum retry count (default: 5)
    - CLAUDESPRINT_CLAUDE_TIMEOUT: Timeout for Claude sessions in seconds (default: 1800 = 30 min)
    - CLAUDESPRINT_TOTAL_TIMEOUT: Total runtime limit in seconds (default: 28800 = 8 hours, 0 = unlimited)
    - CLAUDESPRINT_RATE_LIMIT_RETRIES: Max rate limit retries before exiting (default: 3, 0 = exit immediately)
    - CLAUDESPRINT_RATE_LIMIT_BASE_WAIT: Base wait time in seconds for rate limit backoff (default: 60)
    - CLAUDESPRINT_RATE_LIMIT_MAX_WAIT: Maximum wait time in seconds for rate limit backoff (default: 900 = 15 min)
    - CLAUDESPRINT_MAX_TOTAL_ITERATIONS: Maximum total step executions per issue (default: 50, prevents infinite loops)
    """

    # Runtime settings
    max_retry: Annotated[int, Field(ge=1)] = Field(
        default=5,
        description="Maximum number of retries before giving up",
        validation_alias=AliasChoices("max_retry", "CLAUDESPRINT_MAX_RETRY"),
    )
    max_total_iterations: Annotated[int, Field(ge=1)] = Field(
        default=50,
        description="Maximum total step executions per issue (prevents infinite loops between steps)",
        validation_alias=AliasChoices("max_total_iterations", "CLAUDESPRINT_MAX_TOTAL_ITERATIONS"),
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

    # Rate limiting settings
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

    # Heartbeat settings
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
    heartbeat_check_interval: float = Field(
        default=10.0,
        ge=1.0,
        description="How often to check for inactivity in seconds",
        validation_alias=AliasChoices("heartbeat_check_interval", "CLAUDESPRINT_HEARTBEAT_CHECK_INTERVAL"),
    )

    # Debug settings
    debug_conversations: bool = Field(
        default=False,
        description="Log full agent inputs and outputs to agent_conversations.log",
        validation_alias=AliasChoices("debug_conversations", "CLAUDESPRINT_DEBUG_CONVERSATIONS"),
    )

    # Timeout settings
    kill_timeout: int = Field(
        default=10,
        ge=1,
        description="Grace period before SIGKILL when terminating Claude",
        validation_alias=AliasChoices("kill_timeout", "CLAUDESPRINT_KILL_TIMEOUT"),
    )
    git_timeout: int = Field(
        default=60,
        ge=10,
        description="Git command timeout in seconds",
        validation_alias=AliasChoices("git_timeout", "CLAUDESPRINT_GIT_TIMEOUT"),
    )
    http_timeout: float = Field(
        default=10.0,
        ge=1.0,
        description="HTTP request timeout for notifications in seconds",
        validation_alias=AliasChoices("http_timeout", "CLAUDESPRINT_HTTP_TIMEOUT"),
    )
    issue_delay: float = Field(
        default=2.0,
        ge=0.0,
        description="Delay between processing issues in a sprint",
        validation_alias=AliasChoices("issue_delay", "CLAUDESPRINT_ISSUE_DELAY"),
    )

    # Advanced settings
    min_output_length: int = Field(
        default=50,
        ge=1,
        description="Minimum output length to consider a Claude response valid",
        validation_alias=AliasChoices("min_output_length", "CLAUDESPRINT_MIN_OUTPUT_LENGTH"),
    )
    version_check_timeout: int = Field(
        default=10,
        ge=1,
        description="Health check version check timeout in seconds",
        validation_alias=AliasChoices("version_check_timeout", "CLAUDESPRINT_VERSION_CHECK_TIMEOUT"),
    )
    install_timeout: int = Field(
        default=120,
        ge=10,
        description="Health check dependency install timeout in seconds",
        validation_alias=AliasChoices("install_timeout", "CLAUDESPRINT_INSTALL_TIMEOUT"),
    )

    # Paths (derived from script location) - kept for backward compatibility
    claude_dir: str = Field(default="", description="Path to .claude directory")
    project_dir: str = Field(default="", description="Path to .claudesprint/project directory")
    claudesprint_dir: str = Field(default="", description="Path to .claudesprint directory")
    prompts_dir: str = Field(default="", description="Path to prompts directory (inside claudesprint)")

    model_config = {
        "extra": "ignore",
    }

    @staticmethod
    def _get_project_config_values(project_root: str) -> dict[str, Any]:
        """Load config values from project config file.

        Only returns values for fields where no environment variable is set.
        This ensures env vars have highest precedence.

        Args:
            project_root: Path to the project root directory

        Returns:
            Dict with project config values to use
        """
        # Lazy import to avoid circular dependency
        from claudesprint.services.configuration_manager import ConfigurationManager

        manager = ConfigurationManager(project_root)
        if not manager.exists():
            return {}

        config = manager.project

        # Flatten project config into our field names
        result: dict[str, Any] = {}

        # Runtime settings
        result["max_retry"] = config.runtime.max_retry
        result["max_total_iterations"] = config.runtime.max_total_iterations
        result["claude_timeout"] = config.runtime.claude_timeout
        result["total_timeout"] = config.runtime.total_timeout

        # Rate limiting settings
        result["rate_limit_retries"] = config.rate_limiting.retries
        result["rate_limit_base_wait"] = config.rate_limiting.base_wait
        result["rate_limit_max_wait"] = config.rate_limiting.max_wait

        # Heartbeat settings
        result["heartbeat_enabled"] = config.heartbeat.enabled
        result["heartbeat_timeout"] = config.heartbeat.timeout
        result["heartbeat_check_interval"] = config.heartbeat.check_interval

        # Debug settings
        result["debug_conversations"] = config.debug.conversations

        # Timeout settings
        result["kill_timeout"] = config.timeouts.kill_timeout
        result["git_timeout"] = config.timeouts.git_timeout
        result["http_timeout"] = config.timeouts.http_timeout
        result["issue_delay"] = config.timeouts.issue_delay

        # Advanced settings
        result["min_output_length"] = config.advanced.min_output_length
        result["version_check_timeout"] = config.advanced.version_check_timeout
        result["install_timeout"] = config.advanced.install_timeout

        # Filter out fields where env var is set (env vars take precedence)
        filtered: dict[str, Any] = {}
        for field_name, value in result.items():
            env_var = _ENV_VAR_MAP.get(field_name)
            if env_var and os.environ.get(env_var) is not None:
                # Env var is set, skip this field
                continue
            filtered[field_name] = value

        return filtered

    @staticmethod
    def _get_global_defaults() -> dict[str, Any]:
        """Load defaults from global config file.

        Only returns values for fields where no environment variable is set.
        This ensures env vars have highest precedence.

        Returns:
            Dict with global config values to use as defaults
        """
        # Lazy import to avoid circular dependency
        from claudesprint.services.configuration_manager import ConfigurationManager

        manager = ConfigurationManager()
        config_path = manager.get_default_global_config_path()
        if not config_path.exists():
            return {}

        flat = manager.get_global_flat_dict()

        # Only include values where env var is not set
        result: dict[str, Any] = {}
        for field_name, value in flat.items():
            env_var = _ENV_VAR_MAP.get(field_name)
            if env_var and os.environ.get(env_var) is not None:
                # Env var is set, skip this field (let pydantic-settings handle it)
                continue
            result[field_name] = value

        return result

    @classmethod
    def from_project_root(cls, project_root: str) -> "ClaudesprintConfig":
        """Create config with paths derived from project root.

        Configuration precedence (highest to lowest):
        1. Environment variables (CLAUDESPRINT_*)
        2. Project config (.claudesprint/config.toml) - per-project settings
        3. Global config (~/.config/claudesprint/config.toml) - shared defaults
        4. Hardcoded defaults

        Args:
            project_root: Path to the project root directory

        Returns:
            ClaudesprintConfig instance configured for the project
        """
        claude_dir = os.path.join(project_root, ".claude")
        claudesprint_dir = os.path.join(project_root, ".claudesprint")

        # Build kwargs with path settings first
        kwargs: dict[str, Any] = {
            "claude_dir": claude_dir,
            "project_dir": os.path.join(claudesprint_dir, "project"),
            "claudesprint_dir": claudesprint_dir,
            "prompts_dir": os.path.join(claudesprint_dir, "prompts"),
        }

        # Load global config defaults first (lowest precedence)
        global_defaults = cls._get_global_defaults()

        # All config fields that can be loaded from config files
        config_fields = [
            "max_retry",
            "max_total_iterations",
            "claude_timeout",
            "total_timeout",
            "rate_limit_retries",
            "rate_limit_base_wait",
            "rate_limit_max_wait",
            "heartbeat_enabled",
            "heartbeat_timeout",
            "heartbeat_check_interval",
            "debug_conversations",
            "kill_timeout",
            "git_timeout",
            "http_timeout",
            "issue_delay",
            "min_output_length",
            "version_check_timeout",
            "install_timeout",
        ]

        # Apply global config defaults (fallback)
        for field_name in config_fields:
            if field_name in global_defaults:
                kwargs[field_name] = global_defaults[field_name]

        # Load project config values (higher precedence than global)
        project_config = cls._get_project_config_values(project_root)

        # Apply project config values (overrides global defaults)
        for field_name in config_fields:
            if field_name in project_config:
                kwargs[field_name] = project_config[field_name]

        return cls(**kwargs)

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

    @property
    def models_file(self) -> str:
        """Path to models.json configuration file."""
        return os.path.join(self.claudesprint_dir, "config", "models.json")
