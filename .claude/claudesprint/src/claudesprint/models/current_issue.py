"""CurrentIssue model - session context for the issue loop (replaces Handoff)."""

from datetime import datetime, UTC
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, field_validator


class ChunkType(StrEnum):
    """Chunk types representing phases of issue work."""

    SELECT = "select"       # Agent-driven issue selection
    IMPLEMENT = "implement" # Code implementation
    TEST = "test"           # Write and run tests
    REVIEW = "review"       # Code review
    FIX = "fix"             # Fix issues (tests or review)
    COMPLETE = "complete"   # Mark issue complete, cleanup


class IssueStep(StrEnum):
    """Granular workflow steps within the issue loop."""

    # Selection phase
    SELECT_ISSUE = "select-issue"

    # Implementation phase
    READ_DOCS = "read-docs"
    IMPLEMENT = "implement"

    # Testing phase (gated by require_testing)
    WRITE_TESTS = "write-tests"
    RUN_TESTS = "run-tests"
    FIX_TESTS = "fix-tests"

    # Validation phase (gated by require_browser_qa)
    BROWSER_VALIDATION = "browser-validation"

    # Review phase
    CODE_REVIEW = "code-review"
    FIX_CODE_REVIEW_ISSUES = "fix-code-review-issues"

    # Documentation phase
    UPDATE_DOCS = "update-docs"

    # Completion phase
    STAGE_CHANGES = "stage-changes"
    COMMIT_CHANGES = "commit-changes"
    COMPLETE_ISSUE = "complete-issue"

    @classmethod
    def ordered_steps(cls) -> list["IssueStep"]:
        """Return steps in workflow order."""
        return [
            cls.SELECT_ISSUE,
            cls.READ_DOCS,
            cls.IMPLEMENT,
            cls.WRITE_TESTS,
            cls.RUN_TESTS,
            cls.FIX_TESTS,
            cls.BROWSER_VALIDATION,
            cls.CODE_REVIEW,
            cls.FIX_CODE_REVIEW_ISSUES,
            cls.UPDATE_DOCS,
            cls.STAGE_CHANGES,
            cls.COMMIT_CHANGES,
            cls.COMPLETE_ISSUE,
        ]

    @classmethod
    def steps_requiring_issue_id(cls) -> set["IssueStep"]:
        """Steps that require a selected issue_id."""
        return {
            cls.READ_DOCS,
            cls.IMPLEMENT,
            cls.WRITE_TESTS,
            cls.RUN_TESTS,
            cls.FIX_TESTS,
            cls.BROWSER_VALIDATION,
            cls.CODE_REVIEW,
            cls.FIX_CODE_REVIEW_ISSUES,
            cls.UPDATE_DOCS,
            cls.STAGE_CHANGES,
            cls.COMMIT_CHANGES,
            cls.COMPLETE_ISSUE,
        }

    @classmethod
    def testing_steps(cls) -> set["IssueStep"]:
        """Steps related to testing (gated by require_testing)."""
        return {cls.WRITE_TESTS, cls.RUN_TESTS, cls.FIX_TESTS}

    @classmethod
    def browser_qa_steps(cls) -> set["IssueStep"]:
        """Steps related to browser QA (gated by require_browser_qa)."""
        return {cls.BROWSER_VALIDATION}

    def to_chunk_type(self) -> ChunkType:
        """Map step to its chunk type."""
        step_to_chunk = {
            IssueStep.SELECT_ISSUE: ChunkType.SELECT,
            IssueStep.READ_DOCS: ChunkType.IMPLEMENT,
            IssueStep.IMPLEMENT: ChunkType.IMPLEMENT,
            IssueStep.WRITE_TESTS: ChunkType.TEST,
            IssueStep.RUN_TESTS: ChunkType.TEST,
            IssueStep.FIX_TESTS: ChunkType.FIX,
            IssueStep.BROWSER_VALIDATION: ChunkType.REVIEW,
            IssueStep.CODE_REVIEW: ChunkType.REVIEW,
            IssueStep.FIX_CODE_REVIEW_ISSUES: ChunkType.FIX,
            IssueStep.UPDATE_DOCS: ChunkType.COMPLETE,
            IssueStep.STAGE_CHANGES: ChunkType.COMPLETE,
            IssueStep.COMMIT_CHANGES: ChunkType.COMPLETE,
            IssueStep.COMPLETE_ISSUE: ChunkType.COMPLETE,
        }
        return step_to_chunk[self]


