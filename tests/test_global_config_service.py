"""Tests for global configuration Pydantic models."""


import pytest

from claudesprint.services.global_config_service import (
    DebugConfig,
    DefaultsConfig,
    GlobalConfig,
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
