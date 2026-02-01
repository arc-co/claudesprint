"""Config command group for global configuration management."""

import os
from typing import Annotated

import typer
from rich.panel import Panel

from claudesprint.commands._shared import (
    STYLES,
    console,
    error,
    muted,
    success,
    warning,
)

# Config command group for global configuration
config_app = typer.Typer(
    name="config",
    help="Manage global user configuration",
)


@config_app.command("path")
def config_path() -> None:
    """Show the global config file location."""
    # Lazy import
    from claudesprint.services.configuration_manager import ConfigurationManager

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
    # Lazy imports
    from claudesprint.services.configuration_manager import ConfigurationManager
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
        raise typer.Exit(1) from None


@config_app.command("show")
def config_show() -> None:
    """Display current global configuration."""
    # Lazy import
    from claudesprint.services.configuration_manager import ConfigurationManager

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

    # Lazy imports
    from claudesprint.services.configuration_manager import ConfigurationManager
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
            raise typer.Exit(1) from None

    editor = os.environ.get("EDITOR", os.environ.get("VISUAL", "vim"))
    try:
        subprocess.run([editor, str(config_file)], check=True)
    except FileNotFoundError:
        console.print(error(f"Editor not found: {editor}"))
        console.print("Set the EDITOR environment variable to your preferred editor.")
        raise typer.Exit(1) from None
    except subprocess.CalledProcessError as e:
        console.print(error(f"Editor exited with error: {e.returncode}"))
        raise typer.Exit(1) from None
