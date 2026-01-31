"""Utility commands: validate, reset, notify."""

from pathlib import Path
from typing import Annotated, Optional

import typer

from claudesprint.commands._shared import (
    console,
    get_project_root,
    get_config,
    COLORS,
    success,
    error,
    warning,
    muted,
)


def validate_sprint(
    sprint: Annotated[
        Optional[str],
        typer.Option("--sprint", help="Path to sprint.json"),
    ] = None,
    spec: Annotated[
        Optional[str],
        typer.Option("--spec", help="Spec ID to validate"),
    ] = None,
) -> None:
    """Validate sprint.json and current_issue.json structure."""
    # Lazy imports
    from claudesprint.services.sprint_service import SprintService
    from claudesprint.validation import SprintValidator, CurrentIssueValidator

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
    sprint: Annotated[
        Optional[str],
        typer.Option("--sprint", help="Path to sprint.json"),
    ] = None,
    spec: Annotated[
        Optional[str],
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


def send_notification(
    notification_type: Annotated[
        str,
        typer.Argument(help="Notification type: step, failure, exit, rate_limit"),
    ],
    message: Annotated[
        str,
        typer.Argument(help="Notification message"),
    ],
    title: Annotated[
        Optional[str],
        typer.Option("--title", "-t", help="Optional custom title"),
    ] = None,
) -> None:
    """Send a notification via Bark."""
    # Lazy imports
    from claudesprint.services.configuration_manager import ConfigurationManager
    from claudesprint.services.notification_service import NotificationService, NotificationType

    config = get_config()
    project_root = get_project_root()
    cm = ConfigurationManager(project_root)
    service = NotificationService.from_config_manager(
        cm, http_timeout=config.http_timeout
    )

    if not service.enabled:
        console.print(warning("Notifications are not enabled"))
        return

    try:
        notif_type = NotificationType(notification_type)
    except ValueError:
        console.print(error(f"Invalid type: {notification_type}"))
        console.print(f"Valid types: {', '.join(t.value for t in NotificationType)}")
        raise typer.Exit(1)

    service.send_sync(notif_type, message, title)
    console.print(success("Notification sent"))
