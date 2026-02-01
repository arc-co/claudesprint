"""Tests for project configuration Pydantic models."""


import pytest

from claudesprint.services.project_config_service import (
    DEFAULT_PROJECT_CONFIG_TOML,
    BarkNotificationConfig,
    ModelsConfig,
    NotificationsConfig,
    ProjectConfig,
    ServerConfig,
    WebhookNotificationConfig,
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


class TestProjectConfig:
    """Tests for ProjectConfig model."""

    def test_default_values(self) -> None:
        """Test ProjectConfig has all sections with defaults."""
        config = ProjectConfig()

        assert isinstance(config.server, ServerConfig)
        assert isinstance(config.models, ModelsConfig)


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


class TestWebhookNotificationConfig:
    """Tests for WebhookNotificationConfig model."""

    def test_default_values(self) -> None:
        """Test WebhookNotificationConfig has expected defaults."""
        config = WebhookNotificationConfig()

        assert config.enabled is False
        assert config.url == ""
        assert config.timeout == 10.0
        assert config.retry_count == 3
        assert config.headers == {}
        assert config.events == []

    def test_custom_values(self) -> None:
        """Test WebhookNotificationConfig with custom values."""
        config = WebhookNotificationConfig(
            enabled=True,
            url="https://webhook.example.com/endpoint",
            timeout=15.0,
            retry_count=5,
            headers={"Authorization": "Bearer token123"},
            events=["failure", "exit"],
        )

        assert config.enabled is True
        assert config.url == "https://webhook.example.com/endpoint"
        assert config.timeout == 15.0
        assert config.retry_count == 5
        assert config.headers == {"Authorization": "Bearer token123"}
        assert config.events == ["failure", "exit"]

    def test_timeout_validation(self) -> None:
        """Test timeout minimum validation."""
        with pytest.raises(ValueError):
            WebhookNotificationConfig(timeout=0.5)  # Below minimum of 1.0

    def test_retry_count_validation(self) -> None:
        """Test retry_count range validation."""
        # Below minimum
        with pytest.raises(ValueError):
            WebhookNotificationConfig(retry_count=-1)

        # Above maximum
        with pytest.raises(ValueError):
            WebhookNotificationConfig(retry_count=11)

        # Valid boundary values
        config_min = WebhookNotificationConfig(retry_count=0)
        assert config_min.retry_count == 0

        config_max = WebhookNotificationConfig(retry_count=10)
        assert config_max.retry_count == 10


class TestProjectConfigWithNotifications:
    """Tests for ProjectConfig with notifications section."""

    def test_project_config_includes_notifications(self) -> None:
        """Test ProjectConfig includes notifications section."""
        config = ProjectConfig()

        assert hasattr(config, "notifications")
        assert isinstance(config.notifications, NotificationsConfig)

    def test_project_config_includes_webhook(self) -> None:
        """Test ProjectConfig notifications include webhook."""
        config = ProjectConfig()

        assert hasattr(config.notifications, "webhook")
        assert isinstance(config.notifications.webhook, WebhookNotificationConfig)


class TestDefaultProjectConfigTomlWebhook:
    """Tests for webhook section in default TOML template."""

    def test_template_has_webhook_section(self) -> None:
        """Test template has notifications.webhook section."""
        assert "[notifications.webhook]" in DEFAULT_PROJECT_CONFIG_TOML

    def test_template_webhook_defaults(self) -> None:
        """Test template has expected webhook defaults."""
        import sys
        if sys.version_info >= (3, 11):
            import tomllib
        else:
            import tomli as tomllib

        data = tomllib.loads(DEFAULT_PROJECT_CONFIG_TOML)

        assert "webhook" in data["notifications"]
        webhook = data["notifications"]["webhook"]
        assert webhook["enabled"] is False
        assert webhook["url"] == ""
        assert webhook["timeout"] == 10.0
        assert webhook["retry_count"] == 3
