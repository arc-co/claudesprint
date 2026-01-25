"""Configuration models for ClaudeSprint."""

import os
from typing import Annotated

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


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
        alias="CLAUDESPRINT_MAX_RETRY",
    )
    claude_timeout: Annotated[int, Field(ge=60)] = Field(
        default=1800,
        description="Timeout for individual Claude sessions in seconds",
        alias="CLAUDESPRINT_CLAUDE_TIMEOUT",
    )
    total_timeout: Annotated[int, Field(ge=0)] = Field(
        default=28800,
        description="Total runtime limit in seconds (0 = unlimited)",
        alias="CLAUDESPRINT_TOTAL_TIMEOUT",
    )
    rate_limit_retries: Annotated[int, Field(ge=0)] = Field(
        default=3,
        description="Max rate limit retries before exiting (0 = exit immediately)",
        alias="CLAUDESPRINT_RATE_LIMIT_RETRIES",
    )
    rate_limit_base_wait: Annotated[int, Field(ge=10)] = Field(
        default=60,
        description="Base wait time in seconds for rate limit exponential backoff",
        alias="CLAUDESPRINT_RATE_LIMIT_BASE_WAIT",
    )
    rate_limit_max_wait: Annotated[int, Field(ge=60)] = Field(
        default=900,
        description="Maximum wait time in seconds for rate limit backoff (default 15 min)",
        alias="CLAUDESPRINT_RATE_LIMIT_MAX_WAIT",
    )
    max_rationale_entries: Annotated[int, Field(ge=5)] = Field(
        default=20,
        description="Maximum rationale entries to keep (oldest pruned first)",
        alias="CLAUDESPRINT_MAX_RATIONALE",
    )
    heartbeat_timeout: Annotated[int, Field(ge=60)] = Field(
        default=600,
        description="Seconds of inactivity before triggering hung process notification",
        alias="CLAUDESPRINT_HEARTBEAT_TIMEOUT",
    )
    heartbeat_enabled: bool = Field(
        default=True,
        description="Enable heartbeat monitoring for hung process detection",
        alias="CLAUDESPRINT_HEARTBEAT_ENABLED",
    )
    debug_conversations: bool = Field(
        default=False,
        description="Log full agent inputs and outputs to agent_conversations.log",
        alias="CLAUDESPRINT_DEBUG_CONVERSATIONS",
    )

    # Paths (derived from script location)
    claude_dir: str = Field(default="", description="Path to .claude directory")
    project_dir: str = Field(default="", description="Path to .claude/claudesprint/project directory")
    claudesprint_dir: str = Field(default="", description="Path to .claude/claudesprint directory")
    prompts_dir: str = Field(default="", description="Path to prompts directory (inside claudesprint)")

    model_config = {
        "env_file": ".claude/claudesprint/.env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @classmethod
    def from_project_root(cls, project_root: str) -> "ClaudesprintConfig":
        """Create config with paths derived from project root."""
        claude_dir = os.path.join(project_root, ".claude")
        claudesprint_dir = os.path.join(claude_dir, "claudesprint")
        return cls(
            claude_dir=claude_dir,
            project_dir=os.path.join(claudesprint_dir, "project"),
            claudesprint_dir=claudesprint_dir,
            prompts_dir=os.path.join(claudesprint_dir, "prompts"),
        )

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
