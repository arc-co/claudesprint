"""Tests for GlobalConfigService."""

import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from claudesprint.services.global_config_service import (
    DebugConfig,
    DefaultsConfig,
    GlobalConfig,
    GlobalConfigService,
    HeartbeatConfig,
    RateLimitingConfig,
)


class TestGlobalConfigModels:
    """Tests for Pydantic config models."""

    def test_defaults_config_defaults(self) -> None:
        """Test DefaultsConfig has expected defaults."""
        config = DefaultsConfig()
        assert config.model == "opus"
        assert config.max_retry == 5
        assert config.claude_timeout == 1800
        assert config.total_timeout == 28800

    def test_rate_limiting_config_defaults(self) -> None:
        """Test RateLimitingConfig has expected defaults."""
        config = RateLimitingConfig()
        assert config.retries == 3
        assert config.base_wait == 60
        assert config.max_wait == 900

    def test_heartbeat_config_defaults(self) -> None:
        """Test HeartbeatConfig has expected defaults."""
        config = HeartbeatConfig()
        assert config.enabled is True
        assert config.timeout == 600

    def test_debug_config_defaults(self) -> None:
        """Test DebugConfig has expected defaults."""
        config = DebugConfig()
        assert config.conversations is False

    def test_global_config_defaults(self) -> None:
        """Test GlobalConfig composes all sections."""
        config = GlobalConfig()
        assert isinstance(config.defaults, DefaultsConfig)
        assert isinstance(config.rate_limiting, RateLimitingConfig)
        assert isinstance(config.heartbeat, HeartbeatConfig)
        assert isinstance(config.debug, DebugConfig)

    def test_global_config_from_dict(self) -> None:
        """Test GlobalConfig can be created from dict."""
        data = {
            "defaults": {"max_retry": 10, "model": "sonnet"},
            "rate_limiting": {"retries": 5},
        }
        config = GlobalConfig(**data)
        assert config.defaults.max_retry == 10
        assert config.defaults.model == "sonnet"
        assert config.rate_limiting.retries == 5
        # Other fields should have defaults
        assert config.heartbeat.enabled is True

    def test_defaults_config_validation(self) -> None:
        """Test DefaultsConfig validates constraints."""
        with pytest.raises(ValueError):
            DefaultsConfig(max_retry=0)  # Must be >= 1

        with pytest.raises(ValueError):
            DefaultsConfig(claude_timeout=30)  # Must be >= 60


class TestGlobalConfigServicePaths:
    """Tests for platform-specific path resolution."""

    def test_default_path_linux(self) -> None:
        """Test default path on Linux."""
        with (
            mock.patch.object(sys, "platform", "linux"),
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch.object(Path, "home", return_value=Path("/home/user")),
        ):
            path = GlobalConfigService.get_default_config_path()
            assert path == Path("/home/user/.config/claudesprint/config.toml")

    def test_default_path_linux_xdg(self) -> None:
        """Test default path on Linux with XDG_CONFIG_HOME."""
        with (
            mock.patch.object(sys, "platform", "linux"),
            mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": "/custom/config"}, clear=True),
        ):
            path = GlobalConfigService.get_default_config_path()
            assert path == Path("/custom/config/claudesprint/config.toml")

    def test_default_path_macos(self) -> None:
        """Test default path on macOS."""
        with (
            mock.patch.object(sys, "platform", "darwin"),
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch.object(Path, "home", return_value=Path("/Users/user")),
        ):
            path = GlobalConfigService.get_default_config_path()
            assert path == Path("/Users/user/.config/claudesprint/config.toml")

    def test_default_path_windows(self) -> None:
        """Test default path on Windows."""
        with (
            mock.patch.object(sys, "platform", "win32"),
            mock.patch.dict(
                os.environ, {"APPDATA": "C:\\Users\\user\\AppData\\Roaming"}, clear=True
            ),
        ):
            path = GlobalConfigService.get_default_config_path()
            # Compare string representations to handle cross-platform path sep differences
            expected = "C:/Users/user/AppData/Roaming/claudesprint/config.toml"
            assert str(path).replace("\\", "/") == expected

    def test_env_override(self) -> None:
        """Test CLAUDESPRINT_CONFIG_HOME overrides platform defaults."""
        with mock.patch.dict(os.environ, {"CLAUDESPRINT_CONFIG_HOME": "/custom/path"}):
            path = GlobalConfigService.get_default_config_path()
            assert path == Path("/custom/path/config.toml")

    def test_explicit_path(self) -> None:
        """Test explicit path overrides everything."""
        service = GlobalConfigService(config_path="/explicit/config.toml")
        assert service.config_path == Path("/explicit/config.toml")


