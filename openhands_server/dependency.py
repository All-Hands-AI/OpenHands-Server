import logging
from dataclasses import dataclass
from unittest.mock import MagicMock

from openhands_server.config import get_global_config
from openhands_server.event.event_service import EventServiceResolver
from openhands_server.event_callback.event_callback_result_service import (
    EventCallbackResultServiceResolver,
)
from openhands_server.event_callback.event_callback_service import (
    EventCallbackServiceResolver,
)
from openhands_server.sandbox.sandbox_service import SandboxServiceResolver
from openhands_server.sandbox.sandbox_spec_service import SandboxSpecServiceResolver
from openhands_server.sandboxed_conversation.sandboxed_conversation_service import (
    SandboxedConversationServiceResolver,
)
from openhands_server.user.user_service import UserServiceResolver


_logger = logging.getLogger(__name__)


@dataclass
class DependencyResolver:
    """Object for exposing dependencies and preventing circular imports and lookups"""

    event: EventServiceResolver
    event_callback: EventCallbackServiceResolver
    event_callback_result: EventCallbackResultServiceResolver
    sandbox: SandboxServiceResolver
    sandbox_spec: SandboxSpecServiceResolver
    sandboxed_conversation: SandboxedConversationServiceResolver
    user: UserServiceResolver


_dependency_resolver: DependencyResolver | None = None


def get_dependency_resolver():
    """Get the dependency manager - lazily initializing it the first time
    it is requested"""
    global _dependency_resolver
    if not _dependency_resolver:
        config = get_global_config()
        _dependency_resolver = DependencyResolver(
            event=config.event or _get_event_service_factory(),
            event_callback=config.event_callback
            or _get_event_callback_service_factory(),
            event_callback_result=config.event_callback_result
            or _get_event_callback_result_service_factory(),
            sandbox=config.sandbox or _get_sandbox_service_factory(),
            sandbox_spec=config.sandbox_spec or _get_sandbox_spec_service_factory(),
            sandboxed_conversation=config.sandboxed_conversation
            or _get_sandboxed_conversation_service_factory(),
            user=config.user or _get_user_service_factory(),
        )
    return _dependency_resolver


def _get_event_service_factory():
    from openhands_server.event.filesystem_event_service import (
        FilesystemEventServiceResolver,
    )

    return FilesystemEventServiceResolver()


def _get_event_callback_service_factory():
    from openhands_server.event_callback.sql_event_callback_service import (
        SQLEventCallbackServiceResolver,
    )

    return SQLEventCallbackServiceResolver()


def _get_event_callback_result_service_factory():
    from openhands_server.event_callback import (
        sql_event_callback_result_service as ctx,
    )

    return ctx.SQLEventCallbackResultServiceResolver()


def _get_sandbox_service_factory():
    from openhands_server.sandbox import (
        docker_sandbox_service as ctx,
    )

    return ctx.DockerSandboxServiceResolver()


def _get_sandbox_spec_service_factory():
    from openhands_server.sandbox import (
        docker_sandbox_spec_service as ctx,
    )

    return ctx.DockerSandboxSpecServiceResolver()


def _get_sandboxed_conversation_service_factory():
    return MagicMock()  # TODO: Replace with real implementation!


def _get_user_service_factory():
    from openhands_server.user.sql_user_service import (
        SQLUserServiceResolver,
    )

    return SQLUserServiceResolver()
