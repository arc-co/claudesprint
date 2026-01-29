"""Tests for the exception hierarchy."""

import pytest

from claudesprint.exceptions import (
    ClaudeSprintError,
    FileOperationError,
    FileReadError,
    FileWriteError,
    FileLockError,
    StateError,
    StateCorruptionError,
    InvalidStateTransition,
    CheckpointError,
    ApiError,
    RateLimitExceeded,
    AuthenticationError,
    ModelError,
    ValidationError,
    ConfigValidationError,
    IssueValidationError,
    SprintValidationError,
)


class TestClaudeSprintError:
    """Tests for the base exception class."""

    def test_basic_message(self):
        """Exception stores message correctly."""
        err = ClaudeSprintError("Something went wrong")
        assert err.message == "Something went wrong"
        assert "Something went wrong" in str(err)

    def test_context_storage(self):
        """Exception stores context correctly."""
        err = ClaudeSprintError("Failed", path="/tmp/file", operation="read")
        assert err.context["path"] == "/tmp/file"
        assert err.context["operation"] == "read"

    def test_context_in_string(self):
        """Context is included in string representation."""
        err = ClaudeSprintError("Failed", path="/tmp/file")
        assert "path=" in str(err)
        assert "/tmp/file" in str(err)

    def test_repr(self):
        """Repr includes class name and context."""
        err = ClaudeSprintError("Failed", key="value")
        repr_str = repr(err)
        assert "ClaudeSprintError" in repr_str
        assert "Failed" in repr_str
        assert "key=" in repr_str

    def test_empty_context(self):
        """Exception works with no context."""
        err = ClaudeSprintError("Simple error")
        assert err.context == {}
        assert str(err) == "Simple error"


class TestFileErrors:
    """Tests for file operation exceptions."""

    def test_file_read_error_basic(self):
        """FileReadError with message only."""
        err = FileReadError("Cannot read file")
        assert isinstance(err, FileOperationError)
        assert isinstance(err, ClaudeSprintError)
        assert "Cannot read file" in str(err)

    def test_file_read_error_with_path(self):
        """FileReadError includes path in context."""
        err = FileReadError("File not found", path="/tmp/missing.json")
        assert err.context["path"] == "/tmp/missing.json"
        assert err.context["operation"] == "read"

    def test_file_write_error_with_path(self):
        """FileWriteError includes path and operation."""
        err = FileWriteError("Permission denied", path="/etc/config.json")
        assert err.context["path"] == "/etc/config.json"
        assert err.context["operation"] == "write"

    def test_file_lock_error_with_pid(self):
        """FileLockError includes holder PID."""
        err = FileLockError("Lock held", path="/tmp/lock", holder_pid=12345)
        assert err.context["holder_pid"] == 12345
        assert err.context["operation"] == "lock"

    def test_hierarchy(self):
        """File errors have correct inheritance."""
        err = FileReadError("test")
        assert isinstance(err, FileOperationError)
        assert isinstance(err, ClaudeSprintError)
        assert isinstance(err, Exception)


class TestStateErrors:
    """Tests for state management exceptions."""

    def test_state_corruption_with_checksums(self):
        """StateCorruptionError includes checksum info."""
        err = StateCorruptionError(
            "Checksum mismatch",
            expected_checksum="abc123",
            actual_checksum="def456",
        )
        assert err.context["expected_checksum"] == "abc123"
        assert err.context["actual_checksum"] == "def456"

    def test_invalid_transition_with_states(self):
        """InvalidStateTransition includes state info."""
        err = InvalidStateTransition(
            "Cannot transition",
            from_state="pending",
            to_state="done",
            allowed_transitions=["in_progress"],
        )
        assert err.context["from_state"] == "pending"
        assert err.context["to_state"] == "done"
        assert err.context["allowed_transitions"] == ["in_progress"]

    def test_checkpoint_error_with_path(self):
        """CheckpointError includes checkpoint info."""
        err = CheckpointError(
            "Failed to save",
            checkpoint_path="/tmp/checkpoint.json",
            checkpoint_id="cp-001",
        )
        assert err.context["checkpoint_path"] == "/tmp/checkpoint.json"
        assert err.context["checkpoint_id"] == "cp-001"

    def test_hierarchy(self):
        """State errors have correct inheritance."""
        assert isinstance(StateCorruptionError("test"), StateError)
        assert isinstance(InvalidStateTransition("test"), StateError)
        assert isinstance(CheckpointError("test"), StateError)
        assert isinstance(StateError("test"), ClaudeSprintError)


