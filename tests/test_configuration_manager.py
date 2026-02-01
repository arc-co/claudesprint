"""Tests for ConfigurationManager."""

import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from claudesprint.services.configuration_manager import (
    ConfigurationManager,
    ResolvedPaths,
)
from claudesprint.services.project_config_service import ProjectConfig


class TestResolvedPaths:
    """Tests for ResolvedPaths dataclass."""

    def test_from_project_root(self) -> None:
        """Test creating ResolvedPaths from project root."""
        paths = ResolvedPaths.from_project_root(Path("/project"))

        assert paths.project_root == Path("/project")
        assert paths.claude_dir == Path("/project/.claude")
        assert paths.config_dir == Path("/project/.claudesprint")
        assert paths.project_dir == Path("/project/.claudesprint/project")
        assert paths.sprints_dir == Path("/project/.claudesprint/sprints")
        assert paths.specs_dir == Path("/project/.claudesprint/specs")
        assert paths.config_files_dir == Path("/project/.claudesprint/config")

    def test_file_paths(self) -> None:
        """Test file path resolution."""
        paths = ResolvedPaths.from_project_root(Path("/project"))

        assert paths.current_issue_file == Path(
            "/project/.claudesprint/project/current_issue.json"
        )
        assert paths.current_issue_log_file == Path(
            "/project/.claudesprint/project/current_issue.log"
        )
        assert paths.lock_file == Path("/project/.claudesprint/project/.loop.lock")
        assert paths.project_config_file == Path("/project/.claudesprint/config.toml")
        assert paths.sprint_lock_file == Path(
            "/project/.claudesprint/state/sprint.lock"
        )

    def test_frozen_dataclass(self) -> None:
        """Test that ResolvedPaths is immutable."""
        paths = ResolvedPaths.from_project_root(Path("/project"))

        with pytest.raises(AttributeError):
            paths.project_root = Path("/other")  # type: ignore


class TestConfigurationManagerInit:
    """Tests for ConfigurationManager initialization."""

    def test_explicit_project_root(self) -> None:
        """Test initialization with explicit project root."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = ConfigurationManager(project_root=tmpdir)
            assert cm.project_root == Path(tmpdir)

    def test_auto_discovery_with_claude_dir(self) -> None:
        """Test auto-discovery when .claude directory exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            claude_dir = project_root / ".claude"
            claude_dir.mkdir()

            # Create subdirectory to test discovery from
            subdir = project_root / "src" / "module"
            subdir.mkdir(parents=True)

            with mock.patch.object(Path, "cwd", return_value=subdir):
                cm = ConfigurationManager()
                assert cm.project_root == project_root

    def test_fallback_to_cwd(self) -> None:
        """Test fallback to cwd when .claude not found."""
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            mock.patch.object(Path, "cwd", return_value=Path(tmpdir)),
        ):
            cm = ConfigurationManager()
            assert cm.project_root == Path(tmpdir)


class TestConfigurationManagerPaths:
    """Tests for path resolution."""

    def test_paths_property(self) -> None:
        """Test paths property returns ResolvedPaths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = ConfigurationManager(project_root=tmpdir)
            paths = cm.paths

            assert isinstance(paths, ResolvedPaths)
            assert paths.project_root == Path(tmpdir)

    def test_paths_cached(self) -> None:
        """Test paths is cached."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = ConfigurationManager(project_root=tmpdir)
            paths1 = cm.paths
            paths2 = cm.paths
            assert paths1 is paths2


