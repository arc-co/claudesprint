"""Service container for dependency injection.

Reduces constructor parameter count by grouping related services
into cohesive containers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from claudesprint.core.claude_runner import ClaudeRunner
    from claudesprint.events.workflow_event_bus import WorkflowEventBus
    from claudesprint.services.configuration_manager import ConfigurationManager
    from claudesprint.services.git_service import GitService
    from claudesprint.services.issue_service import IssueService
    from claudesprint.services.notification_service import NotificationService
    from claudesprint.services.prompt_service import PromptService
    from claudesprint.services.sprint_service import SprintService


@dataclass(frozen=True)
class CoreServices:
    """Required core services for workflow engines.

    These services are essential for the workflow to function and must
    always be provided.

    Attributes:
        issue_service: Service for managing current issue state.
        sprint_service: Service for managing sprint data.
        notification_service: Service for sending notifications.
        prompt_service: Service for loading prompt templates.
        claude_runner: Runner for executing Claude commands.
    """

    issue_service: IssueService
    sprint_service: SprintService
    notification_service: NotificationService
    prompt_service: PromptService
    claude_runner: ClaudeRunner


@dataclass(frozen=True)
class OptionalServices:
    """Optional services for workflow engines.

    These services provide additional functionality but are not required
    for basic operation.

    Attributes:
        event_bus: Optional event bus for emitting workflow events.
        config_manager: Optional ConfigurationManager for model configuration.
        git_service: Optional GitService for git operations.
    """

    event_bus: WorkflowEventBus | None = None
    config_manager: ConfigurationManager | None = None
    git_service: GitService | None = None


@dataclass(frozen=True)
class ServiceContainer:
    """Container for all services needed by workflow engines.

    Groups services into core (required) and optional categories to reduce
    constructor parameter count while maintaining clear service dependencies.

    Example:
        >>> core = CoreServices(
        ...     issue_service=issue_svc,
        ...     sprint_service=sprint_svc,
        ...     notification_service=notif_svc,
        ...     prompt_service=prompt_svc,
        ...     claude_runner=runner,
        ... )
        >>> container = ServiceContainer(core=core)
        >>> engine = IssueEngine(config, execution_config, services=container)
    """

    core: CoreServices
    optional: OptionalServices = field(default_factory=OptionalServices)

    # Convenience properties for direct access to core services
    @property
    def issue_service(self) -> IssueService:
        """Access issue_service directly from container."""
        return self.core.issue_service

    @property
    def sprint_service(self) -> SprintService:
        """Access sprint_service directly from container."""
        return self.core.sprint_service

    @property
    def notification_service(self) -> NotificationService:
        """Access notification_service directly from container."""
        return self.core.notification_service

    @property
    def prompt_service(self) -> PromptService:
        """Access prompt_service directly from container."""
        return self.core.prompt_service

    @property
    def claude_runner(self) -> ClaudeRunner:
        """Access claude_runner directly from container."""
        return self.core.claude_runner

    # Convenience properties for direct access to optional services
    @property
    def event_bus(self) -> WorkflowEventBus | None:
        """Access event_bus directly from container."""
        return self.optional.event_bus

    @property
    def config_manager(self) -> ConfigurationManager | None:
        """Access config_manager directly from container."""
        return self.optional.config_manager

    @property
    def git_service(self) -> GitService | None:
        """Access git_service directly from container."""
        return self.optional.git_service

    @classmethod
    def create(
        cls,
        *,
        issue_service: IssueService,
        sprint_service: SprintService,
        notification_service: NotificationService,
        prompt_service: PromptService,
        claude_runner: ClaudeRunner,
        event_bus: WorkflowEventBus | None = None,
        config_manager: ConfigurationManager | None = None,
        git_service: GitService | None = None,
    ) -> ServiceContainer:
        """Factory method to create a ServiceContainer from individual services.

        This provides a convenient way to create a container without manually
        constructing CoreServices and OptionalServices.

        Args:
            issue_service: Service for managing current issue state.
            sprint_service: Service for managing sprint data.
            notification_service: Service for sending notifications.
            prompt_service: Service for loading prompt templates.
            claude_runner: Runner for executing Claude commands.
            event_bus: Optional event bus for workflow events.
            config_manager: Optional ConfigurationManager for model config.
            git_service: Optional GitService for git operations.

        Returns:
            A new ServiceContainer with the provided services.

        Example:
            >>> container = ServiceContainer.create(
            ...     issue_service=issue_svc,
            ...     sprint_service=sprint_svc,
            ...     notification_service=notif_svc,
            ...     prompt_service=prompt_svc,
            ...     claude_runner=runner,
            ...     event_bus=bus,
            ... )
        """
        core = CoreServices(
            issue_service=issue_service,
            sprint_service=sprint_service,
            notification_service=notification_service,
            prompt_service=prompt_service,
            claude_runner=claude_runner,
        )
        optional = OptionalServices(
            event_bus=event_bus,
            config_manager=config_manager,
            git_service=git_service,
        )
        return cls(core=core, optional=optional)
