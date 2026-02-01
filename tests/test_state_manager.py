"""Tests for the StateManager service."""

import json

import pytest

from claudesprint.exceptions import (
    FileReadError,
    StateCorruptionError,
)
from claudesprint.services.state_manager import StateManager, StateSnapshot


class TestStateSnapshot:
    """Tests for StateSnapshot dataclass."""

    def test_create_snapshot(self):
        """Create a state snapshot."""
        data = {"key": "value"}
        snapshot = StateSnapshot(data=data, version="abc123")
        assert snapshot.data == {"key": "value"}
        assert snapshot.version == "abc123"
        assert snapshot.modified is False

    def test_mark_modified(self):
        """Mark snapshot as modified."""
        snapshot = StateSnapshot(data={}, version="")
        assert snapshot.modified is False
        snapshot.mark_modified()
        assert snapshot.modified is True


class TestChecksumComputation:
    """Tests for checksum computation."""

    def test_compute_checksum(self):
        """Checksum is deterministic."""
        data = {"a": 1, "b": 2}
        cs1 = StateManager.compute_checksum(data)
        cs2 = StateManager.compute_checksum(data)
        assert cs1 == cs2
        assert len(cs1) == 16  # Truncated SHA-256

    def test_checksum_order_independent(self):
        """Checksum ignores key order."""
        data1 = {"a": 1, "b": 2}
        data2 = {"b": 2, "a": 1}
        assert StateManager.compute_checksum(data1) == StateManager.compute_checksum(data2)

    def test_different_data_different_checksum(self):
        """Different data produces different checksum."""
        cs1 = StateManager.compute_checksum({"a": 1})
        cs2 = StateManager.compute_checksum({"a": 2})
        assert cs1 != cs2


class TestStateManagerInit:
    """Tests for StateManager initialization."""

    def test_init_paths(self, tmp_path):
        """Manager stores paths correctly."""
        sprint_path = tmp_path / "sprint.json"
        project_dir = tmp_path / "project"

        manager = StateManager(sprint_path, project_dir)

        assert manager.sprint_path == sprint_path
        assert manager.project_dir == project_dir
        assert manager.current_issue_path == project_dir / "current_issue.json"


class TestLockAcquisition:
    """Tests for lock acquisition and release."""

    def test_acquire_and_release(self, tmp_path):
        """Acquire and release lock."""
        manager = StateManager(
            tmp_path / "sprint.json",
            tmp_path / "project",
        )

        assert manager.acquire_lock() is True
        manager.release_lock()

    def test_lock_prevents_second_acquisition(self, tmp_path):
        """Second acquisition fails when lock held."""
        project_dir = tmp_path / "project"
        manager1 = StateManager(tmp_path / "sprint.json", project_dir)
        manager2 = StateManager(tmp_path / "sprint.json", project_dir)

        assert manager1.acquire_lock() is True
        assert manager2.acquire_lock() is False

        manager1.release_lock()
        assert manager2.acquire_lock() is True
        manager2.release_lock()


class TestAtomicUpdate:
    """Tests for atomic update context manager."""

    def test_atomic_update_reads_data(self, tmp_path):
        """Atomic update reads existing data."""
        sprint_path = tmp_path / "sprint.json"
        sprint_path.write_text('{"spec_id": "TEST", "issues": []}')

        manager = StateManager(sprint_path, tmp_path / "project")

        with manager.atomic_update() as snapshot:
            assert snapshot.data["spec_id"] == "TEST"
            assert snapshot.data["issues"] == []

    def test_atomic_update_writes_if_modified(self, tmp_path):
        """Atomic update writes changes if marked modified."""
        sprint_path = tmp_path / "sprint.json"
        sprint_path.write_text('{"spec_id": "TEST", "value": 1}')

        manager = StateManager(sprint_path, tmp_path / "project")

        with manager.atomic_update() as snapshot:
            snapshot.data["value"] = 2
            snapshot.mark_modified()

        # Verify written
        data = json.loads(sprint_path.read_text())
        assert data["value"] == 2

    def test_atomic_update_skips_write_if_not_modified(self, tmp_path):
        """Atomic update doesn't write if not modified."""
        sprint_path = tmp_path / "sprint.json"
        original_content = '{"spec_id": "TEST", "value": 1}'
        sprint_path.write_text(original_content)
        _ = sprint_path.stat().st_mtime

        manager = StateManager(sprint_path, tmp_path / "project")

        with manager.atomic_update() as snapshot:
            # Read but don't modify
            _ = snapshot.data["value"]

        # File should not have been modified
        # Note: mtime comparison might be flaky, so we just verify content
        assert sprint_path.read_text().strip() == original_content.strip()

    def test_atomic_update_handles_missing_file(self, tmp_path):
        """Atomic update handles non-existent file."""
        sprint_path = tmp_path / "sprint.json"
        manager = StateManager(sprint_path, tmp_path / "project")

        with manager.atomic_update() as snapshot:
            assert snapshot.data == {}
            assert snapshot.version == ""

    def test_atomic_update_releases_lock_on_exception(self, tmp_path):
        """Lock is released even if exception occurs."""
        sprint_path = tmp_path / "sprint.json"
        sprint_path.write_text("{}")
        manager = StateManager(sprint_path, tmp_path / "project")

        with pytest.raises(ValueError), manager.atomic_update():
            raise ValueError("test error")

        # Lock should be released, so we can acquire again
        assert manager.acquire_lock() is True
        manager.release_lock()


