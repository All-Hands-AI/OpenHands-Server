from abc import ABC, abstractmethod
from typing import Type
from uuid import UUID

from openhands.agent_server.models import EventPage, EventSortOrder
from openhands.sdk import EventBase
from openhands_server.config import get_global_config
from openhands_server.utils.import_utils import get_impl


class EventContext(ABC):
    """Event Context for getting events"""

    @abstractmethod
    async def get_event(self, event_id: str) -> EventBase | None:
        """Given an id, retrieve an event"""

    @abstractmethod
    async def search_events(
        self,
        page_id: str | None = None,
        limit: int = 100,
        kind: str | None = None,
        sort_order: EventSortOrder = EventSortOrder.TIMESTAMP,
    ) -> EventPage:
        """Search events matching the given filters."""

    @abstractmethod
    async def count_events(
        self,
        kind: str | None = None,
    ) -> int:
        """Count events matching the given filters."""

    @abstractmethod
    async def batch_get_events(self, event_ids: list[str]) -> list[EventBase | None]:
        """Given a list of ids, get events (Or none for any which were not found)"""

    @abstractmethod
    async def __aenter__(self, conversation_id: UUID):
        """Start using this service"""

    @abstractmethod
    async def __aexit__(self, exc_type, exc_value, traceback):
        """Stop using this service"""


_event_context_type: Type[EventContext] | None = None


def get_event_context_type() -> Type[EventContext]:
    global _event_context_type
    if _event_context_type is None:
        config = get_global_config()
        _event_context_type = get_impl(EventContext, config.event_context_type)
    return _event_context_type
