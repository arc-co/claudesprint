"""Tests for rate limit handler."""

from datetime import timedelta
from unittest.mock import patch

import pytest

from claudesprint.core.rate_limit_handler import (
    RateLimitConfig,
    RateLimitHandler,
    RateLimitRetriesExhausted,
)


class TestRateLimitConfig:
    """Tests for RateLimitConfig defaults."""

    def test_config_defaults(self):
        """Verify default values match existing sprint engine config."""
        config = RateLimitConfig()

        assert config.max_retries == 3
        assert config.base_delay_seconds == 60.0
        assert config.max_delay_seconds == 900.0
        assert config.jitter_factor == 0.1

    def test_config_custom_values(self):
        """Test custom configuration values."""
        config = RateLimitConfig(
            max_retries=5,
            base_delay_seconds=30.0,
            max_delay_seconds=600.0,
            jitter_factor=0.2,
        )

        assert config.max_retries == 5
        assert config.base_delay_seconds == 30.0
        assert config.max_delay_seconds == 600.0
        assert config.jitter_factor == 0.2


class TestRateLimitRetriesExhausted:
    """Tests for RateLimitRetriesExhausted exception."""

    def test_exception_message(self):
        """Test exception message format."""
        exc = RateLimitRetriesExhausted(retries=3, max_retries=3)

        assert exc.retries == 3
        assert exc.max_retries == 3
        assert "3/3" in str(exc)


