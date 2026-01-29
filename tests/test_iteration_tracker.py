"""Tests for the IterationTracker."""

import pytest

from claudesprint.core.iteration_tracker import (
    IterationTracker,
    FailureCategory,
    FailureRecord,
)


class TestFailureCategory:
    """Tests for FailureCategory enum."""

    def test_categories_exist(self):
        """All expected categories exist."""
        assert FailureCategory.LOGIC_ERROR
        assert FailureCategory.INFRA_ERROR
        assert FailureCategory.RATE_LIMIT

    def test_categories_are_distinct(self):
        """Categories have distinct values."""
        categories = [
            FailureCategory.LOGIC_ERROR,
            FailureCategory.INFRA_ERROR,
            FailureCategory.RATE_LIMIT,
        ]
        values = [c.value for c in categories]
        assert len(values) == len(set(values))


class TestIterationTrackerCreation:
    """Tests for IterationTracker initialization."""

    def test_default_limits(self):
        """Default limits are set."""
        tracker = IterationTracker()
        assert tracker.max_iterations == 50
        assert tracker.max_logic_errors == 3
        assert tracker.max_infra_errors == 10
        assert tracker.max_consecutive_failures == 5

    def test_custom_limits(self):
        """Custom limits can be set."""
        tracker = IterationTracker(
            max_iterations=100,
            max_logic_errors=5,
            max_infra_errors=20,
            max_consecutive_failures=10,
        )
        assert tracker.max_iterations == 100
        assert tracker.max_logic_errors == 5
        assert tracker.max_infra_errors == 20
        assert tracker.max_consecutive_failures == 10

    def test_initial_counts_zero(self):
        """Initial counts are zero."""
        tracker = IterationTracker()
        assert tracker.iterations == 0
        assert tracker.logic_errors == 0
        assert tracker.infra_errors == 0
        assert tracker.rate_limits == 0
        assert tracker.consecutive_failures == 0


class TestRecordIteration:
    """Tests for recording iterations."""

    def test_record_iteration_increments(self):
        """Recording iteration increments counter."""
        tracker = IterationTracker()
        assert tracker.iterations == 0

        tracker.record_iteration()
        assert tracker.iterations == 1

        tracker.record_iteration()
        assert tracker.iterations == 2


class TestRecordSuccess:
    """Tests for recording successes."""

    def test_success_resets_consecutive_failures(self):
        """Success resets consecutive failure count."""
        tracker = IterationTracker()

        # Record some failures
        tracker.record_failure(FailureCategory.INFRA_ERROR, "test")
        tracker.record_failure(FailureCategory.INFRA_ERROR, "test")
        assert tracker.consecutive_failures == 2

        # Record success
        tracker.record_success()
        assert tracker.consecutive_failures == 0


class TestRecordFailure:
    """Tests for recording failures."""

    def test_record_logic_error(self):
        """Recording logic error increments counter."""
        tracker = IterationTracker()

        tracker.record_failure(FailureCategory.LOGIC_ERROR, "Bug found")
        assert tracker.logic_errors == 1
        assert tracker.infra_errors == 0
        assert tracker.consecutive_failures == 1

    def test_record_infra_error(self):
        """Recording infra error increments counter."""
        tracker = IterationTracker()

        tracker.record_failure(FailureCategory.INFRA_ERROR, "Network timeout")
        assert tracker.infra_errors == 1
        assert tracker.logic_errors == 0
        assert tracker.consecutive_failures == 1

    def test_record_rate_limit(self):
        """Recording rate limit increments counter."""
        tracker = IterationTracker()

        tracker.record_failure(FailureCategory.RATE_LIMIT, "429 response")
        assert tracker.rate_limits == 1
        assert tracker.consecutive_failures == 1

    def test_failure_with_context(self):
        """Failures can include context."""
        tracker = IterationTracker()

        tracker.record_failure(
            FailureCategory.INFRA_ERROR,
            "Connection failed",
            host="api.example.com",
            attempt=3,
        )

        failures = tracker.get_recent_failures(1)
        assert len(failures) == 1
        assert failures[0].context["host"] == "api.example.com"
        assert failures[0].context["attempt"] == 3

    def test_total_failures(self):
        """Total failures sums all categories."""
        tracker = IterationTracker()

        tracker.record_failure(FailureCategory.LOGIC_ERROR, "test")
        tracker.record_failure(FailureCategory.INFRA_ERROR, "test")
        tracker.record_failure(FailureCategory.RATE_LIMIT, "test")

        assert tracker.total_failures == 3


