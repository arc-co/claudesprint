"""Tests for LockFile class."""

import os
import subprocess
import sys

import pytest

from claudesprint.utils.lock import LockFile


class TestLockFileAcquisition:
    """Tests for lock acquisition."""

    def test_acquire_creates_lock_file(self, tmp_path):
        """Lock acquisition creates the lock file."""
        lock_path = tmp_path / "test.lock"
        lock = LockFile(lock_path)

        success, error = lock.acquire()

        assert success is True
        assert error == ""
        assert lock_path.exists()
        lock.release()

    def test_acquire_writes_pid_to_lock_file(self, tmp_path):
        """Lock acquisition writes current PID to lock file."""
        lock_path = tmp_path / "test.lock"
        lock = LockFile(lock_path)

        lock.acquire()

        # Read the content directly (lock is held, so read via os)
        content = lock_path.read_text().strip()
        assert content == str(os.getpid())
        lock.release()

    def test_acquire_creates_parent_directories(self, tmp_path):
        """Lock acquisition creates parent directories if they don't exist."""
        lock_path = tmp_path / "nested" / "dirs" / "test.lock"
        lock = LockFile(lock_path)

        success, _ = lock.acquire()

        assert success is True
        assert lock_path.parent.exists()
        lock.release()

    def test_acquire_fails_when_already_held(self, tmp_path):
        """Second lock acquisition fails when first lock is held."""
        lock_path = tmp_path / "test.lock"
        lock1 = LockFile(lock_path)
        lock2 = LockFile(lock_path)

        success1, _ = lock1.acquire()
        success2, error2 = lock2.acquire()

        assert success1 is True
        assert success2 is False
        assert "Another instance is running" in error2
        lock1.release()

    def test_is_acquired_property(self, tmp_path):
        """is_acquired property reflects lock state."""
        lock_path = tmp_path / "test.lock"
        lock = LockFile(lock_path)

        assert lock.is_acquired is False
        lock.acquire()
        assert lock.is_acquired is True
        lock.release()
        assert lock.is_acquired is False


class TestLockFileRelease:
    """Tests for lock release."""

    def test_release_removes_lock_file(self, tmp_path):
        """Lock release removes the lock file."""
        lock_path = tmp_path / "test.lock"
        lock = LockFile(lock_path)

        lock.acquire()
        assert lock_path.exists()

        lock.release()
        assert not lock_path.exists()

    def test_release_allows_new_acquisition(self, tmp_path):
        """After release, another process can acquire the lock."""
        lock_path = tmp_path / "test.lock"
        lock1 = LockFile(lock_path)
        lock2 = LockFile(lock_path)

        lock1.acquire()
        lock1.release()

        success, _ = lock2.acquire()
        assert success is True
        lock2.release()

    def test_release_returns_false_when_not_acquired(self, tmp_path):
        """Release returns False when lock was never acquired."""
        lock_path = tmp_path / "test.lock"
        lock = LockFile(lock_path)

        result = lock.release()

        assert result is False


class TestLockFileContextManager:
    """Tests for context manager usage."""

    def test_context_manager_acquires_and_releases(self, tmp_path):
        """Context manager acquires on enter and releases on exit."""
        lock_path = tmp_path / "test.lock"
        lock = LockFile(lock_path)

        with lock:
            assert lock.is_acquired is True
            assert lock_path.exists()

        assert lock.is_acquired is False
        assert not lock_path.exists()

    def test_context_manager_raises_on_failure(self, tmp_path):
        """Context manager raises RuntimeError if acquisition fails."""
        lock_path = tmp_path / "test.lock"
        lock1 = LockFile(lock_path)
        lock2 = LockFile(lock_path)

        with lock1, pytest.raises(RuntimeError, match="Another instance is running"), lock2:
            pass

    def test_context_manager_releases_on_exception(self, tmp_path):
        """Context manager releases lock even when exception occurs."""
        lock_path = tmp_path / "test.lock"
        lock = LockFile(lock_path)

        with pytest.raises(ValueError), lock:
            assert lock.is_acquired is True
            raise ValueError("test error")

        assert lock.is_acquired is False
        assert not lock_path.exists()


class TestLockFileCrossProcess:
    """Tests for cross-process locking behavior."""

    def test_lock_held_by_subprocess(self, tmp_path):
        """Lock held by subprocess prevents acquisition in parent."""
        lock_path = tmp_path / "test.lock"

        # Start subprocess that holds the lock
        subprocess_code = f"""
import time
import sys
sys.path.insert(0, '.')
from claudesprint.utils.lock import LockFile
lock = LockFile('{lock_path}')
success, _ = lock.acquire()
print('acquired' if success else 'failed', flush=True)
time.sleep(5)  # Hold lock for 5 seconds
"""
        proc = subprocess.Popen(
            [sys.executable, "-c", subprocess_code],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        try:
            # Wait for subprocess to acquire lock
            output = proc.stdout.readline().strip()
            assert output == "acquired"

            # Try to acquire in parent - should fail
            lock = LockFile(lock_path)
            success, error = lock.acquire()
            assert success is False
            assert "Another instance is running" in error
        finally:
            proc.terminate()
            proc.wait()

    def test_stale_lock_detection(self, tmp_path):
        """Lock from dead process can be identified by PID."""
        lock_path = tmp_path / "test.lock"

        # Create a fake lock file with a non-existent PID
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text("99999999")  # Unlikely to be a real PID

        # Try to acquire - the implementation uses flock which works
        # regardless of PID file content, so this tests reading the PID
        lock = LockFile(lock_path)
        success, _ = lock.acquire()

        # Should succeed because the file isn't actually locked
        assert success is True
        lock.release()
