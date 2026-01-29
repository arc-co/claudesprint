"""Tests for ProjectConfigService."""

import tempfile
from pathlib import Path

import pytest

from claudesprint.services.project_config_service import (
    BarkNotificationConfig,
    DEFAULT_PROJECT_CONFIG_TOML,
    HookConfig,
    HooksConfig,
    ModelsConfig,
    ModelsSpecialConfig,
    ModelsStepsConfig,
    NotificationsConfig,
    ProjectConfig,
    ProjectConfigService,
    ServerConfig,
)


class TestServerConfig:
    """Tests for ServerConfig model."""

    def test_default_values(self) -> None:
        """Test ServerConfig has expected defaults."""
        config = ServerConfig()

        assert config.url == "http://localhost:3000"
        assert config.start_command == "npm run dev"
        assert config.wait_seconds == 5

    def test_custom_values(self) -> None:
        """Test ServerConfig with custom values."""
        config = ServerConfig(
            url="http://localhost:8080",
            start_command="python -m http.server",
            wait_seconds=10,
        )

        assert config.url == "http://localhost:8080"
        assert config.start_command == "python -m http.server"
        assert config.wait_seconds == 10


class TestModelsConfig:
    """Tests for ModelsConfig model."""

    def test_default_values(self) -> None:
        """Test ModelsConfig has expected defaults."""
        config = ModelsConfig()

        assert config.default_model == "opus"
        assert config.model_override is None
        assert config.steps.implement == "opus"
        assert config.steps.read_docs == "sonnet"
        assert config.special.init == "opus"
        assert config.special.plan == "sonnet"

    def test_model_override(self) -> None:
        """Test ModelsConfig with model_override."""
        config = ModelsConfig(model_override="sonnet")

        assert config.model_override == "sonnet"


class TestHookConfig:
    """Tests for HookConfig model."""

    def test_default_values(self) -> None:
        """Test HookConfig has expected defaults."""
        config = HookConfig(command="npm test")

        assert config.command == "npm test"
        assert config.timeout == 300
        assert config.success_exit_codes == [0]
        assert config.failure_patterns == []
        assert config.success_patterns == []

    def test_custom_values(self) -> None:
        """Test HookConfig with custom values."""
        config = HookConfig(
            command="pytest",
            timeout=600,
            success_exit_codes=[0, 5],
            failure_patterns=["FAILED"],
            success_patterns=["passed"],
        )

        assert config.command == "pytest"
        assert config.timeout == 600
        assert config.success_exit_codes == [0, 5]
        assert config.failure_patterns == ["FAILED"]
        assert config.success_patterns == ["passed"]


class TestHooksConfig:
    """Tests for HooksConfig model."""

    def test_default_hooks_exist(self) -> None:
        """Test HooksConfig has all expected default hooks."""
        config = HooksConfig()

        assert config.test.command == "npm test"
        assert config.lint.command == "npm run lint"
        assert config.typecheck.command == "npm run typecheck"
        assert config.build.command == "npm run build"
        assert config.validate_hook.command == "npm run validate"


class TestProjectConfig:
    """Tests for ProjectConfig model."""

    def test_default_values(self) -> None:
        """Test ProjectConfig has all sections with defaults."""
        config = ProjectConfig()

        assert isinstance(config.server, ServerConfig)
        assert isinstance(config.models, ModelsConfig)
        assert isinstance(config.hooks, HooksConfig)


class TestProjectConfigServiceExists:
    """Tests for checking if config exists."""

    def test_exists_returns_false_when_not_initialized(self) -> None:
        """Test exists() returns False when config.toml doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ProjectConfigService(tmpdir)
            assert service.exists() is False

    def test_exists_returns_true_when_initialized(self) -> None:
        """Test exists() returns True when config.toml exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".claudesprint" / "config.toml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text("[server]\nurl = 'http://localhost:3000'\n")

            service = ProjectConfigService(tmpdir)
            assert service.exists() is True


class TestProjectConfigServiceLoad:
    """Tests for loading configuration."""

    def test_load_returns_defaults_when_file_missing(self) -> None:
        """Test load() returns defaults when config.toml doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ProjectConfigService(tmpdir)
            config = service.load()

            assert config.server.url == "http://localhost:3000"
            assert config.models.default_model == "opus"

    def test_load_parses_toml_file(self) -> None:
        """Test load() parses valid TOML file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".claudesprint" / "config.toml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text("""
[server]
url = "http://localhost:8080"
start_command = "python server.py"
wait_seconds = 10

[models]
default_model = "sonnet"

