"""CLI interface for ClaudeSprint using Typer."""

import os
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from claudesprint import __version__
from claudesprint.core.issue_engine import IssueEngine
from claudesprint.core.sprint_engine import SprintEngine, SprintExitReason, SprintResult
from claudesprint.models.config import ClaudesprintConfig
from claudesprint.models.current_issue import IssueStep
from claudesprint.models.sprint import Sprint, Issue, ResolvedConfig
from claudesprint.services.git_service import GitService
from claudesprint.services.sprint_service import SprintService
from claudesprint.services.issue_service import IssueService
from claudesprint.services.models_service import ModelsService, STEP_DEFAULT_MODELS
from claudesprint.services.notification_service import NotificationService, NotificationType
from claudesprint.ui import WorkflowDashboard
from claudesprint.utils.duration import format_duration
from claudesprint.utils.process_manager import get_process_manager

# Initialize process manager early to install signal handlers for cleanup
# This ensures Ctrl+C and other signals properly terminate Claude processes
_process_manager = get_process_manager()

app = typer.Typer(
    name="claudesprint",
    help="ClaudeSprint - Autonomous workflow orchestration for AI-driven development",
    no_args_is_help=False,
)

console = Console()


def get_project_root() -> Path:
    """Get the project root directory."""
    from claudesprint.services.path_service import PathService

    discovered = PathService.discover_project_root()
    return discovered or Path.cwd()


def get_config() -> ClaudesprintConfig:
    """Get configuration for current project."""
    return ClaudesprintConfig.from_project_root(str(get_project_root()))


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option("--version", "-v", help="Show version"),
    ] = False,
) -> None:
    """ClaudeSprint - Run the workflow by default."""
    if version:
        console.print(f"claudesprint version {__version__}")
        raise typer.Exit()

    # If no subcommand, show status
    if ctx.invoked_subcommand is None:
        show_status()


@app.command("run")
def run_workflow(
    max_iterations: Annotated[
        int,
        typer.Option("-n", "--max-iterations", help="Maximum iterations (0 = unlimited)"),
    ] = 0,
    sprint: Annotated[
        Optional[str],
        typer.Option("--sprint", help="Path to sprint.json"),
    ] = None,
    spec: Annotated[
        Optional[str],
        typer.Option("--spec", help="Spec ID to run sprint for (e.g., SPEC_01)"),
    ] = None,
    debug_conversations: Annotated[
        bool,
        typer.Option(
            "--debug-conversations",
            help="Log raw agent inputs/outputs to agent_conversations.log",
        ),
    ] = False,
) -> None:
    """Run the sprint workflow loop.

    Use --sprint to specify a path to sprint.json, or --spec to use a spec ID.
    Without arguments, runs the first active sprint found.
    """
    project_root = get_project_root()
    config = get_config()

    # Override config if CLI flag is set
    if debug_conversations:
        config.debug_conversations = True

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
            console.print("[yellow]No active sprint found.[/yellow]")
            console.print("")
            console.print("Create a sprint with:")
            console.print("  claudesprint init --spec <spec_file>")
            console.print("")
            console.print("Or specify a sprint:")
            console.print("  claudesprint run --spec SPEC_01")
            console.print("  claudesprint run --sprint path/to/sprint.json")
            raise typer.Exit(1)

    _run_sprint_console(project_root, config, sprint_path, max_iterations)


