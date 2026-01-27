"""Service for initializing .claudesprint/ directory in a repository."""

from dataclasses import dataclass, field
from pathlib import Path

from claudesprint.services.constants import PROMPTS_README_CONTENT
from claudesprint.services.git_service import GitService


@dataclass
class InitRepoResult:
    """Result of repository initialization."""

    success: bool
    created_dirs: list[str] = field(default_factory=list)
    created_files: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


class InitRepoService:
    """Service for initializing .claudesprint/ directory structure."""

    CLAUDESPRINT_DIR = ".claudesprint"
    STATE_DIR = "state"
    PROMPTS_DIR = "prompts"
    PROMPTS_README = "README.md"
    GITIGNORE_ENTRY = ".claudesprint/"

    def __init__(self, project_root: str | Path) -> None:
        """Initialize the service.

        Args:
            project_root: Path to the project root directory
        """
        self.project_root = Path(project_root)
        self.claudesprint_dir = self.project_root / self.CLAUDESPRINT_DIR
        self.state_dir = self.claudesprint_dir / self.STATE_DIR
        self.prompts_dir = self.claudesprint_dir / self.PROMPTS_DIR
        self.prompts_readme = self.prompts_dir / self.PROMPTS_README
        self.gitignore_path = self.project_root / ".gitignore"

    def exists(self) -> bool:
        """Check if .claudesprint/ directory already exists.

        Returns:
            True if the directory exists, False otherwise
        """
        return self.claudesprint_dir.exists()

    def init(self, force: bool = False) -> InitRepoResult:
        """Initialize the .claudesprint/ directory structure.

        Args:
            force: If True, overwrite existing README even if directory exists

        Returns:
            InitRepoResult with details of what was created/modified
        """
        result = InitRepoResult(success=True)

        # Check if already initialized
        if self.exists() and not force:
            return InitRepoResult(
                success=False,
                error=f"Directory {self.CLAUDESPRINT_DIR}/ already exists. Use --force to reinitialize.",
            )

        # Check for git repository
        git_service = GitService(self.project_root)
        if not git_service.is_repo():
            result.warnings.append(
                "Not a git repository. Consider running 'git init' first."
            )

        # Create directories
        try:
            # Track if gitignore exists before we start
            gitignore_existed = self.gitignore_path.exists()

            # Create state directory
            state_existed = self.state_dir.exists()
            self.state_dir.mkdir(parents=True, exist_ok=True)
            if not state_existed:
                result.created_dirs.append(f"{self.CLAUDESPRINT_DIR}/{self.STATE_DIR}/")

            # Create prompts directory
            prompts_existed = self.prompts_dir.exists()
            self.prompts_dir.mkdir(parents=True, exist_ok=True)
            if not prompts_existed:
                result.created_dirs.append(f"{self.CLAUDESPRINT_DIR}/{self.PROMPTS_DIR}/")

            # Create prompts README
            if not self.prompts_readme.exists() or force:
                self.prompts_readme.write_text(PROMPTS_README_CONTENT)
                result.created_files.append(
                    f"{self.CLAUDESPRINT_DIR}/{self.PROMPTS_DIR}/{self.PROMPTS_README}"
                )

            # Update .gitignore
            gitignore_updated = self._update_gitignore()
            if gitignore_updated:
                if not gitignore_existed:
                    result.created_files.append(".gitignore")
                else:
                    result.created_files.append(".gitignore (updated)")

        except OSError as e:
            return InitRepoResult(
                success=False,
                error=f"Failed to create directory structure: {e}",
            )

        return result

    def _update_gitignore(self) -> bool:
        """Update .gitignore to include .claudesprint/ entry.

        Returns:
            True if .gitignore was created or modified, False if no changes needed
        """
        # Check if .gitignore exists
        if self.gitignore_path.exists():
            content = self.gitignore_path.read_text()
            lines = content.splitlines()

            # Check if entry already exists (exact match or with trailing newline)
            for line in lines:
                stripped = line.strip()
                if stripped == self.GITIGNORE_ENTRY or stripped == self.GITIGNORE_ENTRY.rstrip("/"):
                    return False  # Already present

            # Append entry
            # Ensure file ends with newline before appending
            if content and not content.endswith("\n"):
                content += "\n"
            content += f"{self.GITIGNORE_ENTRY}\n"
            self.gitignore_path.write_text(content)
            return True
        else:
            # Create new .gitignore
            self.gitignore_path.write_text(f"{self.GITIGNORE_ENTRY}\n")
            return True
