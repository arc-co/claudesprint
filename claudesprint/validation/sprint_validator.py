"""Sprint validation logic."""

import json
from dataclasses import dataclass, field
from pathlib import Path

from claudesprint.models.sprint import IssuePriority, IssueStatus, Sprint
from claudesprint.utils.graph import detect_cycles


@dataclass
class ValidationResult:
    """Result of a validation check."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.valid


class SprintValidator:
    """Validates sprint.json files."""

    REQUIRED_FIELDS = [
        "schema_version",
        "spec_id",
        "spec_file",
        "issues",
        "config",
        "created_at",
        "metadata",
    ]

    REQUIRED_ISSUE_FIELDS = [
        "id",
        "title",
        "status",
        "priority",
        "acceptance_criteria",
    ]

    REQUIRED_CONFIG_FIELDS = [
        "require_testing",
        "require_browser_qa",
    ]

    def __init__(self, sprint_path: str | Path) -> None:
        self.sprint_path = Path(sprint_path)

    def validate(self) -> ValidationResult:
        """Run all validation checks."""
        errors: list[str] = []
        warnings: list[str] = []

        # Check file exists
        if not self.sprint_path.exists():
            return ValidationResult(valid=False, errors=[f"File not found: {self.sprint_path}"])

        # Try to parse JSON
        try:
            data = json.loads(self.sprint_path.read_text())
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

        # Validate spec_id
        spec_id = data.get("spec_id", "")
        if not spec_id:
            errors.append("spec_id must not be empty")

        # Validate spec_file
        spec_file = data.get("spec_file", "")
        if not spec_file:
            errors.append("spec_file must not be empty")

        # Validate issues array
        issues = data.get("issues", [])
        if not isinstance(issues, list):
            errors.append("issues must be an array")
        else:
            # Validate each issue
            issue_ids = set()
            for i, issue in enumerate(issues):
                issue_errors = self._validate_issue(issue, i)
                errors.extend(issue_errors)

                # Check for duplicate IDs
                issue_id = issue.get("id", "")
                if issue_id:
                    if issue_id in issue_ids:
                        errors.append(f"Duplicate issue ID: {issue_id}")
                    issue_ids.add(issue_id)

            # Validate dependencies reference existing issues
            for issue in issues:
                deps = issue.get("dependencies", [])
                for dep_id in deps:
                    if dep_id not in issue_ids:
                        warnings.append(
                            f"Issue {issue.get('id')} depends on non-existent issue: {dep_id}"
                        )

        # Validate config
        config = data.get("config", {})
        if not isinstance(config, dict):
            errors.append("config must be an object")
        else:
            for field_name in self.REQUIRED_CONFIG_FIELDS:
                if field_name not in config:
                    errors.append(f"config missing field: {field_name}")
                elif not isinstance(config[field_name], bool):
                    errors.append(f"config.{field_name} must be a boolean")

        # Validate metadata
        metadata = data.get("metadata", {})
        if not isinstance(metadata, dict):
            errors.append("metadata must be an object")
        else:
            required_meta = ["total_issues", "pending", "in_progress", "completed"]
            for field_name in required_meta:
                if field_name not in metadata:
                    warnings.append(f"metadata missing field: {field_name}")
                elif not isinstance(metadata[field_name], int):
                    errors.append(f"metadata.{field_name} must be an integer")

        # Check for circular dependencies
        circular_deps = self._check_circular_dependencies(issues)
        for cycle in circular_deps:
            warnings.append(f"Circular dependency detected: {' -> '.join(cycle)}")

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def _validate_issue(self, issue: dict, index: int) -> list[str]:
        """Validate a single issue."""
        errors = []
        prefix = f"issues[{index}]"

        if not isinstance(issue, dict):
            return [f"{prefix}: must be an object"]

        # Check required fields
        for field_name in self.REQUIRED_ISSUE_FIELDS:
            if field_name not in issue:
                errors.append(f"{prefix}: missing {field_name}")

        if errors:
            return errors

        # Validate ID format
        issue_id = issue.get("id", "")
        if not issue_id:
            errors.append(f"{prefix}: id must not be empty")
        elif not issue_id.replace("-", "").replace("_", "").isalnum():
            errors.append(f"{prefix}: id must contain only alphanumeric characters and hyphens")

        # Validate status
        status = issue.get("status", "")
        valid_statuses = [s.value for s in IssueStatus]
        if status not in valid_statuses:
            errors.append(f"{prefix}: invalid status '{status}'. Valid: {', '.join(valid_statuses)}")

        # Validate priority
        priority = issue.get("priority", "")
        valid_priorities = [p.value for p in IssuePriority]
        if priority not in valid_priorities:
            errors.append(
                f"{prefix}: invalid priority '{priority}'. Valid: {', '.join(valid_priorities)}"
            )

        # Validate acceptance_criteria
        criteria = issue.get("acceptance_criteria", [])
        if not isinstance(criteria, list):
            errors.append(f"{prefix}: acceptance_criteria must be an array")
        elif len(criteria) == 0:
            errors.append(f"{prefix}: acceptance_criteria must have at least one item")

        # Validate dependencies
        deps = issue.get("dependencies", [])
        if not isinstance(deps, list):
            errors.append(f"{prefix}: dependencies must be an array")

        return errors

    def _check_circular_dependencies(self, issues: list[dict]) -> list[list[str]]:
        """Check for circular dependencies in issue graph."""
        issue_map = {issue.get("id"): issue for issue in issues}
        return detect_cycles(
            nodes=list(issue_map.keys()),
            get_dependencies=lambda node_id: issue_map.get(node_id, {}).get(
                "dependencies", []
            ),
        )

    def load(self) -> Sprint | None:
        """Load and validate sprint, returning the model if valid."""
        result = self.validate()
        if not result.valid:
            return None

        data = json.loads(self.sprint_path.read_text())
        return Sprint.model_validate(data)

    @classmethod
    def validate_data(cls, data: dict) -> ValidationResult:
        """Validate a sprint dict directly."""
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
            Sprint.model_validate(data)
        except Exception as e:
            errors.append(f"Validation error: {e}")

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)
