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
from claudesprint.core.claude_runner import ClaudeRunner
from claudesprint.core.issue_engine import IssueEngine
from claudesprint.core.sprint_engine import SprintEngine, SprintExitReason, SprintResult, IssueEngineFactory
from claudesprint.models.config import ClaudesprintConfig
from claudesprint.models.current_issue import IssueStep
from claudesprint.models.sprint import Sprint, Issue, ResolvedConfig
from claudesprint.services.configuration_manager import ConfigurationManager
from claudesprint.services.git_service import GitService
from claudesprint.services.sprint_service import SprintService
from claudesprint.services.issue_service import IssueService
from claudesprint.services.models_service import ModelsService, STEP_DEFAULT_MODELS
from claudesprint.services.notification_service import NotificationService, NotificationType
from claudesprint.services.path_service import PathService
from claudesprint.services.prompt_service import PromptService
from claudesprint.simple_logs import LogVerbosity, SimpleLogsOutput
from claudesprint.utils.duration import format_duration
from claudesprint.utils.process_manager import get_process_manager

app = typer.Typer(
    name="claudesprint",
    help="ClaudeSprint - Autonomous workflow orchestration for AI-driven development",
    no_args_is_help=False,
)

console = Console()


def get_project_root() -> Path:
    """Get the project root directory."""
    discovered = ConfigurationManager.discover_project_root()
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
    # Initialize process manager to install signal handlers for cleanup
    # This ensures Ctrl+C and other signals properly terminate Claude processes
    get_process_manager()

    if version:
        console.print(f"claudesprint version {__version__}")
        raise typer.Exit()

    # If no subcommand, show status
    if ctx.invoked_subcommand is None:
        show_status()


def _get_verbosity(count: int) -> LogVerbosity:
    """Map verbose flag count to LogVerbosity level.

    Args:
        count: Number of -v flags provided.

    Returns:
        Corresponding LogVerbosity level.
    """
    if count == 0:
        return LogVerbosity.NORMAL
    if count == 1:
        return LogVerbosity.VERBOSE
    return LogVerbosity.DEBUG


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
    verbose: Annotated[
        int,
        typer.Option("-v", "--verbose", count=True, help="Increase verbosity (-v, -vv, -vvv)"),
    ] = 0,
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

    _run_sprint_console(project_root, config, sprint_path, max_iterations, _get_verbosity(verbose))


