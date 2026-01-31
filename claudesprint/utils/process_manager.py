"""Process manager for tracking and cleaning up spawned subprocesses."""

import atexit
import logging
import os
import signal
import subprocess
import weakref
from threading import Lock
from typing import Set

logger = logging.getLogger(__name__)


class ProcessManager:
    """Singleton manager for tracking spawned subprocesses.

    Ensures all Claude processes are properly cleaned up on:
    - Normal exit
    - Signal interruption (Ctrl+C, SIGTERM, etc.)
    - atexit handler (last resort)
    """

    _instance: "ProcessManager | None" = None
    _lock = Lock()

    def __new__(cls) -> "ProcessManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True

        # Track process IDs (PIDs) of spawned processes
        # Using PIDs instead of Popen objects to avoid keeping references
        self._pids: Set[int] = set()
        self._process_groups: Set[int] = set()
        self._pid_lock = Lock()

        # Track if cleanup has been run
        self._cleaned_up = False

        # Store original signal handlers
        self._original_handlers: dict[int, signal.Handlers] = {}

        # Install handlers
        self._install_handlers()

    def _install_handlers(self) -> None:
        """Install signal handlers and atexit hook."""
        # Install atexit handler (last resort)
        atexit.register(self.cleanup_all)

        # Install signal handlers
        signals_to_handle = [signal.SIGINT, signal.SIGTERM]

        # SIGHUP only exists on Unix-like systems
        if hasattr(signal, 'SIGHUP'):
            signals_to_handle.append(signal.SIGHUP)

        for sig in signals_to_handle:
            try:
                self._original_handlers[sig] = signal.signal(sig, self._signal_handler)
            except (OSError, ValueError) as e:
                logger.debug("Could not install signal handler for %s: %s", sig, e)

    def _signal_handler(self, signum: int, frame) -> None:
        """Handle signals by saving state, cleaning up, and re-raising."""
        # Get signal name for state manager
        signal_name = signal.Signals(signum).name if signum in signal.Signals._value2member_map_ else f"signal-{signum}"

        # Save workflow state before cleanup
        try:
            from claudesprint.core.state_manager import get_state_manager
            state_manager = get_state_manager()
            state_manager.save_emergency_state(signal_name)
        except Exception as e:
            logger.debug("Failed to save emergency state during signal handling: %s", e)

        self.cleanup_all()

        # Restore original handler and re-raise
        if signum in self._original_handlers:
            signal.signal(signum, self._original_handlers[signum])
        else:
            signal.signal(signum, signal.SIG_DFL)

        os.kill(os.getpid(), signum)

    def register_process(self, process: subprocess.Popen) -> None:
        """Register a process for cleanup tracking.

        Args:
            process: The subprocess.Popen object to track.
        """
        if process.pid is None:
            return
        self.register_pid(process.pid)

    def register_pid(self, pid: int) -> None:
        """Register a PID for cleanup tracking.

        Args:
            pid: The process ID to track.
        """
        with self._pid_lock:
            self._pids.add(pid)

            # Track process group if it's different from our own
            try:
                pgid = os.getpgid(pid)
                if pgid != os.getpgid(os.getpid()):
                    self._process_groups.add(pgid)
            except (OSError, ProcessLookupError) as e:
                logger.debug("Could not get process group for PID %d during registration: %s", pid, e)

    def unregister_process(self, process: subprocess.Popen) -> None:
        """Unregister a process that has been cleaned up.

        Args:
            process: The subprocess.Popen object to remove.
        """
        if process.pid is None:
            return
        self.unregister_pid(process.pid)

    def unregister_pid(self, pid: int) -> None:
        """Unregister a PID that has been cleaned up.

        Args:
            pid: The process ID to remove.
        """
        with self._pid_lock:
            self._pids.discard(pid)

            # Also try to remove process group
            try:
                pgid = os.getpgid(pid)
                self._process_groups.discard(pgid)
            except (OSError, ProcessLookupError) as e:
                logger.debug("Could not get process group for PID %d during unregistration: %s", pid, e)

    def cleanup_all(self, grace_period: float = 5.0) -> None:
        """Kill all tracked processes.

        Args:
            grace_period: Seconds to wait for graceful termination before SIGKILL.
        """
        if self._cleaned_up:
            return
        self._cleaned_up = True

        with self._pid_lock:
            pids = list(self._pids)
            pgids = list(self._process_groups)

        # First, try graceful termination of process groups
        for pgid in pgids:
            try:
                os.killpg(pgid, signal.SIGTERM)
            except (OSError, ProcessLookupError) as e:
                logger.debug("Could not send SIGTERM to process group %d: %s", pgid, e)

        # Also terminate individual processes (in case they're not in groups)
        for pid in pids:
            try:
                os.kill(pid, signal.SIGTERM)
            except (OSError, ProcessLookupError) as e:
                logger.debug("Could not send SIGTERM to PID %d: %s", pid, e)

        # Wait a bit for graceful termination
        import time
        time.sleep(min(grace_period, 2.0))

        # Force kill anything still running
        for pgid in pgids:
            try:
                os.killpg(pgid, signal.SIGKILL)
            except (OSError, ProcessLookupError) as e:
                logger.debug("Could not send SIGKILL to process group %d: %s", pgid, e)

        for pid in pids:
            try:
                os.kill(pid, signal.SIGKILL)
            except (OSError, ProcessLookupError) as e:
                logger.debug("Could not send SIGKILL to PID %d: %s", pid, e)

        # Clean up zombie processes
        for pid in pids:
            try:
                os.waitpid(pid, os.WNOHANG)
            except (OSError, ChildProcessError) as e:
                logger.debug("Could not reap zombie process %d: %s", pid, e)

        # Clear tracking sets
        with self._pid_lock:
            self._pids.clear()
            self._process_groups.clear()

    def reset(self) -> None:
        """Reset the cleanup state (for testing)."""
        self._cleaned_up = False

    @property
    def active_processes(self) -> int:
        """Return count of tracked processes."""
        with self._pid_lock:
            return len(self._pids)


# Global instance - initialized on first import
_manager: ProcessManager | None = None


def get_process_manager() -> ProcessManager:
    """Get the global process manager instance."""
    global _manager
    if _manager is None:
        _manager = ProcessManager()
    return _manager


def cleanup_all_processes() -> None:
    """Convenience function to cleanup all tracked processes."""
    get_process_manager().cleanup_all()
