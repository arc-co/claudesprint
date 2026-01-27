"""Tests for GitService."""

import json
import subprocess
from pathlib import Path

import pytest

from claudesprint.services.git_service import GitService


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a temporary git repository."""
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    # Create initial commit so HEAD exists
    (tmp_path / "README.md").write_text("# Test")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    return tmp_path


class TestGetDirtyFiles:
    """Tests for get_dirty_files method."""

    def test_returns_empty_set_for_non_repo(self, tmp_path: Path) -> None:
        """Returns empty set when not a git repo."""
        service = GitService(tmp_path)
        assert service.get_dirty_files() == set()

    def test_returns_empty_set_for_clean_repo(self, git_repo: Path) -> None:
        """Returns empty set when repo is clean."""
        service = GitService(git_repo)
        assert service.get_dirty_files() == set()

    def test_detects_modified_file(self, git_repo: Path) -> None:
        """Detects modified tracked files."""
        (git_repo / "README.md").write_text("# Modified")
        service = GitService(git_repo)
        assert service.get_dirty_files() == {"README.md"}

    def test_detects_untracked_file(self, git_repo: Path) -> None:
        """Detects untracked files."""
        (git_repo / "new_file.txt").write_text("content")
        service = GitService(git_repo)
        assert service.get_dirty_files() == {"new_file.txt"}

    def test_detects_staged_file(self, git_repo: Path) -> None:
        """Detects staged files."""
        (git_repo / "staged.txt").write_text("content")
        subprocess.run(["git", "add", "staged.txt"], cwd=git_repo, capture_output=True)
        service = GitService(git_repo)
        assert service.get_dirty_files() == {"staged.txt"}

    def test_detects_multiple_dirty_files(self, git_repo: Path) -> None:
        """Detects multiple dirty files of different types."""
        # Modified
        (git_repo / "README.md").write_text("# Modified")
        # Untracked
        (git_repo / "untracked.txt").write_text("content")
        # Staged new file
        (git_repo / "staged.txt").write_text("content")
        subprocess.run(["git", "add", "staged.txt"], cwd=git_repo, capture_output=True)

        service = GitService(git_repo)
        dirty = service.get_dirty_files()

        assert dirty == {"README.md", "untracked.txt", "staged.txt"}

    def test_handles_files_in_subdirectories(self, git_repo: Path) -> None:
        """Detects files in subdirectories (git shows untracked dirs as dir/)."""
        subdir = git_repo / "subdir"
        subdir.mkdir()
        (subdir / "file.txt").write_text("content")

        service = GitService(git_repo)
        # Git status --porcelain shows untracked directories as "dir/"
        assert service.get_dirty_files() == {"subdir/"}

    def test_handles_deleted_file(self, git_repo: Path) -> None:
        """Detects deleted files."""
        (git_repo / "README.md").unlink()
        service = GitService(git_repo)
        assert service.get_dirty_files() == {"README.md"}


class TestSaveBaselineDirtyFiles:
    """Tests for save_baseline_dirty_files method."""

    def test_saves_dirty_files_to_json(self, git_repo: Path) -> None:
        """Saves dirty files to JSON file."""
        (git_repo / "dirty1.txt").write_text("content")
        (git_repo / "dirty2.txt").write_text("content")

        service = GitService(git_repo)
        output_path = git_repo / ".claudesprint" / "project" / "baseline_dirty.json"

        dirty = service.save_baseline_dirty_files(output_path)

        assert dirty == {"dirty1.txt", "dirty2.txt"}
        assert output_path.exists()

        with open(output_path) as f:
            data = json.load(f)

        assert set(data["files"]) == {"dirty1.txt", "dirty2.txt"}
        assert "recorded_at" in data
        assert "description" in data

    def test_creates_parent_directories(self, git_repo: Path) -> None:
        """Creates parent directories if they don't exist."""
        service = GitService(git_repo)
        output_path = git_repo / "deep" / "nested" / "path" / "baseline.json"

        service.save_baseline_dirty_files(output_path)

        assert output_path.exists()

    def test_saves_empty_list_for_clean_repo(self, git_repo: Path) -> None:
        """Saves empty list when repo is clean."""
        service = GitService(git_repo)
        output_path = git_repo / "baseline.json"

        dirty = service.save_baseline_dirty_files(output_path)

        assert dirty == set()

        with open(output_path) as f:
            data = json.load(f)

        assert data["files"] == []
