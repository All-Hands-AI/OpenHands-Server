import asyncio
from abc import ABC, abstractmethod
from typing import AsyncGenerator
from uuid import UUID

from openhands.sdk.utils.models import DiscriminatedUnionMixin
from openhands_server.event_callback.event_callback_models import (
    CreateEventCallbackRequest,
    EventCallback,
    EventCallbackPage,
    EventKind,
)


class EventCallbackContext(ABC):
    """
    Context for managing event callbacks. This provides CRUD operations
    for event callbacks, allowing creation, retrieval, updating, and deletion
    of callbacks associated with events.
    """

    @abstractmethod
    async def create_event_callback(
        self, request: CreateEventCallbackRequest
    ) -> EventCallback:
        """Create a new event callback"""

    @abstractmethod
    async def get_event_callback(self, id: UUID) -> EventCallback | None:
        """Get a single event callback, returning None if not found."""

    @abstractmethod
    async def delete_event_callback(self, id: UUID) -> bool:
        """Delete a event callback, returning True if deleted, False if not found."""

    @abstractmethod
    async def search_event_callbacks(
        self,
        conversation_id__eq: UUID | None = None,
        event_kind__eq: EventKind | None = None,
        event_id__eq: UUID | None = None,
        page_id: str | None = None,
        limit: int = 100,
    ) -> EventCallbackPage:
        """Search for event callbacks, optionally filtered by event_id"""

    async def batch_get_event_callbacks(
        self, event_callback_ids: list[UUID]
    ) -> list[EventCallback | None]:
        """Get a batch of event callbacks, returning None for any callback which was
        not found"""
        results = await asyncio.gather(
            *[
                self.get_event_callback(event_callback_id)
                for event_callback_id in event_callback_ids
            ]
        )
        return results

    # Lifecycle methods

    async def __aenter__(self):
        """Start using this event callback context"""
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        """Stop using this event callback context"""


class EventCallbackContextFactory(DiscriminatedUnionMixin, ABC):
    @abstractmethod
    async def with_instance(
        self, *args, **kwargs
    ) -> AsyncGenerator["EventCallbackContext", None]:
        """
        Get an instance of event callback context. Parameters are not specified
        so that they can be defined in the implementation classes and overridden using
        FastAPI's dependency injection. This allows merging global config with
        user / request specific variables.
        """
        yield EventCallbackContext()  # type: ignore
