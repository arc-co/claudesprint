"""Git service for repository operations."""

import logging
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


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

    # Default git timeout (can be overridden via config)
    DEFAULT_GIT_TIMEOUT = 60

    def __init__(
        self,
        project_root: str | Path,
        git_timeout: int | None = None,
    ) -> None:
        self.project_root = Path(project_root)
        self._git_timeout = git_timeout if git_timeout is not None else self.DEFAULT_GIT_TIMEOUT

    def _run(self, *args: str, timeout: int | None = None) -> tuple[bool, str, str]:
        """Run a git command and return (success, stdout, stderr)."""
        effective_timeout = timeout if timeout is not None else self._git_timeout
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=effective_timeout,
                env={"GIT_TERMINAL_PROMPT": "0"},
            )
            return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
        except subprocess.TimeoutExpired:
            logger.warning(f"Git command timed out: git {' '.join(args)}")
            return False, "", "Command timed out"
        except subprocess.SubprocessError as e:
            logger.warning(f"Git subprocess error: {e}")
            return False, "", str(e)
        except OSError as e:
            logger.warning(f"Failed to run git command: {e}")
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

        success, output, _ = self._run("log", "--oneline", f"-{count}")
        if not success:
            return []

        return output.split("\n") if output else []

    def get_diff_stat(self) -> str:
        """Get a summary of uncommitted changes."""
        if not self.is_repo():
            return ""

        success, output, _ = self._run("diff", "--stat")
        return output if success else ""

    def get_dirty_files(self) -> set[str]:
        """Get set of files with uncommitted changes (staged or unstaged).

        Returns file paths relative to repo root. Handles renamed files
        by including both old and new paths.
        """
        if not self.is_repo():
            return set()

        # Use git status -z for null-terminated output, which avoids quoting
        # issues with special characters in filenames (tabs, newlines, etc.)
        try:
            result = subprocess.run(
                ["git", "status", "-z"],
                cwd=self.project_root,
                capture_output=True,
                timeout=self._git_timeout,
            )
            if result.returncode != 0 or not result.stdout:
                return set()
            # Use binary mode output - don't decode as text to preserve NUL bytes
            output = result.stdout
        except subprocess.TimeoutExpired:
            logger.warning("git status -z timed out")
            return set()
        except subprocess.SubprocessError as e:
            logger.warning(f"git status -z subprocess error: {e}")
            return set()
        except OSError as e:
            logger.warning(f"Failed to run git status -z: {e}")
            return set()

        dirty_files: set[str] = set()
        # Split on NUL bytes; git status -z format:
        # - Regular entry: "XY PATH\0"
        # - Rename/copy: "XY NEW_PATH\0OLD_PATH\0" (old path is separate NUL field)
        entries = output.split(b"\0")
        i = 0
        while i < len(entries):
            entry = entries[i]
            if not entry:
                i += 1
                continue

            # Entry format: XY<space>PATH where XY is 2 status chars
            if len(entry) < 4:
                i += 1
                continue

            status = entry[:2]
            file_path = entry[3:].decode("utf-8", errors="replace")
            dirty_files.add(file_path)

            # Check for rename/copy: status codes R or C in either position
            # means the next NUL-separated field is the original path
            if b"R" in status or b"C" in status:
                i += 1
                if i < len(entries) and entries[i]:
                    old_path = entries[i].decode("utf-8", errors="replace")
                    dirty_files.add(old_path)

            i += 1

        return dirty_files

    def save_baseline_dirty_files(self, output_path: Path) -> set[str]:
        """Save current dirty files to a JSON file for later reference.

        Args:
            output_path: Path to write the baseline JSON file

        Returns:
            Set of dirty file paths that were saved
        """
        dirty_files = self.get_dirty_files()
        import json

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(
                {
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                    "files": sorted(dirty_files),
                    "description": "Files that were dirty before claudesprint started. "
                    "These should NOT be staged or committed by the agent.",
                },
                f,
                indent=2,
            )
        return dirty_files

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
