"""HTTP server for the dashboard with SSE support."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING

try:
    from aiohttp import web
except ImportError:
    web = None  # type: ignore[assignment]

from claudesprint.dashboard.bridge import DashboardEventBridge
from claudesprint.dashboard.port_manager import find_available_port

if TYPE_CHECKING:
    from claudesprint.events.workflow_event_bus import WorkflowEventBus

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


class DashboardServer:
    """HTTP server for the real-time dashboard.

    Runs aiohttp in a background thread, serving:
    - GET / - Dashboard HTML page
    - GET /events - SSE stream of workflow events
    - GET /state - Current state as JSON
    - GET /static/* - Static files (CSS, JS)
    """

    def __init__(self, event_bus: WorkflowEventBus) -> None:
        """Initialize the dashboard server.

        Args:
            event_bus: The workflow event bus to bridge events from.
        """
        if web is None:
            raise ImportError("aiohttp is required for the dashboard. Install with: pip install aiohttp")

        self._event_bus = event_bus
        self._bridge = DashboardEventBridge(event_bus)
        self._app: web.Application | None = None
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._port: int = 0
        self._running = False
        self._shutdown_event: asyncio.Event | None = None

    def start(self, start_port: int = 9500) -> str | None:
        """Start the dashboard server in a background thread.

        Args:
            start_port: Port to start scanning from.

        Returns:
            Dashboard URL if started successfully, None otherwise.
        """
        if self._running:
            return f"http://127.0.0.1:{self._port}"

        # Find available port
        port_result = find_available_port(start_port)
        if not port_result.success:
            logger.warning(f"Dashboard: {port_result.error}")
            return None

        self._port = port_result.port

        # Connect the event bridge
        self._bridge.connect()

        # Start server in background thread
        self._thread = threading.Thread(target=self._run_server, daemon=True)
        self._thread.start()

        # Wait for server to start (with timeout)
        for _ in range(50):  # 5 seconds max
            if self._running:
                break
            threading.Event().wait(0.1)

        if not self._running:
            logger.warning("Dashboard: Server failed to start")
            return None

        url = f"http://127.0.0.1:{self._port}"
        logger.info(f"Dashboard started at {url}")
        return url

    def stop(self) -> None:
        """Stop the dashboard server gracefully."""
        if not self._running:
            return

        self._running = False

        # Signal shutdown
        if self._loop and self._shutdown_event:
            self._loop.call_soon_threadsafe(self._shutdown_event.set)

        # Wait for thread to finish
        if self._thread:
            self._thread.join(timeout=5.0)

        # Disconnect the event bridge
        self._bridge.disconnect()

        logger.info("Dashboard stopped")

    def _run_server(self) -> None:
        """Run the aiohttp server (called in background thread)."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            self._loop.run_until_complete(self._start_async())
        except Exception as e:
            logger.exception(f"Dashboard server error: {e}")
        finally:
            self._loop.close()

    async def _start_async(self) -> None:
        """Start the async server components."""
        self._shutdown_event = asyncio.Event()

        # Create app with routes
        self._app = web.Application()
        self._app.router.add_get("/", self._handle_index)
        self._app.router.add_get("/events", self._handle_events)
        self._app.router.add_get("/state", self._handle_state)
        self._app.router.add_static("/static", STATIC_DIR)

        # Start the server
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()

        self._site = web.TCPSite(self._runner, "127.0.0.1", self._port)
        await self._site.start()

        self._running = True

        # Wait for shutdown signal
        await self._shutdown_event.wait()

        # Cleanup
        await self._runner.cleanup()

    async def _handle_index(self, _request: web.Request) -> web.StreamResponse:
        """Serve the dashboard HTML page."""
        index_path = STATIC_DIR / "index.html"
        if not index_path.exists():
            return web.Response(text="Dashboard not found", status=404)

        return web.FileResponse(index_path)

    async def _handle_events(self, request: web.Request) -> web.StreamResponse:
        """Handle SSE event stream."""
        response = web.StreamResponse(
            status=200,
            reason="OK",
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
            },
        )
        await response.prepare(request)

        # Track connected clients
        self._bridge.state.connected_clients += 1

        # Send initial state
        initial_state = {
            "type": "initial_state",
            "data": self._bridge.state.to_dict(),
        }
        await response.write(f"data: {json.dumps(initial_state)}\n\n".encode())

        try:
            async for event_data in self._bridge.get_events_async():
                if not self._running:
                    break
                await response.write(event_data.encode())
        except (asyncio.CancelledError, ConnectionResetError):
            pass
        finally:
            self._bridge.state.connected_clients -= 1

        return response

    async def _handle_state(self, _request: web.Request) -> web.Response:
        """Return current state as JSON."""
        return web.json_response(self._bridge.state.to_dict())
