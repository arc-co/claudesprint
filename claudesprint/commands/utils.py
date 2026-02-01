"""Utility commands: validate, reset."""

from pathlib import Path
from typing import Annotated

import typer

from claudesprint.commands._shared import (
    COLORS,
    console,
    error,
    get_config,
    muted,
    success,
    warning,
)


def validate_sprint(
    sprint: Annotated[
        str | None,
        typer.Option("--sprint", help="Path to sprint.json"),
    ] = None,
    spec: Annotated[
        str | None,
        typer.Option("--spec", help="Spec ID to validate"),
    ] = None,
) -> None:
    """Validate sprint.json and current_issue.json structure."""
    # Lazy imports
    from claudesprint.services.sprint_service import SprintService
    from claudesprint.validation import CurrentIssueValidator, SprintValidator

    config = get_config()

    console.print("=== Validating ClaudeSprint artifacts ===")
    console.print("")

    # Determine sprint path
    if sprint:
        sprint_path = Path(sprint)
    elif spec:
        sprint_service = SprintService(config.sprints_dir)
        sprint_path = sprint_service.get_sprint_path(spec)
    else:
        # Find active sprint
        sprint_service = SprintService(config.sprints_dir)
        sprint_path, _ = sprint_service.get_active_sprint()
        if not sprint_path:
            console.print(warning("No active sprint found to validate."))
            return

    # Validate sprint
    if sprint_path and sprint_path.exists():
        console.print(f"[bold]Sprint:[/bold] {sprint_path}")
        validator = SprintValidator(sprint_path)
        result = validator.validate()
        if result.valid:
            console.print(success("Sprint validation PASSED"))
        else:
            console.print(error("Sprint validation FAILED"))
            for err in result.errors:
                console.print(f"  [{COLORS.ERROR}]• {err}[/{COLORS.ERROR}]")
        for warn in result.warnings:
            console.print(f"  {warning(warn)}")
        console.print("")

    # Validate current_issue
    current_issue_path = Path(config.current_issue_file)
    if current_issue_path.exists():
        console.print(f"[bold]Current Issue:[/bold] {current_issue_path}")
        validator = CurrentIssueValidator(current_issue_path)
        result = validator.validate()
        if result.valid:
            console.print(success("Current issue validation PASSED"))
        else:
            console.print(error("Current issue validation FAILED"))
            for err in result.errors:
                console.print(f"  [{COLORS.ERROR}]• {err}[/{COLORS.ERROR}]")
        for warn in result.warnings:
            console.print(f"  {warning(warn)}")
    else:
        console.print(muted("No current_issue.json (not mid-issue)"))


def reset_sprint(
    sprint: Annotated[  # noqa: ARG001
        str | None,
        typer.Option("--sprint", help="Path to sprint.json"),
    ] = None,
    spec: Annotated[  # noqa: ARG001
        str | None,
        typer.Option("--spec", help="Spec ID to reset"),
    ] = None,
) -> None:
    """Reset current issue state (clear current_issue.json)."""
    # Lazy import
    from claudesprint.services.issue_service import IssueService

    config = get_config()
    issue_service = IssueService(config.project_dir)

    if issue_service.clear_current_issue():
        console.print(success("Current issue cleared."))
        console.print("Run 'claudesprint run' to start fresh.")
    else:
        console.print(warning("No current issue to clear."))
