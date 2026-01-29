"""Project configuration models for .claudesprint/config.toml.

Contains Pydantic models for project-level configuration.
Use ConfigurationManager to load and manage these configurations.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


ModelName = Literal["opus", "sonnet", "haiku"]


class ServerConfig(BaseModel):
    """Development server configuration."""

    url: str = Field(
        default="http://localhost:3000",
        description="Development server URL for browser validation",
    )
    start_command: str = Field(
        default="npm run dev",
        description="Command to start the development server",
    )
    wait_seconds: int = Field(
        default=5,
        ge=1,
        description="Seconds to wait for server to start",
    )


class ModelsStepsConfig(BaseModel):
    """Per-step model configuration."""

    read_docs: ModelName = Field(default="sonnet", alias="read-docs")
    implement: ModelName = Field(default="opus")
    write_tests: ModelName = Field(default="sonnet", alias="write-tests")
    fix_tests: ModelName = Field(default="opus", alias="fix-tests")
    browser_validation: ModelName = Field(default="sonnet", alias="browser-validation")
    code_review: ModelName = Field(default="opus", alias="code-review")
    fix_code_review_issues: ModelName = Field(
        default="sonnet", alias="fix-code-review-issues"
    )
    update_docs: ModelName = Field(default="sonnet", alias="update-docs")

    model_config = {"populate_by_name": True}


class ModelsSpecialConfig(BaseModel):
    """Special step model configuration."""

    init: ModelName = Field(default="opus")
    plan: ModelName = Field(default="sonnet")


class ModelsConfig(BaseModel):
    """Model selection configuration."""

    default_model: ModelName = Field(
        default="opus",
        description="Default model when not specified per-step",
    )
    model_override: ModelName | None = Field(
        default=None,
        description="Override to force all steps to use this model",
    )
    steps: ModelsStepsConfig = Field(default_factory=ModelsStepsConfig)
    special: ModelsSpecialConfig = Field(default_factory=ModelsSpecialConfig)


class RuntimeConfig(BaseModel):
    """Runtime execution configuration."""

    max_retry: int = Field(
        default=5,
        ge=1,
        description="Maximum retries before giving up on a step",
    )
    max_total_iterations: int = Field(
        default=50,
        ge=1,
        description="Maximum total step executions per issue (prevents infinite loops)",
    )
    claude_timeout: int = Field(
        default=1800,
        ge=60,
        description="Timeout for individual Claude sessions in seconds",
    )
    total_timeout: int = Field(
        default=28800,
        ge=0,
        description="Total runtime limit in seconds (0 = unlimited)",
    )


class RateLimitingConfig(BaseModel):
    """Rate limiting configuration."""

    retries: int = Field(
        default=3,
        ge=0,
        description="Max rate limit retries before exiting (0 = exit immediately)",
    )
    base_wait: int = Field(
        default=60,
        ge=10,
        description="Base wait time in seconds for exponential backoff",
    )
    max_wait: int = Field(
        default=900,
        ge=60,
        description="Maximum wait time in seconds for backoff",
    )


class HeartbeatConfig(BaseModel):
    """Heartbeat monitoring configuration."""

    enabled: bool = Field(
        default=True,
        description="Enable hung process detection",
    )
    timeout: int = Field(
        default=600,
        ge=60,
        description="Seconds of inactivity before notification",
    )
    check_interval: float = Field(
        default=10.0,
        ge=1.0,
        description="How often to check for inactivity in seconds",
    )


class DebugConfig(BaseModel):
    """Debug configuration."""

    conversations: bool = Field(
        default=False,
        description="Log full agent inputs/outputs to agent_conversations.log",
    )


class TimeoutsConfig(BaseModel):
    """Various timeout settings."""

    kill_timeout: int = Field(
        default=10,
        ge=1,
        description="Grace period before SIGKILL when terminating Claude",
    )
    git_timeout: int = Field(
        default=60,
        ge=10,
        description="Git command timeout in seconds",
    )
    http_timeout: float = Field(
        default=10.0,
        ge=1.0,
        description="HTTP request timeout for notifications in seconds",
    )
    issue_delay: float = Field(
        default=2.0,
        ge=0.0,
        description="Delay between processing issues in a sprint",
    )


class AdvancedConfig(BaseModel):
    """Advanced configuration settings."""

    min_output_length: int = Field(
        default=50,
        ge=1,
        description="Minimum output length to consider a Claude response valid",
    )
    version_check_timeout: int = Field(
        default=10,
        ge=1,
        description="Health check version check timeout in seconds",
    )
    install_timeout: int = Field(
        default=120,
        ge=10,
        description="Health check dependency install timeout in seconds",
    )


class BarkNotificationConfig(BaseModel):
    """Bark push notification configuration."""

    enabled: bool = Field(default=False, description="Enable Bark notifications")
    url: str = Field(default="", description="Bark server URL")


class NotificationsConfig(BaseModel):
    """Notification settings."""

    enabled: bool = Field(default=True, description="Enable notifications globally")
    bark: BarkNotificationConfig = Field(default_factory=BarkNotificationConfig)


class ProjectConfig(BaseModel):
    """Project configuration model with all sections."""

    server: ServerConfig = Field(default_factory=ServerConfig)
    models: ModelsConfig = Field(default_factory=ModelsConfig)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    rate_limiting: RateLimitingConfig = Field(default_factory=RateLimitingConfig)
    heartbeat: HeartbeatConfig = Field(default_factory=HeartbeatConfig)
    debug: DebugConfig = Field(default_factory=DebugConfig)
    timeouts: TimeoutsConfig = Field(default_factory=TimeoutsConfig)
    advanced: AdvancedConfig = Field(default_factory=AdvancedConfig)
    notifications: NotificationsConfig = Field(default_factory=NotificationsConfig)


# Default config TOML template
DEFAULT_PROJECT_CONFIG_TOML = """\
# .claudesprint/config.toml
# Project configuration for ClaudeSprint
#
# Configuration precedence (highest to lowest):
# 1. Environment variables (CLAUDESPRINT_*)
# 2. This file (.claudesprint/config.toml) - per-project settings
# 3. Global config (~/.config/claudesprint/config.toml) - shared defaults
# 4. Hardcoded defaults

