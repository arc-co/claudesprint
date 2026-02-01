"""Quickstart command for single-command project setup."""

from pathlib import Path
from typing import Annotated

import typer
from rich.panel import Panel

from claudesprint.commands._shared import (
    console,
    get_config,
    STYLES,
    error,
    warning,
    info,
    success_icon,
    error_icon,
    warning_icon,
)


def quickstart(
    template: Annotated[
        str | None,
        typer.Option("--template", "-t", help="Template to use (web-application, cli-tool, api-service, minimal)"),
    ] = None,
    name: Annotated[
        str | None,
        typer.Option("--name", "-n", help="Project name"),
    ] = None,
    description: Annotated[
        str | None,
        typer.Option("--description", "-d", help="Project description"),
    ] = None,
    non_interactive: Annotated[
        bool,
        typer.Option("--non-interactive", help="Use defaults without prompting (for CI)"),
    ] = False,
    skip_run: Annotated[
        bool,
        typer.Option("--skip-run", help="Don't offer to start run after setup"),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Reinitialize even if .claudesprint/ exists"),
    ] = False,
) -> None:
    """Quick start a new ClaudeSprint project in one command.

    This command guides you through:
    1. Checking prerequisites (Python, Claude CLI, auth)
    2. Initializing .claudesprint/ directory
    3. Creating a project spec from a template
    4. Initializing the sprint from the spec
    5. Optionally starting the run workflow
    """
    # Lazy imports for faster startup
    from claudesprint.services.health_check_service import HealthCheckService, CheckStatus
    from claudesprint.services.init_repo_service import InitRepoService
    from claudesprint.services.spec_service import SpecService

    project_root = Path.cwd()

    console.print(Panel.fit("ClaudeSprint Quickstart", style=STYLES.PANEL_HEADER))
    console.print("")

    # Step 1: Check prerequisites
    console.print("[bold][1/4] Checking prerequisites...[/bold]")

    health_service = HealthCheckService(project_root)

    # Check Python version
    python_result = health_service.check_python_version()
    if python_result.status == CheckStatus.OK:
        console.print(f"  {success_icon()} {python_result.message}")
    else:
        console.print(f"  {error_icon()} {python_result.message}")
        raise typer.Exit(1)

    # Check Claude CLI
    claude_result = health_service.check_claude_cli()
    if claude_result.status == CheckStatus.OK:
        console.print(f"  {success_icon()} Claude CLI installed")
    elif claude_result.status == CheckStatus.ERROR:
        console.print(f"  {error_icon()} {claude_result.message}")
        console.print("")
        console.print(error("Claude CLI is required. Install from:"))
        console.print(info("  https://docs.anthropic.com/en/docs/claude-code"))
        raise typer.Exit(1)
    else:
        console.print(f"  {warning_icon()} {claude_result.message}")

    # Check Claude auth
    auth_result = health_service.check_claude_auth()
    if auth_result.status == CheckStatus.OK:
        console.print(f"  {success_icon()} Claude CLI authenticated")
    elif auth_result.status == CheckStatus.ERROR:
        console.print(f"  {error_icon()} {auth_result.message}")
        console.print("")
        console.print(error("Claude CLI is not authenticated."))
        console.print(f"Run: {info('claude login')}")
        raise typer.Exit(1)
    else:
        console.print(f"  {warning_icon()} {auth_result.message}")

    console.print("")

    # Step 2: Initialize project
    console.print("[bold][2/4] Initializing project...[/bold]")

    init_service = InitRepoService(project_root)

    if init_service.exists() and not force:
        console.print(f"  {success_icon()} Project already initialized")
    else:
        result = init_service.init(force=force, inject_hooks=True)
        if not result.success:
            console.print(f"  {error_icon()} {result.error}")
            raise typer.Exit(1)
        console.print(f"  {success_icon()} Created .claudesprint/ directory")
        if result.hooks_injected:
            console.print(f"  {success_icon()} Claude hooks configured")

    console.print("")

    # Step 3: Create spec
    console.print("[bold][3/4] Creating project spec...[/bold]")

    spec_service = SpecService(project_root)
    templates = spec_service.get_templates()

    # Get project name
    if name is None:
        if non_interactive:
            # Use directory name as default
            name = project_root.name
            console.print(f"  Using directory name: {name}")
        else:
            name = typer.prompt("  Project name", default=project_root.name)

    # Get template
    if template is None:
        if non_interactive:
            template = "minimal"
            console.print(f"  Using template: {template}")
        else:
            console.print("")
            console.print("  [bold]Available templates:[/bold]")
            for i, t in enumerate(templates, 1):
                console.print(f"    [{i}] {t.display_name} - {t.description}")
            console.print("")

            while True:
                choice = typer.prompt(f"  Select template [1-{len(templates)}]", default="1")
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(templates):
                        template = templates[idx].name
                        break
                    console.print(warning(f"  Please enter a number between 1 and {len(templates)}"))
                except ValueError:
                    # Check if user typed template name directly
                    for t in templates:
                        if t.name == choice or t.display_name.lower() == choice.lower():
                            template = t.name
                            break
                    else:
                        console.print(warning("  Invalid selection."))
                        continue
                    break
    else:
        # Validate template exists
        valid_templates = [t.name for t in templates]
        if template not in valid_templates:
            console.print(f"  {error_icon()} Unknown template: {template}")
            console.print(f"  Available: {', '.join(valid_templates)}")
            raise typer.Exit(1)

    # Get description
    if description is None:
        if non_interactive:
            description = ""
        else:
            description = typer.prompt("  Brief description (optional)", default="")

    # Create the spec
    try:
        spec_path = spec_service.create_spec(
            name=name,
            template=template,
            project_name=name,
            description=description,
        )
        spec_name = spec_path.stem
        console.print(f"  {success_icon()} Created spec: {spec_path.relative_to(project_root)}")
    except (ValueError, OSError) as e:
        console.print(f"  {error_icon()} Failed to create spec: {e}")
        raise typer.Exit(1)

    console.print("")

    # Step 4: Initialize sprint (delegates to init command)
    console.print("[bold][4/4] Initializing sprint...[/bold]")
    console.print("")

    from claudesprint.commands.init import init_project

    try:
        init_project(spec=spec_name, description=description or "")
    except typer.Exit as e:
        if e.exit_code != 0:
            raise
    except SystemExit as e:
        if e.code != 0:
            raise typer.Exit(1)

    # Get sprint info for summary
    from claudesprint.services.sprint_service import SprintService

    config = get_config()
    sprint_service = SprintService(config.sprints_dir)
    sprint_path = sprint_service.get_sprint_path(spec_name)
    sprint = sprint_service.read_sprint(sprint_path)
    issue_count = len(sprint.issues) if sprint else 0
    spec_id = sprint.spec_id if sprint else spec_name

    console.print("")

    # Show success summary
    console.print(Panel.fit(
        f"[bold green]Setup Complete![/bold green]\n\n"
        f"Project: {name}\n"
        f"Template: {template}\n"
        f"Issues: {issue_count}\n"
        f"Sprint: {sprint_path.relative_to(project_root)}",
        style=STYLES.PANEL_SUCCESS if hasattr(STYLES, 'PANEL_SUCCESS') else "green",
    ))

    console.print("")

    # Offer to start run
    if not skip_run and not non_interactive:
        start_run = typer.confirm("Start the sprint now?", default=False)
        if start_run:
            console.print("")
            from claudesprint.commands.run import run_workflow
            run_workflow(spec=spec_id)

    # Show next steps if not starting run
    if skip_run or non_interactive:
        console.print("[bold]Next steps:[/bold]")
        console.print(f"  1. Review spec:  {info(f'claudesprint spec show {spec_name}')}")
        console.print(f"  2. Start sprint: {info(f'claudesprint run --spec {spec_id}')}")
