"""Tests for session state utilities."""

import tempfile
from pathlib import Path

from claudesprint.services.session_state import is_session_active


class TestIsSessionActive:
    """Tests for is_session_active function."""

    def test_returns_false_when_no_project_root(self) -> None:
        """Test returns False when no .claude dir is found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # No .claude directory - discovery will return None
            result = is_session_active(project_root=tmpdir)
            assert result is False

    def test_returns_false_when_no_claudesprint_dir(self) -> None:
        """Test returns False when .claudesprint directory is missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            # Create .claude but not .claudesprint
            (project_root / ".claude").mkdir()

            result = is_session_active(project_root=project_root)
            assert result is False

    def test_returns_false_when_no_lock_file(self) -> None:
        """Test returns False when state dir exists but no lock file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            # Create directory structure but no lock file
            state_dir = project_root / ".claudesprint" / "state"
            state_dir.mkdir(parents=True)

            result = is_session_active(project_root=project_root)
            assert result is False

    def test_returns_true_when_lock_file_exists(self) -> None:
        """Test returns True when sprint.lock file is present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            # Create lock file
            state_dir = project_root / ".claudesprint" / "state"
            state_dir.mkdir(parents=True)
            lock_file = state_dir / "sprint.lock"
            lock_file.write_text("12345")

            result = is_session_active(project_root=project_root)
            assert result is True

    def test_explicit_project_root_overrides_discovery(self) -> None:
        """Test that explicit project_root parameter is used instead of discovery."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            # Create lock file at explicit path
            state_dir = project_root / ".claudesprint" / "state"
            state_dir.mkdir(parents=True)
            lock_file = state_dir / "sprint.lock"
            lock_file.write_text("active")

            # Pass explicit path as string
            result = is_session_active(project_root=str(project_root))
            assert result is True

    def test_handles_string_project_root(self) -> None:
        """Test that string project_root is properly converted to Path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            state_dir = project_root / ".claudesprint" / "state"
            state_dir.mkdir(parents=True)
            (state_dir / "sprint.lock").write_text("test")

            # Pass as string, should work
            result = is_session_active(project_root=tmpdir)
            assert result is True
