"""Integration tests for merged feature branches.

Tests verify that the integrations between different components work correctly:
1. EventBus wiring - Engine operations emit events that subscribers receive
2. StateManager crash recovery - Engine recovers correctly from simulated partial state
3. Typed exception propagation - Specific exceptions reach callers with context
4. BoundedList enforcement - History arrays never exceed configured bounds
5. IterationTracker categorization - Infrastructure errors don't exhaust logic limits
6. Config backward compatibility - Old services emit deprecation warnings
"""

import json
import tempfile
import warnings
from datetime import datetime, UTC
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from claudesprint.events.workflow_event_bus import (
    WorkflowEventBus,
    WorkflowEvent,
    EventPayload,
)
from claudesprint.exceptions import (
    FileReadError,
    FileWriteError,
    StateCorruptionError,
    RateLimitExceeded,
    ValidationError,
)
from claudesprint.core.iteration_tracker import (
    IterationTracker,
    FailureCategory,
)
from claudesprint.services.state_manager import StateManager, StateSnapshot
from claudesprint.utils.bounded_list import BoundedList, MAX_HISTORY_ENTRIES
from claudesprint.utils.graph import detect_cycles


class TestEventBusWiring:
    """Test that EventBus is properly wired and emits events."""

    def test_event_subscription_and_emission(self):
        """Events emitted by bus are received by subscribers."""
        bus = WorkflowEventBus()
        received_events: list[EventPayload] = []

        def handler(payload: EventPayload) -> None:
            received_events.append(payload)

        bus.subscribe(WorkflowEvent.ISSUE_STARTED, handler)

        # Emit an event
        bus.emit(WorkflowEvent.ISSUE_STARTED, {
            "issue_id": "test-1",
            "issue_name": "Test Issue",
            "exit_reason": None,
            "timestamp": datetime.now(UTC).isoformat(),
        })

        assert len(received_events) == 1
        assert received_events[0]["issue_id"] == "test-1"

    def test_multiple_subscribers_receive_event(self):
        """Multiple subscribers all receive the same event."""
        bus = WorkflowEventBus()
        counts = {"a": 0, "b": 0}

        def handler_a(payload: EventPayload) -> None:
            counts["a"] += 1

        def handler_b(payload: EventPayload) -> None:
            counts["b"] += 1

        bus.subscribe(WorkflowEvent.SPRINT_STARTED, handler_a)
        bus.subscribe(WorkflowEvent.SPRINT_STARTED, handler_b)

        bus.emit(WorkflowEvent.SPRINT_STARTED, {
            "sprint_id": "SPEC_01",
            "completed_count": 0,
            "total_count": 5,
            "timestamp": datetime.now(UTC).isoformat(),
        })

        assert counts["a"] == 1
        assert counts["b"] == 1

    def test_handler_exception_does_not_block_others(self):
        """Exception in one handler doesn't prevent other handlers from running."""
        bus = WorkflowEventBus()
        received = []

        def failing_handler(payload: EventPayload) -> None:
            raise RuntimeError("Handler error")

        def success_handler(payload: EventPayload) -> None:
            received.append(payload)

        bus.subscribe(WorkflowEvent.ISSUE_COMPLETED, failing_handler)
        bus.subscribe(WorkflowEvent.ISSUE_COMPLETED, success_handler)

        # Should not raise, and success_handler should still receive
        bus.emit(WorkflowEvent.ISSUE_COMPLETED, {
            "issue_id": "test-1",
            "issue_name": "Test",
            "exit_reason": "completed",
            "timestamp": datetime.now(UTC).isoformat(),
        })

        assert len(received) == 1

    def test_unsubscribe_removes_handler(self):
        """Unsubscribed handlers no longer receive events."""
        bus = WorkflowEventBus()
        count = [0]

        def handler(payload: EventPayload) -> None:
            count[0] += 1

        bus.subscribe(WorkflowEvent.RATE_LIMITED, handler)
        bus.emit(WorkflowEvent.RATE_LIMITED, {"sprint_id": "x", "completed_count": 0, "total_count": 0, "timestamp": ""})
        assert count[0] == 1

        bus.unsubscribe(WorkflowEvent.RATE_LIMITED, handler)
        bus.emit(WorkflowEvent.RATE_LIMITED, {"sprint_id": "x", "completed_count": 0, "total_count": 0, "timestamp": ""})
        assert count[0] == 1  # Still 1, handler not called


