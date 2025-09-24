from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Type
from uuid import UUID

from openhands.sdk.event.types import EventID
from openhands_server.config import get_default_config
from openhands_server.event_callback_result.event_callback_result_models import (
    EventCallbackResult,
    EventCallbackResultPage,
    EventCallbackResultSortOrder,
)
from openhands_server.utils.import_utils import get_impl


class EventCallbackResultContext(ABC):
    """
    This context provides retrieval operations for event callback results available to
    the current user
    """

    @abstractmethod
    async def get_event_callback_result(self, id: UUID) -> EventCallbackResult | None:
        """Get a single event callback result, returning None if not found."""

    @abstractmethod
    async def search_event_callback_results(
        self,
        event_callback_id__eq: UUID | None = None,
        event_id__eq: EventID | None = None,
        conversation_id__eq: UUID | None = None,
        sort_order: EventCallbackResultSortOrder = (
            EventCallbackResultSortOrder.TIMESTAMP
        ),
        page_id: str | None = None,
        limit: int = 100,
    ) -> EventCallbackResultPage:
        """Search for event callback results, optionally filtered by
        callback_id, event_id or conversation_id, and sorting by timestamp
        ascending or descending"""

    async def batch_get_conversation_callbacks(
        self, ids: list[UUID]
    ) -> list[EventCallbackResult | None]:
        """Get a batch of event callback results, returning None for any
        result which was not found"""
        results = []
        for id in ids:
            result = await self.get_event_callback_result(id)
            results.append(result)
        return results

    @abstractmethod
    async def delete_event_callback_result(self, id: UUID) -> bool:
        """Delete an event callback result, returning True if deleted,
        False if not found."""

    # Lifecycle methods

    async def __aenter__(self):
        """Start using this context"""
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        """Stop using this context"""

    @classmethod
    @abstractmethod
    async def with_instance(
        cls, *args, **kwargs
    ) -> AsyncGenerator[EventCallbackResultContext, None]:
        """
        Get an instance of conversation callback result context. Parameters are not
        specified so that they can be defined in the implementation classes and
        overridden using FastAPI's dependency injection. This allows merging global
        config with user / request specific variables.
        """


_event_callback_result_context_type: Type[EventCallbackResultContext] | None = None


def get_event_callback_result_context_type() -> Type[EventCallbackResultContext]:
    global _event_callback_result_context_type
    if _event_callback_result_context_type is None:
        config = get_default_config()
        _event_callback_result_context_type = get_impl(
            EventCallbackResultContext, config.event_callback_result_context_type
        )
    return _event_callback_result_context_type
