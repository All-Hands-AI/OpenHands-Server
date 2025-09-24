"""SQLAlchemy database models for conversation callbacks."""

from __future__ import annotations

import uuid

from sqlalchemy import JSON, UUID, Column, DateTime, String
from sqlalchemy.ext.hybrid import hybrid_property

from openhands_server.conversation_callback.conversation_callback_models import (
    ConversationCallback,
    ConversationCallbackProcessor,
    ConversationCallbackStatus,
)
from openhands_server.database import Base
from openhands_server.utils.date_utils import utc_now


class StoredConversationCallback(Base):
    """SQLAlchemy model for storing conversation callbacks."""

    __tablename__ = "conversation_callbacks"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    status = Column(String, nullable=False, index=True)
    conversation_id = Column(UUID, nullable=False, index=True)
    event_kind = Column(String, nullable=True, index=True)
    processor_data = Column(JSON, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
        index=True,
    )

    @hybrid_property
    def processor(self) -> ConversationCallbackProcessor:
        """
        Get the processor by deserializing from JSON.

        Returns:
            ConversationCallbackProcessor: The deserialized processor instance
        """
        if self.processor_data is None:
            raise ValueError("Processor data is None")

        # Use the DiscriminatedUnionMixin to deserialize the processor
        return ConversationCallbackProcessor.model_validate(self.processor_data)

    @processor.setter
    def processor(self, value: ConversationCallbackProcessor) -> None:
        """
        Set the processor by serializing to JSON.

        Args:
            value: The processor instance to serialize and store
        """
        if value is None:
            self.processor_data = None
        else:
            # Use the model_dump method to serialize the processor
            self.processor_data = value.model_dump()

    @hybrid_property
    def status_enum(self) -> ConversationCallbackStatus:
        """
        Get the status as an enum.

        Returns:
            ConversationCallbackStatus: The status enum value
        """
        return ConversationCallbackStatus(self.status)

    @status_enum.setter
    def status_enum(self, value: ConversationCallbackStatus) -> None:
        """
        Set the status from an enum.

        Args:
            value: The status enum value to set
        """
        self.status = value.value

    def to_pydantic(self) -> ConversationCallback:
        """
        Convert the SQLAlchemy model to a Pydantic model.

        Returns:
            ConversationCallback: The Pydantic model representation
        """
        return ConversationCallback(
            id=self.id,
            status=self.status_enum,
            conversation_id=self.conversation_id,
            processor=self.processor,
            event_kind=self.event_kind,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_pydantic(
        cls, callback: ConversationCallback
    ) -> StoredConversationCallback:
        """
        Create a SQLAlchemy model from a Pydantic model.

        Args:
            callback: The Pydantic ConversationCallback model

        Returns:
            StoredConversationCallback: The SQLAlchemy model instance
        """
        instance = cls(
            id=callback.id,
            status=callback.status.value,
            conversation_id=callback.conversation_id,
            event_kind=callback.event_kind,
            created_at=callback.created_at,
            updated_at=callback.updated_at,
        )
        instance.processor = callback.processor
        return instance
