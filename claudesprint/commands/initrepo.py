"""Init repo command for initializing .claudesprint/ directory."""

from pathlib import Path
from typing import Annotated

import typer
from rich.panel import Panel

from claudesprint.commands._shared import (
    console,
    error,
    info,
    muted,
    success,
    warning,
)


def init_repo(
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Reinitialize even if .claudesprint/ exists"),
    ] = False,
    skip_hooks: Annotated[
        bool,
        typer.Option("--skip-hooks", help="Skip injecting Claude hooks into .claude/settings.json"),
    ] = False,
    skip_optional: Annotated[
        bool,
        typer.Option("--skip-optional", help="Skip all optional features (browser, context7)"),
    ] = False,
    enable_browser: Annotated[
        bool | None,
        typer.Option("--browser/--no-browser", help="Enable/disable browser automation"),
    ] = None,
    enable_context7: Annotated[
        bool | None,
        typer.Option("--context7/--no-context7", help="Enable/disable Context7 MCP"),
    ] = None,
) -> None:
    """Initialize .claudesprint/ directory in the current repository.

    Creates the following structure:
      .claudesprint/
        state/          - Session state files
        prompts/        - Custom prompt overrides
          README.md     - Documentation for prompt overrides

    Also adds .claudesprint/ to .gitignore and injects ClaudeSprint hooks
    into .claude/settings.json (unless --skip-hooks is specified).

    Optional features (browser automation, context7) are auto-detected by default.
    Use --skip-optional to disable all, or --browser/--no-browser and
    --context7/--no-context7 for granular control.
    """
    # Lazy import
    from claudesprint.services.init_repo_service import InitRepoService
    from claudesprint.services.optional_features_service import OptionalFeaturesService

    project_root = Path.cwd()
    service = InitRepoService(project_root)

    # Resolve feature flags
    if skip_optional:
        detected_features = {"agent-browser": False, "context7": False}
    else:
        features_service = OptionalFeaturesService()
        detected = features_service.detect_all()
        detected_features = {
            "agent-browser": enable_browser if enable_browser is not None else detected.get("agent-browser", False),
            "context7": enable_context7 if enable_context7 is not None else detected.get("context7", False),
        }

    result = service.init(
        force=force,
        inject_hooks=not skip_hooks,
        detected_features=detected_features,
    )

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

    # Show feature status
    console.print("")
    console.print("[bold]Features:[/bold]")
    console.print("  ✓ Core workflow hooks configured")
    if detected_features.get("agent-browser", False):
        console.print("  ✓ Browser automation: Available")
    else:
        console.print("  ⚠ Browser automation: Not available")
        console.print(f"    → Install: {info('npm install -g agent-browser')}")
    if detected_features.get("context7", False):
        console.print("  ✓ Context7 MCP: Available")
    else:
        console.print("  ⚠ Context7 MCP: Not available")
        console.print("    → Install: See https://context7.dev")

    console.print("")
    next_steps = (
        "[bold]Next Steps[/bold]\n\n"
        "[bold cyan]Quickstart (Recommended):[/bold cyan]\n"
        f"  {info('claudesprint quickstart')}\n\n"
        "[bold]Manual Setup:[/bold]\n"
        f"  1. {info('claudesprint spec create')} - Create a project spec\n"
        f"  2. {info('claudesprint init --spec <file>')} - Initialize sprint\n"
        f"  3. {info('claudesprint run')} - Start the workflow"
    )
    console.print(Panel(next_steps, border_style="blue"))