class TestApiErrors:
    """Tests for API-related exceptions."""

    def test_rate_limit_with_retry_after(self):
        """RateLimitExceeded includes retry info."""
        err = RateLimitExceeded(
            "Too many requests",
            retry_after=30.0,
            limit_type="requests",
        )
        assert err.context["retry_after"] == 30.0
        assert err.context["limit_type"] == "requests"

    def test_authentication_error_with_api(self):
        """AuthenticationError includes API name."""
        err = AuthenticationError("Invalid key", api_name="claude")
        assert err.context["api_name"] == "claude"

    def test_model_error_with_details(self):
        """ModelError includes model and error code."""
        err = ModelError(
            "Context too long",
            model="claude-3-opus",
            error_code="context_length_exceeded",
        )
        assert err.context["model"] == "claude-3-opus"
        assert err.context["error_code"] == "context_length_exceeded"

    def test_hierarchy(self):
        """API errors have correct inheritance."""
        assert isinstance(RateLimitExceeded("test"), ApiError)
        assert isinstance(AuthenticationError("test"), ApiError)
        assert isinstance(ModelError("test"), ApiError)
        assert isinstance(ApiError("test"), ClaudeSprintError)


class TestValidationErrors:
    """Tests for validation exceptions."""

    def test_validation_error_with_field(self):
        """ValidationError includes field info."""
        err = ValidationError("Invalid value", field="timeout", value=-1)
        assert err.context["field"] == "timeout"
        assert err.context["value"] == "-1"

    def test_validation_error_truncates_long_values(self):
        """ValidationError truncates very long values."""
        long_value = "x" * 200
        err = ValidationError("Too long", field="data", value=long_value)
        assert len(err.context["value"]) <= 103  # 100 + "..."

    def test_config_validation_with_file(self):
        """ConfigValidationError includes config file."""
        err = ConfigValidationError(
            "Missing required field",
            config_file="/tmp/config.json",
            field="api_key",
        )
        assert err.context["config_file"] == "/tmp/config.json"
        assert err.context["field"] == "api_key"

    def test_issue_validation_with_id(self):
        """IssueValidationError includes issue ID."""
        err = IssueValidationError(
            "Invalid status",
            issue_id="feat-001",
            field="status",
            value="invalid",
        )
        assert err.context["issue_id"] == "feat-001"

    def test_sprint_validation_with_path(self):
        """SprintValidationError includes sprint path."""
        err = SprintValidationError(
            "Missing issues",
            sprint_path="/tmp/sprint.json",
            spec_id="SPEC_01",
        )
        assert err.context["sprint_path"] == "/tmp/sprint.json"
        assert err.context["spec_id"] == "SPEC_01"

    def test_hierarchy(self):
        """Validation errors have correct inheritance."""
        assert isinstance(ConfigValidationError("test"), ValidationError)
        assert isinstance(IssueValidationError("test"), ValidationError)
        assert isinstance(SprintValidationError("test"), ValidationError)
        assert isinstance(ValidationError("test"), ClaudeSprintError)


class TestIsinstanceChecks:
    """Tests for isinstance type checking."""

    def test_catch_all_claudesprint_errors(self):
        """All custom exceptions can be caught with ClaudeSprintError."""
        exceptions = [
            FileReadError("test"),
            FileWriteError("test"),
            FileLockError("test"),
            StateCorruptionError("test"),
            InvalidStateTransition("test"),
            CheckpointError("test"),
            RateLimitExceeded("test"),
            AuthenticationError("test"),
            ModelError("test"),
            ConfigValidationError("test"),
            IssueValidationError("test"),
            SprintValidationError("test"),
        ]

        for exc in exceptions:
            assert isinstance(exc, ClaudeSprintError), f"{type(exc)} not ClaudeSprintError"

    def test_catch_file_errors(self):
        """File errors can be caught as a group."""
        file_errors = [
            FileReadError("test"),
            FileWriteError("test"),
            FileLockError("test"),
        ]

        for exc in file_errors:
            assert isinstance(exc, FileOperationError)

    def test_catch_validation_errors(self):
        """Validation errors can be caught as a group."""
        validation_errors = [
            ConfigValidationError("test"),
            IssueValidationError("test"),
            SprintValidationError("test"),
        ]

        for exc in validation_errors:
            assert isinstance(exc, ValidationError)