[hooks.test]
command = "pytest"
timeout = 600
success_exit_codes = [0]
failure_patterns = ["FAILED"]
""")

            service = ProjectConfigService(tmpdir)
            config = service.load()

            assert config.server.url == "http://localhost:8080"
            assert config.server.start_command == "python server.py"
            assert config.server.wait_seconds == 10
            assert config.models.default_model == "sonnet"
            assert config.hooks.test.command == "pytest"
            assert config.hooks.test.timeout == 600

    def test_load_returns_defaults_on_invalid_toml(self) -> None:
        """Test load() returns defaults on invalid TOML."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".claudesprint" / "config.toml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text("invalid { toml content")

            service = ProjectConfigService(tmpdir)
            config = service.load()

            # Should return defaults
            assert config.server.url == "http://localhost:3000"

    def test_load_caches_result(self) -> None:
        """Test load() caches the result."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ProjectConfigService(tmpdir)

            config1 = service.load()
            config2 = service.load()

            assert config1 is config2


class TestProjectConfigServiceSave:
    """Tests for saving configuration."""

    def test_save_creates_file(self) -> None:
        """Test save() creates config.toml file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ProjectConfigService(tmpdir)
            config = ProjectConfig(
                server=ServerConfig(url="http://localhost:8080"),
            )

            result = service.save(config)

            assert result is True
            assert service.exists() is True

    def test_save_roundtrip(self) -> None:
        """Test save() and load() roundtrip preserves data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ProjectConfigService(tmpdir)
            original = ProjectConfig(
                server=ServerConfig(
                    url="http://localhost:8080",
                    start_command="python app.py",
                    wait_seconds=10,
                ),
                models=ModelsConfig(
                    default_model="sonnet",
                ),
            )

            service.save(original)
            service.reload()
            loaded = service.load()

            assert loaded.server.url == "http://localhost:8080"
            assert loaded.server.start_command == "python app.py"
            assert loaded.server.wait_seconds == 10
            assert loaded.models.default_model == "sonnet"


class TestProjectConfigServiceInit:
    """Tests for initializing config file."""

    def test_init_creates_file_with_template(self) -> None:
        """Test init_config() creates file with default template."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ProjectConfigService(tmpdir)

            result = service.init_config()

            assert result is True
            assert service.exists() is True

            content = service.config_path.read_text()
            assert "[server]" in content
            assert "[models]" in content
            assert "[hooks.test]" in content

    def test_init_does_not_overwrite_without_flag(self) -> None:
        """Test init_config() does not overwrite existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".claudesprint" / "config.toml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text("# Custom content\n")

            service = ProjectConfigService(tmpdir)
            result = service.init_config(overwrite=False)

            assert result is False
            assert config_path.read_text() == "# Custom content\n"

    def test_init_overwrites_with_flag(self) -> None:
        """Test init_config() overwrites with overwrite=True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".claudesprint" / "config.toml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text("# Custom content\n")

            service = ProjectConfigService(tmpdir)
            result = service.init_config(overwrite=True)

            assert result is True
            content = config_path.read_text()
            assert "[server]" in content


class TestProjectConfigServiceReload:
    """Tests for reloading configuration."""

    def test_reload_clears_cache(self) -> None:
        """Test reload() clears cached config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ProjectConfigService(tmpdir)

            # Load defaults
            config1 = service.load()
            assert config1.server.url == "http://localhost:3000"

            # Create a config file
            config_path = Path(tmpdir) / ".claudesprint" / "config.toml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text('[server]\nurl = "http://localhost:9000"\n')

            # Reload should pick up new file
            config2 = service.reload()
            assert config2.server.url == "http://localhost:9000"


class TestProjectConfigServiceGetHookConfig:
    """Tests for get_hook_config method."""

    def test_get_existing_hook(self) -> None:
        """Test get_hook_config returns config for existing hook."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ProjectConfigService(tmpdir)

            hook = service.get_hook_config("test")

            assert hook is not None
            assert hook.command == "npm test"

    def test_get_nonexistent_hook(self) -> None:
        """Test get_hook_config returns None for nonexistent hook."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ProjectConfigService(tmpdir)

            hook = service.get_hook_config("nonexistent")

            assert hook is None


class TestProjectConfigServiceGetModel:
    """Tests for get_model_for_step method."""

    def test_get_model_for_step_returns_default(self) -> None:
        """Test get_model_for_step returns step-specific default."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ProjectConfigService(tmpdir)

            assert service.get_model_for_step("implement") == "opus"
            assert service.get_model_for_step("read-docs") == "sonnet"

    def test_get_model_for_step_with_override(self) -> None:
        """Test get_model_for_step respects model_override."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".claudesprint" / "config.toml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text('[models]\nmodel_override = "haiku"\n')

            service = ProjectConfigService(tmpdir)

            assert service.get_model_for_step("implement") == "haiku"
            assert service.get_model_for_step("read-docs") == "haiku"

    def test_get_model_for_special_step(self) -> None:
        """Test get_model_for_special_step returns correct model."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ProjectConfigService(tmpdir)

            assert service.get_model_for_special_step("init") == "opus"
            assert service.get_model_for_special_step("plan") == "sonnet"