def _run_sprint_console(
    project_root: Path,
    config: ClaudesprintConfig,
    sprint_path: Path,
    max_iterations: int,
    verbosity: LogVerbosity = LogVerbosity.NORMAL,
) -> None:
    """Run the sprint workflow with console output."""
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

    # Pre-flight git check: warn if working directory has uncommitted changes
    git_service = GitService(project_root, git_timeout=config.git_timeout)
    git_status = git_service.get_status()
    baseline_dirty_path = Path(config.project_dir) / "baseline_dirty.json"

    if git_status.is_repo and git_status.dirty:
        dirty_files = git_service.get_dirty_files()
        console.print("[yellow]Warning: Working directory has uncommitted changes:[/yellow]")
        for f in sorted(dirty_files)[:10]:
            console.print(f"  [dim]{f}[/dim]")
        if len(dirty_files) > 10:
            console.print(f"  [dim]... and {len(dirty_files) - 10} more[/dim]")
        console.print("")
        console.print("[yellow]These files will be excluded from agent commits.[/yellow]")
        console.print("Recommended: stash or commit your changes first:")
        console.print("  [dim]git stash push -m 'WIP before claudesprint'[/dim]")
        console.print("")

        if not typer.confirm("Continue anyway?", default=False):
            console.print("[dim]Aborted. Commit or stash your changes and try again.[/dim]")
            raise typer.Exit(0)

        # Save baseline dirty files for agent to reference
        git_service.save_baseline_dirty_files(baseline_dirty_path)
        console.print(f"[dim]Baseline saved to {baseline_dirty_path}[/dim]")
        console.print("")
    else:
        # Clean state - remove any stale baseline file
        if baseline_dirty_path.exists():
            baseline_dirty_path.unlink()

    # Create output handler with verbosity level
    output = SimpleLogsOutput(console, verbosity=verbosity)
    stats = sprint.get_stats()
    output.set_sprint_info(
        sprint.spec_id,
        stats["total"],
        stats["completed"],
    )

    # Create all services for dependency injection
    issue_service = IssueService(config.project_dir)
    cm = ConfigurationManager(project_root)
    notification_service = NotificationService.from_config_manager(
        cm, http_timeout=config.http_timeout
    )
    path_service = PathService(project_root)
    prompt_service = PromptService(path_service, project_root)

    # Create ClaudeRunner for sprint-level operations
    claude_runner = ClaudeRunner(
        project_root=project_root,
        timeout=config.claude_timeout,
        kill_timeout=config.kill_timeout,
        min_output_length=config.min_output_length,
        conversation_log_file=config.conversation_log_file if config.debug_conversations else None,
    )

    # Create IssueEngine factory that closes over shared dependencies
    def issue_engine_factory(resolved_config: ResolvedConfig) -> IssueEngine:
        """Factory function to create IssueEngine instances."""
        # Create a ClaudeRunner for this issue engine
        issue_claude_runner = ClaudeRunner(
            project_root=project_root,
            timeout=config.claude_timeout,
            kill_timeout=config.kill_timeout,
            min_output_length=config.min_output_length,
            conversation_log_file=config.conversation_log_file if config.debug_conversations else None,
        )
        return IssueEngine(
            config=config,
            execution_config=resolved_config,
            issue_service=issue_service,
            sprint_service=sprint_service,
            notification_service=notification_service,
            prompt_service=prompt_service,
            claude_runner=issue_claude_runner,
        )

    # Create SprintEngine with all dependencies
    engine = SprintEngine(
        sprint_path=sprint_path,
        config=config,
        git_service=git_service,
        sprint_service=sprint_service,
        issue_service=issue_service,
        notification_service=notification_service,
        prompt_service=prompt_service,
        claude_runner=claude_runner,
        issue_engine_factory=issue_engine_factory,
    )

    # Set up callbacks
    def on_issue_start(issue: Issue) -> None:
        output.set_issue(issue.id, issue.title)

    def on_issue_complete(issue: Issue) -> None:
        output.on_issue_complete(issue.id)

    def on_sprint_complete(result: SprintResult) -> None:
        # Sprint complete message is now shown in the final output
        pass

    def configure_issue_engine(issue_engine: IssueEngine) -> None:
        """Wire up output callbacks to the issue engine."""
        issue_engine.on_step_start = output.on_step_start
        issue_engine.on_step_complete = output.on_step_complete
        issue_engine.on_step_skip = output.on_step_skip
        # Pass max_retry for context in failure logging
        issue_engine.on_step_failure = lambda s, r: output.on_step_failure(s, r, config.max_retry)
        # Wire subprocess callbacks for agent output
        issue_engine.on_subprocess_start = output.on_subprocess_start
        issue_engine.on_subprocess_output = output.on_subprocess_output
        issue_engine.on_subprocess_end = output.on_subprocess_end
        # New callbacks for iteration tracking and routing visibility
        issue_engine.on_routing_signal = output.on_routing_signal
        issue_engine.on_issue_iteration = output.on_issue_iteration

    engine.on_issue_start = on_issue_start
    engine.on_issue_complete = on_issue_complete
    engine.on_sprint_complete = on_sprint_complete
    engine.issue_engine_configurator = configure_issue_engine

    # Wire up the new outer loop callbacks
    engine.on_sprint_iteration = output.on_sprint_iteration
    engine.on_selecting_issue = output.on_selecting_issue
    engine.on_output = output.on_output

    # Run sprint
    with output:
        result = engine.run(max_iterations=max_iterations)

    console.print("")
    if result.exit_reason == SprintExitReason.COMPLETED:
        # Print the instructions message (contains PR submission info)
        if result.message and "Manual PR submission" in result.message:
            console.print(result.message)
        else:
            console.print(
                f"[bold green]SPRINT COMPLETE[/bold green] - "
                f"Issues completed: {result.issues_completed}, "
                f"Runtime: {format_duration(result.elapsed_seconds)}"
            )
    elif result.exit_reason == SprintExitReason.ERROR:
        console.print(f"[bold red]Error: {result.message}[/bold red]")
        if result.error:
            console.print(f"[red]{result.error}[/red]")
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

    Creates a new sprint.json in .claudesprint/sprints/<spec_id>/ and invokes
    the init agent to populate it with issues from the spec.
    """
    project_root = get_project_root()
    config = get_config()

    # Find spec file
    spec_path = Path(spec)
    if not spec_path.exists():
        # Try looking in .claudesprint/specs/
        spec_path = Path(config.specs_dir) / spec
        if not spec_path.exists():
            # Try adding .md extension
            spec_path = Path(config.specs_dir) / f"{spec}.md"

    if not spec_path.exists():
        console.print(f"[red]Spec file not found: {spec}[/red]")
        console.print("Looked in:")
        console.print(f"  • {spec}")
        console.print(f"  • .claudesprint/specs/{spec}")
        console.print(f"  • .claudesprint/specs/{spec}.md")
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
    # Load prompt from package resources via PromptService
    path_service = PathService(project_root=project_root)
    prompt_service = PromptService(path_service, project_root=project_root)
    try:
        prompt_content = prompt_service.get_prompt_content("init")
    except FileNotFoundError:
        console.print("[red]Error: PROMPT_init.xml.j2 not found in package[/red]")
        raise typer.Exit(1)

    # Get model for init step
    cm = ConfigurationManager(project_root)
    models_service = ModelsService.from_config_manager(cm)
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
        kill_timeout=config.kill_timeout,
        min_output_length=config.min_output_length,
        conversation_log_file=(
            config.conversation_log_file if debug_conversations else None
        ),
    )
    result = runner.run_with_content(
        prompt_content,
        source_name="PROMPT_init.xml.j2",
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

    # Load prompt from package resources via PromptService
    path_service = PathService(project_root=project_root)
    prompt_service = PromptService(path_service, project_root=project_root)
    try:
        prompt_content = prompt_service.get_prompt_content("plan")
    except FileNotFoundError:
        console.print("[red]Error: PROMPT_plan.xml.j2 not found in package[/red]")
        raise typer.Exit(1)

    # Get model for plan step
    cm = ConfigurationManager(project_root)
    models_service = ModelsService.from_config_manager(cm)
    model = models_service.get_model_for_special_step("plan")

    console.print(f"[cyan]▶ Running planner (model: {model})...[/cyan]")

    from claudesprint.core.claude_runner import ClaudeRunner

    runner = ClaudeRunner(
        project_root,
        config.claude_timeout,
        kill_timeout=config.kill_timeout,
        min_output_length=config.min_output_length,
        conversation_log_file=(
            config.conversation_log_file if debug_conversations else None
        ),
    )
    result = runner.run_with_content(
        prompt_content,
        source_name="PROMPT_plan.xml.j2",
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
    project_root = get_project_root()
    cm = ConfigurationManager(project_root)
    models_service = ModelsService.from_config_manager(cm)
    project_config = cm.project

    console.print(Panel.fit("Model Configuration", style="bold blue"))
    console.print("")

    # Show override status
    env_override = os.environ.get("CLAUDESPRINT_MODEL_OVERRIDE", "")
    if env_override:
        console.print(f"[yellow]Environment override active: CLAUDESPRINT_MODEL_OVERRIDE={env_override}[/yellow]")
        console.print("")

    if project_config.models.model_override:
        console.print(f"[yellow]Config override active: model_override={project_config.models.model_override}[/yellow]")
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

        if step in [IssueStep.RUN_TESTS, IssueStep.STAGE_CHANGES, IssueStep.COMMIT_CHANGES]:
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
    project_root = get_project_root()
    cm = ConfigurationManager(project_root)
    service = NotificationService.from_config_manager(
        cm, http_timeout=config.http_timeout
    )

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


@app.command("initrepo")
def init_repo(
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Reinitialize even if .claudesprint/ exists"),
    ] = False,
    skip_hooks: Annotated[
        bool,
        typer.Option("--skip-hooks", help="Skip injecting Claude hooks into .claude/settings.json"),
    ] = False,
) -> None:
    """Initialize .claudesprint/ directory in the current repository.

    Creates the following structure:
      .claudesprint/
        state/          - Session state files
        prompts/        - Custom prompt overrides
          README.md     - Documentation for prompt overrides

    Also adds .claudesprint/ to .gitignore and injects ClaudeSprint hooks
    into .claude/settings.json (unless --skip-hooks is specified).
    """
    from claudesprint.services.init_repo_service import InitRepoService

    project_root = Path.cwd()
    service = InitRepoService(project_root)

    result = service.init(force=force, inject_hooks=not skip_hooks)

    # Show warnings first
    for warning in result.warnings:
        console.print(f"[yellow]Warning: {warning}[/yellow]")

    if not result.success:
        console.print(f"[red]Error: {result.error}[/red]")
        raise typer.Exit(1)

    # Show what was created
    console.print("[green]✓ Initialized .claudesprint/ directory[/green]")
    console.print("")

    if result.created_dirs:
        console.print("[bold]Created directories:[/bold]")
        for dir_path in result.created_dirs:
            console.print(f"  {dir_path}")

    if result.created_files:
        console.print("[bold]Created/updated files:[/bold]")
        for file_path in result.created_files:
            console.print(f"  {file_path}")

    # Show hooks status
    if not skip_hooks:
        console.print("")
        if result.hooks_injected:
            console.print("[green]✓ Claude hooks injected into .claude/settings.json[/green]")
            if result.hooks_backup_path:
                console.print(f"  [dim]Backup created: {result.hooks_backup_path}[/dim]")
        else:
            console.print("[yellow]⚠ Claude hooks were not injected[/yellow]")

    console.print("")
    console.print("[bold]Next steps:[/bold]")
    console.print("  1. Create a spec file in .claudesprint/specs/")
    console.print("  2. Run: claudesprint init --spec <spec_file>")
    console.print("  3. Run: claudesprint run")


# Config command group for global configuration
config_app = typer.Typer(
    name="config",
    help="Manage global user configuration",
)
app.add_typer(config_app, name="config")


@config_app.command("path")
def config_path() -> None:
    """Show the global config file location."""
    config_file = ConfigurationManager.get_default_global_config_path()
    console.print(f"[bold]Config file:[/bold] {config_file}")
    if config_file.exists():
        console.print("[green]✓ File exists[/green]")
    else:
        console.print("[dim]File does not exist. Run 'claudesprint config init' to create it.[/dim]")


@config_app.command("init")
def config_init(
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Overwrite existing config file"),
    ] = False,
) -> None:
    """Create the default global config file."""
    from claudesprint.services.global_config_service import DEFAULT_CONFIG_TOML

    config_file = ConfigurationManager.get_default_global_config_path()

    if config_file.exists() and not force:
        console.print(f"[yellow]Config file already exists: {config_file}[/yellow]")
        console.print("Use --force to overwrite.")
        raise typer.Exit(1)

    try:
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(DEFAULT_CONFIG_TOML)
        console.print(f"[green]✓ Created config file: {config_file}[/green]")
    except OSError:
        console.print("[red]✗ Failed to create config file[/red]")
        raise typer.Exit(1)


@config_app.command("show")
def config_show() -> None:
    """Display current global configuration."""
    config_file = ConfigurationManager.get_default_global_config_path()
    cm = ConfigurationManager()

    if not config_file.exists():
        console.print(f"[yellow]Config file not found: {config_file}[/yellow]")
        console.print("Run 'claudesprint config init' to create it.")
        console.print("")
        console.print("[dim]Using built-in defaults:[/dim]")

    config = cm.global_config
    console.print(Panel.fit("Global Configuration", style="bold blue"))
    console.print("")

    # Display as formatted sections
    console.print("[bold]\\[defaults][/bold]")
    console.print(f"  model = {config.defaults.model!r}")
    console.print(f"  max_retry = {config.defaults.max_retry}")
    console.print(f"  claude_timeout = {config.defaults.claude_timeout}")
    console.print(f"  total_timeout = {config.defaults.total_timeout}")
    console.print("")

    console.print("[bold]\\[rate_limiting][/bold]")
    console.print(f"  retries = {config.rate_limiting.retries}")
    console.print(f"  base_wait = {config.rate_limiting.base_wait}")
    console.print(f"  max_wait = {config.rate_limiting.max_wait}")
    console.print("")

    console.print("[bold]\\[heartbeat][/bold]")
    console.print(f"  enabled = {str(config.heartbeat.enabled).lower()}")
    console.print(f"  timeout = {config.heartbeat.timeout}")
    console.print("")

    console.print("[bold]\\[debug][/bold]")
    console.print(f"  conversations = {str(config.debug.conversations).lower()}")


@config_app.command("edit")
def config_edit() -> None:
    """Open global config file in $EDITOR."""
    import subprocess
    from claudesprint.services.global_config_service import DEFAULT_CONFIG_TOML

    config_file = ConfigurationManager.get_default_global_config_path()

    if not config_file.exists():
        console.print(f"[yellow]Config file not found: {config_file}[/yellow]")
        console.print("Creating default config file...")
        try:
            config_file.parent.mkdir(parents=True, exist_ok=True)
            config_file.write_text(DEFAULT_CONFIG_TOML)
            console.print(f"[green]✓ Created: {config_file}[/green]")
        except OSError:
            console.print("[red]✗ Failed to create config file[/red]")
            raise typer.Exit(1)

    editor = os.environ.get("EDITOR", os.environ.get("VISUAL", "vim"))
    try:
        subprocess.run([editor, str(config_file)], check=True)
    except FileNotFoundError:
        console.print(f"[red]Editor not found: {editor}[/red]")
        console.print("Set the EDITOR environment variable to your preferred editor.")
        raise typer.Exit(1)
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Editor exited with error: {e.returncode}[/red]")
        raise typer.Exit(1)


@app.command("doctor")
def doctor(
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Show detailed information"),
    ] = False,
    fix: Annotated[
        bool,
        typer.Option("--fix", help="Attempt to auto-fix issues"),
    ] = False,
) -> None:
    """Diagnose environment and verify dependencies.

    Checks that all required dependencies are installed and configured:
    - Python version (3.10+ required)
    - Required Python packages (rich, typer, pydantic, httpx, jinja2)
    - Claude CLI installed and accessible
    - Project structure (.claudesprint/ directory)
    - Optional dependencies (agent-browser, npm)
    """
    from claudesprint.services.health_check_service import (
        CheckStatus,
        HealthCheckService,
    )

    project_root = get_project_root()
    config = get_config()
    service = HealthCheckService(
        project_root,
        version_check_timeout=config.version_check_timeout,
        install_timeout=config.install_timeout,
    )

    console.print(Panel.fit("ClaudeSprint Doctor", style="bold blue"))
    console.print("")

    # Run all checks
    report = service.run_all_checks(verbose=verbose)

    # Display results
    for check in report.checks:
        if check.status == CheckStatus.OK:
            icon = "[green]✓[/green]"
            message = check.message
        elif check.status == CheckStatus.WARNING:
            icon = "[yellow]⚠[/yellow]"
            message = f"[yellow]{check.message}[/yellow]"
        else:
            icon = "[red]✗[/red]"
            message = f"[red]{check.message}[/red]"

        console.print(f"  {icon} {check.name}: {message}")

        if verbose and check.details:
            for line in check.details.split("\n"):
                console.print(f"      [dim]{line}[/dim]")

    console.print("")

    # Summary
    if report.is_healthy:
        if report.has_warnings:
            console.print(
                f"[green]✓ All required checks passed[/green] "
                f"[yellow]({report.warning_count} warning{'s' if report.warning_count > 1 else ''})[/yellow]"
            )
        else:
            console.print("[green]✓ All checks passed[/green]")
    else:
        console.print(
            f"[red]✗ {report.error_count} error{'s' if report.error_count > 1 else ''} found[/red]"
        )

    # Handle --fix flag
    if fix and report.fixable_issues:
        console.print("")
        console.print("[bold]Attempting auto-fixes...[/bold]")
        console.print("")

        for issue in report.fixable_issues:
            if issue.fix_command:
                console.print(f"  Running: [cyan]{issue.fix_command}[/cyan]")
                success = service.attempt_fix(
                    issue,
                    on_output=lambda line: console.print(f"    {line}"),
                )
                if success:
                    console.print("    [green]✓ Fixed[/green]")
                else:
                    console.print("    [red]✗ Failed - run manually[/red]")

        console.print("")
        console.print("Re-run [cyan]claudesprint doctor[/cyan] to verify fixes.")
    elif not fix and report.fixable_issues:
        console.print("")
        console.print(
            f"[dim]Tip: Run [cyan]claudesprint doctor --fix[/cyan] to attempt auto-fixes "
            f"for {len(report.fixable_issues)} issue{'s' if len(report.fixable_issues) > 1 else ''}[/dim]"
        )

    if not report.is_healthy:
        raise typer.Exit(1)


@app.command("hook")
def run_hook(
    hook_type: Annotated[
        str,
        typer.Option("--type", "-t", help="Hook type: server-guard, browser-guard, autonomous-continue"),
    ],
) -> None:
    """Execute a Claude hook handler.

    This command is called by Claude Code hooks configured in .claude/settings.json.
    It reads JSON input from stdin and exits with:
    - 0: Allow the operation
    - 2: Block the operation

    Example:
        echo '{"tool_input":{"command":"npm test"}}' | claudesprint hook --type server-guard
    """
    from claudesprint.services.session_state import is_session_active

    # Early exit if no active session - allow manual Claude usage
    if not is_session_active():
        raise typer.Exit(0)

    from claudesprint.services.claude_hook_service import (
        ClaudeHookService,
        HookInput,
        HookType,
    )

    # Validate hook type
    try:
        hook_type_enum = HookType(hook_type)
    except ValueError:
        valid_types = ", ".join(t.value for t in list(HookType))
        console.print(f"[red]Invalid hook type: {hook_type}[/red]", style="red")
        console.print(f"Valid types: {valid_types}")
        raise typer.Exit(1)

    # Parse input from stdin
    hook_input = HookInput.from_stdin()

    # Execute hook
    service = ClaudeHookService()
    result = service.execute_hook(hook_type_enum, hook_input)

    # Exit with appropriate code
    raise typer.Exit(result.value)


if __name__ == "__main__":
    app()