def _run_sprint_console(
    project_root: Path,
    config: ClaudesprintConfig,
    sprint_path: Path,
    max_iterations: int,
) -> None:
    """Run the sprint workflow with console output and dashboard."""
    if not sprint_path.exists():
        console.print(f"[red]Sprint file not found: {sprint_path}[/red]")
        console.print("Run 'claudesprint init --spec <spec_file>' to create a sprint.")
        raise typer.Exit(1)

    # Load sprint for initial stats
    sprint_service = SprintService(sprint_path.parent.parent)
    sprint = sprint_service.read_sprint(sprint_path)
    if not sprint:
        console.print(f"[red]Failed to parse sprint file: {sprint_path}[/red]")
        raise typer.Exit(1)

    # Create dashboard with initial sprint info
    dashboard = WorkflowDashboard()
    stats = sprint.get_stats()
    dashboard.set_sprint_info(
        sprint.spec_id,
        stats["total"],
        stats["completed"],
    )

    # Set issues for the board display
    def refresh_issues_board() -> None:
        # Reload sprint from disk to get current status
        # (the sprint_engine updates the file, not our local object)
        current_sprint = sprint_service.read_sprint(sprint_path)
        if current_sprint:
            issues_data = [
                (issue.id, issue.title, issue.status.value)
                for issue in current_sprint.issues
            ]
            dashboard.set_issues(issues_data)

    refresh_issues_board()

    engine = SprintEngine(project_root, sprint_path, config)

    # Set up callbacks
    def on_issue_start(issue: Issue) -> None:
        dashboard.set_issue(issue.id, issue.title)
        refresh_issues_board()

    def on_issue_complete(issue: Issue) -> None:
        dashboard.increment_completed()
        dashboard.clear_issue()
        refresh_issues_board()

    def on_sprint_complete(result: SprintResult) -> None:
        # Sprint complete message is now shown in the final panel
        pass

    def configure_issue_engine(issue_engine: IssueEngine) -> None:
        """Wire up dashboard callbacks to the issue engine."""
        issue_engine.on_step_start = dashboard.on_step_start
        issue_engine.on_step_complete = dashboard.on_step_complete
        issue_engine.on_step_skip = dashboard.on_step_skip
        issue_engine.on_step_failure = dashboard.on_step_failure
        # Wire subprocess callbacks for real-time subprocess info
        issue_engine.on_subprocess_start = dashboard.on_subprocess_start
        issue_engine.on_subprocess_output = dashboard.on_subprocess_output
        issue_engine.on_subprocess_end = dashboard.on_subprocess_end

    engine.on_issue_start = on_issue_start
    engine.on_issue_complete = on_issue_complete
    engine.on_sprint_complete = on_sprint_complete
    engine.issue_engine_configurator = configure_issue_engine

    # Run with dashboard
    with dashboard:
        result = engine.run(max_iterations=max_iterations)

    console.print("")
    if result.exit_reason == SprintExitReason.COMPLETED:
        # Print the instructions message (contains PR submission info)
        if result.message and "Manual PR submission" in result.message:
            console.print(result.message)
        else:
            console.print(Panel.fit(
                f"[bold green]v SPRINT COMPLETE[/bold green]\n"
                f"Issues completed: {result.issues_completed}\n"
                f"Runtime: {format_duration(result.elapsed_seconds)}",
                style="green",
            ))
    elif result.exit_reason == SprintExitReason.ERROR:
        console.print(Panel.fit(
            f"[bold red]x Error: {result.message}[/bold red]\n"
            f"{result.error or ''}",
            style="red",
        ))
        raise typer.Exit(1)
    else:
        console.print(f"[yellow]Exit: {result.exit_reason.value} - {result.message}[/yellow]")


