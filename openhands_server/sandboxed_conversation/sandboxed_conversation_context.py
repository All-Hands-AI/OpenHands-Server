import asyncio
from abc import ABC, abstractmethod
from typing import AsyncGenerator
from uuid import UUID

from openhands.sdk.utils.models import DiscriminatedUnionMixin
from openhands_server.sandboxed_conversation.sandboxed_conversation_models import (
    SandboxedConversationInfo,
    SandboxedConversationPage,
    StartSandboxedConversationRequest,
)


class SandboxedConversationContext(ABC):
    """
    Context for accessing conversations running in sandboxes to which the user has
    access
    """

    @abstractmethod
    async def search_sandboxed_conversations(
        self,
        page_id: str | None = None,
        limit: int = 100,
    ) -> SandboxedConversationPage:
        """Search for sandboxed conversations."""

    @abstractmethod
    async def get_sandboxed_conversation(
        self, conversation_id: UUID
    ) -> SandboxedConversationInfo | None:
        """Get a single sandboxed conversation info. Return None if the conversation
        was not found."""

    async def batch_get_sandboxed_conversations(
        self, conversation_ids: list[UUID]
    ) -> list[SandboxedConversationInfo | None]:
        """Get a batch of sandboxed conversations. Return None for any conversation
        which was not found."""
        return await asyncio.gather(
            *[
                self.get_sandboxed_conversation(conversation_id)
                for conversation_id in conversation_ids
            ]
        )

    @abstractmethod
    async def start_sandboxed_conversation(
        self, request: StartSandboxedConversationRequest
    ):
        """Start a conversation, optionally specifying a sandbox in which to start. If
        no sandbox is specified a default may be used or started. This is a convenience
        method - the same effect should be achievable by creating / getting a sandbox
        id, starting a conversation, attaching a callback, and then running the
        conversation."""

    # Lifecycle methods

    async def __aenter__(self):
        """Start using this sandbox context"""
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        """Stop using this sandbox context"""


class SandboxedConversationContextFactory(DiscriminatedUnionMixin, ABC):
    @abstractmethod
    async def with_instance(
        self, *args, **kwargs
    ) -> AsyncGenerator["SandboxedConversationContext", None]:
        """
        Get an instance of event callback result context. Parameters are not
        specified so that they can be defined in the implementation classes and
        overridden using FastAPI's dependency injection. This allows merging global
        config with user / request specific variables.
        """
        yield SandboxedConversationContext()  # type: ignore
