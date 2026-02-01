"""Prompt service for hierarchical prompt loading with dynamic context injection.

This module provides:
- Hierarchical prompt loading (project → global → package)
- Dynamic context injection for dependency awareness
- Template rendering with Jinja2
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Any

from jinja2 import ChoiceLoader, Environment, FileSystemLoader, PackageLoader, TemplateError

from claudesprint.services.path_service import PathService

logger = logging.getLogger(__name__)


# Reserved keys that cannot be overridden by custom_vars without warning
_RESERVED_CONTEXT_KEYS = frozenset({"browser_validation_enabled", "context7_available", "examples_enabled"})


@dataclass
class PromptContext:
    """Context variables available for prompt template rendering.

    Attributes:
        browser_validation_enabled: True if agent-browser is available
        context7_available: True if context7 binary is available
        examples_enabled: True to include gold standard examples in prompts
        custom_vars: Additional user-defined variables.
        step_name: Name of the current workflow step (e.g., "implement", "run-tests")
        step_goal: Brief description of the step's goal
        sprint_json: Pretty-printed sprint data for context injection
        current_issue_json: Pretty-printed current_issue data for context injection
        log_tail: Session log (last 50 lines) for context injection
        current_failures: Failures if any, for context injection

    Warning:
        If custom_vars contains keys that match reserved context keys
        (browser_validation_enabled, context7_available, examples_enabled), a warning will
        be logged and the custom value will override the built-in value.
    """

    browser_validation_enabled: bool = False
    context7_available: bool = False
    examples_enabled: bool = True
    custom_vars: dict[str, Any] = field(default_factory=dict)

    # XML template context data
    step_name: str = ""
    step_goal: str = ""
    sprint_json: str = ""
    current_issue_json: str = ""
    log_tail: str = ""
    current_failures: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert context to dictionary for template rendering.

        Returns:
            Dictionary with all context variables
        """
        result = {
            "browser_validation_enabled": self.browser_validation_enabled,
            "context7_available": self.context7_available,
            "examples_enabled": self.examples_enabled,
            "step_name": self.step_name,
            "step_goal": self.step_goal,
            "sprint_json": self.sprint_json,
            "current_issue_json": self.current_issue_json,
            "log_tail": self.log_tail,
            "current_failures": self.current_failures,
        }
        # Warn if custom_vars shadows reserved keys
        shadowed_keys = _RESERVED_CONTEXT_KEYS & self.custom_vars.keys()
        if shadowed_keys:
            logger.warning(
                "custom_vars contains reserved keys that will override built-in values: %s",
                sorted(shadowed_keys),
            )
        result.update(self.custom_vars)
        return result


