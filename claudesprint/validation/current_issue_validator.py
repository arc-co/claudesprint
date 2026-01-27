"""CurrentIssue validation logic."""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from claudesprint.models.current_issue import CurrentIssue, ChunkType, IssueStep


@dataclass
class ValidationResult:
    """Result of a validation check."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.valid


class CurrentIssueValidator:
    """Validates current_issue.json files."""

    REQUIRED_FIELDS = [
        "schema_version",
        "session_id",
        "timestamp",
        "sprint_path",
        "issue_id",
        "chunk_type",
        "step",
        "goal",
        "next_action",
        "repo_state",
        "changes",
        "commands_run",
        "current_failures",
        "retry_count",
        "rationale",
    ]

    def __init__(self, current_issue_path: str | Path) -> None:
        self.current_issue_path = Path(current_issue_path)

    def validate(self) -> ValidationResult:
        """Run all validation checks."""
        errors: list[str] = []
        warnings: list[str] = []

        # Check file exists
        if not self.current_issue_path.exists():
            return ValidationResult(
                valid=False, errors=[f"File not found: {self.current_issue_path}"]
            )

        # Try to parse JSON
        try:
            data = json.loads(self.current_issue_path.read_text())
        except json.JSONDecodeError as e:
            return ValidationResult(valid=False, errors=[f"Invalid JSON: {e}"])

        # Check required fields
        for field_name in self.REQUIRED_FIELDS:
            if field_name not in data:
                errors.append(f"MISSING: {field_name}")

        if errors:
            return ValidationResult(valid=False, errors=errors)

        # Validate schema_version
        schema_version = data.get("schema_version", "")
        if not schema_version.startswith("2."):
            warnings.append(f"Expected schema_version 2.x, got: {schema_version}")

        # Validate sprint_path
        sprint_path = data.get("sprint_path", "")
        if not sprint_path:
            errors.append("sprint_path must not be empty")
        else:
            # Check if sprint file exists
            sprint_file = Path(sprint_path)
            if not sprint_file.exists():
                warnings.append(f"sprint_path references non-existent file: {sprint_path}")

        # Validate chunk_type
        chunk_type = data.get("chunk_type", "")
        valid_chunk_types = [c.value for c in ChunkType]
        if chunk_type not in valid_chunk_types:
            errors.append(
                f"Invalid chunk_type: {chunk_type}. Valid: {', '.join(valid_chunk_types)}"
            )

        # Validate step
        step = data.get("step", "")
        valid_steps = [s.value for s in IssueStep]
        if step not in valid_steps:
            errors.append(f"Invalid step: {step}. Valid: {', '.join(valid_steps)}")

        # Validate issue_id constraints based on step
        issue_id = data.get("issue_id", "")
        try:
            current_step = IssueStep(step)
            if current_step in IssueStep.steps_requiring_issue_id() and not issue_id:
                errors.append(f"issue_id must not be empty for step: {step}")
        except ValueError:
            pass  # Already reported invalid step above

        # Check non-empty constraints
        if not data.get("next_action"):
            errors.append("next_action must not be empty")

        if not data.get("goal"):
            errors.append("goal must not be empty")

        # Validate repo_state structure
        repo_state = data.get("repo_state")
        if not isinstance(repo_state, dict):
            errors.append("repo_state must be an object")
        else:
            if "git_head" not in repo_state:
                errors.append("repo_state.git_head is required")
            if not isinstance(repo_state.get("dirty"), bool):
                errors.append("repo_state.dirty must be boolean")

        # Check array types
        array_fields = ["changes", "commands_run", "rationale"]
        for field_name in array_fields:
            if not isinstance(data.get(field_name), list):
                errors.append(f"{field_name} must be an array")

        # Check retry_count
        retry_count = data.get("retry_count")
        if not isinstance(retry_count, int) or retry_count < 0:
            errors.append("retry_count must be a non-negative integer")

        # Validate session_id format (if not empty)
        session_id = data.get("session_id", "")
        if session_id:
            pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z?/[a-z-]+$"
            if not re.match(pattern, session_id):
                errors.append(
                    f"session_id format invalid. Expected: ISO-timestamp/step-name or empty, got: {session_id}"
                )

        # Validate changes array items
        changes = data.get("changes", [])
        if isinstance(changes, list):
            for i, change in enumerate(changes):
                if not isinstance(change, dict):
                    errors.append(f"changes[{i}]: must be an object")
                elif "path" not in change or "summary" not in change:
                    errors.append(f"changes[{i}]: must have 'path' and 'summary' fields")

        # Validate context (optional but must be dict if present)
        context = data.get("context")
        if context is not None and not isinstance(context, dict):
            errors.append("context must be an object if present")

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def load(self) -> CurrentIssue | None:
        """Load and validate current_issue, returning the model if valid."""
        result = self.validate()
        if not result.valid:
            return None

        data = json.loads(self.current_issue_path.read_text())
        return CurrentIssue.model_validate(data)

    @classmethod
    def validate_data(cls, data: dict) -> ValidationResult:
        """Validate a current_issue dict directly."""
        errors: list[str] = []
        warnings: list[str] = []

        # Check required fields
        for field_name in cls.REQUIRED_FIELDS:
            if field_name not in data:
                errors.append(f"MISSING: {field_name}")

        if errors:
            return ValidationResult(valid=False, errors=errors)

        # Try to create Pydantic model for full validation
        try:
            current_issue = CurrentIssue.model_validate(data)
            issue_errors = current_issue.validate_issue_id_constraint()
            errors.extend(issue_errors)
        except Exception as e:
            errors.append(f"Validation error: {e}")

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)
