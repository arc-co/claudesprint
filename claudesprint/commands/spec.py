"""Spec command group for managing project specifications."""

from typing import Annotated

import typer
from rich.panel import Panel
from rich.table import Table

from claudesprint.commands._shared import (
    console,
    get_project_root,
    STYLES,
    success,
    error,
    warning,
    muted,
    info,
    success_icon,
    warning_icon,
    error_icon,
)


# Spec command group
spec_app = typer.Typer(
    name="spec",
    help="Manage project specifications",
)


@spec_app.command("list")
def spec_list() -> None:
    """List all spec files in the project."""
    # Lazy imports
    from claudesprint.services.spec_service import SpecService

    project_root = get_project_root()
    service = SpecService(project_root)
    specs = service.list_specs()

    if not specs:
        console.print(warning("No spec files found."))
        console.print("")
        console.print(f"Create one with: {info('claudesprint spec create')}")
        return

    console.print(Panel.fit("Spec Files", style=STYLES.PANEL_HEADER))
    console.print("")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Name")
    table.add_column("Title")
    table.add_column("Path")

    for spec in specs:
        title = spec.title or muted("(no title)")
        # Make path relative to project root
        rel_path = spec.path.relative_to(project_root)
        table.add_row(spec.name, title, str(rel_path))

    console.print(table)


@spec_app.command("show")
def spec_show(
    name: Annotated[str, typer.Argument(help="Name of the spec file to display")],
) -> None:
    """Display the contents of a spec file."""
    # Lazy imports
    from claudesprint.services.spec_service import SpecService

    project_root = get_project_root()
    service = SpecService(project_root)
    content = service.read_spec(name)

    if content is None:
        console.print(error(f"Spec file '{name}' not found."))
        console.print("")
        console.print(f"List available specs with: {info('claudesprint spec list')}")
        raise typer.Exit(1)

    spec = service.get_spec(name)
    title = spec.title if spec else name

    console.print(Panel.fit(f"Spec: {title}", style=STYLES.PANEL_HEADER))
    console.print("")
    console.print(content)


@spec_app.command("validate")
def spec_validate(
    name: Annotated[str, typer.Argument(help="Name of the spec file to validate")],
) -> None:
    """Validate the structure of a spec file."""
    # Lazy imports
    from claudesprint.services.spec_service import SpecService

    project_root = get_project_root()
    service = SpecService(project_root)
    result = service.validate_spec(name)

    if not result.valid:
        console.print(error(f"Validation failed for '{name}'"))
        console.print("")
        for err in result.errors:
            console.print(f"  {error_icon()} {err}")
        raise typer.Exit(1)

    console.print(success(f"Spec '{name}' is valid"))
    console.print("")

    if result.title:
        console.print(f"  Title: {result.title}")

    if result.sections_found:
        console.print(f"  Sections: {', '.join(result.sections_found)}")

    if result.warnings:
        console.print("")
        console.print("[bold]Suggestions:[/bold]")
        for warn in result.warnings:
            console.print(f"  {warning_icon()} {warn}")


@spec_app.command("create")
def spec_create(
    name: Annotated[
        str | None,
        typer.Option("--name", "-n", help="Name for the spec file"),
    ] = None,
    template: Annotated[
        str | None,
        typer.Option("--template", "-t", help="Template to use"),
    ] = None,
    description: Annotated[
        str | None,
        typer.Option("--description", "-d", help="Project description"),
    ] = None,
) -> None:
    """Create a new spec file from a template.

    If options are not provided, runs in interactive mode.
    """
    # Lazy imports
    from claudesprint.services.spec_service import SpecService

    project_root = get_project_root()
    service = SpecService(project_root)
    templates = service.get_templates()

    console.print(Panel.fit("Create New Spec", style=STYLES.PANEL_HEADER))
    console.print("")

    # Interactive mode for project name
    if name is None:
        name = typer.prompt("Project name")

    # Interactive mode for template selection
    if template is None:
        console.print("[bold]Available templates:[/bold]")
        for i, t in enumerate(templates, 1):
            console.print(f"  [{i}] {t.display_name} - {t.description}")
        console.print("")

        while True:
            choice = typer.prompt(f"Select template [1-{len(templates)}]")
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(templates):
                    template = templates[idx].name
                    break
                console.print(warning(f"Please enter a number between 1 and {len(templates)}"))
            except ValueError:
                # Check if user typed template name directly
                for t in templates:
                    if t.name == choice or t.display_name.lower() == choice.lower():
                        template = t.name
                        break
                else:
                    console.print(warning("Invalid selection. Enter a number or template name."))
                    continue
                break
    else:
        # Validate template exists
        valid_templates = [t.name for t in templates]
        if template not in valid_templates:
            console.print(error(f"Unknown template: {template}"))
            console.print(f"Available templates: {', '.join(valid_templates)}")
            raise typer.Exit(1)

    # Interactive mode for description
    if description is None:
        description = typer.prompt("Brief description (optional)", default="")

    # Create the spec
    try:
        spec_path = service.create_spec(
            name=name,
            template=template,
            project_name=name,
            description=description,
        )

        console.print("")
        console.print(success(f"Created: {spec_path.relative_to(project_root)}"))
        console.print("")

        # Show next steps
        spec_name = spec_path.stem
        console.print("[bold]Next steps:[/bold]")
        console.print(f"  1. Review and customize: {info(f'claudesprint spec show {spec_name}')}")
        console.print(f"  2. Initialize sprint:    {info(f'claudesprint init --spec {spec_name}')}")

    except ValueError as e:
        console.print(error(str(e)))
        raise typer.Exit(1)
    except OSError as e:
        console.print(error(f"Failed to create spec: {e}"))
        raise typer.Exit(1)


@spec_app.command("templates")
def spec_templates() -> None:
    """List available spec templates."""
    # Lazy imports
    from claudesprint.services.spec_service import SpecService

    project_root = get_project_root()
    service = SpecService(project_root)
    templates = service.get_templates()

    console.print(Panel.fit("Available Templates", style=STYLES.PANEL_HEADER))
    console.print("")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Name")
    table.add_column("Description")

    for t in templates:
        table.add_row(t.name, t.description)

    console.print(table)
    console.print("")
    console.print(f"Use with: {info('claudesprint spec create --template <name>')}")
