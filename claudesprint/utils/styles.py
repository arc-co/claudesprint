"""Centralized styling system for ClaudeSprint CLI.

This module provides consistent styling across all CLI output through:
- SYMBOLS: Unicode symbols for status indicators
- COLORS: Color names for Rich markup
- STYLES: Compound styles for panels, badges, etc.
- Helper functions for common formatting patterns
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Symbols:
    """Unicode symbols for status indicators."""

    SUCCESS: str = "✓"
    FAILURE: str = "✗"
    WARNING: str = "⚠"
    RUNNING: str = "▶"
    INDENT: str = ">"


@dataclass(frozen=True)
class Colors:
    """Color names for Rich markup."""

    SUCCESS: str = "green"
    ERROR: str = "red"
    WARNING: str = "yellow"
    INFO: str = "cyan"
    MUTED: str = "dim"


@dataclass(frozen=True)
class Styles:
    """Compound styles for Rich components."""

    PANEL_HEADER: str = "bold blue"
    STATUS_ERROR: str = "bold red"
    MODEL_OPUS: str = "bold magenta"
    MODEL_SONNET: str = "cyan"


# Singleton instances
SYMBOLS = Symbols()
COLORS = Colors()
STYLES = Styles()


def success(msg: str) -> str:
    """Format a success message with green checkmark.

    Args:
        msg: The message to format.

    Returns:
        Rich-formatted success message.

    Example:
        >>> success("Sprint created")
        '[green]✓ Sprint created[/green]'
    """
    return f"[{COLORS.SUCCESS}]{SYMBOLS.SUCCESS} {msg}[/{COLORS.SUCCESS}]"


def error(msg: str) -> str:
    """Format an error message with red X.

    Args:
        msg: The message to format.

    Returns:
        Rich-formatted error message.

    Example:
        >>> error("Failed to parse file")
        '[red]✗ Failed to parse file[/red]'
    """
    return f"[{COLORS.ERROR}]{SYMBOLS.FAILURE} {msg}[/{COLORS.ERROR}]"


def warning(msg: str) -> str:
    """Format a warning message with yellow warning sign.

    Args:
        msg: The message to format.

    Returns:
        Rich-formatted warning message.

    Example:
        >>> warning("Config file not found")
        '[yellow]⚠ Config file not found[/yellow]'
    """
    return f"[{COLORS.WARNING}]{SYMBOLS.WARNING} {msg}[/{COLORS.WARNING}]"


def running(action: str) -> str:
    """Format a running action indicator.

    Args:
        action: Description of the action being performed.

    Returns:
        Rich-formatted running indicator.

    Example:
        >>> running("Running init agent...")
        '[cyan]▶ Running init agent...[/cyan]'
    """
    return f"[{COLORS.INFO}]{SYMBOLS.RUNNING} {action}[/{COLORS.INFO}]"


def subprocess_line(line: str) -> str:
    """Format a subprocess output line with dimmed indent marker.

    Args:
        line: Output line from subprocess.

    Returns:
        Rich-formatted subprocess output line.

    Example:
        >>> subprocess_line("Installing dependencies...")
        '[dim]>[/dim] Installing dependencies...'
    """
    return f"[{COLORS.MUTED}]{SYMBOLS.INDENT}[/{COLORS.MUTED}] {line}"


def status_badge(status: str) -> str:
    """Format a status as a colored badge.

    Args:
        status: Status string (e.g., "pending", "in_progress", "completed", "blocked").

    Returns:
        Rich-formatted status badge.

    Example:
        >>> status_badge("completed")
        '[green]completed[/green]'
    """
    status_lower = status.lower().replace(" ", "_")
    color_map = {
        "pending": COLORS.MUTED,
        "in_progress": COLORS.WARNING,
        "completed": COLORS.SUCCESS,
        "complete": COLORS.SUCCESS,
        "blocked": COLORS.ERROR,
        "failed": COLORS.ERROR,
        "ok": COLORS.SUCCESS,
        "error": COLORS.ERROR,
        "warning": COLORS.WARNING,
    }
    color = color_map.get(status_lower, COLORS.MUTED)
    return f"[{color}]{status}[/{color}]"


def model_badge(model: str) -> str:
    """Format a model name as a styled badge.

    Args:
        model: Model name (e.g., "opus", "sonnet").

    Returns:
        Rich-formatted model badge.

    Example:
        >>> model_badge("opus")
        '[bold magenta]opus[/bold magenta]'
    """
    model_lower = model.lower()
    if model_lower == "opus":
        return f"[{STYLES.MODEL_OPUS}]{model}[/{STYLES.MODEL_OPUS}]"
    elif model_lower == "sonnet":
        return f"[{STYLES.MODEL_SONNET}]{model}[/{STYLES.MODEL_SONNET}]"
    else:
        return f"[{COLORS.MUTED}]{model}[/{COLORS.MUTED}]"


def muted(msg: str) -> str:
    """Format text as muted/dimmed.

    Args:
        msg: The message to format.

    Returns:
        Rich-formatted muted message.

    Example:
        >>> muted("No changes detected")
        '[dim]No changes detected[/dim]'
    """
    return f"[{COLORS.MUTED}]{msg}[/{COLORS.MUTED}]"


def info(msg: str) -> str:
    """Format an info message in cyan.

    Args:
        msg: The message to format.

    Returns:
        Rich-formatted info message.

    Example:
        >>> info("Processing...")
        '[cyan]Processing...[/cyan]'
    """
    return f"[{COLORS.INFO}]{msg}[/{COLORS.INFO}]"


def success_icon() -> str:
    """Return just the success icon (green checkmark).

    Returns:
        Rich-formatted success icon.

    Example:
        >>> success_icon()
        '[green]✓[/green]'
    """
    return f"[{COLORS.SUCCESS}]{SYMBOLS.SUCCESS}[/{COLORS.SUCCESS}]"


def error_icon() -> str:
    """Return just the error icon (red X).

    Returns:
        Rich-formatted error icon.

    Example:
        >>> error_icon()
        '[red]✗[/red]'
    """
    return f"[{COLORS.ERROR}]{SYMBOLS.FAILURE}[/{COLORS.ERROR}]"


def warning_icon() -> str:
    """Return just the warning icon (yellow warning sign).

    Returns:
        Rich-formatted warning icon.

    Example:
        >>> warning_icon()
        '[yellow]⚠[/yellow]'
    """
    return f"[{COLORS.WARNING}]{SYMBOLS.WARNING}[/{COLORS.WARNING}]"