class TestRateLimitHandler:
    """Tests for RateLimitHandler."""

    def test_initial_retry_count_is_zero(self):
        """Handler starts with zero retries."""
        handler = RateLimitHandler()
        assert handler.retry_count == 0

    def test_calculate_backoff_exponential(self):
        """Test exponential backoff: base * 2^(attempt-1)."""
        config = RateLimitConfig(
            base_delay_seconds=60.0,
            max_delay_seconds=900.0,
            jitter_factor=0,  # Disable jitter for deterministic testing
        )
        handler = RateLimitHandler(config)

        # First attempt: 60 * 2^0 = 60
        assert handler.calculate_backoff(1) == timedelta(seconds=60)

        # Second attempt: 60 * 2^1 = 120
        assert handler.calculate_backoff(2) == timedelta(seconds=120)

        # Third attempt: 60 * 2^2 = 240
        assert handler.calculate_backoff(3) == timedelta(seconds=240)

        # Fourth attempt: 60 * 2^3 = 480
        assert handler.calculate_backoff(4) == timedelta(seconds=480)

    def test_calculate_backoff_capped(self):
        """Test that backoff is capped at max_delay."""
        config = RateLimitConfig(
            base_delay_seconds=60.0,
            max_delay_seconds=300.0,  # Cap at 5 minutes
            jitter_factor=0,
        )
        handler = RateLimitHandler(config)

        # Fifth attempt would be 60 * 2^4 = 960, but capped at 300
        assert handler.calculate_backoff(5) == timedelta(seconds=300)

        # Even higher attempts stay capped
        assert handler.calculate_backoff(10) == timedelta(seconds=300)

    def test_calculate_backoff_with_jitter(self):
        """Test that jitter adds +-10% randomization."""
        config = RateLimitConfig(
            base_delay_seconds=100.0,
            max_delay_seconds=1000.0,
            jitter_factor=0.1,
        )
        handler = RateLimitHandler(config)

        # Run multiple times to verify jitter is applied
        delays = [handler.calculate_backoff(1).total_seconds() for _ in range(100)]

        # Base delay for attempt 1 is 100 seconds
        # With 10% jitter, range should be 90-110 seconds
        assert min(delays) >= 90
        assert max(delays) <= 110

        # Verify there's actual variation (not all the same value)
        unique_delays = set(delays)
        assert len(unique_delays) > 1, "Jitter should produce varied delays"

    def test_calculate_backoff_uses_retry_count_by_default(self):
        """Test that calculate_backoff uses current retry_count when no attempt given."""
        config = RateLimitConfig(
            base_delay_seconds=60.0,
            jitter_factor=0,
        )
        handler = RateLimitHandler(config)

        # Record some retries
        handler.record_rate_limit()
        handler.record_rate_limit()
        assert handler.retry_count == 2

        # Should use retry_count (2) as attempt
        # 60 * 2^1 = 120
        assert handler.calculate_backoff() == timedelta(seconds=120)

    def test_calculate_backoff_zero_or_negative_attempt(self):
        """Test edge case handling for zero or negative attempt."""
        config = RateLimitConfig(
            base_delay_seconds=60.0,
            jitter_factor=0,
        )
        handler = RateLimitHandler(config)

        # Should treat 0 and negative as attempt 1
        assert handler.calculate_backoff(0) == timedelta(seconds=60)
        assert handler.calculate_backoff(-1) == timedelta(seconds=60)

    def test_should_retry_within_limit(self):
        """Test should_retry returns True when retries < max."""
        config = RateLimitConfig(max_retries=3)
        handler = RateLimitHandler(config)

        assert handler.should_retry() is True

        handler.record_rate_limit()  # retry_count = 1
        assert handler.should_retry() is True

        handler.record_rate_limit()  # retry_count = 2
        assert handler.should_retry() is True

    def test_should_retry_exceeded(self):
        """Test should_retry returns False when retries >= max."""
        config = RateLimitConfig(max_retries=3)
        handler = RateLimitHandler(config)

        handler.record_rate_limit()  # 1
        handler.record_rate_limit()  # 2
        handler.record_rate_limit()  # 3

        assert handler.should_retry() is False

        # Additional retries still return False
        handler.record_rate_limit()  # 4
        assert handler.should_retry() is False

    def test_reset_clears_counter(self):
        """Test reset() sets retry count back to zero."""
        config = RateLimitConfig(max_retries=3)
        handler = RateLimitHandler(config)

        handler.record_rate_limit()
        handler.record_rate_limit()
        assert handler.retry_count == 2

        handler.reset()
        assert handler.retry_count == 0
        assert handler.should_retry() is True

    def test_record_rate_limit_increments(self):
        """Test that each record_rate_limit() increments the counter."""
        handler = RateLimitHandler()

        assert handler.retry_count == 0

        handler.record_rate_limit()
        assert handler.retry_count == 1

        handler.record_rate_limit()
        assert handler.retry_count == 2

        handler.record_rate_limit()
        assert handler.retry_count == 3

    def test_get_backoff_seconds(self):
        """Test get_backoff_seconds returns integer seconds."""
        config = RateLimitConfig(
            base_delay_seconds=60.5,  # Non-integer to test truncation
            jitter_factor=0,
        )
        handler = RateLimitHandler(config)

        result = handler.get_backoff_seconds(1)
        assert isinstance(result, int)
        assert result == 60

    def test_default_config_when_none_provided(self):
        """Test that handler uses default config when None is provided."""
        handler = RateLimitHandler(None)

        assert handler.config.max_retries == 3
        assert handler.config.base_delay_seconds == 60.0
        assert handler.config.max_delay_seconds == 900.0
        assert handler.config.jitter_factor == 0.1


class TestRateLimitHandlerIntegration:
    """Integration tests for typical usage patterns."""

    def test_typical_retry_loop(self):
        """Test typical retry loop pattern."""
        config = RateLimitConfig(max_retries=3, jitter_factor=0)
        handler = RateLimitHandler(config)

        retries_made = 0
        while handler.should_retry():
            handler.record_rate_limit()
            retries_made += 1

        assert retries_made == 3
        assert not handler.should_retry()

    def test_reset_after_success(self):
        """Test resetting handler after successful operation."""
        config = RateLimitConfig(max_retries=3)
        handler = RateLimitHandler(config)

        # First operation: 2 retries then success
        handler.record_rate_limit()
        handler.record_rate_limit()
        assert handler.retry_count == 2

        # Success! Reset counter
        handler.reset()
        assert handler.retry_count == 0

        # Second operation: should start fresh
        assert handler.should_retry() is True
        handler.record_rate_limit()
        handler.record_rate_limit()
        handler.record_rate_limit()
        assert not handler.should_retry()
