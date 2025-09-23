from pydantic import BaseModel

from openhands.sdk import EventBase


class EventPage(BaseModel):
    items: list[EventBase]
    next_page_id: str | None = None
