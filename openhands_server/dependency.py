import logging
from dataclasses import dataclass
from unittest.mock import MagicMock

from openhands_server.config import get_global_config
from openhands_server.event.event_context import EventContextResolver
from openhands_server.event_callback.event_callback_context import (
    EventCallbackContextResolver,
)
from openhands_server.event_callback.event_callback_result_context import (
    EventCallbackResultContextResolver,
)
from openhands_server.sandbox.sandbox_context import SandboxContextResolver
from openhands_server.sandbox.sandbox_spec_service import SandboxSpecServiceResolver
from openhands_server.sandboxed_conversation.sandboxed_conversation_context import (
    SandboxedConversationContextResolver,
)
from openhands_server.user.user_context import UserContextResolver


_logger = logging.getLogger(__name__)


@dataclass
class DependencyResolver:
    """Object for exposing dependencies and preventing circular imports and lookups"""

    event: EventContextResolver
    event_callback: EventCallbackContextResolver
    event_callback_result: EventCallbackResultContextResolver
    sandbox: SandboxContextResolver
    sandbox_spec: SandboxSpecServiceResolver
    sandboxed_conversation: SandboxedConversationContextResolver
    user: UserContextResolver


_dependency_resolver: DependencyResolver | None = None


def get_dependency_resolver():
    """Get the dependency manager - lazily initializing it the first time
    it is requested"""
    global _dependency_resolver
    if not _dependency_resolver:
        config = get_global_config()
        _dependency_resolver = DependencyResolver(
            event=config.event or _get_event_context_factory(),
            event_callback=config.event_callback
            or _get_event_callback_context_factory(),
            event_callback_result=config.event_callback_result
            or _get_event_callback_result_context_factory(),
            sandbox=config.sandbox or _get_sandbox_context_factory(),
            sandbox_spec=config.sandbox_spec or _get_sandbox_spec_service_factory(),
            sandboxed_conversation=config.sandboxed_conversation
            or _get_sandboxed_conversation_context_factory(),
            user=config.user or _get_user_context_factory(),
        )
    return _dependency_resolver


def _get_event_context_factory():
    from openhands_server.event.filesystem_event_context import (
        FilesystemEventContextResolver,
    )

    return FilesystemEventContextResolver()


def _get_event_callback_context_factory():
    from openhands_server.event_callback.sqlalchemy_event_callback_context import (
        SQLAlchemyEventCallbackContextResolver,
    )

    return SQLAlchemyEventCallbackContextResolver()


def _get_event_callback_result_context_factory():
    from openhands_server.event_callback import (
        sqlalchemy_event_callback_result_context as ctx,
    )

    return ctx.SQLAlchemyEventCallbackResultContextResolver()


def _get_sandbox_context_factory():
    from openhands_server.sandbox import (
        docker_sandbox_context as ctx,
    )

    return ctx.DockerSandboxContextResolver()


def _get_sandbox_spec_service_factory():
    from openhands_server.sandbox import (
        docker_sandbox_spec_service as ctx,
    )

    return ctx.DockerSandboxSpecServiceResolver()


def _get_sandboxed_conversation_context_factory():
    return MagicMock()  # TODO: Replace with real implementation!


def _get_user_context_factory():
    from openhands_server.user.sqlalchemy_user_context import (
        SQLAlchemyUserContextResolver,
    )

    return SQLAlchemyUserContextResolver()
