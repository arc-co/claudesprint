"""Tests for PathService."""

import tempfile
from pathlib import Path

import pytest

from claudesprint.services.path_service import PathService


class TestPathServicePackageAssets:
    """Tests for package asset resolution via importlib.resources."""

    def test_get_prompt_content_exists(self) -> None:
        """Test loading an existing prompt."""
        paths = PathService()
        content = paths.get_prompt_content("init")
        assert content
        assert isinstance(content, str)
        assert len(content) > 0

    def test_get_prompt_content_not_found(self) -> None:
        """Test loading a non-existent prompt raises FileNotFoundError."""
        paths = PathService()
        with pytest.raises(FileNotFoundError, match="PROMPT_nonexistent.md"):
            paths.get_prompt_content("nonexistent")

    def test_get_common_prompt_content(self) -> None:
        """Test loading common prompt content."""
        paths = PathService()
        content = paths.get_common_prompt_content()
        assert content
        assert isinstance(content, str)

    def test_get_schema_content_sprint(self) -> None:
        """Test loading sprint schema."""
        paths = PathService()
        content = paths.get_schema_content("sprint")
        assert content
        assert isinstance(content, str)
        assert "schema" in content.lower() or "$" in content

    def test_get_schema_content_current_issue(self) -> None:
        """Test loading current_issue schema."""
        paths = PathService()
        content = paths.get_schema_content("current_issue")
        assert content
        assert isinstance(content, str)

    def test_get_schema_content_not_found(self) -> None:
        """Test loading a non-existent schema raises FileNotFoundError."""
        paths = PathService()
        with pytest.raises(FileNotFoundError, match="nonexistent.schema.json"):
            paths.get_schema_content("nonexistent")

    def test_list_available_prompts(self) -> None:
        """Test listing available prompts."""
        paths = PathService()
        prompts = paths.list_available_prompts()
        assert isinstance(prompts, list)
        assert len(prompts) > 0
        assert "init" in prompts
        assert "implement" in prompts
        assert "run-tests" in prompts

    def test_prompt_exists(self) -> None:
        """Test checking if prompt exists."""
        paths = PathService()
        assert paths.prompt_exists("init")
        assert paths.prompt_exists("implement")
        assert not paths.prompt_exists("nonexistent")

    def test_schema_exists(self) -> None:
        """Test checking if schema exists."""
        paths = PathService()
        assert paths.schema_exists("sprint")
        assert paths.schema_exists("current_issue")
        assert not paths.schema_exists("nonexistent")


class TestPathServiceLocalPaths:
    """Tests for local config path resolution."""

    def test_project_root_default(self) -> None:
        """Test default project root is cwd when no .claude found."""
        paths = PathService(project_root="/tmp/test")
        assert paths.project_root == Path("/tmp/test")

    def test_project_root_explicit(self) -> None:
        """Test explicit project root."""
        paths = PathService(project_root="/some/path")
        assert paths.project_root == Path("/some/path")

    def test_claude_dir(self) -> None:
        """Test .claude directory path."""
        paths = PathService(project_root="/project")
        assert paths.claude_dir == Path("/project/.claude")

    def test_config_dir(self) -> None:
        """Test config directory path."""
        paths = PathService(project_root="/project")
        assert paths.config_dir == Path("/project/.claudesprint")

    def test_project_dir(self) -> None:
        """Test project state directory path."""
        paths = PathService(project_root="/project")
        assert paths.project_dir == Path("/project/.claudesprint/project")

    def test_sprints_dir(self) -> None:
        """Test sprints directory path."""
        paths = PathService(project_root="/project")
        assert paths.sprints_dir == Path("/project/.claudesprint/sprints")

    def test_specs_dir(self) -> None:
        """Test specs directory path."""
        paths = PathService(project_root="/project")
        assert paths.specs_dir == Path("/project/.claudesprint/specs")

    def test_config_files_dir(self) -> None:
        """Test config files directory path."""
        paths = PathService(project_root="/project")
        assert paths.config_files_dir == Path("/project/.claudesprint/config")

    def test_current_issue_file(self) -> None:
        """Test current_issue.json path."""
        paths = PathService(project_root="/project")
        assert paths.current_issue_file == Path(
            "/project/.claudesprint/project/current_issue.json"
        )

    def test_current_issue_log_file(self) -> None:
        """Test current_issue.log path."""
        paths = PathService(project_root="/project")
        assert paths.current_issue_log_file == Path(
            "/project/.claudesprint/project/current_issue.log"
        )

    def test_lock_file(self) -> None:
        """Test lock file path."""
        paths = PathService(project_root="/project")
        assert paths.lock_file == Path(
            "/project/.claudesprint/project/.loop.lock"
        )

    def test_notifications_file(self) -> None:
        """Test notifications config file path."""
        paths = PathService(project_root="/project")
        assert paths.notifications_file == Path(
            "/project/.claudesprint/config/notifications.json"
        )

    def test_models_file(self) -> None:
        """Test models config file path."""
        paths = PathService(project_root="/project")
        assert paths.models_file == Path(
            "/project/.claudesprint/config/models.json"
        )

    def test_sprint_lock_file(self) -> None:
        """Test sprint lock file path."""
        paths = PathService(project_root="/project")
        assert paths.sprint_lock_file == Path(
            "/project/.claudesprint/state/sprint.lock"
        )


class TestPathServiceSprintPaths:
    """Tests for sprint-specific path resolution."""

    def test_get_sprint_dir(self) -> None:
        """Test getting sprint directory."""
        paths = PathService(project_root="/project")
        sprint_dir = paths.get_sprint_dir("SPEC_01")
        assert sprint_dir == Path("/project/.claudesprint/sprints/SPEC_01")

    def test_get_sprint_path(self) -> None:
        """Test getting sprint.json path."""
        paths = PathService(project_root="/project")
        sprint_path = paths.get_sprint_path("SPEC_01")
        assert sprint_path == Path(
            "/project/.claudesprint/sprints/SPEC_01/sprint.json"
        )


class TestPathServiceDiscovery:
    """Tests for project root discovery."""

    def test_discover_project_root_found(self) -> None:
        """Test discovery when .claude exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            claude_dir = project_root / ".claude"
            claude_dir.mkdir()

            # Create a subdirectory to test discovery from
            subdir = project_root / "src" / "module"
            subdir.mkdir(parents=True)

            discovered = PathService.discover_project_root(start=subdir)
            assert discovered == project_root

    def test_discover_project_root_not_found(self) -> None:
        """Test discovery when .claude doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # No .claude directory
            discovered = PathService.discover_project_root(start=Path(tmpdir))
            assert discovered is None

    def test_discover_project_root_at_root(self) -> None:
        """Test discovery when .claude is at start directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            claude_dir = project_root / ".claude"
            claude_dir.mkdir()

            discovered = PathService.discover_project_root(start=project_root)
            assert discovered == project_root


class TestPathServiceDirectoryCreation:
    """Tests for directory creation."""

    def test_ensure_directories(self) -> None:
        """Test creating all required directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = PathService(project_root=tmpdir)
            paths.ensure_directories()

            assert paths.project_dir.exists()
            assert paths.sprints_dir.exists()
            assert paths.specs_dir.exists()
            assert paths.config_files_dir.exists()


