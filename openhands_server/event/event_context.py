import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from typing import AsyncGenerator
from uuid import UUID

from openhands.agent_server.models import EventPage, EventSortOrder
from openhands.sdk import EventBase
from openhands.sdk.utils.models import DiscriminatedUnionMixin
from openhands_server.event_callback.event_callback_models import EventKind


class EventContext(ABC):
    """Event Context for getting events"""

    @abstractmethod
    async def get_event(self, event_id: str) -> EventBase | None:
        """Given an id, retrieve an event"""

    @abstractmethod
    async def search_events(
        self,
        conversation_id__eq: UUID | None = None,
        kind__eq: EventKind | None = None,
        timestamp__gte: datetime | None = None,
        timestamp__lt: datetime | None = None,
        sort_order: EventSortOrder = EventSortOrder.TIMESTAMP,
        page_id: str | None = None,
        limit: int = 100,
    ) -> EventPage:
        """Search events matching the given filters."""

    @abstractmethod
    async def count_events(
        self,
        conversation_id__eq: UUID | None = None,
        kind__eq: EventKind | None = None,
        timestamp__gte: datetime | None = None,
        timestamp__lt: datetime | None = None,
        sort_order: EventSortOrder = EventSortOrder.TIMESTAMP,
    ) -> int:
        """Count events matching the given filters."""

    async def save_event(self, conversation_id: UUID, event: EventBase):
        """Save an event. Internal method intended not be part of the REST api"""

    async def batch_get_events(self, event_ids: list[str]) -> list[EventBase | None]:
        """Given a list of ids, get events (Or none for any which were not found)"""
        results = await asyncio.gather(
            *[self.get_event(event_id) for event_id in event_ids]
        )
        return results

    async def __aenter__(self) -> "EventContext":
        """Start using this service"""
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        """Stop using this service"""


class EventContextFactory(DiscriminatedUnionMixin, ABC):
    @abstractmethod
    async def with_instance(
        self, *args, **kwargs
    ) -> AsyncGenerator["EventContext", None]:
        """
        Get an instance of event context. Parameters are not specified
        so that they can be defined in the implementation classes and overridden using
        FastAPI's dependency injection. This allows merging global config with
        user / request specific variables.
        """
        yield EventContext()  # type: ignore
