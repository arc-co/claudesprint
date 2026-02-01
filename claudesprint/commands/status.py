"""Status display commands: status, sprints, models."""

import os
from pathlib import Path
from typing import Annotated

import typer
from rich.panel import Panel
from rich.table import Table

from claudesprint.commands._shared import (
    STYLES,
    console,
    error,
    get_config,
    get_project_root,
    model_badge,
    muted,
    status_badge,
    warning,
)


def show_status(
    sprint: Annotated[
        str | None,
        typer.Option("--sprint", help="Path to sprint.json"),
    ] = None,
    spec: Annotated[
        str | None,
        typer.Option("--spec", help="Spec ID to show status for"),
    ] = None,
) -> None:
    """Show current sprint workflow status."""
    # Lazy imports
    from claudesprint.models.sprint import ResolvedConfig
    from claudesprint.services.git_service import GitService
    from claudesprint.services.issue_service import IssueService
    from claudesprint.services.sprint_service import SprintService

    project_root = get_project_root()
    config = get_config()
    git_service = GitService(project_root, git_timeout=config.git_timeout)

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
            console.print(Panel.fit("ClaudeSprint - Status", style=STYLES.PANEL_HEADER))
            console.print("")
            console.print(muted("No active sprint found."))
            console.print("")
            console.print("Create a sprint with:")
            console.print("  claudesprint init --spec <spec_file>")
            console.print("")
            console.print("List available sprints:")
            console.print("  claudesprint sprints")
            return

    if not sprint_path.exists():
        console.print(error(f"Sprint file not found: {sprint_path}"))
        raise typer.Exit(1)

    sprint_service = SprintService(sprint_path.parent.parent)
    sprint_model = sprint_service.read_sprint(sprint_path)
    if not sprint_model:
        console.print(error(f"Failed to parse sprint file: {sprint_path}"))
        raise typer.Exit(1)

    issue_service = IssueService(config.project_dir)
    current_issue = issue_service.read_current_issue()

    console.print(Panel.fit("ClaudeSprint - Sprint Status", style=STYLES.PANEL_HEADER))
    console.print("")

    # Sprint info
    table = Table(show_header=False, box=None)
    table.add_column("Key", style="bold")
    table.add_column("Value")

    table.add_row("Spec ID", sprint_model.spec_id)
    table.add_row("Spec file", sprint_model.spec_file)
    table.add_row("Description", sprint_model.description or muted("<none>"))
    table.add_row("Branch", sprint_model.git_branch or muted("<none>"))
    table.add_row("Status", status_badge("Complete") if sprint_model.is_complete() else status_badge("In progress"))

    console.print(table)
    console.print("")

    # Sprint stats
    stats = sprint_model.get_stats()
    console.print("[bold]Issue Summary:[/bold]")
    stats_table = Table(show_header=False, box=None)
    stats_table.add_column("Status", style="bold")
    stats_table.add_column("Count", justify="right")

    stats_table.add_row("Pending", str(stats["pending"]))
    stats_table.add_row("In Progress", str(stats["in_progress"]))
    stats_table.add_row("Completed", str(stats["completed"]))
    if stats["blocked"] > 0:
        stats_table.add_row("Blocked", str(stats["blocked"]))

    console.print(stats_table)
    console.print("")

    # Current issue
    if current_issue and current_issue.issue_id:
        console.print("[bold]Current Issue:[/bold]")
        console.print(f"  ID: {current_issue.issue_id}")
        console.print(f"  Step: {status_badge(current_issue.step.value)}")
        console.print(f"  Goal: {current_issue.goal}")
    else:
        console.print(muted("No issue currently in progress"))
    console.print("")

    # Available issues
    available = sprint_model.get_available_issues()
    if available:
        console.print("[bold]Available Issues:[/bold]")
        for issue in available[:5]:  # Show first 5
            console.print(f"  [{issue.priority}] {issue.id}: {issue.title}")
        if len(available) > 5:
            console.print(f"  ... and {len(available) - 5} more")

    # Configuration - show active issue config if available, otherwise sprint defaults
    console.print("")
    console.print("[bold]Configuration:[/bold]")
    if current_issue and current_issue.issue_id:
        # Show resolved config for active issue
        active_issue = sprint_model.get_issue(current_issue.issue_id)
        if active_issue:
            resolved = ResolvedConfig.from_sprint_and_issue(sprint_model.config, active_issue.config)
            console.print(f"  {muted(f'(for active issue: {current_issue.issue_id})')}")
            console.print(f"  require_testing: {resolved.require_testing}")
            console.print(f"  require_browser_qa: {resolved.require_browser_qa}")
            if active_issue.config:
                console.print(f"  {muted('(issue overrides sprint defaults)')}")
        else:
            # Fallback to sprint config
            console.print(f"  require_testing: {sprint_model.config.require_testing}")
            console.print(f"  require_browser_qa: {sprint_model.config.require_browser_qa}")
    else:
        # No active issue, show sprint defaults
        console.print(f"  {muted('(sprint defaults)')}")
        console.print(f"  require_testing: {sprint_model.config.require_testing}")
        console.print(f"  require_browser_qa: {sprint_model.config.require_browser_qa}")

    # Git status
    console.print("")
    git_status = git_service.get_status()
    if git_status.is_repo:
        console.print(f"[bold]Git:[/bold] {git_status.branch} @ {git_status.head}")
        if git_status.dirty:
            console.print(f"  {warning('Uncommitted changes')}")
    else:
        console.print(muted("Not a git repository"))