@app.command("init")
def init_project(
    spec: Annotated[
        str,
        typer.Option("--spec", "-s", help="Spec file to create sprint from"),
    ],
    description: Annotated[
        Optional[str],
        typer.Option("--description", "-d", help="Sprint description"),
    ] = None,
    debug_conversations: Annotated[
        bool,
        typer.Option(
            "--debug-conversations",
            help="Log raw agent inputs/outputs to agent_conversations.log",
        ),
    ] = False,
) -> None:
    """Initialize a new sprint from a spec file.

    Creates a new sprint.json in .claude/claudesprint/sprints/<spec_id>/ and invokes
    the init agent to populate it with issues from the spec.
    """
    project_root = get_project_root()
    config = get_config()

    # Find spec file
    spec_path = Path(spec)
    if not spec_path.exists():
        # Try looking in .claude/claudesprint/specs/
        spec_path = Path(config.specs_dir) / spec
        if not spec_path.exists():
            # Try adding .md extension
            spec_path = Path(config.specs_dir) / f"{spec}.md"

    if not spec_path.exists():
        console.print(f"[red]Spec file not found: {spec}[/red]")
        console.print("Looked in:")
        console.print(f"  • {spec}")
        console.print(f"  • .claude/claudesprint/specs/{spec}")
        console.print(f"  • .claude/claudesprint/specs/{spec}.md")
        raise typer.Exit(1)

    sprint_service = SprintService(config.sprints_dir)
    # Convert to relative path for storage
    try:
        relative_spec_path = spec_path.relative_to(project_root)
    except ValueError:
        # If spec_path is not under project_root, use as-is
        relative_spec_path = spec_path
    sprint_path, sprint = sprint_service.create_sprint_from_spec(
        relative_spec_path, description or ""
    )

    # Ensure sprints directory exists
    sprint_path.parent.mkdir(parents=True, exist_ok=True)

    # Write sprint skeleton
    if not sprint_service.write_sprint(sprint, sprint_path):
        console.print(f"[red]✗ Failed to create sprint[/red]")
        raise typer.Exit(1)

    console.print(f"[green]✓ Sprint skeleton created: {sprint_path}[/green]")
    console.print(f"  Spec ID: {sprint.spec_id}")
    console.print(f"  Spec file: {sprint.spec_file}")
    console.print(f"  Branch: {sprint.git_branch}")
    console.print("")

    # Now invoke the init agent to populate the sprint with issues
    # Load prompt from package resources via PathService
    try:
        prompt_content = config.paths.get_prompt_content("init")
    except FileNotFoundError:
        console.print("[red]Error: PROMPT_init.md not found in package[/red]")
        raise typer.Exit(1)

    # Get model for init step
    models_service = ModelsService(config.models_file)
    model = models_service.get_model_for_special_step("init")

    console.print(f"[cyan]▶ Running init agent to generate issues (model: {model})...[/cyan]")

    # Build context for the agent
    context = f"""## Initialization Context

You are initializing a sprint for:
- **Spec ID**: {sprint.spec_id}
- **Spec file**: {relative_spec_path}
- **Sprint file**: {sprint_path.relative_to(project_root)}

Read the spec file and populate the sprint.json with all required issues.

---"""

    from claudesprint.core.claude_runner import ClaudeRunner

    runner = ClaudeRunner(
        project_root,
        config.claude_timeout,
        conversation_log_file=(
            config.conversation_log_file if debug_conversations else None
        ),
    )
    result = runner.run_with_content(
        prompt_content,
        source_name="PROMPT_init.md",
        on_output=lambda line: console.print(line),
        model=model,
        context=context,
    )

    if result.exit_code == 0:
        console.print("")
        console.print("[green]✓ Sprint initialization complete.[/green]")
        console.print(f"Run 'claudesprint run --spec {sprint.spec_id}' to start the sprint workflow.")
    else:
        console.print(f"[red]✗ Init agent failed (exit code: {result.exit_code})[/red]")
        if result.rate_limited:
            console.print("[yellow]Rate limit detected. Please wait and try again.[/yellow]")
        raise typer.Exit(1)


@app.command("plan")
def run_planner(
    spec: Annotated[
        Optional[str],
        typer.Option("--spec", "-s", help="Spec ID to plan for"),
    ] = None,
    debug_conversations: Annotated[
        bool,
        typer.Option(
            "--debug-conversations",
            help="Log raw agent inputs/outputs to agent_conversations.log",
        ),
    ] = False,
) -> None:
    """Run planning mode to generate issues from a spec file."""
    project_root = get_project_root()
    config = get_config()

    # Load prompt from package resources via PathService
    try:
        prompt_content = config.paths.get_prompt_content("plan")
    except FileNotFoundError:
        console.print("[red]Error: PROMPT_plan.md not found in package[/red]")
        raise typer.Exit(1)

    # Get model for plan step
    models_service = ModelsService(config.models_file)
    model = models_service.get_model_for_special_step("plan")

    console.print(f"[cyan]▶ Running planner (model: {model})...[/cyan]")

    from claudesprint.core.claude_runner import ClaudeRunner

    runner = ClaudeRunner(
        project_root,
        config.claude_timeout,
        conversation_log_file=(
            config.conversation_log_file if debug_conversations else None
        ),
    )
    result = runner.run_with_content(
        prompt_content,
        source_name="PROMPT_plan.md",
        on_output=lambda line: console.print(line),
        model=model,
    )

    if result.exit_code == 0:
        console.print("[green]✓ Planning complete.[/green]")
    else:
        console.print(f"[red]✗ Planning failed (exit code: {result.exit_code})[/red]")
        raise typer.Exit(1)


