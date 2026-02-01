"""Init repo command for initializing .claudesprint/ directory."""

from pathlib import Path
from typing import Annotated

import typer
from rich.panel import Panel

from claudesprint.commands._shared import (
    console,
    success,
    error,
    warning,
    muted,
    info,
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
    # Lazy import
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
