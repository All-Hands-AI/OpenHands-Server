from abc import ABC, abstractmethod
from uuid import UUID

from openhands.sdk import Message
from openhands.sdk.utils.async_utils import AsyncConversationCallback
from openhands_server.event.read_only_event_context import ReadOnlyEventContext


class EventContext(ReadOnlyEventContext, ABC):
    """Object for getting / updating event streams."""

    @abstractmethod
    async def send_message(self, message: Message):
        """Send a message to a conversation / agent"""

    @abstractmethod
    async def subscribe_to_events(self, callback: AsyncConversationCallback) -> UUID:
        """Subscribe to events in a conversation / agent"""

    @abstractmethod
    async def unsubscribe_from_events(self, callback_id: UUID) -> bool:
        """Unsubscribe from events in a conversation / agent"""

    # Lifecycle methods

    async def __aenter__(self):
        """Start using this event service"""
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        """Stop using this event service"""