class TestShouldStop:
    """Tests for should_stop() decision logic."""

    def test_should_not_stop_initially(self):
        """Fresh tracker should not stop."""
        tracker = IterationTracker()
        should_stop, reason = tracker.should_stop()
        assert should_stop is False
        assert reason is None

    def test_stop_at_max_iterations(self):
        """Stops at max iterations."""
        tracker = IterationTracker(max_iterations=3)

        for _ in range(3):
            tracker.record_iteration()

        should_stop, reason = tracker.should_stop()
        assert should_stop is True
        assert "iterations" in reason.lower()

    def test_stop_at_max_logic_errors(self):
        """Stops at max logic errors."""
        tracker = IterationTracker(max_logic_errors=2)

        tracker.record_failure(FailureCategory.LOGIC_ERROR, "error 1")
        should_stop, _ = tracker.should_stop()
        assert should_stop is False

        tracker.record_failure(FailureCategory.LOGIC_ERROR, "error 2")
        should_stop, reason = tracker.should_stop()
        assert should_stop is True
        assert "logic" in reason.lower()

    def test_stop_at_max_infra_errors(self):
        """Stops at max infrastructure errors."""
        tracker = IterationTracker(max_infra_errors=2)

        tracker.record_failure(FailureCategory.INFRA_ERROR, "error 1")
        tracker.record_failure(FailureCategory.INFRA_ERROR, "error 2")

        should_stop, reason = tracker.should_stop()
        assert should_stop is True
        assert "infrastructure" in reason.lower()

    def test_stop_at_max_consecutive_failures(self):
        """Stops at max consecutive failures."""
        tracker = IterationTracker(max_consecutive_failures=3)

        tracker.record_failure(FailureCategory.INFRA_ERROR, "error 1")
        tracker.record_failure(FailureCategory.LOGIC_ERROR, "error 2")
        tracker.record_failure(FailureCategory.INFRA_ERROR, "error 3")

        should_stop, reason = tracker.should_stop()
        assert should_stop is True
        assert "consecutive" in reason.lower()

    def test_rate_limit_does_not_trigger_stop(self):
        """Rate limits alone don't trigger stop (within other limits)."""
        tracker = IterationTracker(
            max_iterations=100,
            max_logic_errors=100,
            max_infra_errors=100,
            max_consecutive_failures=100,
        )

        # Record many rate limits
        for _ in range(50):
            tracker.record_failure(FailureCategory.RATE_LIMIT, "rate limited")

        should_stop, _ = tracker.should_stop()
        # Should stop due to consecutive failures (100) unless we reset
        # Actually this will hit consecutive_failures = 50 < 100, so should not stop
        assert should_stop is False


class TestGetRecentFailures:
    """Tests for retrieving failure history."""

    def test_get_recent_failures_empty(self):
        """No failures returns empty list."""
        tracker = IterationTracker()
        failures = tracker.get_recent_failures()
        assert failures == []

    def test_get_recent_failures_limited(self):
        """Returns limited number of recent failures."""
        tracker = IterationTracker()

        for i in range(10):
            tracker.record_failure(FailureCategory.INFRA_ERROR, f"error {i}")

        failures = tracker.get_recent_failures(3)
        assert len(failures) == 3
        # Should be newest first
        assert "error 9" in failures[0].message
        assert "error 8" in failures[1].message

    def test_failure_records_have_timestamp(self):
        """Failure records include timestamp."""
        tracker = IterationTracker()
        tracker.record_failure(FailureCategory.LOGIC_ERROR, "test")

        failures = tracker.get_recent_failures()
        assert len(failures) == 1
        assert failures[0].timestamp is not None


