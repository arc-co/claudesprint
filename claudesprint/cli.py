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
from claudesprint.events.workflow_event_bus import WorkflowEventBus
from claudesprint.models.config import ClaudesprintConfig
from claudesprint.models.current_issue import IssueStep
from claudesprint.models.sprint import Sprint, ResolvedConfig
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
from claudesprint.utils.styles import (
    COLORS,
    STYLES,
    ConsoleThrobber,
    success,
    error,
    warning,
    running,
    subprocess_line,
    status_badge,
    model_badge,
    muted,
    info,
    success_icon,
    error_icon,
    warning_icon,
)

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
    dashboard: Annotated[
        bool,
        typer.Option("--dashboard", help="Start the web dashboard for real-time monitoring"),
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
            console.print(warning("No active sprint found."))
            console.print("")
            console.print("Create a sprint with:")
            console.print("  claudesprint init --spec <spec_file>")
            console.print("")
            console.print("Or specify a sprint:")
            console.print("  claudesprint run --spec SPEC_01")
            console.print("  claudesprint run --sprint path/to/sprint.json")
            raise typer.Exit(1)

    _run_sprint_console(project_root, config, sprint_path, max_iterations, _get_verbosity(verbose), dashboard)


def _run_sprint_console(
    project_root: Path,
    config: ClaudesprintConfig,
    sprint_path: Path,
    max_iterations: int,
    verbosity: LogVerbosity = LogVerbosity.NORMAL,
    enable_dashboard: bool = False,
) -> None:
    """Run the sprint workflow with console output."""
    if not sprint_path.exists():
        console.print(error(f"Sprint file not found: {sprint_path}"))
        console.print("Run 'claudesprint init --spec <spec_file>' to create a sprint.")
        raise typer.Exit(1)

    # Load sprint for initial stats
    sprint_service = SprintService(sprint_path.parent.parent)
    sprint = sprint_service.read_sprint(sprint_path)
    if not sprint:
        console.print(error(f"Failed to parse sprint file: {sprint_path}"))
        raise typer.Exit(1)

    # Pre-flight git check: warn if working directory has uncommitted changes
    git_service = GitService(project_root, git_timeout=config.git_timeout)
    git_status = git_service.get_status()
    baseline_dirty_path = Path(config.project_dir) / "baseline_dirty.json"

    if git_status.is_repo and git_status.dirty:
        dirty_files = git_service.get_dirty_files()
        console.print(warning("Working directory has uncommitted changes:"))
        for f in sorted(dirty_files)[:10]:
            console.print(f"  {muted(f)}")
        if len(dirty_files) > 10:
            console.print(f"  {muted(f'... and {len(dirty_files) - 10} more')}")
        console.print("")
        console.print(warning("These files will be excluded from agent commits."))
        console.print("Recommended: stash or commit your changes first:")
        console.print(f"  {muted('git stash push -m \"WIP before claudesprint\"')}")
        console.print("")

        if not typer.confirm("Continue anyway?", default=False):
            console.print(muted("Aborted. Commit or stash your changes and try again."))
            raise typer.Exit(0)

        # Save baseline dirty files for agent to reference
        git_service.save_baseline_dirty_files(baseline_dirty_path)
        console.print(muted(f"Baseline saved to {baseline_dirty_path}"))
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

    # Create shared event bus for workflow events
    event_bus = WorkflowEventBus()

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
            event_bus=event_bus,
            config_manager=cm,
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
        event_bus=event_bus,
    )

    # Connect event bus to log output via subscriber
    from claudesprint.events.logs_subscriber import LogsEventSubscriber

    logs_subscriber = LogsEventSubscriber(output, event_bus)
    logs_subscriber.connect()

    # Start dashboard server (only if explicitly enabled)
    from claudesprint.dashboard.server import DashboardServer

    dashboard: DashboardServer | None = None
    if enable_dashboard:
        try:
            dashboard = DashboardServer(event_bus)
            dashboard_url = dashboard.start()
            if dashboard_url:
                console.print(f"[cyan]Dashboard: {dashboard_url}[/cyan]")
        except Exception as e:
            # Dashboard is optional - log and continue without it
            import logging

            logging.getLogger(__name__).debug(f"Dashboard failed to start: {e}")
            dashboard = None

    # Run sprint
    try:
        with output:
            result = engine.run(max_iterations=max_iterations)
    finally:
        # Stop dashboard server
        if dashboard:
            dashboard.stop()

    # Disconnect subscriber after sprint completes
    logs_subscriber.disconnect()

    console.print("")
    if result.exit_reason == SprintExitReason.COMPLETED:
        # Print the instructions message (contains PR submission info)
        if result.message and "Manual PR submission" in result.message:
            console.print(result.message)
        else:
            console.print(
                f"{success('SPRINT COMPLETE')} - "
                f"Issues completed: {result.issues_completed}, "
                f"Runtime: {format_duration(result.elapsed_seconds)}"
            )
    elif result.exit_reason == SprintExitReason.ERROR:
        console.print(f"[{STYLES.STATUS_ERROR}]Error: {result.message}[/{STYLES.STATUS_ERROR}]")
        if result.error:
            console.print(error(result.error))
        raise typer.Exit(1)
    else:
        console.print(warning(f"Exit: {result.exit_reason.value} - {result.message}"))


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
        console.print(error(f"Spec file not found: {spec}"))
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
        console.print(error("Failed to create sprint"))
        raise typer.Exit(1)

    console.print(success(f"Sprint skeleton created: {sprint_path}"))
    console.print(f"  {muted('Spec ID:')} {sprint.spec_id}")
    console.print(f"  {muted('Spec file:')} {sprint.spec_file}")
    console.print(f"  {muted('Branch:')} {sprint.git_branch}")
    console.print("")

    # Now invoke the init agent to populate the sprint with issues
    # Load prompt from package resources via PromptService
    path_service = PathService(project_root=project_root)
    prompt_service = PromptService(path_service, project_root=project_root)
    try:
        prompt_content = prompt_service.get_prompt_content("init")
    except FileNotFoundError:
        console.print(error("PROMPT_init.xml.j2 not found in package"))
        raise typer.Exit(1)

    # Get model for init step
    cm = ConfigurationManager(project_root)
    models_service = ModelsService.from_config_manager(cm)
    model = models_service.get_model_for_special_step("init")

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

    # Start throbber while generating sprint from spec
    throbber = ConsoleThrobber(console)
    throbber.start(f"Generating sprint from spec (model: {model})")
    first_output_received = [False]

    def on_output_with_throbber(line: str) -> None:
        """Handle output, stopping throbber on first line."""
        if not first_output_received[0]:
            first_output_received[0] = True
            throbber.stop()
        console.print(subprocess_line(line))

    result = runner.run_with_content(
        prompt_content,
        source_name="PROMPT_init.xml.j2",
        on_output=on_output_with_throbber,
        model=model,
        context=context,
    )

    # Ensure throbber is stopped even if no output was received
    if throbber.is_running:
        throbber.stop()

    if result.exit_code == 0:
        console.print("")
        console.print(success("Sprint initialization complete."))
        console.print(f"Run 'claudesprint run --spec {sprint.spec_id}' to start the sprint workflow.")
    else:
        console.print(error(f"Init agent failed (exit code: {result.exit_code})"))
        if result.rate_limited:
            console.print(warning("Rate limit detected. Please wait and try again."))
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
        console.print(error("PROMPT_plan.xml.j2 not found in package"))
        raise typer.Exit(1)

    # Get model for plan step
    cm = ConfigurationManager(project_root)
    models_service = ModelsService.from_config_manager(cm)
    model = models_service.get_model_for_special_step("plan")

    console.print(running(f"Running planner (model: {model})..."))

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
        on_output=lambda line: console.print(subprocess_line(line)),
        model=model,
    )

    if result.exit_code == 0:
        console.print(success("Planning complete."))
    else:
        console.print(error(f"Planning failed (exit code: {result.exit_code})"))
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


