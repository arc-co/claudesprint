"""Centralized styling system for ClaudeSprint CLI.

This module provides consistent styling across all CLI output through:
- SYMBOLS: Unicode symbols for status indicators
- COLORS: Color names for Rich markup
- STYLES: Compound styles for panels, badges, etc.
- Helper functions for common formatting patterns
- ConsoleThrobber: Animated spinner for long-running operations
"""

import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rich.console import Console


@dataclass(frozen=True)
class Symbols:
    """Unicode symbols for status indicators."""

    SUCCESS: str = "✓"
    FAILURE: str = "✗"
    WARNING: str = "⚠"
    RUNNING: str = "▶"
    INDENT: str = ">"
    # Throbber frames for animated spinner (Braille pattern)
    THROBBER_FRAMES: tuple[str, ...] = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")


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


class ConsoleThrobber:
    """Animated console throbber/spinner for indicating activity.

    Uses Braille pattern characters for smooth animation. Thread-safe
    implementation that updates the console in a background thread.

    Example:
        >>> from rich.console import Console
        >>> console = Console()
        >>> throbber = ConsoleThrobber(console)
        >>> throbber.start("Processing...")
        >>> # Do work...
        >>> throbber.stop()
    """

    def __init__(self, console: "Console", interval: float = 0.1) -> None:
        """Initialize the throbber.

        Args:
            console: Rich console for output.
            interval: Animation interval in seconds (default 0.1 = 100ms).
        """
        self.console = console
        self.interval = interval
        self.frames = SYMBOLS.THROBBER_FRAMES
        self._running = False
        self._thread: threading.Thread | None = None
        self._frame_idx = 0
        self._message = ""
        self._lock = threading.Lock()

    def start(self, message: str = "Working") -> None:
        """Start the throbber animation.

        Args:
            message: Status message to display next to spinner.
        """
        with self._lock:
            if self._running:
                # Update message if already running
                self._message = message
                return
            self._message = message
            self._running = True
            self._frame_idx = 0
            self._thread = threading.Thread(target=self._animate, daemon=True)
            self._thread.start()

    def update(self, message: str) -> None:
        """Update the throbber message without stopping.

        Args:
            message: New status message to display.
        """
        with self._lock:
            self._message = message

    def stop(self, final_message: str | None = None) -> None:
        """Stop the throbber animation.

        Args:
            final_message: Optional message to print after stopping.
        """
        with self._lock:
            if not self._running:
                return
            self._running = False

        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None

        # Clear the spinner line
        self.console.print("\r" + " " * 80 + "\r", end="")

        if final_message:
            self.console.print(final_message)

    def _animate(self) -> None:
        """Animation loop running in background thread."""
        while True:
            with self._lock:
                if not self._running:
                    break
                frame = self.frames[self._frame_idx]
                message = self._message
                self._frame_idx = (self._frame_idx + 1) % len(self.frames)

            # Print spinner with carriage return to overwrite
            spinner_text = f"\r[{COLORS.INFO}]{frame}[/{COLORS.INFO}] {message}..."
            self.console.print(spinner_text, end="")

            time.sleep(self.interval)

    @property
    def is_running(self) -> bool:
        """Check if throbber is currently running."""
        with self._lock:
            return self._running
