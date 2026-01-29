"""Tests for project configuration Pydantic models."""

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