class TestDefaultProjectConfigToml:
    """Tests for the default TOML template."""

    def test_template_is_valid_toml(self) -> None:
        """Test DEFAULT_PROJECT_CONFIG_TOML is valid TOML."""
        import sys
        if sys.version_info >= (3, 11):
            import tomllib
        else:
            import tomli as tomllib

        # Should not raise
        data = tomllib.loads(DEFAULT_PROJECT_CONFIG_TOML)

        assert "server" in data
        assert "models" in data
        assert "hooks" in data
        assert "runtime" in data
        assert "rate_limiting" in data
        assert "heartbeat" in data
        assert "debug" in data
        assert "timeouts" in data
        assert "advanced" in data

    def test_template_has_all_sections(self) -> None:
        """Test template has all expected sections."""
        assert "[server]" in DEFAULT_PROJECT_CONFIG_TOML
        assert "[models]" in DEFAULT_PROJECT_CONFIG_TOML
        assert "[models.steps]" in DEFAULT_PROJECT_CONFIG_TOML
        assert "[models.special]" in DEFAULT_PROJECT_CONFIG_TOML
        # Runtime and other new sections
        assert "[runtime]" in DEFAULT_PROJECT_CONFIG_TOML
        assert "[rate_limiting]" in DEFAULT_PROJECT_CONFIG_TOML
        assert "[heartbeat]" in DEFAULT_PROJECT_CONFIG_TOML
        assert "[debug]" in DEFAULT_PROJECT_CONFIG_TOML
        assert "[timeouts]" in DEFAULT_PROJECT_CONFIG_TOML
        assert "[advanced]" in DEFAULT_PROJECT_CONFIG_TOML
        # Notifications
        assert "[notifications]" in DEFAULT_PROJECT_CONFIG_TOML
        assert "[notifications.bark]" in DEFAULT_PROJECT_CONFIG_TOML
        # Hooks
        assert "[hooks.test]" in DEFAULT_PROJECT_CONFIG_TOML
        assert "[hooks.lint]" in DEFAULT_PROJECT_CONFIG_TOML
        assert "[hooks.typecheck]" in DEFAULT_PROJECT_CONFIG_TOML
        assert "[hooks.build]" in DEFAULT_PROJECT_CONFIG_TOML
        assert "[hooks.validate]" in DEFAULT_PROJECT_CONFIG_TOML


class TestBarkNotificationConfig:
    """Tests for BarkNotificationConfig model."""

    def test_default_values(self) -> None:
        """Test BarkNotificationConfig has expected defaults."""
        config = BarkNotificationConfig()

        assert config.enabled is False
        assert config.url == ""

    def test_custom_values(self) -> None:
        """Test BarkNotificationConfig with custom values."""
        config = BarkNotificationConfig(
            enabled=True,
            url="https://api.day.app/YOUR_KEY",
        )

        assert config.enabled is True
        assert config.url == "https://api.day.app/YOUR_KEY"


class TestNotificationsConfig:
    """Tests for NotificationsConfig model."""

    def test_default_values(self) -> None:
        """Test NotificationsConfig has expected defaults."""
        config = NotificationsConfig()

        assert config.enabled is True
        assert isinstance(config.bark, BarkNotificationConfig)
        assert config.bark.enabled is False
        assert config.bark.url == ""

    def test_custom_values(self) -> None:
        """Test NotificationsConfig with custom values."""
        config = NotificationsConfig(
            enabled=False,
            bark=BarkNotificationConfig(enabled=True, url="https://example.com"),
        )

        assert config.enabled is False
        assert config.bark.enabled is True
        assert config.bark.url == "https://example.com"


class TestProjectConfigWithNotifications:
    """Tests for ProjectConfig with notifications section."""

    def test_project_config_includes_notifications(self) -> None:
        """Test ProjectConfig includes notifications section."""
        config = ProjectConfig()

        assert hasattr(config, "notifications")
        assert isinstance(config.notifications, NotificationsConfig)

    def test_load_notifications_from_toml(self) -> None:
        """Test loading notifications from TOML file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".claudesprint" / "config.toml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text("""
[notifications]
enabled = false

[notifications.bark]
enabled = true
url = "https://api.day.app/TEST_KEY"
""")

            service = ProjectConfigService(tmpdir)
            config = service.load()

            assert config.notifications.enabled is False
            assert config.notifications.bark.enabled is True
            assert config.notifications.bark.url == "https://api.day.app/TEST_KEY"