class PromptService:
    """Hierarchical prompt loading service with template rendering.

    Loads prompts in priority order:
    1. Project-level (.claudesprint/prompts/) - highest priority
    2. Global user-level (~/.config/claudesprint/prompts/)
    3. Package default (claudesprint/prompts/) - lowest priority

    Example:
        >>> from claudesprint.services import PathService, PromptService
        >>> path_service = PathService()
        >>> prompt_service = PromptService(path_service)
        >>> content = prompt_service.get_prompt_content("implement")
        >>> source = prompt_service.prompt_source("implement")
        >>> print(f"Loaded from: {source}")
    """

    def __init__(
        self,
        path_service: PathService,
        project_root: Path | str | None = None,
    ) -> None:
        """Initialize PromptService.

        Args:
            path_service: PathService instance for package resource access
            project_root: Optional explicit project root. If None, uses
                         path_service.project_root.

        Raises:
            ValueError: If no project root can be determined (both project_root
                       parameter and path_service.project_root are None).
        """
        self._path_service = path_service

        # Determine project root with explicit None check
        resolved_root: Path | None
        if project_root is not None:
            resolved_root = Path(project_root)
        else:
            resolved_root = path_service.project_root

        if resolved_root is None:
            raise ValueError(
                "project_root must be provided either directly or via path_service.project_root"
            )

        self._project_root: Path = resolved_root

        # Initialize Jinja2 environment with ChoiceLoader for template inheritance
        # Priority: project > global > package
        self._jinja_env = Environment(
            loader=ChoiceLoader([
                FileSystemLoader(str(self.project_prompts_dir)),
                FileSystemLoader(str(self.global_prompts_dir)),
                PackageLoader('claudesprint', 'prompts'),
            ]),
            autoescape=False,  # Prompts are XML/text, not HTML
            trim_blocks=True,
            lstrip_blocks=True,
        )

    # === Directory Properties ===

    @property
    def project_prompts_dir(self) -> Path:
        """Path to project-level prompts directory (.claudesprint/prompts/)."""
        return self._project_root / ".claudesprint" / "prompts"

    @property
    def global_prompts_dir(self) -> Path:
        """Path to global user-level prompts directory.

        Location varies by platform:
        - Linux: $XDG_CONFIG_HOME/claudesprint/prompts or ~/.config/claudesprint/prompts
        - macOS: ~/.config/claudesprint/prompts
        - Windows: %APPDATA%/claudesprint/prompts
        """
        # Check for environment variable override
        env_home = os.environ.get("CLAUDESPRINT_CONFIG_HOME")
        if env_home:
            return Path(env_home) / "prompts"

        # Platform-specific paths
        if sys.platform == "win32":
            appdata = os.environ.get("APPDATA")
            if appdata:
                return Path(appdata) / "claudesprint" / "prompts"
            return Path.home() / "AppData" / "Roaming" / "claudesprint" / "prompts"
        else:
            xdg_config = os.environ.get("XDG_CONFIG_HOME")
            if xdg_config:
                return Path(xdg_config) / "claudesprint" / "prompts"
            return Path.home() / ".config" / "claudesprint" / "prompts"

    # === Prompt Loading (Hierarchical) ===

    def get_prompt_content(self, step: str, *, render: bool = True) -> str:
        """Get prompt content for a workflow step.

        Loads from hierarchy: project → global → package.
        Uses Jinja2 template inheritance for .xml.j2 templates.

        Args:
            step: The workflow step name (e.g., "init", "implement", "run-tests")
            render: If True, render Jinja2 template with context

        Returns:
            The prompt file content as a string

        Raises:
            FileNotFoundError: If the prompt file doesn't exist anywhere
        """
        prompt_filename = f"PROMPT_{step}.xml.j2"

        # Try project-level first
        project_path = self.project_prompts_dir / prompt_filename
        if project_path.is_file():
            logger.debug("Loading prompt '%s' from project: %s", step, project_path)
            if render:
                return self._render_template_file(prompt_filename)
            return project_path.read_text(encoding="utf-8")

        # Try global-level second
        global_path = self.global_prompts_dir / prompt_filename
        if global_path.is_file():
            logger.debug("Loading prompt '%s' from global: %s", step, global_path)
            if render:
                return self._render_template_file(prompt_filename)
            return global_path.read_text(encoding="utf-8")

        # Fall back to package default
        logger.debug("Loading prompt '%s' from package", step)
        content = self._path_service.get_prompt_content(step)
        if render:
            return self._render_template_file(prompt_filename)
        return content

    def get_common_prompt_content(self, *, render: bool = True) -> str:
        """Get common prompt content.

        Loads from hierarchy: project → global → package.
        Note: For XML templates, common content is included via {% include '_common.xml.j2' %}
        in the base template, so this method is primarily for backwards compatibility.

        Args:
            render: If True, render Jinja2 template with context

        Returns:
            The common prompt content as a string

        Raises:
            FileNotFoundError: If _common.xml.j2 doesn't exist anywhere
        """
        common_filename = "_common.xml.j2"

        # Try project-level first
        project_path = self.project_prompts_dir / common_filename
        if project_path.is_file():
            content = project_path.read_text(encoding="utf-8")
            return self._render_template(content) if render else content

        # Try global-level second
        global_path = self.global_prompts_dir / common_filename
        if global_path.is_file():
            content = global_path.read_text(encoding="utf-8")
            return self._render_template(content) if render else content

        # Fall back to package default
        content = self._path_service.get_common_prompt_content()
        return self._render_template(content) if render else content

    def prompt_source(self, step: str) -> str:
        """Determine the source of a prompt.

        Args:
            step: The workflow step name

        Returns:
            Source identifier: "project", "global", or "package"

        Raises:
            FileNotFoundError: If the prompt doesn't exist anywhere
        """
        prompt_filename = f"PROMPT_{step}.xml.j2"

        # Check project-level
        project_path = self.project_prompts_dir / prompt_filename
        if project_path.is_file():
            return "project"

        # Check global-level
        global_path = self.global_prompts_dir / prompt_filename
        if global_path.is_file():
            return "global"

        # Check package (will raise FileNotFoundError if not found)
        if self._path_service.prompt_exists(step):
            return "package"

        raise FileNotFoundError(f"Prompt not found: PROMPT_{step}.xml.j2")

    def prompt_exists(self, step: str) -> bool:
        """Check if a prompt exists in any source.

        Args:
            step: The workflow step name

        Returns:
            True if prompt exists in project, global, or package
        """
        prompt_filename = f"PROMPT_{step}.xml.j2"

        # Check project-level
        if (self.project_prompts_dir / prompt_filename).is_file():
            return True

        # Check global-level
        if (self.global_prompts_dir / prompt_filename).is_file():
            return True

        # Check package
        return self._path_service.prompt_exists(step)

    # === Context Detection ===

    @cached_property
    def context(self) -> PromptContext:
        """Get the current prompt context with detected dependencies.

        Lazily evaluates and caches dependency detection.
        Use reload_context() to force re-detection.

        Returns:
            PromptContext with dependency flags
        """
        return self._detect_context()

    def reload_context(self) -> PromptContext:
        """Force re-detection of context dependencies.

        Returns:
            Fresh PromptContext with updated dependency flags
        """
        # Clear cached_property by removing from instance __dict__
        if "context" in self.__dict__:
            del self.__dict__["context"]
        return self.context

    def set_context(self, context: PromptContext) -> None:
        """Set the context explicitly (useful for testing).

        Args:
            context: PromptContext to use for template rendering
        """
        self.__dict__["context"] = context

    def _detect_context(self) -> PromptContext:
        """Detect available dependencies and build context.

        Uses OptionalFeaturesService for centralized feature detection.

        Returns:
            PromptContext with detected dependency states
        """
        from claudesprint.services.optional_features_service import OptionalFeaturesService

        features_service = OptionalFeaturesService()
        detected = features_service.detect_all()

        return PromptContext(
            browser_validation_enabled=detected.get("agent-browser", False),
            context7_available=detected.get("context7", False),
        )

    # === Template Rendering ===

    def _render_template(self, content: str) -> str:
        """Render Jinja2 template with current context.

        Args:
            content: Template content string

        Returns:
            Rendered content, or original content if template is invalid
        """
        try:
            template = self._jinja_env.from_string(content)
            rendered: str = template.render(self.context.to_dict())
            return rendered
        except TemplateError as e:
            logger.warning("Failed to render template: %s", e)
            return content

    def _render_template_file(self, template_name: str) -> str:
        """Render a Jinja2 template file with current context.

        Uses the ChoiceLoader to find templates in priority order:
        project > global > package. Supports template inheritance
        via {% extends '_base.xml.j2' %}.

        Args:
            template_name: Name of the template file (e.g., 'PROMPT_implement.xml.j2')

        Returns:
            Rendered template content

        Raises:
            FileNotFoundError: If template is not found in any location
        """
        try:
            template = self._jinja_env.get_template(template_name)
            rendered: str = template.render(self.context.to_dict())
            return rendered
        except TemplateError as e:
            logger.warning("Failed to render template %s: %s", template_name, e)
            raise FileNotFoundError(f"Template not found or invalid: {template_name}") from e

    def render_with_context(
        self,
        content: str,
        extra_context: dict[str, Any] | None = None,
    ) -> str:
        """Render template with context and optional extra variables.

        Args:
            content: Template content string
            extra_context: Additional variables to add to context

        Returns:
            Rendered content
        """
        context_dict = self.context.to_dict()
        if extra_context:
            context_dict.update(extra_context)

        try:
            template = self._jinja_env.from_string(content)
            rendered: str = template.render(context_dict)
            return rendered
        except TemplateError as e:
            logger.warning("Failed to render template: %s", e)
            return content
