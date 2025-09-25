from abc import ABC, abstractmethod
from typing import Type
from uuid import UUID

from openhands_server.config import get_global_config
from openhands_server.sandboxed_conversation.sandboxed_conversation_models import (
    SandboxedConversationInfo,
    SandboxedConversationPage,
    StartSandboxedConversationRequest,
)
from openhands_server.utils.import_utils import get_impl


class SandboxedConversationContext(ABC):
    """
    Context for accessing conversations running in sandboxes to which the user has access
    """  # noqa: E501

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
        """Get a single sandboxed conversation info. Return None if the conversation was not found."""  # noqa: E501

    @abstractmethod
    async def batch_get_sandboxed_conversations(
        self, conversation_ids: list[UUID]
    ) -> list[SandboxedConversationInfo | None]:
        """Get a batch of sandboxed conversations. Return None for any conversation which was not found."""  # noqa: E501
        results = []
        for conversation_id in conversation_ids:
            result = await self.get_sandboxed_conversation(conversation_id)
            results.append(result)
        return results

    @abstractmethod
    async def start_sandboxed_conversation(request: StartSandboxedConversationRequest):
        """Start a conversation, optionally specifying a sandbox in which to start. If no sandbox
        is specified a default may be used or started. This is a convenience method - the same
        effect should be achievable by creating / getting a sandbox id, starting a conversation,
        attaching a callback, and then running the conversation."""  # noqa: E501

    # Lifecycle methods

    async def __aenter__(self):
        """Start using this sandbox context"""
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        """Stop using this sandbox context"""

    @classmethod
    @abstractmethod
    def get_instance(cls, *args, **kwargs) -> "SandboxedConversationContext":
        """Get an instance of sandbox context"""


_sandboxed_conversation_context_type: Type[SandboxedConversationContext] = None


async def get_sandboxed_conversation_context_type() -> Type[
    SandboxedConversationContext
]:
    global _sandboxed_conversation_context_type
    if _sandboxed_conversation_context_type is None:
        config = get_global_config()
        _sandboxed_conversation_context_type = get_impl(
            SandboxedConversationContext, config.sandboxed_conversation_context_type
        )
    return await _sandboxed_conversation_context_type


async def sandboxed_conversation_context_dependency(*args, **kwargs):
    context = get_sandboxed_conversation_context_type().get_instance(args, kwargs)
    async with context:
        yield context