@app.command("status")
def show_status(
    sprint: Annotated[
        Optional[str],
        typer.Option("--sprint", help="Path to sprint.json"),
    ] = None,
    spec: Annotated[
        Optional[str],
        typer.Option("--spec", help="Spec ID to show status for"),
    ] = None,
) -> None:
    """Show current sprint workflow status."""
    project_root = get_project_root()
    config = get_config()
    git_service = GitService(project_root)

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
            console.print(Panel.fit("ClaudeSprint - Status", style="bold blue"))
            console.print("")
            console.print("[dim]No active sprint found.[/dim]")
            console.print("")
            console.print("Create a sprint with:")
            console.print("  claudesprint init --spec <spec_file>")
            console.print("")
            console.print("List available sprints:")
            console.print("  claudesprint sprints")
            return

    if not sprint_path.exists():
        console.print(f"[red]Sprint file not found: {sprint_path}[/red]")
        raise typer.Exit(1)

    sprint_service = SprintService(sprint_path.parent.parent)
    sprint_model = sprint_service.read_sprint(sprint_path)
    if not sprint_model:
        console.print(f"[red]Failed to parse sprint file: {sprint_path}[/red]")
        raise typer.Exit(1)

    issue_service = IssueService(config.project_dir)
    current_issue = issue_service.read_current_issue()

    console.print(Panel.fit("ClaudeSprint - Sprint Status", style="bold magenta"))
    console.print("")

    # Sprint info
    table = Table(show_header=False, box=None)
    table.add_column("Key", style="bold")
    table.add_column("Value")

    table.add_row("Spec ID", sprint_model.spec_id)
    table.add_row("Spec file", sprint_model.spec_file)
    table.add_row("Description", sprint_model.description or "[dim]<none>[/dim]")
    table.add_row("Branch", sprint_model.git_branch or "[dim]<none>[/dim]")
    table.add_row("Status", "[green]Complete[/green]" if sprint_model.is_complete() else "[yellow]In progress[/yellow]")

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
        console.print(f"  Step: [green]{current_issue.step.value}[/green]")
        console.print(f"  Goal: {current_issue.goal}")
    else:
        console.print("[dim]No issue currently in progress[/dim]")
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
            console.print(f"  [dim](for active issue: {current_issue.issue_id})[/dim]")
            console.print(f"  require_testing: {resolved.require_testing}")
            console.print(f"  require_browser_qa: {resolved.require_browser_qa}")
            if active_issue.config:
                console.print(f"  [dim](issue overrides sprint defaults)[/dim]")
        else:
            # Fallback to sprint config
            console.print(f"  require_testing: {sprint_model.config.require_testing}")
            console.print(f"  require_browser_qa: {sprint_model.config.require_browser_qa}")
    else:
        # No active issue, show sprint defaults
        console.print(f"  [dim](sprint defaults)[/dim]")
        console.print(f"  require_testing: {sprint_model.config.require_testing}")
        console.print(f"  require_browser_qa: {sprint_model.config.require_browser_qa}")

    # Git status
    console.print("")
    git_status = git_service.get_status()
    if git_status.is_repo:
        console.print(f"[bold]Git:[/bold] {git_status.branch} @ {git_status.head}")
        if git_status.dirty:
            console.print("  [yellow]Uncommitted changes[/yellow]")
    else:
        console.print("[dim]Not a git repository[/dim]")