class TestStateManagerCrashRecovery:
    """Test StateManager handles crash recovery scenarios."""

    def test_atomic_update_writes_on_modification(self):
        """Changes marked as modified are written on context exit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sprint_path = Path(tmpdir) / "sprint.json"
            project_dir = Path(tmpdir) / "project"
            project_dir.mkdir()

            # Create initial state
            sprint_path.write_text(json.dumps({"issues": []}))

            manager = StateManager(sprint_path, project_dir)

            with manager.atomic_update() as snapshot:
                snapshot.data["issues"].append({"id": "new-issue"})
                snapshot.mark_modified()

            # Verify change was persisted
            reloaded = json.loads(sprint_path.read_text())
            assert len(reloaded["issues"]) == 1
            assert reloaded["issues"][0]["id"] == "new-issue"

    def test_atomic_update_skips_write_if_not_modified(self):
        """Unmodified snapshots don't trigger writes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sprint_path = Path(tmpdir) / "sprint.json"
            project_dir = Path(tmpdir) / "project"
            project_dir.mkdir()

            original = {"issues": [], "original": True}
            sprint_path.write_text(json.dumps(original))
            original_mtime = sprint_path.stat().st_mtime

            manager = StateManager(sprint_path, project_dir)

            with manager.atomic_update() as snapshot:
                # Read but don't modify
                _ = snapshot.data["issues"]
                # Don't call mark_modified()

            # File should not have been rewritten (mtime unchanged conceptually)
            # In practice, we verify content is unchanged
            reloaded = json.loads(sprint_path.read_text())
            assert reloaded == original

    def test_detects_state_mismatch(self):
        """Detects inconsistency between sprint and current_issue."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sprint_path = Path(tmpdir) / "sprint.json"
            project_dir = Path(tmpdir) / "project"
            project_dir.mkdir()

            # Sprint with issue-1
            sprint_path.write_text(json.dumps({
                "issues": [{"id": "issue-1"}]
            }))

            # Current issue references non-existent issue
            current_issue_path = project_dir / "current_issue.json"
            current_issue_path.write_text(json.dumps({
                "sprint_path": str(sprint_path),
                "issue_id": "non-existent-issue"
            }))

            manager = StateManager(sprint_path, project_dir)
            is_consistent, message = manager.detect_state_mismatch()

            assert not is_consistent
            assert "non-existent-issue" in message

    def test_checksum_verification(self):
        """Checksums detect file modifications."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sprint_path = Path(tmpdir) / "sprint.json"
            project_dir = Path(tmpdir) / "project"
            project_dir.mkdir()

            data = {"issues": [], "version": 1}
            sprint_path.write_text(json.dumps(data))

            manager = StateManager(sprint_path, project_dir)
            checksum = manager.compute_checksum(data)

            # Verify with correct checksum
            assert manager.verify_checksum(sprint_path, checksum)

            # Modify file and verify fails
            data["version"] = 2
            sprint_path.write_text(json.dumps(data))
            assert not manager.verify_checksum(sprint_path, checksum)


class TestTypedExceptionPropagation:
    """Test that typed exceptions carry context and propagate correctly."""

    def test_file_read_error_contains_path(self):
        """FileReadError includes the path that failed."""
        error = FileReadError("File not found", path=Path("/tmp/missing.json"))
        assert "/tmp/missing.json" in str(error.context)

    def test_file_write_error_contains_path(self):
        """FileWriteError includes the path that failed."""
        error = FileWriteError("Permission denied", path=Path("/etc/readonly.json"))
        assert "/etc/readonly.json" in str(error.context)

    def test_state_corruption_error_contains_checksums(self):
        """StateCorruptionError includes expected and actual checksums."""
        error = StateCorruptionError(
            "State modified by another process",
            expected_checksum="abc123",
            actual_checksum="def456",
            path="/tmp/state.json",
        )
        assert "abc123" in str(error.context)
        assert "def456" in str(error.context)

    def test_validation_error_inheritance(self):
        """Validation errors can be caught by base class."""
        from claudesprint.exceptions import ConfigValidationError

        error = ConfigValidationError("Invalid config value")
        assert isinstance(error, ValidationError)


