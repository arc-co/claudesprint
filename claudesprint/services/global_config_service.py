"""Global configuration service for user-wide settings.

Manages ~/.config/claudesprint/config.toml (or platform-specific equivalent).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

# TOML parsing: use tomllib (3.11+) or tomli (backport for 3.10)
if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[import-not-found]

import tomli_w


class DefaultsConfig(BaseModel):
    """Default settings section."""

    model: str = Field(
        default="opus",
        description="Default model for all steps (opus, sonnet, haiku)",
    )
    max_retry: int = Field(
        default=5,
        ge=1,
        description="Maximum retries before giving up",
    )
    claude_timeout: int = Field(
        default=1800,
        ge=60,
        description="Timeout for individual Claude sessions (seconds)",
    )
    total_timeout: int = Field(
        default=28800,
        ge=0,
        description="Total runtime limit (seconds, 0 = unlimited)",
    )


class RateLimitingConfig(BaseModel):
    """Rate limiting settings section."""

    retries: int = Field(
        default=3,
        ge=0,
        description="Max rate limit retries (0 = exit immediately)",
    )
    base_wait: int = Field(
        default=60,
        ge=10,
        description="Base wait time for exponential backoff (seconds)",
    )
    max_wait: int = Field(
        default=900,
        ge=60,
        description="Maximum wait time for backoff (seconds)",
    )


class HeartbeatConfig(BaseModel):
    """Heartbeat monitoring settings section."""

    enabled: bool = Field(
        default=True,
        description="Enable hung process detection",
    )
    timeout: int = Field(
        default=600,
        ge=60,
        description="Seconds of inactivity before notification",
    )


class DebugConfig(BaseModel):
    """Debug settings section."""

    conversations: bool = Field(
        default=False,
        description="Log full agent inputs/outputs",
    )


class GlobalConfig(BaseModel):
    """Global configuration model with all sections."""

    defaults: DefaultsConfig = Field(default_factory=DefaultsConfig)
    rate_limiting: RateLimitingConfig = Field(default_factory=RateLimitingConfig)
    heartbeat: HeartbeatConfig = Field(default_factory=HeartbeatConfig)
    debug: DebugConfig = Field(default_factory=DebugConfig)


# Default config TOML template (used for init)
DEFAULT_CONFIG_TOML = """\
# ~/.config/claudesprint/config.toml
# Global configuration for ClaudeSprint

[defaults]
# Default model for all steps (opus, sonnet, haiku)
model = "opus"

# Maximum retries before giving up
max_retry = 5

# Timeout for individual Claude sessions (seconds)
claude_timeout = 1800  # 30 minutes

# Total runtime limit (seconds, 0 = unlimited)
total_timeout = 28800  # 8 hours

[rate_limiting]
# Max rate limit retries (0 = exit immediately)
retries = 3

# Base wait time for exponential backoff (seconds)
base_wait = 60

# Maximum wait time for backoff (seconds)
max_wait = 900  # 15 minutes

[heartbeat]
# Enable hung process detection
enabled = true

# Seconds of inactivity before notification
timeout = 600  # 10 minutes

[debug]
# Log full agent inputs/outputs
conversations = false
"""


class GlobalConfigService:
    """Service for managing global user configuration.

    Handles loading/saving config.toml from platform-specific locations.

    Location precedence:
    1. CLAUDESPRINT_CONFIG_HOME environment variable
    2. Platform-specific default:
       - Linux: $XDG_CONFIG_HOME/claudesprint or ~/.config/claudesprint
       - macOS: ~/.config/claudesprint
       - Windows: %APPDATA%/claudesprint
    """

    def __init__(self, config_path: Path | str | None = None) -> None:
        """Initialize the service.

        Args:
            config_path: Optional explicit path to config.toml.
                        If None, uses default platform-specific location.
        """
        if config_path:
            self._config_path = Path(config_path)
        else:
            self._config_path = self.get_default_config_path()
        self._config: GlobalConfig | None = None

    @staticmethod
    def get_default_config_path() -> Path:
        """Get the default config file path for the current platform.

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

    @property
    def config_path(self) -> Path:
        """Get the config file path."""
        return self._config_path

    @property
    def config_dir(self) -> Path:
        """Get the config directory path."""
        return self._config_path.parent

    def exists(self) -> bool:
        """Check if the config file exists."""
        return self._config_path.exists()

    def load(self) -> GlobalConfig:
        """Load configuration from TOML file.

        Returns:
            GlobalConfig instance (uses defaults if file doesn't exist)
        """
        if self._config is not None:
            return self._config

        if not self._config_path.exists():
            self._config = GlobalConfig()
            return self._config

        try:
            with open(self._config_path, "rb") as f:
                data = tomllib.load(f)
            self._config = GlobalConfig(**data)
        except (OSError, tomllib.TOMLDecodeError) as e:
            # Log error but return defaults
            # In production, consider logging this
            _ = e  # Suppress unused variable warning
            self._config = GlobalConfig()

        return self._config

    def save(self, config: GlobalConfig | None = None) -> bool:
        """Save configuration to TOML file.

        Args:
            config: Configuration to save. If None, saves current config.

        Returns:
            True if save was successful
        """
        if config is None:
            config = self.load()

        try:
            # Ensure directory exists
            self._config_path.parent.mkdir(parents=True, exist_ok=True)

            # Convert to dict for TOML serialization
            data = config.model_dump()

            with open(self._config_path, "wb") as f:
                tomli_w.dump(data, f)

            self._config = config
            return True
        except OSError:
            return False

    def init_config(self, overwrite: bool = False) -> bool:
        """Initialize config file with default template.

        Args:
            overwrite: If True, overwrite existing file

        Returns:
            True if file was created/written
        """
        if self._config_path.exists() and not overwrite:
            return False

        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            self._config_path.write_text(DEFAULT_CONFIG_TOML)
            self._config = None  # Clear cache
            return True
        except OSError:
            return False

    def get(self, section: str, key: str, default: Any = None) -> Any:
        """Get a specific configuration value.

        Args:
            section: Config section (defaults, rate_limiting, heartbeat, debug)
            key: Key within the section
            default: Default value if not found

        Returns:
            Configuration value or default
        """
        config = self.load()
        section_obj = getattr(config, section, None)
        if section_obj is None:
            return default
        return getattr(section_obj, key, default)

    def get_flat_dict(self) -> dict[str, Any]:
        """Get configuration as a flat dictionary for easy access.

        Returns:
            Dict with keys like 'max_retry', 'rate_limit_retries', etc.
        """
        config = self.load()
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

    def reload(self) -> GlobalConfig:
        """Force reload configuration from disk.

        Returns:
            Fresh GlobalConfig instance
        """
        self._config = None
        return self.load()
