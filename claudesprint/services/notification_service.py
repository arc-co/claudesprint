"""Notification service for Bark push notifications."""

from __future__ import annotations

import asyncio
import logging
from enum import StrEnum
from typing import TYPE_CHECKING
from urllib.parse import quote

import httpx

if TYPE_CHECKING:
    from claudesprint.services.configuration_manager import ConfigurationManager
    from claudesprint.services.project_config_service import (
        NotificationsConfig,
        ProjectConfigService,
    )

logger = logging.getLogger(__name__)


class NotificationType(StrEnum):
    """Notification event types."""

    STEP = "step"
    FAILURE = "failure"
    EXIT = "exit"
    RATE_LIMIT = "rate_limit"
    HEARTBEAT = "heartbeat"
    HUNG_PROCESS = "hung_process"


class NotificationService:
    """Service for sending push notifications via Bark."""

    TITLES = {
        NotificationType.STEP: "ClaudeSprint - Step Complete",
        NotificationType.FAILURE: "ClaudeSprint - Failure",
        NotificationType.EXIT: "ClaudeSprint - Exit",
        NotificationType.RATE_LIMIT: "ClaudeSprint - Rate Limited",
        NotificationType.HEARTBEAT: "ClaudeSprint - Heartbeat",
        NotificationType.HUNG_PROCESS: "ClaudeSprint - Hung Process",
    }

    # Default HTTP timeout (can be overridden via config)
    DEFAULT_HTTP_TIMEOUT = 10.0

    def __init__(
        self,
        http_timeout: float | None = None,
    ) -> None:
        self._notifications_config: NotificationsConfig | None = None
        self._client: httpx.AsyncClient | None = None
        self._queue: asyncio.Queue[tuple[NotificationType, str, str | None]] | None = None
        self._worker_task: asyncio.Task[None] | None = None
        self._http_timeout = http_timeout if http_timeout is not None else self.DEFAULT_HTTP_TIMEOUT

    @classmethod
    def from_config_manager(
        cls,
        config_manager: "ConfigurationManager",
        http_timeout: float | None = None,
    ) -> "NotificationService":
        """Create NotificationService from ConfigurationManager.

        Args:
            config_manager: The configuration manager to load from.
            http_timeout: Optional HTTP timeout override.

        Returns:
            Configured NotificationService instance.
        """
        instance = cls(http_timeout=http_timeout)
        instance._notifications_config = config_manager.project.notifications
        return instance

    @property
    def enabled(self) -> bool:
        """Check if notifications are enabled."""
        if self._notifications_config is None:
            return False
        return (
            self._notifications_config.enabled
            and self._notifications_config.bark.enabled
            and bool(self._notifications_config.bark.url)
        )

    async def send(
        self,
        notification_type: NotificationType,
        message: str,
        title: str | None = None,
    ) -> bool:
        """Send a notification asynchronously."""
        if not self.enabled or not self._notifications_config:
            return False

        actual_title = title or self.TITLES.get(notification_type, "ClaudeSprint")
        encoded_title = quote(actual_title)
        encoded_message = quote(message)
        url = f"{self._notifications_config.bark.url}/{encoded_title}/{encoded_message}"

        try:
            async with httpx.AsyncClient(timeout=self._http_timeout) as client:
                response = await client.get(url)
                if response.status_code != 200:
                    logger.warning(
                        f"Notification failed: {notification_type} - HTTP {response.status_code}"
                    )
                    return False
                return True
        except Exception as e:
            logger.warning(f"Notification failed: {notification_type} - {e}")
            return False

    def send_sync(
        self,
        notification_type: NotificationType,
        message: str,
        title: str | None = None,
    ) -> bool:
        """Send a notification synchronously (non-blocking, fire-and-forget)."""
        if not self.enabled or not self._notifications_config:
            return False

        actual_title = title or self.TITLES.get(notification_type, "ClaudeSprint")
        encoded_title = quote(actual_title)
        encoded_message = quote(message)
        url = f"{self._notifications_config.bark.url}/{encoded_title}/{encoded_message}"

        try:
            # Fire and forget - don't wait for response
            with httpx.Client(timeout=self._http_timeout) as client:
                response = client.get(url)
                if response.status_code != 200:
                    logger.warning(
                        f"Notification failed: {notification_type} - HTTP {response.status_code}"
                    )
                    return False
            return True
        except Exception as e:
            logger.warning(f"Notification failed: {notification_type} - {e}")
            return False

    def _ensure_worker_running(self) -> None:
        """Start the background worker if loop is running and worker is dead."""
        try:
            loop = asyncio.get_event_loop()
            if self._queue is None:
                self._queue = asyncio.Queue[tuple[NotificationType, str, str | None]]()
            if self._worker_task is None or self._worker_task.done():
                self._worker_task = loop.create_task(self._consume_queue())
        except RuntimeError:
            pass

    async def _consume_queue(self) -> None:
        """Process notifications one by one to ensure FIFO ordering."""
        while True:
            if self._queue is None:
                break
            # Wait for next item
            notif_type, message, title = await self._queue.get()
            try:
                # Await the actual network call so strict ordering is preserved
                await self.send(notif_type, message, title)
            except Exception as e:
                logger.error(f"Notification worker error: {e}")
            finally:
                self._queue.task_done()

    def send_background(
        self,
        notification_type: NotificationType,
        message: str,
        title: str | None = None,
    ) -> None:
        """Enqueue notification for ordered delivery (non-blocking).

        Uses a FIFO queue to ensure notifications are delivered in order,
        preventing race conditions from network jitter.
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                self._ensure_worker_running()
                # Put in queue (non-blocking)
                if self._queue is not None:
                    self._queue.put_nowait((notification_type, message, title))
            else:
                # Fallback for synchronous contexts (e.g., startup/shutdown errors)
                self.send_sync(notification_type, message, title)
        except RuntimeError:
            # If no event loop, run synchronously
            self.send_sync(notification_type, message, title)

    # Convenience methods
    def notify_step(self, message: str) -> None:
        """Notify of step completion."""
        self.send_background(NotificationType.STEP, message)

    def notify_failure(self, message: str) -> None:
        """Notify of failure."""
        self.send_background(NotificationType.FAILURE, message)

    def notify_exit(self, message: str) -> None:
        """Notify of loop exit."""
        self.send_background(NotificationType.EXIT, message)

    def notify_rate_limit(self, message: str) -> None:
        """Notify of rate limit."""
        self.send_background(NotificationType.RATE_LIMIT, message)

    def notify_hung_process(self, step: str, seconds_inactive: int) -> None:
        """Notify of a hung process.

        Args:
            step: The step that appears hung.
            seconds_inactive: Seconds since last activity.
        """
        minutes = seconds_inactive // 60
        message = f"No activity for {minutes}m on step: {step}"
        self.send_background(NotificationType.HUNG_PROCESS, message)

    def notify_step_with_context(
        self,
        step: str,
        next_step: str,
        task_id: str | None = None,
        task_title: str | None = None,
        progress: tuple[int, int] | None = None,
        status: str = "COMPLETE",
    ) -> None:
        """Send step notification with task context.

        Args:
            step: The step that completed.
            next_step: The next step to execute.
            task_id: Optional task ID being worked on.
            task_title: Optional task title.
            progress: Optional tuple of (completed_tasks, total_tasks).
            status: Status indicator (e.g., "DONE ✅", "SKIPPED ⏭️").
        """
        # Build Title: [Issue-ID] Issue Title
        # Example: [feature-001] Add Login Page
        title_part = "ClaudeSprint"
        if task_id:
            safe_title = (
                (task_title[:30] + "...") if task_title and len(task_title) > 30 else (task_title or "")
            )
            title_part = f"[{task_id}] {safe_title}"

        # Build Body: Step -> Next [Status]
        # Example: write-tests -> run-tests [DONE ✅]
        body_part = f"{step} ➔ {next_step} [{status}]"

        if progress:
            completed, total = progress
            body_part += f"\nProgress: {completed}/{total}"

        # Send via the queue system
        self.send_background(NotificationType.STEP, body_part, title=title_part)

    def notify_failure_with_context(
        self,
        message: str,
        task_id: str | None = None,
        step: str | None = None,
    ) -> None:
        """Send failure notification with task context.

        Args:
            message: The failure message.
            task_id: Optional task ID.
            step: Optional step where failure occurred.
        """
        parts = [message]
        if task_id:
            parts.append(f"Task: {task_id}")
        if step:
            parts.append(f"Step: {step}")

        full_message = " | ".join(parts)
        self.send_background(NotificationType.FAILURE, full_message)
