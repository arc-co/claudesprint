"""Path resolution service for ClaudeSprint.

This module provides centralized path resolution for ClaudeSprint:
- Package assets (prompts, schemas) are read via importlib.resources
- Local configuration is resolved relative to discovered project root
"""

from functools import cached_property
from importlib.resources import files
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from importlib.resources.abc import Traversable


class PathService:
    """Centralized path resolution for ClaudeSprint.

    Package assets are read from the installed package via importlib.resources.
    Local configuration is resolved relative to discovered project root.

    Example:
        >>> paths = PathService()
        >>> content = paths.get_prompt_content("init")
        >>> schema = paths.get_schema_content("sprint")
        >>> current_issue = paths.current_issue_file
    """

    def __init__(self, project_root: Path | str | None = None) -> None:
        """Initialize PathService.

        Args:
            project_root: Explicit project root path. If None, attempts to
                discover project root by walking up from cwd looking for .claude/.
                Falls back to cwd if not found.
        """
        if project_root is None:
            discovered = self.discover_project_root()
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
        resource = self._prompts_pkg.joinpath(f"PROMPT_{step}.md")
        if not resource.is_file():
            raise FileNotFoundError(f"Prompt not found: PROMPT_{step}.md")
        content: str = resource.read_text(encoding="utf-8")
        return content

    def get_common_prompt_content(self) -> str:
        """Get common prompt patterns prepended to all prompts.

        Returns:
            The common prompt content as a string

        Raises:
            FileNotFoundError: If _common.md doesn't exist
        """
        resource = self._prompts_pkg.joinpath("_common.md")
        if not resource.is_file():
            raise FileNotFoundError("Common prompt not found: _common.md")
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
            if name.startswith("PROMPT_") and name.endswith(".md"):
                step_name = name.replace("PROMPT_", "").replace(".md", "")
                prompts.append(step_name)
        return sorted(prompts)

    def prompt_exists(self, step: str) -> bool:
        """Check if a prompt exists for a given step.

        Args:
            step: The workflow step name

        Returns:
            True if the prompt exists, False otherwise
        """
        resource = self._prompts_pkg.joinpath(f"PROMPT_{step}.md")
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

    # === Local Config Paths (relative to project root) ===

    @property
    def project_root(self) -> Path:
        """The discovered or configured project root directory."""
        return self._project_root

    @property
    def claude_dir(self) -> Path:
        """Path to .claude directory."""
        return self._project_root / ".claude"

    @property
    def config_dir(self) -> Path:
        """Main claudesprint config directory (.claudesprint/)."""
        return self._project_root / ".claudesprint"

    @property
    def project_dir(self) -> Path:
        """Project state directory (.claudesprint/project/)."""
        return self.config_dir / "project"

    @property
    def sprints_dir(self) -> Path:
        """Sprints directory (.claudesprint/sprints/)."""
        return self.config_dir / "sprints"

    @property
    def specs_dir(self) -> Path:
        """Specs directory (.claudesprint/specs/)."""
        return self.config_dir / "specs"

    @property
    def config_files_dir(self) -> Path:
        """Config files directory (.claudesprint/config/)."""
        return self.config_dir / "config"

    # === File Paths ===

    @property
    def current_issue_file(self) -> Path:
        """Path to current_issue.json."""
        return self.project_dir / "current_issue.json"

    @property
    def current_issue_log_file(self) -> Path:
        """Path to current_issue.log."""
        return self.project_dir / "current_issue.log"

    @property
    def lock_file(self) -> Path:
        """Path to loop lock file."""
        return self.project_dir / ".loop.lock"

    @property
    def log_file(self) -> Path:
        """Path to loop log file."""
        return self.project_dir / "loop.log"

    @property
    def step_marker_file(self) -> Path:
        """Path to current step marker file."""
        return self.project_dir / ".current_step"

    @property
    def claude_output_file(self) -> Path:
        """Path to temp file for capturing Claude output."""
        return self.project_dir / ".claude_output.tmp"

    @property
    def notifications_file(self) -> Path:
        """Path to notifications config file."""
        return self.config_files_dir / "notifications.json"

    @property
    def models_file(self) -> Path:
        """Path to models config file for per-step model selection."""
        return self.config_files_dir / "models.json"

    @property
    def project_config_file(self) -> Path:
        """Path to project config.toml file (.claudesprint/config.toml)."""
        return self._project_root / ".claudesprint" / "config.toml"

    @property
    def sprint_lock_file(self) -> Path:
        """Path to sprint session lock file (.claudesprint/state/sprint.lock)."""
        return self._project_root / ".claudesprint" / "state" / "sprint.lock"

    @property
    def conversation_log_file(self) -> Path:
        """Path to agent_conversations.log for debug mode."""
        return self.project_dir / "agent_conversations.log"

    # === Sprint-specific ===

    def get_sprint_dir(self, spec_id: str) -> Path:
        """Get the directory for a specific sprint.

        Args:
            spec_id: The spec identifier (e.g., "SPEC_01")

        Returns:
            Path to the sprint directory
        """
        return self.sprints_dir / spec_id

    def get_sprint_path(self, spec_id: str) -> Path:
        """Get the path to a sprint.json file.

        Args:
            spec_id: The spec identifier (e.g., "SPEC_01")

        Returns:
            Path to sprint.json
        """
        return self.get_sprint_dir(spec_id) / "sprint.json"

    # === Discovery ===

    @classmethod
    def discover_project_root(cls, start: Path | None = None) -> Path | None:
        """Walk up from start (or cwd) looking for .claude directory.

        Args:
            start: Starting directory for search. Defaults to cwd.

        Returns:
            Path to project root if .claude found, None otherwise
        """
        cwd = start or Path.cwd()
        for parent in [cwd] + list(cwd.parents):
            if (parent / ".claude").exists():
                return parent
        return None

    # === Directory Creation ===

    def ensure_directories(self) -> None:
        """Create all required directories if they don't exist."""
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self.sprints_dir.mkdir(parents=True, exist_ok=True)
        self.specs_dir.mkdir(parents=True, exist_ok=True)
        self.config_files_dir.mkdir(parents=True, exist_ok=True)
