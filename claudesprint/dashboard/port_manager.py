"""Port selection logic for the dashboard server."""

import socket
from dataclasses import dataclass


@dataclass
class PortResult:
    """Result of port availability check."""

    port: int
    success: bool
    error: str | None = None


def find_available_port(start_port: int = 9500, max_attempts: int = 100) -> PortResult:
    """Find an available port starting from start_port.

    Args:
        start_port: The port to start scanning from.
        max_attempts: Maximum number of ports to try.

    Returns:
        PortResult with the found port or error information.
    """
    for offset in range(max_attempts):
        port = start_port + offset
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(("127.0.0.1", port))
                return PortResult(port=port, success=True)
        except OSError:
            continue

    return PortResult(
        port=0,
        success=False,
        error=f"No available port found in range {start_port}-{start_port + max_attempts - 1}",
    )
