"""Git service for repository operations."""

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class GitStatus:
    """Git repository status."""

    is_repo: bool
    head: str
    dirty: bool
    branch: str
    error: str | None = None


class GitService:
    """Service for Git operations with graceful degradation."""

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root)

    def _run(self, *args: str, timeout: int = 60) -> tuple[bool, str, str]:
        """Run a git command and return (success, stdout, stderr)."""
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=timeout,
                env={"GIT_TERMINAL_PROMPT": "0"},
            )
            return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
        except subprocess.TimeoutExpired:
            return False, "", "Command timed out"
        except Exception as e:
            return False, "", str(e)

    def is_repo(self) -> bool:
        """Check if the project root is a git repository."""
        git_dir = self.project_root / ".git"
        return git_dir.exists()

    def get_status(self) -> GitStatus:
        """Get current git repository status."""
        if not self.is_repo():
            return GitStatus(is_repo=False, head="", dirty=False, branch="")

        # Get HEAD SHA
        success, head, err = self._run("rev-parse", "HEAD")
        if not success:
            return GitStatus(is_repo=True, head="", dirty=False, branch="", error=err)

        # Get current branch
        success, branch, _ = self._run("rev-parse", "--abbrev-ref", "HEAD")
        if not success:
            branch = "detached"

        # Check for uncommitted changes
        success, status_output, _ = self._run("status", "--porcelain")
        dirty = bool(status_output)

        return GitStatus(is_repo=True, head=head[:7], dirty=dirty, branch=branch)

    def get_recent_commits(self, count: int = 5) -> list[str]:
        """Get recent commit messages."""
        if not self.is_repo():
            return []

        success, output, _ = self._run("log", f"--oneline", f"-{count}")
        if not success:
            return []

        return output.split("\n") if output else []

    def get_diff_stat(self) -> str:
        """Get a summary of uncommitted changes."""
        if not self.is_repo():
            return ""

        success, output, _ = self._run("diff", "--stat")
        return output if success else ""

    # Branch operations (new for sprint model)

    def get_current_branch(self) -> str:
        """Get the name of the current branch.

        Returns:
            Branch name or empty string if not in a repo
        """
        if not self.is_repo():
            return ""

        success, branch, _ = self._run("rev-parse", "--abbrev-ref", "HEAD")
        return branch if success else ""

    def branch_exists(self, branch_name: str) -> bool:
        """Check if a branch exists.

        Args:
            branch_name: Name of the branch to check

        Returns:
            True if branch exists, False otherwise
        """
        if not self.is_repo():
            return False

        success, _, _ = self._run("rev-parse", "--verify", f"refs/heads/{branch_name}")
        return success

    def create_branch(self, branch_name: str, checkout: bool = True) -> tuple[bool, str]:
        """Create a new branch.

        Args:
            branch_name: Name of the branch to create
            checkout: Whether to checkout the new branch (default: True)

        Returns:
            Tuple of (success, message)
        """
        if not self.is_repo():
            return False, "Not a git repository"

        # Check if branch already exists
        if self.branch_exists(branch_name):
            if checkout:
                return self.checkout_branch(branch_name)
            return True, f"Branch {branch_name} already exists"

        # Create and optionally checkout
        if checkout:
            success, stdout, stderr = self._run("checkout", "-b", branch_name)
        else:
            success, stdout, stderr = self._run("branch", branch_name)

        return success, stdout if success else stderr

    def checkout_branch(self, branch_name: str) -> tuple[bool, str]:
        """Checkout an existing branch.

        Args:
            branch_name: Name of the branch to checkout

        Returns:
            Tuple of (success, message)
        """
        if not self.is_repo():
            return False, "Not a git repository"

        success, stdout, stderr = self._run("checkout", branch_name)
        return success, stdout if success else stderr

    def delete_branch(self, branch_name: str, force: bool = False) -> tuple[bool, str]:
        """Delete a branch.

        Args:
            branch_name: Name of the branch to delete
            force: Whether to force delete (default: False)

        Returns:
            Tuple of (success, message)
        """
        if not self.is_repo():
            return False, "Not a git repository"

        flag = "-D" if force else "-d"
        success, stdout, stderr = self._run("branch", flag, branch_name)
        return success, stdout if success else stderr

    def merge_branch(self, branch_name: str, message: str | None = None) -> tuple[bool, str]:
        """Merge a branch into the current branch.

        Args:
            branch_name: Name of the branch to merge
            message: Optional merge commit message

        Returns:
            Tuple of (success, message)
        """
        if not self.is_repo():
            return False, "Not a git repository"

        args = ["merge", branch_name]
        if message:
            args.extend(["-m", message])

        success, stdout, stderr = self._run(*args)
        return success, stdout if success else stderr
