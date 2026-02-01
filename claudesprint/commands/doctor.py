"""Doctor command for environment diagnostics."""

from typing import Annotated

import typer
from rich.panel import Panel

from claudesprint.commands._shared import (
    console,
    get_project_root,
    get_config,
    COLORS,
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


def _display_check_results(checks: list, verbose: bool) -> None:
    """Display a list of check results with proper formatting.

    Args:
        checks: List of CheckResult objects.
        verbose: Whether to show detailed information.
    """
    # Import locally to avoid circular imports
    from claudesprint.services.health_check_service import CheckStatus

    for check in checks:
        if check.status == CheckStatus.OK:
            icon = success_icon()
            message = check.message
        elif check.status == CheckStatus.WARNING:
            icon = warning_icon()
            message = f"[{COLORS.WARNING}]{check.message}[/{COLORS.WARNING}]"
            # Add fix hint for warnings
            if check.fix_command:
                message += f" → {info(check.fix_command)}"
        else:
            icon = error_icon()
            message = f"[{COLORS.ERROR}]{check.message}[/{COLORS.ERROR}]"
            if check.fix_command:
                message += f" → {info(check.fix_command)}"

        console.print(f"  {icon} {check.name}: {message}")

        if verbose and check.details:
            for line in check.details.split("\n"):
                console.print(f"      {muted(line)}")


def doctor(
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Show detailed information"),
    ] = False,
    fix: Annotated[
        bool,
        typer.Option("--fix", help="Attempt to auto-fix issues"),
    ] = False,
) -> None:
    """Diagnose environment and verify dependencies.

    Checks that all required dependencies are installed and configured:
    - Python version (3.10+ required)
    - Required Python packages (rich, typer, pydantic, httpx, jinja2)
    - Claude CLI installed and accessible
    - Project structure (.claudesprint/ directory)
    - Optional dependencies (agent-browser, npm)
    """
    # Lazy import for faster startup
    from claudesprint.services.health_check_service import (
        CheckStatus,
        HealthCheckService,
    )

    project_root = get_project_root()
    config = get_config()
    service = HealthCheckService(
        project_root,
        version_check_timeout=config.version_check_timeout,
        install_timeout=config.install_timeout,
    )

    console.print(Panel.fit("ClaudeSprint Doctor", style=STYLES.PANEL_HEADER))
    console.print("")

    # Run all checks
    report = service.run_all_checks(verbose=verbose)

    # Display Environment section
    console.print(f"[bold]=== Environment ===[/bold]")
    _display_check_results(report.checks, verbose)

    # Run and display Setup Readiness section
    console.print("")
    console.print(f"[bold]=== Setup Readiness ===[/bold]")
    setup_report = service.run_setup_checks(verbose=verbose)
    _display_check_results(setup_report.checks, verbose)

    # Merge setup checks into main report for summary
    for check in setup_report.checks:
        report.add(check)

    console.print("")

    # Summary
    if report.is_healthy:
        if report.has_warnings:
            warn_suffix = "s" if report.warning_count > 1 else ""
            console.print(
                f"{success('All required checks passed')} "
                f"{warning(f'({report.warning_count} warning{warn_suffix})')}"
            )
        else:
            console.print(success("All checks passed"))
    else:
        err_suffix = "s" if report.error_count > 1 else ""
        console.print(error(f"{report.error_count} error{err_suffix} found"))

    # Handle --fix flag
    if fix and report.fixable_issues:
        console.print("")
        console.print("[bold]Attempting auto-fixes...[/bold]")
        console.print("")

        for issue in report.fixable_issues:
            if issue.fix_command:
                console.print(f"  Running: {info(issue.fix_command)}")
                fix_success = service.attempt_fix(
                    issue,
                    on_output=lambda line: console.print(f"    {line}"),
                )
                if fix_success:
                    console.print(f"    {success('Fixed')}")
                else:
                    console.print(f"    {error('Failed - run manually')}")

        console.print("")
        console.print(f"Re-run {info('claudesprint doctor')} to verify fixes.")
    elif not fix and report.fixable_issues:
        console.print("")
        console.print(
            muted(
                f"Tip: Run {info('claudesprint doctor --fix')} to attempt auto-fixes "
                f"for {len(report.fixable_issues)} issue{'s' if len(report.fixable_issues) > 1 else ''}"
            )
        )

    if not report.is_healthy:
        raise typer.Exit(1)
