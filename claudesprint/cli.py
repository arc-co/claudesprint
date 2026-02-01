"""CLI interface for ClaudeSprint using Typer.

This is a lightweight router that registers commands from the commands/ modules.
Heavy imports are deferred to command modules for fast startup.
"""

from typing import Annotated

import typer

from claudesprint import __version__
from claudesprint.commands._shared import console
from claudesprint.utils.process_manager import get_process_manager

# Import command modules
from claudesprint.commands import config as config_module
from claudesprint.commands import doctor as doctor_module
from claudesprint.commands import hook as hook_module
from claudesprint.commands import init as init_module
from claudesprint.commands import initrepo as initrepo_module
from claudesprint.commands import quickstart as quickstart_module
from claudesprint.commands import run as run_module
from claudesprint.commands import spec as spec_module
from claudesprint.commands import status as status_module
from claudesprint.commands import utils as utils_module

app = typer.Typer(
    name="claudesprint",
    help="ClaudeSprint - Autonomous workflow orchestration for AI-driven development",
    no_args_is_help=False,
)


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
        status_module.show_status()


# Register commands from modules
app.command("run")(run_module.run_workflow)
app.command("init")(init_module.init_project)
app.command("plan")(init_module.run_planner)
app.command("status")(status_module.show_status)
app.command("models")(status_module.show_models)
app.command("sprints")(status_module.list_sprints)
app.command("validate")(utils_module.validate_sprint)
app.command("reset")(utils_module.reset_sprint)
app.command("notify")(utils_module.send_notification)
app.command("doctor")(doctor_module.doctor)
app.command("hook")(hook_module.run_hook)
app.command("initrepo")(initrepo_module.init_repo)
app.command("quickstart")(quickstart_module.quickstart)

# Register command groups
app.add_typer(config_module.config_app, name="config")
app.add_typer(spec_module.spec_app, name="spec")


if __name__ == "__main__":
    app()