def list_sprints() -> None:
    """List all available sprints."""
    # Lazy import
    from claudesprint.services.sprint_service import SprintService

    config = get_config()
    sprint_service = SprintService(config.sprints_dir)

    console.print(Panel.fit("Available Sprints", style=STYLES.PANEL_HEADER))
    console.print("")

    sprints = sprint_service.list_sprints()

    if not sprints:
        console.print(muted("No sprints found."))
        console.print("")
        console.print("Create a sprint with:")
        console.print("  claudesprint init --spec <spec_file>")
        return

    table = Table()
    table.add_column("Spec ID", style="bold")
    table.add_column("Status")
    table.add_column("Progress")
    table.add_column("Branch")

    for sprint_path in sprints:
        sprint = sprint_service.read_sprint(sprint_path)
        if not sprint:
            continue

        stats = sprint.get_stats()
        progress = f"{stats['completed']}/{stats['total']}"
        status = status_badge("Complete") if sprint.is_complete() else status_badge("In Progress")
        branch = sprint.git_branch or muted("none")

        table.add_row(sprint.spec_id, status, progress, branch)

    console.print(table)


def show_models() -> None:
    """Show model configuration for each step."""
    # Lazy imports
    from claudesprint.models.current_issue import IssueStep
    from claudesprint.services.configuration_manager import ConfigurationManager
    from claudesprint.services.models_service import ModelsService

    project_root = get_project_root()
    cm = ConfigurationManager(project_root)
    models_service = ModelsService.from_config_manager(cm)
    project_config = cm.project

    console.print(Panel.fit("Model Configuration", style=STYLES.PANEL_HEADER))
    console.print("")

    # Show override status
    env_override = os.environ.get("CLAUDESPRINT_MODEL_OVERRIDE", "")
    if env_override:
        console.print(warning(f"Environment override active: CLAUDESPRINT_MODEL_OVERRIDE={env_override}"))
        console.print("")

    if project_config.models.model_override:
        console.print(warning(f"Config override active: model_override={project_config.models.model_override}"))
        console.print("")

    # Show per-step models
    summary = models_service.get_step_model_summary()

    table = Table(title="Step Models")
    table.add_column("Step", style="bold")
    table.add_column("Model")
    table.add_column("Notes", style="dim")

    for step in IssueStep:
        step_name = step.value
        model = summary.get(step_name, "opus")

        if step in [IssueStep.RUN_TESTS, IssueStep.STAGE_CHANGES, IssueStep.COMMIT_CHANGES]:
            notes = muted("automated (no AI)")
        else:
            notes = status_badge("AI required")

        table.add_row(step_name, model_badge(model), notes)

    console.print(table)
    console.print("")

    # Special steps
    console.print("[bold]Special Steps:[/bold]")
    special_table = Table(show_header=False, box=None)
    special_table.add_column("Step", style="bold")
    special_table.add_column("Model")

    for special in ["init", "plan"]:
        model = summary.get(special, "opus")
        special_table.add_row(special, model_badge(model))

    console.print(special_table)
    console.print("")

    # Cost summary
    opus_count = sum(1 for m in summary.values() if m == "opus")
    sonnet_count = sum(1 for m in summary.values() if m == "sonnet")
    console.print(f"[bold]Summary:[/bold] {opus_count} opus steps, {sonnet_count} sonnet steps")
