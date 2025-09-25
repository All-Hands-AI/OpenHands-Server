from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID, uuid4

from pydantic import Field

from openhands.sdk import EventBase
from openhands.sdk.utils.models import DiscriminatedUnionMixin, OpenHandsModel
from openhands_server.utils.date_utils import utc_now


_logger = logging.getLogger(__name__)


class ConversationCallbackProcessor(DiscriminatedUnionMixin, ABC):
    @abstractmethod
    async def __call__(
        self,
        callback: ConversationCallback,
        event: EventBase,
    ) -> None:
        """
        Process a conversation event.

        Args:
            callback: The conversation callback wrapping this processor
            event: The triggering event
        """


class LoggingCallbackProcessor(ConversationCallbackProcessor):
    """Example implementation which logs callbacks"""

    async def __call__(
        self,
        callback: ConversationCallback,
        event: EventBase,
    ) -> None:
        _logger.info(f"Callback {callback.id} Invoked for event {event}")


class CreateConversationCallbackRequest(OpenHandsModel):
    conversation_id: UUID | None = None
    processor: ConversationCallbackProcessor
    event_kind: str | None = Field(
        default=None,
        description="Optional filter on the type of events for this callback",
    )


class ConversationCallback(CreateConversationCallbackRequest):
    id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=utc_now)


class ConversationCallbackPage(OpenHandsModel):
    items: list[ConversationCallback]
    next_page_id: str | None = None
