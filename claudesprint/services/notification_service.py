"""Notification service for Bark push notifications and generic webhooks."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

import httpx

if TYPE_CHECKING:
    from claudesprint.services.configuration_manager import ConfigurationManager
    from claudesprint.services.project_config_service import (
        NotificationsConfig,
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


@dataclass
class WebhookPayload:
    """Payload for webhook notifications."""

    notification_type: str
    title: str
    message: str
    timestamp: str
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert payload to dictionary for JSON serialization."""
        result: dict[str, Any] = {
            "notification_type": self.notification_type,
            "title": self.title,
            "message": self.message,
            "timestamp": self.timestamp,
        }
        if self.metadata:
            result["metadata"] = self.metadata
        return result


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
        self._queue: asyncio.Queue[tuple[NotificationType, str, str | None, dict[str, Any] | None]] | None = None
        self._worker_task: asyncio.Task[None] | None = None
        self._http_timeout = http_timeout if http_timeout is not None else self.DEFAULT_HTTP_TIMEOUT

    @classmethod
    def from_config_manager(
        cls,
        config_manager: ConfigurationManager,
        http_timeout: float | None = None,
    ) -> NotificationService:
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
    def bark_enabled(self) -> bool:
        """Check if Bark notifications are enabled."""
        if not self._notifications_config:
            return False
        return (
            self._notifications_config.enabled
            and self._notifications_config.bark.enabled
            and bool(self._notifications_config.bark.url)
        )

    @property
    def webhook_enabled(self) -> bool:
        """Check if webhook notifications are enabled."""
        if not self._notifications_config:
            return False
        return (
            self._notifications_config.enabled
            and self._notifications_config.webhook.enabled
            and bool(self._notifications_config.webhook.url)
        )

    @property
    def enabled(self) -> bool:
        """Check if any notification provider is enabled."""
        return self.bark_enabled or self.webhook_enabled

    async def _send_bark(
        self,
        notification_type: NotificationType,
        message: str,
        title: str,
    ) -> bool:
        """Send a notification via Bark."""
        if not self.bark_enabled or not self._notifications_config:
            return False

        encoded_title = quote(title)
        encoded_message = quote(message)
        url = f"{self._notifications_config.bark.url}/{encoded_title}/{encoded_message}"

        try:
            async with httpx.AsyncClient(timeout=self._http_timeout) as client:
                response = await client.get(url)
                if response.status_code != 200:
                    logger.warning(
                        f"Bark notification failed: {notification_type} - HTTP {response.status_code}"
                    )
                    return False
                return True
        except Exception as e:
            logger.warning(f"Bark notification failed: {notification_type} - {e}")
            return False

    async def _send_webhook(
        self,
        notification_type: NotificationType,
        message: str,
        title: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Send a notification via generic webhook with retry logic."""
        if not self.webhook_enabled or not self._notifications_config:
            return False

        webhook_config = self._notifications_config.webhook

        # Check event filter
        if webhook_config.events and notification_type.value not in webhook_config.events:
            logger.debug(f"Webhook: skipping {notification_type} (not in event filter)")
            return True  # Not an error, just filtered

        # Build payload
        payload = WebhookPayload(
            notification_type=notification_type.value,
            title=title,
            message=message,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata=metadata,
        )

        # Send with retries (single client for connection pooling)
        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=webhook_config.timeout) as client:
            for attempt in range(webhook_config.retry_count + 1):
                try:
                    response = await client.post(
                        webhook_config.url,
                        json=payload.to_dict(),
                        headers=webhook_config.headers,
                    )
                    if response.status_code >= 200 and response.status_code < 300:
                        return True
                    logger.warning(
                        f"Webhook notification failed: {notification_type} - HTTP {response.status_code}"
                        f" (attempt {attempt + 1}/{webhook_config.retry_count + 1})"
                    )
                except Exception as e:
                    last_error = e
                    logger.warning(
                        f"Webhook notification error: {notification_type} - {e}"
                        f" (attempt {attempt + 1}/{webhook_config.retry_count + 1})"
                    )

                # Wait before retry (exponential backoff)
                if attempt < webhook_config.retry_count:
                    await asyncio.sleep(2 ** attempt)

        if last_error:
            logger.error(f"Webhook notification failed after {webhook_config.retry_count + 1} attempts: {last_error}")
        return False

    async def send(
        self,
        notification_type: NotificationType,
        message: str,
        title: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Send a notification asynchronously to all enabled providers."""
        if not self.enabled or not self._notifications_config:
            return False

        actual_title = title or self.TITLES.get(notification_type, "ClaudeSprint")

        # Send to all enabled providers
        results = await asyncio.gather(
            self._send_bark(notification_type, message, actual_title),
            self._send_webhook(notification_type, message, actual_title, metadata),
            return_exceptions=True,
        )

        # Log any exceptions that were returned
        for r in results:
            if isinstance(r, Exception):
                logger.error(f"Notification provider error: {notification_type} - {r}")

        # Return True if at least one provider succeeded
        return any(r is True for r in results)

    def _send_bark_sync(
        self,
        notification_type: NotificationType,
        message: str,
        title: str,
    ) -> bool:
        """Send a notification via Bark synchronously."""
        if not self.bark_enabled or not self._notifications_config:
            return False

        encoded_title = quote(title)
        encoded_message = quote(message)
        url = f"{self._notifications_config.bark.url}/{encoded_title}/{encoded_message}"

        try:
            with httpx.Client(timeout=self._http_timeout) as client:
                response = client.get(url)
                if response.status_code != 200:
                    logger.warning(
                        f"Bark notification failed: {notification_type} - HTTP {response.status_code}"
                    )
                    return False
            return True
        except Exception as e:
            logger.warning(f"Bark notification failed: {notification_type} - {e}")
            return False

    def _send_webhook_sync(
        self,
        notification_type: NotificationType,
        message: str,
        title: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Send a notification via webhook synchronously with retry logic."""
        if not self.webhook_enabled or not self._notifications_config:
            return False

        webhook_config = self._notifications_config.webhook

        # Check event filter
        if webhook_config.events and notification_type.value not in webhook_config.events:
            logger.debug(f"Webhook: skipping {notification_type} (not in event filter)")
            return True

        # Build payload
        payload = WebhookPayload(
            notification_type=notification_type.value,
            title=title,
            message=message,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata=metadata,
        )

        # Send with retries (single client for connection pooling)
        import time
        last_error: Exception | None = None
        with httpx.Client(timeout=webhook_config.timeout) as client:
            for attempt in range(webhook_config.retry_count + 1):
                try:
                    response = client.post(
                        webhook_config.url,
                        json=payload.to_dict(),
                        headers=webhook_config.headers,
                    )
                    if response.status_code >= 200 and response.status_code < 300:
                        return True
                    logger.warning(
                        f"Webhook notification failed: {notification_type} - HTTP {response.status_code}"
                        f" (attempt {attempt + 1}/{webhook_config.retry_count + 1})"
                    )
                except Exception as e:
                    last_error = e
                    logger.warning(
                        f"Webhook notification error: {notification_type} - {e}"
                        f" (attempt {attempt + 1}/{webhook_config.retry_count + 1})"
                    )

                if attempt < webhook_config.retry_count:
                    time.sleep(2 ** attempt)

        if last_error:
            logger.error(f"Webhook notification failed after {webhook_config.retry_count + 1} attempts: {last_error}")
        return False

    def send_sync(
        self,
        notification_type: NotificationType,
        message: str,
        title: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Send a notification synchronously to all enabled providers."""
        if not self.enabled or not self._notifications_config:
            return False

        actual_title = title or self.TITLES.get(notification_type, "ClaudeSprint")

        # Send to all enabled providers
        bark_result = self._send_bark_sync(notification_type, message, actual_title)
        webhook_result = self._send_webhook_sync(notification_type, message, actual_title, metadata)

        return bark_result or webhook_result

    def _ensure_worker_running(self) -> None:
        """Start the background worker if loop is running and worker is dead."""
        try:
            loop = asyncio.get_event_loop()
            if self._queue is None:
                self._queue = asyncio.Queue[tuple[NotificationType, str, str | None, dict[str, Any] | None]]()
            if self._worker_task is None or self._worker_task.done():
                self._worker_task = loop.create_task(self._consume_queue())
        except RuntimeError as e:
            logger.warning("Could not start notification worker (no event loop): %s. Notifications will use synchronous delivery.", e)

    async def _consume_queue(self) -> None:
        """Process notifications one by one to ensure FIFO ordering."""
        while True:
            if self._queue is None:
                break
            # Wait for next item
            notif_type, message, title, metadata = await self._queue.get()
            try:
                # Await the actual network call so strict ordering is preserved
                await self.send(notif_type, message, title, metadata)
            except Exception as e:
                logger.error(f"Notification worker error: {e}")
            finally:
                self._queue.task_done()

    def send_background(
        self,
        notification_type: NotificationType,
        message: str,
        title: str | None = None,
        metadata: dict[str, Any] | None = None,
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
                    self._queue.put_nowait((notification_type, message, title, metadata))
            else:
                # Fallback for synchronous contexts (e.g., startup/shutdown errors)
                self.send_sync(notification_type, message, title, metadata)
        except RuntimeError:
            # If no event loop, run synchronously
            self.send_sync(notification_type, message, title, metadata)

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

        # Build metadata for webhook
        metadata: dict[str, Any] = {
            "step": step,
            "next_step": next_step,
            "status": status,
        }
        if task_id:
            metadata["issue_id"] = task_id
        if task_title:
            metadata["issue_title"] = task_title
        if progress:
            metadata["progress"] = {"completed": progress[0], "total": progress[1]}

        # Send via the queue system
        self.send_background(NotificationType.STEP, body_part, title=title_part, metadata=metadata)

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

        # Build metadata for webhook
        metadata: dict[str, Any] = {"error": message}
        if task_id:
            metadata["issue_id"] = task_id
        if step:
            metadata["step"] = step

        self.send_background(NotificationType.FAILURE, full_message, metadata=metadata)
