"""Model selection service for per-step Claude model configuration.

This service determines which Claude model to use for each workflow step,
enabling cost optimization by using sonnet for lower-stakes steps while
preserving opus for critical judgment steps.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from claudesprint.models.current_issue import IssueStep

if TYPE_CHECKING:
    from claudesprint.services.project_config_service import ProjectConfigService

# Import ModelName from project_config_service to ensure consistent type definition
from claudesprint.services.project_config_service import ModelName


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


class ModelsService:
    """Service for determining which model to use for each step.

    Resolution order:
    1. CLAUDESPRINT_MODEL_OVERRIDE env var (if set, forces all steps to use this model)
    2. config.toml model_override field (if set)
    3. config.toml step models for the specific step
    4. STEP_DEFAULT_MODELS for the step
    5. config.toml default_model
    6. Fall back to "opus"
    """

    def __init__(self) -> None:
        """Initialize the models service."""
        self._project_config_service: ProjectConfigService | None = None

    @classmethod
    def from_project_config(
        cls, project_config_service: "ProjectConfigService"
    ) -> "ModelsService":
        """Create a ModelsService that reads from ProjectConfigService.

        Args:
            project_config_service: The project config service to use.

        Returns:
            ModelsService instance configured to use TOML config.
        """
        instance = cls()
        instance._project_config_service = project_config_service
        return instance

    def get_model_for_step(self, step: IssueStep | str) -> ModelName:
        """Get the model to use for a workflow step.

        Args:
            step: The workflow step (IssueStep or string).

        Returns:
            Model name ("opus", "sonnet", or "haiku").
        """
        # 1. Check environment variable override
        env_override = os.environ.get("CLAUDESPRINT_MODEL_OVERRIDE", "").lower()
        if env_override in ("opus", "sonnet", "haiku"):
            return env_override  # type: ignore

        # Normalize step to string
        step_name = step.value if isinstance(step, IssueStep) else str(step)

        # 2. Check TOML project config if available
        if self._project_config_service is not None:
            return self._project_config_service.get_model_for_step(step_name)

        # 3. Check STEP_DEFAULT_MODELS
        if isinstance(step, IssueStep) and step in STEP_DEFAULT_MODELS:
            return STEP_DEFAULT_MODELS[step]

        # 4. Fall back to opus
        return "opus"

    def get_model_for_special_step(self, step_name: str) -> ModelName:
        """Get the model for a special step (init, plan).

        Args:
            step_name: The special step name (e.g., "init", "plan").

        Returns:
            Model name ("opus", "sonnet", or "haiku").
        """
        # 1. Check environment variable override
        env_override = os.environ.get("CLAUDESPRINT_MODEL_OVERRIDE", "").lower()
        if env_override in ("opus", "sonnet", "haiku"):
            return env_override  # type: ignore

        # 2. Check TOML project config if available
        if self._project_config_service is not None:
            return self._project_config_service.get_model_for_special_step(step_name)

        # 3. Fall back to defaults (init=opus, plan=sonnet)
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

    @property
    def config(self) -> "ProjectConfigService":
        """Get the project config service (for backward compatibility with CLI models command)."""
        if self._project_config_service is None:
            raise ValueError("ModelsService not initialized with project config")
        return self._project_config_service
