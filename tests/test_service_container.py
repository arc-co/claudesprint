"""Tests for ServiceContainer."""

from unittest.mock import MagicMock

import pytest

from claudesprint.services.service_container import (
    CoreServices,
    OptionalServices,
    ServiceContainer,
)


@pytest.fixture
def mock_issue_service() -> MagicMock:
    """Create a mock IssueService."""
    return MagicMock()


@pytest.fixture
def mock_sprint_service() -> MagicMock:
    """Create a mock SprintService."""
    return MagicMock()


@pytest.fixture
def mock_notification_service() -> MagicMock:
    """Create a mock NotificationService."""
    return MagicMock()


@pytest.fixture
def mock_prompt_service() -> MagicMock:
    """Create a mock PromptService."""
    return MagicMock()


@pytest.fixture
def mock_claude_runner() -> MagicMock:
    """Create a mock ClaudeRunner."""
    return MagicMock()


@pytest.fixture
def mock_event_bus() -> MagicMock:
    """Create a mock WorkflowEventBus."""
    return MagicMock()


@pytest.fixture
def mock_config_manager() -> MagicMock:
    """Create a mock ConfigurationManager."""
    return MagicMock()


@pytest.fixture
def mock_git_service() -> MagicMock:
    """Create a mock GitService."""
    return MagicMock()


@pytest.fixture
def core_services(
    mock_issue_service: MagicMock,
    mock_sprint_service: MagicMock,
    mock_notification_service: MagicMock,
    mock_prompt_service: MagicMock,
    mock_claude_runner: MagicMock,
) -> CoreServices:
    """Create a CoreServices instance with mocks."""
    return CoreServices(
        issue_service=mock_issue_service,
        sprint_service=mock_sprint_service,
        notification_service=mock_notification_service,
        prompt_service=mock_prompt_service,
        claude_runner=mock_claude_runner,
    )


class TestCoreServices:
    """Tests for CoreServices dataclass."""

    def test_core_services_is_frozen(
        self,
        core_services: CoreServices,
    ) -> None:
        """CoreServices is immutable (frozen)."""
        with pytest.raises(AttributeError):
            core_services.issue_service = MagicMock()

    def test_core_services_stores_all_services(
        self,
        mock_issue_service: MagicMock,
        mock_sprint_service: MagicMock,
        mock_notification_service: MagicMock,
        mock_prompt_service: MagicMock,
        mock_claude_runner: MagicMock,
    ) -> None:
        """CoreServices stores all provided services."""
        core = CoreServices(
            issue_service=mock_issue_service,
            sprint_service=mock_sprint_service,
            notification_service=mock_notification_service,
            prompt_service=mock_prompt_service,
            claude_runner=mock_claude_runner,
        )

        assert core.issue_service is mock_issue_service
        assert core.sprint_service is mock_sprint_service
        assert core.notification_service is mock_notification_service
        assert core.prompt_service is mock_prompt_service
        assert core.claude_runner is mock_claude_runner


class TestOptionalServices:
    """Tests for OptionalServices dataclass."""

    def test_optional_services_defaults_to_none(self) -> None:
        """OptionalServices fields default to None."""
        optional = OptionalServices()

        assert optional.event_bus is None
        assert optional.config_manager is None
        assert optional.git_service is None

    def test_optional_services_is_frozen(
        self,
        mock_event_bus: MagicMock,
    ) -> None:
        """OptionalServices is immutable (frozen)."""
        optional = OptionalServices(event_bus=mock_event_bus)

        with pytest.raises(AttributeError):
            optional.event_bus = MagicMock()

    def test_optional_services_stores_provided_services(
        self,
        mock_event_bus: MagicMock,
        mock_config_manager: MagicMock,
        mock_git_service: MagicMock,
    ) -> None:
        """OptionalServices stores provided services."""
        optional = OptionalServices(
            event_bus=mock_event_bus,
            config_manager=mock_config_manager,
            git_service=mock_git_service,
        )

        assert optional.event_bus is mock_event_bus
        assert optional.config_manager is mock_config_manager
        assert optional.git_service is mock_git_service


class TestServiceContainer:
    """Tests for ServiceContainer dataclass."""

    def test_container_with_core_only(
        self,
        core_services: CoreServices,
    ) -> None:
        """Container can be created with core services only."""
        container = ServiceContainer(core=core_services)

        assert container.core is core_services
        assert container.optional.event_bus is None
        assert container.optional.config_manager is None

    def test_container_with_core_and_optional(
        self,
        core_services: CoreServices,
        mock_event_bus: MagicMock,
        mock_config_manager: MagicMock,
    ) -> None:
        """Container can be created with both core and optional services."""
        optional = OptionalServices(
            event_bus=mock_event_bus,
            config_manager=mock_config_manager,
        )
        container = ServiceContainer(core=core_services, optional=optional)

        assert container.core is core_services
        assert container.optional.event_bus is mock_event_bus
        assert container.optional.config_manager is mock_config_manager

    def test_container_is_frozen(
        self,
        core_services: CoreServices,
    ) -> None:
        """Container is immutable (frozen)."""
        container = ServiceContainer(core=core_services)

        with pytest.raises(AttributeError):
            container.core = MagicMock()


