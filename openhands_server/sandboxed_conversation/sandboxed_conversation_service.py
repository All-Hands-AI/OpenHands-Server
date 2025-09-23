from abc import ABC, abstractmethod
from uuid import UUID

from openhands_server.event.read_only_event_context import ReadOnlyEventContext
from openhands_server.sandboxed_conversation.sandboxed_conversation_models import (
    SandboxedConversationInfo,
    SandboxedConversationPage,
)
from openhands_server.utils.import_utils import get_impl


class SandboxedConversationService(ABC):
    """
    Service for interacting with sandboxed conversations.
    """

    @abstractmethod
    async def search_sandboxed_conversations(
        self, user_id: UUID | None = None, page_id: str | None = None, limit: int = 100
    ) -> SandboxedConversationPage:
        """Search for sandboxed conversations"""

    @abstractmethod
    async def get_sandboxed_conversation(
        self, user_id: UUID, conversation_id: UUID
    ) -> SandboxedConversationInfo | None:
        """Get a single sandboxed conversation info. Return None if the conversation was not found."""

    @abstractmethod
    async def batch_get_sandboxed_conversations(
        self, user_id: UUID, conversation_ids: list[UUID]
    ) -> list[SandboxedConversationInfo | None]:
        """Get a batch of sandboxed conversations. Return None for any conversation which was not found."""
        results = []
        for conversation_id in conversation_ids:
            result = await self.get_sandboxed_conversation(user_id, conversation_id)
            results.append(result)
        return results

    # Event methods...

    @abstractmethod
    async def get_event_context(self, id: UUID) -> ReadOnlyEventContext | None:
        """Get an event service for a conversation."""

    # Lifecycle methods

    async def __aenter__(self):
        """Start using this sandboxed conversation service"""
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        """Stop using this sandboxed conversation service"""

    @classmethod
    @abstractmethod
    def get_instance(cls) -> "SandboxedConversationService":
        """Get an instance of sandboxed conversation service"""


_sandboxed_conversation_service: SandboxedConversationService = None


def get_default_sandboxed_conversation_service() -> SandboxedConversationService:
    global _sandboxed_conversation_service
    if _sandboxed_conversation_service:
        return _sandboxed_conversation_service
    _sandboxed_conversation_service = get_impl(SandboxedConversationService)
    return _sandboxed_conversation_service
