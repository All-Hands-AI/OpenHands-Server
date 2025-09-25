from enum import Enum

from openhands.sdk import EventBase
from openhands.sdk.utils.models import OpenHandsModel


class EventSortOrder(str, Enum):
    """Enum for event sorting options."""

    TIMESTAMP = "TIMESTAMP"
    TIMESTAMP_DESC = "TIMESTAMP_DESC"


class EventPage(OpenHandsModel):
    items: list[EventBase]
    next_page_id: str | None = None


class StoredConversation:
    """Placeholder for StoredConversation model."""
    pass