import functools
import logging
from dataclasses import MISSING, dataclass
from typing import Callable
from unittest.mock import MagicMock

from fastapi import FastAPI

from openhands_server.config import get_global_config
from openhands_server.event.event_context import EventContextFactory
from openhands_server.event_callback.event_callback_context import (
    EventCallbackContextFactory,
)
from openhands_server.event_callback.event_callback_result_context import (
    EventCallbackResultContextFactory,
)
from openhands_server.sandbox.sandbox_context import SandboxContextFactory
from openhands_server.sandbox.sandbox_spec_context import SandboxSpecContextFactory
from openhands_server.sandboxed_conversation.sandboxed_conversation_context import (
    SandboxedConversationContextFactory,
)


_logger = logging.getLogger(__name__)


@dataclass
class DependencyManager:
    """Object for exposing dependencies"""

    event: EventContextFactory
    event_callback: EventCallbackContextFactory
    event_callback_result: EventCallbackResultContextFactory
    sandbox: SandboxContextFactory
    sandbox_spec: SandboxSpecContextFactory
    sandboxed_conversation: SandboxedConversationContextFactory

    async def __aenter__(self, app: FastAPI):
        _logger.info("🙌  Starting dependency manager...")
        app.state.dependency_manager = self

    async def __aexit__(self, exc_type, exc_value, traceback):
        _logger.info("🙌  Stopping dependency manager...")


_dependency_manager: DependencyManager | None = None


def get_dependency_manager():
    """Get the dependency manager - lazily initializing it the first time
    it is requested"""
    global _dependency_manager
    if not _dependency_manager:
        config = get_global_config()
        _dependency_manager = DependencyManager(
            event=config.event or _get_event_context_factory(),
            event_callback=config.event_callback
            or _get_event_callback_context_factory(),
            event_callback_result=config.event_callback_result
            or _get_event_callback_result_context_factory(),
            sandbox=config.sandbox or _get_sandbox_context_factory(),
            sandbox_spec=config.sandbox_spec or _get_sandbox_spec_context_factory(),
            sandboxed_conversation=config.sandboxed_conversation
            or _get_sandboxed_conversation_context_factory(),
        )
    return _dependency_manager


class _LazyProxy:
    """
    Proxy which wraps a function, pretends to be its return value and executes it
    lazily only when an attribute of it is retrieved
    """

    def __init__(self, fn, *args, **kwargs):
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self._resolved = MISSING

    def __getattr__(self, name):
        resolved = self._resolved
        if resolved is MISSING:
            resolved = self._fn(*self._args, **self._kwargs)
            self._resolved = resolved
        return getattr(resolved, name)


def lazy_wrapper(fn: Callable):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return _LazyProxy(fn, args, kwargs)

    return wrapper


def _get_event_context_factory():
    from openhands_server.event.filesystem_event_context import (
        FilesystemEventContextFactory,
    )

    return FilesystemEventContextFactory()


def _get_event_callback_context_factory():
    from openhands_server.event_callback.sqlalchemy_event_callback_context import (
        SQLAlchemyEventCallbackContextFactory,
    )

    return SQLAlchemyEventCallbackContextFactory()


def _get_event_callback_result_context_factory():
    from openhands_server.event_callback import (
        sqlalchemy_event_callback_result_context as ctx,
    )

    return ctx.SQLAlchemyEventCallbackResultContextFactory()


def _get_sandbox_context_factory():
    from openhands_server.sandbox import (
        docker_sandbox_context as ctx,
    )

    return ctx.DockerSandboxContextFactory()


def _get_sandbox_spec_context_factory():
    from openhands_server.sandbox import (
        docker_sandbox_spec_context as ctx,
    )

    return ctx.DockerSandboxSpecContextFactory()


def _get_sandboxed_conversation_context_factory():
    return MagicMock()  # TODO: Replace with real implementation!
