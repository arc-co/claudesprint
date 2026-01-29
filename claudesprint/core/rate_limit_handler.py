"""Rate limit handling with exponential backoff.

Encapsulates rate limit tracking and backoff calculation for the sprint engine.
"""

import random
from dataclasses import dataclass
from datetime import timedelta


@dataclass
class RateLimitConfig:
    """Configuration for rate limit handling."""

    max_retries: int = 3
    base_delay_seconds: float = 60.0
    max_delay_seconds: float = 900.0
    jitter_factor: float = 0.1


class RateLimitExceeded(Exception):
    """Raised when max rate limit retries are exhausted."""

    def __init__(self, retries: int, max_retries: int) -> None:
        self.retries = retries
        self.max_retries = max_retries
        super().__init__(
            f"Rate limit retries exhausted: {retries}/{max_retries}"
        )


class RateLimitHandler:
    """Handles rate limiting with exponential backoff.

    Tracks retry count and calculates backoff delays with optional jitter.

    Example:
        handler = RateLimitHandler(RateLimitConfig(max_retries=3))

        while should_continue:
            try:
                result = api_call()
            except RateLimitError:
                handler.record_rate_limit()
                if not handler.should_retry():
                    raise RateLimitExceeded(...)
                wait = handler.calculate_backoff()
                time.sleep(wait.total_seconds())
    """

    def __init__(self, config: RateLimitConfig | None = None) -> None:
        """Initialize rate limit handler.

        Args:
            config: Rate limit configuration. Uses defaults if not provided.
        """
        self.config = config or RateLimitConfig()
        self._retry_count = 0

    @property
    def retry_count(self) -> int:
        """Current number of rate limit retries."""
        return self._retry_count

    def reset(self) -> None:
        """Reset the retry counter to zero.

        Call this after a successful operation to reset the backoff state.
        """
        self._retry_count = 0

    def calculate_backoff(self, attempt: int | None = None) -> timedelta:
        """Calculate exponential backoff delay.

        Uses formula: base * 2^(attempt-1), capped at max_delay.
        Adds random jitter of ±jitter_factor to prevent thundering herd.

        Args:
            attempt: Retry attempt number (1-based). If None, uses current retry_count.

        Returns:
            Backoff delay as timedelta.
        """
        if attempt is None:
            attempt = self._retry_count

        # Handle edge case of attempt <= 0
        if attempt <= 0:
            attempt = 1

        # Exponential backoff: base * 2^(attempt-1)
        exponent = attempt - 1
        delay = self.config.base_delay_seconds * (2 ** exponent)

        # Cap at max delay
        delay = min(delay, self.config.max_delay_seconds)

        # Add jitter: ±jitter_factor
        if self.config.jitter_factor > 0:
            jitter_range = delay * self.config.jitter_factor
            jitter = random.uniform(-jitter_range, jitter_range)
            delay += jitter
            # Ensure delay doesn't go below 0
            delay = max(0, delay)

        return timedelta(seconds=delay)

    def should_retry(self) -> bool:
        """Check if another retry is allowed.

        Returns:
            True if retry_count < max_retries, False otherwise.
        """
        return self._retry_count < self.config.max_retries

    def record_rate_limit(self) -> None:
        """Record that a rate limit was encountered.

        Increments the internal retry counter.
        """
        self._retry_count += 1

    def get_backoff_seconds(self, attempt: int | None = None) -> int:
        """Get backoff delay as integer seconds.

        Convenience method that returns integer seconds for compatibility
        with existing code that uses int seconds.

        Args:
            attempt: Retry attempt number (1-based). If None, uses current retry_count.

        Returns:
            Backoff delay in whole seconds.
        """
        return int(self.calculate_backoff(attempt).total_seconds())