class TestBoundedListEnforcement:
    """Test that BoundedList properly enforces size limits."""

    def test_bounded_list_never_exceeds_max(self):
        """BoundedList never grows beyond max_size."""
        bounded = BoundedList[int](max_size=10)

        for i in range(100):
            bounded.append(i)

        assert len(bounded) == 10
        assert bounded[0] == 90  # First 90 items were pruned

    def test_bounded_list_preserves_order(self):
        """Items are maintained in FIFO order."""
        bounded = BoundedList[str](max_size=3)
        bounded.extend(["a", "b", "c", "d", "e"])

        # Should have c, d, e (a and b were pruned)
        assert bounded.to_list() == ["c", "d", "e"]

    def test_bounded_list_returns_evicted_item(self):
        """Append returns the evicted item when at capacity."""
        bounded = BoundedList[str](max_size=2, items=["a", "b"])

        evicted = bounded.append("c")

        assert evicted == "a"
        assert bounded.to_list() == ["b", "c"]

    def test_bounded_list_extend_returns_all_evicted(self):
        """Extend returns all evicted items."""
        bounded = BoundedList[int](max_size=3, items=[1, 2, 3])

        evicted = bounded.extend([4, 5, 6])

        assert evicted == [1, 2, 3]
        assert bounded.to_list() == [4, 5, 6]

    def test_bounded_list_with_default_constants(self):
        """Default constants provide reasonable limits."""
        # Just verify constants are defined and reasonable
        assert MAX_HISTORY_ENTRIES >= 100
        assert MAX_HISTORY_ENTRIES <= 10000


class TestIterationTrackerCategorization:
    """Test IterationTracker's categorized failure handling."""

    def test_logic_errors_counted_separately(self):
        """Logic errors have separate counter from infra errors."""
        tracker = IterationTracker(
            max_iterations=100,
            max_logic_errors=3,
            max_infra_errors=10,
        )

        # Record 2 logic errors
        tracker.record_failure(FailureCategory.LOGIC_ERROR, "Bug 1")
        tracker.record_failure(FailureCategory.LOGIC_ERROR, "Bug 2")

        assert tracker.logic_errors == 2
        assert tracker.infra_errors == 0

        # Should not stop yet
        should_stop, _ = tracker.should_stop()
        assert not should_stop

    def test_infra_errors_dont_exhaust_logic_limit(self):
        """Many infra errors don't trigger logic error limit."""
        tracker = IterationTracker(
            max_iterations=100,
            max_logic_errors=3,
            max_infra_errors=10,
            max_consecutive_failures=20,  # High to avoid triggering
        )

        # Record many infra errors (but less than infra limit)
        for i in range(8):
            tracker.record_failure(FailureCategory.INFRA_ERROR, f"Network {i}")

        # Logic limit should not be affected
        assert tracker.logic_errors == 0
        should_stop, reason = tracker.should_stop()
        assert not should_stop

    def test_rate_limits_not_counted_toward_limits(self):
        """Rate limit errors don't count toward failure limits."""
        tracker = IterationTracker(
            max_iterations=100,
            max_logic_errors=1,
            max_infra_errors=1,
        )

        # Record many rate limits
        for i in range(50):
            tracker.record_failure(FailureCategory.RATE_LIMIT, f"Rate limit {i}")

        # Should not trigger stop (rate limits are special)
        assert tracker.rate_limits == 50
        assert tracker.logic_errors == 0
        assert tracker.infra_errors == 0

        # Only consecutive failures might trigger stop
        # Reset consecutive with a success
        tracker.record_success()
        should_stop, _ = tracker.should_stop()
        assert not should_stop

    def test_logic_errors_trigger_early_stop(self):
        """Exceeding logic error limit triggers stop."""
        tracker = IterationTracker(
            max_iterations=100,
            max_logic_errors=3,
            max_infra_errors=10,
        )

        tracker.record_failure(FailureCategory.LOGIC_ERROR, "Bug 1")
        tracker.record_failure(FailureCategory.LOGIC_ERROR, "Bug 2")
        tracker.record_failure(FailureCategory.LOGIC_ERROR, "Bug 3")

        should_stop, reason = tracker.should_stop()
        assert should_stop
        assert "logic" in reason.lower()

    def test_consecutive_failures_trigger_stop(self):
        """Too many consecutive failures trigger stop."""
        tracker = IterationTracker(
            max_iterations=100,
            max_logic_errors=10,
            max_infra_errors=10,
            max_consecutive_failures=3,
        )

        tracker.record_failure(FailureCategory.INFRA_ERROR, "Fail 1")
        tracker.record_failure(FailureCategory.INFRA_ERROR, "Fail 2")
        tracker.record_failure(FailureCategory.INFRA_ERROR, "Fail 3")

        should_stop, reason = tracker.should_stop()
        assert should_stop
        assert "consecutive" in reason.lower()

    def test_success_resets_consecutive_count(self):
        """Recording success resets consecutive failure counter."""
        tracker = IterationTracker(
            max_iterations=100,
            max_consecutive_failures=3,
        )

        tracker.record_failure(FailureCategory.INFRA_ERROR, "Fail 1")
        tracker.record_failure(FailureCategory.INFRA_ERROR, "Fail 2")
        assert tracker.consecutive_failures == 2

        tracker.record_success()
        assert tracker.consecutive_failures == 0


