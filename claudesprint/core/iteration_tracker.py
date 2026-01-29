"""Iteration tracking with categorized failure counting.

Distinguishes between infrastructure failures and logic errors
to enable smarter retry behavior.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum, auto
from typing import Any

logger = logging.getLogger(__name__)


class FailureCategory(Enum):
    """Categories of failures for differentiated retry handling.

    LOGIC_ERROR: Bug or fundamental issue that won't be fixed by retrying.
        Limited retries to avoid wasting resources.
        Examples: Invalid state transition, malformed data, assertion failure.

    INFRA_ERROR: Transient infrastructure issue that may resolve.
        More retries allowed since these often self-heal.
        Examples: Network timeout, file system busy, subprocess failure.

    RATE_LIMIT: API rate limiting that requires waiting.
        Not counted toward retry limits since waiting resolves it.
        Examples: Claude API 429, GitHub rate limit.
    """

    LOGIC_ERROR = auto()
    INFRA_ERROR = auto()
    RATE_LIMIT = auto()


@dataclass
class FailureRecord:
    """Record of a single failure occurrence."""

    category: FailureCategory
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    context: dict[str, Any] = field(default_factory=dict)


class IterationTracker:
    """Tracks iterations and failures with categorized counting.

    Provides separate limits for logic errors vs infrastructure errors,
    allowing more retries for transient issues while failing fast for
    fundamental bugs.

    Example:
        tracker = IterationTracker(max_logic_errors=3, max_infra_errors=10)

        for iteration in range(100):
            tracker.record_iteration()

            try:
                result = do_work()
            except NetworkError as e:
                tracker.record_failure(FailureCategory.INFRA_ERROR, str(e))
            except ValidationError as e:
                tracker.record_failure(FailureCategory.LOGIC_ERROR, str(e))
            except RateLimitError as e:
                tracker.record_failure(FailureCategory.RATE_LIMIT, str(e))
                time.sleep(e.retry_after)
                continue

            should_stop, reason = tracker.should_stop()
            if should_stop:
                raise RuntimeError(f"Stopping: {reason}")
    """

    def __init__(
        self,
        max_iterations: int = 50,
        max_logic_errors: int = 3,
        max_infra_errors: int = 10,
        max_consecutive_failures: int = 5,
    ) -> None:
        """Initialize IterationTracker.

        Args:
            max_iterations: Maximum total iterations allowed.
            max_logic_errors: Maximum logic errors before stopping.
            max_infra_errors: Maximum infrastructure errors before stopping.
            max_consecutive_failures: Maximum failures in a row before stopping.
        """
        self.max_iterations = max_iterations
        self.max_logic_errors = max_logic_errors
        self.max_infra_errors = max_infra_errors
        self.max_consecutive_failures = max_consecutive_failures

        self._iterations: int = 0
        self._logic_errors: int = 0
        self._infra_errors: int = 0
        self._rate_limits: int = 0
        self._consecutive_failures: int = 0
        self._failures: list[FailureRecord] = []

    @property
    def iterations(self) -> int:
        """Total iterations recorded."""
        return self._iterations

    @property
    def logic_errors(self) -> int:
        """Total logic errors recorded."""
        return self._logic_errors

    @property
    def infra_errors(self) -> int:
        """Total infrastructure errors recorded."""
        return self._infra_errors

    @property
    def rate_limits(self) -> int:
        """Total rate limit errors recorded."""
        return self._rate_limits

    @property
    def total_failures(self) -> int:
        """Total failures of all types."""
        return self._logic_errors + self._infra_errors + self._rate_limits

    @property
    def consecutive_failures(self) -> int:
        """Current consecutive failure count."""
        return self._consecutive_failures

    def record_iteration(self) -> None:
        """Record a new iteration."""
        self._iterations += 1
        logger.debug(f"Iteration {self._iterations}/{self.max_iterations}")

    def record_success(self) -> None:
        """Record a successful operation, resetting consecutive failure count."""
        self._consecutive_failures = 0

    def record_failure(
        self,
        category: FailureCategory,
        message: str,
        **context: Any,
    ) -> None:
        """Record a failure with its category.

        Args:
            category: Type of failure.
            message: Description of the failure.
            **context: Additional context information.
        """
        record = FailureRecord(
            category=category,
            message=message,
            context=context,
        )
        self._failures.append(record)
        self._consecutive_failures += 1

        if category == FailureCategory.LOGIC_ERROR:
            self._logic_errors += 1
            logger.warning(
                f"Logic error ({self._logic_errors}/{self.max_logic_errors}): {message}"
            )
        elif category == FailureCategory.INFRA_ERROR:
            self._infra_errors += 1
            logger.warning(
                f"Infra error ({self._infra_errors}/{self.max_infra_errors}): {message}"
            )
        elif category == FailureCategory.RATE_LIMIT:
            self._rate_limits += 1
            logger.info(f"Rate limit hit: {message}")

    def should_stop(self) -> tuple[bool, str | None]:
        """Check if iteration should stop based on limits.

        Returns:
            Tuple of (should_stop, reason). If should_stop is True,
            reason contains the explanation.
        """
        if self._iterations >= self.max_iterations:
            return True, f"Max iterations reached ({self._iterations})"

        if self._logic_errors >= self.max_logic_errors:
            return True, f"Too many logic errors ({self._logic_errors})"

        if self._infra_errors >= self.max_infra_errors:
            return True, f"Too many infrastructure errors ({self._infra_errors})"

        if self._consecutive_failures >= self.max_consecutive_failures:
            return True, f"Too many consecutive failures ({self._consecutive_failures})"

        return False, None

    def get_recent_failures(self, count: int = 5) -> list[FailureRecord]:
        """Get the most recent failure records.

        Args:
            count: Maximum number of records to return.

        Returns:
            List of recent FailureRecords, newest first.
        """
        return list(reversed(self._failures[-count:]))

    def get_stats(self) -> dict[str, Any]:
        """Get current tracking statistics.

        Returns:
            Dictionary with iteration and failure counts.
        """
        return {
            "iterations": self._iterations,
            "max_iterations": self.max_iterations,
            "logic_errors": self._logic_errors,
            "max_logic_errors": self.max_logic_errors,
            "infra_errors": self._infra_errors,
            "max_infra_errors": self.max_infra_errors,
            "rate_limits": self._rate_limits,
            "consecutive_failures": self._consecutive_failures,
            "max_consecutive_failures": self.max_consecutive_failures,
            "total_failures": self.total_failures,
        }

    def reset(self) -> None:
        """Reset all counters and records."""
        self._iterations = 0
        self._logic_errors = 0
        self._infra_errors = 0
        self._rate_limits = 0
        self._consecutive_failures = 0
        self._failures.clear()

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"IterationTracker(iterations={self._iterations}/{self.max_iterations}, "
            f"logic={self._logic_errors}/{self.max_logic_errors}, "
            f"infra={self._infra_errors}/{self.max_infra_errors}, "
            f"consecutive={self._consecutive_failures})"
        )