class TestServiceContainerConvenienceProperties:
    """Tests for ServiceContainer convenience properties."""

    def test_issue_service_property(
        self,
        core_services: CoreServices,
        mock_issue_service: MagicMock,
    ) -> None:
        """Container provides direct access to issue_service."""
        container = ServiceContainer(core=core_services)
        assert container.issue_service is mock_issue_service

    def test_sprint_service_property(
        self,
        core_services: CoreServices,
        mock_sprint_service: MagicMock,
    ) -> None:
        """Container provides direct access to sprint_service."""
        container = ServiceContainer(core=core_services)
        assert container.sprint_service is mock_sprint_service

    def test_notification_service_property(
        self,
        core_services: CoreServices,
        mock_notification_service: MagicMock,
    ) -> None:
        """Container provides direct access to notification_service."""
        container = ServiceContainer(core=core_services)
        assert container.notification_service is mock_notification_service

    def test_prompt_service_property(
        self,
        core_services: CoreServices,
        mock_prompt_service: MagicMock,
    ) -> None:
        """Container provides direct access to prompt_service."""
        container = ServiceContainer(core=core_services)
        assert container.prompt_service is mock_prompt_service

    def test_claude_runner_property(
        self,
        core_services: CoreServices,
        mock_claude_runner: MagicMock,
    ) -> None:
        """Container provides direct access to claude_runner."""
        container = ServiceContainer(core=core_services)
        assert container.claude_runner is mock_claude_runner

    def test_event_bus_property_when_set(
        self,
        core_services: CoreServices,
        mock_event_bus: MagicMock,
    ) -> None:
        """Container provides direct access to event_bus when set."""
        optional = OptionalServices(event_bus=mock_event_bus)
        container = ServiceContainer(core=core_services, optional=optional)
        assert container.event_bus is mock_event_bus

    def test_event_bus_property_when_not_set(
        self,
        core_services: CoreServices,
    ) -> None:
        """Container returns None for event_bus when not set."""
        container = ServiceContainer(core=core_services)
        assert container.event_bus is None

    def test_config_manager_property(
        self,
        core_services: CoreServices,
        mock_config_manager: MagicMock,
    ) -> None:
        """Container provides direct access to config_manager."""
        optional = OptionalServices(config_manager=mock_config_manager)
        container = ServiceContainer(core=core_services, optional=optional)
        assert container.config_manager is mock_config_manager

    def test_git_service_property(
        self,
        core_services: CoreServices,
        mock_git_service: MagicMock,
    ) -> None:
        """Container provides direct access to git_service."""
        optional = OptionalServices(git_service=mock_git_service)
        container = ServiceContainer(core=core_services, optional=optional)
        assert container.git_service is mock_git_service


class TestServiceContainerCreate:
    """Tests for ServiceContainer.create() factory method."""

    def test_create_with_core_services_only(
        self,
        mock_issue_service: MagicMock,
        mock_sprint_service: MagicMock,
        mock_notification_service: MagicMock,
        mock_prompt_service: MagicMock,
        mock_claude_runner: MagicMock,
    ) -> None:
        """Create method works with core services only."""
        container = ServiceContainer.create(
            issue_service=mock_issue_service,
            sprint_service=mock_sprint_service,
            notification_service=mock_notification_service,
            prompt_service=mock_prompt_service,
            claude_runner=mock_claude_runner,
        )

        assert container.issue_service is mock_issue_service
        assert container.sprint_service is mock_sprint_service
        assert container.notification_service is mock_notification_service
        assert container.prompt_service is mock_prompt_service
        assert container.claude_runner is mock_claude_runner
        assert container.event_bus is None
        assert container.config_manager is None
        assert container.git_service is None

    def test_create_with_all_services(
        self,
        mock_issue_service: MagicMock,
        mock_sprint_service: MagicMock,
        mock_notification_service: MagicMock,
        mock_prompt_service: MagicMock,
        mock_claude_runner: MagicMock,
        mock_event_bus: MagicMock,
        mock_config_manager: MagicMock,
        mock_git_service: MagicMock,
    ) -> None:
        """Create method works with all services."""
        container = ServiceContainer.create(
            issue_service=mock_issue_service,
            sprint_service=mock_sprint_service,
            notification_service=mock_notification_service,
            prompt_service=mock_prompt_service,
            claude_runner=mock_claude_runner,
            event_bus=mock_event_bus,
            config_manager=mock_config_manager,
            git_service=mock_git_service,
        )

        assert container.issue_service is mock_issue_service
        assert container.sprint_service is mock_sprint_service
        assert container.notification_service is mock_notification_service
        assert container.prompt_service is mock_prompt_service
        assert container.claude_runner is mock_claude_runner
        assert container.event_bus is mock_event_bus
        assert container.config_manager is mock_config_manager
        assert container.git_service is mock_git_service

    def test_create_is_equivalent_to_manual_construction(
        self,
        mock_issue_service: MagicMock,
        mock_sprint_service: MagicMock,
        mock_notification_service: MagicMock,
        mock_prompt_service: MagicMock,
        mock_claude_runner: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Create method produces equivalent result to manual construction."""
        container_via_create = ServiceContainer.create(
            issue_service=mock_issue_service,
            sprint_service=mock_sprint_service,
            notification_service=mock_notification_service,
            prompt_service=mock_prompt_service,
            claude_runner=mock_claude_runner,
            event_bus=mock_event_bus,
        )

        core = CoreServices(
            issue_service=mock_issue_service,
            sprint_service=mock_sprint_service,
            notification_service=mock_notification_service,
            prompt_service=mock_prompt_service,
            claude_runner=mock_claude_runner,
        )
        optional = OptionalServices(event_bus=mock_event_bus)
        container_manual = ServiceContainer(core=core, optional=optional)

        # Both should have the same services
        assert container_via_create.issue_service is container_manual.issue_service
        assert container_via_create.sprint_service is container_manual.sprint_service
        assert container_via_create.event_bus is container_manual.event_bus
