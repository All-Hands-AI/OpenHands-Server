from abc import ABC, abstractmethod
from uuid import UUID

from openhands.agent_server.models import (
    ConfirmationResponseRequest,
    EventPage,
    EventSortOrder,
)
from openhands.agent_server.pub_sub import Subscriber
from openhands.sdk import EventBase, Message
from openhands.sdk.conversation.secrets_manager import SecretValue
from openhands.sdk.security.confirmation_policy import ConfirmationPolicyBase


class EventService(ABC):
    """Read Only Event Service for getting events - which may be related to a conversation, and may or may not be running"""  # noqa: E501

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
    async def send_message(self, message: Message):
        """Send a message to a conversation"""

    @abstractmethod
    async def subscribe_to_events(self, subscriber: Subscriber) -> UUID:
        """Subscribe to events from a conversation"""

    @abstractmethod
    async def unsubscribe_from_events(self, subscriber_id: UUID) -> bool:
        """Unsubscribe to events from a conversation"""

    @abstractmethod
    async def start(self):
        """Start a conversation"""

    @abstractmethod
    async def run(self):
        """Run the conversation asynchronously."""

    @abstractmethod
    async def respond_to_confirmation(self, request: ConfirmationResponseRequest):
        """Respond to confirmation"""

    @abstractmethod
    async def pause(self):
        """Pause a conversation"""

    @abstractmethod
    async def update_secrets(self, secrets: dict[str, SecretValue]):
        """Update secrets in the conversation."""

    @abstractmethod
    async def set_confirmation_policy(self, policy: ConfirmationPolicyBase):
        """Set the confirmation policy for the conversation."""

    @abstractmethod
    async def close(self):
        """Close this event service."""

    @abstractmethod
    async def __aenter__(self, conversation_id: UUID):
        """Start using this service"""

    @abstractmethod
    async def __aexit__(self, exc_type, exc_value, traceback):
        """Stop using this service"""