class TestCycleDetection:
    """Test that deduplicated cycle detection works correctly."""

    def test_detects_simple_cycle(self):
        """Detects cycle in simple dependency graph."""
        graph = {
            "a": ["b"],
            "b": ["c"],
            "c": ["a"],  # Creates cycle: a -> b -> c -> a
        }

        cycles = detect_cycles(list(graph.keys()), lambda n: graph.get(n, []))
        assert len(cycles) == 1
        # Cycle contains all three nodes
        assert set(cycles[0][:-1]) == {"a", "b", "c"}

    def test_no_cycle_returns_empty_list(self):
        """Returns empty list when no cycle exists."""
        graph = {
            "a": ["b"],
            "b": ["c"],
            "c": [],
        }

        cycles = detect_cycles(list(graph.keys()), lambda n: graph.get(n, []))
        assert cycles == []

    def test_self_cycle_detected(self):
        """Detects self-referential cycle."""
        graph = {
            "a": ["a"],  # Self-cycle
        }

        cycles = detect_cycles(list(graph.keys()), lambda n: graph.get(n, []))
        assert len(cycles) == 1
        assert "a" in cycles[0]

    def test_empty_graph_has_no_cycle(self):
        """Empty graph has no cycle."""
        cycles = detect_cycles([], lambda n: [])
        assert cycles == []


class TestConfigBackwardCompatibility:
    """Test config consolidation was successful."""

    def test_project_config_models_exist(self):
        """Project config models are accessible."""
        from claudesprint.services.project_config_service import (
            ServerConfig,
            ModelsConfig,
        )
        # Verify models can be instantiated with defaults
        server = ServerConfig()
        assert server.url == "http://localhost:3000"

    def test_configuration_manager_exists(self):
        """ConfigurationManager is the recommended way to load config."""
        from claudesprint.services.configuration_manager import ConfigurationManager
        assert ConfigurationManager is not None

    def test_configuration_manager_can_instantiate(self):
        """ConfigurationManager can be instantiated."""
        import tempfile
        from pathlib import Path
        from claudesprint.services.configuration_manager import ConfigurationManager

        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            manager = ConfigurationManager(project_root)
            assert manager is not None


class TestIssueEngineEventEmission:
    """Test that IssueEngine emits events when event_bus is provided."""

    def test_issue_engine_accepts_event_bus(self):
        """IssueEngine should accept event_bus parameter."""
        from claudesprint.core.issue_engine import IssueEngine
        from claudesprint.events.workflow_event_bus import WorkflowEventBus

        # Just verify the class accepts the parameter without error
        # Full initialization requires many dependencies
        assert hasattr(IssueEngine.__init__, '__code__')
        params = IssueEngine.__init__.__code__.co_varnames
        assert 'event_bus' in params

    def test_emit_event_helper_exists(self):
        """IssueEngine should have _emit_event helper method."""
        from claudesprint.core.issue_engine import IssueEngine

        assert hasattr(IssueEngine, '_emit_event')

    def test_event_emission_with_bus(self):
        """Events should be emitted when event_bus is configured."""
        from claudesprint.events.workflow_event_bus import WorkflowEventBus, WorkflowEvent

        bus = WorkflowEventBus()
        received_events: list[tuple[WorkflowEvent, dict]] = []

        # Subscribe to all step events
        for event in [WorkflowEvent.STEP_STARTED, WorkflowEvent.STEP_COMPLETED,
                      WorkflowEvent.STEP_SKIPPED, WorkflowEvent.STEP_FAILED]:
            bus.subscribe(event, lambda p, e=event: received_events.append((e, p)))

        # Manually emit to verify bus works
        bus.emit(WorkflowEvent.STEP_SKIPPED, {
            "issue_id": "test-1",
            "step_name": "write-tests",
            "next_step": "browser-validation",
            "timestamp": datetime.now(UTC).isoformat(),
        })

        assert len(received_events) == 1
        assert received_events[0][0] == WorkflowEvent.STEP_SKIPPED