class TestGetStats:
    """Tests for statistics retrieval."""

    def test_get_stats(self):
        """Stats include all counters."""
        tracker = IterationTracker(
            max_iterations=50,
            max_logic_errors=3,
            max_infra_errors=10,
        )

        tracker.record_iteration()
        tracker.record_iteration()
        tracker.record_failure(FailureCategory.LOGIC_ERROR, "test")
        tracker.record_failure(FailureCategory.INFRA_ERROR, "test")

        stats = tracker.get_stats()

        assert stats["iterations"] == 2
        assert stats["max_iterations"] == 50
        assert stats["logic_errors"] == 1
        assert stats["max_logic_errors"] == 3
        assert stats["infra_errors"] == 1
        assert stats["max_infra_errors"] == 10
        assert stats["total_failures"] == 2
        assert stats["consecutive_failures"] == 2


class TestReset:
    """Tests for reset functionality."""

    def test_reset_clears_all(self):
        """Reset clears all counters and records."""
        tracker = IterationTracker()

        # Record some data
        tracker.record_iteration()
        tracker.record_failure(FailureCategory.LOGIC_ERROR, "test")
        tracker.record_failure(FailureCategory.INFRA_ERROR, "test")

        # Reset
        tracker.reset()

        # Verify all cleared
        assert tracker.iterations == 0
        assert tracker.logic_errors == 0
        assert tracker.infra_errors == 0
        assert tracker.rate_limits == 0
        assert tracker.consecutive_failures == 0
        assert tracker.get_recent_failures() == []


class TestRepr:
    """Tests for string representation."""

    def test_repr(self):
        """Repr includes useful info."""
        tracker = IterationTracker()
        tracker.record_iteration()
        tracker.record_failure(FailureCategory.LOGIC_ERROR, "test")

        repr_str = repr(tracker)
        assert "IterationTracker" in repr_str
        assert "iterations=1" in repr_str
        assert "logic=1" in repr_str


class TestCategorizedCounting:
    """Tests demonstrating differentiated retry behavior."""

    def test_logic_errors_have_lower_limit(self):
        """Logic errors stop sooner than infra errors."""
        # Use high consecutive failure limit to isolate category testing
        tracker = IterationTracker(
            max_logic_errors=3,
            max_infra_errors=10,
            max_consecutive_failures=20,
        )

        # Can have many infra errors
        for _ in range(5):
            tracker.record_failure(FailureCategory.INFRA_ERROR, "timeout")

        should_stop, _ = tracker.should_stop()
        assert should_stop is False  # Still under 10

        # But few logic errors stop quickly
        tracker.reset()
        for _ in range(3):
            tracker.record_failure(FailureCategory.LOGIC_ERROR, "bug")

        should_stop, _ = tracker.should_stop()
        assert should_stop is True  # At 3 limit

    def test_mixed_failures_tracked_separately(self):
        """Different failure types are tracked independently."""
        tracker = IterationTracker(max_logic_errors=3, max_infra_errors=3)

        # Record 2 of each - neither at limit
        tracker.record_failure(FailureCategory.LOGIC_ERROR, "bug 1")
        tracker.record_failure(FailureCategory.LOGIC_ERROR, "bug 2")
        tracker.record_failure(FailureCategory.INFRA_ERROR, "timeout 1")
        tracker.record_failure(FailureCategory.INFRA_ERROR, "timeout 2")

        should_stop, _ = tracker.should_stop()
        # With consecutive_failures default=5, we have 4, so not stopped yet
        # Logic=2, Infra=2, both under limit of 3
        assert tracker.logic_errors == 2
        assert tracker.infra_errors == 2
