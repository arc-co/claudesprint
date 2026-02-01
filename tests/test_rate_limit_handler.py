"""Tests for tenacity-based rate limit handler."""

from unittest.mock import MagicMock

import pytest

from claudesprint.core.rate_limit_handler import (
    RateLimitConfig,
    RateLimitRetriesExhausted,
    create_rate_limit_retry,
    create_rate_limit_retrying,
    get_retry_state_info,
)
from claudesprint.exceptions import RateLimitDetected


class TestRateLimitConfig:
    """Tests for RateLimitConfig with tenacity parameters."""

    def test_config_defaults(self):
        """Verify default values match the plan specifications."""
        config = RateLimitConfig()

        assert config.max_attempts == 5
        assert config.wait_min == 4.0
        assert config.wait_max == 60.0
        assert config.wait_multiplier == 1.0
        assert config.before_sleep_callback is None

    def test_config_custom_values(self):
        """Test custom configuration values."""
        callback = MagicMock()
        config = RateLimitConfig(
            max_attempts=10,
            wait_min=2.0,
            wait_max=120.0,
            wait_multiplier=2.0,
            before_sleep_callback=callback,
        )

        assert config.max_attempts == 10
        assert config.wait_min == 2.0
        assert config.wait_max == 120.0
        assert config.wait_multiplier == 2.0
        assert config.before_sleep_callback is callback


class TestRateLimitRetriesExhausted:
    """Tests for RateLimitRetriesExhausted exception (backward compatibility)."""

    def test_exception_message(self):
        """Test exception message format."""
        exc = RateLimitRetriesExhausted(retries=3, max_retries=5)

        assert exc.retries == 3
        assert exc.max_retries == 5
        assert "3/5" in str(exc)


class TestCreateRateLimitRetry:
    """Tests for the tenacity retry decorator factory."""

    def test_decorator_retries_on_rate_limit_detected(self):
        """Test that decorator retries when RateLimitDetected is raised."""
        config = RateLimitConfig(max_attempts=3, wait_min=0, wait_max=0)
        call_count = 0

        @create_rate_limit_retry(config)
        def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RateLimitDetected("Rate limited")
            return "success"

        result = flaky_function()

        assert result == "success"
        assert call_count == 3

    def test_decorator_raises_after_max_attempts(self):
        """Test that decorator raises after exhausting retries."""
        config = RateLimitConfig(max_attempts=3, wait_min=0, wait_max=0)
        call_count = 0

        @create_rate_limit_retry(config)
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise RateLimitDetected("Rate limited")

        with pytest.raises(RateLimitDetected):
            always_fails()

        assert call_count == 3

    def test_decorator_does_not_retry_other_exceptions(self):
        """Test that decorator doesn't retry non-RateLimitDetected exceptions."""
        config = RateLimitConfig(max_attempts=3, wait_min=0, wait_max=0)
        call_count = 0

        @create_rate_limit_retry(config)
        def raises_value_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("Not a rate limit")

        with pytest.raises(ValueError):
            raises_value_error()

        # Should only be called once since ValueError is not retried
        assert call_count == 1

    def test_decorator_calls_before_sleep_callback(self):
        """Test that before_sleep callback is invoked on retry."""
        callback = MagicMock()
        config = RateLimitConfig(
            max_attempts=3,
            wait_min=0,
            wait_max=0,
            before_sleep_callback=callback,
        )
        call_count = 0

        @create_rate_limit_retry(config)
        def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RateLimitDetected("Rate limited")
            return "success"

        flaky_function()

        # Callback should be called twice (before each retry sleep)
        assert callback.call_count == 2

    def test_decorator_with_default_config(self):
        """Test decorator works with None config (uses defaults)."""
        call_count = 0

        @create_rate_limit_retry(None)
        def success_function():
            nonlocal call_count
            call_count += 1
            return "success"

        result = success_function()

        assert result == "success"
        assert call_count == 1


class TestCreateRateLimitRetrying:
    """Tests for the tenacity Retrying context manager factory."""

    def test_retrying_succeeds_on_first_attempt(self):
        """Test Retrying succeeds immediately when no exception."""
        config = RateLimitConfig(max_attempts=3, wait_min=0, wait_max=0)
        call_count = 0

        for attempt in create_rate_limit_retrying(config):
            with attempt:
                call_count += 1
                result = "success"

        assert result == "success"
        assert call_count == 1

    def test_retrying_retries_on_rate_limit_detected(self):
        """Test Retrying retries when RateLimitDetected is raised."""
        config = RateLimitConfig(max_attempts=3, wait_min=0, wait_max=0)
        call_count = 0
        result = None

        for attempt in create_rate_limit_retrying(config):
            with attempt:
                call_count += 1
                if call_count < 3:
                    raise RateLimitDetected("Rate limited")
                result = "success"

        assert result == "success"
        assert call_count == 3

    def test_retrying_raises_after_max_attempts(self):
        """Test Retrying raises RateLimitDetected after exhausting retries.

        With reraise=True, tenacity re-raises the original exception rather
        than wrapping it in RetryError.
        """
        config = RateLimitConfig(max_attempts=3, wait_min=0, wait_max=0)
        call_count = 0

        with pytest.raises(RateLimitDetected):
            for attempt in create_rate_limit_retrying(config):
                with attempt:
                    call_count += 1
                    raise RateLimitDetected("Rate limited")

        assert call_count == 3

    def test_retrying_does_not_retry_other_exceptions(self):
        """Test Retrying doesn't retry non-RateLimitDetected exceptions."""
        config = RateLimitConfig(max_attempts=3, wait_min=0, wait_max=0)
        call_count = 0

        with pytest.raises(ValueError):
            for attempt in create_rate_limit_retrying(config):
                with attempt:
                    call_count += 1
                    raise ValueError("Not a rate limit")

        assert call_count == 1

    def test_retrying_calls_before_sleep_callback(self):
        """Test that before_sleep callback is invoked on retry."""
        callback = MagicMock()
        config = RateLimitConfig(
            max_attempts=3,
            wait_min=0,
            wait_max=0,
            before_sleep_callback=callback,
        )
        call_count = 0
        result = None

        for attempt in create_rate_limit_retrying(config):
            with attempt:
                call_count += 1
                if call_count < 3:
                    raise RateLimitDetected("Rate limited")
                result = "success"

        assert result == "success"
        # Callback called twice (before each retry sleep)
        assert callback.call_count == 2

    def test_retrying_with_default_config(self):
        """Test Retrying works with None config (uses defaults)."""
        call_count = 0

        for attempt in create_rate_limit_retrying(None):
            with attempt:
                call_count += 1
                result = "success"

        assert result == "success"
        assert call_count == 1


