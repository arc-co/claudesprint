"""Model selection service for per-step Claude model configuration.

This service determines which Claude model to use for each workflow step,
enabling cost optimization by using sonnet for lower-stakes steps while
preserving opus for critical judgment steps.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from claudesprint.models.current_issue import IssueStep

ModelName = Literal["opus", "sonnet"]


# Default model mappings for issue steps
STEP_DEFAULT_MODELS: dict[IssueStep, ModelName] = {
    IssueStep.SELECT_ISSUE: "sonnet",  # Algorithmic selection
    IssueStep.READ_DOCS: "sonnet",  # Research/summarization
    IssueStep.IMPLEMENT: "opus",  # Core code generation - quality critical
    IssueStep.WRITE_TESTS: "sonnet",  # Pattern-based - failures caught by run-tests
    IssueStep.RUN_TESTS: "sonnet",  # Automated step, model not used
    IssueStep.FIX_TESTS: "opus",  # Nuanced judgment (code bug vs test bug)
    IssueStep.BROWSER_VALIDATION: "sonnet",  # Procedural agent-browser commands
    IssueStep.CODE_REVIEW: "opus",  # Critical quality gate
    IssueStep.FIX_CODE_REVIEW_ISSUES: "sonnet",  # Targeted fixes
    IssueStep.UPDATE_DOCS: "sonnet",  # Formulaic documentation updates
    IssueStep.STAGE_CHANGES: "sonnet",  # Automated step
    IssueStep.COMMIT_CHANGES: "sonnet",  # Automated step
    IssueStep.COMPLETE_ISSUE: "sonnet",  # Automated step
}


@dataclass
class ModelsConfig:
    """Configuration for per-step model selection."""

    default_model: ModelName = "opus"
    model_override: ModelName | None = None  # Force all steps to use this model
    step_models: dict[str, ModelName] | None = None
    special_step_models: dict[str, ModelName] | None = None

    @classmethod
    def from_file(cls, config_path: str | Path) -> "ModelsConfig":
        """Load configuration from JSON file.

        Args:
            config_path: Path to models.json config file.

        Returns:
            ModelsConfig instance, falling back to defaults if file missing.
        """
        path = Path(config_path)
        if not path.exists():
            return cls()

        try:
            with open(path) as f:
                data = json.load(f)
            return cls(
                default_model=data.get("default_model", "opus"),
                model_override=data.get("model_override"),
                step_models=data.get("step_models"),
                special_step_models=data.get("special_step_models"),
            )
        except (json.JSONDecodeError, OSError):
            return cls()


class ModelsService:
    """Service for determining which model to use for each step.

    Resolution order:
    1. CLAUDESPRINT_MODEL_OVERRIDE env var (if set, forces all steps to use this model)
    2. models.json model_override field (if set)
    3. models.json step_models for the specific step
    4. STEP_DEFAULT_MODELS for the step
    5. models.json default_model
    6. Fall back to "opus"
    """

    def __init__(self, config_path: str | Path | None = None) -> None:
        """Initialize the models service.

        Args:
            config_path: Path to models.json. If None, uses default location.
        """
        self.config_path = config_path
        self._config: ModelsConfig | None = None

    @property
    def config(self) -> ModelsConfig:
        """Lazy load configuration."""
        if self._config is None:
            if self.config_path:
                self._config = ModelsConfig.from_file(self.config_path)
            else:
                self._config = ModelsConfig()
        return self._config

    def reload_config(self) -> None:
        """Force reload of configuration from file."""
        self._config = None

    def get_model_for_step(self, step: IssueStep | str) -> ModelName:
        """Get the model to use for a workflow step.

        Args:
            step: The workflow step (IssueStep or string).

        Returns:
            Model name ("opus" or "sonnet").
        """
        # 1. Check environment variable override
        env_override = os.environ.get("CLAUDESPRINT_MODEL_OVERRIDE", "").lower()
        if env_override in ("opus", "sonnet"):
            return env_override  # type: ignore

        # 2. Check config file override
        if self.config.model_override in ("opus", "sonnet"):
            return self.config.model_override

        # Normalize step to string
        step_name = step.value if isinstance(step, IssueStep) else str(step)

        # 3. Check config file step_models
        if self.config.step_models and step_name in self.config.step_models:
            model = self.config.step_models[step_name]
            if model in ("opus", "sonnet"):
                return model  # type: ignore

        # 4. Check STEP_DEFAULT_MODELS
        if isinstance(step, IssueStep) and step in STEP_DEFAULT_MODELS:
            return STEP_DEFAULT_MODELS[step]

        # 5. Check config file default_model
        if self.config.default_model in ("opus", "sonnet"):
            return self.config.default_model

        # 6. Fall back to opus
        return "opus"

    def get_model_for_special_step(self, step_name: str) -> ModelName:
        """Get the model for a special step (init, plan).

        Args:
            step_name: The special step name (e.g., "init", "plan").

        Returns:
            Model name ("opus" or "sonnet").
        """
        # 1. Check environment variable override
        env_override = os.environ.get("CLAUDESPRINT_MODEL_OVERRIDE", "").lower()
        if env_override in ("opus", "sonnet"):
            return env_override  # type: ignore

        # 2. Check config file override
        if self.config.model_override in ("opus", "sonnet"):
            return self.config.model_override

        # 3. Check config file special_step_models
        if self.config.special_step_models and step_name in self.config.special_step_models:
            model = self.config.special_step_models[step_name]
            if model in ("opus", "sonnet"):
                return model  # type: ignore

        # 4. Fall back to defaults (init=opus, plan=sonnet)
        defaults = {"init": "opus", "plan": "sonnet"}
        return defaults.get(step_name, "opus")  # type: ignore

    def get_step_model_summary(self) -> dict[str, ModelName]:
        """Get a summary of which model each step will use.

        Useful for debugging and status display.

        Returns:
            Dict mapping step names to their resolved models.
        """
        summary: dict[str, ModelName] = {}

        # Regular workflow steps
        for step in IssueStep:
            summary[step.value] = self.get_model_for_step(step)

        # Special steps
        for special in ["init", "plan"]:
            summary[special] = self.get_model_for_special_step(special)

        return summary
