"""CLI interface for ClaudeSprint using Typer.

This is a lightweight router that registers commands from the commands/ modules.
Heavy imports are deferred to command modules for fast startup.
"""

from pathlib import Path
from typing import Annotated

import typer

from claudesprint import __version__
from claudesprint.commands._shared import console
from claudesprint.utils.process_manager import get_process_manager

# Import command modules
from claudesprint.commands import config as config_module
from claudesprint.commands import demo as demo_module
from claudesprint.commands import doctor as doctor_module
from claudesprint.commands import hook as hook_module
from claudesprint.commands import init as init_module
from claudesprint.commands import quickstart as quickstart_module
from claudesprint.commands import run as run_module
from claudesprint.commands import spec as spec_module
from claudesprint.commands import status as status_module
from claudesprint.commands import utils as utils_module

# Help panel groupings for better discoverability
PANEL_GETTING_STARTED = "Getting Started"
PANEL_WORKFLOW = "Workflow"
PANEL_SETUP = "Setup"
PANEL_UTILITIES = "Utilities"

app = typer.Typer(
    name="claudesprint",
    help="ClaudeSprint - Autonomous workflow orchestration for AI-driven development",
    no_args_is_help=False,
    rich_markup_mode="rich",
)


def _is_first_run() -> bool:
    """Check if this is first run (no .claudesprint/ directory)."""
    return not (Path.cwd() / ".claudesprint").exists()


def _check_claude_cli() -> tuple[bool, bool]:
    """Quick check for Claude CLI availability.

    Returns:
        Tuple of (cli_installed, cli_authenticated).
    """
    import shutil

    claude_path = shutil.which("claude")
    if not claude_path:
        return False, False

    # Check for credentials file directly - fast and reliable
    credentials_path = Path.home() / ".claude" / ".credentials.json"

    if credentials_path.exists():
        try:
            content = credentials_path.read_text()
            if len(content) > 10:  # Minimal valid JSON
                return True, True
        except (OSError, PermissionError):
            pass

    return True, False  # Installed but not authenticated


def _show_welcome() -> None:
    """Show welcome screen for first-time users."""
    from rich.panel import Panel

    # Check Claude CLI status
    cli_installed, cli_authed = _check_claude_cli()

    console.print("")
    console.print(Panel.fit(
        "[bold cyan]Welcome to ClaudeSprint![/bold cyan]",
        border_style="cyan",
    ))
    console.print("")

    if not cli_installed:
        console.print("[bold red]⚠ Claude CLI Required[/bold red]")
        console.print("")
        console.print("ClaudeSprint uses Claude Code CLI to orchestrate AI agents.")
        console.print("")
        console.print("[bold]Install Claude CLI:[/bold]")
        console.print("  https://docs.anthropic.com/en/docs/claude-code")
        console.print("")
        console.print("[bold]Then authenticate:[/bold]")
        console.print("  [cyan]claude login[/cyan]")
        console.print("")
        console.print("[dim]After setup, run:[/dim] [cyan]claudesprint quickstart[/cyan]")
        return

    if not cli_authed:
        console.print("[bold yellow]⚠ Claude CLI Not Authenticated[/bold yellow]")
        console.print("")
        console.print("[bold]Run:[/bold] [cyan]claude login[/cyan]")
        console.print("")
        console.print("[dim]After login, run:[/dim] [cyan]claudesprint quickstart[/cyan]")
        return

    # All good - show quickstart options
    console.print("[bold green]✓ Environment ready[/bold green]")
    console.print("")
    console.print("[bold]Get started:[/bold]")
    console.print("")
    console.print("  [cyan]claudesprint quickstart[/cyan]")
    console.print("      Interactive setup - creates spec and initializes sprint")
    console.print("")
    console.print("  [cyan]claudesprint demo[/cyan]")
    console.print("      Try with a sample project - see results immediately")
    console.print("")
    console.print("[bold]Other commands:[/bold]")
    console.print("  [dim]claudesprint doctor[/dim]    Check environment")
    console.print("  [dim]claudesprint --help[/dim]    All commands")


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

    # If no subcommand provided
    if ctx.invoked_subcommand is None:
        # First run? Show welcome instead of status
        if _is_first_run():
            _show_welcome()
        else:
            status_module.show_status()


# Register commands with help panel groupings for better discoverability
# Getting Started - first things new users should try
app.command("quickstart", rich_help_panel=PANEL_GETTING_STARTED)(quickstart_module.quickstart)
app.command("demo", rich_help_panel=PANEL_GETTING_STARTED)(demo_module.demo)
app.command("doctor", rich_help_panel=PANEL_GETTING_STARTED)(doctor_module.doctor)

# Workflow - daily usage commands
app.command("run", rich_help_panel=PANEL_WORKFLOW)(run_module.run_workflow)
app.command("status", rich_help_panel=PANEL_WORKFLOW)(status_module.show_status)
app.command("sprints", rich_help_panel=PANEL_WORKFLOW)(status_module.list_sprints)

# Setup - project configuration
app.command("init", rich_help_panel=PANEL_SETUP)(init_module.init_project)

# Utilities - less common operations
app.command("validate", rich_help_panel=PANEL_UTILITIES)(utils_module.validate_sprint)
app.command("reset", rich_help_panel=PANEL_UTILITIES)(utils_module.reset_sprint)
app.command("models", rich_help_panel=PANEL_UTILITIES)(status_module.show_models)
app.command("hook", rich_help_panel=PANEL_UTILITIES)(hook_module.run_hook)

# Register command groups
app.add_typer(config_module.config_app, name="config", rich_help_panel=PANEL_UTILITIES)
app.add_typer(spec_module.spec_app, name="spec", rich_help_panel=PANEL_SETUP)


if __name__ == "__main__":
    app()
