"""SQLAlchemy database models for event callbacks."""

from __future__ import annotations

import json
import uuid

from pydantic import TypeAdapter
from sqlalchemy import UUID, Column, DateTime, String, Text

from openhands_server.database import Base
from openhands_server.event_callback.event_callback_models import (
    EventCallback,
    EventCallbackProcessor,
)
from openhands_server.utils.date_utils import utc_now


class StoredEventCallback(Base):
    """SQLAlchemy model for storing event callbacks."""

    __tablename__ = "event_callbacks"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID, nullable=True, index=True)
    processor_json = Column(Text, nullable=False)
    event_kind = Column(String, nullable=True, index=True)
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    def to_pydantic(self) -> EventCallback:
        """
        Convert the SQLAlchemy model to a Pydantic model.

        Returns:
            EventCallback: The Pydantic representation of the event callback
        """
        processor_data = json.loads(self.processor_json)  # type: ignore[arg-type]
        processor_adapter: TypeAdapter[EventCallbackProcessor] = TypeAdapter(
            EventCallbackProcessor
        )
        processor = processor_adapter.validate_python(processor_data)

        return EventCallback(
            id=self.id,  # type: ignore[arg-type]
            conversation_id=self.conversation_id,  # type: ignore[arg-type]
            processor=processor,
            event_kind=self.event_kind,  # type: ignore[arg-type]
            created_at=self.created_at,  # type: ignore[arg-type]
        )

    @classmethod
    def from_pydantic(cls, event_callback: EventCallback) -> "StoredEventCallback":
        """
        Create a SQLAlchemy model from a Pydantic model.

        Args:
            event_callback: The Pydantic event callback model

        Returns:
            StoredEventCallback: The SQLAlchemy representation
        """
        import json

        processor_json = json.dumps(event_callback.processor.model_dump())

        return cls(
            id=event_callback.id,
            conversation_id=event_callback.conversation_id,
            processor_json=processor_json,
            event_kind=event_callback.event_kind,
            created_at=event_callback.created_at,
        )
