"""Features command for managing optional ClaudeSprint features."""

from typing import Annotated

import typer
from rich.panel import Panel
from rich.table import Table

from claudesprint.commands._shared import (
    console,
    error,
    error_icon,
    get_project_root,
    info,
    success,
    success_icon,
    warning_icon,
)

app = typer.Typer(help="Manage optional features (browser automation, context7)")


@app.callback(invoke_without_command=True)
def features_status(ctx: typer.Context) -> None:
    """Show status of optional features.

    Displays which optional features are available and configured.
    """
    if ctx.invoked_subcommand is not None:
        return

    # Lazy imports
    from claudesprint.services.optional_features_service import OptionalFeaturesService

    features_service = OptionalFeaturesService()

    console.print(Panel.fit("Optional Features", border_style="blue"))
    console.print("")

    # Create a table for features
    table = Table(show_header=True, header_style="bold")
    table.add_column("Feature", style="cyan")
    table.add_column("Status")
    table.add_column("Install")

    for _name, display_name, available, install_hint in features_service.get_features_summary():
        if available:
            status = "[green]✓ Available[/green]"
            hint = "[dim]Installed[/dim]"
        else:
            status = "[yellow]✗ Not available[/yellow]"
            hint = f"[dim]{install_hint}[/dim]"
        table.add_row(display_name, status, hint)

    console.print(table)
    console.print("")

    # Show usage hints
    available_features = features_service.get_available_features()
    unavailable_features = features_service.get_unavailable_features()

    if unavailable_features:
        console.print("[bold]To enable features:[/bold]")
        console.print("  1. Install the missing dependencies")
        console.print(f"  2. Run {info('claudesprint features refresh')} to update configuration")
        console.print("")

    if available_features:
        console.print("[dim]Features are auto-detected during initialization.[/dim]")
        console.print(f"[dim]Use {info('claudesprint init-repo --force')} to reconfigure.[/dim]")


@app.command("refresh")
def refresh_features(
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Recreate settings even if they exist"),
    ] = False,
) -> None:
    """Re-detect features and update configuration.

    Re-runs feature detection and updates .claude/settings.json
    with the appropriate hooks based on what's available.
    """
    # Lazy imports
    from claudesprint.services.claude_settings_service import ClaudeSettingsService
    from claudesprint.services.init_repo_service import InitRepoService
    from claudesprint.services.optional_features_service import OptionalFeaturesService

    project_root = get_project_root()

    # Check if project is initialized
    claudesprint_dir = project_root / ".claudesprint"
    if not claudesprint_dir.exists():
        console.print(error("Project not initialized. Run 'claudesprint init-repo' first."))
        raise typer.Exit(1)

    console.print("[bold]Refreshing feature detection...[/bold]")
    console.print("")

    # Detect features
    features_service = OptionalFeaturesService()
    detected_features = features_service.reload()

    # Show detection results
    for _name, display_name, available, _install_hint in features_service.get_features_summary():
        if available:
            console.print(f"  {success_icon()} {display_name}: Detected")
        else:
            console.print(f"  {warning_icon()} {display_name}: Not found")

    console.print("")

    # Update settings.json
    settings_service = ClaudeSettingsService(project_root)
    init_service = InitRepoService(project_root)

    if not settings_service.settings_exist() or force:
        console.print("[bold]Updating configuration...[/bold]")

        # Re-initialize with force to update hooks and skills
        result = init_service.init(force=True, detected_features=detected_features)

        if result.success:
            console.print(f"  {success_icon()} Settings updated")
            if result.hooks_injected:
                console.print(f"  {success_icon()} Hooks configured based on available features")
        else:
            console.print(f"  {error_icon()} Failed to update: {result.error}")
            raise typer.Exit(1)
    else:
        # Just update hooks in existing settings
        console.print("[bold]Updating hooks configuration...[/bold]")

        enabled_plugins = features_service.get_enabled_plugins(detected_features)
        hook_result = settings_service.inject_hooks(
            include_browser_guard=detected_features.get("agent-browser", False),
            enabled_plugins=enabled_plugins,
        )

        if hook_result.success:
            console.print(f"  {success_icon()} Hooks updated")
        else:
            console.print(f"  {error_icon()} Failed to update hooks: {hook_result.error}")
            raise typer.Exit(1)

        # Create agent-browser skill if now available and missing
        if detected_features.get("agent-browser", False):
            agent_browser_skill = project_root / ".claude" / "skills" / "agent-browser" / "SKILL.md"
            if not agent_browser_skill.exists():
                from claudesprint.services.constants import AGENT_BROWSER_SKILL_CONTENT
                agent_browser_skill.parent.mkdir(parents=True, exist_ok=True)
                agent_browser_skill.write_text(AGENT_BROWSER_SKILL_CONTENT)
                console.print(f"  {success_icon()} Created agent-browser skill")

    console.print("")
    console.print(success("Features refreshed"))


@app.command("list")
def list_features() -> None:
    """List all available optional features with descriptions."""
    from claudesprint.services.optional_features_service import OPTIONAL_FEATURES

    console.print(Panel.fit("Available Optional Features", border_style="blue"))
    console.print("")

    for feature in OPTIONAL_FEATURES:
        console.print(f"[bold cyan]{feature.display_name}[/bold cyan]")
        console.print(f"  Name: {feature.name}")
        console.print(f"  Description: {feature.description}")
        console.print(f"  Install: {info(feature.install_hint)}")
        if feature.skill_name:
            console.print(f"  Provides: Skill ({feature.skill_name})")
        if feature.plugin_key:
            console.print(f"  Provides: Plugin ({feature.plugin_key})")
        console.print("")