class TestGlobalConfigServiceLoad:
    """Tests for loading configuration."""

    def test_load_nonexistent_returns_defaults(self) -> None:
        """Test loading when file doesn't exist returns defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "nonexistent" / "config.toml"
            service = GlobalConfigService(config_path=config_path)

            assert not service.exists()
            config = service.load()

            assert isinstance(config, GlobalConfig)
            assert config.defaults.max_retry == 5

    def test_load_valid_toml(self) -> None:
        """Test loading valid TOML file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text("""
[defaults]
max_retry = 10
model = "sonnet"

[rate_limiting]
retries = 5
""")
            service = GlobalConfigService(config_path=config_path)
            config = service.load()

            assert config.defaults.max_retry == 10
            assert config.defaults.model == "sonnet"
            assert config.rate_limiting.retries == 5
            # Unspecified values should be defaults
            assert config.heartbeat.enabled is True

    def test_load_invalid_toml_returns_defaults(self) -> None:
        """Test loading invalid TOML returns defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text("invalid { toml content")

            service = GlobalConfigService(config_path=config_path)
            config = service.load()

            # Should return defaults on parse error
            assert isinstance(config, GlobalConfig)
            assert config.defaults.max_retry == 5

    def test_load_cached(self) -> None:
        """Test config is cached after first load."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text("[defaults]\nmax_retry = 10\n")

            service = GlobalConfigService(config_path=config_path)
            config1 = service.load()
            config2 = service.load()

            assert config1 is config2

    def test_reload_refreshes_cache(self) -> None:
        """Test reload() refreshes the cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text("[defaults]\nmax_retry = 10\n")

            service = GlobalConfigService(config_path=config_path)
            config1 = service.load()

            # Modify file
            config_path.write_text("[defaults]\nmax_retry = 20\n")
            config2 = service.reload()

            assert config1.defaults.max_retry == 10
            assert config2.defaults.max_retry == 20


class TestGlobalConfigServiceSave:
    """Tests for saving configuration."""

    def test_save_creates_directory(self) -> None:
        """Test save creates parent directory if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "nested" / "dir" / "config.toml"
            service = GlobalConfigService(config_path=config_path)

            config = GlobalConfig()
            config.defaults.max_retry = 15

            result = service.save(config)
            assert result is True
            assert config_path.exists()

    def test_save_writes_valid_toml(self) -> None:
        """Test save writes valid TOML that can be loaded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            service = GlobalConfigService(config_path=config_path)

            config = GlobalConfig()
            config.defaults.max_retry = 15
            config.rate_limiting.retries = 7

            service.save(config)

            # Reload and verify
            service2 = GlobalConfigService(config_path=config_path)
            loaded = service2.load()

            assert loaded.defaults.max_retry == 15
            assert loaded.rate_limiting.retries == 7


class TestGlobalConfigServiceInit:
    """Tests for config initialization."""

    def test_init_config_creates_file(self) -> None:
        """Test init_config creates file with template."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            service = GlobalConfigService(config_path=config_path)

            result = service.init_config()
            assert result is True
            assert config_path.exists()

            content = config_path.read_text()
            assert "[defaults]" in content
            assert "max_retry" in content

    def test_init_config_no_overwrite(self) -> None:
        """Test init_config doesn't overwrite by default."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text("# existing content\n")

            service = GlobalConfigService(config_path=config_path)
            result = service.init_config(overwrite=False)

            assert result is False
            assert config_path.read_text() == "# existing content\n"

    def test_init_config_with_overwrite(self) -> None:
        """Test init_config overwrites when requested."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text("# existing content\n")

            service = GlobalConfigService(config_path=config_path)
            result = service.init_config(overwrite=True)

            assert result is True
            content = config_path.read_text()
            assert "[defaults]" in content


