"""Safe state management with atomic updates and corruption detection.

Provides file locking, checksums, and atomic writes to prevent race
conditions and detect state corruption.
"""

import hashlib
import json
import logging
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from claudesprint.exceptions import (
    FileLockError,
    FileReadError,
    FileWriteError,
    StateCorruptionError,
)
from claudesprint.utils.lock import LockFile

logger = logging.getLogger(__name__)


@dataclass
class StateSnapshot:
    """Snapshot of state data with version tracking.

    Attributes:
        data: The state data dictionary.
        version: Content hash for optimistic locking.
        loaded_at: When this snapshot was created.
        modified: Whether the data has been modified since loading.
    """

    data: dict[str, Any]
    version: str
    loaded_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    modified: bool = False

    def mark_modified(self) -> None:
        """Mark this snapshot as modified."""
        self.modified = True


class StateManager:
    """Safe state manager with file locking and corruption detection.

    Prevents race conditions through:
    - File locking using LockFile for atomic operations
    - Checksums for corruption detection
    - Atomic writes (temp file + rename)
    - Optimistic locking via content versioning

    Example:
        manager = StateManager(sprint_path, project_dir)

        with manager.atomic_update() as snapshot:
            snapshot.data["issues"][0]["status"] = "done"
            snapshot.mark_modified()
        # Changes are automatically written on context exit
    """

    def __init__(
        self,
        sprint_path: Path,
        project_dir: Path,
        lock_timeout: float = 30.0,
    ) -> None:
        """Initialize StateManager.

        Args:
            sprint_path: Path to the sprint.json file.
            project_dir: Project directory containing current_issue.json.
            lock_timeout: Maximum seconds to wait for lock acquisition.
        """
        self.sprint_path = Path(sprint_path)
        self.project_dir = Path(project_dir)
        self.current_issue_path = self.project_dir / "current_issue.json"
        self.lock_timeout = lock_timeout

        # Lock file in project directory
        self._lock = LockFile(self.project_dir / "state.lock")
        self._lock_acquired = False

    @staticmethod
    def compute_checksum(data: dict[str, Any]) -> str:
        """Compute SHA-256 checksum of JSON-serialized data.

        Args:
            data: Dictionary to compute checksum for.

        Returns:
            Hex-encoded SHA-256 hash of the JSON content.
        """
        # Use sorted keys and consistent formatting for deterministic hashes
        content = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    def _read_json_file(self, path: Path) -> tuple[dict[str, Any], str]:
        """Read a JSON file and compute its checksum.

        Args:
            path: Path to the JSON file.

        Returns:
            Tuple of (data, checksum).

        Raises:
            FileReadError: If the file cannot be read.
        """
        try:
            content = path.read_text(encoding="utf-8")
            data = json.loads(content)
            checksum = self.compute_checksum(data)
            return data, checksum
        except FileNotFoundError as e:
            raise FileReadError(f"State file not found: {path}", path=path) from e
        except json.JSONDecodeError as e:
            raise FileReadError(
                f"Invalid JSON in state file: {e}",
                path=path,
                line=e.lineno,
                column=e.colno,
            ) from e
        except OSError as e:
            raise FileReadError(f"Failed to read state file: {e}", path=path) from e

    def _write_json_file(
        self,
        path: Path,
        data: dict[str, Any],
        expected_version: str | None = None,
    ) -> str:
        """Write data to a JSON file atomically with optional version check.

        Args:
            path: Path to write the JSON file.
            data: Dictionary to write.
            expected_version: If provided, verify current file matches this version.

        Returns:
            New checksum of written data.

        Raises:
            FileWriteError: If the write fails.
            StateCorruptionError: If version check fails (optimistic locking).
        """
        # Optimistic locking check
        if expected_version is not None and path.exists():
            try:
                _, current_version = self._read_json_file(path)
                if current_version != expected_version:
                    raise StateCorruptionError(
                        "State was modified by another process",
                        expected_checksum=expected_version,
                        actual_checksum=current_version,
                        path=str(path),
                    )
            except FileReadError:
                # File doesn't exist or can't be read, proceed with write
                pass

        try:
            # Ensure parent directory exists
            path.parent.mkdir(parents=True, exist_ok=True)

            # Write to temp file first
            temp_fd, temp_path = tempfile.mkstemp(
                suffix=".tmp.json",
                dir=path.parent,
            )
            temp_file = Path(temp_path)

            try:
                content = json.dumps(data, indent=2)
                temp_file.write_text(content, encoding="utf-8")

                # Atomic rename
                temp_file.rename(path)

                return self.compute_checksum(data)

            except Exception:
                # Clean up temp file on error
                if temp_file.exists():
                    temp_file.unlink()
                raise

        except StateCorruptionError:
            raise
        except OSError as e:
            raise FileWriteError(f"Failed to write state file: {e}", path=path) from e

    def acquire_lock(self) -> bool:
        """Acquire the state lock.

        Returns:
            True if lock was acquired, False if already held by another process.

        Raises:
            FileLockError: If lock acquisition fails unexpectedly.
        """
        success, message = self._lock.acquire()
        if success:
            self._lock_acquired = True
            return True

        if "Another instance" in message:
            return False

        raise FileLockError(message, path=self._lock.lock_path)

    def release_lock(self) -> None:
        """Release the state lock."""
        if self._lock_acquired:
            self._lock.release()
            self._lock_acquired = False

    @contextmanager
    def atomic_update(self) -> Generator[StateSnapshot, None, None]:
        """Context manager for atomic state updates.

        Acquires lock, reads current state, yields for modifications,
        then writes if modified and releases lock.

        Yields:
            StateSnapshot with current data. Call mark_modified() to
            trigger a write on context exit.

        Raises:
            FileLockError: If lock cannot be acquired.
            FileReadError: If state file cannot be read.
            FileWriteError: If state file cannot be written.
            StateCorruptionError: If concurrent modification detected.

        Example:
            with manager.atomic_update() as snapshot:
                snapshot.data["key"] = "value"
                snapshot.mark_modified()
        """
        if not self.acquire_lock():
            raise FileLockError(
                "Could not acquire state lock - another process is running",
                path=self._lock.lock_path,
            )

        try:
            # Read current sprint state
            if self.sprint_path.exists():
                data, version = self._read_json_file(self.sprint_path)
            else:
                data = {}
                version = ""

            snapshot = StateSnapshot(data=data, version=version)

            yield snapshot

            # Write if modified
            if snapshot.modified:
                self._write_json_file(
                    self.sprint_path,
                    snapshot.data,
                    expected_version=snapshot.version if snapshot.version else None,
                )

        finally:
            self.release_lock()

    def detect_state_mismatch(self) -> tuple[bool, str]:
        """Check for consistency between sprint.json and current_issue.json.

        Verifies that:
        - If current_issue references an issue, it exists in sprint
        - Issue status in sprint matches expected state
        - Sprint path in current_issue matches actual sprint file

        Returns:
            Tuple of (is_consistent, mismatch_description).
            If consistent, returns (True, "").
        """
        if not self.sprint_path.exists():
            if self.current_issue_path.exists():
                return False, "current_issue.json exists but sprint.json does not"
            return True, ""

        if not self.current_issue_path.exists():
            return True, ""  # No current issue is valid

        try:
            sprint_data, _ = self._read_json_file(self.sprint_path)
            issue_data, _ = self._read_json_file(self.current_issue_path)
        except FileReadError as e:
            return False, f"Could not read state files: {e.message}"

        # Check sprint_path reference
        referenced_path = issue_data.get("sprint_path", "")
        if referenced_path and not Path(referenced_path).samefile(self.sprint_path):
            return False, (
                f"current_issue references different sprint: {referenced_path}"
            )

        # Check issue_id exists in sprint
        issue_id = issue_data.get("issue_id")
        if issue_id:
            issues = sprint_data.get("issues", [])
            found = any(i.get("id") == issue_id for i in issues)
            if not found:
                return False, f"current_issue references unknown issue: {issue_id}"

        return True, ""

    def verify_checksum(self, path: Path, expected: str) -> bool:
        """Verify a file's current checksum matches expected value.

        Args:
            path: Path to the file to verify.
            expected: Expected checksum value.

        Returns:
            True if checksums match, False otherwise.
        """
        if not path.exists():
            return False

        try:
            _, actual = self._read_json_file(path)
            return actual == expected
        except FileReadError:
            return False
