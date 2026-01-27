"""Project configuration service for .claudesprint/config.toml.

Manages project-level configuration that consolidates settings from
hooks.json, models.json, and project.json into a single TOML file.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# TOML parsing: use tomllib (3.11+) or tomli (backport for 3.10)
if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[import-not-found]

import tomli_w


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


class HookConfig(BaseModel):
    """Configuration for a single hook."""

    command: str = Field(description="Shell command to execute")
    timeout: int = Field(default=300, ge=1, description="Timeout in seconds")
    success_exit_codes: list[int] = Field(
        default_factory=lambda: [0],
        description="Exit codes that indicate success",
    )
    failure_patterns: list[str] = Field(
        default_factory=list,
        description="Patterns in output that indicate failure",
    )
    success_patterns: list[str] = Field(
        default_factory=list,
        description="Patterns in output that indicate success",
    )


class HooksConfig(BaseModel):
    """Hooks configuration section.

    Note: The 'validate' hook uses 'validate_hook' as the attribute name
    because 'validate' conflicts with Pydantic's BaseModel.validate method.
    The alias="validate" ensures TOML files use [hooks.validate] as expected.
    """

    model_config = {"protected_namespaces": ()}  # Allow 'validate' field name

    test: HookConfig = Field(
        default_factory=lambda: HookConfig(
            command="npm test",
            timeout=300,
            success_exit_codes=[0],
            failure_patterns=["FAIL", "failed", "Error:"],
            success_patterns=["passed", "PASS"],
        )
    )
    lint: HookConfig = Field(
        default_factory=lambda: HookConfig(
            command="npm run lint",
            timeout=120,
            success_exit_codes=[0],
            failure_patterns=["error", "warning"],
        )
    )
    typecheck: HookConfig = Field(
        default_factory=lambda: HookConfig(
            command="npm run typecheck",
            timeout=120,
            success_exit_codes=[0],
            failure_patterns=["error TS", "Error:"],
        )
    )
    build: HookConfig = Field(
        default_factory=lambda: HookConfig(
            command="npm run build",
            timeout=300,
            success_exit_codes=[0],
            failure_patterns=["error", "Error:", "failed"],
            success_patterns=["Successfully", "Built"],
        )
    )
    validate_hook: HookConfig = Field(
        default_factory=lambda: HookConfig(
            command="npm run validate",
            timeout=600,
            success_exit_codes=[0],
            failure_patterns=["FAIL", "error", "Error:"],
        ),
        alias="validate",
    )


class ProjectConfig(BaseModel):
    """Project configuration model with all sections."""

    server: ServerConfig = Field(default_factory=ServerConfig)
    models: ModelsConfig = Field(default_factory=ModelsConfig)
    hooks: HooksConfig = Field(default_factory=HooksConfig)


# Default config TOML template
DEFAULT_PROJECT_CONFIG_TOML = """\
# .claudesprint/config.toml
# Project configuration for ClaudeSprint

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

[hooks.test]
command = "npm test"
timeout = 300
success_exit_codes = [0]
failure_patterns = ["FAIL", "failed", "Error:"]
success_patterns = ["passed", "PASS"]

[hooks.lint]
command = "npm run lint"
timeout = 120
success_exit_codes = [0]
failure_patterns = ["error", "warning"]

[hooks.typecheck]
command = "npm run typecheck"
timeout = 120
success_exit_codes = [0]
failure_patterns = ["error TS", "Error:"]

[hooks.build]
command = "npm run build"
timeout = 300
success_exit_codes = [0]
failure_patterns = ["error", "Error:", "failed"]
success_patterns = ["Successfully", "Built"]

[hooks.validate]
command = "npm run validate"
timeout = 600
success_exit_codes = [0]
failure_patterns = ["FAIL", "error", "Error:"]
"""


class ProjectConfigService:
    """Service for managing project-level configuration.

    Handles loading/saving .claudesprint/config.toml.
    """

    CONFIG_FILENAME = "config.toml"

    def __init__(self, project_root: Path | str | None = None) -> None:
        """Initialize the service.

        Args:
            project_root: Project root directory containing .claudesprint/.
                         If None, uses current working directory.
        """
        if project_root is None:
            self._project_root = Path.cwd()
        else:
            self._project_root = Path(project_root)

        self._config_path = (
            self._project_root / ".claudesprint" / self.CONFIG_FILENAME
        )
        self._config: ProjectConfig | None = None

    @property
    def config_path(self) -> Path:
        """Get the config file path."""
        return self._config_path

    @property
    def project_root(self) -> Path:
        """Get the project root directory."""
        return self._project_root

    def exists(self) -> bool:
        """Check if the config file exists."""
        return self._config_path.exists()

    def load(self) -> ProjectConfig:
        """Load configuration from TOML file.

        Returns:
            ProjectConfig instance (uses defaults if file doesn't exist)
        """
        if self._config is not None:
            return self._config

        if not self._config_path.exists():
            self._config = ProjectConfig()
            return self._config

        try:
            with open(self._config_path, "rb") as f:
                data = tomllib.load(f)
            self._config = ProjectConfig(**data)
        except (OSError, tomllib.TOMLDecodeError) as e:
            logger.warning(
                "Failed to load config from %s: %s. Using defaults.",
                self._config_path,
                e,
            )
            self._config = ProjectConfig()

        return self._config

    def save(self, config: ProjectConfig | None = None) -> bool:
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
            # Use by_alias=True to get hyphenated keys like "read-docs"
            data = config.model_dump(by_alias=True, exclude_none=True)

            with open(self._config_path, "wb") as f:
                tomli_w.dump(data, f)

            self._config = config
            return True
        except OSError as e:
            logger.warning("Failed to save config to %s: %s", self._config_path, e)
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
            self._config_path.write_text(DEFAULT_PROJECT_CONFIG_TOML)
            self._config = None  # Clear cache
            return True
        except OSError as e:
            logger.warning("Failed to initialize config at %s: %s", self._config_path, e)
            return False

    def reload(self) -> ProjectConfig:
        """Force reload configuration from disk.

        Returns:
            Fresh ProjectConfig instance
        """
        self._config = None
        return self.load()

    def get_hook_config(self, hook_name: str) -> HookConfig | None:
        """Get configuration for a specific hook.

        Args:
            hook_name: Name of the hook (test, lint, typecheck, build, validate)

        Returns:
            HookConfig if found, None otherwise
        """
        config = self.load()
        # Handle 'validate' -> 'validate_hook' mapping
        attr_name = "validate_hook" if hook_name == "validate" else hook_name
        return getattr(config.hooks, attr_name, None)

    def get_model_for_step(self, step_name: str) -> ModelName:
        """Get the model to use for a workflow step.

        Args:
            step_name: Step name (e.g., "implement", "code-review")

        Returns:
            Model name
        """
        config = self.load()

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
        config = self.load()

        # Check for override
        if config.models.model_override:
            return config.models.model_override

        # Check special config
        special_model: ModelName | None = getattr(config.models.special, step_name, None)
        if special_model:
            return special_model

        # Fall back to default
        return config.models.default_model
