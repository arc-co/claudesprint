"""Type definitions for step execution.

These types are shared between issue_engine.py and step_executors.py.
Keeping them in a separate module avoids circular imports.
"""

from dataclasses import dataclass

from claudesprint.models.current_issue import IssueStep


@dataclass
class StepResult:
    """Result of executing a single workflow step."""

    success: bool
    next_step: IssueStep | None
    output: str
    rate_limited: bool = False
    crashed: bool = False
    error: str | None = None
    matched_signal: str | None = None  # The routing signal that matched, or None if default


@dataclass
class ParseResult:
    """Result of parsing step output."""

    next_step: IssueStep | None
    matched_signal: str | None  # The signal that matched, or None if default