class TestConfigurationManagerProjectConfig:
    """Tests for project config loading."""

    def test_load_defaults_when_file_missing(self) -> None:
        """Test loading defaults when config.toml doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = ConfigurationManager(project_root=tmpdir)
            config = cm.project

            assert isinstance(config, ProjectConfig)
            assert config.server.url == "http://localhost:3000"
            assert config.models.default_model == "opus"

    def test_load_from_toml_file(self) -> None:
        """Test loading from existing TOML file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".claudesprint" / "config.toml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text(
                """
[server]
url = "http://localhost:8080"

[models]
default_model = "sonnet"
"""
            )

            cm = ConfigurationManager(project_root=tmpdir)
            config = cm.project

            assert config.server.url == "http://localhost:8080"
            assert config.models.default_model == "sonnet"

    def test_load_returns_defaults_on_invalid_toml(self) -> None:
        """Test loading returns defaults on invalid TOML."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".claudesprint" / "config.toml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text("invalid { toml content")

            cm = ConfigurationManager(project_root=tmpdir)
            config = cm.project

            assert config.server.url == "http://localhost:3000"

    def test_project_config_cached(self) -> None:
        """Test project config is cached."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = ConfigurationManager(project_root=tmpdir)
            config1 = cm.project
            config2 = cm.project
            assert config1 is config2


class TestConfigurationManagerSave:
    """Tests for saving configuration."""

    def test_save_creates_file(self) -> None:
        """Test save_project creates config.toml file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = ConfigurationManager(project_root=tmpdir)

            from claudesprint.services.project_config_service import ServerConfig

            config = ProjectConfig(server=ServerConfig(url="http://localhost:9000"))
            result = cm.save_project(config)

            assert result is True
            assert cm.exists()

    def test_save_roundtrip(self) -> None:
        """Test save and load roundtrip."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = ConfigurationManager(project_root=tmpdir)

            from claudesprint.services.project_config_service import (
                ModelsConfig,
                ServerConfig,
            )

            original = ProjectConfig(
                server=ServerConfig(url="http://localhost:9000"),
                models=ModelsConfig(default_model="sonnet"),
            )
            cm.save_project(original)
            cm.reload()
            loaded = cm.project

            assert loaded.server.url == "http://localhost:9000"
            assert loaded.models.default_model == "sonnet"


class TestConfigurationManagerInitConfig:
    """Tests for init_config method."""

    def test_init_creates_file(self) -> None:
        """Test init_config creates file with template."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = ConfigurationManager(project_root=tmpdir)

            result = cm.init_config()

            assert result is True
            assert cm.exists()
            content = cm.paths.project_config_file.read_text()
            assert "[server]" in content
            assert "[models]" in content

    def test_init_does_not_overwrite(self) -> None:
        """Test init_config doesn't overwrite without flag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".claudesprint" / "config.toml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text("# Custom content\n")

            cm = ConfigurationManager(project_root=tmpdir)
            result = cm.init_config(overwrite=False)

            assert result is False
            assert config_path.read_text() == "# Custom content\n"

    def test_init_overwrites_with_flag(self) -> None:
        """Test init_config overwrites with flag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".claudesprint" / "config.toml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text("# Custom content\n")

            cm = ConfigurationManager(project_root=tmpdir)
            result = cm.init_config(overwrite=True)

            assert result is True
            assert "[server]" in config_path.read_text()


class TestConfigurationManagerReload:
    """Tests for reload functionality."""

    def test_reload_clears_cache(self) -> None:
        """Test reload clears cached config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = ConfigurationManager(project_root=tmpdir)

            # Load defaults
            config1 = cm.project
            assert config1.server.url == "http://localhost:3000"

            # Create a config file
            config_path = Path(tmpdir) / ".claudesprint" / "config.toml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text('[server]\nurl = "http://localhost:9000"\n')

            # Reload should pick up new file
            cm.reload()
            config2 = cm.project
            assert config2.server.url == "http://localhost:9000"


