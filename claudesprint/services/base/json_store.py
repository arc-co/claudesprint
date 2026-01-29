"""Generic JSON file storage with atomic writes."""

import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Generic, TypeVar

T = TypeVar("T")

logger = logging.getLogger(__name__)


class JsonStore(ABC, Generic[T]):
    """Generic JSON file storage with atomic writes.

    Subclasses must implement _serialize and _deserialize to convert between
    the typed data object and JSON strings/dicts.

    Example:
        class SprintStore(JsonStore[Sprint]):
            def _serialize(self, data: Sprint) -> str:
                return data.model_dump_json(indent=2, by_alias=True)

            def _deserialize(self, raw: dict) -> Sprint:
                return Sprint.model_validate(raw)
    """

    def read(self, path: Path) -> T | None:
        """Read and deserialize JSON file.

        Args:
            path: Path to the JSON file

        Returns:
            Deserialized data object, or None if file doesn't exist or is invalid
        """
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text())
            return self._deserialize(raw)
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in {path}: {e}")
            return None
        except Exception as e:
            logger.warning(f"Failed to deserialize {path}: {e}")
            return None

    def write(self, path: Path, data: T) -> bool:
        """Write data atomically using temp file + rename.

        Args:
            path: Path to the JSON file
            data: Data object to serialize and write

        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure parent directory exists
            path.parent.mkdir(parents=True, exist_ok=True)

            # Write to temp file first
            temp_file = path.with_suffix(".tmp.json")
            content = self._serialize(data)
            temp_file.write_text(content)

            # Atomic rename
            temp_file.rename(path)
            return True
        except Exception as e:
            logger.warning(f"Failed to write {path}: {e}")
            return False

    @abstractmethod
    def _serialize(self, data: T) -> str:
        """Convert data to JSON string.

        Args:
            data: Typed data object

        Returns:
            JSON string representation
        """
        ...

    @abstractmethod
    def _deserialize(self, raw: dict) -> T:
        """Convert raw dict to typed object.

        Args:
            raw: Dictionary parsed from JSON

        Returns:
            Typed data object
        """
        ...
