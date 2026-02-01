"""Demo command for trying ClaudeSprint with a sample project."""

from importlib import resources
from pathlib import Path
from typing import Annotated

import typer
from rich.panel import Panel

from claudesprint.commands._shared import (
    console,
    error,
    error_icon,
    info,
    success_icon,
    warning,
    warning_icon,
)


def _get_demo_spec_content() -> str:
    """Load demo spec from package templates."""
    try:
        return resources.files("claudesprint.templates.specs").joinpath("demo.md").read_text()
    except Exception:
        # Fallback for older Python or missing resource
        template_path = Path(__file__).parent.parent / "templates" / "specs" / "demo.md"
        return template_path.read_text()


def demo(
    directory: Annotated[
        str | None,
        typer.Option("--dir", "-d", help="Directory for demo project (default: ./claudesprint-demo)"),
    ] = None,
    skip_run: Annotated[
        bool,
        typer.Option("--skip-run", help="Set up demo but don't run the workflow"),
    ] = False,
    clean: Annotated[
        bool,
        typer.Option("--clean", help="Remove existing demo directory first"),
    ] = False,
    full: Annotated[
        bool,
        typer.Option("--full", help="Include optional features (browser automation, context7)"),
    ] = False,
) -> None:
    """Try ClaudeSprint with a sample project.

    Creates a simple demo project to see ClaudeSprint in action without
    having to write your own spec. Perfect for first-time users.

    The demo creates a "Hello World" CLI tool with 2 simple issues.

    By default, runs in minimal mode (no optional dependencies required).
    Use --full to include browser automation and context7 if available.
    """
    import os
    import shutil

    # Lazy imports for speed
    from claudesprint.services.health_check_service import CheckStatus, HealthCheckService
    from claudesprint.services.optional_features_service import OptionalFeaturesService

    demo_dir = Path(directory) if directory else Path.cwd() / "claudesprint-demo"

    # Determine features based on --full flag
    if full:
        # Auto-detect features when --full is specified
        features_service = OptionalFeaturesService()
        detected_features = features_service.detect_all()
    else:
        # Minimal mode: no optional features
        detected_features = {"agent-browser": False, "context7": False}

    console.print(Panel.fit("[bold cyan]ClaudeSprint Demo[/bold cyan]", border_style="cyan"))
    console.print("")

    # Check prerequisites first
    console.print("[bold]Checking prerequisites...[/bold]")

    health_service = HealthCheckService(Path.cwd())

    # Check Claude CLI
    claude_result = health_service.check_claude_cli()
    if claude_result.status == CheckStatus.ERROR:
        console.print(f"  {error_icon()} {claude_result.message}")
        console.print("")
        console.print(error("Claude CLI is required for the demo."))
        console.print("Install from: https://docs.anthropic.com/en/docs/claude-code")
        raise typer.Exit(1)
    console.print(f"  {success_icon()} Claude CLI installed")

    # Check auth
    auth_result = health_service.check_claude_auth()
    if auth_result.status == CheckStatus.ERROR:
        console.print(f"  {error_icon()} {auth_result.message}")
        console.print("")
        console.print(error("Claude CLI must be authenticated."))
        console.print(f"Run: {info('claude login')}")
        raise typer.Exit(1)
    console.print(f"  {success_icon()} Claude CLI authenticated")
    console.print("")

    # Handle existing directory
    if demo_dir.exists():
        if clean:
            console.print(f"Removing existing demo directory: {demo_dir}")
            shutil.rmtree(demo_dir)
        else:
            console.print(warning(f"Demo directory already exists: {demo_dir}"))
            console.print("")
            console.print("Options:")
            console.print(f"  • Run with {info('--clean')} to remove and recreate")
            console.print(f"  • Use {info('--dir <path>')} for a different location")
            console.print(f"  • Navigate into it: {info(f'cd {demo_dir} && claudesprint run')}")
            raise typer.Exit(1)

    # Create demo project
    console.print(f"[bold]Creating demo project in:[/bold] {demo_dir}")
    console.print("")

    demo_dir.mkdir(parents=True, exist_ok=True)

    # Initialize using InitRepoService with feature flags
    from claudesprint.services.init_repo_service import InitRepoService

    init_service = InitRepoService(demo_dir)
    init_result = init_service.init(force=True, detected_features=detected_features)

    if not init_result.success:
        console.print(f"  {error_icon()} {init_result.error}")
        raise typer.Exit(1)

    console.print(f"  {success_icon()} Initialized .claudesprint/ directory")
    if init_result.hooks_injected:
        console.print(f"  {success_icon()} Claude hooks configured")

    # Show feature status
    if full:
        if detected_features.get("agent-browser", False):
            console.print(f"  {success_icon()} Browser automation: Available")
        else:
            console.print(f"  {warning_icon()} Browser automation: Not available")
        if detected_features.get("context7", False):
            console.print(f"  {success_icon()} Context7 MCP: Available")
        else:
            console.print(f"  {warning_icon()} Context7 MCP: Not available")
    else:
        console.print(f"  {info('Minimal mode')} (use --full for optional features)")

    # Create specs directory and write demo spec
    claudesprint_dir = demo_dir / ".claudesprint"
    specs_dir = claudesprint_dir / "specs"
    specs_dir.mkdir(parents=True, exist_ok=True)
    sprints_dir = claudesprint_dir / "sprints"
    sprints_dir.mkdir(parents=True, exist_ok=True)

    spec_path = specs_dir / "hello-world.md"
    spec_path.write_text(_get_demo_spec_content())
    console.print(f"  {success_icon()} Created demo spec")

    # Create a minimal README
    readme_content = """# ClaudeSprint Demo Project

This is a demo project created by `claudesprint demo`.

## What's in here

- `.claudesprint/specs/hello-world.md` - The project specification
- `.claudesprint/sprints/` - Sprint data (after init)

## Next steps

```bash
cd claudesprint-demo
claudesprint status      # See sprint status
claudesprint run         # Continue the workflow
```

## Clean up

Delete this entire directory when done:
```bash
rm -rf claudesprint-demo
```
"""
    (demo_dir / "README.md").write_text(readme_content)
    console.print(f"  {success_icon()} Created README.md")

    # Initialize git repo
    try:
        import subprocess
        subprocess.run(
            ["git", "init"],
            cwd=demo_dir,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "add", "."],
            cwd=demo_dir,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "Initial demo setup"],
            cwd=demo_dir,
            capture_output=True,
            check=True,
        )
        console.print(f"  {success_icon()} Initialized git repository")
    except (subprocess.SubprocessError, FileNotFoundError):
        console.print(f"  {warning_icon()} Could not initialize git (optional)")

    console.print("")

    if skip_run:
        console.print(Panel.fit(
            f"[bold green]Demo project created![/bold green]\n\n"
            f"Location: {demo_dir}\n\n"
            f"[bold]Next steps:[/bold]\n"
            f"  cd {demo_dir}\n"
            f"  claudesprint init --spec hello-world\n"
            f"  claudesprint run",
            border_style="green",
        ))
        return

    # Change to demo directory and initialize sprint
    original_cwd = Path.cwd()
    os.chdir(demo_dir)

    try:
        console.print("[bold]Initializing sprint from spec...[/bold]")
        console.print("")

        # Import and run init
        from claudesprint.commands.init import init_project

        # Call init with the demo spec
        try:
            init_project(spec="hello-world")
        except typer.Exit as e:
            if e.exit_code != 0:
                console.print(error("Sprint initialization failed"))
                raise
        except SystemExit as e:
            if e.code != 0:
                console.print(error("Sprint initialization failed"))
                raise typer.Exit(1) from None

        console.print("")
        console.print(Panel.fit(
            f"[bold green]Demo ready![/bold green]\n\n"
            f"Location: {demo_dir}\n\n"
            f"[bold]Start the workflow:[/bold]\n"
            f"  claudesprint run\n\n"
            f"[bold]Or run with limits:[/bold]\n"
            f"  claudesprint run -n 5  [dim]# Max 5 iterations[/dim]",
            border_style="green",
        ))

        # Offer to start run
        console.print("")
        start_run = typer.confirm("Start the workflow now?", default=False)
        if start_run:
            console.print("")
            from claudesprint.commands.run import run_workflow
            run_workflow(max_iterations=10, dashboard=True)

    finally:
        os.chdir(original_cwd)