class TestConfigurationManagerModelSelection:
    """Tests for model selection methods."""

    def test_get_model_for_step_default(self) -> None:
        """Test get_model_for_step returns default."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = ConfigurationManager(project_root=tmpdir)

            assert cm.get_model_for_step("implement") == "opus"
            assert cm.get_model_for_step("read-docs") == "sonnet"

    def test_get_model_for_step_with_override(self) -> None:
        """Test get_model_for_step respects override."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".claudesprint" / "config.toml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text('[models]\nmodel_override = "haiku"\n')

            cm = ConfigurationManager(project_root=tmpdir)

            assert cm.get_model_for_step("implement") == "haiku"
            assert cm.get_model_for_step("read-docs") == "haiku"

    def test_get_model_for_special_step(self) -> None:
        """Test get_model_for_special_step returns correct model."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = ConfigurationManager(project_root=tmpdir)

            assert cm.get_model_for_special_step("init") == "opus"
            assert cm.get_model_for_special_step("plan") == "sonnet"


class TestConfigurationManagerDirectories:
    """Tests for directory management."""

    def test_ensure_directories(self) -> None:
        """Test ensure_directories creates all required dirs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = ConfigurationManager(project_root=tmpdir)
            cm.ensure_directories()

            assert cm.paths.project_dir.exists()
            assert cm.paths.sprints_dir.exists()
            assert cm.paths.specs_dir.exists()
            assert cm.paths.config_files_dir.exists()


class TestConfigurationManagerSprintPaths:
    """Tests for sprint-specific paths."""

    def test_get_sprint_dir(self) -> None:
        """Test get_sprint_dir returns correct path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = ConfigurationManager(project_root=tmpdir)
            sprint_dir = cm.get_sprint_dir("SPEC_01")

            assert sprint_dir == Path(tmpdir) / ".claudesprint" / "sprints" / "SPEC_01"

    def test_get_sprint_path(self) -> None:
        """Test get_sprint_path returns correct path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = ConfigurationManager(project_root=tmpdir)
            sprint_path = cm.get_sprint_path("SPEC_01")

            assert sprint_path == (
                Path(tmpdir) / ".claudesprint" / "sprints" / "SPEC_01" / "sprint.json"
            )


class TestConfigurationManagerDiscovery:
    """Tests for project root discovery."""

    def test_discover_project_root_found(self) -> None:
        """Test discovery when .claude exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            claude_dir = project_root / ".claude"
            claude_dir.mkdir()

            subdir = project_root / "src" / "module"
            subdir.mkdir(parents=True)

            discovered = ConfigurationManager.discover_project_root(start=subdir)
            assert discovered == project_root

    def test_discover_project_root_not_found(self) -> None:
        """Test discovery when .claude doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            discovered = ConfigurationManager.discover_project_root(start=Path(tmpdir))
            assert discovered is None


class TestConfigurationManagerGlobalConfig:
    """Tests for global config functionality."""

    def test_get_default_global_config_path_linux(self) -> None:
        """Test default path on Linux."""
        with (
            mock.patch.object(sys, "platform", "linux"),
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch.object(Path, "home", return_value=Path("/home/user")),
        ):
            path = ConfigurationManager.get_default_global_config_path()
            assert path == Path("/home/user/.config/claudesprint/config.toml")

    def test_get_default_global_config_path_env_override(self) -> None:
        """Test CLAUDESPRINT_CONFIG_HOME override."""
        with mock.patch.dict(os.environ, {"CLAUDESPRINT_CONFIG_HOME": "/custom/path"}):
            path = ConfigurationManager.get_default_global_config_path()
            assert path == Path("/custom/path/config.toml")

    def test_get_global_flat_dict(self) -> None:
        """Test get_global_flat_dict returns flattened config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = ConfigurationManager(project_root=tmpdir)
            flat = cm.get_global_flat_dict()

            assert "max_retry" in flat
            assert "rate_limit_retries" in flat
            assert "heartbeat_enabled" in flat


class TestConfigurationManagerExists:
    """Tests for exists check."""

    def test_exists_returns_false_when_not_initialized(self) -> None:
        """Test exists returns False when config doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = ConfigurationManager(project_root=tmpdir)
            assert cm.exists() is False

    def test_exists_returns_true_when_initialized(self) -> None:
        """Test exists returns True when config exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".claudesprint" / "config.toml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text("[server]\n")

            cm = ConfigurationManager(project_root=tmpdir)
            assert cm.exists() is True
