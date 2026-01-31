"""Run command - main workflow execution."""

from pathlib import Path
from typing import Annotated, Optional

import typer

from claudesprint.commands._shared import (
    console,
    get_project_root,
    get_config,
    STYLES,
    success,
    error,
    warning,
    muted,
)
from claudesprint.simple_logs import LogVerbosity


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
    # Lazy import for faster startup
    from claudesprint.services.sprint_service import SprintService

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
    config,
    sprint_path: Path,
    max_iterations: int,
    verbosity: LogVerbosity = LogVerbosity.NORMAL,
    enable_dashboard: bool = False,
) -> None:
    """Run the sprint workflow with console output."""
    # Lazy imports - only load heavy modules when actually running
    from claudesprint.core.claude_runner import ClaudeRunner
    from claudesprint.core.issue_engine import IssueEngine
    from claudesprint.core.sprint_engine import SprintEngine, SprintExitReason
    from claudesprint.events.workflow_event_bus import WorkflowEventBus
    from claudesprint.models.sprint import ResolvedConfig
    from claudesprint.services.configuration_manager import ConfigurationManager
    from claudesprint.services.git_service import GitService
    from claudesprint.services.issue_service import IssueService
    from claudesprint.services.notification_service import NotificationService
    from claudesprint.services.path_service import PathService
    from claudesprint.services.prompt_service import PromptService
    from claudesprint.services.sprint_service import SprintService
    from claudesprint.simple_logs import SimpleLogsOutput
    from claudesprint.utils.duration import format_duration

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
            conversation_log_file=config.conversation_log_file if config.debug_conversations else None,
        )
        return IssueEngine.from_services(
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
    engine = SprintEngine.from_services(
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

    dashboard_server: DashboardServer | None = None
    if enable_dashboard:
        try:
            dashboard_server = DashboardServer(event_bus)
            dashboard_url = dashboard_server.start()
            if dashboard_url:
                console.print(f"[cyan]Dashboard: {dashboard_url}[/cyan]")
        except Exception as e:
            # Dashboard is optional - log and continue without it
            import logging

            logging.getLogger(__name__).debug(f"Dashboard failed to start: {e}")
            dashboard_server = None

    # Run sprint
    try:
        with output:
            result = engine.run(max_iterations=max_iterations)
    finally:
        # Stop dashboard server
        if dashboard_server:
            dashboard_server.stop()

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