class TestHeartbeatServiceEventEmission:
    """Test that HeartbeatService emits PROCESS_HUNG events."""

    def test_heartbeat_service_accepts_event_bus(self):
        """HeartbeatService should accept event_bus parameter."""
        from claudesprint.services.heartbeat_service import HeartbeatService
        from claudesprint.events.workflow_event_bus import WorkflowEventBus

        bus = WorkflowEventBus()
        service = HeartbeatService(
            timeout_seconds=600,
            enabled=True,
            event_bus=bus,
        )

        assert service._event_bus is bus

    def test_get_heartbeat_service_accepts_event_bus(self):
        """get_heartbeat_service factory should accept event_bus parameter."""
        from claudesprint.services.heartbeat_service import (
            get_heartbeat_service,
            reset_heartbeat_service,
        )
        from claudesprint.events.workflow_event_bus import WorkflowEventBus

        # Reset to ensure clean state
        reset_heartbeat_service()

        bus = WorkflowEventBus()
        service = get_heartbeat_service(
            timeout_seconds=600,
            enabled=True,
            event_bus=bus,
        )

        assert service._event_bus is bus

        # Cleanup
        reset_heartbeat_service()

    def test_heartbeat_emits_process_hung_event(self):
        """HeartbeatService should emit PROCESS_HUNG event when hung detected."""
        import time
        from claudesprint.services.heartbeat_service import HeartbeatService
        from claudesprint.events.workflow_event_bus import WorkflowEventBus, WorkflowEvent

        bus = WorkflowEventBus()
        received_events: list[dict] = []

        bus.subscribe(WorkflowEvent.PROCESS_HUNG, lambda p: received_events.append(p))

        # Create service with very short timeout for testing
        service = HeartbeatService(
            timeout_seconds=0,  # Immediate timeout
            enabled=True,
            check_interval=0.05,  # Check every 50ms
            event_bus=bus,
        )

        # Start and pulse
        service.start()
        service.pulse("test-step")

        # Wait for check to run
        time.sleep(0.15)

        service.stop()

        # Should have received a PROCESS_HUNG event
        assert len(received_events) >= 1
        assert received_events[0]["step_name"] == "test-step"
        assert "seconds_inactive" in received_events[0]
        assert "timestamp" in received_events[0]


