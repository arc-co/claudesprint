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
