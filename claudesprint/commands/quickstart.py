"""Quickstart command for single-command project setup."""

from pathlib import Path
from typing import Annotated

import typer
from rich.panel import Panel

from claudesprint.commands._shared import (
    console,
    get_config,
    ConsoleThrobber,
    STYLES,
    success,
    error,
    warning,
    muted,
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

    # Step 4: Initialize sprint
    console.print("[bold][4/4] Initializing sprint...[/bold]")

    # Import init components lazily
    from claudesprint.core.claude_runner import ClaudeRunner
    from claudesprint.services.configuration_manager import ConfigurationManager
    from claudesprint.services.models_service import ModelsService
    from claudesprint.services.path_service import PathService
    from claudesprint.services.prompt_service import PromptService
    from claudesprint.services.sprint_service import SprintService

    config = get_config()

    # Create sprint from spec
    sprint_service = SprintService(config.sprints_dir)
    try:
        relative_spec_path = spec_path.relative_to(project_root)
    except ValueError:
        relative_spec_path = spec_path

    sprint_path, sprint = sprint_service.create_sprint_from_spec(
        relative_spec_path, description or ""
    )

    # Ensure sprints directory exists
    sprint_path.parent.mkdir(parents=True, exist_ok=True)

    # Write sprint skeleton
    if not sprint_service.write_sprint(sprint, sprint_path):
        console.print(f"  {error_icon()} Failed to create sprint")
        raise typer.Exit(1)

    console.print(f"  {success_icon()} Sprint skeleton created")

    # Load init prompt
    path_service = PathService(project_root=project_root)
    prompt_service = PromptService(path_service, project_root=project_root)
    try:
        prompt_content = prompt_service.get_prompt_content("init")
    except FileNotFoundError:
        console.print(f"  {error_icon()} Init prompt template not found")
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

    runner = ClaudeRunner(
        project_root,
        config.claude_timeout,
        kill_timeout=config.kill_timeout,
    )

    # Run init agent with throbber
    throbber = ConsoleThrobber(console)
    throbber.start(f"  Generating issues from spec (model: {model})")
    first_output_received = [False]

    def on_output(line: str) -> None:
        if not first_output_received[0]:
            first_output_received[0] = True
            throbber.stop()
        # Don't show verbose output in quickstart

    result = runner.run_with_content(
        prompt_content,
        source_name="PROMPT_init.xml.j2",
        on_output=on_output,
        model=model,
        context=context,
    )

    if throbber.is_running:
        throbber.stop()

    if result.exit_code != 0:
        console.print(f"  {error_icon()} Sprint initialization failed")
        if result.rate_limited:
            console.print(warning("  Rate limit detected. Please wait and try again."))
        raise typer.Exit(1)

    # Count issues in sprint
    updated_sprint = sprint_service.read_sprint(sprint_path)
    issue_count = len(updated_sprint.issues) if updated_sprint else 0

    console.print(f"  {success_icon()} Sprint ready with {issue_count} issue(s)")

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
            console.print(f"Starting: {info(f'claudesprint run --spec {sprint.spec_id}')}")
            console.print("")
            # Import and call run command
            from claudesprint.commands.run import run_workflow
            # We need to exit and re-invoke since run_workflow takes control
            raise typer.Exit(0)

    # Show next steps
    console.print("[bold]Next steps:[/bold]")
    console.print(f"  1. Review spec:  {info(f'claudesprint spec show {spec_name}')}")
    console.print(f"  2. Start sprint: {info(f'claudesprint run --spec {sprint.spec_id}')}")
