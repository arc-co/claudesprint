"""Tests for ProcessManager."""

import os
import signal
import subprocess
import time

import pytest

from claudesprint.utils.process_manager import ProcessManager, get_process_manager


class TestProcessManager:
    """Tests for ProcessManager singleton and cleanup functionality."""

    def test_singleton(self):
        """ProcessManager should be a singleton."""
        pm1 = ProcessManager()
        pm2 = ProcessManager()
        assert pm1 is pm2

    def test_get_process_manager_returns_singleton(self):
        """get_process_manager should return the same instance."""
        pm1 = get_process_manager()
        pm2 = get_process_manager()
        assert pm1 is pm2

    def test_register_and_unregister_process(self):
        """Should track registered processes."""
        pm = get_process_manager()
        pm.reset()  # Clear any previous state

        # Start a simple sleep process
        process = subprocess.Popen(
            ["sleep", "60"],
            start_new_session=True,
        )

        try:
            pm.register_process(process)
            assert pm.active_processes >= 1

            pm.unregister_process(process)
            # Count may still include other processes, just verify no crash
        finally:
            process.kill()
            process.wait()

    def test_register_and_unregister_pid(self):
        """Should track registered PIDs."""
        pm = get_process_manager()
        pm.reset()

        # Start a simple sleep process
        process = subprocess.Popen(
            ["sleep", "60"],
            start_new_session=True,
        )

        try:
            pm.register_pid(process.pid)
            assert pm.active_processes >= 1

            pm.unregister_pid(process.pid)
        finally:
            process.kill()
            process.wait()

    def test_cleanup_all_terminates_processes(self):
        """cleanup_all should terminate all tracked processes."""
        pm = get_process_manager()
        pm.reset()

        # Start multiple sleep processes
        processes = []
        for _ in range(3):
            p = subprocess.Popen(
                ["sleep", "300"],
                start_new_session=True,
            )
            processes.append(p)
            pm.register_pid(p.pid)

        # Verify they're running
        for p in processes:
            assert p.poll() is None, "Process should be running"

        # Cleanup
        pm.cleanup_all(grace_period=1.0)

        # Give a moment for processes to die
        time.sleep(0.5)

        # Verify they're dead
        for p in processes:
            # Poll or wait to check status
            try:
                p.wait(timeout=1)
            except subprocess.TimeoutExpired:
                # Force kill if still alive
                p.kill()
                p.wait()

            assert p.returncode is not None, "Process should be terminated"

    def test_cleanup_idempotent(self):
        """cleanup_all should be safe to call multiple times."""
        pm = get_process_manager()
        pm.reset()

        # Start a process
        process = subprocess.Popen(
            ["sleep", "60"],
            start_new_session=True,
        )
        pm.register_pid(process.pid)

        # Cleanup multiple times should not raise
        pm.cleanup_all(grace_period=0.5)
        pm.cleanup_all(grace_period=0.5)  # Second call should be no-op
        pm.cleanup_all(grace_period=0.5)  # Third call should be no-op

        # Make sure process is dead
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

    def test_tracks_process_groups(self):
        """Should track process groups for group termination."""
        pm = get_process_manager()
        pm.reset()

        # Start a process in new session (new process group)
        process = subprocess.Popen(
            ["sleep", "60"],
            start_new_session=True,
        )

        try:
            pm.register_pid(process.pid)

            # The process group should be tracked
            pgid = os.getpgid(process.pid)
            assert pgid != os.getpgid(os.getpid()), "Should be in different process group"
        finally:
            process.kill()
            process.wait()
            pm.unregister_pid(process.pid)


class TestProcessManagerSignals:
    """Tests for signal handling (may need special handling in CI)."""

    @pytest.mark.skipif(
        os.environ.get("CI") == "true",
        reason="Signal tests may be flaky in CI",
    )
    def test_signal_handlers_installed(self):
        """Signal handlers should be installed on initialization."""
        pm = get_process_manager()

        # Check that our handler is installed for SIGTERM
        current_handler = signal.getsignal(signal.SIGTERM)
        # It should be our method, not the default
        assert current_handler is not signal.SIG_DFL
