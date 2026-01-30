"""Duration formatting utilities."""

from datetime import timedelta
from typing import Union

import isodate  # type: ignore[import-untyped]
from isodate import Duration, ISO8601Error


def format_duration(seconds: int) -> str:
    """Format seconds into human-readable duration.

    Examples:
        45 -> "45s"
        90 -> "1m 30s"
        3665 -> "1h 1m"
    """
    if seconds < 0:
        return "0s"

    if seconds < 60:
        return f"{seconds}s"

    if seconds < 3600:
        mins = seconds // 60
        secs = seconds % 60
        return f"{mins}m {secs}s"

    hours = seconds // 3600
    mins = (seconds % 3600) // 60
    return f"{hours}h {mins}m"


def _parse_simple_duration(duration_str: str) -> int:
    """Parse a simple duration string into seconds.

    Supports formats:
        - "45s" or "45" -> 45 seconds
        - "5m" -> 300 seconds
        - "1h" -> 3600 seconds
        - "1h30m" -> 5400 seconds

    Raises:
        ValueError: If the format is invalid.
    """
    duration_str = duration_str.strip().lower()

    if not duration_str:
        raise ValueError("Empty duration string")

    total = 0
    current_num = ""

    for char in duration_str:
        if char.isdigit():
            current_num += char
        elif char == "h":
            if not current_num:
                raise ValueError(f"Invalid duration format: {duration_str}")
            total += int(current_num) * 3600
            current_num = ""
        elif char == "m":
            if not current_num:
                raise ValueError(f"Invalid duration format: {duration_str}")
            total += int(current_num) * 60
            current_num = ""
        elif char == "s":
            if not current_num:
                raise ValueError(f"Invalid duration format: {duration_str}")
            total += int(current_num)
            current_num = ""
        elif not char.isspace():
            raise ValueError(f"Invalid duration format: {duration_str}")

    # Handle bare numbers (interpreted as seconds)
    if current_num:
        total += int(current_num)

    return total


def _duration_to_seconds(duration: Union[timedelta, Duration]) -> int:
    """Convert a timedelta or isodate.Duration to integer seconds.

    Raises:
        ValueError: If the duration contains years or months (cannot convert precisely).
    """
    if isinstance(duration, Duration):
        # Duration has years, months, and a timedelta component
        if duration.years != 0 or duration.months != 0:
            raise ValueError(
                "Cannot convert duration with years or months to seconds "
                "(variable-length periods)"
            )
        # Get the timedelta component
        td = duration.tdelta
    else:
        td = duration

    return int(td.total_seconds())


def _is_iso8601_duration(duration_str: str) -> bool:
    """Check if a string looks like an ISO 8601 duration."""
    stripped = duration_str.strip()
    return stripped.startswith("P") or stripped.startswith("-P")


def parse_duration(duration_str: str) -> int:
    """Parse a duration string into seconds.

    Supports both simple and ISO 8601 formats:

    Simple formats:
        - "45s" or "45" -> 45 seconds
        - "5m" -> 300 seconds
        - "1h" -> 3600 seconds
        - "1h30m" -> 5400 seconds

    ISO 8601 formats:
        - "PT45S" -> 45 seconds
        - "PT5M" -> 300 seconds
        - "PT1H" -> 3600 seconds
        - "PT1H30M" -> 5400 seconds
        - "P1D" -> 86400 seconds (1 day)

    Raises:
        ValueError: If the format is invalid or contains years/months.
    """
    duration_str = duration_str.strip()

    if not duration_str:
        raise ValueError("Empty duration string")

    if _is_iso8601_duration(duration_str):
        try:
            parsed = isodate.parse_duration(duration_str)
            return _duration_to_seconds(parsed)
        except ISO8601Error as e:
            raise ValueError(f"Invalid ISO 8601 duration format: {duration_str}") from e

    return _parse_simple_duration(duration_str)
