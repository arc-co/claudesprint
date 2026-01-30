"""Sprint model - multi-spec project management with execution gates."""

from datetime import datetime, UTC
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, model_validator

from claudesprint.utils.graph import detect_cycles


class IssueStatus(StrEnum):
    """Issue status values."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"


class IssuePriority(StrEnum):
    """Issue priority levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IssueCategory(StrEnum):
    """Issue category types."""

    SETUP = "setup"
    INFRASTRUCTURE = "infrastructure"
    FEATURE = "feature"
    API = "api"
    UI = "ui"
    TESTING = "testing"
    DOCS = "docs"
    BUGFIX = "bugfix"


class IssueHistory(BaseModel):
    """A history entry for issue status changes."""

    timestamp: str = Field(..., description="ISO 8601 timestamp")
    action: str = Field(..., description="Description of the action taken")
    session_id: str | None = Field(default=None, description="Session ID when action occurred")


class IssueConfig(BaseModel):
    """Issue-specific execution configuration with gates.

    When set on an issue, these override the sprint-level defaults.
    """

    require_testing: bool | None = Field(
        default=None,
        description="Whether testing steps are required. None inherits from sprint config.",
    )
    require_browser_qa: bool | None = Field(
        default=None,
        description="Whether browser-validation step is required. None inherits from sprint config.",
    )


class Issue(BaseModel):
    """A single issue in the sprint (replaces Task in backlog model)."""

    id: Annotated[str, Field(pattern=r"^[a-z0-9-]+$")] = Field(
        ...,
        description="Unique identifier (lowercase, hyphens, numbers only)",
    )
    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Short issue title",
    )
    status: IssueStatus = Field(
        default=IssueStatus.PENDING,
        description="Current issue status",
    )
    priority: IssuePriority = Field(
        ...,
        description="Issue priority level",
    )
    category: IssueCategory | None = Field(
        default=None,
        description="Issue category type",
    )
    acceptance_criteria: list[str] = Field(
        ...,
        min_length=1,
        description="Specific, testable criteria for completion",
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="IDs of issues that must complete before this one",
    )
    notes: str | None = Field(
        default=None,
        description="Optional notes about the issue",
    )
    config: IssueConfig | None = Field(
        default=None,
        description="Issue-specific execution gates. Inherits from sprint config if null.",
    )
    history: list[IssueHistory] = Field(
        default_factory=list,
        description="Append-only history of status changes",
    )

    def add_history(self, action: str, session_id: str | None = None) -> None:
        """Add a history entry with current timestamp."""
        self.history.append(
            IssueHistory(
                timestamp=datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                action=action,
                session_id=session_id,
            )
        )

    def is_blocked_by(self, issues: list["Issue"]) -> bool:
        """Check if this issue is blocked by incomplete dependencies."""
        if not self.dependencies:
            return False
        issue_map = {i.id: i for i in issues}
        for dep_id in self.dependencies:
            dep = issue_map.get(dep_id)
            if dep and dep.status != IssueStatus.COMPLETED:
                return True
        return False

    def get_dependency_chain(self, issues: list["Issue"], visited: set[str] | None = None) -> list[str]:
        """Get the chain of dependencies for this issue.

        Args:
            issues: All issues to search for dependencies
            visited: Set of already-visited issue IDs (for cycle detection)

        Returns:
            List of issue IDs in dependency order, empty if cycle detected
        """
        if visited is None:
            visited = set()

        if self.id in visited:
            return []  # Cycle detected

        visited.add(self.id)
        issue_map = {i.id: i for i in issues}
        chain = []

        for dep_id in self.dependencies:
            dep = issue_map.get(dep_id)
            if dep:
                sub_chain = dep.get_dependency_chain(issues, visited.copy())
                chain.extend(sub_chain)
                chain.append(dep_id)

        return chain


class SprintConfig(BaseModel):
    """Sprint execution configuration with gates (global defaults)."""

    require_testing: bool = Field(
        default=True,
        description="Whether testing steps (write-tests, run-tests, fix-tests) are required",
    )
    require_browser_qa: bool = Field(
        default=False,
        description="Whether browser-validation step is required",
    )


class ResolvedConfig(BaseModel):
    """Resolved execution configuration for a specific issue.

    This is the result of merging issue-specific config with sprint defaults.
    All fields are guaranteed to have values (no None).
    """

    require_testing: bool = Field(
        default=True,
        description="Whether testing steps are required",
    )
    require_browser_qa: bool = Field(
        default=False,
        description="Whether browser-validation step is required",
    )

    @classmethod
    def from_sprint_and_issue(
        cls,
        sprint_config: "SprintConfig",
        issue_config: "IssueConfig | None",
    ) -> "ResolvedConfig":
        """Resolve configuration by merging issue overrides with sprint defaults.

        Args:
            sprint_config: Sprint-level default configuration
            issue_config: Issue-specific overrides (may be None)

        Returns:
            ResolvedConfig with all fields resolved to concrete values
        """
        # Start with sprint defaults
        require_testing = sprint_config.require_testing
        require_browser_qa = sprint_config.require_browser_qa

        # Override with issue-specific values if present
        if issue_config:
            if issue_config.require_testing is not None:
                require_testing = issue_config.require_testing
            if issue_config.require_browser_qa is not None:
                require_browser_qa = issue_config.require_browser_qa

        return cls(
            require_testing=require_testing,
            require_browser_qa=require_browser_qa,
        )