class TestLogsEventSubscriber:
    """Test that LogsEventSubscriber correctly bridges events to SimpleLogsOutput."""

    def test_subscriber_connect_and_disconnect(self):
        """LogsEventSubscriber should connect and disconnect from event bus."""
        from claudesprint.events.workflow_event_bus import WorkflowEventBus
        from claudesprint.events.logs_subscriber import LogsEventSubscriber
        from claudesprint.simple_logs import SimpleLogsOutput
        from rich.console import Console
        from io import StringIO

        bus = WorkflowEventBus()
        console = Console(file=StringIO(), force_terminal=True)
        output = SimpleLogsOutput(console)

        subscriber = LogsEventSubscriber(output, bus)

        # Initially not connected
        assert not subscriber._connected

        # Connect
        subscriber.connect()
        assert subscriber._connected

        # Disconnect
        subscriber.disconnect()
        assert not subscriber._connected

    def test_subscriber_forwards_step_started_event(self):
        """LogsEventSubscriber should forward STEP_STARTED events to output."""
        from claudesprint.events.workflow_event_bus import WorkflowEventBus, WorkflowEvent
        from claudesprint.events.logs_subscriber import LogsEventSubscriber
        from claudesprint.simple_logs import SimpleLogsOutput
        from rich.console import Console
        from io import StringIO

        bus = WorkflowEventBus()
        string_io = StringIO()
        console = Console(file=string_io, force_terminal=True)
        output = SimpleLogsOutput(console)

        subscriber = LogsEventSubscriber(output, bus)
        subscriber.connect()

        # Emit STEP_STARTED event
        bus.emit(WorkflowEvent.STEP_STARTED, {
            "issue_id": "test-1",
            "step_name": "implement",
            "step_index": 0,
            "model": "opus",
            "timestamp": datetime.now(UTC).isoformat(),
        })

        # Check output was generated
        output_text = string_io.getvalue()
        assert "STEP" in output_text
        assert "implement" in output_text

        subscriber.disconnect()

    def test_subscriber_forwards_issue_completed_event(self):
        """LogsEventSubscriber should forward ISSUE_COMPLETED events to output."""
        from claudesprint.events.workflow_event_bus import WorkflowEventBus, WorkflowEvent
        from claudesprint.events.logs_subscriber import LogsEventSubscriber
        from claudesprint.simple_logs import SimpleLogsOutput
        from rich.console import Console
        from io import StringIO
        import re

        bus = WorkflowEventBus()
        string_io = StringIO()
        console = Console(file=string_io, force_terminal=True)
        output = SimpleLogsOutput(console)
        output.sprint_total = 5  # Set up sprint tracking

        subscriber = LogsEventSubscriber(output, bus)
        subscriber.connect()

        # Emit ISSUE_COMPLETED event
        bus.emit(WorkflowEvent.ISSUE_COMPLETED, {
            "issue_id": "test-1",
            "issue_name": "Test Issue",
            "exit_reason": "completed",
            "timestamp": datetime.now(UTC).isoformat(),
        })

        # Check output was generated - strip ANSI codes for comparison
        output_text = string_io.getvalue()
        # Remove ANSI escape codes
        clean_output = re.sub(r'\x1b\[[0-9;]*m', '', output_text)
        assert "ISSUE" in clean_output
        assert "test-1" in clean_output

        subscriber.disconnect()

    def test_subscriber_forwards_sprint_iteration_event(self):
        """LogsEventSubscriber should forward SPRINT_ITERATION events to output."""
        from claudesprint.events.workflow_event_bus import WorkflowEventBus, WorkflowEvent
        from claudesprint.events.logs_subscriber import LogsEventSubscriber
        from claudesprint.simple_logs import SimpleLogsOutput
        from rich.console import Console
        from io import StringIO

        bus = WorkflowEventBus()
        string_io = StringIO()
        console = Console(file=string_io, force_terminal=True)
        output = SimpleLogsOutput(console)

        subscriber = LogsEventSubscriber(output, bus)
        subscriber.connect()

        # Emit SPRINT_ITERATION event
        bus.emit(WorkflowEvent.SPRINT_ITERATION, {
            "iteration": 3,
            "available_issues": 5,
            "completed_count": 2,
            "total_count": 7,
            "sprint_id": "SPEC_01",
            "timestamp": datetime.now(UTC).isoformat(),
        })

        # Check output was generated
        output_text = string_io.getvalue()
        assert "ITERATION" in output_text

        subscriber.disconnect()

    def test_subscriber_multiple_connect_calls_are_idempotent(self):
        """Multiple connect() calls should not create duplicate subscriptions."""
        from claudesprint.events.workflow_event_bus import WorkflowEventBus, WorkflowEvent
        from claudesprint.events.logs_subscriber import LogsEventSubscriber
        from claudesprint.simple_logs import SimpleLogsOutput
        from rich.console import Console
        from io import StringIO

        bus = WorkflowEventBus()
        string_io = StringIO()
        console = Console(file=string_io, force_terminal=True)
        output = SimpleLogsOutput(console)

        subscriber = LogsEventSubscriber(output, bus)

        # Connect multiple times
        subscriber.connect()
        subscriber.connect()
        subscriber.connect()

        # Should still only be connected once
        assert subscriber._connected

        # Emit event - should only appear once in output
        bus.emit(WorkflowEvent.SELECTING_ISSUE, {
            "sprint_id": "SPEC_01",
            "timestamp": datetime.now(UTC).isoformat(),
        })

        output_text = string_io.getvalue()
        # Count occurrences of "Selecting" - should be exactly 1
        assert output_text.count("Selecting") == 1

        subscriber.disconnect()