class TestGetRetryStateInfo:
    """Tests for the retry state info extraction utility."""

    def test_extracts_attempt_number(self):
        """Test extraction of attempt number from retry state."""
        mock_state = MagicMock()
        mock_state.attempt_number = 3
        mock_state.next_action = MagicMock()
        mock_state.next_action.sleep = 10.5
        mock_state.outcome = None

        info = get_retry_state_info(mock_state)

        assert info["attempt_number"] == 3
        assert info["wait_seconds"] == 10.5
        assert info["exception"] is None

    def test_extracts_exception_info(self):
        """Test extraction of exception info from retry state."""
        mock_state = MagicMock()
        mock_state.attempt_number = 2
        mock_state.next_action = MagicMock()
        mock_state.next_action.sleep = 5.0
        mock_state.outcome = MagicMock()
        mock_state.outcome.exception.return_value = RateLimitDetected("Test error")

        info = get_retry_state_info(mock_state)

        assert info["attempt_number"] == 2
        assert info["wait_seconds"] == 5.0
        assert "Test error" in info["exception"]

    def test_handles_no_next_action(self):
        """Test handling when next_action is None."""
        mock_state = MagicMock()
        mock_state.attempt_number = 1
        mock_state.next_action = None
        mock_state.outcome = None

        info = get_retry_state_info(mock_state)

        assert info["attempt_number"] == 1
        assert info["wait_seconds"] == 0
        assert info["exception"] is None


class TestRateLimitDetectedException:
    """Tests for the RateLimitDetected exception used with tenacity."""

    def test_exception_with_default_message(self):
        """Test exception with default message."""
        exc = RateLimitDetected()

        assert "Rate limit detected" in str(exc)

    def test_exception_with_custom_message(self):
        """Test exception with custom message."""
        exc = RateLimitDetected("Custom rate limit message")

        assert "Custom rate limit message" in str(exc)

    def test_exception_with_output_context(self):
        """Test exception stores output in context."""
        exc = RateLimitDetected(
            message="Rate limited",
            output="API returned 429",
        )

        assert exc.context.get("output") == "API returned 429"


class TestIntegrationPatterns:
    """Integration tests for typical usage patterns."""

    def test_typical_retry_loop_with_context_manager(self):
        """Test typical retry loop pattern using Retrying context manager."""
        config = RateLimitConfig(max_attempts=5, wait_min=0, wait_max=0)
        attempts = 0
        result = None

        for attempt in create_rate_limit_retrying(config):
            with attempt:
                attempts += 1
                if attempts < 3:
                    raise RateLimitDetected("Simulated rate limit")
                result = "Operation succeeded"

        assert result == "Operation succeeded"
        assert attempts == 3

    def test_decorator_pattern_for_api_call(self):
        """Test decorator pattern for wrapping API calls."""
        config = RateLimitConfig(max_attempts=5, wait_min=0, wait_max=0)
        api_calls = []

        @create_rate_limit_retry(config)
        def mock_api_call(data: str) -> str:
            api_calls.append(data)
            if len(api_calls) < 2:
                raise RateLimitDetected("API rate limited")
            return f"Result: {data}"

        result = mock_api_call("test_data")

        assert result == "Result: test_data"
        assert len(api_calls) == 2
        assert all(call == "test_data" for call in api_calls)

    def test_callback_receives_retry_info(self):
        """Test that callback receives useful retry information."""
        received_info = []

        def capture_callback(retry_state):
            info = get_retry_state_info(retry_state)
            received_info.append(info)

        config = RateLimitConfig(
            max_attempts=4,
            wait_min=0,
            wait_max=0,
            before_sleep_callback=capture_callback,
        )
        call_count = 0

        for attempt in create_rate_limit_retrying(config):
            with attempt:
                call_count += 1
                if call_count < 3:
                    raise RateLimitDetected("Rate limit")
                break

        # Should have 2 callbacks (before attempts 2 and 3)
        assert len(received_info) == 2
        assert received_info[0]["attempt_number"] == 1
        assert received_info[1]["attempt_number"] == 2

    def test_early_exit_on_success(self):
        """Test that retry loop exits immediately on success."""
        config = RateLimitConfig(max_attempts=10, wait_min=0, wait_max=0)
        iterations = 0

        for attempt in create_rate_limit_retrying(config):
            with attempt:
                iterations += 1
                # Success on first try
                result = "immediate success"

        assert result == "immediate success"
        assert iterations == 1