@app.command("models")
def show_models() -> None:
    """Show model configuration for each step."""
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
        default = STEP_DEFAULT_MODELS.get(step, "opus")

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


@app.command("sprints")
def list_sprints() -> None:
    """List all available sprints."""
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
        console.print(success("Current issue cleared."))
        console.print("Run 'claudesprint run' to start fresh.")
    else:
        console.print(warning("No current issue to clear."))


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
    for warn in result.warnings:
        console.print(warning(f"Warning: {warn}"))

    if not result.success:
        console.print(error(f"Error: {result.error}"))
        raise typer.Exit(1)

    # Show what was created
    console.print(success("Initialized .claudesprint/ directory"))
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
            console.print(success("Claude hooks injected into .claude/settings.json"))
            if result.hooks_backup_path:
                console.print(f"  {muted(f'Backup created: {result.hooks_backup_path}')}")
        else:
            console.print(warning("Claude hooks were not injected"))

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
        console.print(success("File exists"))
    else:
        console.print(muted("File does not exist. Run 'claudesprint config init' to create it."))


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
        console.print(warning(f"Config file already exists: {config_file}"))
        console.print("Use --force to overwrite.")
        raise typer.Exit(1)

    try:
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(DEFAULT_CONFIG_TOML)
        console.print(success(f"Created config file: {config_file}"))
    except OSError:
        console.print(error("Failed to create config file"))
        raise typer.Exit(1)