class TestGlobalConfigServiceGet:
    """Tests for getting specific values."""

    def test_get_value(self) -> None:
        """Test getting a specific config value."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text("[defaults]\nmax_retry = 15\n")

            service = GlobalConfigService(config_path=config_path)
            value = service.get("defaults", "max_retry")

            assert value == 15

    def test_get_missing_returns_default(self) -> None:
        """Test getting missing value returns default."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "nonexistent" / "config.toml"
            service = GlobalConfigService(config_path=config_path)

            value = service.get("nonexistent", "key", default="fallback")
            assert value == "fallback"

    def test_get_flat_dict(self) -> None:
        """Test get_flat_dict returns flattened config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text("""
[defaults]
max_retry = 15

[rate_limiting]
retries = 7
""")
            service = GlobalConfigService(config_path=config_path)
            flat = service.get_flat_dict()

            assert flat["max_retry"] == 15
            assert flat["rate_limit_retries"] == 7
            assert flat["heartbeat_enabled"] is True


class TestGlobalConfigIntegration:
    """Tests for integration with ClaudesprintConfig."""

    def test_claudesprint_config_uses_global_defaults(self) -> None:
        """Test ClaudesprintConfig loads global defaults."""
        from claudesprint.models.config import ClaudesprintConfig

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create global config
            config_dir = Path(tmpdir) / ".config" / "claudesprint"
            config_dir.mkdir(parents=True)
            config_path = config_dir / "config.toml"
            config_path.write_text("[defaults]\nmax_retry = 15\n")

            # Create project directory
            project_dir = Path(tmpdir) / "project"
            project_dir.mkdir()

            # Patch the static method to return our custom defaults
            def mock_get_global_defaults() -> dict:
                service = GlobalConfigService(config_path=config_path)
                return service.get_flat_dict()

            with mock.patch.object(ClaudesprintConfig, "_get_global_defaults", mock_get_global_defaults):
                config = ClaudesprintConfig.from_project_root(str(project_dir))
                assert config.max_retry == 15

    def test_env_var_overrides_global_config(self) -> None:
        """Test environment variables override global config."""
        from claudesprint.models.config import ClaudesprintConfig

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create global config with max_retry = 15
            config_dir = Path(tmpdir) / ".config" / "claudesprint"
            config_dir.mkdir(parents=True)
            config_path = config_dir / "config.toml"
            config_path.write_text("[defaults]\nmax_retry = 15\n")

            # Create project directory
            project_dir = Path(tmpdir) / "project"
            project_dir.mkdir()

            # Set env var FIRST so the mock can see it
            with mock.patch.dict(os.environ, {"CLAUDESPRINT_MAX_RETRY": "3"}):
                # The mock simulates _get_global_defaults which checks env vars
                # and excludes fields that have env vars set
                def mock_get_global_defaults() -> dict:
                    # Simulate the real behavior: global config has max_retry=15
                    # but env var CLAUDESPRINT_MAX_RETRY=3 is set, so max_retry
                    # should NOT be returned (pydantic-settings will use env var)
                    flat = {"max_retry": 15}  # What global config would return

                    # But since CLAUDESPRINT_MAX_RETRY is set, we exclude it
                    # (this is what the real implementation does)
                    if os.environ.get("CLAUDESPRINT_MAX_RETRY"):
                        del flat["max_retry"]
                    return flat

                with mock.patch.object(ClaudesprintConfig, "_get_global_defaults", mock_get_global_defaults):
                    config = ClaudesprintConfig.from_project_root(str(project_dir))
                    assert config.max_retry == 3  # Env var wins

    def test_no_global_config_uses_hardcoded_defaults(self) -> None:
        """Test hardcoded defaults are used when no global config."""
        from claudesprint.models.config import ClaudesprintConfig

        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir) / "project"
            project_dir.mkdir()

            # Patch the static method to return empty dict (no global config)
            def mock_get_global_defaults() -> dict:
                return {}

            # Remove any existing CLAUDESPRINT_ env vars that could override
            env_without_claudesprint = {
                k: v for k, v in os.environ.items()
                if not k.startswith("CLAUDESPRINT_")
            }

            with (
                mock.patch.object(
                    ClaudesprintConfig, "_get_global_defaults", mock_get_global_defaults
                ),
                mock.patch.dict(os.environ, env_without_claudesprint, clear=True),
            ):
                config = ClaudesprintConfig.from_project_root(str(project_dir))
                assert config.max_retry == 5  # Hardcoded default
