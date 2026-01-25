"""Duration formatting utilities."""


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


def parse_duration(duration_str: str) -> int:
    """Parse a duration string into seconds.

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
