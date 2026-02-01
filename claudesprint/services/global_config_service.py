"""Global configuration models for user-wide settings.

Contains Pydantic models for global configuration.
Use ConfigurationManager to load and manage these configurations.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


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


