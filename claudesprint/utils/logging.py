"""Logging utilities for ClaudeSprint."""

import sys
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import TextIO

from rich.console import Console


class LogLevel(StrEnum):
    """Log levels."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ClaudesprintLogger:
    """Logger that outputs to both console (with colors) and file (without)."""

    def __init__(
        self,
        log_file: Path | None = None,
        console: Console | None = None,
        level: LogLevel = LogLevel.INFO,
    ) -> None:
        self.log_file = log_file
        self.console = console or Console()
        self.level = level
        self._file: TextIO | None = None
        self._log_levels = {
            LogLevel.DEBUG: 0,
            LogLevel.INFO: 1,
            LogLevel.WARNING: 2,
            LogLevel.ERROR: 3,
        }

    def _should_log(self, level: LogLevel) -> bool:
        """Check if message should be logged at current level."""
        return self._log_levels[level] >= self._log_levels[self.level]

    def setup(self) -> None:
        """Set up the log file."""
        if self.log_file:
            self._file = open(self.log_file, "w")
            self._write_header()

    def close(self) -> None:
        """Close the log file."""
        if self._file:
            self._file.close()
            self._file = None

    def _write_header(self) -> None:
        """Write header to log file."""
        if self._file:
            import os

            self._file.write("==============================================\n")
            self._file.write(f"ClaudeSprint - Log started {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            self._file.write(f"PID: {os.getpid()}\n")
            self._file.write("==============================================\n\n")
            self._file.flush()

    def _timestamp(self) -> str:
        """Get current timestamp string."""
        return datetime.now().strftime("%H:%M:%S")

    def _write_to_file(self, message: str) -> None:
        """Write message to log file without ANSI codes."""
        if self._file:
            # Strip ANSI codes for file output
            import re

            clean_msg = re.sub(r"\x1b\[[0-9;]*m", "", message)
            self._file.write(f"[{self._timestamp()}] {clean_msg}\n")
            self._file.flush()

    def log(self, message: str, style: str = "") -> None:
        """Log a message to console and file."""
        if style:
            self.console.print(message, style=style)
        else:
            self.console.print(message)
        self._write_to_file(message)

    def log_raw(self, message: str) -> None:
        """Log raw message without timestamp prefix."""
        self.console.print(message)
        if self._file:
            import re

            clean_msg = re.sub(r"\x1b\[[0-9;]*m", "", message)
            self._file.write(f"{clean_msg}\n")
            self._file.flush()

    def debug(self, message: str) -> None:
        """Log debug message."""
        if self._should_log(LogLevel.DEBUG):
            self.log(message, style="dim")

    def info(self, message: str) -> None:
        """Log info message."""
        if self._should_log(LogLevel.INFO):
            self.log(message)

    def success(self, message: str) -> None:
        """Log success message."""
        if self._should_log(LogLevel.INFO):
            self.log(f"[green]✓[/green] {message}")

    def warning(self, message: str) -> None:
        """Log warning message."""
        if self._should_log(LogLevel.WARNING):
            self.log(f"[yellow]⚠[/yellow] {message}")

    def error(self, message: str) -> None:
        """Log error message."""
        if self._should_log(LogLevel.ERROR):
            self.log(f"[red]✗[/red] {message}")

    def __enter__(self) -> "ClaudesprintLogger":
        self.setup()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


# Global logger instance
_logger: ClaudesprintLogger | None = None


def setup_logging(
    log_file: Path | str | None = None,
    level: LogLevel = LogLevel.INFO,
) -> ClaudesprintLogger:
    """Set up global logging."""
    global _logger
    log_path = Path(log_file) if log_file else None
    _logger = ClaudesprintLogger(log_file=log_path, level=level)
    _logger.setup()
    return _logger


def get_logger() -> ClaudesprintLogger:
    """Get the global logger, creating one if needed."""
    global _logger
    if _logger is None:
        _logger = ClaudesprintLogger()
    return _logger


class ConversationLogger:
    """Logger for raw agent conversations (inputs and outputs).

    This logger captures the full input and output of each Claude interaction
    for debugging purposes. Enable via CLAUDESPRINT_DEBUG_CONVERSATIONS=true
    or --debug-conversations flag.
    """

    def __init__(self, log_file: Path | str) -> None:
        """Initialize conversation logger.

        Args:
            log_file: Path to the log file for conversation data.
        """
        self.log_file = Path(log_file)

    def log_interaction(
        self,
        source: str,
        input_text: str,
        output_text: str,
        exit_code: int,
        model: str | None = None,
        duration_seconds: int | None = None,
    ) -> None:
        """Log a full interaction cycle.

        Args:
            source: Identifier for this interaction (e.g., prompt file name).
            input_text: The full input sent to Claude.
            output_text: The full output received from Claude.
            exit_code: The process exit code.
            model: Optional model name used for this interaction.
            duration_seconds: Optional duration of the interaction.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Ensure directory exists
        if not self.log_file.parent.exists():
            self.log_file.parent.mkdir(parents=True, exist_ok=True)

        separator = "=" * 80

        entry_lines = [
            f"\n{separator}",
            f"TIMESTAMP:  {timestamp}",
            f"SOURCE:     {source}",
            f"EXIT CODE:  {exit_code}",
        ]

        if model:
            entry_lines.append(f"MODEL:      {model}")
        if duration_seconds is not None:
            entry_lines.append(f"DURATION:   {duration_seconds}s")

        entry_lines.extend([
            separator,
            "--- INPUT START ---",
            input_text,
            "--- INPUT END ---",
            "",
            "--- OUTPUT START ---",
            output_text,
            "--- OUTPUT END ---",
        ])

        entry = "\n".join(entry_lines)

        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(entry)

    def clear(self) -> None:
        """Clear the conversation log file."""
        if self.log_file.exists():
            self.log_file.unlink()
