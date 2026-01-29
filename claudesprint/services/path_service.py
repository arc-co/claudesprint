"""Resource service for ClaudeSprint package assets.

This module provides access to package-bundled resources (prompts, schemas)
via importlib.resources. For path resolution, use ConfigurationManager.
"""

from functools import cached_property
from importlib.resources import files
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from importlib.resources.abc import Traversable


class PathService:
    """Package asset service for ClaudeSprint.

    Provides access to package-bundled resources (prompts, schemas) via
    importlib.resources.

    For path resolution, use ConfigurationManager instead.

    Example:
        >>> paths = PathService()
        >>> content = paths.get_prompt_content("init")
        >>> schema = paths.get_schema_content("sprint")
    """

    def __init__(self, project_root: Path | str | None = None) -> None:
        """Initialize PathService.

        Args:
            project_root: Optional project root path (kept for compatibility
                with PromptService which needs it for hierarchical loading).
        """
        if project_root is None:
            from claudesprint.services.configuration_manager import ConfigurationManager
            discovered = ConfigurationManager.discover_project_root()
            self._project_root = discovered or Path.cwd()
        else:
            self._project_root = Path(project_root)

    # === Package Assets (importlib.resources) ===

    @cached_property
    def _prompts_pkg(self) -> "Traversable":
        """Get the prompts package resource."""
        return files("claudesprint.prompts")

    @cached_property
    def _schemas_pkg(self) -> "Traversable":
        """Get the schemas package resource."""
        return files("claudesprint.schemas")

    def get_prompt_content(self, step: str) -> str:
        """Get prompt content for a workflow step.

        Args:
            step: The workflow step name (e.g., "init", "implement", "run-tests")

        Returns:
            The prompt file content as a string

        Raises:
            FileNotFoundError: If the prompt file doesn't exist
        """
        resource = self._prompts_pkg.joinpath(f"PROMPT_{step}.xml.j2")
        if not resource.is_file():
            raise FileNotFoundError(f"Prompt not found: PROMPT_{step}.xml.j2")
        content: str = resource.read_text(encoding="utf-8")
        return content

    def get_common_prompt_content(self) -> str:
        """Get common prompt patterns.

        Returns:
            The common prompt content as a string

        Raises:
            FileNotFoundError: If _common.xml.j2 doesn't exist
        """
        resource = self._prompts_pkg.joinpath("_common.xml.j2")
        if not resource.is_file():
            raise FileNotFoundError("Common prompt not found: _common.xml.j2")
        content: str = resource.read_text(encoding="utf-8")
        return content

    def get_schema_content(self, name: str) -> str:
        """Get JSON schema content by name.

        Args:
            name: Schema name without extension (e.g., "sprint", "current_issue")

        Returns:
            The schema file content as a string

        Raises:
            FileNotFoundError: If the schema file doesn't exist
        """
        resource = self._schemas_pkg.joinpath(f"{name}.schema.json")
        if not resource.is_file():
            raise FileNotFoundError(f"Schema not found: {name}.schema.json")
        content: str = resource.read_text(encoding="utf-8")
        return content

    def list_available_prompts(self) -> list[str]:
        """List available prompt step names.

        Returns:
            List of step names (e.g., ["init", "implement", "run-tests"])
        """
        prompts = []
        for item in self._prompts_pkg.iterdir():
            name = item.name
            if name.startswith("PROMPT_") and name.endswith(".xml.j2"):
                step_name = name.replace("PROMPT_", "").replace(".xml.j2", "")
                prompts.append(step_name)
        return sorted(prompts)

    def prompt_exists(self, step: str) -> bool:
        """Check if a prompt exists for a given step.

        Args:
            step: The workflow step name

        Returns:
            True if the prompt exists, False otherwise
        """
        resource = self._prompts_pkg.joinpath(f"PROMPT_{step}.xml.j2")
        result: bool = resource.is_file()
        return result

    def schema_exists(self, name: str) -> bool:
        """Check if a schema exists.

        Args:
            name: Schema name without extension

        Returns:
            True if the schema exists, False otherwise
        """
        resource = self._schemas_pkg.joinpath(f"{name}.schema.json")
        result: bool = resource.is_file()
        return result

    # === Kept for PromptService compatibility ===

    @property
    def project_root(self) -> Path:
        """The discovered or configured project root directory.

        Note: Kept for PromptService which needs project_root for
        hierarchical prompt loading.
        """
        return self._project_root