[server]
# Development server URL for browser validation
url = "http://localhost:3000"

# Command to start the development server
start_command = "npm run dev"

# Seconds to wait for server to start
wait_seconds = 5

[models]
# Default model for all steps (opus, sonnet, haiku)
default_model = "opus"

# Uncomment to force all steps to use this model
# model_override = "sonnet"

[models.steps]
read-docs = "sonnet"
implement = "opus"
write-tests = "sonnet"
fix-tests = "opus"
browser-validation = "sonnet"
code-review = "opus"
fix-code-review-issues = "sonnet"
update-docs = "sonnet"

[models.special]
init = "opus"
plan = "sonnet"

[runtime]
# Maximum retries before giving up on a step
max_retry = 5

# Maximum total step executions per issue (prevents infinite loops)
max_total_iterations = 50

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

# How often to check for inactivity (seconds)
check_interval = 10.0

[debug]
# Log full agent inputs/outputs to agent_conversations.log
conversations = false

[timeouts]
# Grace period before SIGKILL when terminating Claude (seconds)
kill_timeout = 10

# Git command timeout (seconds)
git_timeout = 60

# HTTP request timeout for notifications (seconds)
http_timeout = 10.0

# Delay between processing issues in a sprint (seconds)
issue_delay = 2.0

[advanced]
# Minimum output length to consider a Claude response valid
min_output_length = 50

# Health check version check timeout (seconds)
version_check_timeout = 10

# Health check dependency install timeout (seconds)
install_timeout = 120

[notifications]
# Enable notifications globally
enabled = true

[notifications.bark]
# Enable Bark push notifications
enabled = false
# Bark server URL (e.g., "https://api.day.app/YOUR_KEY")
url = ""
"""