class RepoState(BaseModel):
    """Git repository state."""

    git_head: str = Field(default="", description="Current git HEAD SHA")
    dirty: bool = Field(default=False, description="Whether there are uncommitted changes")


class FileChange(BaseModel):
    """A file change record."""

    path: str = Field(..., description="Path to the changed file")
    summary: str = Field(..., description="Brief summary of what changed")


class CurrentIssue(BaseModel):
    """Current issue session context - replaces Handoff for the new sprint model.

    Lives in: .claude/claudesprint/project/current_issue.json
    """

    model_config = {
        "populate_by_name": True,  # Allows initializing via CurrentIssue(schema_url=...)
        "extra": "ignore",  # Robustness: ignore unexpected fields in existing JSON
    }

    schema_url: str = Field(
        default="../../claudesprint/schemas/current_issue.schema.json",
        alias="$schema",
        description="Path to the JSON schema",
    )
    schema_version: Annotated[str, Field(pattern=r"^[0-9]+\.[0-9]+$")] = "2.0"
    session_id: str = Field(
        default="",
        description="Unique session identifier (ISO timestamp/step format)",
    )
    timestamp: str = Field(
        default="",
        description="ISO 8601 timestamp of last update",
    )

    # Sprint context
    sprint_path: str = Field(
        ...,
        min_length=1,
        description="Path to the sprint.json file (e.g., .claude/claudesprint/sprints/SPEC_01/sprint.json)",
    )

    # Issue context
    issue_id: str = Field(
        default="",
        description="ID of the current issue being worked on",
    )
    issue_title: str = Field(
        default="",
        description="Title of the current issue (for display purposes)",
    )

    # Workflow state
    chunk_type: ChunkType = Field(
        default=ChunkType.SELECT,
        description="Current chunk/phase of work",
    )
    step: IssueStep = Field(
        default=IssueStep.SELECT_ISSUE,
        description="Current granular workflow step",
    )
    goal: str = Field(
        default="Select next issue from sprint",
        description="1-2 sentence description of the current goal",
        max_length=500,
    )
    next_action: str = Field(
        default="Review sprint and select next issue to work on",
        description="Single concrete instruction for the next session",
        min_length=1,
    )

    # Repository state
    repo_state: RepoState = Field(
        default_factory=RepoState,
        description="Current git repository state",
    )

    # Changes and history
    changes: list[FileChange] = Field(
        default_factory=list,
        description="Files changed in this session with brief summaries",
    )
    commands_run: list[str] = Field(
        default_factory=list,
        description="Commands executed during the session",
    )

    # Failure tracking
    current_failures: str = Field(
        default="",
        description="Current test/build failures (empty if none)",
    )
    retry_count: Annotated[int, Field(ge=0)] = Field(
        default=0,
        description="Number of times the current step has been retried due to failures",
    )

    # Context preservation
    rationale: list[str] = Field(
        default_factory=list,
        description="Key decisions made and their reasoning",
    )
    context: dict[str, str] = Field(
        default_factory=dict,
        description="Arbitrary context data for the session",
    )

    # Optimization
    last_test_run_hash: str = Field(
        default="",
        description="Hash of code files at last successful test run (for skip logic)",
    )
    cached_docs: dict[str, str] = Field(
        default_factory=dict,
        description="Path -> content hash for documentation caching",
    )

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, v: str) -> str:
        """Validate session_id format (ISO timestamp/step or empty)."""
        import re

        if not v:
            return v
        pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z?/[a-z-]+$"
        if not re.match(pattern, v):
            raise ValueError(
                f"Invalid session_id format. Expected: ISO-timestamp/step-name or empty, got: {v}"
            )
        return v

    def validate_issue_id_constraint(self) -> list[str]:
        """Validate issue_id based on current step."""
        errors = []
        if self.step in IssueStep.steps_requiring_issue_id() and not self.issue_id:
            errors.append(f"issue_id must not be empty for step: {self.step}")
        return errors

    def generate_session_id(self) -> str:
        """Generate a new session_id based on current timestamp and step."""
        timestamp = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        return f"{timestamp}/{self.step.value}"

    def update_timestamp(self) -> None:
        """Update the timestamp to current UTC time."""
        self.timestamp = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    def prune_rationale(self, max_entries: int = 5) -> int:
        """Prune rationale array to prevent context window exhaustion.

        Keeps the most recent entries (last N entries).
        Default is conservative (5) to prevent token bloat in debugging loops.

        Args:
            max_entries: Maximum number of entries to keep.

        Returns:
            Number of entries pruned.
        """
        if len(self.rationale) <= max_entries:
            return 0

        pruned_count = len(self.rationale) - max_entries
        self.rationale = self.rationale[-max_entries:]
        return pruned_count

    def prune_arrays(
        self,
        max_rationale: int = 5,
        max_changes: int = 20,
        max_commands: int = 30,
    ) -> dict[str, int]:
        """Prune all arrays that can grow unbounded.

        Conservative defaults prevent context window exhaustion during
        debugging loops (e.g., fix-tests cycling 5+ times).

        Args:
            max_rationale: Maximum rationale entries to keep (default 5).
            max_changes: Maximum file change entries to keep (default 20).
            max_commands: Maximum commands_run entries to keep (default 30).

        Returns:
            Dict with counts of pruned entries per field.
        """
        pruned = {}

        # Prune rationale - most likely to grow large during debugging
        if len(self.rationale) > max_rationale:
            pruned["rationale"] = len(self.rationale) - max_rationale
            self.rationale = self.rationale[-max_rationale:]

        # Prune changes (keep most recent)
        if len(self.changes) > max_changes:
            pruned["changes"] = len(self.changes) - max_changes
            self.changes = self.changes[-max_changes:]

        # Prune commands_run
        if len(self.commands_run) > max_commands:
            pruned["commands_run"] = len(self.commands_run) - max_commands
            self.commands_run = self.commands_run[-max_commands:]

        return pruned

    @classmethod
    def create_initial(cls, sprint_path: str) -> "CurrentIssue":
        """Create an initial current issue for starting fresh."""
        return cls(
            schema_version="2.0",
            session_id="",
            timestamp="",
            sprint_path=sprint_path,
            issue_id="",
            issue_title="",
            chunk_type=ChunkType.SELECT,
            step=IssueStep.SELECT_ISSUE,
            goal="Select next issue from sprint",
            next_action="Review sprint and select next issue to work on",
            repo_state=RepoState(git_head="", dirty=False),
            changes=[],
            commands_run=[],
            current_failures="",
            retry_count=0,
            rationale=[],
            context={},
            last_test_run_hash="",
            cached_docs={},
        )

    def to_handoff_dict(self) -> dict:
        """Convert to a dict compatible with legacy Handoff schema (for backward compat)."""
        return {
            "schema_version": "1.0",
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "feature": self.issue_title or self.issue_id,
            "step": self._map_step_to_workflow_step(),
            "selected_task_id": self.issue_id,
            "recommended_task_id": "",
            "goal": self.goal,
            "repo_state": self.repo_state.model_dump(),
            "changes": [c.model_dump() for c in self.changes],
            "commands_run": self.commands_run,
            "current_failures": self.current_failures,
            "next_action": self.next_action,
            "assumptions": [],
            "open_questions": [],
            "rationale": self.rationale,
            "retry_count": self.retry_count,
            "last_test_run_hash": self.last_test_run_hash,
            "cached_docs": self.cached_docs,
            "shutdown_reason": "",
        }

    def _map_step_to_workflow_step(self) -> str:
        """Map IssueStep to workflow step string (matches prompt file names)."""
        step_map = {
            IssueStep.SELECT_ISSUE: "select-issue",
            IssueStep.READ_DOCS: "read-docs",
            IssueStep.IMPLEMENT: "implement",
            IssueStep.WRITE_TESTS: "write-tests",
            IssueStep.RUN_TESTS: "run-tests",
            IssueStep.FIX_TESTS: "fix-tests",
            IssueStep.BROWSER_VALIDATION: "browser-validation",
            IssueStep.CODE_REVIEW: "code-review",
            IssueStep.FIX_CODE_REVIEW_ISSUES: "fix-code-review-issues",
            IssueStep.UPDATE_DOCS: "update-docs",
            IssueStep.STAGE_CHANGES: "stage-changes",
            IssueStep.COMMIT_CHANGES: "commit-changes",
            IssueStep.COMPLETE_ISSUE: "complete-issue",
        }
        return step_map.get(self.step, "select-issue")