class SprintMetadata(BaseModel):
    """Sprint statistics metadata."""

    total_issues: Annotated[int, Field(ge=0)] = 0
    pending: Annotated[int, Field(ge=0)] = 0
    in_progress: Annotated[int, Field(ge=0)] = 0
    completed: Annotated[int, Field(ge=0)] = 0


class Sprint(BaseModel):
    """Sprint model - a collection of issues for a specific spec.

    Lives in: .claudesprint/sprints/<spec_id>/sprint.json
    """

    model_config = {
        "populate_by_name": True,  # Allows initializing via Sprint(schema_url=...)
        "extra": "ignore",  # Robustness: ignore unexpected fields in existing JSON
    }

    schema_url: str = Field(
        default="../../claudesprint/schemas/sprint.schema.json",
        alias="$schema",
        description="Path to the JSON schema",
    )
    schema_version: Annotated[str, Field(pattern=r"^[0-9]+\.[0-9]+$")] = "2.0"
    spec_id: str = Field(
        ...,
        min_length=1,
        description="Unique identifier derived from spec file (e.g., SPEC_01)",
    )
    spec_file: str = Field(
        ...,
        min_length=1,
        description="Path to the source spec file (e.g., .claudesprint/specs/SPEC_01.md)",
    )
    description: str = Field(
        default="",
        description="Sprint description",
    )
    issues: list[Issue] = Field(
        default_factory=list,
        description="List of issues in the sprint",
    )
    config: SprintConfig = Field(
        default_factory=SprintConfig,
        description="Sprint execution configuration",
    )
    git_branch: str | None = Field(
        default=None,
        description="Git branch for this sprint (e.g., sprint/SPEC_01)",
    )
    created_at: str = Field(
        default="",
        description="ISO 8601 timestamp of sprint creation",
    )
    last_modified: str | None = Field(
        default=None,
        description="ISO 8601 timestamp of last modification",
    )
    metadata: SprintMetadata = Field(
        default_factory=SprintMetadata,
        description="Sprint statistics",
    )

    @model_validator(mode="after")
    def update_metadata(self) -> "Sprint":
        """Update metadata counts based on issues."""
        self.metadata.total_issues = len(self.issues)
        self.metadata.pending = sum(1 for i in self.issues if i.status == IssueStatus.PENDING)
        self.metadata.in_progress = sum(1 for i in self.issues if i.status == IssueStatus.IN_PROGRESS)
        self.metadata.completed = sum(1 for i in self.issues if i.status == IssueStatus.COMPLETED)
        return self

    def get_issue(self, issue_id: str) -> Issue | None:
        """Get an issue by ID."""
        for issue in self.issues:
            if issue.id == issue_id:
                return issue
        return None

    def get_available_issues(self) -> list[Issue]:
        """Get all pending issues that are not blocked by dependencies or cycles.

        Returns:
            List of issues that can be worked on.
        """
        # First, find all issues involved in cycles
        cycles = self.detect_circular_dependencies()
        cyclic_issue_ids = set()
        for cycle in cycles:
            cyclic_issue_ids.update(cycle[:-1])  # Exclude last (duplicate of first)

        # Return pending issues that are not blocked and not in cycles
        return [
            issue
            for issue in self.issues
            if (
                issue.status == IssueStatus.PENDING
                and not issue.is_blocked_by(self.issues)
                and issue.id not in cyclic_issue_ids
            )
        ]

    def get_stats(self) -> dict[str, int]:
        """Get current issue statistics."""
        blocked = sum(
            1 for i in self.issues if i.status == IssueStatus.PENDING and i.is_blocked_by(self.issues)
        )
        return {
            "total": self.metadata.total_issues,
            "pending": self.metadata.pending,
            "in_progress": self.metadata.in_progress,
            "completed": self.metadata.completed,
            "blocked": blocked,
        }

    def detect_circular_dependencies(self) -> list[list[str]]:
        """Detect circular dependencies in the issue graph.

        Uses DFS to find all cycles with normalization to avoid duplicates.

        Returns:
            List of cycles, where each cycle is a list of issue IDs.
            Empty list if no cycles found.
        """
        issue_map = {i.id: i for i in self.issues}
        return detect_cycles(
            nodes=list(issue_map.keys()),
            get_dependencies=lambda node_id: (
                list(issue_map[node_id].dependencies) if node_id in issue_map else []
            ),
        )

    def has_circular_dependencies(self) -> bool:
        """Check if there are any circular dependencies.

        Returns:
            True if circular dependencies exist, False otherwise.
        """
        return len(self.detect_circular_dependencies()) > 0

    def update_last_modified(self) -> None:
        """Update the last_modified timestamp."""
        self.last_modified = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    def is_complete(self) -> bool:
        """Check if all issues in the sprint are completed."""
        return all(issue.status == IssueStatus.COMPLETED for issue in self.issues)

    @classmethod
    def create_initial(cls, spec_id: str, spec_file: str, description: str = "") -> "Sprint":
        """Create an initial sprint for a spec file."""
        return cls(
            schema_version="2.0",
            spec_id=spec_id,
            spec_file=spec_file,
            description=description,
            issues=[],
            config=SprintConfig(),
            git_branch=f"sprint/{spec_id}",
            created_at=datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            last_modified=None,
            metadata=SprintMetadata(),
        )
