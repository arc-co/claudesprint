"""Tests for notification service with webhook support."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from claudesprint.services.notification_service import (
    NotificationService,
    NotificationType,
    WebhookPayload,
)
from claudesprint.services.project_config_service import (
    BarkNotificationConfig,
    NotificationsConfig,
    WebhookNotificationConfig,
)


class TestWebhookPayload:
    """Tests for WebhookPayload dataclass."""

    def test_to_dict_without_metadata(self) -> None:
        """Test to_dict without metadata."""
        payload = WebhookPayload(
            notification_type="step",
            title="Test Title",
            message="Test message",
            timestamp="2026-02-01T12:00:00+00:00",
        )

        result = payload.to_dict()

        assert result == {
            "notification_type": "step",
            "title": "Test Title",
            "message": "Test message",
            "timestamp": "2026-02-01T12:00:00+00:00",
        }

    def test_to_dict_with_metadata(self) -> None:
        """Test to_dict with metadata."""
        payload = WebhookPayload(
            notification_type="step",
            title="Test Title",
            message="Test message",
            timestamp="2026-02-01T12:00:00+00:00",
            metadata={"issue_id": "feature-001", "step": "implement"},
        )

        result = payload.to_dict()

        assert result == {
            "notification_type": "step",
            "title": "Test Title",
            "message": "Test message",
            "timestamp": "2026-02-01T12:00:00+00:00",
            "metadata": {"issue_id": "feature-001", "step": "implement"},
        }


class TestNotificationServiceProperties:
    """Tests for notification service enabled properties."""

    def test_bark_enabled_when_configured(self) -> None:
        """Test bark_enabled returns True when fully configured."""
        service = NotificationService()
        service._notifications_config = NotificationsConfig(
            enabled=True,
            bark=BarkNotificationConfig(enabled=True, url="https://api.day.app/KEY"),
        )

        assert service.bark_enabled is True

    def test_bark_enabled_false_when_global_disabled(self) -> None:
        """Test bark_enabled returns False when global notifications disabled."""
        service = NotificationService()
        service._notifications_config = NotificationsConfig(
            enabled=False,
            bark=BarkNotificationConfig(enabled=True, url="https://api.day.app/KEY"),
        )

        assert service.bark_enabled is False

    def test_bark_enabled_false_when_no_url(self) -> None:
        """Test bark_enabled returns False when URL is empty."""
        service = NotificationService()
        service._notifications_config = NotificationsConfig(
            enabled=True,
            bark=BarkNotificationConfig(enabled=True, url=""),
        )

        assert service.bark_enabled is False

    def test_webhook_enabled_when_configured(self) -> None:
        """Test webhook_enabled returns True when fully configured."""
        service = NotificationService()
        service._notifications_config = NotificationsConfig(
            enabled=True,
            webhook=WebhookNotificationConfig(
                enabled=True, url="https://webhook.example.com"
            ),
        )

        assert service.webhook_enabled is True

    def test_webhook_enabled_false_when_global_disabled(self) -> None:
        """Test webhook_enabled returns False when global notifications disabled."""
        service = NotificationService()
        service._notifications_config = NotificationsConfig(
            enabled=False,
            webhook=WebhookNotificationConfig(
                enabled=True, url="https://webhook.example.com"
            ),
        )

        assert service.webhook_enabled is False

    def test_webhook_enabled_false_when_no_url(self) -> None:
        """Test webhook_enabled returns False when URL is empty."""
        service = NotificationService()
        service._notifications_config = NotificationsConfig(
            enabled=True,
            webhook=WebhookNotificationConfig(enabled=True, url=""),
        )

        assert service.webhook_enabled is False

    def test_enabled_true_when_bark_enabled(self) -> None:
        """Test enabled returns True when only Bark is enabled."""
        service = NotificationService()
        service._notifications_config = NotificationsConfig(
            enabled=True,
            bark=BarkNotificationConfig(enabled=True, url="https://api.day.app/KEY"),
            webhook=WebhookNotificationConfig(enabled=False),
        )

        assert service.enabled is True

    def test_enabled_true_when_webhook_enabled(self) -> None:
        """Test enabled returns True when only webhook is enabled."""
        service = NotificationService()
        service._notifications_config = NotificationsConfig(
            enabled=True,
            bark=BarkNotificationConfig(enabled=False),
            webhook=WebhookNotificationConfig(
                enabled=True, url="https://webhook.example.com"
            ),
        )

        assert service.enabled is True

    def test_enabled_true_when_both_enabled(self) -> None:
        """Test enabled returns True when both providers are enabled."""
        service = NotificationService()
        service._notifications_config = NotificationsConfig(
            enabled=True,
            bark=BarkNotificationConfig(enabled=True, url="https://api.day.app/KEY"),
            webhook=WebhookNotificationConfig(
                enabled=True, url="https://webhook.example.com"
            ),
        )

        assert service.enabled is True

    def test_enabled_false_when_none_configured(self) -> None:
        """Test enabled returns False when no providers are configured."""
        service = NotificationService()
        service._notifications_config = NotificationsConfig(
            enabled=True,
            bark=BarkNotificationConfig(enabled=False),
            webhook=WebhookNotificationConfig(enabled=False),
        )

        assert service.enabled is False


class TestWebhookEventFiltering:
    """Tests for webhook event filtering."""

    @pytest.mark.asyncio
    async def test_webhook_skips_filtered_events(self) -> None:
        """Test webhook skips events not in the filter list."""
        service = NotificationService()
        service._notifications_config = NotificationsConfig(
            enabled=True,
            webhook=WebhookNotificationConfig(
                enabled=True,
                url="https://webhook.example.com",
                events=["failure", "exit"],  # Only failure and exit
            ),
        )

        # STEP is not in the events list, should be skipped (return True)
        result = await service._send_webhook(
            NotificationType.STEP,
            "Test message",
            "Test Title",
        )

        assert result is True  # Filtered events return True (not an error)

    @pytest.mark.asyncio
    async def test_webhook_sends_when_event_matches_filter(self) -> None:
        """Test webhook sends when event matches filter."""
        service = NotificationService()
        service._notifications_config = NotificationsConfig(
            enabled=True,
            webhook=WebhookNotificationConfig(
                enabled=True,
                url="https://webhook.example.com",
                events=["failure", "exit"],
                retry_count=0,
            ),
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            result = await service._send_webhook(
                NotificationType.FAILURE,  # In the events list
                "Test failure",
                "Test Title",
            )

            assert result is True
            mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_webhook_sends_all_when_no_filter(self) -> None:
        """Test webhook sends all events when filter is empty."""
        service = NotificationService()
        service._notifications_config = NotificationsConfig(
            enabled=True,
            webhook=WebhookNotificationConfig(
                enabled=True,
                url="https://webhook.example.com",
                events=[],  # Empty = all events
                retry_count=0,
            ),
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            result = await service._send_webhook(
                NotificationType.STEP,  # Should be sent when no filter
                "Test step",
                "Test Title",
            )

            assert result is True
            mock_client.post.assert_called_once()


class TestWebhookRetryLogic:
    """Tests for webhook retry logic."""

    @pytest.mark.asyncio
    async def test_webhook_retries_on_failure(self) -> None:
        """Test webhook retries on HTTP failure."""
        service = NotificationService()
        service._notifications_config = NotificationsConfig(
            enabled=True,
            webhook=WebhookNotificationConfig(
                enabled=True,
                url="https://webhook.example.com",
                retry_count=2,
            ),
        )

        with patch("httpx.AsyncClient") as mock_client_class, patch(
            "asyncio.sleep", new_callable=AsyncMock
        ) as mock_sleep:
            # All attempts fail
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            result = await service._send_webhook(
                NotificationType.STEP,
                "Test message",
                "Test Title",
            )

            assert result is False
            # Should have made 3 attempts (1 initial + 2 retries)
            assert mock_client.post.call_count == 3
            # Should have slept twice (between retries)
            assert mock_sleep.call_count == 2

    @pytest.mark.asyncio
    async def test_webhook_succeeds_on_retry(self) -> None:
        """Test webhook succeeds after initial failure."""
        service = NotificationService()
        service._notifications_config = NotificationsConfig(
            enabled=True,
            webhook=WebhookNotificationConfig(
                enabled=True,
                url="https://webhook.example.com",
                retry_count=2,
            ),
        )

        with patch("httpx.AsyncClient") as mock_client_class, patch(
            "asyncio.sleep", new_callable=AsyncMock
        ):
            # First call fails, second succeeds
            mock_response_fail = MagicMock()
            mock_response_fail.status_code = 500
            mock_response_success = MagicMock()
            mock_response_success.status_code = 200

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=[mock_response_fail, mock_response_success]
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            result = await service._send_webhook(
                NotificationType.STEP,
                "Test message",
                "Test Title",
            )

            assert result is True
            assert mock_client.post.call_count == 2


class TestWebhookPayloadContent:
    """Tests for webhook payload content."""

    @pytest.mark.asyncio
    async def test_webhook_sends_correct_payload(self) -> None:
        """Test webhook sends correctly formatted payload."""
        service = NotificationService()
        service._notifications_config = NotificationsConfig(
            enabled=True,
            webhook=WebhookNotificationConfig(
                enabled=True,
                url="https://webhook.example.com",
                headers={"Authorization": "Bearer token123"},
                retry_count=0,
            ),
        )

        captured_payload = None
        captured_headers = None

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200

            async def capture_post(url, json, headers):
                nonlocal captured_payload, captured_headers
                captured_payload = json
                captured_headers = headers
                return mock_response

            mock_client = AsyncMock()
            mock_client.post = capture_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            await service._send_webhook(
                NotificationType.STEP,
                "Test message",
                "Test Title",
                metadata={"issue_id": "feature-001"},
            )

            assert captured_payload is not None
            assert captured_payload["notification_type"] == "step"
            assert captured_payload["title"] == "Test Title"
            assert captured_payload["message"] == "Test message"
            assert "timestamp" in captured_payload
            assert captured_payload["metadata"] == {"issue_id": "feature-001"}
            assert captured_headers == {"Authorization": "Bearer token123"}


class TestNotifyStepWithContextMetadata:
    """Tests for notify_step_with_context metadata."""

    def test_notify_step_with_context_builds_metadata(self) -> None:
        """Test notify_step_with_context builds correct metadata."""
        service = NotificationService()
        service._notifications_config = NotificationsConfig(
            enabled=True,
            webhook=WebhookNotificationConfig(
                enabled=True, url="https://webhook.example.com"
            ),
        )

        captured_metadata = None

        def capture_send_background(notif_type, message, title=None, metadata=None):
            nonlocal captured_metadata
            captured_metadata = metadata

        service.send_background = capture_send_background

        service.notify_step_with_context(
            step="implement",
            next_step="write-tests",
            task_id="feature-001",
            task_title="Add Login Page",
            progress=(3, 5),
            status="COMPLETE",
        )

        assert captured_metadata == {
            "step": "implement",
            "next_step": "write-tests",
            "status": "COMPLETE",
            "issue_id": "feature-001",
            "issue_title": "Add Login Page",
            "progress": {"completed": 3, "total": 5},
        }


class TestNotifyFailureWithContextMetadata:
    """Tests for notify_failure_with_context metadata."""

    def test_notify_failure_with_context_builds_metadata(self) -> None:
        """Test notify_failure_with_context builds correct metadata."""
        service = NotificationService()
        service._notifications_config = NotificationsConfig(
            enabled=True,
            webhook=WebhookNotificationConfig(
                enabled=True, url="https://webhook.example.com"
            ),
        )

        captured_metadata = None

        def capture_send_background(notif_type, message, title=None, metadata=None):
            nonlocal captured_metadata
            captured_metadata = metadata

        service.send_background = capture_send_background

        service.notify_failure_with_context(
            message="Tests failed",
            task_id="feature-001",
            step="write-tests",
        )

        assert captured_metadata == {
            "error": "Tests failed",
            "issue_id": "feature-001",
            "step": "write-tests",
        }