@config_app.command("show")
def config_show() -> None:
    """Display current global configuration."""
    config_file = ConfigurationManager.get_default_global_config_path()
    cm = ConfigurationManager()

    if not config_file.exists():
        console.print(warning(f"Config file not found: {config_file}"))
        console.print("Run 'claudesprint config init' to create it.")
        console.print("")
        console.print(muted("Using built-in defaults:"))

    config = cm.global_config
    console.print(Panel.fit("Global Configuration", style=STYLES.PANEL_HEADER))
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
        console.print(warning(f"Config file not found: {config_file}"))
        console.print("Creating default config file...")
        try:
            config_file.parent.mkdir(parents=True, exist_ok=True)
            config_file.write_text(DEFAULT_CONFIG_TOML)
            console.print(success(f"Created: {config_file}"))
        except OSError:
            console.print(error("Failed to create config file"))
            raise typer.Exit(1)

    editor = os.environ.get("EDITOR", os.environ.get("VISUAL", "vim"))
    try:
        subprocess.run([editor, str(config_file)], check=True)
    except FileNotFoundError:
        console.print(error(f"Editor not found: {editor}"))
        console.print("Set the EDITOR environment variable to your preferred editor.")
        raise typer.Exit(1)
    except subprocess.CalledProcessError as e:
        console.print(error(f"Editor exited with error: {e.returncode}"))
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

    console.print(Panel.fit("ClaudeSprint Doctor", style=STYLES.PANEL_HEADER))
    console.print("")

    # Run all checks
    report = service.run_all_checks(verbose=verbose)

    # Display results
    for check in report.checks:
        if check.status == CheckStatus.OK:
            icon = success_icon()
            message = check.message
        elif check.status == CheckStatus.WARNING:
            icon = warning_icon()
            message = f"[{COLORS.WARNING}]{check.message}[/{COLORS.WARNING}]"
        else:
            icon = error_icon()
            message = f"[{COLORS.ERROR}]{check.message}[/{COLORS.ERROR}]"

        console.print(f"  {icon} {check.name}: {message}")

        if verbose and check.details:
            for line in check.details.split("\n"):
                console.print(f"      {muted(line)}")

    console.print("")

    # Summary
    if report.is_healthy:
        if report.has_warnings:
            warn_suffix = "s" if report.warning_count > 1 else ""
            console.print(
                f"{success('All required checks passed')} "
                f"{warning(f'({report.warning_count} warning{warn_suffix})')}"
            )
        else:
            console.print(success("All checks passed"))
    else:
        err_suffix = "s" if report.error_count > 1 else ""
        console.print(error(f"{report.error_count} error{err_suffix} found"))

    # Handle --fix flag
    if fix and report.fixable_issues:
        console.print("")
        console.print("[bold]Attempting auto-fixes...[/bold]")
        console.print("")

        for issue in report.fixable_issues:
            if issue.fix_command:
                console.print(f"  Running: {info(issue.fix_command)}")
                fix_success = service.attempt_fix(
                    issue,
                    on_output=lambda line: console.print(f"    {line}"),
                )
                if fix_success:
                    console.print(f"    {success('Fixed')}")
                else:
                    console.print(f"    {error('Failed - run manually')}")

        console.print("")
        console.print(f"Re-run {info('claudesprint doctor')} to verify fixes.")
    elif not fix and report.fixable_issues:
        console.print("")
        console.print(
            muted(
                f"Tip: Run {info('claudesprint doctor --fix')} to attempt auto-fixes "
                f"for {len(report.fixable_issues)} issue{'s' if len(report.fixable_issues) > 1 else ''}"
            )
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
        console.print(error(f"Invalid hook type: {hook_type}"))
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
