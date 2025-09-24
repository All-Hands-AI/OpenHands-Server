from abc import ABC, abstractmethod
from typing import AsyncGenerator, Type
from uuid import UUID

from openhands_server.config import get_default_config
from openhands_server.conversation_callback.conversation_callback_models import (
    ConversationCallback,
    ConversationCallbackPage,
    CreateConversationCallbackRequest,
)
from openhands_server.utils.import_utils import get_impl


class ConversationCallbackContext(ABC):
    """
    Context for managing conversation callbacks. This provides CRUD operations
    for conversation callbacks, allowing creation, retrieval, updating, and deletion
    of callbacks associated with conversations.
    """

    @abstractmethod
    async def create_conversation_callback(
        self, request: CreateConversationCallbackRequest
    ) -> ConversationCallback:
        """Create a new conversation callback"""

    @abstractmethod
    async def get_conversation_callback(self, id: UUID) -> ConversationCallback | None:
        """Get a single conversation callback, returning None if not found."""

    @abstractmethod
    async def delete_conversation_callback(self, id: UUID) -> bool:
        """Delete a conversation callback, returning True if deleted, False if not found."""

    @abstractmethod
    async def search_conversation_callbacks(
        self,
        conversation_id: UUID | None = None,
        page_id: str | None = None,
        limit: int = 100,
    ) -> ConversationCallbackPage:
        """Search for conversation callbacks, optionally filtered by conversation_id"""

    async def batch_get_conversation_callbacks(
        self, ids: list[UUID]
    ) -> list[ConversationCallback | None]:
        """Get a batch of conversation callbacks, returning None for any callback which was not found"""  # noqa: E501
        results = []
        for id in ids:
            result = await self.get_conversation_callback(id)
            results.append(result)
        return results

    async def get_callbacks_for_conversation(
        self, conversation_id: UUID, page_id: str | None = None, limit: int = 100
    ) -> ConversationCallbackPage:
        """Get all callbacks for a specific conversation"""
        return await self.search_conversation_callbacks(
            conversation_id=conversation_id, page_id=page_id, limit=limit
        )

    # Lifecycle methods

    async def __aenter__(self):
        """Start using this conversation callback context"""
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        """Stop using this conversation callback context"""

    @classmethod
    @abstractmethod
    async def with_instance(
        cls, *args, **kwargs
    ) -> AsyncGenerator["ConversationCallbackContext", None]:
        """
        Get an instance of conversation callback context. Parameters are not specified
        so that they can be defined in the implementation classes and overridden using
        FastAPI's dependency injection. This allows merging global config with
        user / request specific variables.
        """


_conversation_callback_context_type: Type[ConversationCallbackContext] = None


def get_conversation_callback_context_type() -> Type[ConversationCallbackContext]:
    global _conversation_callback_context_type
    if _conversation_callback_context_type is None:
        config = get_default_config()
        _conversation_callback_context_type = get_impl(
            ConversationCallbackContext, config.conversation_callback_context_type
        )
    return _conversation_callback_context_type
