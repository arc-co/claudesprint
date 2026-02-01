"""Rate limit handling with tenacity-based exponential backoff.

Provides factory functions for creating tenacity retry decorators and
context managers with configurable exponential backoff.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from tenacity import (
    RetryCallState,
    Retrying,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from claudesprint.exceptions import RateLimitDetected


@dataclass
class RateLimitConfig:
    """Configuration for rate limit handling with tenacity.

    Attributes:
        max_attempts: Maximum number of retry attempts (default: 5).
        wait_min: Minimum wait time in seconds (default: 4).
        wait_max: Maximum wait time in seconds (default: 60).
        wait_multiplier: Multiplier for exponential backoff (default: 1).
    """

    max_attempts: int = 5
    wait_min: float = 4.0
    wait_max: float = 60.0
    wait_multiplier: float = 1.0

    # Callbacks for integration with event systems
    before_sleep_callback: Callable[[RetryCallState], None] | None = field(
        default=None, repr=False
    )


class RateLimitRetriesExhausted(Exception):
    """Raised when max rate limit retries are exhausted.

    Kept for backward compatibility with existing code.
    """

    def __init__(self, retries: int, max_retries: int) -> None:
        self.retries = retries
        self.max_retries = max_retries
        super().__init__(
            f"Rate limit retries exhausted: {retries}/{max_retries}"
        )


def create_rate_limit_retry(
    config: RateLimitConfig | None = None,
) -> Callable:
    """Create a tenacity retry decorator for rate limit handling.

    The decorator will retry on RateLimitDetected exceptions using
    exponential backoff with the configured parameters.

    Args:
        config: Rate limit configuration. Uses defaults if not provided.

    Returns:
        A tenacity retry decorator configured for rate limit handling.

    Example:
        config = RateLimitConfig(max_attempts=5, wait_min=4, wait_max=60)

        @create_rate_limit_retry(config)
        def call_api():
            result = api.call()
            if is_rate_limited(result):
                raise RateLimitDetected("Rate limit detected")
            return result
    """
    config = config or RateLimitConfig()

    decorator_kwargs = {
        "retry": retry_if_exception_type(RateLimitDetected),
        "stop": stop_after_attempt(config.max_attempts),
        "wait": wait_exponential(
            multiplier=config.wait_multiplier,
            min=config.wait_min,
            max=config.wait_max,
        ),
        "reraise": True,
    }

    if config.before_sleep_callback:
        decorator_kwargs["before_sleep"] = config.before_sleep_callback

    return retry(**decorator_kwargs)


def create_rate_limit_retrying(
    config: RateLimitConfig | None = None,
) -> Retrying:
    """Create a tenacity Retrying context manager for rate limit handling.

    Use this when you need programmatic control over the retry loop,
    such as when rate limits are detected via output parsing rather
    than exceptions.

    Args:
        config: Rate limit configuration. Uses defaults if not provided.

    Returns:
        A tenacity Retrying context manager configured for rate limit handling.

    Example:
        config = RateLimitConfig(max_attempts=5, wait_min=4, wait_max=60)

        for attempt in create_rate_limit_retrying(config):
            with attempt:
                result = call_api()
                if is_rate_limited(result):
                    raise RateLimitDetected("Rate limit detected")
                return result
    """
    config = config or RateLimitConfig()

    retrying_kwargs = {
        "retry": retry_if_exception_type(RateLimitDetected),
        "stop": stop_after_attempt(config.max_attempts),
        "wait": wait_exponential(
            multiplier=config.wait_multiplier,
            min=config.wait_min,
            max=config.wait_max,
        ),
        "reraise": True,
    }

    if config.before_sleep_callback:
        retrying_kwargs["before_sleep"] = config.before_sleep_callback

    return Retrying(**retrying_kwargs)


def get_retry_state_info(retry_state: RetryCallState) -> dict:
    """Extract useful information from a tenacity RetryCallState.

    Useful for logging and event emission in before_sleep callbacks.

    Args:
        retry_state: The tenacity retry state object.

    Returns:
        Dictionary with attempt_number, wait_seconds, and exception info.
    """
    return {
        "attempt_number": retry_state.attempt_number,
        "wait_seconds": retry_state.next_action.sleep if retry_state.next_action else 0,
        "exception": str(retry_state.outcome.exception()) if retry_state.outcome else None,
    }