@app.command("models")
def show_models() -> None:
    """Show model configuration for each step."""
    config = get_config()
    models_service = ModelsService(config.models_file)

    console.print(Panel.fit("Model Configuration", style="bold blue"))
    console.print("")

    # Show override status
    env_override = os.environ.get("CLAUDESPRINT_MODEL_OVERRIDE", "")
    if env_override:
        console.print(f"[yellow]Environment override active: CLAUDESPRINT_MODEL_OVERRIDE={env_override}[/yellow]")
        console.print("")

    if models_service.config.model_override:
        console.print(f"[yellow]Config override active: model_override={models_service.config.model_override}[/yellow]")
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
        default = STEP_DEFAULT_MODELS.get(step, "opus")

        if step in [IssueStep.SELECT_ISSUE, IssueStep.RUN_TESTS, IssueStep.STAGE_CHANGES,
                    IssueStep.COMMIT_CHANGES]:
            notes = "[dim]automated (no AI)[/dim]"
        else:
            notes = "[green]AI required[/green]" if model == "opus" else "[cyan]AI required[/cyan]"

        model_style = "[bold magenta]" if model == "opus" else "[cyan]"
        table.add_row(step_name, f"{model_style}{model}[/]", notes)

    console.print(table)
    console.print("")

    # Special steps
    console.print("[bold]Special Steps:[/bold]")
    special_table = Table(show_header=False, box=None)
    special_table.add_column("Step", style="bold")
    special_table.add_column("Model")

    for special in ["init", "plan"]:
        model = summary.get(special, "opus")
        model_style = "[bold magenta]" if model == "opus" else "[cyan]"
        special_table.add_row(special, f"{model_style}{model}[/]")

    console.print(special_table)
    console.print("")

    # Cost summary
    opus_count = sum(1 for m in summary.values() if m == "opus")
    sonnet_count = sum(1 for m in summary.values() if m == "sonnet")
    console.print(f"[bold]Summary:[/bold] {opus_count} opus steps, {sonnet_count} sonnet steps")


@app.command("notify")
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
    config = get_config()
    service = NotificationService(config.notifications_file)

    if not service.enabled:
        console.print("[yellow]Notifications are not enabled[/yellow]")
        return

    try:
        notif_type = NotificationType(notification_type)
    except ValueError:
        console.print(f"[red]Invalid type: {notification_type}[/red]")
        console.print(f"Valid types: {', '.join(t.value for t in NotificationType)}")
        raise typer.Exit(1)

    service.send_sync(notif_type, message, title)
    console.print("[green]✓ Notification sent[/green]")


@app.command("sprints")
def list_sprints() -> None:
    """List all available sprints."""
    config = get_config()
    sprint_service = SprintService(config.sprints_dir)

    console.print(Panel.fit("Available Sprints", style="bold blue"))
    console.print("")

    sprints = sprint_service.list_sprints()

    if not sprints:
        console.print("[dim]No sprints found.[/dim]")
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
        status = "[green]Complete[/green]" if sprint.is_complete() else "[yellow]In Progress[/yellow]"
        branch = sprint.git_branch or "[dim]none[/dim]"

        table.add_row(sprint.spec_id, status, progress, branch)

    console.print(table)


@app.command("validate")
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
    project_root = get_project_root()
    config = get_config()

    from claudesprint.validation import SprintValidator, CurrentIssueValidator

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
            console.print("[yellow]No active sprint found to validate.[/yellow]")
            return

    # Validate sprint
    if sprint_path and sprint_path.exists():
        console.print(f"[bold]Sprint:[/bold] {sprint_path}")
        validator = SprintValidator(sprint_path)
        result = validator.validate()
        if result.valid:
            console.print("[green]✓ Sprint validation PASSED[/green]")
        else:
            console.print("[red]✗ Sprint validation FAILED[/red]")
            for error in result.errors:
                console.print(f"  [red]• {error}[/red]")
        for warning in result.warnings:
            console.print(f"  [yellow]⚠ {warning}[/yellow]")
        console.print("")

    # Validate current_issue
    current_issue_path = Path(config.current_issue_file)
    if current_issue_path.exists():
        console.print(f"[bold]Current Issue:[/bold] {current_issue_path}")
        validator = CurrentIssueValidator(current_issue_path)
        result = validator.validate()
        if result.valid:
            console.print("[green]✓ Current issue validation PASSED[/green]")
        else:
            console.print("[red]✗ Current issue validation FAILED[/red]")
            for error in result.errors:
                console.print(f"  [red]• {error}[/red]")
        for warning in result.warnings:
            console.print(f"  [yellow]⚠ {warning}[/yellow]")
    else:
        console.print("[dim]No current_issue.json (not mid-issue)[/dim]")


@app.command("reset")
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
    config = get_config()
    issue_service = IssueService(config.project_dir)

    if issue_service.clear_current_issue():
        console.print("[green]✓ Current issue cleared.[/green]")
        console.print("Run 'claudesprint run' to start fresh.")
    else:
        console.print("[yellow]No current issue to clear.[/yellow]")


if __name__ == "__main__":
    app()
