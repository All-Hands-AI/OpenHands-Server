


from abc import ABC, abstractmethod
from uuid import UUID

from openhands.sdk import EventBase, Message
from openhands.sdk.utils.async_utils import AsyncConversationCallback

from openhands_server.event.event_models import EventPage


class ReadOnlyEventService(ABC):
    """ Service for getting events from a conversation which may not be running  """

    @abstractmethod
    async def get_event(self, event_id: str) -> EventBase | None:
        """ Get an event from a conversation """
        
    @abstractmethod
    async def search_events(self, page_id: str | None = None, limit: int = 100) -> EventPage:
        """ Search / List events from a conversation """

    async def batch_get_events(self, event_ids: list[str]) -> list[EventBase | None]:
        """Get a batch of events given their ids, returning None for any which were not found """
        results = []
        for event_id in event_ids:
            result = await self.get_event(event_id)
            results.append(result)
        return results

    # Lifecycle methods

    async def __aenter__(self):
        """Start using this event service"""

    async def __aexit__(self, exc_type, exc_value, traceback):
        """Stop using this event service"""