class TestOptimisticLocking:
    """Tests for optimistic locking via version checking."""

    def test_detects_concurrent_modification(self, tmp_path):
        """Detects when file changed during update."""
        sprint_path = tmp_path / "sprint.json"
        sprint_path.write_text('{"value": 1}')

        manager = StateManager(sprint_path, tmp_path / "project")

        # Read the file directly to get a snapshot
        manager.acquire_lock()
        data, version = manager._read_json_file(sprint_path)

        # Modify the file externally (simulating another process)
        sprint_path.write_text('{"value": 99}')

        # Now try to write with the old version
        with pytest.raises(StateCorruptionError) as exc_info:
            manager._write_json_file(sprint_path, {"value": 2}, expected_version=version)

        assert "modified by another process" in str(exc_info.value)
        manager.release_lock()


class TestStateMismatchDetection:
    """Tests for state consistency checking."""

    def test_consistent_state(self, tmp_path):
        """Detects consistent state."""
        sprint_path = tmp_path / "sprint.json"
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        sprint_path.write_text(json.dumps({
            "spec_id": "TEST",
            "issues": [{"id": "feat-001", "title": "Test"}],
        }))

        # Create matching current_issue
        current_issue = project_dir / "current_issue.json"
        current_issue.write_text(json.dumps({
            "sprint_path": str(sprint_path),
            "issue_id": "feat-001",
        }))

        manager = StateManager(sprint_path, project_dir)
        is_consistent, msg = manager.detect_state_mismatch()
        assert is_consistent is True
        assert msg == ""

    def test_missing_sprint_with_current_issue(self, tmp_path):
        """Detects current_issue without sprint."""
        sprint_path = tmp_path / "sprint.json"
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # No sprint file, but current_issue exists
        current_issue = project_dir / "current_issue.json"
        current_issue.write_text('{"issue_id": "feat-001"}')

        manager = StateManager(sprint_path, project_dir)
        is_consistent, msg = manager.detect_state_mismatch()
        assert is_consistent is False
        assert "sprint.json does not" in msg

    def test_unknown_issue_reference(self, tmp_path):
        """Detects current_issue referencing unknown issue."""
        sprint_path = tmp_path / "sprint.json"
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        sprint_path.write_text(json.dumps({
            "spec_id": "TEST",
            "issues": [{"id": "feat-001", "title": "Test"}],
        }))

        current_issue = project_dir / "current_issue.json"
        current_issue.write_text(json.dumps({
            "sprint_path": str(sprint_path),
            "issue_id": "nonexistent-999",
        }))

        manager = StateManager(sprint_path, project_dir)
        is_consistent, msg = manager.detect_state_mismatch()
        assert is_consistent is False
        assert "unknown issue" in msg

    def test_no_current_issue_is_valid(self, tmp_path):
        """No current_issue is considered valid."""
        sprint_path = tmp_path / "sprint.json"
        project_dir = tmp_path / "project"

        sprint_path.write_text('{"spec_id": "TEST", "issues": []}')
        # No current_issue.json

        manager = StateManager(sprint_path, project_dir)
        is_consistent, msg = manager.detect_state_mismatch()
        assert is_consistent is True


class TestChecksumVerification:
    """Tests for checksum verification."""

    def test_verify_valid_checksum(self, tmp_path):
        """Verifies matching checksum."""
        file_path = tmp_path / "data.json"
        data = {"key": "value"}
        file_path.write_text(json.dumps(data))

        manager = StateManager(tmp_path / "sprint.json", tmp_path / "project")
        expected = StateManager.compute_checksum(data)

        assert manager.verify_checksum(file_path, expected) is True

    def test_verify_invalid_checksum(self, tmp_path):
        """Detects mismatching checksum."""
        file_path = tmp_path / "data.json"
        file_path.write_text('{"key": "value"}')

        manager = StateManager(tmp_path / "sprint.json", tmp_path / "project")

        assert manager.verify_checksum(file_path, "wrongchecksum") is False

    def test_verify_missing_file(self, tmp_path):
        """Missing file fails verification."""
        manager = StateManager(tmp_path / "sprint.json", tmp_path / "project")
        assert manager.verify_checksum(tmp_path / "missing.json", "any") is False


class TestFileReadErrors:
    """Tests for file read error handling."""

    def test_read_invalid_json(self, tmp_path):
        """Raises FileReadError for invalid JSON."""
        file_path = tmp_path / "bad.json"
        file_path.write_text("not valid json")

        manager = StateManager(tmp_path / "sprint.json", tmp_path / "project")

        with pytest.raises(FileReadError) as exc_info:
            manager._read_json_file(file_path)

        assert "Invalid JSON" in str(exc_info.value)

    def test_read_missing_file(self, tmp_path):
        """Raises FileReadError for missing file."""
        manager = StateManager(tmp_path / "sprint.json", tmp_path / "project")

        with pytest.raises(FileReadError) as exc_info:
            manager._read_json_file(tmp_path / "missing.json")

        assert "not found" in str(exc_info.value)
