"""Tests for JSON store base class."""

import json
from pathlib import Path

from pydantic import BaseModel

from claudesprint.services.base.json_store import JsonStore


class SampleModel(BaseModel):
    """Simple Pydantic model for testing."""

    name: str
    value: int


class SampleStore(JsonStore[SampleModel]):
    """Concrete implementation for testing."""

    def _serialize(self, data: SampleModel) -> str:
        return data.model_dump_json(indent=2)

    def _deserialize(self, raw: dict) -> SampleModel:
        return SampleModel.model_validate(raw)


class TestJsonStore:
    """Tests for JsonStore base class."""

    def test_read_nonexistent_returns_none(self, tmp_path: Path) -> None:
        """Reading a nonexistent file should return None."""
        store = SampleStore()
        result = store.read(tmp_path / "nonexistent.json")
        assert result is None

    def test_write_then_read_roundtrip(self, tmp_path: Path) -> None:
        """Write then read should return equivalent data."""
        store = SampleStore()
        test_file = tmp_path / "test.json"
        model = SampleModel(name="test", value=42)

        # Write
        success = store.write(test_file, model)
        assert success is True
        assert test_file.exists()

        # Read
        result = store.read(test_file)
        assert result is not None
        assert result.name == "test"
        assert result.value == 42

    def test_atomic_write_creates_file(self, tmp_path: Path) -> None:
        """Atomic write should create the file successfully."""
        store = SampleStore()
        test_file = tmp_path / "atomic.json"
        model = SampleModel(name="atomic", value=123)

        success = store.write(test_file, model)
        assert success is True
        assert test_file.exists()

        # Verify content
        content = json.loads(test_file.read_text())
        assert content["name"] == "atomic"
        assert content["value"] == 123

    def test_write_creates_parent_directories(self, tmp_path: Path) -> None:
        """Write should create parent directories if they don't exist."""
        store = SampleStore()
        test_file = tmp_path / "nested" / "dir" / "test.json"
        model = SampleModel(name="nested", value=1)

        success = store.write(test_file, model)
        assert success is True
        assert test_file.exists()

    def test_read_invalid_json_returns_none(self, tmp_path: Path) -> None:
        """Reading invalid JSON should return None."""
        store = SampleStore()
        test_file = tmp_path / "invalid.json"
        test_file.write_text("not valid json {{{")

        result = store.read(test_file)
        assert result is None

    def test_read_invalid_structure_returns_none(self, tmp_path: Path) -> None:
        """Reading JSON that doesn't match the model should return None."""
        store = SampleStore()
        test_file = tmp_path / "wrong_structure.json"
        test_file.write_text('{"wrong_field": "data"}')

        result = store.read(test_file)
        assert result is None

    def test_write_overwrites_existing(self, tmp_path: Path) -> None:
        """Write should overwrite existing file."""
        store = SampleStore()
        test_file = tmp_path / "overwrite.json"

        # First write
        model1 = SampleModel(name="first", value=1)
        store.write(test_file, model1)

        # Second write
        model2 = SampleModel(name="second", value=2)
        store.write(test_file, model2)

        # Verify second value
        result = store.read(test_file)
        assert result is not None
        assert result.name == "second"
        assert result.value == 2

    def test_temp_file_not_left_behind(self, tmp_path: Path) -> None:
        """After successful write, temp file should not exist."""
        store = SampleStore()
        test_file = tmp_path / "clean.json"
        temp_file = test_file.with_suffix(".tmp.json")
        model = SampleModel(name="clean", value=0)

        store.write(test_file, model)

        assert test_file.exists()
        assert not temp_file.exists()

    def test_concurrent_reads_safe(self, tmp_path: Path) -> None:
        """Multiple reads should not corrupt data."""
        store = SampleStore()
        test_file = tmp_path / "concurrent.json"
        model = SampleModel(name="concurrent", value=99)
        store.write(test_file, model)

        # Multiple reads
        results = [store.read(test_file) for _ in range(10)]

        # All should return same data
        for result in results:
            assert result is not None
            assert result.name == "concurrent"
            assert result.value == 99
